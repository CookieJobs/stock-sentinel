#!/bin/bash
# StockSentinel — 一键启动前后端
# 访问 http://localhost:5173 即可，API 自动代理到后端端口
#
# 端口配置：
# - 默认后端 8000
# - 端口冲突时自动 fallback 到 8001/8002/...
# - 用 BACKEND_PORT 环境变量可指定

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── 端口检测（自动 fallback） ──────────────────────
check_port() {
    local port=$1
    ! lsof -i ":$port" >/dev/null 2>&1
}

find_available_port() {
    local start=${1:-8000}
    for port in $start $((start+1)) $((start+2)) $((start+3)) $((start+4)); do
        if check_port $port; then
            echo $port
            return 0
        fi
    done
    return 1
}

# 1. 决定后端端口
REQUESTED_PORT=${BACKEND_PORT:-8000}
BACKEND_PORT=$(find_available_port $REQUESTED_PORT) || {
    echo "❌ 错误：8000-8004 端口都被占用，请手动指定："
    echo "   BACKEND_PORT=9000 ./start.sh"
    exit 1
}
if [ "$BACKEND_PORT" != "$REQUESTED_PORT" ]; then
    echo "⚠️  端口 $REQUESTED_PORT 被占用，自动改用 $BACKEND_PORT"
    echo "   （如需强制使用 $REQUESTED_PORT，先 kill 占用进程）"
    echo ""
fi
export BACKEND_PORT

# 2. 进程清理（Ctrl+C 时）
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
    echo "Done."
}
trap cleanup EXIT INT TERM

# 3. 启动
echo "============================================"
echo "  StockSentinel — 量化分析平台 v1.0"
echo "============================================"
echo ""

# 后端（DEV_MODE=true 让 :8000 跳转到 :5173）
cd "$SCRIPT_DIR/backend"
DEV_MODE=true PORT=$BACKEND_PORT python3 main.py &
BACKEND_PID=$!

# 等 2 秒确认启动成功
sleep 2
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "❌ 后端启动失败（请检查 $BACKEND_PORT 端口或日志）"
    exit 1
fi

# 前端（Vite proxy 读 BACKEND_PORT env）
cd "$SCRIPT_DIR/frontend"
BACKEND_PORT=$BACKEND_PORT npm run dev &
FRONTEND_PID=$!

sleep 2
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo "❌ 前端启动失败"
    exit 1
fi

echo "  Backend  : http://localhost:$BACKEND_PORT  (API)"
echo "  Frontend : http://localhost:5173  (UI)"
echo ""
echo "  >>> 请访问 http://localhost:5173 <<<"
echo ""
echo "  Ctrl+C 停止所有服务"
echo ""

wait
