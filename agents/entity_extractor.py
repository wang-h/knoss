"""Entity Extractor Agent implementation for Knoss.

The Entity Extractor Agent detects and normalizes medical terminology within
segments and claims. It identifies entities like diseases, drugs, markers,
and links them to the concept dictionary.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from ..models.payloads import ClaimModel, EntityModel, SegmentModel
from ..models.types import EntityType
from .base import Agent, AgentResult


class EntityExtractorInput(BaseModel):
    """Input payload for Entity Extractor Agent.

    Attributes:
        article_id: Unique identifier for the article
        segment: Segment to extract entities from
        claims: Claims in the segment for context
        concept_dictionary_snapshot: Optional snapshot of concept dictionary
    """

    article_id: str = Field(description="Unique identifier for the article")
    segment: dict[str, Any] | SegmentModel = Field(
        description="Segment to extract entities from",
    )
    claims: list[dict[str, Any] | ClaimModel] = Field(
        default_factory=list,
        description="Claims in the segment for context",
    )
    concept_dictionary_snapshot: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Optional concept dictionary for matching",
    )


class EntityExtractorOutput(BaseModel):
    """Output payload for Entity Extractor Agent.

    Attributes:
        entities: List of entities extracted from the segment
    """

    entities: list[EntityModel] = Field(default_factory=list)


class EntityExtractorAgent(Agent[EntityExtractorInput, EntityExtractorOutput]):
    """Agent that detects and normalizes medical terminology.

    The Entity Extractor Agent processes segments by:
    1. Identifying medical entities (diseases, drugs, markers, etc.)
    2. Extracting entity text with character offsets
    3. Classifying entity type
    4. Matching to canonical concepts from the dictionary
    5. Assigning confidence scores

    This enables downstream taxonomy assignment and evidence traceability.
    """

    input_model = EntityExtractorInput
    output_model = EntityExtractorOutput

    # Entity detection patterns
    _DISEASE_PATTERNS = [
        r"[乳腺肺肝胃宫颈卵巢甲状腺][癌瘤]+",
        r"[白血病淋巴瘤]+",
        r"糖尿病",
        r"高血压",
        r"冠心病|心梗",
    ]

    _DRUG_PATTERNS = [
        r"[阿匹][司匹林]+",
        r"[曲妥珠单抗帕妥珠单抗]+",
        r"[他莫昔芬来曲唑]+",
        r"[化疗靶向免疫]+[药药物]",
        r".*?[单抗抗体药物]",
    ]

    _MARKER_PATTERNS = [
        r"HER[02]",
        r"ER|PR",
        r"Ki-?67",
        r"CA-?\d+",
        r"[癌胚抗原CEA]+",
        r"[肿瘤标志物]+",
        r"血糖|血压|心率|体温|呼吸|体重",
    ]

    _TREATMENT_PATTERNS = [
        r"[化疗放疗靶向免疫]+[疗法治疗]",
        r"[手术切除移植]+",
        r"[内分泌激素]+[治疗疗法]",
    ]

    _TEST_PATTERNS = [
        r"[CTMRI超声B超X光]+[检查显像]",
        r"[穿刺活检]+",
        r"[血尿常规]+",
        r"[基因检测]+",
    ]

    # Special classification rules
    _SPECIAL_CLASSIFICATIONS = {
        "受体": "marker",
        "因子": "marker",
        "酶": "marker",
        "指标": "marker",
        "抑制": "drug",
        "阻滞": "drug",
        "激动": "drug",
    }

    _DRUG_SUFFIXES = ["抑制剂", "阻滞剂", "激动剂", "单抗", "药物"]
    _MARKER_SUFFIXES = ["受体", "因子", "酶", "指标", "水平"]

    def execute(self, input_data: EntityExtractorInput) -> AgentResult:
        """Execute terminology detection from a segment.

        Args:
            input_data: Validated input with segment to process

        Returns:
            AgentResult with list of EntityModel outputs
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
                output=EntityExtractorOutput(entities=[]),
                warnings=["Skipped noise segment"],
                metadata=metadata,
            )

        # Build concept lookup from snapshot
        concept_lookup = self._build_concept_lookup(
            input_data.concept_dictionary_snapshot,
        )

        # Extract entities from segment text
        entities = self._extract_entities(
            segment,
            concept_lookup,
            input_data.article_id,
        )

        metadata["entity_count"] = len(entities)

        if not entities:
            warnings.append("No entities extracted from segment")

        return AgentResult.ok(
            output=EntityExtractorOutput(entities=entities),
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

    def _build_concept_lookup(
        self,
        snapshot: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Build a lookup dictionary from concept snapshot.

        Args:
            snapshot: Concept dictionary snapshot

        Returns:
            Dictionary mapping names/aliases to concept info
        """
        lookup: dict[str, dict[str, Any]] = {}

        for concept in snapshot:
            canonical = concept.get("canonical_name", "")
            category = concept.get("category", "")
            aliases = concept.get("aliases", [])

            if canonical:
                lookup[canonical] = {
                    "canonical_name": canonical,
                    "category": category,
                }

            for alias in aliases:
                lookup[alias] = {
                    "canonical_name": canonical,
                    "category": category,
                }

        return lookup

    def _extract_entities(
        self,
        segment: SegmentModel,
        concept_lookup: dict[str, dict[str, Any]],
        article_id: str,
    ) -> list[EntityModel]:
        """Extract medical entities from segment text.

        Args:
            segment: The segment to extract from
            concept_lookup: Concept dictionary for matching
            article_id: Article ID for generating segment IDs

        Returns:
            List of extracted entities
        """
        text = segment.text
        entities: list[EntityModel] = []
        seen_positions: set[tuple[int, int]] = set()
        entity_index = 0

        all_patterns = [
            (self._DISEASE_PATTERNS, "disease"),
            (self._DRUG_PATTERNS, "drug"),
            (self._MARKER_PATTERNS, "marker"),
            (self._TREATMENT_PATTERNS, "treatment"),
            (self._TEST_PATTERNS, "test"),
        ]

        for patterns, entity_type in all_patterns:
            for pattern in patterns:
                for match in re.finditer(pattern, text):
                    start, end = match.span()

                    if self._overlaps((start, end), seen_positions):
                        continue

                    entity_text = match.group()

                    if not self._is_valid_entity(entity_text):
                        continue

                    candidate_name, confidence = self._match_to_concept(
                        entity_text,
                        entity_type,
                        concept_lookup,
                    )

                    improved_type = self._improve_entity_classification(
                        entity_text, entity_type, text, start, end
                    )

                    entity = EntityModel(
                        entity_index=entity_index,
                        entity_text=entity_text,
                        entity_type=improved_type,
                        candidate_canonical_name=candidate_name,
                        confidence=confidence,
                        segment_id=f"seg_{article_id}_{segment.level}_{segment.segment_index}",
                    )

                    entities.append(entity)
                    seen_positions.add((start, end))
                    entity_index += 1

        entities.sort(key=lambda e: e.entity_index)

        return entities

    def _improve_entity_classification(
        self,
        entity_text: str,
        initial_type: str,
        full_text: str,
        start: int,
        end: int,
    ) -> str:
        """Improve entity classification based on patterns and context.

        Args:
            entity_text: The entity text to classify
            initial_type: The initially detected type
            full_text: The full segment text for context
            start: Entity start position
            end: Entity end position

        Returns:
            Improved entity type
        """
        for pattern, correct_type in self._SPECIAL_CLASSIFICATIONS.items():
            if pattern in entity_text:
                if pattern == "受体":
                    context_window = 20
                    context_start = max(0, start - context_window)
                    context_end = min(len(full_text), end + context_window)
                    context = full_text[context_start:context_end]

                    if any(word in context for word in ["抑制剂", "阻滞剂", "拮抗剂", "调节剂"]):
                        return "drug"
                    else:
                        return correct_type
                else:
                    return correct_type

        if entity_text.endswith(tuple(self._DRUG_SUFFIXES)):
            return "drug"
        elif entity_text.endswith(tuple(self._MARKER_SUFFIXES)):
            return "marker"

        if initial_type == "treatment":
            if "药" in entity_text or "物" in entity_text:
                return "drug"
            elif "检" in entity_text or "查" in entity_text or "测" in entity_text:
                return "test"

        if initial_type == "drug":
            if "受体" in entity_text or "因子" in entity_text:
                return "marker"
            elif "反应" in entity_text or "效果" in entity_text:
                return "marker"

        if initial_type == "test":
            if "水平" in entity_text or "指数" in entity_text or "比值" in entity_text:
                return "marker"
            if entity_text.startswith("CA") and entity_text[2:].isdigit():
                return "marker"

        if entity_text in ["血糖", "血压", "心率", "体温", "呼吸"]:
            return "marker"

        return initial_type

    def _overlaps(
        self,
        span: tuple[int, int],
        existing: set[tuple[int, int]],
    ) -> bool:
        """Check if a span overlaps with existing spans.

        Args:
            span: The (start, end) position to check
            existing: Set of existing (start, end) positions

        Returns:
            True if there's an overlap
        """
        start, end = span
        for existing_start, existing_end in existing:
            if not (end <= existing_start or start >= existing_end):
                return True
        return False

    def _match_to_concept(
        self,
        entity_text: str,
        entity_type: str,
        concept_lookup: dict[str, dict[str, Any]],
    ) -> tuple[str | None, float]:
        """Match entity text to concept dictionary.

        Args:
            entity_text: The entity text to match
            entity_type: The detected entity type
            concept_lookup: Concept dictionary lookup

        Returns:
            Tuple of (candidate_canonical_name, confidence)
        """
        if entity_text in concept_lookup:
            concept = concept_lookup[entity_text]
            if self._category_matches(entity_type, concept["category"]):
                return concept["canonical_name"], 0.98

        for key, concept in concept_lookup.items():
            if key in entity_text or entity_text in key:
                if self._category_matches(entity_type, concept["category"]):
                    return concept["canonical_name"], 0.85

        return entity_text, 0.70

    def _is_valid_entity(self, entity_text: str) -> bool:
        """Check if entity text meets minimum quality standards.

        Args:
            entity_text: The entity text to validate

        Returns:
            True if entity meets quality standards
        """
        if len(entity_text) <= 1:
            return False

        if len(entity_text) > 12:
            return False

        name_patterns = [
            r'医生.*介绍', r'医生.*讲解', r'医生.*聚焦',
            r'主任.*介绍', r'主任.*讲解',
            r'教授.*介绍', r'教授.*讲解',
            r'专家.*介绍', r'专家.*讲解',
        ]
        for pattern in name_patterns:
            if re.search(pattern, entity_text):
                return False

        if len(re.findall(r'[\u4e00-\u9fff]', entity_text)) > 8:
            return False

        if len(entity_text) == 2:
            allowed_2char_terms = {
                "高血压", "糖尿病", "心脏病", "高血脂", "白血病",
                "中风", "痛风", "哮喘", "肺炎", "肾炎",
                "CT", "MRI", "B超", "X光", "血压", "血糖",
            }
            if entity_text not in allowed_2char_terms:
                return False

        if entity_text.isascii() and entity_text.isalpha() and len(entity_text) <= 2:
            return False

        stop_words = {
            "的", "了", "是", "在", "有", "和", "与", "等", "如", "及",
            "或", "但", "而", "以", "可", "会", "能", "要", "需", "应",
            "对", "将", "把", "被", "从", "到", "向", "于", "之",
            "包括", "例如", "建议", "推荐", "需要", "应该", "可以",
            "治疗", "检查", "诊断", "疾病", "药物", "症状", "患者",
        }
        if entity_text in stop_words:
            return False

        meaningless_fragments = {
            "物", "药", "病", "症", "术", "法", "剂", "素", "体",
            "检", "查", "测", "试", "验", "观", "察", "断", "定",
            "常", "规", "标", "指", "数", "据", "信", "息", "内", "容",
            "前", "后", "左", "右", "上", "下", "中", "外", "内",
            "血", "尿", "便", "痰", "液", "水", "肿", "瘤", "癌", "炎",
            "心", "肝", "肾", "肺", "胃", "肠", "脑", "神经", "血管",
        }
        if entity_text in meaningless_fragments:
            return False

        punctuation_chars = ['。', '，', '：', '、', '；', '！', '？', '、', '【', '】', '（', '）', '《', '》']
        if any(punct in entity_text for punct in punctuation_chars):
            return False

        sentence_patterns = ['的是', '可以', '需要', '应该', '包括', '例如', '建议', '推荐']
        if any(pattern in entity_text for pattern in sentence_patterns):
            return False

        sentence_starters = ['的', '了', '是', '在', '有', '和', '与', '等', '如', '或', '但', '而', '以', '可', '会', '能', '要', '需', '应']
        if entity_text.startswith(tuple(sentence_starters)):
            return False

        sentence_enders = ['等', '等。', '等，', '等等', '、', '，', '。']
        if entity_text.endswith(tuple(sentence_enders)):
            return False

        return True

    def _category_matches(self, entity_type: str, concept_category: str) -> bool:
        """Check if entity type matches concept category.

        Args:
            entity_type: The detected entity type
            concept_category: The concept category from dictionary

        Returns:
            True if categories are compatible
        """
        if entity_type == concept_category:
            return True

        compatible: dict[str, list[str]] = {
            "treatment": ["treatment", "drug"],
            "drug": ["drug", "treatment"],
            "marker": ["marker", "diagnosis"],
            "test": ["diagnosis", "test"],
        }

        return concept_category in compatible.get(entity_type, [])


__all__ = ["EntityExtractorAgent", "EntityExtractorInput", "EntityExtractorOutput"]
