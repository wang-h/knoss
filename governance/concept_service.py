"""Concept Service for Knoss governance.

This service provides operations for managing canonical concepts
in the taxonomy registry.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..models.types import ConceptCategory, ConceptStatus
from ..repositories.models import Concept, ConceptAlias, ConceptChangeLog


class ConceptCreateInput(BaseModel):
    """Input for creating a new concept."""
    canonical_name: str = Field(description="Standard name for the concept")
    category: ConceptCategory = Field(description="Concept category")
    patient_friendly_name: Optional[str] = Field(default=None, description="Patient-friendly name")
    patient_friendly_explanation: Optional[str] = Field(default=None, description="Patient-friendly explanation")
    source_note: Optional[str] = Field(default=None, description="Source or provenance note")
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class ConceptUpdateInput(BaseModel):
    """Input for updating an existing concept."""
    canonical_name: Optional[str] = Field(default=None)
    patient_friendly_name: Optional[str] = Field(default=None)
    patient_friendly_explanation: Optional[str] = Field(default=None)
    status: Optional[ConceptStatus] = Field(default=None)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    source_note: Optional[str] = Field(default=None)


class ConceptService:
    """Service for managing canonical concepts.

    This service provides CRUD operations for concepts in the
    taxonomy registry, including version tracking and change logging.
    """

    def __init__(self, session: Session):
        """Initialize the concept service.

        Args:
            session: SQLAlchemy ORM session
        """
        self.session = session

    def create_concept(self, input_data: ConceptCreateInput) -> Concept:
        """Create a new canonical concept.

        Args:
            input_data: Concept creation input

        Returns:
            Created concept
        """
        concept_id = f"concept_{uuid.uuid4().hex[:8]}"

        concept = Concept(
            id=concept_id,
            canonical_name=input_data.canonical_name,
            category=input_data.category.value,
            patient_friendly_name=input_data.patient_friendly_name,
            patient_friendly_explanation=input_data.patient_friendly_explanation,
            status=ConceptStatus.DRAFT.value,
            source_note=input_data.source_note,
            confidence=input_data.confidence,
            version=1,
        )

        self.session.add(concept)
        self.session.flush()

        # Log creation
        self._log_change(
            concept_id=concept.id,
            change_type="create",
            after_json=self._concept_to_dict(concept),
            operator="system",
            change_note=f"Created concept: {input_data.canonical_name}",
        )

        return concept

    def get_concept(self, concept_id: str) -> Optional[Concept]:
        """Get a concept by ID.

        Args:
            concept_id: Concept ID

        Returns:
            Concept if found, None otherwise
        """
        return self.session.get(Concept, concept_id)

    def get_concept_by_name(self, canonical_name: str) -> Optional[Concept]:
        """Get a concept by canonical name.

        Args:
            canonical_name: Canonical name

        Returns:
            Concept if found, None otherwise
        """
        return self.session.query(Concept).filter_by(
            canonical_name=canonical_name
        ).first()

    def list_concepts(
        self,
        category: Optional[ConceptCategory] = None,
        status: Optional[ConceptStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Concept]:
        """List concepts with optional filtering.

        Args:
            category: Filter by category
            status: Filter by status
            limit: Max results
            offset: Results offset

        Returns:
            List of concepts
        """
        query = self.session.query(Concept)

        if category:
            query = query.filter(Concept.category == category.value)
        if status:
            query = query.filter(Concept.status == status.value)

        return query.order_by(Concept.created_at.desc()).offset(offset).limit(limit).all()

    def update_concept(self, concept_id: str, input_data: ConceptUpdateInput) -> Optional[Concept]:
        """Update an existing concept.

        Args:
            concept_id: Concept ID
            input_data: Update input data

        Returns:
            Updated concept if found, None otherwise
        """
        concept = self.get_concept(concept_id)
        if not concept:
            return None

        before_json = self._concept_to_dict(concept)

        # Update fields
        if input_data.canonical_name is not None:
            concept.canonical_name = input_data.canonical_name
        if input_data.patient_friendly_name is not None:
            concept.patient_friendly_name = input_data.patient_friendly_name
        if input_data.patient_friendly_explanation is not None:
            concept.patient_friendly_explanation = input_data.patient_friendly_explanation
        if input_data.status is not None:
            concept.status = input_data.status.value
        if input_data.confidence is not None:
            concept.confidence = input_data.confidence
        if input_data.source_note is not None:
            concept.source_note = input_data.source_note

        concept.version += 1
        concept.updated_at = datetime.utcnow()

        self.session.flush()

        # Log update
        self._log_change(
            concept_id=concept.id,
            change_type="update",
            before_json=before_json,
            after_json=self._concept_to_dict(concept),
            operator="system",
            change_note=f"Updated concept to version {concept.version}",
        )

        return concept

    def activate_concept(self, concept_id: str) -> Optional[Concept]:
        """Activate a concept (mark as reviewed and active).

        Args:
            concept_id: Concept ID

        Returns:
            Updated concept if found, None otherwise
        """
        return self.update_concept(
            concept_id,
            ConceptUpdateInput(status=ConceptStatus.ACTIVE),
        )

    def deprecate_concept(self, concept_id: str, reason: Optional[str] = None) -> Optional[Concept]:
        """Deprecate a concept.

        Args:
            concept_id: Concept ID
            reason: Optional reason for deprecation

        Returns:
            Updated concept if found, None otherwise
        """
        concept = self.update_concept(
            concept_id,
            ConceptUpdateInput(status=ConceptStatus.DEPRECATED),
        )
        if concept and reason:
            concept.source_note = f"Deprecated: {reason}"
            self.session.flush()

        return concept

    def search_concepts(
        self,
        query: str,
        category: Optional[ConceptCategory] = None,
        limit: int = 20,
    ) -> list[Concept]:
        """Search concepts by name or alias.

        Args:
            query: Search query string
            category: Optional category filter
            limit: Max results

        Returns:
            List of matching concepts
        """
        from ..repositories.models import ConceptAlias

        # Search by canonical name
        name_query = self.session.query(Concept).filter(
            Concept.canonical_name.ilike(f"%{query}%")
        )

        # Search by alias
        alias_query = self.session.query(Concept).join(
            ConceptAlias, ConceptAlias.concept_id == Concept.id
        ).filter(
            ConceptAlias.alias.ilike(f"%{query}%")
        )

        if category:
            name_query = name_query.filter(Concept.category == category.value)
            alias_query = alias_query.filter(Concept.category == category.value)

        # Combine results (union removes duplicates)
        results = name_query.union(alias_query).limit(limit).all()

        return results

    def _concept_to_dict(self, concept: Concept) -> dict[str, Any]:
        """Convert concept to dictionary for logging.

        Args:
            concept: Concept to convert

        Returns:
            Dictionary representation
        """
        return {
            "id": concept.id,
            "canonical_name": concept.canonical_name,
            "category": concept.category,
            "status": concept.status,
            "version": concept.version,
            "confidence": concept.confidence,
        }

    def _log_change(
        self,
        concept_id: str,
        change_type: str,
        operator: str = "system",
        before_json: Optional[str] = None,
        after_json: Optional[str] = None,
        change_note: Optional[str] = None,
    ) -> ConceptChangeLog:
        """Log a concept change for audit trail.

        Args:
            concept_id: Concept ID
            change_type: Type of change
            operator: Who made the change
            before_json: State before change
            after_json: State after change
            change_note: Optional note

        Returns:
            Created change log entry
        """
        log = ConceptChangeLog(
            id=f"log_{uuid.uuid4().hex[:8]}",
            concept_id=concept_id,
            change_type=change_type,
            before_json=str(before_json) if before_json else None,
            after_json=str(after_json) if after_json else None,
            operator=operator,
            change_note=change_note,
        )

        self.session.add(log)
        self.session.flush()

        return log


__all__ = [
    "ConceptService",
    "ConceptCreateInput",
    "ConceptUpdateInput",
]
