# Phase 1 测试指南

> 快速验证 Phase 1 所有功能是否正常

---

## 启动服务

```bash
# 终端 1 - 后端
cd C:/Users/86175/Desktop/Cyberdiary/backend
python -m uvicorn app.main:app --reload --port 8000

# 终端 2 - 前端
cd C:/Users/86175/Desktop/Cyberdiary/frontend
npm run dev
```

浏览器打开 **http://localhost:5173**

---

## 功能测试清单

### 1. 笔记时间流（Memo Flow）

| 步骤 | 操作 | 预期结果 |
|------|------|---------|
| 1.1 | 点击 "+ 新建笔记" | 右侧滑出编辑器面板 |
| 1.2 | 输入 Markdown 内容 `# 测试笔记`，添加标签 `test, demo`，类型选「笔记」 | 内容可输入 |
| 1.3 | 点击「保存」 | 面板关闭，时间流出现新卡片，显示"笔记"标签和时间 |
| 1.4 | 点击卡片内容区域 | 重新打开编辑器，可修改保存 |
| 1.5 | 再次新建，类型选「想法」 | 卡片显示紫色"想法"标签 |
| 1.6 | 点击 📍 按钮 | 笔记置顶，卡片左侧出现蓝色边框 |
| 1.7 | 在搜索框输入关键词，回车 | 只显示匹配的笔记 |
| 1.8 | 点击搜索框旁的 ✕ | 清除搜索，恢复全部笔记 |
| 1.9 | 点击 📁 归档 | 笔记从列表消失 |
| 1.10 | 点击 🗑️ 删除 | 确认后笔记删除 |

### 2. AI 对话（Chat）

| 步骤 | 操作 | 预期结果 |
|------|------|---------|
| 2.1 | 左侧导航点击「对话」 | 进入聊天页面，左侧会话列表，右侧聊天区 |
| 2.2 | 点击 "+ 新对话" | 清空聊天区 |
| 2.3 | 输入消息，Enter 发送 | 消息出现在右侧 |
| **注** | 需先在设置页配置模型 API Key 才能收到 AI 回复 | — |

### 3. 设置 / 模型管理（Settings）

| 步骤 | 操作 | 预期结果 |
|------|------|---------|
| 3.1 | 左侧导航点击「设置」 | 进入设置页面 |
| 3.2 | 点击 "+ 添加模型" | 弹出添加模型对话框 |
| 3.3 | 选择「DeepSeek」，填入 `deepseek-chat`，输入 API Key | 表单正常 |
| 3.4 | 点击「保存」 | 模型出现在表格中 |
| 3.5 | 点击「测试」 | 显示 ✅ 连接成功 或 ❌ 错误信息 |
| 3.6 | 点击「探测 Ollama」 | 显示本地 Ollama 模型列表（如有安装） |

### 4. API 接口验证

浏览器打开 **http://localhost:8000/docs**，Swagger UI 测试：

```
POST   /api/v1/memos      → 创建笔记
GET    /api/v1/memos      → 笔记列表
GET    /api/v1/memos/search?q=关键词 → 全文搜索
GET    /api/v1/chat/conversations → 会话列表
POST   /api/v1/chat/stream → SSE 流式对话（需先配模型）
GET    /api/v1/models      → 模型列表
POST   /api/v1/models      → 添加模型
GET    /api/health         → {"status":"healthy"}
```

### 5. 自动化测试

```bash
cd backend
python -c "
import asyncio
from app.core.database import init_db, async_session
from app.services.memo_service import create_memo, list_memos, search_memos
from app.schemas.memo import MemoCreate

async def quick_test():
    await init_db()
    async with async_session() as db:
        m = await create_memo(db, MemoCreate(content='# Test', tags=['test']))
        items, total = await list_memos(db)
        results = await search_memos(db, 'Test')
        assert total > 0 and len(results) > 0
        print('Memo CRUD: OK')
        print(f'Database has {total} memos')

asyncio.run(quick_test())
"
```

---

## 常见问题

| 问题 | 解决 |
|------|------|
| `uvicorn` 命令找不到 | 用 `python -m uvicorn` 代替 |
| 前端 import 报错 | `cd frontend && npm install` |
| 数据库被锁 | 关闭正在运行的 uvicorn，或重启电脑 |
| 后端端口占用 | 换端口：`--port 8001` |
| API 返回 500 | 查看后端终端日志，检查 `.env` 配置 |
