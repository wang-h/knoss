"""Alias Service for Knoss governance.

This service provides operations for managing aliases and synonyms
for canonical concepts.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..models.types import AliasType, ConceptStatus
from ..repositories.models import Concept, ConceptAlias


class AliasCreateInput(BaseModel):
    """Input for creating a new alias."""
    alias: str = Field(description="Alias text")
    alias_type: AliasType = Field(default=AliasType.EXACT)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class AliasService:
    """Service for managing concept aliases.

    This service provides operations for adding, removing, and managing
    aliases that link to canonical concepts.
    """

    def __init__(self, session: Session):
        """Initialize the alias service.

        Args:
            session: SQLAlchemy ORM session
        """
        self.session = session

    def add_alias(
        self,
        concept_id: str,
        input_data: AliasCreateInput,
    ) -> Optional[ConceptAlias]:
        """Add an alias to a concept.

        Args:
            concept_id: Concept ID
            input_data: Alias creation input

        Returns:
            Created alias if concept exists, None otherwise
        """
        concept = self.session.get(Concept, concept_id)
        if not concept:
            return None

        # Check for duplicate
        existing = self.session.query(ConceptAlias).filter_by(
            concept_id=concept_id,
            alias=input_data.alias,
        ).first()

        if existing:
            return existing

        alias = ConceptAlias(
            id=f"alias_{uuid.uuid4().hex[:8]}",
            concept_id=concept_id,
            alias=input_data.alias,
            alias_type=input_data.alias_type.value,
            status=ConceptStatus.DRAFT.value,
            confidence=input_data.confidence,
        )

        self.session.add(alias)
        self.session.flush()

        return alias

    def remove_alias(self, alias_id: str) -> bool:
        """Remove an alias.

        Args:
            alias_id: Alias ID

        Returns:
            True if removed, False if not found
        """
        alias = self.session.get(ConceptAlias, alias_id)
        if not alias:
            return False

        self.session.delete(alias)
        self.session.flush()

        return True

    def get_aliases_for_concept(
        self,
        concept_id: str,
        alias_type: Optional[AliasType] = None,
    ) -> list[ConceptAlias]:
        """Get all aliases for a concept.

        Args:
            concept_id: Concept ID
            alias_type: Optional alias type filter

        Returns:
            List of aliases
        """
        query = self.session.query(ConceptAlias).filter_by(concept_id=concept_id)

        if alias_type:
            query = query.filter(ConceptAlias.alias_type == alias_type.value)

        return query.all()

    def find_concept_by_alias(
        self,
        alias: str,
        alias_type: Optional[AliasType] = None,
    ) -> Optional[Concept]:
        """Find a concept by its alias.

        Args:
            alias: Alias text
            alias_type: Optional alias type filter

        Returns:
            Concept if found, None otherwise
        """
        query = self.session.query(Concept).join(
            ConceptAlias, ConceptAlias.concept_id == Concept.id
        ).filter(
            ConceptAlias.alias == alias,
            ConceptAlias.status == ConceptStatus.ACTIVE.value,
        )

        if alias_type:
            query = query.filter(ConceptAlias.alias_type == alias_type.value)

        return query.first()

    def activate_alias(self, alias_id: str) -> Optional[ConceptAlias]:
        """Activate an alias.

        Args:
            alias_id: Alias ID

        Returns:
            Updated alias if found, None otherwise
        """
        alias = self.session.get(ConceptAlias, alias_id)
        if not alias:
            return None

        alias.status = ConceptStatus.ACTIVE.value
        self.session.flush()

        return alias

    def search_aliases(
        self,
        query: str,
        limit: int = 20,
    ) -> list[ConceptAlias]:
        """Search aliases by text.

        Args:
            query: Search query string
            limit: Max results

        Returns:
            List of matching aliases
        """
        return self.session.query(ConceptAlias).filter(
            ConceptAlias.alias.ilike(f"%{query}%")
        ).limit(limit).all()


__all__ = [
    "AliasService",
    "AliasCreateInput",
]
