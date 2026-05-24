# 赛博笔记（CyberNote）开发阶段规划

> 版本：v1.0 | 日期：2026-05-23 | 总工期：6周

---

## Phase 1：核心骨架 ✅ 已完成

**时间**：2026-05-23 | **状态**：Done

### 完成内容

| 模块 | 交付物 |
|------|--------|
| 项目骨架 | 后端 FastAPI + 前端 Vue3+Vite+TS 完整目录结构 |
| 数据库 | 8 张 ORM 表 + 2 个 FTS5 全文索引 + 3 个同步触发器 |
| Memo CRUD | 7 个 REST 端点（创建/列表/详情/更新/软删除/搜索），FTS5 全文检索 |
| 前端 MemoFlow | 时间流页面：日期分组、Markdown 编辑/渲染、置顶/归档/标签 |
| 模型管理 | 6 个 API 端点：CRUD + 连接测试 + Ollama 探测 |
| 前端 Settings | 模型添加/编辑/测试面板，API Key AES-256 加密 |
| AI 对话 | SSE 流式对话，多会话管理，上下文注入架构 |
| 前端 ChatView | 会话列表 + 流式打字机效果聊天窗 |
| 部署配置 | Docker Compose + Nginx + Dockerfile ×2 |

### 测试方法

```bash
# 终端 1：启动后端
cd backend
python -m uvicorn app.main:app --reload --port 8000

# 终端 2：启动前端
cd frontend
npm run dev

# 浏览器访问 http://localhost:5173
```

**功能验证清单：**

1. **笔记时间流** - 点击"+ 新建笔记"，写 Markdown 内容，添加标签，保存后在时间流中按日期分组显示
2. **笔记搜索** - 在搜索框输入关键词，FTS5 全文检索返回匹配笔记
3. **笔记操作** - 置顶、编辑、归档、删除均正常工作
4. **AI 对话** - 切换到"对话"页，配置模型后可以流式对话（需先添加 API Key）
5. **模型管理** - 在"设置"页添加 DeepSeek/Qwen/Ollama 模型，测试连接
6. **API 验证** - 访问 `http://localhost:8000/docs` 查看 Swagger 文档，直接测试所有接口

---

## Phase 2：Wiki 核心（预计 2 周）

**目标**：实现 Karpathy Wiki 编译范式的核心循环

### 2.1 LLM 编译引擎（3天）

**后端：**
- `compile_service.py` — 完整编译逻辑
  - 读取 `compiled=false` 的笔记
  - 组装 Prompt（加载 `compile_system.md` + `compile_user.md`）
  - 调用 LLM API 批量编译
  - 解析 LLM 输出（每个 Wiki 页面用 `===` 分隔）
  - 提取 front matter（title, type, tags, summary, sources）
  - 写入 `wiki_pages` 表 + 本地 `wiki/*.md` 文件
  - 标记来源笔记 `compiled=true`
- **增量编译** — 仅处理新增/修改的笔记
- **编译任务队列** — `compile_jobs` 表跟踪状态，异步执行
- API：
  - `POST /api/v1/compile/trigger` — 手动触发（支持指定 memo_ids）
  - `GET /api/v1/compile/jobs` — 任务列表
  - `GET /api/v1/compile/jobs/{id}` — 单个任务状态
  - `GET /api/v1/compile/jobs/{id}/stream` — SSE 实时进度流

**前端：**
- 编译触发按钮（在 MemoFlow 顶部栏）
- 编译进度弹窗（SSE 实时更新：读取笔记 → 调用 LLM → 写入 Wiki）
- 编译历史列表

### 2.2 Wiki Hub 页面（3天）

**后端：**
- `wiki_service.py` — Wiki CRUD
- API：
  - `GET /api/v1/wiki` — Wiki 列表（分页，按 type/tag 筛选）
  - `GET /api/v1/wiki/{slug}` — 单个 Wiki 页面
  - `PUT /api/v1/wiki/{slug}` — 手动编辑（版本号 +1）
  - `GET /api/v1/wiki/search` — 全文搜索（wiki_fts）
  - `GET /api/v1/wiki/backlinks/{slug}` — 反链查询
  - `GET /api/v1/wiki/graph` — 知识图谱数据（nodes + edges）

**前端 (`WikiHub.vue`)：**
- Wiki 列表页：左侧「领域/概念/实体/对比/来源」五类筛选 + 右侧卡片网格
- 每张卡片：标题、类型标签、摘要、来源笔记数
- 搜索框 + 排序（最新/最多引用）

**前端 (`WikiPage.vue`)：**
- 完整 Wiki 页面渲染（Markdown with front matter）
- 双向链接高亮：`[[页面名]]` 渲染为可点击链接
- 反链区域：列出所有链接到当前页面的 Wiki 页面
- 来源笔记区域：列出编译来源的原始笔记
- 编辑按钮 → Markdown 编辑器 → 保存（版本号递增）

### 2.3 双向链接解析（1天）

**markdown-it 插件：**
- 扩展 `MarkdownRenderer`，解析 `[[链接名]]` 语法
- 链接名 → slug 映射（中文转拼音或保持原名）
- 渲染为 `<router-link to="/wiki/{slug}">`
- 编写时自动提取链接关系，写入 `wiki_links` 表

**后端链接维护：**
- 保存 Wiki 页面时自动扫描 `[[...]]`，更新 `wiki_links`
- 反链查询：`SELECT from_slug, title FROM wiki_links JOIN wiki_pages ON from_slug = slug WHERE to_slug = ?`

### 2.4 知识图谱可视化（2天）

**前端 (`components/ForceGraph.vue`)：**
- 使用 `force-graph` 库（WebGL 加速）
- 节点 = Wiki 页面，大小 = 引用数，颜色 = wiki_type
- 边 = 双向链接
- 交互：拖拽、缩放、点击节点跳转 Wiki 页面
- 性能目标：100 节点不卡顿

**API 数据格式：**
```json
{
  "nodes": [{"id": "slug", "label": "title", "type": "concept"}],
  "edges": [{"source": "from-slug", "target": "to-slug"}]
}
```

### 2.5 Chat 上下文注入（1天）

**增强 `chat_service.py`：**
- `build_chat_context()` 从 Wiki 表读取摘要注入 system prompt
- 支持 `@页面名` 语法：对话中引用具体 Wiki 页面，将其全文注入上下文
- Wiki 摘要限制 50 条，按更新时间倒序

### Phase 2 验收标准

| 功能 | 条件 |
|------|------|
| 编译引擎 | 5 条测试笔记 → 触发编译 → 生成 N 个 Wiki 页面（合并相关主题），格式符合 TheSchema |
| Wiki 浏览 | 五类分类筛选正常，双向链接可点击跳转 |
| 知识图谱 | 100 节点力导向图流畅渲染，节点点击跳转 Wiki 页面 |
| Chat 上下文 | 编译 Wiki 后，对话回答能引用 Wiki 知识库内容 |

---

## Phase 3：体验打磨（预计 1 周）

### 3.1 阿里云百炼接入（1天）

- LiteLLM 已验证支持 `openai/` 前缀 + DashScope compatible endpoint
- 前端设置页已有 Qwen 提供商选项
- 需补充：`qwen-vl` 视觉模型支持、百炼 API Key 申请引导

### 3.2 PWA 支持（1天）

- `public/manifest.json` — 应用名称、图标、启动 URL、主题色
- Service Worker — 缓存策略（stale-while-revalidate）、离线提示页
- 图标生成（192×192 + 512×512 PNG）
- `vite-plugin-pwa` 集成

### 3.3 移动端响应式适配（2天）

- **布局**：≤768px 时侧边栏收折为底部 TabBar
- **MemoFlow**：卡片全宽，编辑器全屏
- **ChatView**：会话列表收折，对话区全宽
- **WikiPage**：字体缩放，代码块横向滚动
- **触摸优化**：按钮最小 44×44px 点击区域，长按菜单

### 3.4 Docker 生产部署验证（1天）

- `docker-compose.prod.yml` — PostgreSQL + Nginx + 前后端
- 数据持久化验证（volume 挂载）
- 环境变量注入验证（SECRET_KEY、DB_PASSWORD）
- 健康检查配置

### Phase 3 验收标准

| 功能 | 条件 |
|------|------|
| 百炼接入 | 配置 Qwen API Key → 对话正常流式输出 |
| PWA | Chrome 访问 → 地址栏出现"安装"按钮 → 安装后离线可用 |
| 移动端 | iPhone 14 竖屏：笔记/Chat/Wiki/设置 核心功能可用 |
| 生产部署 | `docker compose -f docker-compose.prod.yml up` → 8080 端口所有功能正常 |

---

## Phase 4：扩展模块（后期）

### 4.1 定时编译（2天）

- **后端**：APScheduler 定时任务
  - Cron 配置存储在 `settings` 表（key: `compile_cron`）
  - 默认每天凌晨 2:00 自动编译未处理笔记
  - 前端设置页 Cron 表达式配置 UI（如："每天 2:00" → `0 2 * * *`）
- **前端**：Settings 页新增「定时编译」配置卡片

### 4.2 Wiki 版本历史（1天）

- 新增 `wiki_revisions` 表：
  ```sql
  CREATE TABLE wiki_revisions (
      id TEXT PRIMARY KEY,
      page_id TEXT NOT NULL REFERENCES wiki_pages(id),
      version INTEGER NOT NULL,
      content TEXT NOT NULL,
      created_at DATETIME NOT NULL
  );
  ```
- 每次编辑保存旧版本到 `wiki_revisions`
- 前端 WikiPage 增加「版本历史」侧面板，可对比/恢复

### 4.3 扩展模块示例：求职模块（1天）

**演示 Plugin Slot 架构：**

- **后端** `pluginRouter`：`backend/app/api/v1/jobs.py`
  - 独立的 Job 模型（公司、职位、状态、备注）
  - CRUD 端点
- **前端**：`frontend/src/views/JobTracker.vue`
  - 看板视图（投递/面试/Offer/拒绝）
  - 拖拽卡片改变状态
- 导航新增「求职」入口，不影响核心代码

### 4.4 更多扩展方向

- **数据导出** — 一键导出所有笔记为 Markdown zip，Wiki 为静态站点
- **多用户支持** — 启用 JWT 认证，多账号数据隔离
- **Webhook 集成** — 编译完成后通知（钉钉/飞书/企业微信）
- **Obsidian 双向同步** — 监听 `wiki/` 目录变化，自动同步到数据库

---

## 附录：技术 Roadmap 时间线

```
Week 1-2:  Phase 1 ✅ 核心骨架
  ├── 项目初始化 + 数据库
  ├── Memo CRUD + 前端时间流
  ├── 模型管理 + SSE 对话
  └── Docker 配置

Week 3-4:  Phase 2 🔜 Wiki 核心
  ├── LLM 编译引擎
  ├── Wiki Hub 页面 + 详情页
  ├── 双向链接 + 知识图谱
  └── Chat 上下文注入增强

Week 5:    Phase 3 🔜 体验打磨
  ├── 百炼接入 + PWA
  ├── 移动端适配
  └── 生产部署验证

Week 6+:   Phase 4 📋 扩展
  ├── 定时编译 + 版本历史
  ├── 求职模块示例
  └── 更多扩展...
```

---

## 附录：测试检查清单

### 每次开发完成后跑一遍

```bash
# 1. TypeScript 编译检查
cd frontend && npx vue-tsc --noEmit

# 2. 后端导入检查
cd backend && python -c "from app.main import app; print('OK')"

# 3. 数据库初始化
cd backend && python -c "
import asyncio
from app.core.database import init_db
asyncio.run(init_db())
print('DB OK')
"

# 4. 启动后端
cd backend && python -m uvicorn app.main:app --reload --port 8000

# 5. 启动前端
cd frontend && npm run dev

# 6. 浏览器测试
# - http://localhost:5173          前端页面
# - http://localhost:8000/docs     Swagger API 文档
# - http://localhost:8000/api/health  健康检查
```
