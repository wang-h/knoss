"""Concept Mapper Agent implementation for Knoss.

The Concept Mapper Agent assigns concepts from claims and entities to the
medical taxonomy, creating structured concept relationships and
patient-friendly explanations.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from ..models.payloads import ClaimModel, ConceptModel, ConceptRelationPayload, EntityModel
from ..models.types import ConceptCategory, RelationType
from .base import Agent, AgentResult


class ConceptMapperInput(BaseModel):
    """Input payload for Concept Mapper Agent.

    Attributes:
        article_id: Unique identifier for the article
        claims: Claims to assign concepts to
        entities: Entities extracted from claims
        concept_dictionary_snapshot: Optional snapshot of concept dictionary
    """

    article_id: str = Field(description="Unique identifier for the article")
    claims: list[dict[str, Any] | ClaimModel] = Field(
        default_factory=list,
        description="Claims to assign concepts to",
    )
    entities: list[dict[str, Any] | EntityModel] = Field(
        default_factory=list,
        description="Entities extracted from claims",
    )
    concept_dictionary_snapshot: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Optional concept dictionary for enrichment",
    )


class ConceptMapperOutput(BaseModel):
    """Output payload for Concept Mapper Agent.

    Attributes:
        concepts: List of concepts assigned from claims and entities
    """

    concepts: list[ConceptModel] = Field(default_factory=list)


class ConceptMapperAgent(Agent[ConceptMapperInput, ConceptMapperOutput]):
    """Agent that assigns concepts to the medical taxonomy.

    The Concept Mapper Agent processes claims and entities by:
    1. Identifying unique concepts from entities and claims
    2. Assigning appropriate categories (disease, drug, marker, etc.)
    3. Creating patient-friendly names and explanations
    4. Building relationships between concepts
    5. Matching to or creating concept dictionary entries

    This enables structured knowledge representation and patient-friendly
    content generation.
    """

    input_model = ConceptMapperInput
    output_model = ConceptMapperOutput

    # Category detection patterns
    _DISEASE_PATTERNS = [
        r"[癌瘤]+$",
        r"[病炎症]+$",
    ]

    _DRUG_PATTERNS = [
        r"[单抗抗体]+$",
        r"[药片剂丸]+$",
        r".*?[替芬唑西]",
    ]

    _MARKER_PATTERNS = [
        r"^HER[02]$",
        r"^ER$|^PR$",
        r"^[A-Z]{2,}-?\d*$",
    ]

    _FOLLOW_UP_PATTERNS = [
        r"复查|随访|监测",
        r"术后.*恢复",
    ]

    _ADVERSE_EFFECT_PATTERNS = [
        r"[反应副作用]+",
        r"[不适症状]+",
        r"并发症",
    ]

    def execute(self, input_data: ConceptMapperInput) -> AgentResult:
        """Execute concept assignment from claims and entities.

        Args:
            input_data: Validated input with claims and entities

        Returns:
            AgentResult with list of ConceptModel outputs
        """
        warnings = []
        metadata = {"article_id": input_data.article_id}

        # Parse claims and entities
        claims = self._parse_claims(input_data.claims)
        entities = self._parse_entities(input_data.entities)

        if not claims and not entities:
            return AgentResult.fail("No claims or entities provided for concept mapping")

        # Build concept lookup from snapshot
        concept_lookup = self._build_concept_lookup(
            input_data.concept_dictionary_snapshot,
        )

        # Extract concepts from entities
        concepts = self._extract_concepts_from_entities(
            entities,
            concept_lookup,
        )

        # Extract concepts from claims
        additional_concepts = self._extract_concepts_from_claims(
            claims,
            concepts,
            concept_lookup,
        )

        # Merge concepts
        all_concepts = self._merge_concepts(concepts, additional_concepts)

        # Build relationships between concepts
        all_concepts = self._build_relations(all_concepts, claims)

        metadata["concept_count"] = len(all_concepts)

        if not all_concepts:
            warnings.append("No concepts extracted from claims and entities")

        return AgentResult.ok(
            output=ConceptMapperOutput(concepts=all_concepts),
            warnings=warnings,
            metadata=metadata,
        )

    def _parse_claims(
        self,
        claims: list[dict[str, Any] | ClaimModel],
    ) -> list[ClaimModel]:
        """Parse claims from input.

        Args:
            claims: List of claims from input

        Returns:
            List of validated ClaimModel instances
        """
        parsed = []
        for claim in claims:
            if isinstance(claim, ClaimModel):
                parsed.append(claim)
            else:
                parsed.append(ClaimModel.model_validate(claim))
        return parsed

    def _parse_entities(
        self,
        entities: list[dict[str, Any] | EntityModel],
    ) -> list[EntityModel]:
        """Parse entities from input.

        Args:
            entities: List of entities from input

        Returns:
            List of validated EntityModel instances
        """
        parsed = []
        for entity in entities:
            if isinstance(entity, EntityModel):
                parsed.append(entity)
            else:
                parsed.append(EntityModel.model_validate(entity))
        return parsed

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
            patient_friendly = concept.get("patient_friendly_name")
            explanation = concept.get("patient_friendly_explanation")

            if canonical:
                lookup[canonical] = {
                    "canonical_name": canonical,
                    "category": category,
                    "patient_friendly_name": patient_friendly,
                    "patient_friendly_explanation": explanation,
                    "aliases": set(aliases),
                }

            for alias in aliases:
                if alias not in lookup:
                    lookup[alias] = {
                        "canonical_name": canonical,
                        "category": category,
                        "patient_friendly_name": patient_friendly,
                        "patient_friendly_explanation": explanation,
                        "aliases": set(),
                    }

        return lookup

    def _extract_concepts_from_entities(
        self,
        entities: list[EntityModel],
        concept_lookup: dict[str, dict[str, Any]],
    ) -> list[ConceptModel]:
        """Extract concepts from entities.

        Args:
            entities: List of entities
            concept_lookup: Concept dictionary lookup

        Returns:
            List of concepts from entities
        """
        concepts: dict[str, ConceptModel] = {}

        for entity in entities:
            canonical_name = entity.candidate_canonical_name or entity.entity_text

            if canonical_name in concept_lookup:
                lookup_info = concept_lookup[canonical_name]
                category = self._parse_category(lookup_info["category"])

                if canonical_name not in concepts:
                    concepts[canonical_name] = ConceptModel(
                        canonical_name=canonical_name,
                        category=category,
                        aliases=[entity.entity_text],
                        patient_friendly_name=lookup_info.get("patient_friendly_name"),
                        patient_friendly_explanation=lookup_info.get("patient_friendly_explanation"),
                    )
                else:
                    if entity.entity_text not in concepts[canonical_name].aliases:
                        concepts[canonical_name].aliases.append(entity.entity_text)
            else:
                category = self._detect_category_from_entity(entity)

                if canonical_name not in concepts:
                    concepts[canonical_name] = ConceptModel(
                        canonical_name=canonical_name,
                        category=category,
                        aliases=[entity.entity_text],
                        patient_friendly_name=self._generate_patient_friendly_name(
                            canonical_name,
                            category,
                        ),
                        patient_friendly_explanation=self._generate_explanation(
                            canonical_name,
                            category,
                        ),
                    )

        return list(concepts.values())

    def _extract_concepts_from_claims(
        self,
        claims: list[ClaimModel],
        existing_concepts: list[ConceptModel],
        concept_lookup: dict[str, dict[str, Any]],
    ) -> list[ConceptModel]:
        """Extract additional concepts from claims.

        Args:
            claims: List of claims
            existing_concepts: Concepts already extracted
            concept_lookup: Concept dictionary lookup

        Returns:
            List of additional concepts from claims
        """
        existing_names = {c.canonical_name for c in existing_concepts}
        additional: dict[str, ConceptModel] = {}

        for claim in claims:
            text = claim.claim_text

            if any(re.search(p, text) for p in self._FOLLOW_UP_PATTERNS):
                canonical_name = "术后复查"
                if canonical_name not in existing_names and canonical_name not in additional:
                    additional[canonical_name] = ConceptModel(
                        canonical_name=canonical_name,
                        category=ConceptCategory.FOLLOW_UP,
                        aliases=["复查", "随访", "定期检查"],
                        patient_friendly_name="治疗后的定期检查",
                        patient_friendly_explanation=(
                            "完成主要治疗后，医生会安排定期的复查，"
                            "以便监测恢复情况和及时发现可能的异常。"
                        ),
                    )

            if any(re.search(p, text) for p in self._ADVERSE_EFFECT_PATTERNS):
                match = re.search(r"([恶心呕吐疼痛脱发乏力发热]+)[的不良反应副作用]*", text)
                if match:
                    effect_name = match.group(1)
                    canonical_name = f"{effect_name}反应"
                    if canonical_name not in existing_names and canonical_name not in additional:
                        additional[canonical_name] = ConceptModel(
                            canonical_name=canonical_name,
                            category=ConceptCategory.ADVERSE_EFFECT,
                            aliases=[effect_name],
                            patient_friendly_name=f"治疗可能引起的{effect_name}",
                            patient_friendly_explanation=(
                                f"部分患者可能会出现{effect_name}，"
                                "通常可以采取措施缓解。"
                            ),
                        )

        return list(additional.values())

    def _merge_concepts(
        self,
        concepts1: list[ConceptModel],
        concepts2: list[ConceptModel],
    ) -> list[ConceptModel]:
        """Merge two concept lists.

        Args:
            concepts1: First list of concepts
            concepts2: Second list of concepts

        Returns:
            Merged list of concepts
        """
        merged: dict[str, ConceptModel] = {}

        for concept in concepts1 + concepts2:
            if concept.canonical_name not in merged:
                merged[concept.canonical_name] = concept
            else:
                existing = merged[concept.canonical_name]
                for alias in concept.aliases:
                    if alias not in existing.aliases:
                        existing.aliases.append(alias)

                for rel in concept.relations:
                    if not any(
                        r.target_canonical_name == rel.target_canonical_name
                        and r.relation_type == rel.relation_type
                        for r in existing.relations
                    ):
                        existing.relations.append(rel)

        return list(merged.values())

    def _build_relations(
        self,
        concepts: list[ConceptModel],
        claims: list[ClaimModel],
    ) -> list[ConceptModel]:
        """Build relationships between concepts.

        Args:
            concepts: List of concepts
            claims: Claims for context

        Returns:
            List of concepts with relations
        """
        concept_map = {c.canonical_name: c for c in concepts}

        for concept in concepts:
            if concept.category == ConceptCategory.DRUG:
                for other in concepts:
                    if other.category == ConceptCategory.TREATMENT:
                        if not any(
                            r.target_canonical_name == other.canonical_name
                            and r.relation_type == RelationType.USED_FOR
                            for r in concept.relations
                        ):
                            concept.relations.append(
                                ConceptRelationPayload(
                                    target_canonical_name=other.canonical_name,
                                    relation_type=RelationType.USED_FOR,
                                )
                            )

            if concept.category == ConceptCategory.DISEASE:
                for other in concepts:
                    if other.category == ConceptCategory.ADVERSE_EFFECT:
                        if not any(
                            r.target_canonical_name == other.canonical_name
                            and r.relation_type == RelationType.ADVERSE_OF
                            for r in concept.relations
                        ):
                            concept.relations.append(
                                ConceptRelationPayload(
                                    target_canonical_name=other.canonical_name,
                                    relation_type=RelationType.ADVERSE_OF,
                                )
                            )

            if concept.category == ConceptCategory.MARKER:
                for other in concepts:
                    if other.category in (ConceptCategory.DISEASE, ConceptCategory.DIAGNOSIS):
                        if not any(
                            r.target_canonical_name == other.canonical_name
                            and r.relation_type == RelationType.RELATED_TO
                            for r in concept.relations
                        ):
                            concept.relations.append(
                                ConceptRelationPayload(
                                    target_canonical_name=other.canonical_name,
                                    relation_type=RelationType.RELATED_TO,
                                )
                            )

        return concepts

    def _detect_category_from_entity(self, entity: EntityModel) -> ConceptCategory:
        """Detect concept category from entity.

        Args:
            entity: The entity to classify

        Returns:
            Detected concept category
        """
        entity_type = entity.entity_type

        type_mapping: dict[str, ConceptCategory] = {
            "disease": ConceptCategory.DISEASE,
            "drug": ConceptCategory.DRUG,
            "marker": ConceptCategory.MARKER,
            "treatment": ConceptCategory.TREATMENT,
        }

        if entity_type in type_mapping:
            return type_mapping[entity_type]

        text = entity.entity_text

        if any(re.search(p, text) for p in self._DISEASE_PATTERNS):
            return ConceptCategory.DISEASE
        if any(re.search(p, text) for p in self._DRUG_PATTERNS):
            return ConceptCategory.DRUG
        if any(re.search(p, text) for p in self._MARKER_PATTERNS):
            return ConceptCategory.MARKER
        if any(re.search(p, text) for p in self._FOLLOW_UP_PATTERNS):
            return ConceptCategory.FOLLOW_UP

        return ConceptCategory.DIAGNOSIS

    def _parse_category(self, category: str | ConceptCategory) -> ConceptCategory:
        """Parse category to enum.

        Args:
            category: Category as string or enum

        Returns:
            ConceptCategory enum value
        """
        if isinstance(category, ConceptCategory):
            return category
        try:
            return ConceptCategory(category)
        except ValueError:
            return ConceptCategory.DIAGNOSIS

    def _generate_patient_friendly_name(
        self,
        canonical_name: str,
        category: ConceptCategory,
    ) -> str:
        """Generate patient-friendly name for concept.

        Args:
            canonical_name: The canonical name
            category: The concept category

        Returns:
            Patient-friendly name
        """
        if len(canonical_name) <= 1:
            return f"{canonical_name}（需人工审核）"

        category_descriptions = {
            ConceptCategory.DRUG: "相关药物",
            ConceptCategory.DISEASE: "相关疾病",
            ConceptCategory.MARKER: "相关检查指标",
            ConceptCategory.TREATMENT: "相关治疗方式",
            ConceptCategory.FOLLOW_UP: "相关随访检查",
            ConceptCategory.DIAGNOSIS: "相关诊断方法",
        }

        description = category_descriptions.get(category, "相关概念")

        if len(canonical_name) <= 3:
            return f"{canonical_name}（{description}，需专业医生解读）"

        return f"{canonical_name}（{description}）"

    def _generate_explanation(
        self,
        canonical_name: str,
        category: ConceptCategory,
    ) -> str:
        """Generate patient-friendly explanation.

        Args:
            canonical_name: The canonical name
            category: The concept category

        Returns:
            Patient-friendly explanation
        """
        if len(canonical_name) <= 1:
            return f"该术语为提取片段，具体含义需结合上下文由专业医生判断。"

        generic = {
            ConceptCategory.DRUG: f"{canonical_name}是一种治疗药物，具体使用需遵医嘱。",
            ConceptCategory.DISEASE: f"{canonical_name}需要规范的诊断和治疗，请咨询专业医生。",
            ConceptCategory.MARKER: f"{canonical_name}是检查中的重要指标，结果解读需由医生进行。",
            ConceptCategory.TREATMENT: f"{canonical_name}是治疗选择之一，具体方案需根据患者情况制定。",
            ConceptCategory.FOLLOW_UP: f"{canonical_name}是治疗后管理的重要组成部分，请按医生建议执行。",
            ConceptCategory.DIAGNOSIS: f"{canonical_name}是诊断方法之一，具体选择需根据临床情况决定。",
        }

        return generic.get(category, f"关于{canonical_name}的相关信息，请咨询专业医生。")


__all__ = ["ConceptMapperAgent", "ConceptMapperInput", "ConceptMapperOutput"]
