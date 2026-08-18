#!/bin/bash
# StockSentinel — 一键启动器（macOS 双击运行）
#
# 双击本文件即可启动项目：自动检查环境 → 装缺失依赖 → 启动前后端 → 打开浏览器。
# 关闭弹出的终端窗口（或按 Ctrl+C）即停止所有服务。
#
# 提示：首次双击若被系统拦截，右键 →「打开」即可（macOS Gatekeeper）。

set -e

# 定位项目根目录（脚本自身所在目录）
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 双击 .command 时 PATH 可能不含 anaconda / node 等目录，显式补全
export PATH="/opt/anaconda3/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

# 颜色
G=$'\033[0;32m' Y=$'\033[1;33m' R=$'\033[0;31m' C=$'\033[0;36m' N=$'\033[0m'

echo ""
echo "============================================"
echo "  ${C}StockSentinel — 量化分析平台 v1.0${N}"
echo "============================================"
echo ""

# ── 1. 检查基础工具 ──────────────────────────────
for cmd in node npm python3 lsof; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "${R}❌ 缺少命令：$cmd${N}"
        echo "   请先安装后重试（Node.js 见 https://nodejs.org，Python 3 需带 fastapi/pandas）"
        echo ""
        read -r -p "按回车退出..." _
        exit 1
    fi
done
echo "${G}✓ 基础环境：node $(node -v) / $(python3 -V 2>&1)${N}"

# ── 2. 前端依赖（首次运行自动安装）─────────────────
if [ ! -d "frontend/node_modules" ]; then
    echo ""
    echo "${Y}首次运行：正在安装前端依赖（约 1 分钟，请稍候）...${N}"
    ( cd frontend && npm install )
fi

# ── 3. 后端关键依赖快检 ────────────────────────────
if ! python3 -c "import fastapi, uvicorn, pandas, dotenv" >/dev/null 2>&1; then
    echo ""
    echo "${Y}⚠️  后端依赖不完整（fastapi/uvicorn/pandas/dotenv）${N}"
    echo "   请手动安装： pip install fastapi uvicorn pandas python-dotenv requests"
    echo "   （backend/requirements.txt 当前为空，尚未固化清单）"
    echo ""
    sleep 4
fi

# ── 4. 已在运行？直接打开浏览器，不重复启动 ──────────
if lsof -i :5173 >/dev/null 2>&1; then
    echo ""
    echo "${G}✅ 前端已在运行（http://localhost:5173），直接打开浏览器。${N}"
    if [ "${STOCKSENTINEL_NO_BROWSER:-0}" != "1" ]; then
        open "http://localhost:5173"
    fi
    echo ""
    read -r -p "按回车关闭此窗口..." _
    exit 0
fi

# ── 5. 延迟自动打开浏览器（等服务就绪）─────────────
if [ "${STOCKSENTINEL_NO_BROWSER:-0}" != "1" ]; then
    ( sleep 7 && open "http://localhost:5173" ) &
fi

# ── 6. 启动（复用 start.sh 的端口 fallback + 清理）─
echo ""
echo "${G}启动中... 服务就绪后会自动打开浏览器。${N}"
echo "${Y}关闭此窗口（或 Ctrl+C）即可停止所有服务。${N}"
echo ""
exec ./start.sh
