"""Evidence Pack Builder for Knoss.

This service provides operations for building evidence packs
that can be consumed by downstream systems like Press.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..models.payloads import EvidenceItemModel, EvidencePackModel
from ..models.types import EvidenceRole
from ..repositories.models import Concept, ConceptEvidence, ConceptAlias


class EvidencePackConfig(BaseModel):
    """Configuration for building an evidence pack."""
    topic_bundle_id: str = Field(description="Topic bundle ID")
    patient_profile: str = Field(description="Target patient profile")
    concept_ids: List[str] = Field(description="Concepts to include")
    min_quality: float = Field(default=0.6, ge=0.0, le=1.0)
    max_evidence_per_concept: int = Field(default=10, ge=1, le=100)
    include_explanations: bool = Field(default=True)
    audience_level: str = Field(default="patient", description="Target audience")


class EvidencePackBuilder:
    """Service for building evidence packs.

    This service assembles evidence packs containing:
    - Reviewed claims linked to concepts
    - Patient-friendly explanations
    - Evidence quality indicators
    - Source traceability information

    Evidence packs are designed for consumption by downstream
    content generation systems like Press.
    """

    def __init__(self, session: Session):
        """Initialize the evidence pack builder.

        Args:
            session: SQLAlchemy ORM session
        """
        self.session = session

    def build_evidence_pack(
        self,
        config: EvidencePackConfig,
    ) -> Optional[EvidencePackModel]:
        """Build an evidence pack from configuration.

        Args:
            config: Evidence pack configuration

        Returns:
            Built evidence pack, or None if concepts not found
        """
        all_evidence_items: List[EvidenceItemModel] = []
        notes: Dict[str, Any] = {
            "concept_count": len(config.concept_ids),
            "patient_profile": config.patient_profile,
            "audience_level": config.audience_level,
            "concepts": {},
        }

        for concept_id in config.concept_ids:
            concept = self.session.get(Concept, concept_id)
            if not concept:
                continue

            # Get evidence for this concept
            evidence = self.session.query(ConceptEvidence).filter_by(
                concept_id=concept_id
            ).filter(
                ConceptEvidence.quality_score >= config.min_quality
            ).order_by(
                ConceptEvidence.quality_score.desc(),
                ConceptEvidence.relevance_score.desc(),
            ).limit(config.max_evidence_per_concept).all()

            # Convert to evidence items
            for ev in evidence:
                all_evidence_items.append(EvidenceItemModel(
                    claim_id=ev.claim_id or f"ev_{ev.id}",
                    segment_id=ev.segment_id or f"seg_{ev.article_id}",
                    evidence_role=EvidenceRole(ev.evidence_role),
                    score=(ev.quality_score + ev.relevance_score) / 2,
                ))

            # Add concept info to notes
            notes["concepts"][concept_id] = {
                "canonical_name": concept.canonical_name,
                "category": concept.category,
                "evidence_count": len(evidence),
                "patient_friendly_name": concept.patient_friendly_name,
                "explanation": concept.patient_friendly_explanation if config.include_explanations else None,
            }

        # Sort all evidence items by score
        all_evidence_items.sort(key=lambda e: e.score or 0, reverse=True)

        return EvidencePackModel(
            topic_bundle_id=config.topic_bundle_id,
            patient_profile=config.patient_profile,
            evidence_items=all_evidence_items,
            notes=notes,
        )

    def build_evidence_pack_for_claims(
        self,
        topic_bundle_id: str,
        claim_ids: List[str],
        patient_profile: str = "general",
    ) -> Optional[EvidencePackModel]:
        """Build an evidence pack for specific claims.

        Args:
            topic_bundle_id: Topic bundle ID
            claim_ids: List of claim IDs
            patient_profile: Target patient profile

        Returns:
            Built evidence pack
        """
        evidence_items: List[EvidenceItemModel] = []

        for claim_id in claim_ids:
            # Find evidence for this claim
            evidence = self.session.query(ConceptEvidence).filter_by(
                claim_id=claim_id
            ).order_by(
                ConceptEvidence.quality_score.desc(),
                ConceptEvidence.relevance_score.desc(),
            ).first()

            if evidence:
                evidence_items.append(EvidenceItemModel(
                    claim_id=claim_id,
                    segment_id=evidence.segment_id or f"seg_{evidence.article_id}",
                    evidence_role=EvidenceRole(evidence.evidence_role),
                    score=(evidence.quality_score + evidence.relevance_score) / 2,
                ))

        return EvidencePackModel(
            topic_bundle_id=topic_bundle_id,
            patient_profile=patient_profile,
            evidence_items=evidence_items,
            notes={"claim_count": len(claim_ids)},
        )

    def get_patient_friendly_explanations(
        self,
        concept_ids: List[str],
        audience_level: str = "patient",
    ) -> Dict[str, Dict[str, str]]:
        """Get patient-friendly explanations for concepts.

        Args:
            concept_ids: List of concept IDs
            audience_level: Target audience level

        Returns:
            Dictionary mapping concept IDs to explanations
        """
        explanations: Dict[str, Dict[str, str]] = {}

        for concept_id in concept_ids:
            concept = self.session.get(Concept, concept_id)
            if not concept:
                continue

            explanations[concept_id] = {
                "canonical_name": concept.canonical_name,
                "category": concept.category,
                "friendly_name": concept.patient_friendly_name or concept.canonical_name,
                "explanation": concept.patient_friendly_explanation or "",
                "audience_level": audience_level,
            }

            # Add common aliases
            aliases = self.session.query(ConceptAlias).filter_by(
                concept_id=concept_id
            ).filter(
                ConceptAlias.status == "active"
            ).limit(5).all()

            explanations[concept_id]["common_aliases"] = [a.alias for a in aliases]

        return explanations

    def validate_evidence_pack(
        self,
        pack: EvidencePackModel,
    ) -> Dict[str, Any]:
        """Validate an evidence pack for quality and completeness.

        Args:
            pack: Evidence pack to validate

        Returns:
            Validation results
        """
        issues = []
        warnings = []

        # Check for empty evidence pack
        if not pack.evidence_items:
            issues.append("Evidence pack contains no evidence items")

        # Check evidence quality
        low_quality_count = sum(
            1 for item in pack.evidence_items
            if item.score and item.score < 0.5
        )

        if low_quality_count > len(pack.evidence_items) * 0.3:
            warnings.append(
                f"More than 30% of evidence items have low quality scores ({low_quality_count}/{len(pack.evidence_items)})"
            )

        # Check for conflicting evidence
        conflicting = [
            item for item in pack.evidence_items
            if item.evidence_role == EvidenceRole.CONFLICTING
        ]

        if conflicting:
            warnings.append(f"Contains {len(conflicting)} conflicting evidence items")

        # Check patient profile alignment
        if pack.patient_profile == "pediatric" and not pack.notes.get("pediatric_approved"):
            warnings.append("Pediatric evidence pack not specifically approved")

        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "evidence_count": len(pack.evidence_items),
            "quality_score": sum(item.score or 0 for item in pack.evidence_items) / len(pack.evidence_items) if pack.evidence_items else 0,
        }

    def filter_evidence_by_audience(
        self,
        pack: EvidencePackModel,
        audience_filters: Dict[str, Any],
    ) -> EvidencePackModel:
        """Filter evidence pack items by audience criteria.

        Args:
            pack: Original evidence pack
            audience_filters: Audience-specific filters

        Returns:
            Filtered evidence pack
        """
        filtered_items = []

        for item in pack.evidence_items:
            # Apply audience-specific filters
            include = True

            # Example: filter by complexity, reading level, etc.
            if "min_quality" in audience_filters:
                if (item.score or 0) < audience_filters["min_quality"]:
                    include = False

            if "exclude_conflicting" in audience_filters and audience_filters["exclude_conflicting"]:
                if item.evidence_role == EvidenceRole.CONFLICTING:
                    include = False

            if include:
                filtered_items.append(item)

        return EvidencePackModel(
            topic_bundle_id=pack.topic_bundle_id,
            patient_profile=pack.patient_profile,
            evidence_items=filtered_items,
            notes={
                **pack.notes,
                "filtered": True,
                "original_count": len(pack.evidence_items),
                "filtered_count": len(filtered_items),
            },
        )


__all__ = [
    "EvidencePackBuilder",
    "EvidencePackConfig",
]
