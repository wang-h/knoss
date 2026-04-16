"""Taxonomy Assigner Agent implementation for Knoss.

The Taxonomy Assigner Agent integrates taxonomy governance with concept mapping,
ensuring that reviewed concepts are prioritized over raw entities.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..models.payloads import ClaimModel, ConceptModel, EntityModel
from ..models.types import ConceptStatus, MappingStatus
from .base import Agent, AgentResult
from .concept_mapper import ConceptMapperAgent, ConceptMapperInput, ConceptMapperOutput


class TaxonomyAssignerInput(BaseModel):
    """Input payload for Taxonomy Assigner Agent.

    Attributes:
        article_id: Unique identifier for the article
        claims: Claims to assign concepts to
        entities: Entities extracted from claims
        enable_governance: Enable governance integration
        session: Database session for governance lookup (optional)
    """

    article_id: str = Field(description="Unique identifier for the article")
    claims: list[dict[str, Any] | ClaimModel] = Field(
        default_factory=list,
        description="Claims to assign concepts to",
    )
    entities: list[dict[str, Any] | EntityModel] = Field(
        default_factory=list,
        description="Entities extracted from claims",
    )
    enable_governance: bool = Field(
        default=True,
        description="Enable governance integration for reviewed concepts",
    )
    concept_dictionary_snapshot: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Concept dictionary snapshot for matching",
    )


class TaxonomyAssignerOutput(BaseModel):
    """Output payload for Taxonomy Assigner Agent.

    Attributes:
        concepts: List of concepts with governance status
        governed_entities: Entities with reviewed concept mappings
        ungoverned_entities: Entities needing governance review
    """

    concepts: list[ConceptModel] = Field(default_factory=list)
    governed_entities: list[dict[str, Any]] = Field(default_factory=list)
    ungoverned_entities: list[dict[str, Any]] = Field(default_factory=list)


class GovernedConcept:
    """A concept that has been through taxonomy governance."""

    def __init__(
        self,
        concept_id: str,
        canonical_name: str,
        category: str,
        status: str,
        patient_friendly_name: Optional[str] = None,
        patient_friendly_explanation: Optional[str] = None,
        aliases: list[str] = None,
        relations: list[dict[str, Any]] = None,
        is_reviewed: bool = True,
        mapping_source: str = "reviewed",
    ):
        self.concept_id = concept_id
        self.canonical_name = canonical_name
        self.category = category
        self.status = status
        self.patient_friendly_name = patient_friendly_name
        self.patient_friendly_explanation = patient_friendly_explanation
        self.aliases = aliases or []
        self.relations = relations or []
        self.is_reviewed = is_reviewed
        self.mapping_source = mapping_source


class TaxonomyAssignerAgent(ConceptMapperAgent):
    """Agent that assigns concepts with governance integration.

    The Taxonomy Assigner Agent extends Concept Mapper with:
    1. Governance service integration for reviewed concept lookup
    2. Prioritization of reviewed concepts over raw entities
    3. Tracking of governed vs ungoverned entities
    4. Fallback warnings when governance fails

    This ensures downstream processes use the highest quality
    concept mappings available.
    """

    input_model = TaxonomyAssignerInput
    output_model = TaxonomyAssignerOutput

    def __init__(self, session: Optional[Session] = None):
        """Initialize the taxonomy assigner.

        Args:
            session: Optional database session for governance lookup
        """
        super().__init__()
        self.session = session
        self._governance_warnings: list[str] = []

    def execute(self, input_data: TaxonomyAssignerInput) -> AgentResult:
        """Execute concept assignment with governance.

        Args:
            input_data: Validated input with claims and entities

        Returns:
            AgentResult with concepts and governance status
        """
        warnings = []
        metadata = {"article_id": input_data.article_id, "governance_enabled": input_data.enable_governance}

        # First, run the base concept mapping
        mapper_input = ConceptMapperInput(
            article_id=input_data.article_id,
            claims=input_data.claims,
            entities=input_data.entities,
            concept_dictionary_snapshot=input_data.concept_dictionary_snapshot,
        )

        mapper_result = super().execute(mapper_input)
        if not mapper_result.success:
            return AgentResult.fail(
                f"Concept mapping failed: {mapper_result.error}",
                warnings=mapper_result.warnings,
            )

        concepts = mapper_result.output.concepts
        warnings.extend(mapper_result.warnings)

        # Then apply governance if enabled
        governed_entities = []
        ungoverned_entities = []

        if input_data.enable_governance and self.session:
            governed_entities, ungoverned_entities, governance_warnings = self._apply_governance(
                input_data.entities,
                input_data.article_id,
            )
            warnings.extend(governance_warnings)
            metadata["governed_count"] = len(governed_entities)
            metadata["ungoverned_count"] = len(ungoverned_entities)
        else:
            # Mark all entities as ungoverned if governance is disabled
            entities = self._parse_entities(input_data.entities)
            ungoverned_entities = [
                {
                    "entity_text": e.entity_text,
                    "entity_type": e.entity_type,
                    "reason": "governance_disabled",
                }
                for e in entities
            ]

        return AgentResult.ok(
            output=TaxonomyAssignerOutput(
                concepts=concepts,
                governed_entities=governed_entities,
                ungoverned_entities=ungoverned_entities,
            ),
            warnings=warnings,
            metadata=metadata,
        )

    def _apply_governance(
        self,
        entities: list[dict[str, Any] | EntityModel],
        article_id: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        """Apply governance to entity mappings.

        Args:
            entities: List of entities to govern
            article_id: Article ID for context

        Returns:
            Tuple of (governed entities, ungoverned entities, warnings)
        """
        from ..repositories.models import EntityMapping, Concept

        governed = []
        ungoverned = []
        warnings = []

        parsed_entities = []
        for e in entities:
            if isinstance(e, EntityModel):
                parsed_entities.append(e)
            else:
                parsed_entities.append(EntityModel.model_validate(e))

        for entity in parsed_entities:
            entity_text = entity.entity_text

            # Try to find human-confirmed mapping first
            confirmed_mapping = self.session.query(EntityMapping).filter_by(
                entity_text=entity_text,
                mapping_status=MappingStatus.HUMAN_CONFIRMED.value,
            ).first()

            if confirmed_mapping:
                concept = self.session.get(Concept, confirmed_mapping.final_concept_id)
                if concept:
                    governed.append(self._create_governed_entity(entity, concept, "human_confirmed"))
                    continue

            # Try to find auto-accepted mapping with active concept
            auto_mapping = self.session.query(EntityMapping).filter_by(
                entity_text=entity_text,
                mapping_status=MappingStatus.AUTO_ACCEPTED.value,
            ).first()

            if auto_mapping:
                concept_id = auto_mapping.final_concept_id or auto_mapping.candidate_concept_id
                concept = self.session.get(Concept, concept_id)
                if concept and concept.status == ConceptStatus.ACTIVE.value:
                    governed.append(self._create_governed_entity(entity, concept, "auto_accepted"))
                    continue

            # Try direct name match
            concept = self.session.query(Concept).filter_by(
                canonical_name=entity_text,
                status=ConceptStatus.ACTIVE.value,
            ).first()

            if concept:
                governed.append(self._create_governed_entity(entity, concept, "direct_match"))
                continue

            # No reviewed concept found
            ungoverned.append({
                "entity_text": entity_text,
                "entity_type": entity.entity_type,
                "reason": "no_reviewed_concept",
                "suggestion": "Submit for taxonomy review",
            })

        return governed, ungoverned, warnings

    def _create_governed_entity(
        self,
        entity: EntityModel,
        concept: Any,
        mapping_source: str,
    ) -> dict[str, Any]:
        """Create a governed entity record.

        Args:
            entity: The original entity
            concept: The governed concept
            mapping_source: Source of the mapping

        Returns:
            Governed entity dictionary
        """
        return {
            "entity_text": entity.entity_text,
            "entity_type": entity.entity_type,
            "concept_id": concept.id,
            "canonical_name": concept.canonical_name,
            "category": concept.category,
            "is_reviewed": concept.status == ConceptStatus.ACTIVE.value,
            "mapping_source": mapping_source,
        }

    def _parse_entities(
        self,
        entities: list[dict[str, Any] | EntityModel],
    ) -> list[EntityModel]:
        """Parse entities from input.

        Args:
            entities: List of entities from input

        Returns:
            List of validated EntityModel instances
        """
        parsed = []
        for entity in entities:
            if isinstance(entity, EntityModel):
                parsed.append(entity)
            else:
                parsed.append(EntityModel.model_validate(entity))
        return parsed


__all__ = [
    "TaxonomyAssignerAgent",
    "TaxonomyAssignerInput",
    "TaxonomyAssignerOutput",
    "GovernedConcept",
]
