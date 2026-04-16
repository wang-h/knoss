"""Shared type literals used across Knoss models and payloads.

This module defines the enums and type literals that form the foundational
type system for Knoss knowledge extraction and governance.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal


# -----------------------------------------------------------------------------
# Segment Types
# -----------------------------------------------------------------------------

class SegmentLevel(str, Enum):
    """Segment level types."""

    RAW = "raw"
    SEMANTIC = "semantic"


# -----------------------------------------------------------------------------
# Claim Types
# -----------------------------------------------------------------------------

class ClaimType(str, Enum):
    """Claim type categories."""

    FACT = "fact"
    RECOMMENDATION = "recommendation"
    WARNING = "warning"
    CASE = "case"
    OPINION = "opinion"


class CertaintyLevel(str, Enum):
    """Certainty level categories."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# -----------------------------------------------------------------------------
# Entity Types
# -----------------------------------------------------------------------------

class EntityType(str, Enum):
    """Entity type categories."""

    DISEASE = "disease"
    SYMPTOM = "symptom"
    TEST = "test"
    TREATMENT = "treatment"
    DRUG = "drug"
    MARKER = "marker"
    POPULATION = "population"


# -----------------------------------------------------------------------------
# Concept Types (Taxonomy/Governance)
# -----------------------------------------------------------------------------

class ConceptCategory(str, Enum):
    """Concept category types for taxonomy."""

    DISEASE = "disease"
    DIAGNOSIS = "diagnosis"
    TREATMENT = "treatment"
    DRUG = "drug"
    ADVERSE_EFFECT = "adverse_effect"
    FOLLOW_UP = "follow_up"
    MARKER = "marker"


class ConceptStatus(str, Enum):
    """Concept status values in governance workflow."""

    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    PENDING_REVIEW = "pending_review"
    UNDER_REVIEW = "under_review"


# -----------------------------------------------------------------------------
# Relation Types
# -----------------------------------------------------------------------------

class RelationType(str, Enum):
    """Relation type categories between concepts."""

    PARENT_OF = "parent_of"
    SUBTYPE_OF = "subtype_of"
    RELATED_TO = "related_to"
    USED_FOR = "used_for"
    ADVERSE_OF = "adverse_of"
    CONTRAINDICATED_FOR = "contraindicated_for"
    TREATS = "treats"
    PREVENTS = "prevents"
    DIAGNOSES = "diagnoses"
    CAUSES = "causes"


# -----------------------------------------------------------------------------
# Evidence Types
# -----------------------------------------------------------------------------

class EvidenceRole(str, Enum):
    """Evidence role categories."""

    PRIMARY = "primary"
    SUPPORTING = "supporting"
    CAUTION = "caution"
    CONFLICTING = "conflicting"


# -----------------------------------------------------------------------------
# Mapping/Governance Types
# -----------------------------------------------------------------------------

class MappingStatus(str, Enum):
    """Entity mapping status values."""

    AUTO_ACCEPTED = "auto_accepted"
    NEEDS_REVIEW = "needs_review"
    HUMAN_CONFIRMED = "human_confirmed"
    REJECTED = "rejected"
    AUTO_REJECTED = "auto_rejected"


class AliasType(str, Enum):
    """Alias type values."""

    EXACT = "exact"
    SYNONYM = "synonym"
    ABBREV = "abbrev"
    AMBIGUOUS = "ambiguous"


# -----------------------------------------------------------------------------
# Workflow Types
# -----------------------------------------------------------------------------

class WorkflowType(str, Enum):
    """Workflow type identifiers."""

    REFINERY = "refinery"
    GOVERNANCE = "governance"


class WorkflowStatus(str, Enum):
    """Workflow execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


__all__ = [
    "SegmentLevel",
    "ClaimType",
    "CertaintyLevel",
    "EntityType",
    "ConceptCategory",
    "ConceptStatus",
    "RelationType",
    "EvidenceRole",
    "MappingStatus",
    "AliasType",
    "WorkflowType",
    "WorkflowStatus",
]
