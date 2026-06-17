# CyberNote 赛博笔记

> **笔记 + LLM 第二大脑** —— 基于 Karpathy Wiki 编译范式的个人知识管理系统
>
> 致力于打造一个 个人知识行为信息库，专属于个人的数据层。
>
> 基于数据层的个性化智能体正在开发中，非常欢迎各位开发者测试、提出问题、改进。

<p align="center">
  <img src="https://img.shields.io/badge/version-1.1-blue" alt="version">
  <img src="https://img.shields.io/badge/Vue-3.5-green" alt="vue">
  <img src="https://img.shields.io/badge/FastAPI-0.111+-teal" alt="fastapi">
  <img src="https://img.shields.io/badge/Python-3.10+-yellow" alt="python">
  <img src="https://img.shields.io/badge/LangGraph-1.2+-purple" alt="langgraph">
  <img src="https://img.shields.io/badge/license-MIT-gray" alt="license">
</p>

---



## 更新与开发日志

### 最新更新 V1.1（2026-06-16）

| 日期 | 更新内容 |
|------|----------|
| 2026-06-16 | 📊 知识图谱可视化已完成（2D/3D 双模式，D3-force + Three.js） |
| 2026-06-11 | 🔥 多智能体协作编译引擎已完整落地（LangGraph 8-Agent 层次协作） |

### 最近开发

🧮 **知识防御战（Knowledge Arena）答题模块**

基于 Wiki 知识库的 LLM 驱动知识测验，核心目的：让学习者在交互形式中进行信息加工，避免枯燥乏味的直接阅读。

> **已完成**：Wiki 页面内容 → LLM 出题 (Prompt) → 选择题 → 用户作答 → 即时判分 → 成绩报告

#### 开发计划

1. 塔防游戏核心功能开发
2. LLM 编译及题目生成的可视化思考过程
3. 前端页面风格优化与个性化设计
4. 知识图谱交互性与性能持续优化



## V1.1

![V1.1 总览 1](docs/images/image-20260616235218513.png)

![V1.1 总览 2](docs/images/image-20260616235234176.png)

![V1.1 总览 3](docs/images/image-20260616235321448.png)

![V1.1 总览 4](docs/images/image-20260616235348348.png)





## V1.0

![Memo Flow](docs/images/image-20260524222727893.png)

![Compile Engine](docs/images/image-20260524223038460.png)

![Wiki Hub](docs/images/image-20260524223102805.png)

![Chat](docs/images/image-20260524223127422.png)

![Settings](docs/images/image-20260524223146180.png)



## 目录

- [核心理念](#核心理念)
- [功能概览](#功能概览)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
  - [方式一：一键启动脚本（Windows 推荐）](#方式一一键启动脚本windows-推荐)
  - [方式二：手动启动（开发模式）](#方式二手动启动开发模式)
  - [方式三：Docker Compose 部署](#方式三docker-compose-部署)
- [配置 LLM 模型](#配置-llm-模型)
- [使用指南](#使用指南)
- [环境变量说明](#环境变量说明)
- [项目结构](#项目结构)
- [API 文档](#api-文档)
- [常见问题](#常见问题)

---

## 核心理念

灵感来自 Andrej Karpathy 提出的 Wiki 编译范式：

```
原始笔记（随便写） → LLM 编译（自动整理） → Wiki 知识库（结构化） → AI 对话（智能查询）
```

你只管把想法「倒进来」，LLM 帮你整理成结构化知识，你随时可以和 AI 对话查询这些知识。

---

## 功能概览

| 模块 | 功能 |
|------|------|
| **Memo Flow** | 时间流笔记，支持 Markdown 编辑（CodeMirror 6）、标签、全文搜索 |
| **Compile Engine** | LLM 编译引擎，将碎片笔记编译为结构化 Wiki 页面（支持手动/定时触发）<br>🔥 **v1.1 新增** 多智能体协作编译：Coordinator → Researcher×3 → Integrator → Writer → Reviewer×2 → Arbiter → Editor/Linker，LangGraph 编排，SSE 实时追踪 |
| **Wiki Hub** | 结构化知识库，支持分类浏览、双向链接 `[[页面名]]`、知识图谱可视化<br>🔥 **新增** 2D/3D 双模式图谱：D3-force 力导向图（Canvas 渲染，拖拽/缩放/筛选）+ Three.js 3D 沉浸模式（星空背景 + 泛光），SSE 实时生长动画 |
| **Chat** | AI 对话助手，自动注入 Wiki 上下文，支持流式输出（SSE） |
| **Model Hub** | 多模型管理，支持 DeepSeek / Qwen / Ollama，API Key 加密存储 |

---

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Vue 3 + Vite + TypeScript + Pinia + Vue Router |
| 编辑器 | CodeMirror 6（Markdown）+ markdown-it + highlight.js |
| 后端 | Python FastAPI + SQLAlchemy 2.0 (async) + Pydantic v2 |
| 数据库 | SQLite + aiosqlite（单机）/ PostgreSQL + asyncpg（生产） |
| 全文搜索 | SQLite FTS5 虚拟表 |
| 编排 | LangGraph 1.2+（多智能体 DAG 编排） |
| LLM | LiteLLM 统一调用（DeepSeek / Qwen / Ollama） |
| 部署 | Docker Compose + Nginx 反向代理 |

---

## 快速开始

### 环境要求

| 依赖 | 最低版本 | 说明 |
|------|---------|------|
| Python | 3.10+ | 后端运行环境 |
| Node.js | 18+ | 前端构建与开发服务器 |
| Git | 任意版本 | 克隆项目 |

可选：
- **Docker + Docker Compose**：用于容器化部署
- **Ollama**：如需使用本地大模型（[下载地址](https://ollama.com)）

---

### 方式一：一键启动脚本（Windows 推荐）

> 适合快速体验，脚本会自动安装依赖并启动前后端服务。

**第 1 步：克隆项目**

```bash
git clone https://github.com/user0752/Cyberdiary.git
cd Cyberdiary
```

**第 2 步：双击运行启动脚本**

```bash
start.bat
```

脚本会自动：
1. 检测 Python 和 Node.js 是否安装
2. 首次运行时创建虚拟环境并安装依赖
3. 启动后端（`http://localhost:8000`）和前端（`http://localhost:5173`）
4. 打开浏览器访问应用

> **Linux / macOS** 用户使用 `./start.sh`（需先 `chmod +x start.sh`）

---

### 方式二：手动启动（开发模式）

**第 1 步：克隆项目**

```bash
git clone https://github.com/user0752/Cyberdiary.git
cd Cyberdiary
```

**第 2 步：启动后端**

```bash
cd backend

# 创建并激活虚拟环境
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux / macOS

# 安装依赖
pip install -r requirements.txt

# 复制并编辑环境配置（可选，默认配置即可运行）
copy .env.example .env       # Windows
# cp .env.example .env       # Linux / macOS

# 启动服务
uvicorn app.main:app --reload --port 8000
```

启动成功后看到：

```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
```

**第 3 步：启动前端**（新开一个终端窗口）

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

启动成功后看到：

```
  VITE v8.x.x  ready in xxx ms

  ➜  Local:   http://localhost:5173/
```

**第 4 步：打开浏览器**

访问 **http://localhost:5173** 即可使用。

> 前端开发服务器会自动将 `/api` 请求代理到后端 `localhost:8000`（配置在 `frontend/vite.config.ts`）。

---

### 方式三：Docker Compose 部署

> 适合生产部署或快速体验完整功能，前后端统一容器化运行。

**第 1 步：克隆项目**

```bash
git clone https://github.com/user0752/Cyberdiary.git
cd Cyberdiary
```

**第 2 步：配置环境变量**

在**项目根目录**创建 `.env` 文件（与 `docker-compose.yml` 同级）：

```env
# 必填：修改为一个随机字符串（JWT 密钥）
SECRET_KEY=your-random-secret-key-here
```

> 不设置则使用默认值 `dev-secret-key-change-in-production`，仅限本地测试使用。

**第 3 步：启动服务**

```bash
docker compose up --build
```

**第 4 步：打开浏览器**

访问 **http://localhost:8080** 即可使用。

> Nginx 监听 8080 端口，统一代理前端页面和后端 API，并支持 SSE 流式输出。

**使用本地 Ollama 模型**

如果已在宿主机运行 Ollama，Docker 容器会自动通过 `host.docker.internal:11434` 连接。

如需修改 Ollama 地址，在 `.env` 中覆盖：

```env
OLLAMA_BASE_URL=http://your-ollama-host:11434
```

---

## 配置 LLM 模型

应用启动后，进入 **Settings（设置）** 页面配置模型：

### 云端模型

| 提供商 | 模型 | 所需配置 |
|--------|------|---------|
| DeepSeek | `deepseek-v4-flash` / `deepseek-v4-pro | API Key（[申请地址](https://platform.deepseek.com)） |
| 阿里云百炼（Qwen） | `qwen-max` / `qwen-plus` / `qwen-turbo` | DashScope API Key（[申请地址](https://dashscope.console.aliyun.com)） |

> API Key 使用 AES-256-GCM 加密存储，不会明文落盘。

### 本地模型（Ollama）

1. 安装 Ollama：https://ollama.com
2. 拉取模型，例如：
   ```bash
   ollama pull qwen2.5:7b
   ```
3. 确保 Ollama 运行在 `http://localhost:11434`
4. 在设置页面会自动检测到可用模型

### 为不同功能指定模型

在设置页面可以分别为以下功能指定使用的模型：

- **编译模型**：将笔记编译为 Wiki 使用的模型（推荐能力强的模型，如 `qwen-max`、`deepseek-reasoner`）
- **对话模型**：AI 对话使用的模型（推荐响应快的模型，如 `deepseek-chat`、`qwen-plus`）

---

## 使用指南

### 第 1 步：写笔记（Memo Flow）

打开应用后，在 **Memo** 页面直接输入笔记内容：

- 支持 Markdown 格式（标题、列表、代码块等）
- 随手记录想法、学习内容、灵感，无需在意格式
- 笔记按时间倒序展示，支持全文搜索

### 第 2 步：编译为 Wiki（Compile）

积累了一些笔记后，点击 **Compile** 按钮：

- 系统会读取所有未编译的笔记
- 调用 LLM 自动整理为结构化 Wiki 页面
- 页面类型包括：概念（concept）、实体（entity）、对比（comparison）、综合（synthesis）、来源（source）
- 编译进度实时显示（SSE 流式推送）

### 第 3 步：浏览知识库（Wiki Hub）

编译完成后，在 **Wiki** 页面浏览整理好的知识：

- 按类型分类浏览
- 点击 `[[页面名]]` 链接在 Wiki 页面之间跳转
- 查看知识图谱可视化（力导向图展示页面间关系）
- 可手动编辑 Wiki 页面

### 第 4 步：AI 对话（Chat）

在 **Chat** 页面向 AI 提问：

- AI 自动以你的 Wiki 知识库为上下文回答
- 支持流式输出，实时看到回答生成过程
- 可以追问、讨论、深入某个知识点

---

## 环境变量说明

在 `backend/` 目录下创建 `.env` 文件进行配置：

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/cybernote.db` | 数据库连接字符串，生产环境可改为 PostgreSQL |
| `SECRET_KEY` | `change-me-to-a-random-string` | JWT 签名密钥，生产环境**必须**修改 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440`（24小时） | JWT Token 有效期 |
| `AUTH_MODE` | `none` | 认证模式：`none` 关闭认证（单用户本地），`jwt` 开启登录 |
| `ALLOWED_ORIGINS` | `*` | CORS 允许的前端域名，生产建议改为具体域名 |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama 服务地址 |

---

## 项目结构

```
Cyberdiary/
├── backend/                    # 后端（FastAPI）
│   ├── app/
│   │   ├── agents/             # 🆕 多智能体模块（Coordinator / Researcher / Integrator / Writer / Reviewer / Arbiter / Editor / Linker）
│   │   ├── api/
│   │   │   ├── v1/             # 路由层（memo, wiki, chat, compile, multi_agent_compile, model）
│   │   │   └── deps.py         # 依赖注入（DB session、认证）
│   │   ├── core/               # 配置、数据库连接、安全工具、🆕 熔断/重试/缓存/追踪
│   │   ├── models/             # SQLAlchemy ORM 模型（🆕 agent_state, multi_agent）
│   │   ├── schemas/            # Pydantic 请求/响应模型
│   │   ├── services/           # 业务逻辑层（🆕 multi_agent_graph, human_review_manager, evaluation_service）
│   │   ├── prompts/            # LLM Prompt 模板（🆕 multi_agent/ 含 8 个 Agent 提示词）
│   │   └── main.py             # 应用入口
│   ├── data/                   # 运行时数据（SQLite、Wiki .md 文件）
│   ├── tests/                  # 🆕 单元测试 + 集成测试
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── frontend/                   # 前端（Vue 3 + Vite）
│   ├── src/
│   │   ├── api/                # API 请求层（🆕 compile.ts）
│   │   ├── components/         # 通用组件（🆕 CompilationTracePanel, CompileResult, HumanReviewPanel）
│   │   ├── stores/             # Pinia 状态管理
│   │   ├── views/              # 页面组件（🆕 MultiAgentCompileView）
│   │   ├── styles/             # 全局样式与 CSS 变量
│   │   ├── router/             # 路由配置（🆕 /compile 页面）
│   │   ├── App.vue
│   │   └── main.ts
│   ├── Dockerfile
│   ├── package.json
│   └── vite.config.ts
├── docs/                       # 项目文档
│   ├── PRD.md                  # 产品需求文档
│   ├── DEV.md                  # 开发架构文档
│   ├── PHASES.md               # 开发阶段规划
│   ├── TESTING.md              # 测试指南
│   ├── manuals/                # 模块开发手册（多智能体、知识图谱、塔防游戏）
│   └── reviews/                # 代码审查报告
├── nginx/
│   └── nginx.conf              # Nginx 反向代理配置
├── docker-compose.yml
├── launcher.py                 # 🆕 交互式服务仪表盘（Q=退出 R=重启后端 F=重启前端）
├── start.bat                   # Windows 一键启动脚本（🆕 改用 launcher.py）
└── start.sh                    # Linux/macOS 一键启动脚本
```

---

## API 文档

后端启动后，访问以下地址查看自动生成的 API 文档：

| 文档 | 地址 |
|------|------|
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |

### 主要接口

| 模块 | 端点 | 说明 |
|------|------|------|
| Memo | `GET/POST /api/v1/memo` | 笔记增删改查 |
| Wiki | `GET /api/v1/wiki` | Wiki 页面查询 |
| Compile | `POST /api/v1/compile` / `POST /api/v1/compile/multi-agent` | 触发编译任务（SSE 流式），🆕 多智能体模式 |
| Chat | `POST /api/v1/chat` | AI 对话（SSE 流式） |
| Model | `GET/POST /api/v1/model` | 模型配置管理 |

---

## 常见问题

**Q: 启动后浏览器显示空白页？**

A: 请确认后端是否正常运行（访问 `http://localhost:8000/docs` 检查），然后查看浏览器控制台（F12）是否有报错。

**Q: 编译或对话时提示模型错误？**

A: 进入 Settings 页面检查 LLM 配置，确认 API Key 已填写且有效。如果使用 Ollama，确认 Ollama 服务正在运行。

**Q: 如何使用 PostgreSQL 替代 SQLite？**

A: 修改 `.env` 中的 `DATABASE_URL`：

```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/cybernote
```

然后安装 asyncpg：`pip install asyncpg`，重启后端即可，数据库表会自动创建。

**Q: Docker 部署后无法连接 Ollama？**

A: Docker 容器通过 `host.docker.internal` 访问宿主机服务。Linux 上需要在 `docker-compose.yml` 中添加：

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

**Q: 如何开启登录认证？**

A: 修改 `.env`：

```env
AUTH_MODE=jwt
SECRET_KEY=一个随机长字符串
```

重启后端，应用将要求用户注册/登录。

---

## License

MIT
