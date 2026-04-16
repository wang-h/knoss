"""Knoss to Lenss Contract for Knoss.

This module defines the contract for knowledge transfer from Knoss
to the Lenss system for topic synthesis and audience targeting.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from ..models.types import ClaimType, CertaintyLevel, ConceptCategory


class LenssConcept(BaseModel):
    """Concept data for Lenss consumption."""
    concept_id: str
    canonical_name: str
    category: ConceptCategory
    patient_friendly_name: Optional[str] = None
    patient_friendly_explanation: Optional[str] = None
    is_reviewed: bool = True
    evidence_count: int = 0


class LenssClaim(BaseModel):
    """Claim data for Lenss consumption."""
    claim_id: str
    claim_text: str
    claim_type: ClaimType
    certainty_level: CertaintyLevel
    scope_note: Optional[str] = None
    linked_concepts: list[LenssConcept] = Field(default_factory=list)
    is_reviewed: bool = True
    evidence_quality_score: float = 0.7


class LenssAudienceProfile(BaseModel):
    """Audience profile for targeted content."""
    profile_id: str
    audience_type: str  # e.g., "patient", "caregiver", "general_public"
    demographics: dict[str, Any] = Field(default_factory=dict)
    health_literacy_level: str = "medium"  # "low", "medium", "high"
    information_needs: list[str] = Field(default_factory=list)
    preferred_topics: list[str] = Field(default_factory=list)


class LenssTopicBundle(BaseModel):
    """Topic bundle for Lenss consumption.

    A topic bundle contains reviewed claims and concepts organized
    around a specific topic for targeted content generation.
    """

    bundle_id: str
    topic_name: str
    topic_frame: str  # e.g., "follow_up_explainer", "treatment_decision"
    patient_intent: str
    summary: Optional[str] = None

    # Reviewed claims with concept links
    reviewed_claims: list[LenssClaim] = Field(default_factory=list)

    # Reviewed concepts with explanations
    reviewed_concepts: list[LenssConcept] = Field(default_factory=list)

    # Audience targeting metadata
    audience_profiles: list[LenssAudienceProfile] = Field(default_factory=list)

    # Evidence and quality indicators
    min_evidence_quality: float = 0.6
    governance_status: str = "reviewed"  # "reviewed", "partial", "pending"

    # Metadata
    source_articles: list[str] = Field(default_factory=list)
    created_at: Optional[str] = None
    reviewed_by: Optional[str] = None


class LenssRetrievalRequest(BaseModel):
    """Request for governed retrieval from Lenss."""

    topic_keywords: list[str] = Field(description="Keywords for topic matching")
    concept_ids: list[str] = Field(default_factory=list, description="Specific concept IDs to include")
    audience_profile: Optional[str] = Field(default=None, description="Target audience profile")
    min_governance_status: str = Field(default="active", description="Minimum governance status")
    include_evidence: bool = Field(default=True, description="Include evidence links")
    limit: int = Field(default=50, ge=1, le=500)


class LenssRetrievalResponse(BaseModel):
    """Response from governed retrieval."""

    topic_bundle: LenssTopicBundle
    retrieval_metadata: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    fallback_used: bool = False
    fallback_reason: Optional[str] = None


class LenssContract:
    """Contract interface for Knoss to Lenss communication.

    This contract defines:
    1. Data structures for topic bundles
    2. Retrieval interface with governance guarantees
    3. Fallback behavior when reviewed content is unavailable
    4. Quality and provenance metadata requirements
    """

    @staticmethod
    def create_topic_bundle(
        bundle_id: str,
        topic_name: str,
        topic_frame: str,
        patient_intent: str,
    ) -> LenssTopicBundle:
        """Create a new topic bundle.

        Args:
            bundle_id: Unique bundle identifier
            topic_name: Name of the topic
            topic_frame: Frame for the topic
            patient_intent: Patient intent description

        Returns:
            New topic bundle
        """
        return LenssTopicBundle(
            bundle_id=bundle_id,
            topic_name=topic_name,
            topic_frame=topic_frame,
            patient_intent=patient_intent,
            reviewed_claims=[],
            reviewed_concepts=[],
            audience_profiles=[],
            governance_status="pending",
        )

    @staticmethod
    def validate_bundle_for_lenss(bundle: LenssTopicBundle) -> tuple[bool, list[str]]:
        """Validate a topic bundle for Lenss consumption.

        Args:
            bundle: Topic bundle to validate

        Returns:
            Tuple of (is_valid, validation_errors)
        """
        errors = []

        # Check for reviewed content
        if not bundle.reviewed_claims and not bundle.reviewed_concepts:
            errors.append("Topic bundle contains no reviewed claims or concepts")

        # Check governance status
        if bundle.governance_status == "pending":
            errors.append("Topic bundle has not been reviewed")

        # Check evidence quality
        if bundle.reviewed_claims:
            low_quality_count = sum(
                1 for c in bundle.reviewed_claims
                if c.evidence_quality_score < 0.5
            )
            if low_quality_count > len(bundle.reviewed_claims) * 0.5:
                errors.append(f"More than 50% of claims have low evidence quality")

        # Check for audience targeting
        if not bundle.audience_profiles:
            errors.append("Topic bundle lacks audience profile information")

        return len(errors) == 0, errors

    @staticmethod
    def add_claim_to_bundle(
        bundle: LenssTopicBundle,
        claim: LenssClaim,
    ) -> LenssTopicBundle:
        """Add a reviewed claim to the bundle.

        Args:
            bundle: Topic bundle
            claim: Claim to add

        Returns:
            Updated bundle
        """
        bundle.reviewed_claims.append(claim)
        return bundle

    @staticmethod
    def add_concept_to_bundle(
        bundle: LenssTopicBundle,
        concept: LenssConcept,
    ) -> LenssTopicBundle:
        """Add a reviewed concept to the bundle.

        Args:
            bundle: Topic bundle
            concept: Concept to add

        Returns:
            Updated bundle
        """
        bundle.reviewed_concepts.append(concept)
        return bundle


__all__ = [
    "LenssContract",
    "LenssConcept",
    "LenssClaim",
    "LenssAudienceProfile",
    "LenssTopicBundle",
    "LenssRetrievalRequest",
    "LenssRetrievalResponse",
]
