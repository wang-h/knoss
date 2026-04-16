# Knoss - Knowledge Extraction and Governance System

## Overview

Knoss extracts structured knowledge from raw articles, governs it through review workflows, and provides evidence linkage and traceability for downstream systems.

## What Knoss Does

1. **Knowledge Extraction**
   - Extracts atomic claims from article segments
   - Identifies medical entities (diseases, drugs, markers, etc.)
   - Maps entities to canonical concepts
   - Builds semantic taxonomies

2. **Knowledge Governance**
   - Concept registry with aliases and relations
   - Mapping review queues
   - Blacklist management
   - Conflict detection and resolution
   - Change audit trails

3. **Evidence Linkage**
   - Links concepts to source articles
   - Builds evidence packs for downstream
   - Provides complete traceability
   - Quality and relevance scoring

4. **Downstream Integration**
   - Contract-based interfaces to Lenss (topic synthesis)
   - Contract-based interfaces to Press (content generation)
   - Governed retrieval with fallback warnings

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

## Core Components

### Agents
- **Cleaner**: Removes noise from raw articles
- **Segmenter**: Splits articles into structural/semantic segments
- **Claim Extractor**: Extracts atomic medical claims
- **Entity Extractor**: Identifies medical terminology
- **Concept Mapper**: Maps entities to concepts
- **Taxonomy Assigner**: Assigns concepts to taxonomy

### Governance Services
- **Concept Service**: Concept registry management
- **Alias Service**: Alias management
- **Relation Service**: Concept relationships
- **Mapping Review Service**: Entity-to-concept mapping review
- **Blacklist Service**: Term blacklisting
- **Conflict Service**: Conflict detection and resolution
- **Governed Retrieval**: Prioritizes reviewed knowledge assets

### Evidence Services
- **Evidence Linker**: Creates concept-evidence links
- **Evidence Pack Builder**: Builds evidence packs for downstream
- **Trace Service**: Provides complete provenance tracking

### Workflows
- **Refinery Workflow**: End-to-end knowledge extraction
- **Governance Workflow**: Knowledge governance operations

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```python
from knoss.workflows import RefineryWorkflow

# Process an article
workflow = RefineryWorkflow(session)
result = workflow.run({
    "article_id": "article_001",
    "title": "Article Title",
    "raw_text": "Article content..."
})
```

## Testing

```bash
# Run smoke tests
python knoss/tests/smoke_test.py

# Run quality audit
python knoss/tests/quality_audit.py
```

## Documentation

- [Module Boundaries](KNOWN_MODULE_BOUNDARIES.md) - What belongs to Knoss
- [Test Reports](../docs/) - Smoke test and quality audit results

## License

MIT
