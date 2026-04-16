"""Segmenter Agent implementation for Knoss.

The Segmenter Agent splits cleaned article content into structural and semantic
segments for downstream processing. It maintains source offsets and heading paths
for traceability.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from ..models.payloads import PreservedStructureBlock, SegmentModel
from ..models.types import SegmentLevel
from .base import Agent, AgentResult


class SegmenterInput(BaseModel):
    """Input payload for Segmenter Agent.

    Attributes:
        article_id: Unique identifier for the article
        title: Article title
        clean_text: Cleaned text from Cleaner Agent
        preserved_structure_blocks: Structure blocks from Cleaner Agent
    """

    article_id: str = Field(description="Unique identifier for the article")
    title: str = Field(description="Article title")
    clean_text: str = Field(description="Cleaned text from Cleaner Agent")
    preserved_structure_blocks: list[dict[str, Any] | PreservedStructureBlock] = Field(
        default_factory=list,
        description="Structure blocks from Cleaner Agent",
    )


class SegmenterOutput(BaseModel):
    """Output payload for Segmenter Agent.

    Attributes:
        segments: List of segments extracted from the article
    """

    segments: list[SegmentModel] = Field(default_factory=list)


class SegmenterAgent(Agent[SegmenterInput, SegmenterOutput]):
    """Agent that splits articles into structural and semantic segments.

    The Segmenter Agent processes cleaned articles by:
    1. Creating raw segments based on document structure (headings, paragraphs)
    2. Creating semantic segments by grouping related content
    3. Maintaining source offsets for traceability
    4. Assigning initial segment types based on content
    5. Building heading paths for navigation

    Segments can be:
    - Raw: Direct structural divisions (sections, subsections)
    - Semantic: Meaningful content units (procedures, explanations, warnings)
    """

    input_model = SegmenterInput
    output_model = SegmenterOutput

    # Segment type detection patterns
    _FOLLOW_UP_PATTERNS = [
        r"复查|随访|检查|监测",
        r"术后.*恢复|康复",
    ]

    _TREATMENT_PATTERNS = [
        r"治疗|方案|手术|化疗|放疗|靶向",
        r"药物|服用|用药",
    ]

    _WARNING_PATTERNS = [
        r"注意|警惕|避免|禁忌",
        r"不良反应|副作用|并发症",
    ]

    _DIAGNOSIS_PATTERNS = [
        r"诊断|分期|分级",
        r"检测|筛查|标志物",
    ]

    def execute(self, input_data: SegmenterInput) -> AgentResult:
        """Execute segmentation on cleaned article content.

        Args:
            input_data: Validated input with cleaned text and structure

        Returns:
            AgentResult with list of SegmentModel outputs
        """
        if not input_data.clean_text:
            return AgentResult.fail("No clean text provided for segmentation")

        warnings = []
        metadata = {"article_id": input_data.article_id}

        # Parse structure blocks
        structure_blocks = self._parse_structure_blocks(
            input_data.preserved_structure_blocks,
        )

        # Create raw segments from structure
        raw_segments = self._create_raw_segments(
            input_data.clean_text,
            input_data.title,
            structure_blocks,
        )

        # Create semantic segments from raw segments
        all_segments = self._create_semantic_segments(raw_segments)

        # Assign initial segment types
        all_segments = self._assign_segment_types(all_segments)

        # Calculate char offsets
        all_segments = self._calculate_char_offsets(
            input_data.clean_text,
            all_segments,
        )

        metadata["raw_segment_count"] = len(raw_segments)
        metadata["semantic_segment_count"] = len(all_segments)

        # Check for potential noise
        noise_count = sum(1 for s in all_segments if s.is_noise)
        if noise_count > 0:
            warnings.append(f"Marked {noise_count} segments as potential noise")
            metadata["noise_segment_count"] = noise_count

        return AgentResult.ok(
            output=SegmenterOutput(segments=all_segments),
            warnings=warnings,
            metadata=metadata,
        )

    def _parse_structure_blocks(
        self,
        blocks: list[dict[str, Any] | PreservedStructureBlock],
    ) -> list[PreservedStructureBlock]:
        """Parse structure blocks from input.

        Args:
            blocks: Structure blocks from Cleaner Agent

        Returns:
            List of validated PreservedStructureBlock instances
        """
        parsed = []
        for block in blocks:
            if isinstance(block, PreservedStructureBlock):
                parsed.append(block)
            else:
                parsed.append(PreservedStructureBlock.model_validate(block))
        return parsed

    def _create_raw_segments(
        self,
        clean_text: str,
        title: str,
        structure_blocks: list[PreservedStructureBlock],
    ) -> list[SegmentModel]:
        """Create raw segments from document structure.

        Args:
            clean_text: The cleaned article text
            title: Article title
            structure_blocks: Parsed structure blocks

        Returns:
            List of raw-level segments
        """
        segments: list[SegmentModel] = []
        lines = clean_text.split("\n")

        current_heading_path: list[str] = [title]
        segment_index = 0
        buffer: list[str] = []
        buffer_start = 0

        def flush_buffer(parent_idx: int | None = None) -> None:
            nonlocal segment_index, buffer_start
            if buffer:
                text = " ".join(buffer).strip()
                if len(text) > 10:
                    segments.append(
                        SegmentModel(
                            segment_index=segment_index,
                            parent_segment_index=parent_idx,
                            level=SegmentLevel.RAW,
                            heading_path=current_heading_path.copy(),
                            text=text,
                            char_start=buffer_start,
                            char_end=buffer_start + len(text),
                        )
                    )
                    segment_index += 1
                buffer_start += len(text) + 1
                buffer.clear()

        char_pos = 0
        for line in lines:
            stripped = line.strip()

            if not stripped:
                flush_buffer()
                char_pos += len(line) + 1
                continue

            if self._is_heading(stripped):
                flush_buffer()

                heading_level = self._get_heading_level(stripped)
                heading_text = stripped.lstrip("#").strip()

                if heading_level == 1:
                    current_heading_path = [heading_text]
                elif heading_level == 2:
                    if len(current_heading_path) > 1:
                        current_heading_path[1:] = [heading_text]
                    else:
                        current_heading_path.append(heading_text)
                else:
                    while len(current_heading_path) >= heading_level:
                        current_heading_path.pop()
                    current_heading_path.append(heading_text)

                segments.append(
                    SegmentModel(
                        segment_index=segment_index,
                        parent_segment_index=None,
                        level=SegmentLevel.RAW,
                        heading_path=current_heading_path.copy(),
                        text=heading_text,
                        segment_type_initial="heading",
                        char_start=char_pos,
                        char_end=char_pos + len(stripped),
                    )
                )
                segment_index += 1
            else:
                buffer.append(stripped)

            char_pos += len(line) + 1

        flush_buffer()

        return segments

    def _create_semantic_segments(
        self,
        raw_segments: list[SegmentModel],
    ) -> list[SegmentModel]:
        """Create semantic segments by splitting or grouping raw segments.

        Args:
            raw_segments: List of raw-level segments

        Returns:
            List including both raw and semantic segments
        """
        all_segments: list[SegmentModel] = []
        semantic_index = 0

        for raw_seg in raw_segments:
            all_segments.append(raw_seg)

            if raw_seg.segment_type_initial == "heading":
                continue

            if len(raw_seg.text) > 300:
                semantic_subsegments = self._split_into_semantic_units(
                    raw_seg,
                    semantic_index,
                )
                all_segments.extend(semantic_subsegments)
                semantic_index += len(semantic_subsegments)
            else:
                semantic_seg = SegmentModel(
                    segment_index=semantic_index,
                    parent_segment_index=raw_seg.segment_index,
                    level=SegmentLevel.SEMANTIC,
                    heading_path=raw_seg.heading_path,
                    text=raw_seg.text,
                    char_start=raw_seg.char_start,
                    char_end=raw_seg.char_end,
                )
                all_segments.append(semantic_seg)
                semantic_index += 1

        return all_segments

    def _split_into_semantic_units(
        self,
        parent_segment: SegmentModel,
        start_index: int,
    ) -> list[SegmentModel]:
        """Split a long raw segment into semantic units.

        Args:
            parent_segment: The parent raw segment
            start_index: Starting index for semantic segments

        Returns:
            List of semantic-level segments
        """
        text = parent_segment.text
        semantic_segments: list[SegmentModel] = []

        sentences = re.split(r"([。！？\n])", text)

        current_buffer: list[str] = []
        current_offset = parent_segment.char_start or 0

        for i in range(0, len(sentences) - 1, 2):
            sentence = sentences[i]
            delimiter = sentences[i + 1] if i + 1 < len(sentences) else ""

            full_sentence = sentence + delimiter
            current_buffer.append(full_sentence)

            buffer_text = "".join(current_buffer)

            if len(buffer_text) > 150 or delimiter in ("。", "！", "？"):
                semantic_segments.append(
                    SegmentModel(
                        segment_index=start_index + len(semantic_segments),
                        parent_segment_index=parent_segment.segment_index,
                        level=SegmentLevel.SEMANTIC,
                        heading_path=parent_segment.heading_path,
                        text=buffer_text.strip(),
                        char_start=current_offset,
                        char_end=current_offset + len(buffer_text.strip()),
                    )
                )
                current_offset += len(buffer_text) + 1
                current_buffer = []

        if current_buffer:
            buffer_text = "".join(current_buffer).strip()
            if buffer_text:
                semantic_segments.append(
                    SegmentModel(
                        segment_index=start_index + len(semantic_segments),
                        parent_segment_index=parent_segment.segment_index,
                        level=SegmentLevel.SEMANTIC,
                        heading_path=parent_segment.heading_path,
                        text=buffer_text,
                        char_start=current_offset,
                        char_end=current_offset + len(buffer_text),
                    )
                )

        return semantic_segments

    def _assign_segment_types(self, segments: list[SegmentModel]) -> list[SegmentModel]:
        """Assign initial segment types based on content.

        Args:
            segments: List of segments to type

        Returns:
            List of segments with assigned types
        """
        for segment in segments:
            if segment.segment_type_initial:
                continue

            segment_type = self._detect_segment_type(segment.text)
            segment.segment_type_initial = segment_type

        return segments

    def _detect_segment_type(self, text: str) -> str:
        """Detect the type of a segment based on its content.

        Args:
            text: The segment text to analyze

        Returns:
            Detected segment type
        """
        if any(re.search(p, text) for p in self._FOLLOW_UP_PATTERNS):
            return "follow_up"
        if any(re.search(p, text) for p in self._WARNING_PATTERNS):
            return "warning"
        if any(re.search(p, text) for p in self._DIAGNOSIS_PATTERNS):
            return "diagnosis"
        if any(re.search(p, text) for p in self._TREATMENT_PATTERNS):
            return "treatment"

        return "general"

    def _calculate_char_offsets(
        self,
        clean_text: str,
        segments: list[SegmentModel],
    ) -> list[SegmentModel]:
        """Calculate and validate character offsets for segments.

        Args:
            clean_text: The source clean text
            segments: List of segments to update

        Returns:
            List of segments with validated offsets
        """
        for segment in segments:
            if segment.char_start is None or segment.char_end is None:
                pos = clean_text.find(segment.text[:50])
                if pos >= 0:
                    segment.char_start = pos
                    segment.char_end = pos + len(segment.text)

        return segments

    def _is_heading(self, line: str) -> bool:
        """Check if a line is a heading.

        Args:
            line: The line to check

        Returns:
            True if the line appears to be a heading
        """
        if line.startswith("#"):
            return True

        if len(line) < 30 and re.match(r"^[\u4e00-\u9fff]{2,15}$", line):
            return True

        return False

    def _get_heading_level(self, line: str) -> int:
        """Get the heading level from a heading line.

        Args:
            line: The heading line

        Returns:
            Heading level (1-6)
        """
        match = re.match(r"^(#{1,6})\s", line)
        if match:
            return len(match.group(1))

        return 2


__all__ = ["SegmenterAgent", "SegmenterInput", "SegmenterOutput"]
