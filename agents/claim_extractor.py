"""Claim Extractor Agent implementation for Knoss.

The Claim Extractor Agent extracts atomic medical claims from article segments.
Each claim is a self-contained statement that can be verified, traced,
and used for evidence curation.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from ..models.payloads import ClaimModel, SegmentModel
from ..models.types import CertaintyLevel, ClaimType
from .base import Agent, AgentResult


class ClaimExtractorInput(BaseModel):
    """Input payload for Claim Extractor Agent.

    Attributes:
        article_id: Unique identifier for the article
        segment: Segment to extract claims from
        existing_claims: Optional list of existing claims to avoid duplicates
    """

    article_id: str = Field(description="Unique identifier for the article")
    segment: dict[str, Any] | SegmentModel = Field(
        description="Segment to extract claims from",
    )
    existing_claims: list[dict[str, Any] | ClaimModel] = Field(
        default_factory=list,
        description="Existing claims to avoid duplicates",
    )


class ClaimExtractorOutput(BaseModel):
    """Output payload for Claim Extractor Agent.

    Attributes:
        claims: List of claims extracted from the segment
    """

    claims: list[ClaimModel] = Field(default_factory=list)


class ClaimExtractorAgent(Agent[ClaimExtractorInput, ClaimExtractorOutput]):
    """Agent that extracts atomic medical claims from segments.

    The Claim Extractor Agent processes semantic segments by:
    1. Identifying discrete factual claims within the segment text
    2. Classifying each claim by type (fact, recommendation, warning, etc.)
    3. Assessing certainty level (high, medium, low)
    4. Normalizing claim text for consistency
    5. Adding scope notes for context

    Claims are atomic - each represents a single verifiable statement.
    This enables precise evidence tracing and fact-checking.
    """

    input_model = ClaimExtractorInput
    output_model = ClaimExtractorOutput

    # Claim type detection patterns
    _RECOMMENDATION_PATTERNS = [
        r"应该|应当|建议|推荐",
        r"需要[要]|要[去可]",
        r"可以[考虑选择]",
    ]

    _WARNING_PATTERNS = [
        r"注意|警惕|避免|禁止",
        r"不要[需]|不宜",
        r"[副不]反应|副作用|并发症",
    ]

    _FACT_PATTERNS = [
        r"是[的为]{0,2}",
        r"[有含有具]备",
        r"包括[含有]",
    ]

    _CASE_PATTERNS = [
        r"[例个案病]例",
        r"临床.*研究",
        r"[试验观察]显示",
    ]

    def execute(self, input_data: ClaimExtractorInput) -> AgentResult:
        """Execute claim extraction from a segment.

        Args:
            input_data: Validated input with segment to process

        Returns:
            AgentResult with list of ClaimModel outputs
        """
        segment = self._parse_segment(input_data.segment)

        if not segment.text:
            return AgentResult.fail("Segment has no text content")

        warnings = []
        metadata = {
            "article_id": input_data.article_id,
            "segment_index": segment.segment_index,
        }

        # Skip noise segments
        if segment.is_noise:
            metadata["skipped"] = "noise_segment"
            return AgentResult.ok(
                output=ClaimExtractorOutput(claims=[]),
                warnings=["Skipped noise segment"],
                metadata=metadata,
            )

        # Parse existing claims for deduplication
        existing_texts = self._get_existing_claim_texts(input_data.existing_claims)

        # Extract claims from segment text
        claims = self._extract_claims(
            segment,
            existing_texts,
            input_data.article_id,
        )

        metadata["claim_count"] = len(claims)

        if not claims:
            warnings.append("No claims extracted from segment")

        return AgentResult.ok(
            output=ClaimExtractorOutput(claims=claims),
            warnings=warnings,
            metadata=metadata,
        )

    def _parse_segment(self, segment: dict[str, Any] | SegmentModel) -> SegmentModel:
        """Parse segment from input.

        Args:
            segment: Segment from input

        Returns:
            Validated SegmentModel instance
        """
        if isinstance(segment, SegmentModel):
            return segment
        return SegmentModel.model_validate(segment)

    def _get_existing_claim_texts(
        self,
        claims: list[dict[str, Any] | ClaimModel],
    ) -> set[str]:
        """Extract normalized text from existing claims.

        Args:
            claims: List of existing claims

        Returns:
            Set of normalized claim texts
        """
        texts = set()
        for claim in claims:
            if isinstance(claim, ClaimModel):
                if claim.normalized_text:
                    texts.add(claim.normalized_text)
                else:
                    texts.add(claim.claim_text)
            else:
                normalized = claim.get("normalized_text")
                if normalized:
                    texts.add(normalized)
                else:
                    texts.add(claim.get("claim_text", ""))
        return texts

    def _extract_claims(
        self,
        segment: SegmentModel,
        existing_texts: set[str],
        article_id: str,
    ) -> list[ClaimModel]:
        """Extract atomic claims from segment text.

        Args:
            segment: The segment to extract from
            existing_texts: Existing claim texts for deduplication
            article_id: Article ID for generating segment IDs

        Returns:
            List of extracted claims
        """
        text = segment.text

        # Split text into potential claim units
        claim_units = self._split_into_claim_units(text)

        claims = []
        claim_index = 0

        for unit_text in claim_units:
            if len(unit_text.strip()) < 10:
                continue

            normalized = self._normalize_claim(unit_text)
            if normalized in existing_texts:
                continue

            claim_type = self._classify_claim_type(unit_text)
            certainty = self._assess_certainty(unit_text, claim_type)

            scope_note = self._generate_scope_note(
                unit_text,
                segment.heading_path,
            )

            claim = ClaimModel(
                claim_index=claim_index,
                claim_text=unit_text.strip(),
                claim_type=claim_type,
                certainty_level=certainty,
                scope_note=scope_note,
                normalized_text=normalized,
                segment_id=f"seg_{article_id}_{segment.level}_{segment.segment_index}",
            )

            claims.append(claim)
            existing_texts.add(normalized)
            claim_index += 1

        return claims

    def _split_into_claim_units(self, text: str) -> list[str]:
        """Split text into potential claim units.

        Args:
            text: The text to split

        Returns:
            List of claim unit strings
        """
        pattern = r"[。！？.!?]+"
        units = re.split(pattern, text)

        result = []
        for unit in units:
            unit = unit.strip()
            if len(unit) >= 10:
                result.append(unit)

        return result

    def _normalize_claim(self, text: str) -> str:
        """Normalize claim text for deduplication.

        Args:
            text: The claim text to normalize

        Returns:
            Normalized claim text
        """
        text = re.sub(r"\s+", " ", text).strip()

        filler_patterns = [
            r"\[注\d*\]",
            r"\(注[^\)]*\)",
            r"另外|此外|同时",
        ]

        for pattern in filler_patterns:
            text = re.sub(pattern, "", text)

        return text.strip()

    def _classify_claim_type(self, text: str) -> ClaimType:
        """Classify a claim by its type.

        Args:
            text: The claim text to classify

        Returns:
            Classified claim type
        """
        if any(re.search(p, text) for p in self._WARNING_PATTERNS):
            return ClaimType.WARNING

        if any(re.search(p, text) for p in self._RECOMMENDATION_PATTERNS):
            return ClaimType.RECOMMENDATION

        if any(re.search(p, text) for p in self._CASE_PATTERNS):
            return ClaimType.CASE

        opinion_markers = ["认为", "觉得", "可能", "也许", "推测"]
        if any(marker in text for marker in opinion_markers):
            return ClaimType.OPINION

        return ClaimType.FACT

    def _assess_certainty(
        self,
        text: str,
        claim_type: ClaimType,
    ) -> CertaintyLevel:
        """Assess the certainty level of a claim.

        Args:
            text: The claim text to assess
            claim_type: The classified claim type

        Returns:
            Assessed certainty level
        """
        high_markers = [
            r"必须|一定|确定|确认",
            r"明确|肯定|无疑",
            r"[已经]+证实|证明",
        ]

        low_markers = [
            r"可能|也许|或许",
            r"大概|估计|推测",
            r"有待.*[进一步]*[研究观察证实]",
        ]

        if any(re.search(p, text) for p in high_markers):
            return CertaintyLevel.HIGH

        if any(re.search(p, text) for p in low_markers):
            return CertaintyLevel.LOW

        if claim_type == ClaimType.WARNING:
            return CertaintyLevel.HIGH
        if claim_type == ClaimType.OPINION:
            return CertaintyLevel.LOW
        if claim_type == ClaimType.RECOMMENDATION:
            return CertaintyLevel.MEDIUM

        return CertaintyLevel.MEDIUM

    def _generate_scope_note(
        self,
        text: str,
        heading_path: list[str],
    ) -> str | None:
        """Generate a scope note for the claim.

        Args:
            text: The claim text
            heading_path: Heading path from the segment

        Returns:
            Scope note or None
        """
        if heading_path:
            context = heading_path[-1] if len(heading_path) == 1 else heading_path[1]

            if "术后" in text or "手术后" in text:
                return f"适用于{context}的术后患者"
            if "复查" in text or "随访" in text:
                return f"适用于{context}的复查随访"
            if "治疗" in text or "用药" in text:
                return f"适用于{context}的治疗决策"

        return None


__all__ = ["ClaimExtractorAgent", "ClaimExtractorInput", "ClaimExtractorOutput"]
