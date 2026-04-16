"""Evidence Linker for Knoss.

This service provides operations for linking evidence to concepts
and managing concept-evidence relationships.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..models.types import EvidenceRole
from ..repositories.models import Concept, ConceptEvidence, ConceptChangeLog


class EvidenceLinkInput(BaseModel):
    """Input for creating a new evidence link."""
    concept_id: str = Field(description="Concept ID")
    article_id: str = Field(description="Article ID")
    segment_id: Optional[str] = Field(default=None, description="Segment ID")
    claim_id: Optional[str] = Field(default=None, description="Claim ID")
    evidence_role: EvidenceRole = Field(default=EvidenceRole.PRIMARY)
    relevance_score: float = Field(default=0.8, ge=0.0, le=1.0)
    quality_score: float = Field(default=0.7, ge=0.0, le=1.0)


class EvidenceQueryInput(BaseModel):
    """Input for querying evidence."""
    concept_id: str = Field(description="Concept ID")
    evidence_role: Optional[EvidenceRole] = Field(default=None)
    min_relevance: float = Field(default=0.0, ge=0.0, le=1.0)
    min_quality: float = Field(default=0.0, ge=0.0, le=1.0)
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class EvidenceStats(BaseModel):
    """Evidence statistics for a concept."""
    concept_id: str
    total_evidence: int
    by_role: Dict[str, int]
    by_article: int
    avg_relevance: float
    avg_quality: float
    strong_evidence_count: int
    weak_evidence_count: int


class EvidenceLinker:
    """Service for managing concept-evidence relationships.

    This service provides operations for linking evidence to concepts,
    querying evidence, and calculating evidence statistics.
    """

    def __init__(self, session: Session):
        """Initialize the evidence linker.

        Args:
            session: SQLAlchemy ORM session
        """
        self.session = session

    def link_evidence(self, input_data: EvidenceLinkInput) -> Optional[ConceptEvidence]:
        """Create a new evidence link.

        Args:
            input_data: Evidence link input

        Returns:
            Created evidence link, or None if concept not found
        """
        # Verify concept exists
        concept = self.session.get(Concept, input_data.concept_id)
        if not concept:
            return None

        # Check for duplicate link
        existing = self.session.query(ConceptEvidence).filter_by(
            concept_id=input_data.concept_id,
            article_id=input_data.article_id,
            segment_id=input_data.segment_id,
            claim_id=input_data.claim_id,
        ).first()

        if existing:
            # Update existing link
            existing.evidence_role = input_data.evidence_role.value
            existing.relevance_score = input_data.relevance_score
            existing.quality_score = input_data.quality_score
            self.session.flush()
            return existing

        # Create new link
        evidence = ConceptEvidence(
            id=f"ev_{uuid.uuid4().hex[:8]}",
            concept_id=input_data.concept_id,
            article_id=input_data.article_id,
            segment_id=input_data.segment_id,
            claim_id=input_data.claim_id,
            evidence_role=input_data.evidence_role.value,
            relevance_score=input_data.relevance_score,
            quality_score=input_data.quality_score,
        )

        self.session.add(evidence)
        self.session.flush()

        # Log the evidence linkage
        self._log_change(
            concept_id=input_data.concept_id,
            change_type="evidence_link",
            after_json=f"Linked evidence from article {input_data.article_id}",
            operator="system",
            change_note=f"Added {input_data.evidence_role.value} evidence link",
        )

        return evidence

    def get_concept_evidence(
        self,
        concept_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ConceptEvidence]:
        """Get all evidence for a concept.

        Args:
            concept_id: Concept ID
            limit: Max results
            offset: Results offset

        Returns:
            List of evidence links
        """
        return (
            self.session.query(ConceptEvidence)
            .filter_by(concept_id=concept_id)
            .order_by(ConceptEvidence.quality_score.desc(), ConceptEvidence.relevance_score.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def query_evidence(self, input_data: EvidenceQueryInput) -> List[ConceptEvidence]:
        """Query evidence with filters.

        Args:
            input_data: Query parameters

        Returns:
            Filtered list of evidence
        """
        query = self.session.query(ConceptEvidence).filter_by(
            concept_id=input_data.concept_id
        )

        if input_data.evidence_role:
            query = query.filter(ConceptEvidence.evidence_role == input_data.evidence_role.value)

        if input_data.min_relevance > 0:
            query = query.filter(ConceptEvidence.relevance_score >= input_data.min_relevance)

        if input_data.min_quality > 0:
            query = query.filter(ConceptEvidence.quality_score >= input_data.min_quality)

        return (
            query.order_by(ConceptEvidence.quality_score.desc(), ConceptEvidence.relevance_score.desc())
            .offset(input_data.offset)
            .limit(input_data.limit)
            .all()
        )

    def get_evidence_stats(self, concept_id: str) -> EvidenceStats:
        """Get evidence statistics for a concept.

        Args:
            concept_id: Concept ID

        Returns:
            Evidence statistics
        """
        evidence_list = self.session.query(ConceptEvidence).filter_by(
            concept_id=concept_id
        ).all()

        if not evidence_list:
            return EvidenceStats(
                concept_id=concept_id,
                total_evidence=0,
                by_role={},
                by_article=0,
                avg_relevance=0.0,
                avg_quality=0.0,
                strong_evidence_count=0,
                weak_evidence_count=0,
            )

        total = len(evidence_list)
        by_role: Dict[str, int] = {}
        unique_articles = set()
        total_relevance = 0.0
        total_quality = 0.0
        strong_count = 0
        weak_count = 0

        for evidence in evidence_list:
            role = evidence.evidence_role
            by_role[role] = by_role.get(role, 0) + 1
            unique_articles.add(evidence.article_id)
            total_relevance += evidence.relevance_score or 0.5
            total_quality += evidence.quality_score or 0.5

            relevance = evidence.relevance_score or 0.5
            quality = evidence.quality_score or 0.5
            if relevance >= 0.7 and quality >= 0.7:
                strong_count += 1
            elif relevance < 0.5 or quality < 0.5:
                weak_count += 1

        return EvidenceStats(
            concept_id=concept_id,
            total_evidence=total,
            by_role=by_role,
            by_article=len(unique_articles),
            avg_relevance=total_relevance / total,
            avg_quality=total_quality / total,
            strong_evidence_count=strong_count,
            weak_evidence_count=weak_count,
        )

    def trace_evidence_source(self, concept_id: str) -> Dict[str, Any]:
        """Trace the evidence sources for a concept.

        Args:
            concept_id: Concept ID

        Returns:
            Dictionary with evidence source information
        """
        evidence_list = self.session.query(ConceptEvidence).filter_by(
            concept_id=concept_id
        ).all()

        by_article: Dict[str, Dict[str, Any]] = {}

        for evidence in evidence_list:
            article_id = evidence.article_id
            if article_id not in by_article:
                by_article[article_id] = {
                    "segments": [],
                    "claims": [],
                    "evidence_count": 0,
                    "roles": set(),
                }

            info = by_article[article_id]
            info["evidence_count"] += 1
            info["roles"].add(evidence.evidence_role)

            if evidence.segment_id:
                info["segments"].append(evidence.segment_id)
            if evidence.claim_id:
                info["claims"].append(evidence.claim_id)

        # Convert to list format
        articles = []
        for article_id, info in by_article.items():
            articles.append({
                "article_id": article_id,
                "evidence_count": info["evidence_count"],
                "roles": list(info["roles"]),
                "segment_count": len(info["segments"]),
                "claim_count": len(info["claims"]),
            })

        # Sort by evidence count
        articles.sort(key=lambda x: x["evidence_count"], reverse=True)

        return {
            "concept_id": concept_id,
            "total_articles": len(articles),
            "articles": articles[:10],  # Top 10 articles
        }

    def bulk_link_evidence(
        self,
        concept_id: str,
        evidence_links: List[EvidenceLinkInput],
    ) -> int:
        """Bulk link evidence to a concept.

        Args:
            concept_id: Concept ID
            evidence_links: List of evidence link inputs

        Returns:
            Number of evidence links created
        """
        count = 0
        for link_data in evidence_links:
            link_data.concept_id = concept_id
            try:
                if self.link_evidence(input_data=link_data):
                    count += 1
            except Exception:
                pass

        return count

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
            before_json=before_json,
            after_json=after_json,
            operator=operator,
            change_note=change_note,
        )

        self.session.add(log)
        self.session.flush()

        return log


__all__ = [
    "EvidenceLinker",
    "EvidenceLinkInput",
    "EvidenceQueryInput",
    "EvidenceStats",
]
