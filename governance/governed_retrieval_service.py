"""Governed Retrieval Service for Knoss.

This service provides governed retrieval of knowledge assets for
downstream systems like Lenss and Press, with proper fallback warnings.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..contracts.knoss_lenss_contract import (
    LenssContract,
    LenssRetrievalRequest,
    LenssRetrievalResponse,
    LenssTopicBundle,
    LenssClaim,
    LenssConcept,
)
from ..contracts.knoss_press_contract import (
    PressContract,
    PressRetrievalRequest,
    PressRetrievalResponse,
    PressEvidencePack,
    PressConceptExplanation,
    PressEvidenceItem,
)
from ..models.types import ClaimType, CertaintyLevel, ConceptStatus, ConceptCategory
from ..repositories.models import Concept, ConceptEvidence, EntityMapping, ConceptAlias


class GovernedRetrievalConfig(BaseModel):
    """Configuration for governed retrieval."""
    min_governance_status: str = Field(default="active", description="Minimum governance status")
    require_medical_review: bool = Field(default=True, description="Require medical review flag")
    allow_fallback: bool = Field(default=False, description="Allow fallback to ungoverned content")
    fallback_warning_required: bool = Field(default=True, description="Require warning when using fallback")


class GovernedRetrievalService:
    """Service for governed retrieval of knowledge assets.

    This service ensures that downstream systems receive the highest
    quality governed knowledge assets, with proper fallback handling
    and warnings when ungoverned content must be used.

    Key principles:
    1. Prioritize reviewed concepts over raw entities
    2. Never use ungoverned content silently
    3. Provide clear warnings when fallback occurs
    4. Enable quality filtering by downstream systems
    """

    def __init__(self, session: Session):
        """Initialize the governed retrieval service.

        Args:
            session: SQLAlchemy ORM session
        """
        self.session = session

    def retrieve_for_lenss(
        self,
        request: LenssRetrievalRequest,
        config: Optional[GovernedRetrievalConfig] = None,
    ) -> LenssRetrievalResponse:
        """Retrieve governed knowledge for Lenss.

        Args:
            request: Retrieval request from Lenss
            config: Optional retrieval configuration

        Returns:
            Governed retrieval response
        """
        if config is None:
            config = GovernedRetrievalConfig()

        warnings: List[str] = []
        retrieval_metadata: Dict[str, Any] = {
            "request": request.model_dump(),
            "config": config.model_dump(),
        }

        try:
            # Find reviewed concepts
            concepts = self._get_reviewed_concepts(
                request.concept_ids,
                request.topic_keywords,
                config.min_governance_status,
            )

            # Find reviewed claims linked to these concepts
            claims = self._get_reviewed_claims_for_concepts(
                [c.id for c in concepts],
                config.min_governance_status,
            )

            # Build topic bundle
            bundle = LenssContract.create_topic_bundle(
                bundle_id=f"bundle_{request.topic_keywords[0] if request.topic_keywords else 'generic'}",
                topic_name=request.topic_keywords[0] if request.topic_keywords else "General Topic",
                topic_frame="information",
                patient_intent=request.audience_profile or "general",
            )

            # Add concepts
            for concept in concepts:
                lenss_concept = self._concept_to_lenss(concept)
                bundle = LenssContract.add_concept_to_bundle(bundle, lenss_concept)

            # Add claims
            for claim_data in claims:
                lenss_claim = self._claim_to_lenss(claim_data, concepts)
                bundle = LenssContract.add_claim_to_bundle(bundle, lenss_claim)

            # Validate bundle
            is_valid, errors = LenssContract.validate_bundle_for_lenss(bundle)

            if not is_valid and not config.allow_fallback:
                return LenssRetrievalResponse(
                    topic_bundle=bundle,
                    warnings=errors,
                    fallback_used=False,
                    fallback_reason="Validation failed and fallback not allowed",
                )

            if not is_valid:
                warnings.extend(errors)
                warnings.append("Using bundle with validation warnings")

            # Update governance status
            if config.min_governance_status == "active":
                bundle.governance_status = "reviewed"
            else:
                bundle.governance_status = "partial"

            retrieval_metadata["concepts_found"] = len(concepts)
            retrieval_metadata["claims_found"] = len(claims)

            return LenssRetrievalResponse(
                topic_bundle=bundle,
                retrieval_metadata=retrieval_metadata,
                warnings=warnings,
                fallback_used=False,
            )

        except Exception as e:
            if config.allow_fallback:
                return LenssRetrievalResponse(
                    topic_bundle=LenssContract.create_topic_bundle(
                        bundle_id="fallback",
                        topic_name=request.topic_keywords[0] if request.topic_keywords else "Fallback",
                        topic_frame="information",
                        patient_intent="general",
                    ),
                    retrieval_metadata=retrieval_metadata,
                    warnings=[f"Retrieval failed: {str(e)}", "Using fallback empty bundle"],
                    fallback_used=True,
                    fallback_reason=str(e),
                )
            else:
                raise

    def retrieve_for_press(
        self,
        request: PressRetrievalRequest,
        config: Optional[GovernedRetrievalConfig] = None,
    ) -> PressRetrievalResponse:
        """Retrieve governed evidence pack for Press.

        Args:
            request: Retrieval request from Press
            config: Optional retrieval configuration

        Returns:
            Governed retrieval response
        """
        if config is None:
            config = GovernedRetrievalConfig()

        warnings: List[str] = []
        retrieval_metadata: Dict[str, Any] = {
            "request": request.model_dump(),
            "config": config.model_dump(),
        }

        try:
            # Find reviewed concepts
            concepts = self._get_reviewed_concepts(
                request.concepts,
                [request.topic],
                config.min_governance_status,
            )

            if not concepts:
                if config.allow_fallback:
                    return PressContract.create_fallback_warning(
                        request,
                        "No reviewed concepts found for topic",
                    )
                else:
                    return PressRetrievalResponse(
                        evidence_pack=None,
                        warnings=["No reviewed concepts found and fallback not allowed"],
                        fallback_used=False,
                        fallback_reason="No reviewed concepts",
                    )

            # Build evidence pack
            pack = PressContract.create_evidence_pack(
                pack_id=f"pack_{request.topic}_{request.patient_profile}",
                topic=request.topic,
                patient_profile=request.patient_profile,
            )

            # Add concept explanations
            for concept in concepts:
                explanation = self._concept_to_press_explanation(concept)
                pack = PressContract.add_concept_explanation(pack, explanation)

            # Get evidence items
            evidence_items = self._get_evidence_for_concepts(
                [c.id for c in concepts],
                config.min_governance_status,
            )

            for ev in evidence_items:
                pack.evidence_items.append(PressEvidenceItem(
                    claim_text=ev.get("claim_text", ""),
                    evidence_summary=ev.get("summary", ""),
                    quality_indicators=ev.get("quality", {}),
                ))

            # Update metadata
            pack.is_medically_reviewed = config.min_governance_status == "active"
            pack.minimum_quality_threshold = config.min_governance_status
            pack.reading_level = request.reading_level

            # Validate pack
            is_valid, errors = PressContract.validate_pack_for_press(pack)

            if not is_valid:
                warnings.extend(errors)

            retrieval_metadata["concepts_found"] = len(concepts)
            retrieval_metadata["evidence_items"] = len(evidence_items)

            return PressRetrievalResponse(
                evidence_pack=pack,
                retrieval_metadata=retrieval_metadata,
                warnings=warnings,
                fallback_used=False,
            )

        except Exception as e:
            if config.allow_fallback:
                return PressContract.create_fallback_warning(
                    request,
                    str(e),
                )
            else:
                raise

    def _get_reviewed_concepts(
        self,
        concept_ids: List[str],
        keywords: List[str],
        min_status: str,
    ) -> List[Concept]:
        """Get reviewed concepts by ID or keyword search.

        Args:
            concept_ids: Specific concept IDs
            keywords: Keywords for search
            min_status: Minimum governance status

        Returns:
            List of reviewed concepts
        """
        concepts: List[Concept] = []

        # Get by IDs
        if concept_ids:
            for cid in concept_ids:
                concept = self.session.get(Concept, cid)
                if concept and self._meets_governance_status(concept.status, min_status):
                    concepts.append(concept)

        # Search by keywords
        if keywords and len(concepts) < 50:  # Limit results
            for keyword in keywords:
                results = self.session.query(Concept).filter(
                    Concept.canonical_name.ilike(f"%{keyword}%"),
                    Concept.status == min_status,
                ).limit(20).all()

                for concept in results:
                    if concept not in concepts:
                        concepts.append(concept)

        return concepts[:50]  # Limit total results

    def _get_reviewed_claims_for_concepts(
        self,
        concept_ids: List[str],
        min_status: str,
    ) -> List[Dict[str, Any]]:
        """Get reviewed claims for concepts.

        Args:
            concept_ids: Concept IDs
            min_status: Minimum governance status

        Returns:
            List of claim data
        """
        # For now, return empty list
        # In full implementation, this would query from claim tables
        return []

    def _get_evidence_for_concepts(
        self,
        concept_ids: List[str],
        min_status: str,
    ) -> List[Dict[str, Any]]:
        """Get evidence for concepts.

        Args:
            concept_ids: Concept IDs
            min_status: Minimum governance status

        Returns:
            List of evidence data
        """
        evidence_items: List[Dict[str, Any]] = []

        for cid in concept_ids:
            evidence = self.session.query(ConceptEvidence).filter_by(
                concept_id=cid
            ).all()

            for ev in evidence:
                evidence_items.append({
                    "claim_text": f"Evidence for {cid}",
                    "summary": f"Quality: {ev.quality_score:.2f}, Relevance: {ev.relevance_score:.2f}",
                    "quality": {
                        "score": ev.quality_score,
                        "relevance": ev.relevance_score,
                    },
                })

        return evidence_items[:10]

    def _meets_governance_status(self, status: str, min_status: str) -> bool:
        """Check if status meets minimum governance requirement.

        Args:
            status: Concept status
            min_status: Minimum required status

        Returns:
            True if meets requirement
        """
        status_hierarchy = {
            "active": 3,
            "under_review": 2,
            "pending_review": 1,
            "draft": 0,
        }

        return status_hierarchy.get(status, 0) >= status_hierarchy.get(min_status, 0)

    def _concept_to_lenss(self, concept: Concept) -> LenssConcept:
        """Convert a concept to Lenss format.

        Args:
            concept: Database concept

        Returns:
            Lenss concept
        """
        return LenssConcept(
            concept_id=concept.id,
            canonical_name=concept.canonical_name,
            category=ConceptCategory(concept.category),
            patient_friendly_name=concept.patient_friendly_name,
            patient_friendly_explanation=concept.patient_friendly_explanation,
            is_reviewed=concept.status == "active",
        )

    def _concept_to_press_explanation(self, concept: Concept) -> PressConceptExplanation:
        """Convert a concept to Press explanation format.

        Args:
            concept: Database concept

        Returns:
            Press concept explanation
        """
        # Get common aliases
        aliases = self.session.query(ConceptAlias).filter_by(
            concept_id=concept.id,
            status="active",
        ).limit(5).all()

        return PressConceptExplanation(
            concept_id=concept.id,
            canonical_name=concept.canonical_name,
            category=ConceptCategory(concept.category),
            patient_friendly_name=concept.patient_friendly_name or concept.canonical_name,
            patient_friendly_explanation=concept.patient_friendly_explanation or "",
            common_aliases=[a.alias for a in aliases],
            what_is_it=f"{concept.canonical_name} is a {concept.category} in medical terminology.",
            why_it_matters=f"Understanding {concept.canonical_name} can help you make informed decisions.",
            questions_to_ask=[
                f"What does {concept.canonical_name} mean for my condition?",
                f"How does {concept.canonical_name} affect my treatment?",
            ],
        )

    def _claim_to_lenss(
        self,
        claim_data: Dict[str, Any],
        concepts: List[Concept],
    ) -> LenssClaim:
        """Convert claim data to Lenss format.

        Args:
            claim_data: Claim data
            concepts: Related concepts

        Returns:
            Lenss claim
        """
        return LenssClaim(
            claim_id=claim_data.get("id", ""),
            claim_text=claim_data.get("text", ""),
            claim_type=ClaimType(claim_data.get("type", "fact")),
            certainty_level=CertaintyLevel(claim_data.get("certainty", "medium")),
            scope_note=claim_data.get("scope_note"),
            linked_concepts=[self._concept_to_lenss(c) for c in concepts[:3]],
            is_reviewed=claim_data.get("reviewed", True),
            evidence_quality_score=claim_data.get("quality", 0.7),
        )


__all__ = [
    "GovernedRetrievalService",
    "GovernedRetrievalConfig",
]
