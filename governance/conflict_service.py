"""Conflict Service for Knoss governance.

This service provides operations for detecting and resolving conflicts
in concept mappings and relationships.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..repositories.models import Concept, ConceptAlias, EntityMapping, ConceptRelation
from ..models.types import MappingStatus, ConceptStatus


class ConflictDetectionInput(BaseModel):
    """Input for conflict detection."""
    entity_text: str = Field(description="Entity text to check for conflicts")
    proposed_concept_id: Optional[str] = Field(default=None, description="Proposed concept mapping")


class ConflictResolution(BaseModel):
    """A detected conflict with resolution suggestions."""
    conflict_type: str = Field(description="Type of conflict")
    description: str = Field(description="Conflict description")
    conflicting_items: List[Dict[str, Any]] = Field(description="Conflicting items")
    resolution_suggestions: List[str] = Field(description="Suggested resolutions")


class ConflictService:
    """Service for detecting and resolving conflicts.

    This service identifies conflicts in:
    - Multiple concepts mapped to the same entity
    - Same concept mapped to conflicting entity types
    - Circular concept relationships
    - Conflicting patient-friendly explanations
    """

    def __init__(self, session: Session):
        """Initialize the conflict service.

        Args:
            session: SQLAlchemy ORM session
        """
        self.session = session

    def detect_entity_conflicts(
        self,
        entity_text: str,
    ) -> List[ConflictResolution]:
        """Detect conflicts for an entity mapping.

        Args:
            entity_text: Entity text to check

        Returns:
            List of detected conflicts
        """
        conflicts = []

        # Find all existing mappings for this entity
        mappings = self.session.query(EntityMapping).filter_by(
            entity_text=entity_text
        ).all()

        if not mappings:
            return conflicts

        # Group by concept
        concept_mappings: Dict[str, List[EntityMapping]] = {}
        for mapping in mappings:
            concept_id = mapping.final_concept_id or mapping.candidate_concept_id
            if concept_id:
                if concept_id not in concept_mappings:
                    concept_mappings[concept_id] = []
                concept_mappings[concept_id].append(mapping)

        # Check for multiple concept mappings
        if len(concept_mappings) > 1:
            conflicts.append(ConflictResolution(
                conflict_type="multiple_concept_mappings",
                description=f"Entity '{entity_text}' is mapped to {len(concept_mappings)} different concepts",
                conflicting_items=[
                    {
                        "concept_id": cid,
                        "mapping_count": len(mappings),
                        "statuses": [m.mapping_status for m in mappings],
                    }
                    for cid, mappings in concept_mappings.items()
                ],
                resolution_suggestions=[
                    "Review all mappings and confirm the correct concept",
                    "Consider if these are legitimate homonyms (create separate entries)",
                    "Deprecate incorrect mappings",
                ],
            ))

        # Check for conflicting entity types
        entity_types = set(m.entity_type for m in mappings)
        if len(entity_types) > 1:
            conflicts.append(ConflictResolution(
                conflict_type="conflicting_entity_types",
                description=f"Entity '{entity_text}' has conflicting type classifications: {', '.join(entity_types)}",
                conflicting_items=[
                    {"entity_type": et, "count": sum(1 for m in mappings if m.entity_type == et)}
                    for et in entity_types
                ],
                resolution_suggestions=[
                    "Determine the most appropriate entity type",
                    "Consider if context-dependent types are needed",
                    "Update mappings with the correct type",
                ],
            ))

        return conflicts

    def detect_alias_conflicts(
        self,
        alias: str,
    ) -> List[ConflictResolution]:
        """Detect conflicts for an alias.

        Args:
            alias: Alias text to check

        Returns:
            List of detected conflicts
        """
        conflicts = []

        # Find all concepts with this alias
        alias_entries = self.session.query(ConceptAlias).filter_by(
            alias=alias
        ).all()

        if len(alias_entries) <= 1:
            return conflicts

        # Get concept details
        concepts = []
        for alias_entry in alias_entries:
            concept = self.session.get(Concept, alias_entry.concept_id)
            if concept:
                concepts.append({
                    "concept_id": concept.id,
                    "canonical_name": concept.canonical_name,
                    "category": concept.category,
                    "alias_type": alias_entry.alias_type,
                    "status": alias_entry.status,
                })

        conflicts.append(ConflictResolution(
            conflict_type="shared_alias",
            description=f"Alias '{alias}' is shared by {len(concepts)} different concepts",
            conflicting_items=concepts,
            resolution_suggestions=[
                "Mark as ambiguous if this is intentional",
                "Create more specific aliases for each concept",
                "Deprecate incorrect alias assignments",
            ],
        ))

        return conflicts

    def detect_relation_conflicts(
        self,
        concept_id: str,
    ) -> List[ConflictResolution]:
        """Detect conflicts in concept relationships.

        Args:
            concept_id: Concept ID to check

        Returns:
            List of detected conflicts
        """
        conflicts = []

        # Check for circular relationships
        visited = set()
        path = []

        def has_cycle(current_id: str, target_id: str) -> Optional[List[str]]:
            if current_id in visited:
                return None

            if current_id == target_id and len(path) > 1:
                return path.copy()

            visited.add(current_id)

            relations = self.session.query(ConceptRelation).filter_by(
                source_concept_id=current_id
            ).all()

            for rel in relations:
                path.append(rel.relation_type)
                cycle = has_cycle(rel.target_concept_id, target_id)
                if cycle:
                    return cycle
                path.pop()

            return None

        cycle = has_cycle(concept_id, concept_id)
        if cycle:
            conflicts.append(ConflictResolution(
                conflict_type="circular_relation",
                description=f"Concept has circular relationship: {' -> '.join(cycle)}",
                conflicting_items=[{"path": cycle}],
                resolution_suggestions=[
                    "Break the cycle by removing or reclassifying one relation",
                    "Consider if a different relation type is more appropriate",
                ],
            ))

        # Check for contradictory relations (e.g., both parent_of and subtype_of)
        relations = self.session.query(ConceptRelation).filter_by(
            source_concept_id=concept_id
        ).all()

        relation_targets: Dict[str, Set[str]] = {}
        for rel in relations:
            if rel.target_concept_id not in relation_targets:
                relation_targets[rel.target_concept_id] = set()
            relation_targets[rel.target_concept_id].add(rel.relation_type)

        for target_id, relation_types in relation_targets.items():
            # Check for contradictory pairs
            contradictory_pairs = [
                (RelationType.PARENT_OF, RelationType.SUBTYPE_OF),
                (RelationType.USED_FOR, RelationType.CONTRAINDICATED_FOR),
            ]

            for type1, type2 in contradictory_pairs:
                if type1.value in relation_types and type2.value in relation_types:
                    target = self.session.get(Concept, target_id)
                    conflicts.append(ConflictResolution(
                        conflict_type="contradictory_relations",
                        description=f"Concept has contradictory relations to '{target.canonical_name if target else target_id}'",
                        conflicting_items=[{"types": list(relation_types)}],
                        resolution_suggestions=[
                            f"Remove either {type1.value} or {type2.value} relation",
                            "Review the intended relationship between concepts",
                        ],
                    ))

        return conflicts

    def get_all_conflicts(
        self,
        limit: int = 100,
    ) -> Dict[str, List[ConflictResolution]]:
        """Get all conflicts in the taxonomy.

        Args:
            limit: Maximum number of items to check per category

        Returns:
            Dictionary with conflicts grouped by category
        """
        all_conflicts: Dict[str, List[ConflictResolution]] = {
            "entity_conflicts": [],
            "alias_conflicts": [],
            "relation_conflicts": [],
        }

        # Check entity conflicts for frequently mapped entities
        from sqlalchemy import func

        entity_counts = self.session.query(
            EntityMapping.entity_text,
            func.count(EntityMapping.id).label('count')
        ).group_by(
            EntityMapping.entity_text
        ).having(
            func.count(EntityMapping.id) > 1
        ).limit(limit).all()

        for entity_text, _ in entity_counts:
            conflicts = self.detect_entity_conflicts(entity_text)
            all_conflicts["entity_conflicts"].extend(conflicts)

        # Check alias conflicts for shared aliases
        alias_counts = self.session.query(
            ConceptAlias.alias,
            func.count(ConceptAlias.id).label('count')
        ).group_by(
            ConceptAlias.alias
        ).having(
            func.count(ConceptAlias.id) > 1
        ).limit(limit).all()

        for alias, _ in alias_counts:
            conflicts = self.detect_alias_conflicts(alias)
            all_conflicts["alias_conflicts"].extend(conflicts)

        # Check relation conflicts for active concepts
        concepts = self.session.query(Concept).filter_by(
            status=ConceptStatus.ACTIVE.value
        ).limit(limit).all()

        for concept in concepts:
            conflicts = self.detect_relation_conflicts(concept.id)
            all_conflicts["relation_conflicts"].extend(conflicts)

        return all_conflicts

    def resolve_conflict(
        self,
        conflict_type: str,
        resolution: str,
        items: Dict[str, Any],
    ) -> bool:
        """Apply a resolution to a detected conflict.

        Args:
            conflict_type: Type of conflict
            resolution: Resolution action to take
            items: Items affected by the conflict

        Returns:
            True if resolution was applied successfully
        """
        # Resolution logic depends on conflict type
        # This is a placeholder for actual resolution implementation

        if conflict_type == "multiple_concept_mappings":
            # Deprecate all but the correct concept mapping
            correct_concept_id = items.get("correct_concept_id")
            entity_text = items.get("entity_text")

            if correct_concept_id and entity_text:
                mappings = self.session.query(EntityMapping).filter_by(
                    entity_text=entity_text
                ).all()

                for mapping in mappings:
                    if (mapping.final_concept_id or mapping.candidate_concept_id) != correct_concept_id:
                        mapping.mapping_status = MappingStatus.REJECTED.value

                self.session.flush()
                return True

        elif conflict_type == "shared_alias":
            # Mark as ambiguous
            alias = items.get("alias")
            if alias:
                alias_entries = self.session.query(ConceptAlias).filter_by(
                    alias=alias
                ).all()

                for entry in alias_entries:
                    entry.alias_type = "ambiguous"

                self.session.flush()
                return True

        return False


__all__ = [
    "ConflictService",
    "ConflictDetectionInput",
    "ConflictResolution",
]
