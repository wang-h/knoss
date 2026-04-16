# Knoss - 知识提炼与治理系统 / Knowledge Extraction and Governance System

[English](#english) | [中文](#中文)

---

## 中文

### 概述

Knoss从原始文章中提取结构化知识，通过审核工作流进行治理，并为下游系统提供证据链接和可追溯性。

### 🎯 核心功能

1. **知识提取 (Knowledge Extraction)**
   - 从文章段落中提取原子化声明
   - 识别医学术语（疾病、药物、标志物等）
   - 将实体映射到规范概念
   - 构建语义分类体系

2. **知识治理 (Knowledge Governance)**
   - 概念注册表（含别名和关系）
   - 映射审核队列
   - 黑名单管理
   - 冲突检测与解决
   - 变更审计追踪

3. **证据链接 (Evidence Linkage)**
   - 将概念链接到源文章
   - 为下游构建证据包
   - 提供完整的可追溯性
   - 质量和相关性评分

4. **下游集成 (Downstream Integration)**
   - 基于契约的Lenss接口（主题合成）
   - 基于契约的Press接口（内容生成）
   - 受治理的检索（带降级警告）

### 🌐 Web管理系统

Knoss包含完整的React Web管理界面，提供可视化的知识治理能力。

**核心页面 (4个):**
- 📊 **数据分析Dashboard** (424行) - 实时统计数据和图表
- ✅ **概念管理页面** (345行) - 完整CRUD操作，搜索和过滤
- 🔍 **映射审核工作台** (397行) - 批准/拒绝工作流，自动接受
- ⚠️ **质量队列处理** (440行) - 批量操作，实时过滤

**技术栈:**
- React 18 + TypeScript + Vite
- shadcn/ui + Tailwind CSS
- Recharts (图表可视化)
- Zustand (状态管理)
- React Router v6

**启动Web UI:**
```bash
cd frontend
npm install
npm run dev
# 访问: http://localhost:5173
```

**功能特性:**
- ✅ 实时数据更新和统计图表
- ✅ 批量操作和批量审核
- ✅ 高级搜索和多维度过滤
- ✅ 响应式设计（支持移动端）
- ✅ Toast通知和错误处理
- ✅ 完整的TypeScript类型安全

### 📁 目录结构

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

/frontend/           # Web管理系统 (React)
├── src/
│   ├── pages/
│   │   ├── Dashboard.tsx           # 数据分析Dashboard
│   │   ├── concepts/
│   │   │   └── ConceptManagement.tsx  # 概念管理
│   │   ├── MappingReview.tsx       # 映射审核工作台
│   │   └── quality/
│   │       └── QualityQueue.tsx    # 质量队列处理
│   ├── api/
│   │   ├── concepts.ts             # 概念管理API
│   │   ├── mappings.ts             # 映射审核API
│   │   ├── quality.ts              # 质量队列API
│   │   └── statistics.ts           # 统计数据API
│   └── components/ui/              # shadcn/ui组件
└── package.json
```

### 🔧 核心组件

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

### 📦 安装

```bash
# 安装后端依赖
pip install -r requirements.txt

# 安装前端依赖
cd frontend
npm install
```

### 🚀 使用方法

**后端使用:**
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

**前端启动:**
```bash
# 启动Web管理界面
cd frontend
npm run dev
# 访问: http://localhost:5173
```

### 🧪 测试

```bash
# 运行冒烟测试
python knoss/tests/smoke_test.py

# 运行质量审计
python knoss/tests/quality_audit.py

# 运行前端测试
cd frontend
npm test
```

### 📚 文档

- [模块边界](KNOWN_MODULE_BOUNDARIES.md) - 什么属于Knoss
- [Web UI状态](WEB_UI_STATUS.md) - 前端实现状态
- [测试报告](../docs/) - 冒烟测试和质量审计结果

### 📊 项目状态

**后端:**
- ✅ **Phase 1**: 边界收敛 - 完成
- ✅ **Phase 2-4**: 核心功能 - 完成
- ✅ **Phase 5**: 下游接口 - 完成
- ✅ **Phase 6**: 真实数据验证 - 完成

**前端:**
- ✅ Dashboard (数据分析) - 424行
- ✅ 概念管理 (CRUD) - 345行
- ✅ 映射审核 (工作台) - 397行
- ✅ 质量队列 (批量处理) - 440行

**测试结果:**
- Smoke Tests: 7/7 PASS (100%)
- Quality Audit: 79% (477/600)

### 📈 代码统计

- **后端**: 34个文件，8,109行代码
- **前端**: 1,606行UI代码 + 12个shadcn/ui组件
- **总计**: ~10,000行生产代码

### 📄 许可证

MIT

---

## English

### Overview

Knoss extracts structured knowledge from raw articles, governs it through review workflows, and provides evidence linkage and traceability for downstream systems.

### 🎯 What Knoss Does

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

### 🌐 Web Management System

Knoss includes a complete React Web management interface for visual knowledge governance.

**Core Pages (4):**
- 📊 **Analytics Dashboard** (424 lines) - Real-time statistics and charts
- ✅ **Concept Management** (345 lines) - Full CRUD operations, search and filters
- 🔍 **Mapping Review Workbench** (397 lines) - Approve/reject workflow, auto-accept
- ⚠️ **Quality Queue Processing** (440 lines) - Batch operations, real-time filters

**Tech Stack:**
- React 18 + TypeScript + Vite
- shadcn/ui + Tailwind CSS
- Recharts (chart visualization)
- Zustand (state management)
- React Router v6

**Start Web UI:**
```bash
cd frontend
npm install
npm run dev
# Visit: http://localhost:5173
```

**Features:**
- ✅ Real-time data updates and statistical charts
- ✅ Batch operations and bulk reviews
- ✅ Advanced search and multi-dimensional filtering
- ✅ Responsive design (mobile support)
- ✅ Toast notifications and error handling
- ✅ Complete TypeScript type safety

### 📁 Directory Structure

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

/frontend/           # Web Management System (React)
├── src/
│   ├── pages/
│   │   ├── Dashboard.tsx           # Analytics Dashboard
│   │   ├── concepts/
│   │   │   └── ConceptManagement.tsx  # Concept Management
│   │   ├── MappingReview.tsx       # Mapping Review Workbench
│   │   └── quality/
│   │       └── QualityQueue.tsx    # Quality Queue Processing
│   ├── api/
│   │   ├── concepts.ts             # Concept management API
│   │   ├── mappings.ts             # Mapping review API
│   │   ├── quality.ts              # Quality queue API
│   │   └── statistics.ts           # Statistics data API
│   └── components/ui/              # shadcn/ui components
└── package.json
```

### 🔧 Core Components

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

### 📦 Installation

```bash
# Install backend dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
```

### 🚀 Usage

**Backend Usage:**
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

**Frontend Start:**
```bash
# Start Web Management Interface
cd frontend
npm run dev
# Visit: http://localhost:5173
```

### 🧪 Testing

```bash
# Run smoke tests
python knoss/tests/smoke_test.py

# Run quality audit
python knoss/tests/quality_audit.py

# Run frontend tests
cd frontend
npm test
```

### 📚 Documentation

- [Module Boundaries](KNOWN_MODULE_BOUNDARIES.md) - What belongs to Knoss
- [Web UI Status](WEB_UI_STATUS.md) - Frontend implementation status
- [Test Reports](../docs/) - Smoke test and quality audit results

### 📊 Project Status

**Backend:**
- ✅ **Phase 1**: Boundary Convergence - Complete
- ✅ **Phase 2-4**: Core Features - Complete
- ✅ **Phase 5**: Downstream Interfaces - Complete
- ✅ **Phase 6**: Real Data Validation - Complete

**Frontend:**
- ✅ Dashboard (Analytics) - 424 lines
- ✅ Concept Management (CRUD) - 345 lines
- ✅ Mapping Review (Workbench) - 397 lines
- ✅ Quality Queue (Batch Processing) - 440 lines

**Test Results:**
- Smoke Tests: 7/7 PASS (100%)
- Quality Audit: 79% (477/600)

### 📈 Code Statistics

- **Backend**: 34 files, 8,109 lines of code
- **Frontend**: 1,606 lines of UI code + 12 shadcn/ui components
- **Total**: ~10,000 lines of production code

### 📄 License

MIT
