#!/bin/bash
# StockSentinel — 一键停止器（macOS 双击运行）
#
# 双击本文件停止所有服务：按端口（5173 前端 / 8000-8004 后端）精准结束进程。
# 只杀监听这些端口的进程，不影响其他程序。

set -e

# 颜色
G=$'\033[0;32m' Y=$'\033[1;33m' N=$'\033[0m'

echo ""
echo "============================================"
echo "  StockSentinel — 停止服务"
echo "============================================"
echo ""

KILLED=0

for port in 5173 8000 8001 8002 8003 8004; do
    PIDS="$(lsof -ti :$port 2>/dev/null || true)"
    if [ -n "$PIDS" ]; then
        echo "${Y}停止端口 $port 上的进程：$PIDS${N}"
        kill $PIDS 2>/dev/null || true
        KILLED=1
    fi
done

sleep 1

# 再补一轮（有些进程需要一点时间退出）
for port in 5173 8000 8001 8002 8003 8004; do
    PIDS="$(lsof -ti :$port 2>/dev/null || true)"
    if [ -n "$PIDS" ]; then
        echo "${Y}强制结束端口 $port：$PIDS${N}"
        kill -9 $PIDS 2>/dev/null || true
    fi
done

if [ "$KILLED" = "1" ]; then
    echo ""
    echo "${G}✅ 已停止所有 StockSentinel 服务。${N}"
else
    echo "${G}✅ 没有发现正在运行的 StockSentinel 服务。${N}"
fi
echo ""
read -r -p "按回车关闭此窗口..." _
