"""Trace Service for Knoss.

This service provides operations for tracking provenance and lineage
of knowledge assets through the extraction and governance process.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..repositories.models import (
    Concept,
    ConceptEvidence,
    ConceptAlias,
    ConceptChangeLog,
    EntityMapping,
)


class TraceQuery(BaseModel):
    """Query for tracing knowledge provenance."""
    item_type: str = Field(description="Type of item: concept, entity, claim, segment")
    item_id: str = Field(description="ID of the item to trace")
    include_upstream: bool = Field(default=True, description="Include upstream sources")
    include_downstream: bool = Field(default=True, description="Include downstream uses")
    max_depth: int = Field(default=3, ge=1, le=10, description="Maximum traversal depth")


class TraceResult(BaseModel):
    """Result of a trace query."""
    item_type: str
    item_id: str
    current_state: Dict[str, Any]
    upstream_sources: List[Dict[str, Any]] = Field(default_factory=list)
    downstream_uses: List[Dict[str, Any]] = Field(default_factory=list)
    lineage: List[Dict[str, Any]] = Field(default_factory=list)
    audit_trail: List[Dict[str, Any]] = Field(default_factory=list)


class TraceService:
    """Service for tracking knowledge provenance and lineage.

    This service provides complete traceability from:
    - Raw article text → Segments → Claims → Entities → Concepts
    - Concepts → Evidence links → Topic bundles → Generated content

    This enables audit trails, debugging, and quality control.
    """

    def __init__(self, session: Session):
        """Initialize the trace service.

        Args:
            session: SQLAlchemy ORM session
        """
        self.session = session

    def trace_concept(self, concept_id: str, max_depth: int = 3) -> Optional[TraceResult]:
        """Trace the provenance and lineage of a concept.

        Args:
            concept_id: Concept ID to trace
            max_depth: Maximum traversal depth

        Returns:
            Trace result with full lineage
        """
        concept = self.session.get(Concept, concept_id)
        if not concept:
            return None

        # Current state
        current_state = {
            "id": concept.id,
            "canonical_name": concept.canonical_name,
            "category": concept.category,
            "status": concept.status,
            "version": concept.version,
            "created_at": concept.created_at.isoformat() if concept.created_at else None,
            "updated_at": concept.updated_at.isoformat() if concept.updated_at else None,
        }

        # Upstream sources (entities, claims, segments that led to this concept)
        upstream_sources = self._trace_concept_upstream(concept_id, max_depth)

        # Downstream uses (where this concept is used)
        downstream_uses = self._trace_concept_downstream(concept_id, max_depth)

        # Audit trail (change logs)
        audit_trail = self._get_concept_audit_trail(concept_id)

        # Lineage (full path from source to current)
        lineage = self._build_lineage(upstream_sources, downstream_uses)

        return TraceResult(
            item_type="concept",
            item_id=concept_id,
            current_state=current_state,
            upstream_sources=upstream_sources,
            downstream_uses=downstream_uses,
            lineage=lineage,
            audit_trail=audit_trail,
        )

    def trace_entity(self, entity_text: str, max_depth: int = 3) -> Optional[TraceResult]:
        """Trace an entity through the governance process.

        Args:
            entity_text: Entity text to trace
            max_depth: Maximum traversal depth

        Returns:
            Trace result for the entity
        """
        # Find all mappings for this entity
        mappings = self.session.query(EntityMapping).filter_by(
            entity_text=entity_text
        ).all()

        if not mappings:
            return None

        # Get the most recent/confirmed mapping
        primary_mapping = max(
            mappings,
            key=lambda m: (
                1 if m.mapping_status == "human_confirmed" else 0,
                m.confidence or 0,
                m.created_at or datetime.min,
            ),
        )

        current_state = {
            "entity_text": entity_text,
            "entity_type": primary_mapping.entity_type,
            "mapping_status": primary_mapping.mapping_status,
            "candidate_concept_id": primary_mapping.candidate_concept_id,
            "final_concept_id": primary_mapping.final_concept_id,
            "confidence": primary_mapping.confidence,
            "source_article": primary_mapping.article_id,
            "reviewed_by": primary_mapping.reviewed_by,
            "reviewed_at": primary_mapping.reviewed_at.isoformat() if primary_mapping.reviewed_at else None,
        }

        # Upstream: what articles/segments produced this entity
        upstream_sources = [{
            "type": "article",
            "id": primary_mapping.article_id,
            "relation": "source_of_entity",
        }]

        # Downstream: what concept this maps to
        downstream_uses = []
        if primary_mapping.final_concept_id:
            concept = self.session.get(Concept, primary_mapping.final_concept_id)
            if concept:
                downstream_uses.append({
                    "type": "concept",
                    "id": concept.id,
                    "canonical_name": concept.canonical_name,
                    "relation": "mapped_to_concept",
                })

        return TraceResult(
            item_type="entity",
            item_id=entity_text,
            current_state=current_state,
            upstream_sources=upstream_sources,
            downstream_uses=downstream_uses,
            lineage=[],
            audit_trail=[],
        )

    def trace_evidence(self, evidence_id: str) -> Optional[Dict[str, Any]]:
        """Trace an evidence link to its source.

        Args:
            evidence_id: Evidence ID to trace

        Returns:
            Trace information for the evidence
        """
        evidence = self.session.get(ConceptEvidence, evidence_id)
        if not evidence:
            return None

        # Get the concept
        concept = self.session.get(Concept, evidence.concept_id)

        # Build trace
        return {
            "evidence_id": evidence_id,
            "concept": {
                "id": concept.id if concept else None,
                "canonical_name": concept.canonical_name if concept else None,
                "category": concept.category if concept else None,
            },
            "source": {
                "article_id": evidence.article_id,
                "segment_id": evidence.segment_id,
                "claim_id": evidence.claim_id,
            },
            "quality": {
                "role": evidence.evidence_role,
                "relevance_score": evidence.relevance_score,
                "quality_score": evidence.quality_score,
            },
        }

    def get_full_lineage(
        self,
        item_type: str,
        item_id: str,
        max_depth: int = 5,
    ) -> List[Dict[str, Any]]:
        """Get the full lineage from raw source to final use.

        Args:
            item_type: Type of item
            item_id: Item ID
            max_depth: Maximum traversal depth

        Returns:
            List of lineage steps
        """
        if item_type == "concept":
            result = self.trace_concept(item_id, max_depth)
            return result.lineage if result else []

        # For other item types, implement as needed
        return []

    def _trace_concept_upstream(
        self,
        concept_id: str,
        max_depth: int,
    ) -> List[Dict[str, Any]]:
        """Trace upstream sources for a concept.

        Args:
            concept_id: Concept ID
            max_depth: Maximum traversal depth

        Returns:
            List of upstream sources
        """
        sources = []

        # Find entity mappings that point to this concept
        mappings = self.session.query(EntityMapping).filter(
            (EntityMapping.candidate_concept_id == concept_id) |
            (EntityMapping.final_concept_id == concept_id)
        ).all()

        for mapping in mappings:
            sources.append({
                "type": "entity_mapping",
                "id": mapping.id,
                "entity_text": mapping.entity_text,
                "article_id": mapping.article_id,
                "mapping_status": mapping.mapping_status,
                "confidence": mapping.confidence,
            })

        # Find evidence links
        evidence = self.session.query(ConceptEvidence).filter_by(
            concept_id=concept_id
        ).all()

        for ev in evidence:
            sources.append({
                "type": "evidence",
                "id": ev.id,
                "article_id": ev.article_id,
                "segment_id": ev.segment_id,
                "claim_id": ev.claim_id,
                "role": ev.evidence_role,
            })

        return sources[:max_depth * 10]  # Limit results

    def _trace_concept_downstream(
        self,
        concept_id: str,
        max_depth: int,
    ) -> List[Dict[str, Any]]:
        """Trace downstream uses for a concept.

        Args:
            concept_id: Concept ID
            max_depth: Maximum traversal depth

        Returns:
            List of downstream uses
        """
        uses = []

        # Find relations where this concept is the source
        from ..repositories.models import ConceptRelation

        relations = self.session.query(ConceptRelation).filter_by(
            source_concept_id=concept_id
        ).all()

        for rel in relations:
            target = self.session.get(Concept, rel.target_concept_id)
            if target:
                uses.append({
                    "type": "concept_relation",
                    "id": rel.id,
                    "relation_type": rel.relation_type,
                    "target_concept": {
                        "id": target.id,
                        "canonical_name": target.canonical_name,
                    },
                })

        return uses[:max_depth * 10]

    def _get_concept_audit_trail(self, concept_id: str) -> List[Dict[str, Any]]:
        """Get the audit trail for a concept.

        Args:
            concept_id: Concept ID

        Returns:
            List of audit trail entries
        """
        logs = self.session.query(ConceptChangeLog).filter_by(
            concept_id=concept_id
        ).order_by(ConceptChangeLog.created_at).all()

        return [
            {
                "log_id": log.id,
                "change_type": log.change_type,
                "operator": log.operator,
                "timestamp": log.created_at.isoformat() if log.created_at else None,
                "note": log.change_note,
            }
            for log in logs
        ]

    def _build_lineage(
        self,
        upstream: List[Dict[str, Any]],
        downstream: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Build a lineage path from sources to uses.

        Args:
            upstream: Upstream sources
            downstream: Downstream uses

        Returns:
            Combined lineage path
        """
        lineage = []

        # Add upstream sources
        for source in upstream:
            lineage.append({
                "direction": "upstream",
                **source,
            })

        # Add downstream uses
        for use in downstream:
            lineage.append({
                "direction": "downstream",
                **use,
            })

        return lineage


__all__ = [
    "TraceService",
    "TraceQuery",
    "TraceResult",
]
