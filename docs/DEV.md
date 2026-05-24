# 赛博笔记（CyberNote）技术开发文档

> 版本：v1.0 | 日期：2026-05-23 | 状态：草稿

---

## 一、技术选型

### 总体原则
- 选你已熟练掌握的技术，零学习成本优先
- 企业级生产标准：有完善的错误处理、日志、测试覆盖
- 前后端严格分离，通过 OpenAPI 规范对接

### 技术栈总览

| 层次 | 技术 | 版本 | 选型理由 |
|------|------|------|---------|
| 前端框架 | Vue 3 + Vite | ^3.4 / ^5.2 | 已熟练，生态成熟 |
| 前端状态管理 | Pinia | ^2.1 | Vue 官方推荐，TypeScript 支持好 |
| 前端 UI | 自定义 CSS（极简风） | — | 避免 UI 库引入冗余样式 |
| Markdown 编辑器 | CodeMirror 6 | ^6.0 | 轻量、高度可定制 |
| Markdown 渲染 | markdown-it + highlight.js | — | 支持 front matter / 双向链接扩展 |
| 知识图谱 | force-graph | ^1.43 | 轻量、WebGL 加速，100+ 节点流畅 |
| 后端框架 | Python FastAPI | ^0.111 | 你的主力后端，SSE 原生支持 |
| 异步任务 | asyncio + APScheduler | — | 编译任务队列，定时触发 |
| 数据库（开发） | SQLite（aiosqlite） | — | 零配置，文件即数据库 |
| 数据库（生产） | PostgreSQL 15 + asyncpg | — | 与 SQLite 共用同一 ORM |
| ORM | SQLAlchemy 2.0（async） | ^2.0 | 统一 SQLite / PG 切换 |
| 认证 | python-jose (JWT) + bcrypt | — | 标准 JWT 实现 |
| LLM 统一接口 | LiteLLM | ^1.40 | 一套 API 同时接 DeepSeek / Qwen / Ollama |
| 加密 | cryptography (AES-256-GCM) | — | API Key 加密存储 |
| 容器化 | Docker + Docker Compose | — | 前后端一键部署 |
| 反向代理 | Nginx | latest | 静态文件托管 + API 代理 |

---

## 二、系统架构

```
┌──────────────────────────────────────────────────────────┐
│                    Browser / Mobile PWA                   │
│                    Vue 3 + Vite SPA                       │
│    Memo Flow │ Wiki Hub │ Chat │ Model Hub │ Settings     │
└───────────────────────┬──────────────────────────────────┘
                        │ HTTP / SSE (OpenAPI)
┌───────────────────────▼──────────────────────────────────┐
│                   FastAPI Backend                         │
│                                                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │
│  │  Memo    │ │  Wiki    │ │  Chat    │ │  Compile   │  │
│  │  Router  │ │  Router  │ │  Router  │ │  Engine    │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬──────┘  │
│       └────────────┴────────────┴─────────────┘          │
│                         │                                 │
│  ┌──────────────────────▼─────────────────────────────┐  │
│  │             Service Layer                          │  │
│  │  MemoService │ WikiService │ LLMService │ AuthSvc  │  │
│  └──────────────────────┬─────────────────────────────┘  │
│                         │                                 │
│  ┌──────────────────────▼─────────────────────────────┐  │
│  │             Data Layer                             │  │
│  │  SQLAlchemy ORM  │  File Storage (wiki/*.md)       │  │
│  └──────────────────────┬─────────────────────────────┘  │
│                         │                                 │
│              SQLite (dev) / PostgreSQL (prod)             │
└──────────────────────────────────────────────────────────┘
                        │
         ┌──────────────┴─────────────┐
         │         LLM Layer          │
         │  LiteLLM Router             │
         │  ├── DeepSeek API           │
         │  ├── 阿里云百炼 API          │
         │  └── Ollama (localhost)     │
         └────────────────────────────┘
```

---

## 三、目录结构

```
cybernote/
├── frontend/                    # Vue 3 前端
│   ├── src/
│   │   ├── api/                 # axios 封装，按模块分文件
│   │   │   ├── memo.ts
│   │   │   ├── wiki.ts
│   │   │   ├── chat.ts
│   │   │   └── model.ts
│   │   ├── components/          # 公共组件
│   │   │   ├── MarkdownEditor.vue
│   │   │   ├── MarkdownRenderer.vue
│   │   │   ├── ChatWindow.vue
│   │   │   └── ForceGraph.vue
│   │   ├── views/               # 页面级组件
│   │   │   ├── MemoFlow.vue
│   │   │   ├── WikiHub.vue
│   │   │   ├── WikiPage.vue
│   │   │   ├── ChatView.vue
│   │   │   └── Settings.vue
│   │   ├── stores/              # Pinia 状态
│   │   │   ├── memo.ts
│   │   │   ├── wiki.ts
│   │   │   ├── chat.ts
│   │   │   └── settings.ts
│   │   ├── router/              # Vue Router
│   │   │   └── index.ts
│   │   ├── styles/              # 全局样式
│   │   │   ├── variables.css
│   │   │   └── global.css
│   │   ├── App.vue
│   │   └── main.ts
│   ├── public/
│   │   └── manifest.json        # PWA manifest
│   ├── index.html
│   ├── vite.config.ts
│   └── package.json
│
├── backend/                     # FastAPI 后端
│   ├── app/
│   │   ├── api/                 # 路由层
│   │   │   ├── v1/
│   │   │   │   ├── memo.py
│   │   │   │   ├── wiki.py
│   │   │   │   ├── chat.py
│   │   │   │   ├── compile.py
│   │   │   │   ├── model.py
│   │   │   │   └── auth.py
│   │   │   └── deps.py          # 依赖注入（db session, current_user 等）
│   │   ├── services/            # 业务逻辑层
│   │   │   ├── memo_service.py
│   │   │   ├── wiki_service.py
│   │   │   ├── chat_service.py
│   │   │   ├── compile_service.py
│   │   │   └── llm_service.py   # LiteLLM 统一封装
│   │   ├── models/              # SQLAlchemy ORM 模型
│   │   │   ├── memo.py
│   │   │   ├── wiki.py
│   │   │   ├── chat.py
│   │   │   └── user.py
│   │   ├── schemas/             # Pydantic 请求/响应模型
│   │   │   ├── memo.py
│   │   │   ├── wiki.py
│   │   │   ├── chat.py
│   │   │   └── compile.py
│   │   ├── core/
│   │   │   ├── config.py        # 环境变量配置（pydantic-settings）
│   │   │   ├── security.py      # JWT / AES 加密工具
│   │   │   ├── database.py      # SQLAlchemy engine / session
│   │   │   └── scheduler.py     # APScheduler 定时编译任务
│   │   ├── prompts/             # Prompt 模板
│   │   │   ├── compile_system.md
│   │   │   ├── compile_user.md
│   │   │   └── chat_system.md
│   │   └── main.py              # FastAPI 应用入口
│   ├── data/
│   │   ├── cybernote.db         # SQLite（开发用）
│   │   └── wiki/                # 编译后的 Markdown 文件（与数据库同步）
│   ├── tests/                   # pytest 测试
│   │   ├── test_memo.py
│   │   ├── test_wiki.py
│   │   └── test_compile.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
├── nginx/
│   └── nginx.conf
├── docker-compose.yml
├── docker-compose.prod.yml
└── docs/
    ├── PRD.md                   # 产品需求文档（本文档）
    └── DEV.md                   # 技术开发文档（本文档）
```

---

## 四、数据库设计

### 4.1 memos 表（笔记）
```sql
CREATE TABLE memos (
    id          TEXT PRIMARY KEY,           -- UUID v4
    content     TEXT NOT NULL,              -- Markdown 原文
    tags        TEXT DEFAULT '[]',          -- JSON array of strings
    memo_type   TEXT DEFAULT 'note',        -- note | idea | reference | log
    source_url  TEXT,                       -- 可选来源链接
    compiled    BOOLEAN DEFAULT FALSE,      -- 是否已编译进 Wiki
    archived    BOOLEAN DEFAULT FALSE,      -- 是否已归档
    pinned      BOOLEAN DEFAULT FALSE,      -- 是否置顶
    created_at  DATETIME NOT NULL,
    updated_at  DATETIME NOT NULL
);
CREATE INDEX idx_memos_created_at ON memos(created_at DESC);
CREATE INDEX idx_memos_compiled ON memos(compiled);
-- FTS5 全文索引
CREATE VIRTUAL TABLE memos_fts USING fts5(
    content, tags, content=memos, content_rowid=rowid
);
```

### 4.2 wiki_pages 表（Wiki 页面）
```sql
CREATE TABLE wiki_pages (
    id          TEXT PRIMARY KEY,           -- UUID v4
    slug        TEXT UNIQUE NOT NULL,       -- URL slug（e.g. "transformer-architecture"）
    title       TEXT NOT NULL,
    wiki_type   TEXT NOT NULL,              -- concept | entity | comparison | synthesis | source
    content     TEXT NOT NULL,              -- Markdown 正文（含 front matter）
    summary     TEXT,                       -- 一句话摘要
    tags        TEXT DEFAULT '[]',          -- JSON array
    file_path   TEXT,                       -- 对应本地 .md 文件路径
    source_memo_ids TEXT DEFAULT '[]',      -- 来源 memo id 列表（JSON array）
    version     INTEGER DEFAULT 1,
    created_at  DATETIME NOT NULL,
    updated_at  DATETIME NOT NULL
);
CREATE INDEX idx_wiki_slug ON wiki_pages(slug);
CREATE INDEX idx_wiki_type ON wiki_pages(wiki_type);
CREATE VIRTUAL TABLE wiki_fts USING fts5(
    title, content, summary, content=wiki_pages, content_rowid=rowid
);
```

### 4.3 wiki_links 表（双向链接关系）
```sql
CREATE TABLE wiki_links (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    from_slug   TEXT NOT NULL,              -- 来源页面 slug
    to_slug     TEXT NOT NULL,              -- 目标页面 slug
    UNIQUE(from_slug, to_slug)
);
```

### 4.4 compile_jobs 表（编译任务）
```sql
CREATE TABLE compile_jobs (
    id          TEXT PRIMARY KEY,           -- UUID v4
    status      TEXT DEFAULT 'pending',     -- pending | running | done | failed
    memo_ids    TEXT NOT NULL,              -- JSON array of memo ids
    model_id    TEXT NOT NULL,              -- 使用的模型 ID
    result_summary TEXT,                    -- 编译结果摘要
    error_msg   TEXT,                       -- 失败原因
    started_at  DATETIME,
    finished_at DATETIME,
    created_at  DATETIME NOT NULL
);
```

### 4.5 conversations 表（对话历史）
```sql
CREATE TABLE conversations (
    id          TEXT PRIMARY KEY,           -- UUID v4
    title       TEXT NOT NULL DEFAULT '新对话',
    model_id    TEXT NOT NULL,
    created_at  DATETIME NOT NULL,
    updated_at  DATETIME NOT NULL
);

CREATE TABLE messages (
    id          TEXT PRIMARY KEY,           -- UUID v4
    conv_id     TEXT NOT NULL REFERENCES conversations(id),
    role        TEXT NOT NULL,              -- user | assistant | system
    content     TEXT NOT NULL,
    created_at  DATETIME NOT NULL
);
CREATE INDEX idx_messages_conv ON messages(conv_id, created_at);
```

### 4.6 settings 表（系统设置）
```sql
CREATE TABLE settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,              -- JSON 序列化值
    updated_at  DATETIME NOT NULL
);
-- 重要 key 示例：
-- "models" → [{id, provider, api_key_enc, endpoint, enabled}, ...]
-- "default_compile_model" → "deepseek-chat"
-- "default_chat_model" → "deepseek-chat"
-- "compile_cron" → "0 2 * * *"（每天凌晨2点）
```

---

## 五、API 设计

### 5.1 基础规范
- Base URL：`/api/v1`
- 认证：`Authorization: Bearer <JWT>`（单用户本地模式可关闭）
- 统一响应格式：
```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```
- 错误码：`400` 参数错误，`401` 未认证，`404` 资源不存在，`500` 服务器错误

### 5.2 Memo 接口
```
POST   /api/v1/memos              创建笔记
GET    /api/v1/memos              查询笔记列表（分页、筛选）
GET    /api/v1/memos/{id}         获取单条笔记
PATCH  /api/v1/memos/{id}         更新笔记
DELETE /api/v1/memos/{id}         软删除笔记
GET    /api/v1/memos/search       全文搜索（?q=关键词）
```

### 5.3 Wiki 接口
```
GET    /api/v1/wiki               Wiki 列表（分页、按类型筛选）
GET    /api/v1/wiki/{slug}        获取单个 Wiki 页面
PUT    /api/v1/wiki/{slug}        手动编辑 Wiki 页面
GET    /api/v1/wiki/search        全文搜索
GET    /api/v1/wiki/graph         知识图谱数据（nodes + edges）
GET    /api/v1/wiki/backlinks/{slug}  获取反链
```

### 5.4 编译接口
```
POST   /api/v1/compile/trigger    手动触发编译
GET    /api/v1/compile/jobs       查询编译任务列表
GET    /api/v1/compile/jobs/{id}  查询单个任务状态
GET    /api/v1/compile/jobs/{id}/stream  SSE 实时进度流
```

### 5.5 Chat 接口
```
GET    /api/v1/chat/conversations       会话列表
POST   /api/v1/chat/conversations       新建会话
DELETE /api/v1/chat/conversations/{id}  删除会话
GET    /api/v1/chat/conversations/{id}/messages  历史消息
POST   /api/v1/chat/stream              SSE 流式对话（返回 text/event-stream）
```

### 5.6 Model 接口
```
GET    /api/v1/models             获取所有模型配置
POST   /api/v1/models             添加模型
PUT    /api/v1/models/{id}        更新模型配置
DELETE /api/v1/models/{id}        删除模型
POST   /api/v1/models/{id}/test   测试模型连接
GET    /api/v1/models/ollama/list 探测本地 Ollama 可用模型
```

---

## 六、LLM 集成设计

### 6.1 LiteLLM 路由配置
```python
# backend/app/services/llm_service.py
import litellm

PROVIDER_MAP = {
    "deepseek": {
        "model_prefix": "deepseek/",
        "api_base": "https://api.deepseek.com",
    },
    "qwen": {
        "model_prefix": "openai/",
        "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    "ollama": {
        "model_prefix": "ollama/",
        "api_base": "http://localhost:11434",
    }
}

async def chat_completion(model_id: str, messages: list, stream: bool = False):
    """统一调用入口"""
    model_config = await get_model_config(model_id)
    api_key = decrypt_api_key(model_config.api_key_enc)
    return await litellm.acompletion(
        model=model_config.litellm_model,
        messages=messages,
        api_key=api_key,
        api_base=model_config.api_base,
        stream=stream,
    )
```

### 6.2 Karpathy Wiki 编译 Prompt

**系统 Prompt（compile_system.md）：**
```markdown
你是一个知识编译助手。你的任务是将用户提供的原始笔记编译为结构化的 Wiki 页面。

## 输出要求
- 每个 Wiki 页面必须是完整的 Markdown 文档
- 必须包含 YAML front matter
- 必须遵循 TheSchema 规范
- 使用 [[链接名]] 语法标注与其他概念的关联
- 输出中文（除代码外）

## TheSchema 规范（front matter 模板）
\`\`\`yaml
---
title: 页面标题
type: concept | entity | comparison | synthesis | source
tags: [标签1, 标签2]
summary: 一句话说明这个页面的核心内容
sources: [memo_001, memo_002]
updated: YYYY-MM-DD
---
\`\`\`

## 页面类型说明
- concept：抽象概念（如"反向传播"、"注意力机制"）
- entity：具体实体（如"FastAPI 框架"、"赛博日记项目"）
- comparison：对比分析（如"RAG vs Wiki 模式"）
- synthesis：综合总结（如"2026年5月学习回顾"）
- source：原始资料整理
```

**用户 Prompt（compile_user.md）：**
```markdown
以下是需要编译的原始笔记（共 {memo_count} 条）：

{memo_content}

请将以上笔记编译为结构化 Wiki 页面。
规则：
1. 相关主题合并为一个页面，不要机械地一条笔记对应一个页面
2. 每个页面聚焦一个清晰的主题
3. 输出格式：每个 Wiki 页面用 === 分隔
4. 尽量保留笔记的原始观点，不要过度归纳导致信息丢失

开始编译：
```

### 6.3 Chat 上下文注入策略

不使用向量检索（RAG），而是直接注入 Wiki 摘要：

```python
async def build_chat_context(conv_id: str) -> str:
    """构建对话系统提示词，注入 Wiki 知识库摘要"""
    wiki_pages = await get_wiki_summaries(limit=50)  # 取最近50条摘要
    
    wiki_context = "\n".join([
        f"- **{p.title}** ({p.wiki_type}): {p.summary}"
        for p in wiki_pages
    ])
    
    return f"""你是用户的个人知识助手，代号「赛博龙虾」。
    
## 用户的知识库摘要
{wiki_context}

回答时优先引用知识库中的内容。如果用户的问题与知识库无关，正常回答即可。
用中文回答，语气自然，不要机器腔。"""
```

---

## 七、前端核心实现

### 7.1 路由设计
```typescript
// frontend/src/router/index.ts
const routes = [
  { path: '/', redirect: '/memos' },
  { path: '/memos', component: MemoFlow },
  { path: '/wiki', component: WikiHub },
  { path: '/wiki/:slug', component: WikiPage },
  { path: '/chat', component: ChatView },
  { path: '/settings', component: Settings },
  // 扩展模块插槽（后期新增）
  // { path: '/jobs', component: JobModule },
]
```

### 7.2 SSE 流式输出处理
```typescript
// frontend/src/api/chat.ts
export async function* chatStream(messages: Message[], modelId: string) {
  const response = await fetch('/api/v1/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, model_id: modelId }),
  })
  
  const reader = response.body!.getReader()
  const decoder = new TextDecoder()
  
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const chunk = decoder.decode(value)
    for (const line of chunk.split('\n')) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6))
        if (data.content) yield data.content
      }
    }
  }
}
```

### 7.3 双向链接解析
```typescript
// markdown-it 插件：解析 [[链接名]] 语法
function wikiLinkPlugin(md: MarkdownIt) {
  md.core.ruler.push('wiki_links', (state) => {
    for (const token of state.tokens) {
      if (token.type === 'inline' && token.children) {
        token.children = parseWikiLinks(token.children)
      }
    }
  })
}

function parseWikiLinks(tokens: Token[]): Token[] {
  // 将 [[页面名]] 替换为 <a href="/wiki/{slug}">页面名</a>
  // ...
}
```

---

## 八、部署方案

### 8.1 开发环境
```bash
# 启动后端（Python 虚拟环境）
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 启动前端
cd frontend
npm install
npm run dev  # 默认 http://localhost:5173
```

### 8.2 docker-compose.yml（生产）
```yaml
version: '3.9'
services:
  backend:
    build: ./backend
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/cybernote
      - SECRET_KEY=${SECRET_KEY}
      - OLLAMA_BASE_URL=http://host.docker.internal:11434
    volumes:
      - ./data/wiki:/app/data/wiki
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy

  frontend:
    build: ./frontend
    ports:
      - "80:80"
    depends_on:
      - backend

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: cybernote
      POSTGRES_USER: user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user"]
      interval: 5s
      timeout: 5s
      retries: 5

  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf
    ports:
      - "8080:80"
    depends_on:
      - frontend
      - backend

volumes:
  pgdata:
```

### 8.3 nginx.conf
```nginx
server {
    listen 80;
    
    # 前端静态文件
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }
    
    # API 反向代理
    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        
        # SSE 支持
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        chunked_transfer_encoding on;
    }
}
```

---

## 九、开发阶段规划

### Phase 1：核心骨架（预计 2 周）
- [ ] 项目初始化（前后端脚手架、Docker 配置）
- [ ] 数据库建表（SQLAlchemy async）
- [ ] Memo CRUD（接口 + 前端时间流页面）
- [ ] 基础模型管理（支持 DeepSeek + Ollama）
- [ ] AI 对话（单会话流式输出）

### Phase 2：Wiki 核心（预计 2 周）
- [ ] LLM 编译引擎（Prompt 设计 + 异步任务）
- [ ] Wiki CRUD（接口 + 前端 Wiki Hub 页面）
- [ ] Wiki 页面双向链接解析
- [ ] 知识图谱可视化

### Phase 3：体验打磨（预计 1 周）
- [ ] 阿里云百炼接入
- [ ] PWA 配置（manifest + service worker）
- [ ] 移动端响应式适配
- [ ] Docker Compose 生产部署验证

### Phase 4：扩展模块（后期）
- [ ] 求职模块（Plugin Slot 示例）
- [ ] 定时编译（APScheduler + 前端 Cron 配置）
- [ ] Wiki 版本历史

---

## 十、扩展模块接入规范

后期新增功能模块（如求职模块）需遵循：

**后端**：在 `backend/app/api/v1/` 新建路由文件，在 `main.py` 中 `include_router` 挂载即可，无需修改其他代码。

**前端**：在 `frontend/src/views/` 新建页面组件，在 `router/index.ts` 新增路由条目，在 `App.vue` 导航中新增入口。

模块间共享：统一使用 `useSettingsStore()` 获取模型配置，统一使用 `chatStream()` 调用 LLM，不重复实现。
