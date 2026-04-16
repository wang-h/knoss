# Knoss Module Boundaries

This document defines the boundaries between Knoss and other modules in the medpop-article-generation-skill codebase.

## Overview

Knoss (Knowledge extraction and governance system) is responsible for:
1. Extracting structured knowledge from raw articles
2. Governing that knowledge through review and approval workflows
3. Providing evidence linkage and traceability
4. Supplying governed knowledge to downstream systems

## Directory Structure

```
/knoss/
├── agents/           # Knowledge extraction agents
├── governance/       # Knowledge governance services
├── evidence/         # Evidence linkage and traceability
├── workflows/        # Orchestration of agents and governance
├── models/           # Type definitions and payloads
├── repositories/     # ORM models for persistence
├── contracts/        # Interfaces to downstream systems
├── fixtures/         # Test fixtures
└── tests/            # Unit tests
```

## Module Ownership

### Agents (Knoss Core)

| Module | Belongs to Knoss | Original Location |
|--------|------------------|-------------------|
| `cleaner.py` | Yes | `medpop_article_generation/agents/cleaner.py` |
| `segmenter.py` | Yes | `medpop_article_generation/agents/segmenter.py` |
| `claim_extractor.py` | Yes | `medpop_article_generation/agents/claim.py` |
| `entity_extractor.py` | Yes | `medpop_article_generation/agents/terminology.py` |
| `concept_mapper.py` | Yes | `medpop_article_generation/agents/taxonomy.py` |
| `taxonomy_assigner.py` | Yes | New in Knoss |

### Governance (Knoss Core)

| Module | Belongs to Knoss | Original Location |
|--------|------------------|-------------------|
| `concept_service.py` | Yes | `medpop_article_generation/taxonomy/services.py` (partial) |
| `alias_service.py` | Yes | `medpop_article_generation/taxonomy/services.py` (partial) |
| `relation_service.py` | Yes | New in Knoss |
| `mapping_review_service.py` | Yes | `medpop_article_generation/taxonomy/mapping_service.py` (partial) |
| `blacklist_service.py` | Yes | `medpop_article_generation/taxonomy/blacklist_service.py` |
| `conflict_service.py` | Yes | New in Knoss |
| `governed_retrieval_service.py` | Yes | New in Knoss |

### Evidence (Knoss Core)

| Module | Belongs to Knoss | Original Location |
|--------|------------------|-------------------|
| `evidence_linker.py` | Yes | `medpop_article_generation/taxonomy/evidence_service.py` |
| `evidence_pack_builder.py` | Yes | New in Knoss |
| `trace_service.py` | Yes | New in Knoss |

### Workflows (Knoss Core)

| Module | Belongs to Knoss | Original Location |
|--------|------------------|-------------------|
| `refinery_workflow.py` | Yes | `medpop_article_generation/workflows/refinery.py` (partial) |
| `governance_workflow.py` | Yes | New in Knoss |

### Contracts (Knoss Downstream Interface)

| Module | Belongs to Knoss | Purpose |
|--------|------------------|---------|
| `knoss_lenss_contract.py` | Yes | Interface to Lenss system |
| `knoss_press_contract.py` | Yes | Interface to Press system |

## What Does NOT Belong to Knoss

### Writer Module
- **Location**: `/writer/`
- **Purpose**: Content generation, plain language adaptation, audience targeting
- **Reason**: Writer is a downstream consumer of Knoss knowledge assets

### Medpop-specific Workflows
- **Location**: `medpop_article_generation/workflows/topic_build.py`
- **Purpose**: Topic synthesis for medpop-specific use cases
- **Reason**: These are application-specific workflows that use Knoss

### Adapters
- **Location**: `/adapters/`
- **Purpose**: External system integration (e.g., WERSS)
- **Reason**: Adapters are integration points, not core knowledge extraction

### Frontend
- **Location**: `/frontend/`
- **Purpose**: User interface for review and management
- **Reason**: Frontend is a UI layer, not part of the knowledge system

### Services (Application Layer)
- **Location**: `medpop_article_generation/services/`
- **Purpose**: Editorial review, human review workflows
- **Reason**: These are application-level services, not core knowledge extraction

## Data Flow

```
Raw Article
    ↓
[Knoss: Refinery Workflow]
    ├─ Cleaner Agent
    ├─ Segmenter Agent
    ├─ Claim Extractor Agent
    ├─ Entity Extractor Agent
    └─ Concept Mapper Agent
    ↓
Structured Knowledge (Segments, Claims, Entities, Concepts)
    ↓
[Knoss: Governance Workflow]
    ├─ Conflict Detection
    ├─ Mapping Review
    └─ Concept Approval
    ↓
[Knoss: Evidence Services]
    ├─ Evidence Linkage
    ├─ Evidence Pack Building
    └─ Trace Service
    ↓
[Knoss: Governed Retrieval]
    ↓
Downstream Systems:
    ├─ Lenss (Topic synthesis)
    └─ Press (Patient-friendly content)
```

## API Boundaries

### Knoss Exports

Knoss provides the following to downstream systems:

1. **Reviewed Concepts**: Canonical concepts with patient-friendly explanations
2. **Evidence Packs**: Curated evidence collections for specific topics
3. **Governed Retrieval**: APIs that prioritize reviewed over ungoverned content
4. **Fallback Warnings**: Clear communication when ungoverned content must be used

### Knoss Imports

Knoss depends on:

1. **SQLAlchemy**: For ORM and persistence
2. **Pydantic**: For data validation and serialization
3. **External APIs**: For fetching raw articles (via adapters)

## Migration Status

| Module | Status | Notes |
|--------|--------|-------|
| Agents | ✅ Migrated | All core agents in `/knoss/agents/` |
| Governance | ✅ Migrated | All governance services in `/knoss/governance/` |
| Evidence | ✅ Migrated | All evidence services in `/knoss/evidence/` |
| Workflows | ✅ Migrated | Refinery and governance workflows in `/knoss/workflows/` |
| Contracts | ✅ Created | Lenss and Press contracts in `/knoss/contracts/` |
| Models | ✅ Created | Types and payloads in `/knoss/models/` |
| Repositories | ✅ Created | ORM models in `/knoss/repositories/` |

## Ownership Map

```
medpop-article-generation-skill/
├── knoss/                    ✅ Knoss Core (NEW)
├── writer/                   ❌ NOT Knoss (Downstream Consumer)
├── adapters/                 ❌ NOT Knoss (External Integration)
├── frontend/                 ❌ NOT Knoss (UI Layer)
├── medpop_article_generation/
│   ├── workflows/            ⚠️  Partial (Topic build is app-specific)
│   ├── services/             ❌ NOT Knoss (Application Layer)
│   ├── api/                  ❌ NOT Knoss (API Layer)
│   └── agents/               ⚠️  MIGRATED to /knoss/agents/
└── contracts/                ⚠️  Schema definitions (moved to /knoss/contracts/)
```
