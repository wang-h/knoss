"""Mapping Review Service for Knoss governance.

This service provides operations for managing the entity-to-concept
mapping review workflow.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..models.types import MappingStatus
from ..repositories.models import EntityMapping, Concept


class MappingReviewInput(BaseModel):
    """Input for reviewing an entity mapping."""
    entity_text: str = Field(description="Entity text")
    entity_type: str = Field(description="Entity type")
    candidate_concept_id: Optional[str] = Field(default=None, description="Candidate concept ID")
    final_concept_id: Optional[str] = Field(default=None, description="Final confirmed concept ID")
    mapping_status: MappingStatus = Field(description="Mapping status")
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    reviewer_note: Optional[str] = Field(default=None)


class MappingBatchInput(BaseModel):
    """Input for batch mapping review."""
    mappings: list[MappingReviewInput] = Field(description="List of mappings to review")
    reviewer: str = Field(default="system", description="Reviewer identifier")


class MappingReviewService:
    """Service for managing entity mapping reviews.

    This service provides operations for the mapping review workflow,
    including creating, updating, and approving entity-to-concept mappings.
    """

    def __init__(self, session: Session):
        """Initialize the mapping review service.

        Args:
            session: SQLAlchemy ORM session
        """
        self.session = session

    def create_mapping(
        self,
        article_id: str,
        input_data: MappingReviewInput,
    ) -> Optional[EntityMapping]:
        """Create a new entity mapping.

        Args:
            article_id: Source article ID
            input_data: Mapping creation input

        Returns:
            Created mapping if concept exists, None otherwise
        """
        # Verify concept exists if provided
        concept_id = input_data.final_concept_id or input_data.candidate_concept_id
        if concept_id:
            concept = self.session.get(Concept, concept_id)
            if not concept:
                return None

        # Check for existing mapping
        existing = self.session.query(EntityMapping).filter_by(
            entity_text=input_data.entity_text,
            article_id=article_id,
        ).first()

        if existing:
            # Update existing mapping
            existing.candidate_concept_id = input_data.candidate_concept_id
            existing.final_concept_id = input_data.final_concept_id
            existing.mapping_status = input_data.mapping_status.value
            existing.confidence = input_data.confidence
            existing.reviewed_at = datetime.utcnow()
            self.session.flush()
            return existing

        # Create new mapping
        mapping = EntityMapping(
            id=f"map_{uuid.uuid4().hex[:8]}",
            entity_text=input_data.entity_text,
            entity_type=input_data.entity_type,
            article_id=article_id,
            candidate_concept_id=input_data.candidate_concept_id,
            final_concept_id=input_data.final_concept_id,
            mapping_status=input_data.mapping_status.value,
            confidence=input_data.confidence,
            reviewer_note=input_data.reviewer_note,
            created_at=datetime.utcnow(),
        )

        self.session.add(mapping)
        self.session.flush()

        return mapping

    def get_mapping(self, mapping_id: str) -> Optional[EntityMapping]:
        """Get a mapping by ID.

        Args:
            mapping_id: Mapping ID

        Returns:
            Mapping if found, None otherwise
        """
        return self.session.get(EntityMapping, mapping_id)

    def get_mappings_for_review(
        self,
        limit: int = 100,
    ) -> list[EntityMapping]:
        """Get mappings that need review.

        Args:
            limit: Max results

        Returns:
            List of mappings needing review
        """
        return self.session.query(EntityMapping).filter(
            EntityMapping.mapping_status == MappingStatus.NEEDS_REVIEW.value
        ).order_by(
            EntityMapping.confidence.desc(),
            EntityMapping.created_at.desc(),
        ).limit(limit).all()

    def get_mappings_for_entity(
        self,
        entity_text: str,
    ) -> list[EntityMapping]:
        """Get all mappings for an entity.

        Args:
            entity_text: Entity text

        Returns:
            List of mappings
        """
        return self.session.query(EntityMapping).filter_by(
            entity_text=entity_text
        ).order_by(
            EntityMapping.created_at.desc()
        ).all()

    def approve_mapping(
        self,
        mapping_id: str,
        final_concept_id: str,
        reviewer: str = "human",
    ) -> Optional[EntityMapping]:
        """Approve a mapping with final concept.

        Args:
            mapping_id: Mapping ID
            final_concept_id: Final confirmed concept ID
            reviewer: Reviewer identifier

        Returns:
            Updated mapping if found, None otherwise
        """
        mapping = self.get_mapping(mapping_id)
        if not mapping:
            return None

        # Verify concept exists
        concept = self.session.get(Concept, final_concept_id)
        if not concept:
            return None

        mapping.final_concept_id = final_concept_id
        mapping.mapping_status = MappingStatus.HUMAN_CONFIRMED.value
        mapping.reviewed_by = reviewer
        mapping.reviewed_at = datetime.utcnow()

        self.session.flush()

        return mapping

    def reject_mapping(
        self,
        mapping_id: str,
        reason: Optional[str] = None,
        reviewer: str = "human",
    ) -> Optional[EntityMapping]:
        """Reject a mapping.

        Args:
            mapping_id: Mapping ID
            reason: Optional rejection reason
            reviewer: Reviewer identifier

        Returns:
            Updated mapping if found, None otherwise
        """
        mapping = self.get_mapping(mapping_id)
        if not mapping:
            return None

        mapping.mapping_status = MappingStatus.REJECTED.value
        mapping.reviewed_by = reviewer
        mapping.reviewed_at = datetime.utcnow()
        mapping.reviewer_note = reason

        self.session.flush()

        return mapping

    def batch_review(
        self,
        article_id: str,
        input_data: MappingBatchInput,
    ) -> dict[str, Any]:
        """Batch review multiple mappings.

        Args:
            article_id: Source article ID
            input_data: Batch review input

        Returns:
            Summary of batch review results
        """
        created = 0
        updated = 0
        failed = 0

        for mapping_input in input_data.mappings:
            try:
                existing = self.session.query(EntityMapping).filter_by(
                    entity_text=mapping_input.entity_text,
                    article_id=article_id,
                ).first()

                if existing:
                    # Update existing
                    existing.candidate_concept_id = mapping_input.candidate_concept_id
                    existing.final_concept_id = mapping_input.final_concept_id
                    existing.mapping_status = mapping_input.mapping_status.value
                    existing.confidence = mapping_input.confidence
                    existing.reviewed_by = input_data.reviewer
                    existing.reviewed_at = datetime.utcnow()
                    updated += 1
                else:
                    # Create new
                    mapping = EntityMapping(
                        id=f"map_{uuid.uuid4().hex[:8]}",
                        entity_text=mapping_input.entity_text,
                        entity_type=mapping_input.entity_type,
                        article_id=article_id,
                        candidate_concept_id=mapping_input.candidate_concept_id,
                        final_concept_id=mapping_input.final_concept_id,
                        mapping_status=mapping_input.mapping_status.value,
                        confidence=mapping_input.confidence,
                        reviewer_note=mapping_input.reviewer_note,
                        reviewed_by=input_data.reviewer,
                        created_at=datetime.utcnow(),
                        reviewed_at=datetime.utcnow(),
                    )
                    self.session.add(mapping)
                    created += 1

            except Exception:
                failed += 1

        self.session.flush()

        return {
            "created": created,
            "updated": updated,
            "failed": failed,
            "total": len(input_data.mappings),
        }

    def get_review_statistics(self) -> dict[str, Any]:
        """Get mapping review statistics.

        Returns:
            Dictionary with review statistics
        """
        total = self.session.query(EntityMapping).count()

        by_status = {}
        for status in MappingStatus:
            count = self.session.query(EntityMapping).filter_by(
                mapping_status=status.value
            ).count()
            by_status[status.value] = count

        return {
            "total_mappings": total,
            "by_status": by_status,
        }


__all__ = [
    "MappingReviewService",
    "MappingReviewInput",
    "MappingBatchInput",
]
