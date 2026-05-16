#!/bin/bash
# StockSentinel — 一键启动前后端
# 访问 http://localhost:5173 即可，API 自动代理到 :8000

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cleanup() {
    echo ""
    echo "Shutting down..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
    echo "Done."
}
trap cleanup EXIT INT TERM

echo "============================================"
echo "  StockSentinel — 回撤监控系统"
echo "============================================"
echo ""

# 启动后端（DEV_MODE 让 :8000 自动跳转到 :5173）
cd "$SCRIPT_DIR/backend"
DEV_MODE=true python3 main.py &
BACKEND_PID=$!

# 启动前端
cd "$SCRIPT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "  Backend  : http://localhost:8000  (API)"
echo "  Frontend : http://localhost:5173  (UI)"
echo ""
echo "  >>> 请访问 http://localhost:5173 <<<"
echo ""
echo "  Ctrl+C 停止所有服务"
echo ""

wait
