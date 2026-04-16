"""Refinery Workflow for Knoss.

The Refinery Workflow orchestrates the knowledge extraction agents
to process raw articles through cleaning, segmentation, claim extraction,
entity extraction, and concept mapping.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..agents.base import Agent, AgentResult
from ..agents.cleaner import CleanerAgent, CleanerInput
from ..agents.segmenter import SegmenterAgent, SegmenterInput
from ..agents.claim_extractor import ClaimExtractorAgent, ClaimExtractorInput
from ..agents.entity_extractor import EntityExtractorAgent, EntityExtractorInput
from ..agents.concept_mapper import ConceptMapperAgent, ConceptMapperInput
from ..models.payloads import WorkflowStateModel
from ..models.types import WorkflowStatus
from ..repositories.models import WorkflowRun


class RefineryWorkflowInput(BaseModel):
    """Input payload for Refinery Workflow.

    Attributes:
        article_id: Unique identifier for the article
        title: Article title
        raw_html: Raw HTML content (optional)
        raw_text: Plain text content
        enable_governance: Enable governance integration
    """

    article_id: str = Field(description="Unique identifier for the article")
    title: str = Field(description="Article title")
    raw_html: str | None = Field(default=None, description="Raw HTML content")
    raw_text: str = Field(description="Plain text content")
    enable_governance: bool = Field(default=True, description="Enable governance integration")


class RefineryWorkflowOutput(BaseModel):
    """Output payload for Refinery Workflow.

    Attributes:
        article_id: The processed article ID
        segment_count: Number of segments created
        claim_count: Number of claims extracted
        entity_count: Number of entities detected
        concept_count: Number of concepts assigned
        governed_entity_count: Number of entities with reviewed concepts
        ungoverned_entity_count: Number of entities needing review
        workflow_run_id: The workflow run ID
    """

    article_id: str
    segment_count: int
    claim_count: int
    entity_count: int
    concept_count: int
    governed_entity_count: int = 0
    ungoverned_entity_count: int = 0
    workflow_run_id: str


InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class Workflow(Generic[InputT, OutputT]):
    """Base class for Knoss workflows.

    Workflows orchestrate multiple agents in sequence to achieve
    complex knowledge extraction and governance tasks.
    """

    workflow_type: str = "base"

    def __init__(self, session: Session):
        """Initialize the workflow.

        Args:
            session: SQLAlchemy ORM session
        """
        self.session = session

    def execute(
        self,
        input_data: InputT,
        workflow_run_id: str,
    ) -> tuple[OutputT, list[str], dict[str, Any]]:
        """Execute the workflow.

        Args:
            input_data: Validated workflow input
            workflow_run_id: Workflow run ID for tracking

        Returns:
            Tuple of (output, warnings, metadata)
        """
        raise NotImplementedError("Subclasses must implement execute()")


class RefineryWorkflow(Workflow[RefineryWorkflowInput, RefineryWorkflowOutput]):
    """Workflow that processes raw articles through the refinery pipeline.

    The Refinery Workflow orchestrates:
    1. Cleaner Agent - removes ads, QR prompts, signatures
    2. Segmenter Agent - splits into structural/semantic segments
    3. Claim Extractor Agent - extracts atomic medical claims
    4. Entity Extractor Agent - detects and normalizes medical terminology
    5. Concept Mapper Agent - assigns concepts to taxonomy

    The workflow maintains full state for resumption and traceability.
    """

    workflow_type: str = "refinery"

    # Stage constants
    STAGE_CLEANING = "cleaning"
    STAGE_SEGMENTING = "segmenting"
    STAGE_CLAIMS = "claims"
    STAGE_TERMINOLOGY = "terminology"
    STAGE_TAXONOMY = "taxonomy"

    def __init__(self, session: Session):
        """Initialize the refinery workflow.

        Args:
            session: SQLAlchemy ORM session
        """
        super().__init__(session)
        self.cleaner = CleanerAgent()
        self.segmenter = SegmenterAgent()
        self.claim_extractor = ClaimExtractorAgent()
        self.entity_extractor = EntityExtractorAgent()
        self.concept_mapper = ConceptMapperAgent()

    def execute(
        self,
        input_data: RefineryWorkflowInput,
        workflow_run_id: str,
    ) -> tuple[RefineryWorkflowOutput, list[str], dict[str, Any]]:
        """Execute the refinery workflow.

        Args:
            input_data: Validated refinery input
            workflow_run_id: ID of the workflow run

        Returns:
            Tuple of (output, warnings, metadata)
        """
        # Initialize workflow run
        self._init_workflow_run(workflow_run_id, input_data)

        started_at = datetime.utcnow()
        warnings: list[str] = []
        metadata: dict[str, Any] = {
            "article_id": input_data.article_id,
            "governance_enabled": input_data.enable_governance,
        }

        # Initialize state
        state = WorkflowStateModel(
            workflow_run_id=workflow_run_id,
            workflow_type=self.workflow_type,
            target_type="article",
            target_id=input_data.article_id,
            status="running",
            article={"id": input_data.article_id, "title": input_data.title},
        )

        try:
            # Stage 1: Cleaning
            state, stage_warnings = self._run_cleaning_stage(state, input_data)
            warnings.extend(stage_warnings)
            self._update_workflow_stage(workflow_run_id, self.STAGE_CLEANING, "completed")

            # Stage 2: Segmenting
            state, stage_warnings = self._run_segmenting_stage(state)
            warnings.extend(stage_warnings)
            self._update_workflow_stage(workflow_run_id, self.STAGE_SEGMENTING, "completed")

            # Stage 3: Claim Extraction
            state, stage_warnings = self._run_claims_stage(state)
            warnings.extend(stage_warnings)
            self._update_workflow_stage(workflow_run_id, self.STAGE_CLAIMS, "completed")

            # Stage 4: Entity Extraction
            state, stage_warnings = self._run_terminology_stage(state)
            warnings.extend(stage_warnings)
            self._update_workflow_stage(workflow_run_id, self.STAGE_TERMINOLOGY, "completed")

            # Stage 5: Concept Mapping
            state, stage_warnings = self._run_taxonomy_stage(state)
            warnings.extend(stage_warnings)
            self._update_workflow_stage(workflow_run_id, self.STAGE_TAXONOMY, "completed")

            # Update workflow run as completed
            self._complete_workflow_run(workflow_run_id, state)

            # Create output
            output = RefineryWorkflowOutput(
                article_id=input_data.article_id,
                segment_count=len(state.segments),
                claim_count=len(state.claims),
                entity_count=len(state.entities),
                concept_count=len(state.concepts),
                ungoverned_entities=state.ungoverned_entities,
                ungoverned_entity_count=len(state.ungoverned_entities),
                workflow_run_id=workflow_run_id,
            )

            metadata.update({
                "segment_count": len(state.segments),
                "claim_count": len(state.claims),
                "entity_count": len(state.entities),
                "concept_count": len(state.concepts),
            })

            return output, warnings, metadata

        except Exception as e:
            self._fail_workflow_run(workflow_run_id, str(e))
            raise

    def _init_workflow_run(self, run_id: str, input_data: RefineryWorkflowInput) -> None:
        """Initialize workflow run in database.

        Args:
            run_id: Workflow run ID
            input_data: Input data
        """
        run = WorkflowRun(
            id=run_id,
            workflow_type=self.workflow_type,
            target_type="article",
            target_id=input_data.article_id,
            status=WorkflowStatus.RUNNING.value,
            metadata={"article_title": input_data.title},
        )
        self.session.add(run)
        self.session.flush()

    def _update_workflow_stage(
        self,
        run_id: str,
        stage: str,
        status: str,
    ) -> None:
        """Update workflow stage status.

        Args:
            run_id: Workflow run ID
            stage: Stage name
            status: Stage status
        """
        run = self.session.get(WorkflowRun, run_id)
        if run:
            run.stage = stage
            self.session.flush()

    def _complete_workflow_run(self, run_id: str, state: WorkflowStateModel) -> None:
        """Mark workflow run as completed.

        Args:
            run_id: Workflow run ID
            state: Final workflow state
        """
        run = self.session.get(WorkflowRun, run_id)
        if run:
            run.status = WorkflowStatus.COMPLETED.value
            run.completed_at = datetime.utcnow()
            run.metadata = {
                "segment_count": len(state.segments),
                "claim_count": len(state.claims),
                "entity_count": len(state.entities),
                "concept_count": len(state.concepts),
            }
            self.session.flush()

    def _fail_workflow_run(self, run_id: str, error_message: str) -> None:
        """Mark workflow run as failed.

        Args:
            run_id: Workflow run ID
            error_message: Error message
        """
        run = self.session.get(WorkflowRun, run_id)
        if run:
            run.status = WorkflowStatus.FAILED.value
            run.error_message = error_message
            run.completed_at = datetime.utcnow()
            self.session.flush()

    def _run_cleaning_stage(
        self,
        state: WorkflowStateModel,
        input_data: RefineryWorkflowInput,
    ) -> tuple[WorkflowStateModel, list[str]]:
        """Run the cleaning stage.

        Args:
            state: Current workflow state
            input_data: Original input data

        Returns:
            Tuple of (updated state, warnings)
        """
        warnings = []

        cleaner_input = CleanerInput(
            article_id=input_data.article_id,
            title=input_data.title,
            raw_html=input_data.raw_html,
            raw_text=input_data.raw_text,
        )

        result = self.cleaner.run(cleaner_input.model_dump())

        if result.success:
            state.cleaning = {
                "clean_text": result.output.clean_text,
                "removed_blocks": [b.model_dump() for b in result.output.removed_blocks],
                "preserved_structure_blocks": [b.model_dump() for b in result.output.preserved_structure_blocks],
            }
            warnings.extend(result.warnings)
        else:
            raise Exception(f"Cleaning stage failed: {result.error}")

        return state, warnings

    def _run_segmenting_stage(
        self,
        state: WorkflowStateModel,
    ) -> tuple[WorkflowStateModel, list[str]]:
        """Run the segmenting stage.

        Args:
            state: Current workflow state

        Returns:
            Tuple of (updated state, warnings)
        """
        warnings = []

        segmenter_input = SegmenterInput(
            article_id=state.article["id"],
            title=state.article.get("title", ""),
            clean_text=state.cleaning["clean_text"],
            preserved_structure_blocks=state.cleaning["preserved_structure_blocks"],
        )

        result = self.segmenter.run(segmenter_input.model_dump())

        if result.success:
            state.segments = [s.model_dump() for s in result.output.segments]
            warnings.extend(result.warnings)
        else:
            raise Exception(f"Segmenting stage failed: {result.error}")

        return state, warnings

    def _run_claims_stage(
        self,
        state: WorkflowStateModel,
    ) -> tuple[WorkflowStateModel, list[str]]:
        """Run the claim extraction stage.

        Args:
            state: Current workflow state

        Returns:
            Tuple of (updated state, warnings)
        """
        warnings = []

        for segment in state.segments:
            if segment.get("is_noise"):
                continue

            claim_input = ClaimExtractorInput(
                article_id=state.article["id"],
                segment=segment,
                existing_claims=state.claims,
            )

            result = self.claim_extractor.run(claim_input.model_dump())

            if result.success:
                state.claims.extend([c.model_dump() for c in result.output.claims])
                warnings.extend(result.warnings)

        return state, warnings

    def _run_terminology_stage(
        self,
        state: WorkflowStateModel,
    ) -> tuple[WorkflowStateModel, list[str]]:
        """Run the entity extraction stage.

        Args:
            state: Current workflow state

        Returns:
            Tuple of (updated state, warnings)
        """
        warnings = []

        for segment in state.segments:
            if segment.get("is_noise"):
                continue

            # Find claims for this segment
            segment_claims = [c for c in state.claims if c.get("segment_id") == segment.get("id")]

            entity_input = EntityExtractorInput(
                article_id=state.article["id"],
                segment=segment,
                claims=segment_claims,
            )

            result = self.entity_extractor.run(entity_input.model_dump())

            if result.success:
                state.entities.extend([e.model_dump() for e in result.output.entities])
                warnings.extend(result.warnings)

        return state, warnings

    def _run_taxonomy_stage(
        self,
        state: WorkflowStateModel,
    ) -> tuple[WorkflowStateModel, list[str]]:
        """Run the concept mapping stage.

        Args:
            state: Current workflow state

        Returns:
            Tuple of (updated state, warnings)
        """
        warnings = []

        concept_input = ConceptMapperInput(
            article_id=state.article["id"],
            claims=state.claims,
            entities=state.entities,
        )

        result = self.concept_mapper.run(concept_input.model_dump())

        if result.success:
            state.concepts = [c.model_dump() for c in result.output.concepts]
            warnings.extend(result.warnings)

        return state, warnings


__all__ = [
    "RefineryWorkflow",
    "RefineryWorkflowInput",
    "RefineryWorkflowOutput",
    "Workflow",
]
