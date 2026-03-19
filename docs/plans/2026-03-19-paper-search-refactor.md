# Paper Search 服务化重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 paper-search-mcp 重构为独立的 `PaperSearchService` 服务层 + 薄 MCP 适配层，保留全部 25+ 平台连接器。

**Architecture:** 三层架构 — Connectors（平台连接器，@register 自动注册）→ Service（业务编排：搜索/下载/导出）→ Transports（MCP adapter，薄包装）。连接器内部逻辑保持不变，仅改 imports 和基类；核心改进在 Service 层和注册表模式。

**Tech Stack:** Python 3.10+, Pydantic v2 (models), requests (connectors), httpx (service 层新代码), FastMCP (transport)

---

## 源项目位置

- 原项目: `/Users/deme/Downloads/temp_wenxian_jishu/paper-search-mcp/`
- 新项目: `/Users/deme/Downloads/temp_wenxian_jishu/paper-search/`

## 文件结构总览

```
paper-search/
├── pyproject.toml                          # ✅ 已创建
├── paper_search/
│   ├── __init__.py                         # ✅ 已创建
│   ├── config.py                           # ✅ 已创建
│   ├── utils.py                            # ✅ 已创建
│   ├── models/
│   │   ├── __init__.py                     # ✅ 已创建
│   │   └── paper.py                        # ✅ 已创建
│   ├── connectors/
│   │   ├── __init__.py                     # ✅ 已创建
│   │   ├── base.py                         # ✅ 已创建
│   │   ├── registry.py                     # ✅ 已创建
│   │   ├── arxiv.py                        # 📋 Task 2
│   │   ├── pubmed.py                       # 📋 Task 2
│   │   ├── biorxiv.py                      # 📋 Task 2
│   │   ├── medrxiv.py                      # 📋 Task 2
│   │   ├── iacr.py                         # 📋 Task 2
│   │   ├── crossref.py                     # 📋 Task 2
│   │   ├── europepmc.py                    # 📋 Task 2
│   │   ├── pmc.py                          # 📋 Task 2
│   │   ├── dblp.py                         # 📋 Task 2
│   │   ├── openalex.py                     # 📋 Task 2
│   │   ├── hal.py                          # 📋 Task 2
│   │   ├── ssrn.py                         # 📋 Task 2
│   │   ├── semantic.py                     # 📋 Task 3 (特殊：有 citations/references)
│   │   ├── core.py                         # 📋 Task 3
│   │   ├── openaire.py                     # 📋 Task 3
│   │   ├── doaj.py                         # 📋 Task 3
│   │   ├── citeseerx.py                    # 📋 Task 3
│   │   ├── zenodo.py                       # 📋 Task 3
│   │   ├── google_scholar.py               # 📋 Task 3
│   │   ├── oaipmh.py                       # 📋 Task 4 (继承链基类)
│   │   ├── base_search.py                  # 📋 Task 4 (继承 oaipmh)
│   │   ├── chemrxiv.py                     # 📋 Task 4 (继承 crossref)
│   │   ├── unpaywall.py                    # 📋 Task 4 (双类: Resolver + Searcher)
│   │   ├── sci_hub.py                      # 📋 Task 4 (工具类，非 PaperConnector)
│   │   ├── acm.py                          # 📋 Task 4 (requires_key)
│   │   └── ieee.py                         # 📋 Task 4 (requires_key)
│   ├── service/
│   │   ├── __init__.py                     # ✅ 已创建
│   │   ├── search_service.py               # 📋 Task 5
│   │   ├── download_service.py             # 📋 Task 6
│   │   └── export_service.py               # 📋 Task 7
│   └── transports/
│       ├── __init__.py                     # 📋 Task 8
│       └── mcp_server.py                   # 📋 Task 8
└── tests/
    ├── __init__.py                         # 📋 Task 1
    ├── test_models.py                      # 📋 Task 1
    ├── test_registry.py                    # 📋 Task 5
    ├── test_search_service.py              # 📋 Task 5
    ├── test_download_service.py            # 📋 Task 6
    ├── test_export_service.py              # 📋 Task 7
    └── test_mcp_server.py                  # 📋 Task 8
```

## 连接器清单与迁移策略

### 标准连接器（无 API key，直接迁移）

> **Capabilities 原则:** 只要原 server.py 注册了对应的 MCP tool，就设为 True（即使实现是 stub/返回错误信息），以保持 MCP API 向后兼容。

| 原文件 | 原类名 | 新注册名 | capabilities |
|--------|--------|---------|-------------|
| arxiv.py | ArxivSearcher | `arxiv` | search + download + read |
| pubmed.py | PubMedSearcher | `pubmed` | search + download + read (stub: 返回提示信息) |
| biorxiv.py | BioRxivSearcher | `biorxiv` | search + download + read |
| medrxiv.py | MedRxivSearcher | `medrxiv` | search + download + read |
| iacr.py | IACRSearcher | `iacr` | search + download + read |
| crossref.py | CrossRefSearcher | `crossref` | search + download + read (stub) + 特殊方法 `get_paper_by_doi` |
| europepmc.py | EuropePMCSearcher | `europepmc` | search + download + read |
| pmc.py | PMCSearcher | `pmc` | search + download + read |
| dblp.py | DBLPSearcher | `dblp` | search + download + read (stub: 返回提示信息) |
| openalex.py | OpenAlexSearcher | `openalex` | search + download + read (stub: 返回提示信息) |
| hal.py | HALSearcher | `hal` | search + download + read |
| ssrn.py | SSRNSearcher | `ssrn` | search + download + read (best-effort) |

### 可选 API key 连接器

| 原文件 | 原类名 | 新注册名 | API key 环境变量 |
|--------|--------|---------|-----------------|
| semantic.py | SemanticSearcher | `semantic` | SEMANTIC_SCHOLAR_API_KEY (可选) |
| core.py | CORESearcher | `core` | CORE_API_KEY (可选) |
| openaire.py | OpenAiresearcher | `openaire` | OPENAIRE_API_KEY (可选) |
| doaj.py | DOAJSearcher | `doaj` | DOAJ_API_KEY (可选) |
| citeseerx.py | CiteSeerXSearcher | `citeseerx` | CITESEERX_API_KEY (可选) |
| zenodo.py | ZenodoSearcher | `zenodo` | ZENODO_ACCESS_TOKEN (可选) |
| google_scholar.py | GoogleScholarSearcher | `google_scholar` | GOOGLE_SCHOLAR_PROXY_URL (可选代理) |

### 必需 API key 连接器（requires_key）

| 原文件 | 原类名 | 新注册名 | API key 环境变量 |
|--------|--------|---------|-----------------|
| ieee.py | IEEESearcher | `ieee` | IEEE_API_KEY (必需) |
| acm.py | ACMSearcher | `acm` | ACM_API_KEY (必需) |

### 特殊连接器

| 原文件 | 原类名 | 说明 |
|--------|--------|------|
| oaipmh.py | OAIPMHSearcher | 中间基类，被 base_search.py 继承 |
| base_search.py | BASESearcher | 继承 OAIPMHSearcher，注册为 `base` |
| chemrxiv.py | ChemRxivSearcher | 继承 CrossRefSearcher，注册为 `chemrxiv` |
| unpaywall.py | UnpaywallResolver | 工具类（非 PaperConnector），提供 `resolve_best_pdf_url()` |
| unpaywall.py | UnpaywallSearcher | PaperConnector，注册为 `unpaywall`，依赖 UnpaywallResolver |
| sci_hub.py | SciHubFetcher | 工具类（非 PaperConnector），仅用于 download fallback |

---

## 连接器迁移标准模式

所有标准连接器的迁移步骤完全相同，以 arxiv 为例：

**原始代码**（关键部分）:
```python
from ..paper import Paper
from .base import PaperSource

class ArxivSearcher(PaperSource):
    def search(self, query: str, max_results: int = 10) -> List[Paper]:
        ...
```

**迁移后**:
```python
from ..models.paper import Paper
from .base import PaperConnector, ConnectorCapabilities
from .registry import register

@register("arxiv")
class ArxivConnector(PaperConnector):
    capabilities = ConnectorCapabilities(search=True, download=True, read=True)

    def search(self, query: str, max_results: int = 10, **kwargs) -> List[Paper]:
        # 内部逻辑完全不变
        ...
```

**变更清单:**
1. `from ..paper import Paper` → `from ..models.paper import Paper`
2. `from .base import PaperSource` → `from .base import PaperConnector, ConnectorCapabilities` + `from .registry import register`
3. 类名后缀 `Searcher` → `Connector`（可选，但更语义化）
4. 继承 `PaperSource` → `PaperConnector`
5. 添加 `@register("name")` 装饰器
6. 添加 `capabilities = ConnectorCapabilities(...)` 类属性
7. `search` 方法签名加 `**kwargs`（兼容 registry 统一调用）
8. 删除文件末尾的 `if __name__ == "__main__":` 测试代码
9. 内部业务逻辑（HTTP 调用、解析、PDF 处理）**完全不动**

---

## 任务分解

### Task 1: 验证骨架 + 模型测试

**目标:** 确保已创建的骨架文件正确，写 Paper 模型的单元测试。

**Files:**
- 审查: `paper_search/models/paper.py`
- 审查: `paper_search/connectors/base.py`
- 审查: `paper_search/connectors/registry.py`
- 审查: `paper_search/config.py`
- 创建: `tests/__init__.py`
- 创建: `tests/test_models.py`

- [ ] **Step 1: 审查并修正骨架文件**

审查已创建的所有骨架文件，确保：
- `Paper` 模型字段与原 `paper.py` 完全兼容（字段名、类型、默认值）
- `ConnectorCapabilities` 涵盖所有需要的属性
- `ConnectorRegistry` 的 auto-import 逻辑正确
- `config.py` 的 `get_env()` 行为与原项目一致

如发现问题，修正后再继续。

- [ ] **Step 2: 写 Paper 模型测试**

```python
# tests/test_models.py
from datetime import datetime
from paper_search.models.paper import Paper, SearchResult, SnowballResult

def test_paper_creation_minimal():
    p = Paper(paper_id="123", title="Test")
    assert p.paper_id == "123"
    assert p.authors == []
    assert p.doi == ""

def test_paper_creation_full():
    p = Paper(
        paper_id="2106.12345",
        title="Test Paper",
        authors=["Alice", "Bob"],
        abstract="An abstract",
        doi="10.1234/test",
        published_date=datetime(2021, 6, 1),
        pdf_url="https://example.com/paper.pdf",
        url="https://example.com/paper",
        source="arxiv",
    )
    assert p.source == "arxiv"
    assert len(p.authors) == 2

def test_paper_to_api_dict():
    p = Paper(
        paper_id="123",
        title="Test",
        authors=["Alice", "Bob"],
        published_date=datetime(2021, 1, 1),
    )
    d = p.to_api_dict()
    assert d["authors"] == "Alice; Bob"
    assert d["published_date"] == "2021-01-01T00:00:00"
    assert d["doi"] == ""

def test_search_result():
    sr = SearchResult(query="test", sources_requested="all")
    assert sr.total == 0
    assert sr.papers == []

def test_snowball_result():
    sb = SnowballResult(seed_paper_id="abc", direction="both", depth=1)
    assert sb.errors == []
```

- [ ] **Step 3: 运行测试确认通过**

```bash
cd /Users/deme/Downloads/temp_wenxian_jishu/paper-search
uv run pytest tests/test_models.py -v
```
Expected: 5 PASSED

- [ ] **Step 4: 提交**

```bash
git init
git add -A
git commit -m "feat: project skeleton with pydantic models, connector framework, and config"
```

---

### Task 2: 迁移标准连接器（12 个，无 API key）

**目标:** 迁移所有不需要 API key 的标准连接器。

**Files:**
- 创建: `paper_search/connectors/arxiv.py`
- 创建: `paper_search/connectors/pubmed.py`
- 创建: `paper_search/connectors/biorxiv.py`
- 创建: `paper_search/connectors/medrxiv.py`
- 创建: `paper_search/connectors/iacr.py`
- 创建: `paper_search/connectors/crossref.py`
- 创建: `paper_search/connectors/europepmc.py`
- 创建: `paper_search/connectors/pmc.py`
- 创建: `paper_search/connectors/dblp.py`
- 创建: `paper_search/connectors/openalex.py`
- 创建: `paper_search/connectors/hal.py`
- 创建: `paper_search/connectors/ssrn.py`
- 源文件: `paper-search-mcp/paper_search_mcp/academic_platforms/` 下同名文件

**对每个连接器执行相同的迁移模式（参见上方"连接器迁移标准模式"）:**

- [ ] **Step 1: 迁移 arxiv.py**

从原文件 `paper-search-mcp/.../arxiv.py` 复制，按标准模式修改：
- `@register("arxiv")`
- `class ArxivConnector(PaperConnector)`
- `capabilities = ConnectorCapabilities(search=True, download=True, read=True)`
- 修改 imports，保留内部逻辑

注意: ArxivSearcher 的 `search` 方法签名为 `search(self, query: str, max_results: int = 10)`，需要加 `**kwargs`。

- [ ] **Step 2: 迁移 pubmed.py**

同上模式。注意 PubMedSearcher 的 download_pdf 和 read_paper 返回提示信息（stub），但为保持 MCP 兼容性仍设为 True。
- `capabilities = ConnectorCapabilities(search=True, download=True, read=True)`

- [ ] **Step 3: 迁移 biorxiv.py**

- `capabilities = ConnectorCapabilities(search=True, download=True, read=True)`

- [ ] **Step 4: 迁移 medrxiv.py**

- `capabilities = ConnectorCapabilities(search=True, download=True, read=True)`

- [ ] **Step 5: 迁移 iacr.py**

注意: IACRSearcher 有额外的 `get_paper_details()` 方法，保留。search 方法有额外的 `fetch_details` 参数，通过 `**kwargs` 传递。

- [ ] **Step 6: 迁移 crossref.py**

注意: CrossRefSearcher 有额外的 `get_paper_by_doi()` 方法，保留。search 方法有额外参数 `filter`, `sort`, `order`，通过 `**kwargs` 传递。
- `capabilities = ConnectorCapabilities(search=True, download=True, read=True)`

- [ ] **Step 7: 迁移 europepmc.py**

- `capabilities = ConnectorCapabilities(search=True, download=True, read=True)`

- [ ] **Step 8: 迁移 pmc.py**

- `capabilities = ConnectorCapabilities(search=True, download=True, read=True)`

- [ ] **Step 9: 迁移 dblp.py**

- `capabilities = ConnectorCapabilities(search=True, download=True, read=True)` (stub: 返回提示信息，保持 MCP 兼容)

- [ ] **Step 10: 迁移 openalex.py**

- `capabilities = ConnectorCapabilities(search=True, download=True, read=True)` (stub: 返回提示信息，保持 MCP 兼容)

- [ ] **Step 11: 迁移 hal.py**

- `capabilities = ConnectorCapabilities(search=True, download=True, read=True)`

- [ ] **Step 12: 迁移 ssrn.py**

- `capabilities = ConnectorCapabilities(search=True, download=True, read=True)` (best-effort，保持 MCP 兼容)

- [ ] **Step 13: 验证所有连接器可导入**

```python
# 在 Python REPL 中运行
import paper_search.connectors.arxiv
import paper_search.connectors.pubmed
import paper_search.connectors.biorxiv
import paper_search.connectors.medrxiv
import paper_search.connectors.iacr
import paper_search.connectors.crossref
import paper_search.connectors.europepmc
import paper_search.connectors.pmc
import paper_search.connectors.dblp
import paper_search.connectors.openalex
import paper_search.connectors.hal
import paper_search.connectors.ssrn
print("All standard connectors imported OK")
```

- [ ] **Step 14: 提交**

```bash
git add paper_search/connectors/
git commit -m "feat: migrate 12 standard connectors (no API key required)"
```

---

### Task 3: 迁移可选 API key 连接器（7 个）

**目标:** 迁移需要可选 API key 的连接器。

**Files:**
- 创建: `paper_search/connectors/semantic.py`
- 创建: `paper_search/connectors/core.py`
- 创建: `paper_search/connectors/openaire.py`
- 创建: `paper_search/connectors/doaj.py`
- 创建: `paper_search/connectors/citeseerx.py`
- 创建: `paper_search/connectors/zenodo.py`
- 创建: `paper_search/connectors/google_scholar.py`

- [ ] **Step 1: 迁移 semantic.py（最复杂的连接器）**

这是最特殊的连接器，必须保留额外方法：
- `get_paper_details(paper_id) -> Optional[Paper]`
- `get_references(paper_id, max_results) -> List[Paper]` — snowball 搜索需要
- `get_citations(paper_id, max_results) -> List[Paper]` — snowball 搜索需要
- `request_api(path, params) -> dict` — 内部 API 调用封装
- `get_api_key() -> Optional[str]` — 静态方法

```python
@register("semantic")
class SemanticConnector(PaperConnector):
    capabilities = ConnectorCapabilities(search=True, download=True, read=True)
    # 保留所有原有方法，仅改 imports 和基类
```

注意: `from ..config import get_env` 路径不变（config.py 位置相同）。

- [ ] **Step 2: 迁移 core.py**

- `capabilities = ConnectorCapabilities(search=True, download=True, read=True)`
- 内部使用 `get_env("CORE_API_KEY")` — 可选

- [ ] **Step 3: 迁移 openaire.py**

注意: 原类名是 `OpenAiresearcher`（小写 s），统一为 `OpenAIREConnector`。
- `capabilities = ConnectorCapabilities(search=True, download=True, read=True)`
- 原 server.py 注册了 `download_openaire` 和 `read_openaire_paper` 工具

- [ ] **Step 4: 迁移 doaj.py**

- `capabilities = ConnectorCapabilities(search=True, download=True, read=True)`

- [ ] **Step 5: 迁移 citeseerx.py**

- `capabilities = ConnectorCapabilities(search=True, download=True, read=True)`

- [ ] **Step 6: 迁移 zenodo.py**

- `capabilities = ConnectorCapabilities(search=True, download=True, read=True)`

- [ ] **Step 7: 迁移 google_scholar.py**

- `capabilities = ConnectorCapabilities(search=True, download=False, read=False)`
- 内部使用 `get_env("GOOGLE_SCHOLAR_PROXY_URL")` 配置代理

- [ ] **Step 8: 验证导入**

```bash
cd /Users/deme/Downloads/temp_wenxian_jishu/paper-search
uv run python -c "
from paper_search.connectors.registry import _REGISTRY
import paper_search.connectors.semantic
import paper_search.connectors.core
import paper_search.connectors.openaire
import paper_search.connectors.doaj
import paper_search.connectors.citeseerx
import paper_search.connectors.zenodo
import paper_search.connectors.google_scholar
print(f'Registry has {len(_REGISTRY)} connectors: {sorted(_REGISTRY.keys())}')
"
```
Expected: 19 connectors (12 标准 + 7 可选)

- [ ] **Step 9: 提交**

```bash
git add paper_search/connectors/
git commit -m "feat: migrate 7 optional-key connectors (semantic, core, openaire, doaj, citeseerx, zenodo, google_scholar)"
```

---

### Task 4: 迁移特殊连接器（6 个文件）

**目标:** 迁移有继承关系、双类、工具类、或必需 API key 的连接器。

**Files:**
- 创建: `paper_search/connectors/oaipmh.py`
- 创建: `paper_search/connectors/base_search.py`
- 创建: `paper_search/connectors/chemrxiv.py`
- 创建: `paper_search/connectors/unpaywall.py`
- 创建: `paper_search/connectors/sci_hub.py`
- 创建: `paper_search/connectors/acm.py`
- 创建: `paper_search/connectors/ieee.py`

- [ ] **Step 1: 迁移 oaipmh.py（中间基类，不注册）**

OAIPMHSearcher 是 BASESearcher 的父类，自身不直接作为平台使用。
- **不加** `@register` 装饰器
- 继承 `PaperConnector`

```python
# 不注册，作为中间基类
class OAIPMHConnector(PaperConnector):
    capabilities = ConnectorCapabilities(search=True, download=True, read=True)
    ...
```

- [ ] **Step 2: 迁移 base_search.py（继承 oaipmh）**

```python
from .oaipmh import OAIPMHConnector
from .registry import register

@register("base")
class BASEConnector(OAIPMHConnector):
    capabilities = ConnectorCapabilities(search=True, download=True, read=True)
    ...
```

- [ ] **Step 3: 迁移 chemrxiv.py（继承 crossref）**

```python
from .crossref import CrossRefConnector
from .registry import register

@register("chemrxiv")
class ChemRxivConnector(CrossRefConnector):
    capabilities = ConnectorCapabilities(search=True, download=True, read=True)
    ...
```

注意: 确保 crossref.py 已在 Task 2 中迁移完毕。

- [ ] **Step 4: 迁移 unpaywall.py（双类文件）**

这个文件有两个类：
1. `UnpaywallResolver` — 工具类，**不继承** PaperConnector，不注册。提供 `resolve_best_pdf_url()` 和 `get_paper_by_doi()`。download_service 需要它。
2. `UnpaywallSearcher` — 继承 PaperConnector，注册为 `unpaywall`。内部依赖 `UnpaywallResolver`。

```python
# 工具类，不注册
class UnpaywallResolver:
    def __init__(self, email: Optional[str] = None): ...
    def resolve_best_pdf_url(self, doi: str) -> Optional[str]: ...
    def get_paper_by_doi(self, doi: str) -> Optional[Paper]: ...

@register("unpaywall")
class UnpaywallConnector(PaperConnector):
    capabilities = ConnectorCapabilities(search=True, download=False, read=False)
    def __init__(self, resolver: Optional[UnpaywallResolver] = None): ...
```

- [ ] **Step 5: 迁移 sci_hub.py（工具类，不注册）**

SciHubFetcher 不是 PaperConnector，是独立的下载工具。
- **不继承** PaperConnector
- **不加** `@register`
- download_service 的 fallback chain 需要它

```python
class SciHubFetcher:
    def __init__(self, base_url: str = "https://sci-hub.se", output_dir: str = "./downloads"): ...
    def download_pdf(self, identifier: str) -> Optional[str]: ...
```

- [ ] **Step 6: 迁移 ieee.py（必需 API key）**

```python
@register("ieee")
class IEEEConnector(PaperConnector):
    capabilities = ConnectorCapabilities(
        search=True, download=True, read=True,
        requires_key="IEEE_API_KEY",
    )
```

ConnectorRegistry 会检查 `requires_key`，如果环境变量未设置则跳过实例化。

- [ ] **Step 7: 迁移 acm.py（必需 API key）**

```python
@register("acm")
class ACMConnector(PaperConnector):
    capabilities = ConnectorCapabilities(
        search=True, download=True, read=True,
        requires_key="ACM_API_KEY",
    )
```

- [ ] **Step 8: 验证完整注册表**

```bash
cd /Users/deme/Downloads/temp_wenxian_jishu/paper-search
uv run python -c "
from paper_search.connectors.registry import ConnectorRegistry
reg = ConnectorRegistry()
print(f'Active connectors ({len(reg)}): {sorted(reg.all_names())}')
"
```

Expected: 应包含所有不需要必需 API key 的连接器（约 21-23 个，ieee/acm 只有设置了 key 才出现）。unpaywall 是否出现取决于 UNPAYWALL_EMAIL 是否设置。

- [ ] **Step 9: 提交**

```bash
git add paper_search/connectors/
git commit -m "feat: migrate special connectors (oaipmh chain, chemrxiv, unpaywall, sci_hub, ieee, acm)"
```

---

### Task 5: 实现搜索服务 (search_service.py)

**目标:** 实现核心 `PaperSearchService`，提供 `search()` 和 `snowball()` 方法。

**Files:**
- 创建: `paper_search/service/search_service.py`
- 修改: `paper_search/service/__init__.py`
- 创建: `tests/test_registry.py`
- 创建: `tests/test_search_service.py`

- [ ] **Step 1: 写 registry 测试**

```python
# tests/test_registry.py
from paper_search.connectors.base import PaperConnector, ConnectorCapabilities
from paper_search.connectors.registry import ConnectorRegistry, register, _REGISTRY

def test_registry_discovers_connectors():
    reg = ConnectorRegistry()
    names = reg.all_names()
    # 至少应有 arxiv, pubmed 等核心连接器
    assert "arxiv" in names
    assert "pubmed" in names
    assert len(names) >= 10

def test_registry_get():
    reg = ConnectorRegistry()
    arxiv = reg.get("arxiv")
    assert arxiv is not None
    assert isinstance(arxiv, PaperConnector)

def test_registry_contains():
    reg = ConnectorRegistry()
    assert "arxiv" in reg
    assert "nonexistent" not in reg
```

- [ ] **Step 2: 运行 registry 测试确认通过**

```bash
uv run pytest tests/test_registry.py -v
```

- [ ] **Step 3: 写 search_service 测试**

```python
# tests/test_search_service.py
import pytest
from paper_search.service.search_service import PaperSearchService
from paper_search.models.paper import Paper, SearchResult, SnowballResult

def test_service_init():
    svc = PaperSearchService()
    assert len(svc.available_sources()) >= 10

def test_parse_sources_all():
    svc = PaperSearchService()
    assert svc._parse_sources("all") == svc.available_sources()

def test_parse_sources_specific():
    svc = PaperSearchService()
    result = svc._parse_sources("arxiv,pubmed,nonexistent")
    assert "arxiv" in result
    assert "pubmed" in result
    assert "nonexistent" not in result

def test_dedupe_papers():
    svc = PaperSearchService()
    papers = [
        Paper(paper_id="1", title="Paper A", doi="10.1/a"),
        Paper(paper_id="2", title="Paper B", doi="10.1/a"),  # 同 DOI
        Paper(paper_id="3", title="Paper C"),
    ]
    deduped = svc._dedupe_papers(papers)
    assert len(deduped) == 2

@pytest.mark.asyncio
async def test_search_empty_query():
    svc = PaperSearchService()
    result = await svc.search("")
    assert result.total == 0
    assert "query" in result.errors
```

- [ ] **Step 4: 运行测试确认失败（search_service 尚未实现）**

```bash
uv run pytest tests/test_search_service.py -v
```
Expected: ImportError / FAIL

- [ ] **Step 5: 实现 search_service.py**

```python
# paper_search/service/search_service.py
"""Core search orchestration service."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from ..connectors.registry import ConnectorRegistry
from ..connectors.base import PaperConnector
from ..models.paper import Paper, SearchResult, SnowballResult

logger = logging.getLogger(__name__)


class PaperSearchService:
    """独立的论文搜索服务，不依赖任何传输协议。

    Usage:
        svc = PaperSearchService()
        result = await svc.search("machine learning", sources="arxiv,semantic")
    """

    def __init__(self, registry: Optional[ConnectorRegistry] = None):
        self.registry = registry or ConnectorRegistry()

    def available_sources(self) -> List[str]:
        return self.registry.all_names()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        sources: str = "all",
        max_results_per_source: int = 5,
        year: Optional[str] = None,
    ) -> SearchResult:
        if not query or not query.strip():
            return SearchResult(
                query=query or "",
                sources_requested=sources,
                errors={"query": "Query string is empty."},
            )

        selected = self._parse_sources(sources)
        if not selected:
            return SearchResult(
                query=query,
                sources_requested=sources,
                errors={"sources": "No valid sources selected."},
            )

        # 并发搜索
        task_map: Dict[str, asyncio.Task] = {}
        for name in selected:
            connector = self.registry.get(name)
            if connector is None:
                continue
            kwargs: Dict[str, Any] = {}
            if year and name == "semantic":
                kwargs["year"] = year
            task_map[name] = asyncio.ensure_future(
                self._async_search(connector, query, max_results_per_source, **kwargs)
            )

        source_names = list(task_map.keys())
        outputs = await asyncio.gather(*task_map.values(), return_exceptions=True)

        source_results: Dict[str, int] = {}
        errors: Dict[str, str] = {}
        merged: List[Paper] = []

        for name, output in zip(source_names, outputs):
            if isinstance(output, Exception):
                errors[name] = str(output)
                source_results[name] = 0
                continue
            source_results[name] = len(output)
            for paper in output:
                if not paper.source:
                    paper.source = name
                merged.append(paper)

        deduped = self._dedupe_papers(merged)

        return SearchResult(
            query=query,
            sources_requested=sources,
            sources_used=source_names,
            source_results=source_results,
            errors=errors,
            papers=deduped,
            total=len(deduped),
            raw_total=len(merged),
        )

    # ------------------------------------------------------------------
    # Snowball
    # ------------------------------------------------------------------

    async def snowball(
        self,
        paper_id: str,
        direction: str = "both",
        max_results_per_direction: int = 20,
        depth: int = 1,
    ) -> SnowballResult:
        depth = min(max(depth, 1), 3)
        semantic = self.registry.get("semantic")
        if semantic is None:
            return SnowballResult(
                seed_paper_id=paper_id,
                direction=direction,
                depth=depth,
                errors=["Semantic Scholar connector not available"],
            )

        all_papers: List[Paper] = []
        visited: set[str] = set()
        current_ids = [paper_id]
        layer_errors: List[str] = []

        for layer in range(depth):
            next_ids: List[str] = []
            for idx, pid in enumerate(current_ids):
                if pid in visited:
                    continue
                visited.add(pid)

                if layer > 0 or idx > 0:
                    await asyncio.sleep(1.0)

                refs: List[Paper] = []
                cites: List[Paper] = []

                if direction in ("backward", "both"):
                    try:
                        refs = await asyncio.to_thread(
                            semantic.get_references, pid, max_results_per_direction
                        )
                    except Exception as exc:
                        layer_errors.append(f"layer{layer}:refs:{pid}:{exc}")

                if direction in ("forward", "both"):
                    if direction == "both":
                        await asyncio.sleep(1.0)
                    try:
                        cites = await asyncio.to_thread(
                            semantic.get_citations, pid, max_results_per_direction
                        )
                    except Exception as exc:
                        layer_errors.append(f"layer{layer}:cites:{pid}:{exc}")

                for p in refs + cites:
                    all_papers.append(p)
                    if p.paper_id and p.paper_id not in visited:
                        next_ids.append(p.paper_id)

            current_ids = next_ids
            if not current_ids:
                break

        deduped = self._dedupe_papers(all_papers)
        return SnowballResult(
            seed_paper_id=paper_id,
            direction=direction,
            depth=depth,
            total=len(deduped),
            raw_total=len(all_papers),
            papers=deduped,
            errors=layer_errors,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _async_search(
        connector: PaperConnector,
        query: str,
        max_results: int,
        **kwargs,
    ) -> List[Paper]:
        papers = await asyncio.to_thread(
            connector.search, query, max_results=max_results, **kwargs
        )
        return papers or []

    def _parse_sources(self, sources: str) -> List[str]:
        if not sources or sources.strip().lower() == "all":
            return self.available_sources()
        normalized = [s.strip().lower() for s in sources.split(",") if s.strip()]
        return [s for s in normalized if s in self.registry]

    @staticmethod
    def _dedupe_papers(papers: List[Paper]) -> List[Paper]:
        deduped: List[Paper] = []
        seen: set[str] = set()
        for p in papers:
            key = PaperSearchService._paper_key(p)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(p)
        return deduped

    @staticmethod
    def _paper_key(paper: Paper) -> str:
        doi = (paper.doi or "").strip().lower()
        if doi:
            return f"doi:{doi}"
        title = (paper.title or "").strip().lower()
        authors = "; ".join(paper.authors).strip().lower() if paper.authors else ""
        if title:
            return f"title:{title}|authors:{authors}"
        return f"id:{(paper.paper_id or '').strip().lower()}"
```

- [ ] **Step 6: 运行测试确认通过**

```bash
uv run pytest tests/test_search_service.py tests/test_registry.py -v
```
Expected: ALL PASSED

- [ ] **Step 7: 提交**

```bash
git add paper_search/service/search_service.py tests/
git commit -m "feat: implement PaperSearchService with search and snowball"
```

---

### Task 6: 实现下载服务 (download_service.py)

**目标:** 实现 `DownloadService`，包含源原生下载 + 仓库回退 + Unpaywall + Sci-Hub 回退链。

**Files:**
- 创建: `paper_search/service/download_service.py`
- 创建: `tests/test_download_service.py`

- [ ] **Step 1: 写下载服务测试**

```python
# tests/test_download_service.py
import pytest
from paper_search.service.download_service import DownloadService
from paper_search.connectors.registry import ConnectorRegistry

def test_download_service_init():
    reg = ConnectorRegistry()
    ds = DownloadService(registry=reg)
    assert ds is not None

@pytest.mark.asyncio
async def test_download_unsupported_source():
    reg = ConnectorRegistry()
    ds = DownloadService(registry=reg)
    result = await ds.download(source="nonexistent", paper_id="123")
    assert "failed" in result.lower() or "unsupported" in result.lower()
```

- [ ] **Step 2: 实现 download_service.py**

逻辑迁移自原 `server.py` 的 `download_with_fallback()`、`_try_repository_fallback()`、`_download_from_url()` 函数。

核心方法：
- `download(source, paper_id, doi, title, save_path, use_scihub) -> str`
- `download_from_source(source, paper_id, save_path) -> str`
- `_try_repository_fallback(doi, title, save_path) -> tuple[Optional[str], str]`
- `_download_from_url(pdf_url, save_path, filename_hint) -> Optional[str]`

仓库回退顺序: openaire → core → europepmc → pmc → Unpaywall → Sci-Hub（可选）

- [ ] **Step 3: 运行测试**

```bash
uv run pytest tests/test_download_service.py -v
```

- [ ] **Step 4: 提交**

```bash
git add paper_search/service/download_service.py tests/test_download_service.py
git commit -m "feat: implement DownloadService with OA fallback chain"
```

---

### Task 7: 实现导出服务 (export_service.py)

**目标:** 实现 `ExportService`，支持 CSV、RIS、BibTeX 导出。

**Files:**
- 创建: `paper_search/service/export_service.py`
- 创建: `tests/test_export_service.py`

- [ ] **Step 1: 写导出服务测试**

```python
# tests/test_export_service.py
import os
import pytest
from paper_search.service.export_service import ExportService
from paper_search.models.paper import Paper

@pytest.fixture
def sample_papers():
    return [
        Paper(paper_id="1", title="Paper A", authors=["Alice"], doi="10.1/a"),
        Paper(paper_id="2", title="Paper B", authors=["Bob", "Carol"]),
    ]

def test_export_csv(sample_papers, tmp_path):
    svc = ExportService()
    path = svc.export(sample_papers, format="csv", save_path=str(tmp_path))
    assert path.endswith(".csv")
    assert os.path.exists(path)

def test_export_ris(sample_papers, tmp_path):
    svc = ExportService()
    path = svc.export(sample_papers, format="ris", save_path=str(tmp_path))
    assert path.endswith(".ris")

def test_export_bibtex(sample_papers, tmp_path):
    svc = ExportService()
    path = svc.export(sample_papers, format="bibtex", save_path=str(tmp_path))
    assert path.endswith(".bib")

def test_export_unsupported_format(sample_papers, tmp_path):
    svc = ExportService()
    result = svc.export(sample_papers, format="xml", save_path=str(tmp_path))
    assert "unsupported" in result.lower()
```

- [ ] **Step 2: 实现 export_service.py**

逻辑迁移自原 `server.py` 的 `export_papers()` 函数。接受 `List[Paper]`（pydantic 对象）而非 `List[Dict]`。

- [ ] **Step 3: 运行测试**

```bash
uv run pytest tests/test_export_service.py -v
```

- [ ] **Step 4: 更新 service/__init__.py 导出所有服务**

```python
from .search_service import PaperSearchService
from .download_service import DownloadService
from .export_service import ExportService

__all__ = ["PaperSearchService", "DownloadService", "ExportService"]
```

- [ ] **Step 5: 提交**

```bash
git add paper_search/service/ tests/test_export_service.py
git commit -m "feat: implement ExportService (csv, ris, bibtex)"
```

---

### Task 8: 实现 MCP 传输层 (mcp_server.py)

**目标:** 实现薄 MCP 适配层，将 PaperSearchService 暴露为 MCP tools。

**Files:**
- 创建: `paper_search/transports/__init__.py`
- 创建: `paper_search/transports/mcp_server.py`
- 创建: `tests/test_mcp_server.py`

> **审查修正 — 两个 BLOCKING 问题的解决方案:**
>
> **问题 1: `**kwargs` 与 FastMCP 不兼容。** FastMCP 用 `inspect.signature` 生成 JSON schema，`**kwargs` 无法序列化。
> **解决:** 动态注册的通用工具只暴露 `(query: str, max_results: int = 10)` 两个参数。有特殊参数的连接器（semantic: `year`, crossref: `filter/sort/order`, iacr: `fetch_details`）作为**静态工具**手动注册，用显式参数签名。
>
> **问题 2: `get_crossref_paper_by_doi` 和 `download_scihub` 工具缺失。**
> **解决:** 作为静态顶层工具手动注册在 mcp_server.py 中。

- [ ] **Step 1: 创建 transports/__init__.py**

```python
# paper_search/transports/__init__.py
```

- [ ] **Step 2: 实现 mcp_server.py**

设计要点：
1. **静态顶层工具:** `search_papers`, `download_with_fallback`, `snowball_search`, `export_papers`, `get_crossref_paper_by_doi`, `download_scihub`
2. **静态特殊参数工具:** `search_semantic`(有 year), `search_crossref`(有 filter/sort/order), `search_iacr`(有 fetch_details) — 手动注册，显式参数签名
3. **动态注册通用工具:** 遍历 registry，为每个连接器自动注册 `search_<name>(query, max_results)`, `download_<name>(paper_id, save_path)`, `read_<name>_paper(paper_id, save_path)` — 仅 `query` + `max_results` 两个参数，无 `**kwargs`
4. 动态注册跳过已手动注册的（semantic, crossref, iacr）

```python
# paper_search/transports/mcp_server.py
import asyncio
from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP
from ..service.search_service import PaperSearchService
from ..service.download_service import DownloadService
from ..service.export_service import ExportService
from ..connectors.sci_hub import SciHubFetcher

mcp = FastMCP("paper_search_server")
search_service = PaperSearchService()
download_service = DownloadService(registry=search_service.registry)
export_service = ExportService()

# ========== 静态顶层工具 ==========

@mcp.tool()
async def search_papers(
    query: str,
    max_results_per_source: int = 5,
    sources: str = "all",
    year: Optional[str] = None,
) -> Dict[str, Any]:
    """Unified search across all configured academic platforms."""
    result = await search_service.search(query, sources, max_results_per_source, year)
    data = result.model_dump()
    # 将 Paper 对象转为 API dict
    data["papers"] = [p.to_api_dict() for p in result.papers]
    return data

@mcp.tool()
async def download_with_fallback(
    source: str,
    paper_id: str,
    doi: str = "",
    title: str = "",
    save_path: str = "./downloads",
    use_scihub: bool = True,
    scihub_base_url: str = "https://sci-hub.se",
) -> str:
    """Try source-native download, OA repositories, Unpaywall, then optional Sci-Hub."""
    return await download_service.download(
        source, paper_id, doi, title, save_path, use_scihub, scihub_base_url
    )

@mcp.tool()
async def snowball_search(
    paper_id: str,
    direction: str = "both",
    max_results_per_direction: int = 20,
    depth: int = 1,
) -> Dict[str, Any]:
    """Snowball search: find references and/or citations of a seed paper recursively."""
    result = await search_service.snowball(paper_id, direction, max_results_per_direction, depth)
    data = result.model_dump()
    data["papers"] = [p.to_api_dict() for p in result.papers]
    return data

@mcp.tool()
async def export_papers(
    papers: List[Dict[str, Any]],
    format: str = "csv",
    save_path: str = "./exports",
    filename: str = "papers",
) -> str:
    """Export paper dicts to CSV, RIS, or BibTeX."""
    return export_service.export_from_dicts(papers, format, save_path, filename)

@mcp.tool()
async def get_crossref_paper_by_doi(doi: str) -> Dict:
    """Get a specific paper from CrossRef by its DOI."""
    connector = search_service.registry.get("crossref")
    if connector is None:
        return {}
    paper = await asyncio.to_thread(connector.get_paper_by_doi, doi)
    return paper.to_api_dict() if paper else {}

@mcp.tool()
async def download_scihub(
    identifier: str,
    save_path: str = "./downloads",
    base_url: str = "https://sci-hub.se",
) -> str:
    """Download paper PDF via Sci-Hub (optional fallback)."""
    fetcher = SciHubFetcher(base_url=base_url, output_dir=save_path)
    result = await asyncio.to_thread(fetcher.download_pdf, identifier)
    return result or "Sci-Hub download failed."

# ========== 静态特殊参数工具 ==========
# 这些连接器有 FastMCP 无法从 **kwargs 推断的特殊参数

@mcp.tool()
async def search_semantic(
    query: str, year: Optional[str] = None, max_results: int = 10
) -> List[Dict]:
    """Search academic papers from Semantic Scholar."""
    connector = search_service.registry.get("semantic")
    if connector is None:
        return []
    kwargs = {"year": year} if year else {}
    papers = await search_service._async_search(connector, query, max_results, **kwargs)
    return [p.to_api_dict() for p in papers]

@mcp.tool()
async def search_crossref(
    query: str,
    max_results: int = 10,
    filter: Optional[str] = None,
    sort: Optional[str] = None,
    order: Optional[str] = None,
) -> List[Dict]:
    """Search academic papers from CrossRef database."""
    connector = search_service.registry.get("crossref")
    if connector is None:
        return []
    kwargs = {k: v for k, v in {"filter": filter, "sort": sort, "order": order}.items() if v}
    papers = await search_service._async_search(connector, query, max_results, **kwargs)
    return [p.to_api_dict() for p in papers]

@mcp.tool()
async def search_iacr(
    query: str, max_results: int = 10, fetch_details: bool = True
) -> List[Dict]:
    """Search academic papers from IACR ePrint Archive."""
    connector = search_service.registry.get("iacr")
    if connector is None:
        return []
    papers = await asyncio.to_thread(
        connector.search, query, max_results, fetch_details
    )
    return [p.to_api_dict() for p in (papers or [])]

# ========== 动态注册通用工具 ==========

# 已手动注册的连接器，跳过动态注册 search 工具
_STATIC_SEARCH_TOOLS = {"semantic", "crossref", "iacr"}


def _register_search_tool(name: str) -> None:
    """注册 search_<name>(query, max_results) 工具。"""
    _name = name  # 闭包捕获

    async def tool_fn(query: str, max_results: int = 10) -> List[Dict]:
        connector = search_service.registry.get(_name)
        if connector is None:
            return []
        papers = await search_service._async_search(connector, query, max_results)
        return [p.to_api_dict() for p in papers]

    tool_fn.__name__ = f"search_{name}"
    tool_fn.__doc__ = f"Search academic papers from {name}."
    tool_fn.__qualname__ = f"search_{name}"
    mcp.tool()(tool_fn)


def _register_download_tool(name: str) -> None:
    _name = name

    async def tool_fn(paper_id: str, save_path: str = "./downloads") -> str:
        connector = search_service.registry.get(_name)
        if connector is None:
            return f"Connector {_name} not available."
        return await asyncio.to_thread(connector.download_pdf, paper_id, save_path)

    tool_fn.__name__ = f"download_{name}"
    tool_fn.__doc__ = f"Download PDF of a {name} paper."
    tool_fn.__qualname__ = f"download_{name}"
    mcp.tool()(tool_fn)


def _register_read_tool(name: str) -> None:
    _name = name

    async def tool_fn(paper_id: str, save_path: str = "./downloads") -> str:
        connector = search_service.registry.get(_name)
        if connector is None:
            return f"Connector {_name} not available."
        return await asyncio.to_thread(connector.read_paper, paper_id, save_path)

    tool_fn.__name__ = f"read_{name}_paper"
    tool_fn.__doc__ = f"Read and extract text content from a {name} paper."
    tool_fn.__qualname__ = f"read_{name}_paper"
    mcp.tool()(tool_fn)


def _register_platform_tools() -> None:
    for name in search_service.available_sources():
        connector = search_service.registry.get(name)
        if connector is None:
            continue
        caps = connector.capabilities

        if name not in _STATIC_SEARCH_TOOLS:
            _register_search_tool(name)

        if caps.download:
            _register_download_tool(name)

        if caps.read:
            _register_read_tool(name)


_register_platform_tools()


def main():
    mcp.run(transport="stdio")
```

- [ ] **Step 3: ExportService 需要同时支持 Paper 对象和 dict 输入**

MCP `export_papers` 工具接收的是 `List[Dict]`（来自 LLM），而 service 层内部使用 `List[Paper]`。需要在 `ExportService` 中添加 `export_from_dicts()` 方法，接受 dict 列表。

在 Task 7 的 `export_service.py` 中添加:
```python
def export_from_dicts(self, papers: List[Dict], format: str, save_path: str, filename: str = "papers") -> str:
    """Accept raw dicts (from MCP tool input) and export."""
    return self._do_export(papers, format, save_path, filename)

def export(self, papers: List[Paper], format: str, save_path: str, filename: str = "papers") -> str:
    """Accept Paper objects and export."""
    dicts = [p.to_api_dict() for p in papers]
    return self._do_export(dicts, format, save_path, filename)
```

- [ ] **Step 4: 写 MCP server 基础测试**

```python
# tests/test_mcp_server.py
def test_mcp_server_imports():
    """Verify the MCP transport module can be imported without errors."""
    from paper_search.transports import mcp_server
    assert hasattr(mcp_server, "mcp")
    assert hasattr(mcp_server, "main")

def test_static_tools_registered():
    from paper_search.transports import mcp_server
    # 检查静态工具存在
    tool_names = [t.name for t in mcp_server.mcp._tools.values()]
    assert "search_papers" in tool_names
    assert "download_with_fallback" in tool_names
    assert "snowball_search" in tool_names
    assert "get_crossref_paper_by_doi" in tool_names
    assert "download_scihub" in tool_names
    # 特殊参数工具
    assert "search_semantic" in tool_names
    assert "search_crossref" in tool_names
    assert "search_iacr" in tool_names

def test_dynamic_tools_registered():
    from paper_search.transports import mcp_server
    tool_names = [t.name for t in mcp_server.mcp._tools.values()]
    # 动态注册的 search 工具（不含已静态注册的）
    assert "search_arxiv" in tool_names
    assert "search_pubmed" in tool_names
    # 动态注册的 download/read 工具
    assert "download_arxiv" in tool_names
    assert "read_arxiv_paper" in tool_names
```

注意: MCP server 的完整功能测试需要运行实际的 MCP 协议，这里只做导入和注册验证。
`mcp._tools` 的具体 API 可能因 FastMCP 版本不同而异，实现时需调整。

- [ ] **Step 5: 运行测试**

```bash
uv run pytest tests/test_mcp_server.py -v
```

- [ ] **Step 6: 提交**

```bash
git add paper_search/transports/ tests/test_mcp_server.py
git commit -m "feat: implement MCP transport layer with static + dynamic tool registration"
```

---

### Task 9: 集成测试 + 收尾

**目标:** 验证整个系统端到端可用，清理代码。

**Files:**
- 修改: `paper_search/__init__.py` — 确保顶层导出正确
- 审查: 所有文件 — import 链完整性
- 创建: `.env.example`

- [ ] **Step 1: 运行全量测试**

```bash
cd /Users/deme/Downloads/temp_wenxian_jishu/paper-search
uv run pytest tests/ -v
```
Expected: ALL PASSED

- [ ] **Step 2: 验证 MCP server 可启动**

```bash
cd /Users/deme/Downloads/temp_wenxian_jishu/paper-search
timeout 5 uv run paper-search-mcp || true  # 应启动 stdio 模式，5秒后超时退出
```
Expected: 启动无报错（超时退出是正常的，因为 stdio 模式等待输入）

- [ ] **Step 3: 验证作为库使用**

```python
# 验证独立服务可用
import asyncio
from paper_search import PaperSearchService

async def main():
    svc = PaperSearchService()
    print(f"Available: {svc.available_sources()}")
    # 可选: 测试真实搜索（需要网络）
    # result = await svc.search("machine learning", sources="arxiv", max_results_per_source=2)
    # print(f"Found {result.total} papers")

asyncio.run(main())
```

- [ ] **Step 4: 创建 .env.example**

```bash
# .env.example
PAPER_SEARCH_MCP_UNPAYWALL_EMAIL=your@email.com
PAPER_SEARCH_MCP_CORE_API_KEY=
PAPER_SEARCH_MCP_SEMANTIC_SCHOLAR_API_KEY=
PAPER_SEARCH_MCP_ZENODO_ACCESS_TOKEN=
PAPER_SEARCH_MCP_GOOGLE_SCHOLAR_PROXY_URL=
PAPER_SEARCH_MCP_IEEE_API_KEY=
PAPER_SEARCH_MCP_ACM_API_KEY=
PAPER_SEARCH_MCP_DOAJ_API_KEY=
```

- [ ] **Step 5: 最终提交**

```bash
git add -A
git commit -m "feat: complete paper-search service refactoring with all connectors and MCP transport"
```

---

## 风险与注意事项

1. **连接器内部逻辑不改** — 仅改 imports、基类、装饰器，降低回归风险
2. **Pydantic Paper 兼容性** — 构造方式与原 dataclass 相同，但 `to_dict()` 改为 `to_api_dict()`（原方法名在 service 层不再使用）
3. **SemanticSearcher 的特殊方法** — `get_references()` 和 `get_citations()` 是 snowball 搜索的依赖，必须保留且在 search_service 中通过 `semantic.get_references` 直接调用
4. **动态工具注册** — FastMCP 用 `inspect.signature` 生成 JSON schema，**不能使用 `**kwargs`**。动态工具只有 `(query, max_results)` 两个参数。特殊参数的连接器（semantic, crossref, iacr）必须作为静态工具手动注册
5. **可选依赖** — `fastmcp` 和 `mcp` 放在 `[project.optional-dependencies.mcp]` 中，纯服务使用不需要安装
6. **Capabilities 设为 True 保兼容** — 即使连接器的 download/read 是 stub（返回错误信息），只要原 server.py 注册了对应 MCP 工具就设为 True，确保 MCP API 向后兼容

## 审查修正记录

| 问题 | 严重程度 | 修正 |
|------|---------|------|
| `get_crossref_paper_by_doi` MCP 工具缺失 | BLOCKING | 作为静态顶层工具在 Task 8 中注册 |
| `**kwargs` 与 FastMCP schema 不兼容 | BLOCKING | 动态工具不用 `**kwargs`；semantic/crossref/iacr 作为静态工具注册 |
| pubmed/dblp/openalex/crossref/ssrn/openaire 的 capabilities 映射错误 | MINOR | 统一设为 True 保持 MCP 兼容 |
| `download_scihub` 独立工具缺失 | MINOR | 作为静态顶层工具注册 |

## 扩展新平台的步骤（未来）

添加一个新平台只需：
1. 创建 `paper_search/connectors/new_platform.py`
2. 继承 `PaperConnector`，实现 `search()` 方法
3. 加 `@register("new_platform")` 装饰器
4. 设置 `capabilities`

**无需修改任何其他文件** — registry 自动发现，service 自动包含，MCP 自动注册工具。
