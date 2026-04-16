"""Governance Workflow for Knoss.

The Governance Workflow manages the review and approval process for
concepts, mappings, and relationships in the taxonomy.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..governance.concept_service import ConceptService, ConceptCreateInput
from ..governance.alias_service import AliasService, AliasCreateInput
from ..governance.mapping_review_service import MappingReviewService, MappingReviewInput
from ..governance.conflict_service import ConflictService
from ..models.types import ConceptStatus, MappingStatus
from ..repositories.models import Concept, EntityMapping, WorkflowRun


class GovernanceWorkflowInput(BaseModel):
    """Input payload for Governance Workflow.

    Attributes:
        article_id: Article ID for the governance review
        entities: Entities to govern
        auto_approve_threshold: Confidence threshold for auto-approval
        reviewer: Reviewer identifier
    """

    article_id: str = Field(description="Article ID for governance review")
    entities: list[dict[str, Any]] = Field(description="Entities to govern")
    auto_approve_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    reviewer: str = Field(default="system", description="Reviewer identifier")


class GovernanceWorkflowOutput(BaseModel):
    """Output payload for Governance Workflow.

    Attributes:
        article_id: The article ID
        concepts_created: Number of new concepts created
        mappings_approved: Number of mappings approved
        mappings_needing_review: Number of mappings needing review
        conflicts_detected: Number of conflicts detected
        workflow_run_id: The workflow run ID
    """

    article_id: str
    concepts_created: int
    mappings_approved: int
    mappings_needing_review: int
    conflicts_detected: int
    workflow_run_id: str


class GovernanceWorkflow:
    """Workflow that manages the governance review process.

    The Governance Workflow orchestrates:
    1. Conflict detection for entities and concepts
    2. Concept creation for new entities
    3. Mapping review and approval
    4. Alias management
    5. Quality queue management

    This ensures that all knowledge assets go through proper
    review before being used in downstream systems.
    """

    workflow_type: str = "governance"

    def __init__(self, session: Session):
        """Initialize the governance workflow.

        Args:
            session: SQLAlchemy ORM session
        """
        self.session = session
        self.concept_service = ConceptService(session)
        self.alias_service = AliasService(session)
        self.mapping_service = MappingReviewService(session)
        self.conflict_service = ConflictService(session)

    def execute(
        self,
        input_data: GovernanceWorkflowInput,
        workflow_run_id: str,
    ) -> tuple[GovernanceWorkflowOutput, list[str], dict[str, Any]]:
        """Execute the governance workflow.

        Args:
            input_data: Validated governance input
            workflow_run_id: ID of the workflow run

        Returns:
            Tuple of (output, warnings, metadata)
        """
        # Initialize workflow run
        self._init_workflow_run(workflow_run_id, input_data)

        warnings: list[str] = []
        metadata: dict[str, Any] = {
            "article_id": input_data.article_id,
            "reviewer": input_data.reviewer,
        }

        concepts_created = 0
        mappings_approved = 0
        mappings_needing_review = 0
        conflicts_detected = 0

        try:
            for entity_data in input_data.entities:
                entity_text = entity_data.get("entity_text")
                entity_type = entity_data.get("entity_type")
                candidate_name = entity_data.get("candidate_canonical_name", entity_text)
                confidence = entity_data.get("confidence", 0.7)

                # Check for conflicts
                conflicts = self.conflict_service.detect_entity_conflicts(entity_text)
                if conflicts:
                    conflicts_detected += len(conflicts)
                    warnings.append(f"Conflicts detected for entity '{entity_text}': {len(conflicts)}")

                # Determine mapping status based on confidence
                if confidence >= input_data.auto_approve_threshold:
                    # Auto-approve if confidence is high enough
                    mapping_status = MappingStatus.AUTO_ACCEPTED
                    mappings_approved += 1
                else:
                    # Needs human review
                    mapping_status = MappingStatus.NEEDS_REVIEW
                    mappings_needing_review += 1

                # Create or find concept
                concept = self.concept_service.get_concept_by_name(candidate_name)

                if not concept:
                    # Create new concept
                    category = self._infer_category(entity_type)
                    concept_input = ConceptCreateInput(
                        canonical_name=candidate_name,
                        category=category,
                        confidence=confidence,
                        source_note=f"Created from entity '{entity_text}' in article {input_data.article_id}",
                    )

                    concept = self.concept_service.create_concept(concept_input)
                    concepts_created += 1

                    # Add alias for original entity text
                    if entity_text != candidate_name:
                        self.alias_service.add_alias(
                            concept.id,
                            AliasCreateInput(
                                alias=entity_text,
                                alias_type="exact",
                                confidence=confidence,
                            ),
                        )

                # Create mapping
                mapping_input = MappingReviewInput(
                    entity_text=entity_text,
                    entity_type=entity_type,
                    candidate_concept_id=concept.id,
                    final_concept_id=concept.id if mapping_status == MappingStatus.AUTO_ACCEPTED else None,
                    mapping_status=mapping_status,
                    confidence=confidence,
                )

                self.mapping_service.create_mapping(input_data.article_id, mapping_input)

            # Complete workflow run
            self._complete_workflow_run(workflow_run_id, {
                "concepts_created": concepts_created,
                "mappings_approved": mappings_approved,
                "mappings_needing_review": mappings_needing_review,
                "conflicts_detected": conflicts_detected,
            })

            output = GovernanceWorkflowOutput(
                article_id=input_data.article_id,
                concepts_created=concepts_created,
                mappings_approved=mappings_approved,
                mappings_needing_review=mappings_needing_review,
                conflicts_detected=conflicts_detected,
                workflow_run_id=workflow_run_id,
            )

            metadata.update({
                "concepts_created": concepts_created,
                "mappings_approved": mappings_approved,
                "mappings_needing_review": mappings_needing_review,
                "conflicts_detected": conflicts_detected,
            })

            return output, warnings, metadata

        except Exception as e:
            self._fail_workflow_run(workflow_run_id, str(e))
            raise

    def _init_workflow_run(self, run_id: str, input_data: GovernanceWorkflowInput) -> None:
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
            status="running",
            metadata={"reviewer": input_data.reviewer},
        )
        self.session.add(run)
        self.session.flush()

    def _complete_workflow_run(self, run_id: str, stats: dict[str, int]) -> None:
        """Mark workflow run as completed.

        Args:
            run_id: Workflow run ID
            stats: Statistics to store
        """
        run = self.session.get(WorkflowRun, run_id)
        if run:
            run.status = "completed"
            run.completed_at = datetime.utcnow()
            run.metadata = stats
            self.session.flush()

    def _fail_workflow_run(self, run_id: str, error_message: str) -> None:
        """Mark workflow run as failed.

        Args:
            run_id: Workflow run ID
            error_message: Error message
        """
        run = self.session.get(WorkflowRun, run_id)
        if run:
            run.status = "failed"
            run.error_message = error_message
            run.completed_at = datetime.utcnow()
            self.session.flush()

    def _infer_category(self, entity_type: str) -> Any:
        """Infer concept category from entity type.

        Args:
            entity_type: Entity type string

        Returns:
            Inferred concept category
        """
        from ..models.types import ConceptCategory

        type_mapping = {
            "disease": ConceptCategory.DISEASE,
            "drug": ConceptCategory.DRUG,
            "marker": ConceptCategory.MARKER,
            "treatment": ConceptCategory.TREATMENT,
            "test": ConceptCategory.DIAGNOSIS,
        }

        return type_mapping.get(entity_type, ConceptCategory.DIAGNOSIS)

    def get_review_queue(
        self,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get items in the review queue.

        Args:
            limit: Maximum number of items

        Returns:
            List of items needing review
        """
        mappings = self.mapping_service.get_mappings_for_review(limit)

        return [
            {
                "mapping_id": m.id,
                "entity_text": m.entity_text,
                "entity_type": m.entity_type,
                "candidate_concept_id": m.candidate_concept_id,
                "confidence": m.confidence,
                "article_id": m.article_id,
            }
            for m in mappings
        ]


__all__ = [
    "GovernanceWorkflow",
    "GovernanceWorkflowInput",
    "GovernanceWorkflowOutput",
]
