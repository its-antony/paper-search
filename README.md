# Paper Search

> **基于 [openags/paper-search-mcp](https://github.com/openags/paper-search-mcp) 重构** — 原项目由 P.S Zhang 开发，MIT 协议。
>
> 本项目在原始项目基础上进行了**服务化架构重构**，将业务逻辑从 MCP 协议绑定中解耦，形成独立的服务层，可作为 **Python 库**直接调用，也可作为 **MCP Server** 接入 Claude Desktop 等 LLM 客户端。

一个支持 **20+ 学术平台**的论文搜索、下载与导出服务。

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Pydantic v2](https://img.shields.io/badge/pydantic-v2-green.svg)

---

## 特性

- **20+ 学术数据源** — arXiv、PubMed、Semantic Scholar、Crossref、OpenAlex、Google Scholar 等
- **三层架构** — Connectors → Service → Transport，关注点清晰分离
- **即插即用** — 添加新平台只需一个文件，自动注册，零配置
- **双模式使用** — 既是 Python 库（`from paper_search import PaperSearchService`），也是 MCP Server
- **Pydantic 数据模型** — 类型安全、序列化友好
- **多源并发搜索 + 自动去重** — 基于 DOI / 标题+作者 去重
- **Open-access first 下载链** — 源原生下载 → OA 仓库 → Unpaywall；其他来源需要显式 opt-in
- **引文网络追踪** — Snowball search，支持前向/后向引用递归（1-3 层深度）
- **多格式导出** — CSV、RIS（Zotero/Mendeley/EndNote）、BibTeX

---

## 架构

```
paper_search/
├── models/          # Pydantic 数据模型 (Paper, SearchResult, SnowballResult)
├── connectors/      # 平台连接器 (@register 自动注册)
│   ├── base.py      #   抽象基类 PaperConnector
│   ├── registry.py  #   连接器注册表（自动发现）
│   ├── arxiv.py     #   arXiv 连接器
│   ├── semantic.py  #   Semantic Scholar 连接器
│   └── ...          #   25+ 连接器
├── service/         # 业务编排层（不依赖任何传输协议）
│   ├── search_service.py    # 多源搜索 + Snowball
│   ├── download_service.py  # 下载回退链
│   └── export_service.py    # CSV/RIS/BibTeX 导出
├── transports/      # 传输适配层
│   └── mcp_server.py        # MCP Server（薄包装）
├── config.py        # 环境变量管理
└── utils.py         # 工具函数
```

### 与原项目的区别

| 方面 | 原项目 (paper-search-mcp) | 本项目 (paper-search) |
|------|--------------------------|----------------------|
| 架构 | 单文件 server.py（1570 行） | 三层架构，职责分离 |
| 数据模型 | dataclass | Pydantic v2 |
| 复用性 | 仅限 MCP 调用 | 可作为库 import 使用 |
| 添加新平台 | 改 5 处代码 | 只写 1 个文件 |
| 平台分派 | 20+ 个 if/elif | @register 自动注册 |
| 测试 | 需启动 MCP Server | 直接测试 Service 层 |

---

## 支持的数据源

### 免费开放数据源（无需 API Key）

| 平台 | 搜索 | 下载 | 读取 | 说明 |
|------|:----:|:----:|:----:|------|
| arXiv | ✅ | ✅ | ✅ | 预印本，覆盖物理/CS/数学等 |
| PubMed | ✅ | - | - | 生物医学文献元数据 |
| bioRxiv | ✅ | ✅ | ✅ | 生物学预印本 |
| medRxiv | ✅ | ✅ | ✅ | 医学预印本 |
| Crossref | ✅ | - | - | DOI 元数据骨干 |
| OpenAlex | ✅ | - | - | 开放学术知识图谱 |
| Europe PMC | ✅ | ✅ | ✅ | 欧洲生物医学 OA |
| PubMed Central | ✅ | ✅ | ✅ | NIH OA 全文 |
| dblp | ✅ | - | - | 计算机科学文献索引 |
| IACR | ✅ | ✅ | ✅ | 密码学预印本 |
| HAL | ✅ | ✅ | ✅ | 法国开放存档 |
| SSRN | ✅ | ⚠️ | ⚠️ | 社科预印本（best-effort） |
| ChemRxiv | ✅ | ✅ | ✅ | 化学预印本 |

### 可选 API Key 数据源（免费申请，提升速率）

| 平台 | 环境变量 | 申请地址 |
|------|---------|---------|
| Semantic Scholar | `PAPER_SEARCH_MCP_SEMANTIC_SCHOLAR_API_KEY` | [semanticscholar.org](https://www.semanticscholar.org/product/api) |
| CORE | `PAPER_SEARCH_MCP_CORE_API_KEY` | [core.ac.uk](https://core.ac.uk/services/api) |
| DOAJ | `PAPER_SEARCH_MCP_DOAJ_API_KEY` | [doaj.org](https://doaj.org/apply-for-api-key/) |
| Zenodo | `PAPER_SEARCH_MCP_ZENODO_ACCESS_TOKEN` | [zenodo.org](https://zenodo.org/account/settings/applications/) |
| Unpaywall | `PAPER_SEARCH_MCP_UNPAYWALL_EMAIL` | [unpaywall.org](https://unpaywall.org/products/api) |
| Google Scholar | `PAPER_SEARCH_MCP_GOOGLE_SCHOLAR_PROXY_URL` | 自备代理 |
| OpenAIRE | `PAPER_SEARCH_MCP_OPENAIRE_API_KEY` | [openaire.eu](https://develop.openaire.eu/) |
| CiteSeerX | `PAPER_SEARCH_MCP_CITESEERX_API_KEY` | - |

### 付费/受限数据源（需 API Key 激活）

| 平台 | 环境变量 | 说明 |
|------|---------|------|
| IEEE Xplore | `PAPER_SEARCH_MCP_IEEE_API_KEY` | 未设置 key 时自动禁用 |
| ACM Digital Library | `PAPER_SEARCH_MCP_ACM_API_KEY` | 未设置 key 时自动禁用 |

---

## 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/its-antony/paper-search.git
cd paper-search

# 安装依赖（自动创建虚拟环境）
uv sync

# 如果需要 MCP Server 功能
uv sync --extra mcp
```

### 作为 Python 库使用

```python
import asyncio
from paper_search import PaperSearchService

async def main():
    svc = PaperSearchService()

    # 多源并发搜索
    result = await svc.search(
        "real world assets tokenization",
        sources="crossref,openalex,arxiv",
        max_results_per_source=5,
    )

    for paper in result.papers:
        print(f"{paper.title} ({paper.source})")
        print(f"  DOI: {paper.doi}")

asyncio.run(main())
```

### 引文网络追踪（Snowball Search）

```python
async def snowball_demo():
    svc = PaperSearchService()

    result = await svc.snowball(
        paper_id="DOI:10.1038/nature12373",
        direction="both",      # forward + backward
        depth=2,               # 2 层递归
        max_results_per_direction=10,
    )
    print(f"发现 {result.total} 篇相关论文")
```

### 下载与导出

```python
from paper_search.service import DownloadService, ExportService
from paper_search.connectors.registry import ConnectorRegistry

async def download_and_export():
    reg = ConnectorRegistry()
    dl = DownloadService(registry=reg)
    export = ExportService()

    # 下载论文 PDF（默认只走 open-access fallback）
    path = await dl.download(
        source="arxiv",
        paper_id="2106.12345",
        save_path="./downloads",
    )

    # 导出搜索结果
    svc = PaperSearchService()
    result = await svc.search("blockchain finance", sources="crossref")
    export.export(result.papers, format="bibtex", save_path="./exports")
```

### 作为 MCP Server 使用

#### Claude Desktop 配置

```json
{
  "mcpServers": {
    "paper-search": {
      "command": "uv",
      "args": [
        "run", "--directory", "/path/to/paper-search",
        "-m", "paper_search.transports.mcp_server"
      ],
      "env": {
        "PAPER_SEARCH_MCP_UNPAYWALL_EMAIL": "your@email.com",
        "PAPER_SEARCH_MCP_SEMANTIC_SCHOLAR_API_KEY": ""
      }
    }
  }
}
```

#### Claude Code (CLI) 配置

```bash
# 添加为全局 MCP Server（所有项目可用）
claude mcp add --scope user paper-search -- \
  uv run --directory /path/to/paper-search -m paper_search.transports.mcp_server

# 或仅当前项目可用
claude mcp add paper-search -- \
  uv run --directory /path/to/paper-search -m paper_search.transports.mcp_server

# 如需配置 API Key
claude mcp add --scope user paper-search \
  -e PAPER_SEARCH_MCP_UNPAYWALL_EMAIL=your@email.com \
  -e PAPER_SEARCH_MCP_SEMANTIC_SCHOLAR_API_KEY=sk-xxx \
  -- uv run --directory /path/to/paper-search -m paper_search.transports.mcp_server
```

添加后重启 Claude Code 即可在对话中直接使用论文搜索工具。

#### 局域网 / 远程访问（HTTP 模式）

MCP Server 支持三种传输模式：`stdio`（默认）、`sse`、`streamable-http`。

```bash
# 启动 HTTP 模式（局域网可访问）
uv run -m paper_search.transports.mcp_server --transport streamable-http --host 0.0.0.0 --port 8000

# 或 SSE 模式
uv run -m paper_search.transports.mcp_server --transport sse --host 0.0.0.0 --port 8000
```

其他机器的 Claude Code 通过 URL 连接：

```bash
claude mcp add --scope user paper-search --transport http http://192.168.x.x:8000/mcp
```

---

## 配置

将 API Key 写入项目根目录的 `.env` 文件（启动时自动加载）：

```bash
cp .env.example .env
# 编辑 .env 填入你的 key
```

所有环境变量均使用 `PAPER_SEARCH_MCP_` 前缀，兼容原项目的无前缀写法。

### 下载策略

默认下载流程只使用源站、开放仓库和 Unpaywall 等 open-access 来源。任何非 OA fallback 都需要调用方显式开启，并由使用者自行确认合规性。

---

## 扩展新平台

添加一个新的学术数据源只需 **1 个文件**：

```python
# paper_search/connectors/my_platform.py
from ..models.paper import Paper
from .base import PaperConnector, ConnectorCapabilities
from .registry import register

@register("my_platform")
class MyPlatformConnector(PaperConnector):
    capabilities = ConnectorCapabilities(search=True, download=True, read=False)

    def search(self, query: str, max_results: int = 10, **kwargs):
        # 你的搜索逻辑
        return [Paper(paper_id="...", title="...", source="my_platform")]

    def download_pdf(self, paper_id: str, save_path: str) -> str:
        # 你的下载逻辑
        return f"{save_path}/{paper_id}.pdf"
```

**无需修改任何其他文件** — Registry 自动发现，Service 自动包含，MCP 自动注册工具。

---

## 开发

```bash
# 安装开发依赖
uv sync --extra dev --extra mcp

# 运行测试
uv run pytest tests/ -v

# 启动 MCP Server（stdio 模式）
uv run paper-search-mcp

# 启动 MCP Server（HTTP 模式，局域网可访问）
uv run paper-search-mcp --transport streamable-http --host 0.0.0.0 --port 8000
```

---

## 致谢

- 原始项目 [openags/paper-search-mcp](https://github.com/openags/paper-search-mcp)，由 [P.S Zhang](https://github.com/openags) 开发
- 本项目在其基础上进行了服务化架构重构，保留了全部平台连接器的业务逻辑

## 许可证

MIT License — 详见 [LICENSE](LICENSE) 文件。
