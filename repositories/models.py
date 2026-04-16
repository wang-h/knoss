"""Repository/ORM models for Knoss.

This module defines the data models for the Knoss knowledge extraction
and governance system.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    """Base class for Knoss ORM models."""
    pass


# -----------------------------------------------------------------------------
# Concept Registry
# -----------------------------------------------------------------------------

class Concept(Base):
    """Canonical concept registry.

    This is the core table for managing canonical medical concepts.
    """

    __tablename__ = "knoss_concepts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    category: Mapped[str] = mapped_column(String, nullable=False, index=True)
    patient_friendly_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    patient_friendly_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft", index=True)
    source_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.7, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    # relationships
    aliases: Mapped[list["ConceptAlias"]] = relationship(
        back_populates="concept", cascade="all, delete-orphan"
    )
    outgoing_relations: Mapped[list["ConceptRelation"]] = relationship(
        foreign_keys="[ConceptRelation.source_concept_id]",
        back_populates="source_concept",
        cascade="all, delete-orphan"
    )
    incoming_relations: Mapped[list["ConceptRelation"]] = relationship(
        foreign_keys="[ConceptRelation.target_concept_id]",
        back_populates="target_concept",
        cascade="all, delete-orphan"
    )
    entity_mappings: Mapped[list["EntityMapping"]] = relationship(
        foreign_keys="[EntityMapping.candidate_concept_id]",
        back_populates="candidate_concept",
        cascade="all, delete-orphan"
    )
    evidence_links: Mapped[list["ConceptEvidence"]] = relationship(
        back_populates="concept", cascade="all, delete-orphan"
    )
    change_logs: Mapped[list["ConceptChangeLog"]] = relationship(
        back_populates="concept", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_concepts_category_status", "category", "status"),
        Index("ix_concepts_confidence", "confidence"),
    )


class ConceptAlias(Base):
    """Alias and synonym management."""

    __tablename__ = "knoss_concept_aliases"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    concept_id: Mapped[str] = mapped_column(
        String, ForeignKey("knoss_concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    alias: Mapped[str] = mapped_column(String, nullable=False, index=True)
    alias_type: Mapped[str] = mapped_column(String, nullable=False, default="exact", index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft", index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())

    # relationships
    concept: Mapped["Concept"] = relationship(back_populates="aliases")

    __table_args__ = (
        UniqueConstraint("concept_id", "alias", name="uq_concept_alias"),
        Index("ix_concept_aliases_alias_type", "alias", "alias_type"),
    )


class ConceptRelation(Base):
    """Concept-to-concept relationships."""

    __tablename__ = "knoss_concept_relations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_concept_id: Mapped[str] = mapped_column(
        String, ForeignKey("knoss_concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_concept_id: Mapped[str] = mapped_column(
        String, ForeignKey("knoss_concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relation_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft", index=True)
    source_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())

    # relationships
    source_concept: Mapped["Concept"] = relationship(
        foreign_keys="[ConceptRelation.source_concept_id]",
        back_populates="outgoing_relations"
    )
    target_concept: Mapped["Concept"] = relationship(
        foreign_keys="[ConceptRelation.target_concept_id]",
        back_populates="incoming_relations"
    )

    __table_args__ = (
        UniqueConstraint("source_concept_id", "target_concept_id", "relation_type", name="uq_concept_relation"),
        Index("ix_concept_relations_type", "relation_type"),
    )


class EntityMapping(Base):
    """Entity-to-concept mapping tracking."""

    __tablename__ = "knoss_entity_mappings"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    entity_text: Mapped[str] = mapped_column(String, nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    article_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    candidate_concept_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("knoss_concepts.id", ondelete="SET NULL"), nullable=True
    )
    final_concept_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("knoss_concepts.id", ondelete="SET NULL"), nullable=True
    )
    mapping_status: Mapped[str] = mapped_column(String, nullable=False, default="needs_review", index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    reviewer_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())

    # relationships
    candidate_concept: Mapped[Optional["Concept"]] = relationship(
        foreign_keys=[candidate_concept_id],
        back_populates="entity_mappings"
    )

    __table_args__ = (
        Index("ix_entity_mappings_status", "mapping_status"),
        Index("ix_entity_mappings_article", "article_id"),
    )


class ConceptEvidence(Base):
    """Concept-evidence linkage."""

    __tablename__ = "knoss_concept_evidence"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    concept_id: Mapped[str] = mapped_column(
        String, ForeignKey("knoss_concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    article_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    segment_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    claim_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    evidence_role: Mapped[str] = mapped_column(String, nullable=False, default="primary")
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.8)
    quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())

    # relationships
    concept: Mapped["Concept"] = relationship(back_populates="evidence_links")

    __table_args__ = (
        Index("ix_concept_evidence_role", "evidence_role"),
        Index("ix_concept_evidence_quality", "quality_score"),
    )


class ConceptChangeLog(Base):
    """Audit log for concept changes."""

    __tablename__ = "knoss_concept_change_log"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    concept_id: Mapped[str] = mapped_column(
        String, ForeignKey("knoss_concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    change_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    before_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    after_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    operator: Mapped[str] = mapped_column(String, nullable=False)
    change_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())

    # relationships
    concept: Mapped["Concept"] = relationship(back_populates="change_logs")

    __table_args__ = (
        Index("ix_concept_change_log_type", "change_type"),
    )


class AliasBlacklist(Base):
    """Blacklisted aliases that should be filtered."""

    __tablename__ = "knoss_alias_blacklist"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    alias: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False, default="noise")
    severity: Mapped[str] = mapped_column(String, nullable=False, default="medium")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())

    __table_args__ = (
        Index("ix_alias_blacklist_category", "category"),
    )


# -----------------------------------------------------------------------------
# Workflow State
# -----------------------------------------------------------------------------

class WorkflowRun(Base):
    """Workflow execution tracking."""

    __tablename__ = "knoss_workflow_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    workflow_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String, nullable=False)
    target_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending", index=True)
    stage: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata: Mapped[Optional[dict]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_workflow_runs_target", "target_type", "target_id"),
        Index("ix_workflow_runs_status", "status"),
    )


__all__ = [
    "Base",
    "Concept",
    "ConceptAlias",
    "ConceptRelation",
    "EntityMapping",
    "ConceptEvidence",
    "ConceptChangeLog",
    "AliasBlacklist",
    "WorkflowRun",
]
