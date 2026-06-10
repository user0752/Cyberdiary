# CyberNote Code Review — 修复报告

> 审查时间: 2026-06-10 | 总问题数: 14 → 已修复: 14

---

## 🔴 阻断级修复 (3项)

### 1. 全局异常处理器不再误吞 HTTPException
- **文件**: `backend/app/main.py`
- **修改**: 新增 `StarletteHTTPException` 专用 handler，保留 status code；通用 Exception handler 记录日志但返回无泄漏的 500 消息
- **验证**: 
  - `HTTPException` handler 正确注册 ✅
  - `Exception` handler 正确注册 ✅

### 2. AES-256-GCM 密钥派生升级为 PBKDF2-HMAC-SHA256
- **文件**: `backend/app/core/security.py`
- **修改**: `encrypt_api_key()` 使用 salt(16) + 600k PBKDF2 迭代派生密钥
- **兼容性**: `decrypt_api_key()` 支持解密旧格式 (零值填充) 和新格式 (salt+PBKDF2)
- **验证**: 加解密往返测试通过 ✅

### 3. SECRET_KEY 强制校验
- **文件**: `backend/app/core/config.py`
- **修改**: 新增 `field_validator`，拒绝默认值或长度 < 32 的密钥
- **配套**:
  - `docker-compose.yml`: `${SECRET_KEY:? ...}` 要求必须设置
  - `backend/.env`: 已生成强随机密钥
  - `backend/.env.example`: 新增配置模板

---

## 🟡 高风险修复 (4项)

### 4. 移除 core/database.py 中的重复 get_db()
- **文件**: `backend/app/core/database.py`
- 仅保留 `api/deps.py` 中的唯一版本
- **验证**: import 确认无 get_db 残留 ✅

### 5. 后台编译任务生命周期管理
- **文件**: `backend/app/main.py` + `backend/app/services/compile_service.py`
- `lifespan()` 新增 app.state.background_tasks 管理，shutdown 时优雅取消
- `trigger_compile()` 将 task 注册到 app.state
- `_do_compile` 的裸 `except Exception: pass` 改为 `logger.exception()`

### 6. FTS5 搜索异常不再静默吞没
- **文件**: `backend/app/services/memo_service.py`, `backend/app/services/wiki_service.py`
- 改为 `logger.warning()` 记录回退原因

### 7. Wiki 删除顺序: 文件删除移到 DB 提交之后
- **文件**: `backend/app/services/wiki_service.py`
- `os.remove()` 移至 `await db.flush()` 之后，避免 DB 回滚导致文件丢失

---

## 🟢 中低风险修复 (4项)

### 8. 提取共享 markdown 工具模块
- **新文件**: `backend/app/utils/markdown.py` — `slugify()`, `parse_front_matter()`, `extract_wiki_links()`
- `compile_service.py` 和 `wiki_service.py` 改为从 `app.utils.markdown` 导入
- 消除循环依赖风险 ✅

### 9. _compile_progress 并发安全
- **文件**: `backend/app/services/compile_service.py`
- 新增 `_safe_progress_update()` 使用 `asyncio.Lock`

### 10. 新增性能索引
- **文件**: `backend/app/core/database.py`
- `init_db()` 新增 `idx_memos_compiled_archived` 和 `idx_wiki_pages_type_tags`

### 11. 前端统一 API 客户端
- **新文件**: `frontend/src/api/client.ts` — 统一 axios 实例，包含响应拦截器
- `frontend/src/api/chat.ts`: 改用统一 client + SSE 错误时读取响应体
- `frontend/src/stores/settings.ts`: 改用统一 client

### 12. 内部错误信息不再暴露
- `global_exception_handler` 返回 `"Internal server error"` 而非 `str(exc)`
- 完整错误通过 `logger.exception()` 记录

### 13. 重新生成 .env 密钥
- `backend/.env`: `SECRET_KEY` 已更新为强随机值

### 14. .env.example 文档化
- **新文件**: `backend/.env.example`

---

## 验证结果

| 检查项 | 状态 |
|--------|------|
| Python 所有模块 import | ✅ 通过 |
| get_db 重复定义消除 | ✅ 确认 |
| AES 加解密往返 | ✅ 通过 |
| FastAPI app 启动 | ✅ 通过 |
| HTTPException handler | ✅ 注册 |
| Exception handler | ✅ 注册 |
| 39 个路由 | ✅ 正常 |

---

## 遗留建议

| 建议 | 优先级 | 说明 |
|------|--------|------|
| 编写测试 | 🔴 高 | 至少 AES + Memo CRUD + 编译解析器的单元测试 |
| 前端剩余 API 模块迁移 | 🟡 中 | `memo.ts`、`wiki.ts`、`game.ts` 迁移到 `client.ts` |
| Docker 前端生产构建 | 🟡 中 | nginx 应直接 serve 前端 dist，而非代理到宿主机 |
| Pydantic v2 `pattern` → `pattern` 兼容 | 🟢 低 | `schemas/memo.py` 中的 `pattern=` 在新版可能弃用 |
