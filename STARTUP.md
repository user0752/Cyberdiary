# 一键启动说明

## Windows 用户

双击运行 `start.bat` 或在命令行执行：

```bash
start.bat
```

## Linux / macOS 用户

在终端执行：

```bash
./start.sh
```

## 启动后

- **前端界面**: http://localhost:5173
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs

## 首次运行

脚本会自动：
1. 创建 Python 虚拟环境（`backend/venv`）
2. 安装后端依赖（`pip install -r requirements.txt`）
3. 安装前端依赖（`npm install`）

## 停止服务

**Windows**:
- 关闭对应的命令行窗口
- 或在任务管理器中结束 `uvicorn` 和 `node` 进程

**Linux / macOS**:
- 在启动脚本的终端按 `Ctrl+C`

## 环境要求

- Python 3.10+
- Node.js 18+
- npm 或 yarn
