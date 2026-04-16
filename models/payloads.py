"""Pydantic payload models for Knoss agents and workflows.

These models represent the structured payloads that agents consume and produce.
They are NOT database models. For ORM persistence models, see repositories/models.py.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from .types import (
    CertaintyLevel,
    ClaimType,
    ConceptCategory,
    EvidenceRole,
    RelationType,
    SegmentLevel,
)


# -----------------------------------------------------------------------------
# Agent Output Payloads
# -----------------------------------------------------------------------------

class RemovedBlock(BaseModel):
    """A block of text that was removed during cleaning."""
    type: str
    text: str
    reason: str


class PreservedStructureBlock(BaseModel):
    """A structural block preserved from the original document."""
    block_index: int
    heading_path: list[str]
    text: str


class CleanerOutput(BaseModel):
    """Output from the Cleaner agent."""
    article_id: str
    clean_text: str
    removed_blocks: list[RemovedBlock] = Field(default_factory=list)
    preserved_structure_blocks: list[PreservedStructureBlock] = Field(default_factory=list)


class SegmentModel(BaseModel):
    """A text segment from document segmentation."""
    id: Optional[str] = Field(default=None, description="Segment ID for traceability")
    segment_index: int = Field(ge=0)
    parent_segment_index: Optional[int] = Field(default=None, ge=0)
    level: SegmentLevel
    heading_path: list[str] = Field(default_factory=list)
    text: str
    segment_type_initial: Optional[str] = None
    segment_type_final: Optional[str] = None
    char_start: Optional[int] = Field(default=None, ge=0)
    char_end: Optional[int] = Field(default=None, ge=0)
    is_noise: bool = False
    quality_score: Optional[float] = Field(default=None, ge=0, le=1)


class ClaimModel(BaseModel):
    """An atomic claim extracted from text."""
    claim_index: int = Field(ge=0)
    claim_text: str
    claim_type: ClaimType
    certainty_level: CertaintyLevel
    scope_note: Optional[str] = None
    normalized_text: Optional[str] = None
    segment_id: Optional[str] = Field(default=None, description="Source segment ID for traceability")


class EntityModel(BaseModel):
    """A named entity extracted from text."""
    entity_index: int = Field(ge=0)
    entity_text: str
    entity_type: str
    candidate_canonical_name: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    segment_id: Optional[str] = Field(default=None, description="Source segment ID for traceability")
    governance_info: Optional[dict[str, Any]] = Field(
        default=None,
        description="Governance mapping info from taxonomy service",
    )


class ConceptRelationPayload(BaseModel):
    """A relationship between concepts."""
    target_canonical_name: str
    relation_type: RelationType


class ConceptModel(BaseModel):
    """A concept in the medical taxonomy."""
    canonical_name: str
    category: ConceptCategory
    aliases: list[str] = Field(default_factory=list)
    patient_friendly_name: Optional[str] = None
    patient_friendly_explanation: Optional[str] = None
    relations: list[ConceptRelationPayload] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Evidence Payloads
# -----------------------------------------------------------------------------

class EvidenceItemModel(BaseModel):
    """A single evidence item linked to a claim."""
    claim_id: str
    segment_id: str
    evidence_role: EvidenceRole
    score: Optional[float] = Field(default=None, ge=0, le=1)


class EvidencePackModel(BaseModel):
    """A collection of evidence items for a topic."""
    topic_bundle_id: str
    patient_profile: str
    evidence_items: list[EvidenceItemModel]
    notes: dict[str, Any] = Field(default_factory=dict)


# -----------------------------------------------------------------------------
# Workflow State
# -----------------------------------------------------------------------------

class WorkflowErrorModel(BaseModel):
    """An error that occurred during workflow execution."""
    stage: str
    message: str
    details: Optional[dict[str, Any]] = None


class WorkflowStateModel(BaseModel):
    """Complete workflow execution state."""
    workflow_run_id: str
    workflow_type: str
    target_type: str
    target_id: str
    status: str
    article: dict[str, Any] = Field(default_factory=dict)
    cleaning: dict[str, Any] = Field(default_factory=dict)
    segments: list[SegmentModel] = Field(default_factory=list)
    claims: list[ClaimModel] = Field(default_factory=list)
    entities: list[EntityModel] = Field(default_factory=list)
    concepts: list[ConceptModel] = Field(default_factory=list)
    ungoverned_entities: list[dict[str, Any]] = Field(default_factory=list)
    topic_bundles: list[dict[str, Any]] = Field(default_factory=list)
    evidence_pack: dict[str, Any] = Field(default_factory=dict)
    errors: list[WorkflowErrorModel] = Field(default_factory=list)


__all__ = [
    "RemovedBlock",
    "PreservedStructureBlock",
    "CleanerOutput",
    "SegmentModel",
    "ClaimModel",
    "EntityModel",
    "ConceptRelationPayload",
    "ConceptModel",
    "EvidenceItemModel",
    "EvidencePackModel",
    "WorkflowErrorModel",
    "WorkflowStateModel",
]
