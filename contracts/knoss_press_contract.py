"""Knoss to Press Contract for Knoss.

This module defines the contract for knowledge transfer from Knoss
to the Press system for patient-friendly article generation.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from ..models.types import ConceptCategory


class PressConceptExplanation(BaseModel):
    """Patient-friendly explanation for Press consumption."""
    concept_id: str
    canonical_name: str
    category: ConceptCategory
    patient_friendly_name: str
    patient_friendly_explanation: str
    common_aliases: list[str] = Field(default_factory=list)
    what_is_it: Optional[str] = Field(default=None, description="Simple 'what is this' explanation")
    why_it_matters: Optional[str] = Field(default=None, description="Why this matters to the patient")
    questions_to_ask: list[str] = Field(default_factory=list, description="Suggested questions for doctor")


class PressEvidenceItem(BaseModel):
    """Evidence item for Press consumption."""
    claim_text: str
    evidence_summary: str
    quality_indicators: dict[str, Any] = Field(default_factory=dict)
    source_attribution: Optional[str] = None


class PressEvidencePack(BaseModel):
    """Evidence pack for Press consumption.

    Contains evidence organized for patient-friendly content generation.
    """

    pack_id: str
    topic: str
    patient_profile: str

    # Patient-friendly concept explanations
    concept_explanations: list[PressConceptExplanation] = Field(default_factory=list)

    # Evidence items with simple summaries
    evidence_items: list[PressEvidenceItem] = Field(default_factory=list)

    # Quality and safety metadata
    is_medically_reviewed: bool = False
    minimum_quality_threshold: float = 0.6
    safety_warnings: list[str] = Field(default_factory=list)

    # Reading level and accessibility
    reading_level: str = "medium"  # "low", "medium", "high"
    estimated_reading_time_minutes: int = 5

    # Metadata
    last_updated: Optional[str] = None
    reviewed_by: Optional[str] = None


class PressRetrievalRequest(BaseModel):
    """Request for evidence pack from Press."""

    topic: str = Field(description="Topic for evidence pack")
    concepts: list[str] = Field(default_factory=list, description="Concept IDs to include")
    patient_profile: str = Field(default="general", description="Target patient profile")
    reading_level: str = Field(default="medium", description="Target reading level")
    include_safety_warnings: bool = Field(default=True, description="Include safety warnings")
    min_review_status: str = Field(default="active", description="Minimum review status")


class PressRetrievalResponse(BaseModel):
    """Response from Press evidence pack retrieval."""

    evidence_pack: Optional[PressEvidencePack] = None
    retrieval_metadata: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    # Fallback information if pack couldn't be created
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    alternative_suggestions: list[str] = Field(default_factory=list)


class PressContentRequest(BaseModel):
    """Request for content generation assistance."""

    topic: str
    target_audience: str
    content_type: str  # "explainer", "faq", "checklist", etc.
    tone: str = "supportive"  # "supportive", "neutral", "authoritative"
    max_reading_time_minutes: int = 5


class PressContentAssistance(BaseModel):
    """Content generation assistance from Knoss.

    Provides reviewed concepts and explanations to help with
    patient-friendly content generation.
    """

    topic: str
    key_concepts: list[PressConceptExplanation]
    suggested_structure: list[dict[str, Any]] = Field(default_factory=list)
    plain_language_alternatives: dict[str, str] = Field(default_factory=dict)
    common_misconceptions: list[dict[str, Any]] = Field(default_factory=list)
    questions_to_address: list[str] = Field(default_factory=list)


class PressContract:
    """Contract interface for Knoss to Press communication.

    This contract defines:
    1. Evidence pack structure for patient-friendly content
    2. Patient-friendly explanation formats
    3. Reading level and accessibility requirements
    4. Safety warning inclusion
    5. Fallback behavior when reviewed content is unavailable
    """

    @staticmethod
    def create_evidence_pack(
        pack_id: str,
        topic: str,
        patient_profile: str,
    ) -> PressEvidencePack:
        """Create a new evidence pack.

        Args:
            pack_id: Unique pack identifier
            topic: Topic for the pack
            patient_profile: Target patient profile

        Returns:
            New evidence pack
        """
        return PressEvidencePack(
            pack_id=pack_id,
            topic=topic,
            patient_profile=patient_profile,
            concept_explanations=[],
            evidence_items=[],
        )

    @staticmethod
    def validate_pack_for_press(pack: PressEvidencePack) -> tuple[bool, list[str]]:
        """Validate an evidence pack for Press consumption.

        Args:
            pack: Evidence pack to validate

        Returns:
            Tuple of (is_valid, validation_errors)
        """
        errors = []

        # Check for content
        if not pack.concept_explanations and not pack.evidence_items:
            errors.append("Evidence pack contains no concepts or evidence")

        # Check for medical review
        if not pack.is_medically_reviewed:
            errors.append("Evidence pack has not been medically reviewed")

        # Check quality threshold
        if pack.minimum_quality_threshold < 0.5:
            errors.append("Evidence pack quality threshold is too low")

        # Check for patient-friendly explanations
        for concept in pack.concept_explanations:
            if not concept.patient_friendly_explanation:
                errors.append(f"Concept '{concept.canonical_name}' lacks patient-friendly explanation")

        return len(errors) == 0, errors

    @staticmethod
    def add_concept_explanation(
        pack: PressEvidencePack,
        explanation: PressConceptExplanation,
    ) -> PressEvidencePack:
        """Add a concept explanation to the pack.

        Args:
            pack: Evidence pack
            explanation: Concept explanation to add

        Returns:
            Updated pack
        """
        pack.concept_explanations.append(explanation)
        return pack

    @staticmethod
    def create_fallback_warning(
        original_request: PressRetrievalRequest,
        reason: str,
    ) -> PressRetrievalResponse:
        """Create a response with fallback warning.

        Args:
            original_request: Original request
            reason: Reason for fallback

        Returns:
            Response with fallback warning
        """
        return PressRetrievalResponse(
            evidence_pack=None,
            fallback_used=True,
            fallback_reason=reason,
            warnings=[
                f"Could not create evidence pack for topic '{original_request.topic}': {reason}",
                "Fallback: Using ungoverned content - medical review required before publication",
            ],
            retrieval_metadata={
                "original_request": original_request.model_dump(),
                "fallback_reason": reason,
            },
        )

    @staticmethod
    def get_content_assistance(
        topic: str,
        concepts: list[PressConceptExplanation],
        target_audience: str = "patient",
        content_type: str = "explainer",
    ) -> PressContentAssistance:
        """Get content generation assistance.

        Args:
            topic: Content topic
            concepts: Key concepts to cover
            target_audience: Target audience
            content_type: Type of content

        Returns:
            Content generation assistance
        """
        # Generate suggested structure based on content type
        if content_type == "explainer":
            suggested_structure = [
                {"section": "introduction", "title": f"What is {topic}?"},
                {"section": "key_concepts", "title": "Key Terms to Understand"},
                {"section": "how_it_works", "title": "How It Works"},
                {"section": "what_to_expect", "title": "What to Expect"},
                {"section": "questions", "title": "Questions to Ask Your Doctor"},
            ]
        elif content_type == "faq":
            suggested_structure = [
                {"section": "overview", "title": "Common Questions About {topic}"},
                {"section": "faq_list", "title": "Frequently Asked Questions"},
            ]
        else:
            suggested_structure = [
                {"section": "introduction", "title": f"Understanding {topic}"},
            ]

        return PressContentAssistance(
            topic=topic,
            key_concepts=concepts,
            suggested_structure=suggested_structure,
            plain_language_alternatives={
                c.canonical_name: c.patient_friendly_name
                for c in concepts
            },
        )


__all__ = [
    "PressContract",
    "PressConceptExplanation",
    "PressEvidenceItem",
    "PressEvidencePack",
    "PressRetrievalRequest",
    "PressRetrievalResponse",
    "PressContentRequest",
    "PressContentAssistance",
]
