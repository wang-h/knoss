"""Relation Service for Knoss governance.

This service provides operations for managing relationships
between concepts in the taxonomy.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..models.types import ConceptStatus, RelationType
from ..repositories.models import Concept, ConceptRelation


class RelationCreateInput(BaseModel):
    """Input for creating a new relation."""
    target_concept_id: str = Field(description="Target concept ID")
    relation_type: RelationType = Field(description="Type of relation")
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    source_note: Optional[str] = Field(default=None)


class RelationService:
    """Service for managing concept relations.

    This service provides operations for creating, removing, and
    managing relationships between concepts.
    """

    def __init__(self, session: Session):
        """Initialize the relation service.

        Args:
            session: SQLAlchemy ORM session
        """
        self.session = session

    def add_relation(
        self,
        source_concept_id: str,
        input_data: RelationCreateInput,
    ) -> Optional[ConceptRelation]:
        """Add a relation between concepts.

        Args:
            source_concept_id: Source concept ID
            input_data: Relation creation input

        Returns:
            Created relation if both concepts exist, None otherwise
        """
        # Verify both concepts exist
        source = self.session.get(Concept, source_concept_id)
        target = self.session.get(Concept, input_data.target_concept_id)

        if not source or not target:
            return None

        # Check for duplicate
        existing = self.session.query(ConceptRelation).filter_by(
            source_concept_id=source_concept_id,
            target_concept_id=input_data.target_concept_id,
            relation_type=input_data.relation_type.value,
        ).first()

        if existing:
            return existing

        relation = ConceptRelation(
            id=f"rel_{uuid.uuid4().hex[:8]}",
            source_concept_id=source_concept_id,
            target_concept_id=input_data.target_concept_id,
            relation_type=input_data.relation_type.value,
            weight=input_data.weight,
            status=ConceptStatus.DRAFT.value,
            source_note=input_data.source_note,
        )

        self.session.add(relation)
        self.session.flush()

        return relation

    def remove_relation(self, relation_id: str) -> bool:
        """Remove a relation.

        Args:
            relation_id: Relation ID

        Returns:
            True if removed, False if not found
        """
        relation = self.session.get(ConceptRelation, relation_id)
        if not relation:
            return False

        self.session.delete(relation)
        self.session.flush()

        return True

    def get_relations_for_concept(
        self,
        concept_id: str,
        relation_type: Optional[RelationType] = None,
        direction: str = "outgoing",  # "outgoing", "incoming", or "both"
    ) -> list[ConceptRelation]:
        """Get relations for a concept.

        Args:
            concept_id: Concept ID
            relation_type: Optional relation type filter
            direction: Direction of relations to return

        Returns:
            List of relations
        """
        if direction == "outgoing":
            query = self.session.query(ConceptRelation).filter_by(
                source_concept_id=concept_id
            )
        elif direction == "incoming":
            query = self.session.query(ConceptRelation).filter_by(
                target_concept_id=concept_id
            )
        else:  # both
            query = self.session.query(ConceptRelation).filter(
                (ConceptRelation.source_concept_id == concept_id) |
                (ConceptRelation.target_concept_id == concept_id)
            )

        if relation_type:
            query = query.filter(ConceptRelation.relation_type == relation_type.value)

        return query.all()

    def get_related_concepts(
        self,
        concept_id: str,
        relation_type: Optional[RelationType] = None,
        max_depth: int = 1,
    ) -> dict[str, Any]:
        """Get all concepts related to a concept.

        Args:
            concept_id: Concept ID
            relation_type: Optional relation type filter
            max_depth: Maximum depth of relation traversal

        Returns:
            Dictionary with related concepts grouped by relation type
        """
        result: dict[str, Any] = {
            "concept_id": concept_id,
            "relations": {},
        }

        relations = self.get_relations_for_concept(
            concept_id,
            relation_type,
            direction="both",
        )

        for rel in relations:
            if rel.relation_type not in result["relations"]:
                result["relations"][rel.relation_type] = []

            # Determine related concept
            if rel.source_concept_id == concept_id:
                related_id = rel.target_concept_id
            else:
                related_id = rel.source_concept_id

            related = self.session.get(Concept, related_id)
            if related:
                result["relations"][rel.relation_type].append({
                    "concept_id": related.id,
                    "canonical_name": related.canonical_name,
                    "category": related.category,
                    "weight": rel.weight,
                })

        return result

    def activate_relation(self, relation_id: str) -> Optional[ConceptRelation]:
        """Activate a relation.

        Args:
            relation_id: Relation ID

        Returns:
            Updated relation if found, None otherwise
        """
        relation = self.session.get(ConceptRelation, relation_id)
        if not relation:
            return None

        relation.status = ConceptStatus.ACTIVE.value
        self.session.flush()

        return relation


__all__ = [
    "RelationService",
    "RelationCreateInput",
]
