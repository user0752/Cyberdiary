#!/bin/bash

# 设置 UTF-8 编码
export LANG=en_US.UTF-8

echo "========================================"
echo "  CyberNote 一键启动脚本"
echo "========================================"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未检测到 Python3，请先安装 Python 3.10+"
    exit 1
fi

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "[错误] 未检测到 Node.js，请先安装 Node.js 18+"
    exit 1
fi

echo "[信息] 正在启动后端服务..."
cd backend

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "[信息] 首次运行，正在创建 Python 虚拟环境..."
    python3 -m venv venv
    source venv/bin/activate
    echo "[信息] 正在安装后端依赖..."
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# 启动后端（后台运行）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

cd ..

echo "[信息] 正在启动前端服务..."
cd frontend

# 检查 node_modules
if [ ! -d "node_modules" ]; then
    echo "[信息] 首次运行，正在安装前端依赖..."
    npm install
fi

# 启动前端（后台运行）
npm run dev &
FRONTEND_PID=$!

cd ..

echo ""
echo "========================================"
echo "  启动完成！"
echo "========================================"
echo ""
echo "后端服务: http://localhost:8000"
echo "前端服务: http://localhost:5173"
echo "API 文档: http://localhost:8000/docs"
echo ""

# 等待 3 秒让服务启动
sleep 3

# 尝试打开浏览器
if command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:5173 &> /dev/null &
elif command -v open &> /dev/null; then
    open http://localhost:5173 &> /dev/null &
fi

echo ""
echo "[提示] 服务已在后台运行"
echo "[提示] 按 Ctrl+C 停止所有服务"
echo ""

# 捕获退出信号
trap "echo ''; echo '[信息] 正在停止服务...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

# 等待
wait
