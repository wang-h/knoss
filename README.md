# Knoss - 知识提炼与治理系统 / Knowledge Extraction and Governance System

[English](#english) | [中文](#中文)

---

## 中文

### 概述

Knoss从原始文章中提取结构化知识，通过审核工作流进行治理，并为下游系统提供证据链接和可追溯性。

### Knoss的功能

1. **知识提取**
   - 从文章段落中提取原子化声明
   - 识别医学术语（疾病、药物、标志物等）
   - 将实体映射到规范概念
   - 构建语义分类体系

2. **知识治理**
   - 概念注册表（含别名和关系）
   - 映射审核队列
   - 黑名单管理
   - 冲突检测与解决
   - 变更审计追踪

3. **证据链接**
   - 将概念链接到源文章
   - 为下游构建证据包
   - 提供完整的可追溯性
   - 质量和相关性评分

4. **下游集成**
   - 基于契约的Lenss接口（主题合成）
   - 基于契约的Press接口（内容生成）
   - 受治理的检索（带降级警告）

### 目录结构

```
/knoss/
├── agents/           # 知识提取代理
├── governance/       # 知识治理服务
├── evidence/         # 证据链接和可追溯性
├── workflows/        # 代理和治理的编排
├── models/           # 类型定义和负载
├── repositories/     # 持久化的ORM模型
├── contracts/        # 下游系统接口
├── fixtures/         # 测试数据
└── tests/            # 单元测试
```

### 核心组件

**代理 (Agents)**
- **Cleaner**: 清理原始文章中的噪声
- **Segmenter**: 将文章分割为结构化/语义化段落
- **Claim Extractor**: 提取原子化医学声明
- **Entity Extractor**: 识别医学术语
- **Concept Mapper**: 将实体映射到概念
- **Taxonomy Assigner**: 将概念分配到分类体系

**治理服务 (Governance Services)**
- **Concept Service**: 概念注册表管理
- **Alias Service**: 别名管理
- **Relation Service**: 概念关系
- **Mapping Review Service**: 实体到概念的映射审核
- **Blacklist Service**: 术语黑名单
- **Conflict Service**: 冲突检测与解决
- **Governed Retrieval**: 优先返回已审核的知识资产

**证据服务 (Evidence Services)**
- **Evidence Linker**: 创建概念-证据链接
- **Evidence Pack Builder**: 为下游构建证据包
- **Trace Service**: 提供完整的来源追踪

**工作流 (Workflows)**
- **Refinery Workflow**: 端到端知识提取
- **Governance Workflow**: 知识治理操作

### 安装

```bash
pip install -r requirements.txt
```

### 使用方法

```python
from knoss.workflows import RefineryWorkflow

# 处理文章
workflow = RefineryWorkflow(session)
result = workflow.run({
    "article_id": "article_001",
    "title": "文章标题",
    "raw_text": "文章内容..."
})
```

### 测试

```bash
# 运行冒烟测试
python knoss/tests/smoke_test.py

# 运行质量审计
python knoss/tests/quality_audit.py
```

### 文档

- [模块边界](KNOWN_MODULE_BOUNDARIES.md) - 什么属于Knoss
- [测试报告](../docs/) - 冒烟测试和质量审计结果

### 项目状态

- ✅ **Phase 1**: 边界收敛 - 完成
- ✅ **Phase 2-4**: 核心功能 - 完成
- ✅ **Phase 5**: 下游接口 - 完成
- ✅ **Phase 6**: 真实数据验证 - 完成

**测试结果**:
- Smoke Tests: 7/7 PASS (100%)
- Quality Audit: 79% (477/600)

### 许可证

MIT

---

## English

### Overview

Knoss extracts structured knowledge from raw articles, governs it through review workflows, and provides evidence linkage and traceability for downstream systems.

### What Knoss Does

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

### Directory Structure

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

### Core Components

**Agents**
- **Cleaner**: Removes noise from raw articles
- **Segmenter**: Splits articles into structural/semantic segments
- **Claim Extractor**: Extracts atomic medical claims
- **Entity Extractor**: Identifies medical terminology
- **Concept Mapper**: Maps entities to concepts
- **Taxonomy Assigner**: Assigns concepts to taxonomy

**Governance Services**
- **Concept Service**: Concept registry management
- **Alias Service**: Alias management
- **Relation Service**: Concept relationships
- **Mapping Review Service**: Entity-to-concept mapping review
- **Blacklist Service**: Term blacklisting
- **Conflict Service**: Conflict detection and resolution
- **Governed Retrieval**: Prioritizes reviewed knowledge assets

**Evidence Services**
- **Evidence Linker**: Creates concept-evidence links
- **Evidence Pack Builder**: Builds evidence packs for downstream
- **Trace Service**: Provides complete provenance tracking

**Workflows**
- **Refinery Workflow**: End-to-end knowledge extraction
- **Governance Workflow**: Knowledge governance operations

### Installation

```bash
pip install -r requirements.txt
```

### Usage

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

### Testing

```bash
# Run smoke tests
python knoss/tests/smoke_test.py

# Run quality audit
python knoss/tests/quality_audit.py
```

### Documentation

- [Module Boundaries](KNOWN_MODULE_BOUNDARIES.md) - What belongs to Knoss
- [Test Reports](../docs/) - Smoke test and quality audit results

### Project Status

- ✅ **Phase 1**: Boundary Convergence - Complete
- ✅ **Phase 2-4**: Core Features - Complete
- ✅ **Phase 5**: Downstream Interfaces - Complete
- ✅ **Phase 6**: Real Data Validation - Complete

**Test Results**:
- Smoke Tests: 7/7 PASS (100%)
- Quality Audit: 79% (477/600)

### License

MIT
