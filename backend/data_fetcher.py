"""股票数据获取封装 - Finnhub API (美股) + 东方财富 (A股/港股)"""
import os
import json
import hashlib
import logging
import random
import time
import requests
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# 确保日志能输出到文件，方便诊断 API 问题
if not logger.handlers:
    _log_file = os.path.join(os.path.dirname(__file__), "data_fetcher.log")
    _fh = logging.FileHandler(_log_file)
    _fh.setLevel(logging.DEBUG)
    _fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(_fh)
    logger.setLevel(logging.DEBUG)

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"
# 东财用 http 而非 https：本机/运行环境对 push2/push2his 的 TLS 握手被重置
# （RemoteDisconnected），http 是实测可通的 workaround。
# ⚠️ 安全债：行情数据明文传输，待环境 TLS 问题查证后应改回 https（见 CHANGELOG 2026-08-15）。
EASTMONEY_QUOTE_URL = "http://push2.eastmoney.com/api/qt/stock/get"
EASTMONEY_KLINE_URL = "http://push2his.eastmoney.com/api/qt/stock/kline/get"

# 股票名称静态映射（API 兜底）
_NAME_MAP = {
    # A 股
    "000001": "平安银行", "000333": "美的集团", "000568": "泸州老窖",
    "000725": "京东方A", "000858": "五粮液", "002415": "海康威视",
    "002594": "比亚迪", "002714": "牧原股份", "300750": "宁德时代",
    "300760": "迈瑞医疗", "600030": "中信证券", "600036": "招商银行",
    "600276": "恒瑞医药", "600519": "贵州茅台", "600809": "山西汾酒",
    "600887": "伊利股份", "600900": "长江电力", "601012": "隆基绿能",
    "601318": "中国平安", "601888": "中国中免",
    # 港股
    "00005": "汇丰控股", "00020": "商汤-W", "00100": "MINIMAX-W",
    "00388": "香港交易所", "00700": "腾讯控股", "00941": "中国移动",
    "01024": "快手-W", "01211": "比亚迪股份", "01299": "友邦保险",
    "01810": "小米集团-W", "01818": "招金矿业", "02015": "理想汽车-W",
    "02269": "药明生物", "02318": "中国平安", "03690": "美团-W",
    "09618": "京东集团-SW", "09626": "哔哩哔哩-W", "09633": "农夫山泉",
    "09888": "百度集团-SW", "09988": "阿里巴巴-SW", "09999": "网易-S",
}

# 显式禁用代理的全局 session，防止系统代理干扰 API 调用
_SESSION = requests.Session()
_SESSION.trust_env = False

# 行业板块静态映射（API 兜底）
_SECTOR_MAP = {
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Internet", "META": "Internet",
    "AMZN": "E-Commerce", "NVDA": "Semiconductors", "TSLA": "Automotive", "AMD": "Semiconductors",
    "ORCL": "Software", "NKE": "Consumer", "PYPL": "FinTech", "ADBE": "Software",
    "SPOT": "Media", "INTC": "Semiconductors", "NFLX": "Media", "DIS": "Media",
    "JPM": "Banking", "BAC": "Banking", "WMT": "Retail", "COST": "Retail",
    "CRM": "Software", "UBER": "Ride-Hailing", "SNAP": "Social Media",
    "SQ": "FinTech", "SHOP": "E-Commerce", "BABA": "E-Commerce",
    "BA": "Aerospace", "CAT": "Industrial", "XOM": "Energy", "CVX": "Energy",
    "PFE": "Pharma", "JNJ": "Pharma", "V": "FinTech", "MA": "FinTech",
    "600519": "白酒", "000858": "白酒", "000001": "银行", "300750": "电池",
    "00700": "互联网", "09988": "互联网", "03690": "互联网", "09618": "互联网",
    "09888": "互联网", "09999": "互联网", "01810": "消费电子", "02318": "保险",
    "00388": "金融", "02015": "汽车", "00100": "AI",
}

# 演示/测试数据 — 包含 3 个市场
DEMO_DATA: Dict[str, Dict[str, Any]] = {
    "AAPL": {"current_price": 273.17, "week52_high": 288.61, "week52_low": 193.25,
             "name": "苹果", "pe_ratio": 34.6, "market": "US"},
    "MSFT": {"current_price": 432.92, "week52_high": 555.45, "week52_low": 356.28,
             "name": "微软", "pe_ratio": 27.1, "market": "US"},
    "GOOGL": {"current_price": 339.32, "week52_high": 349.00, "week52_low": 147.84,
              "name": "谷歌", "pe_ratio": 31.4, "market": "US"},
    "META": {"current_price": 674.72, "week52_high": 796.25, "week52_low": 516.52,
             "name": "Meta", "pe_ratio": 23.3, "market": "US"},
    "ORCL": {"current_price": 187.50, "week52_high": 345.72, "week52_low": 130.99,
             "name": "甲骨文", "pe_ratio": 33.7, "market": "US"},
    "NVDA": {"current_price": 875.35, "week52_high": 974.00, "week52_low": 495.22,
             "name": "英伟达", "pe_ratio": 65.2, "market": "US"},
    "TSLA": {"current_price": 245.80, "week52_high": 414.50, "week52_low": 138.80,
             "name": "特斯拉", "pe_ratio": 78.5, "market": "US"},
    "AMZN": {"current_price": 245.80, "week52_high": 289.00, "week52_low": 151.61,
             "name": "亚马逊", "pe_ratio": 62.1, "market": "US"},
    "AMD":  {"current_price": 156.75, "week52_high": 227.30, "week52_low": 93.12,
             "name": "AMD",   "pe_ratio": 45.2, "market": "US"},
    "600519": {"current_price": 1371.72, "week52_high": 1593.44, "week52_low": 1322.01,
               "name": "贵州茅台", "pe_ratio": 15.8, "market": "CN"},
    "000001": {"current_price": 11.50, "week52_high": 12.50, "week52_low": 10.22,
               "name": "平安银行", "pe_ratio": 3.8, "market": "CN"},
    "300750": {"current_price": 438.19, "week52_high": 468.75, "week52_low": 196.67,
               "name": "宁德时代", "pe_ratio": 25.2, "market": "CN"},
    "01810": {"current_price": 31.12, "week52_high": 61.45, "week52_low": 28.80,
              "name": "小米集团-W", "pe_ratio": 18.31, "market": "HK"},
    "00100": {"current_price": 708.00, "week52_high": 1330.00, "week52_low": 220.00,
              "name": "MINIMAX-W", "pe_ratio": 108.58, "market": "HK"},
    "00700": {"current_price": 485.00, "week52_high": 580.00, "week52_low": 340.00,
              "name": "腾讯控股", "pe_ratio": 22.5, "market": "HK"},
    "09988": {"current_price": 138.00, "week52_high": 165.00, "week52_low": 88.00,
              "name": "阿里巴巴-SW", "pe_ratio": 18.2, "market": "HK"},
    "03690": {"current_price": 165.00, "week52_high": 215.00, "week52_low": 95.00,
              "name": "美团-W", "pe_ratio": 28.5, "market": "HK"},
    "09618": {"current_price": 158.00, "week52_high": 195.00, "week52_low": 112.00,
              "name": "京东集团-SW", "pe_ratio": 15.8, "market": "HK"},
    "09888": {"current_price": 98.00, "week52_high": 125.00, "week52_low": 72.00,
              "name": "百度集团-SW", "pe_ratio": 12.3, "market": "HK"},
    "09999": {"current_price": 168.00, "week52_high": 210.00, "week52_low": 125.00,
              "name": "网易-S", "pe_ratio": 18.9, "market": "HK"},
    "02015": {"current_price": 88.00, "week52_high": 135.00, "week52_low": 65.00,
              "name": "理想汽车-W", "pe_ratio": 16.5, "market": "HK"},
    "02318": {"current_price": 52.00, "week52_high": 68.00, "week52_low": 42.00,
              "name": "中国平安", "pe_ratio": 8.5, "market": "HK"},
    "00388": {"current_price": 365.00, "week52_high": 420.00, "week52_low": 285.00,
              "name": "香港交易所", "pe_ratio": 35.2, "market": "HK"},
}


class DataFetcher:
    """统一的数据获取接口 — 支持 US / CN / HK 三市场"""

    # ── 市场检测 ──────────────────────────────────────────────

    @staticmethod
    def detect_market(ticker: str) -> str:
        """根据 ticker 格式自动检测市场。

        规则:
          - 6 位纯数字 → CN (A股)
          - 1-5 位纯数字 → HK (港股)
          - 其他 → US (美股)
        """
        t = ticker.strip().upper()
        if t.endswith(".HK"):
            return "HK"
        if t.isdigit():
            if len(t) == 6:
                return "CN"
            if 1 <= len(t) <= 5:
                return "HK"
        return "US"

    @staticmethod
    def _hk_secid(ticker: str) -> str:
        """港股东方财富 secid: 116.00xxx"""
        return f"116.{ticker.zfill(5)}"

    # ── 入口方法 ──────────────────────────────────────────────

    @staticmethod
    def get_stock_info(ticker: str, api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """获取单只股票的完整信息（自动选择数据源）。

        流程: 检测市场 → 调用对应 API → 失败则回退 DEMO_DATA
        """
        clean = ticker.strip().upper().replace(".HK", "")
        market = DataFetcher.detect_market(ticker)

        result = None
        source = "demo"

        # ── 美股 ──
        if market == "US" and api_key:
            result = DataFetcher._get_finnhub_quote(clean, api_key)
            if result:
                result["market"] = "US"
                result["source"] = "finnhub"
                source = "finnhub"
                # sector 优先用 API 返回的 finnhubIndustry，否则用静态映射兜底
                if not result.get("sector"):
                    result["sector"] = _SECTOR_MAP.get(clean)

        # ── A 股 ──
        elif market == "CN":
            result = DataFetcher._get_eastmoney_quote(clean)
            if result:
                result["market"] = "CN"
                result["source"] = "eastmoney"
                source = "eastmoney"
                sector = _SECTOR_MAP.get(clean)
                if sector:
                    result["sector"] = sector

        # ── 港股 ──
        elif market == "HK":
            result = DataFetcher._get_eastmoney_hk_quote(clean)
            if result:
                result["market"] = "HK"
                result["source"] = "eastmoney"
                source = "eastmoney"
                sector = _SECTOR_MAP.get(clean)
                if sector:
                    result["sector"] = sector

        # ── 回退: 演示数据 ──
        if not result and clean in DEMO_DATA:
            logger.info("Falling back to DEMO_DATA for %s (market=%s, API returned no data)", clean, market)
            demo = dict(DEMO_DATA[clean])
            base_price = demo.get("current_price", 0)
            dynamic_price = DataFetcher._dynamic_demo_price(clean, base_price)
            dynamic_change = round((dynamic_price - base_price) / base_price * 100, 2)

            demo["ticker"] = clean
            demo["market"] = demo.get("market", market)
            demo["source"] = "demo"
            demo["current_price"] = dynamic_price
            demo["change_pct"] = dynamic_change
            demo["week52_high_date"] = demo.get("week52_high_date", "-")
            demo["week52_low_date"] = demo.get("week52_low_date", "-")
            demo["drawdown"] = DataFetcher.calculate_drawdown(
                dynamic_price, demo.get("week52_high", 0))
            demo["distance_low_pct"] = DataFetcher._calc_distance_low(
                dynamic_price, demo.get("week52_low", 0))
            demo["last_updated"] = datetime.now().isoformat()
            if "sector" not in demo:
                demo["sector"] = _SECTOR_MAP.get(clean)
            if "market_status" not in demo:
                demo["market_status"] = DataFetcher.get_market_status(
                    demo.get("drawdown"))
            return demo

        return result

    # ── Finnhub 美股 ──────────────────────────────────────────

    @staticmethod
    def _get_finnhub_quote(ticker: str, api_key: str) -> Optional[Dict[str, Any]]:
        """从 Finnhub 获取美股行情 — 3 次 API 调用覆盖全部字段。

        接口:
          /quote              → 当前价 (c), 涨跌幅 (dp), 前收盘 (pc), 时间戳 (t)
          /stock/metric?metric=all → 52周高低点 + PE (单次调用取全部)
          /stock/profile2     → 公司名称 + 行业分类
        """
        try:
            # 1. 实时报价
            resp = _SESSION.get(
                f"{FINNHUB_BASE_URL}/quote",
                params={"symbol": ticker, "token": api_key},
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning("Finnhub /quote failed for %s: HTTP %s", ticker, resp.status_code)
                return None
            q = resp.json()
            current = q.get("c")
            if current is None or current == 0:
                return None
            change_pct = q.get("dp")

            # 2. 全部指标（52周高低点 + PE，一次调用替代原来的两次 metric 请求）
            week52_high = None
            week52_low = None
            week52_high_date = None
            week52_low_date = None
            pe_ratio = None
            try:
                resp2 = _SESSION.get(
                    f"{FINNHUB_BASE_URL}/stock/metric",
                    params={"symbol": ticker, "metric": "all", "token": api_key},
                    timeout=10,
                )
                if resp2.status_code == 200:
                    m = resp2.json().get("metric", {}) or {}
                    week52_high = m.get("52WeekHigh")
                    week52_low = m.get("52WeekLow")
                    week52_high_date = m.get("52WeekHighDate")
                    week52_low_date = m.get("52WeekLowDate")
                    pe_ratio = m.get("peBasicExclExtraTTM") or m.get("peTTM")
            except Exception:
                logger.debug("Finnhub /stock/metric failed for %s", ticker, exc_info=True)

            # 3. 公司名称 + 行业（一次 profile2 调用同时获取）
            name = ticker
            sector = None
            try:
                resp3 = _SESSION.get(
                    f"{FINNHUB_BASE_URL}/stock/profile2",
                    params={"symbol": ticker, "token": api_key},
                    timeout=10,
                )
                if resp3.status_code == 200:
                    p = resp3.json()
                    name = p.get("name") or ticker
                    sector = p.get("finnhubIndustry")
            except Exception:
                logger.debug("Finnhub /stock/profile2 failed for %s", ticker, exc_info=True)

            # 组装
            distance_low_pct = DataFetcher._calc_distance_low(current, week52_low)
            drawdown = DataFetcher.calculate_drawdown(current, week52_high)
            now = datetime.now()

            ts_local = q.get("t", 0)
            ah_change_pct, ah_change_label = DataFetcher._calc_ah_change(current, q.get("pc"), ts_local)

            return {
                "ticker": ticker,
                "name": name,
                "market": "US",
                "source": "finnhub",
                "current_price": current,
                "change_pct": change_pct,
                "ah_change_pct": ah_change_pct,
                "ah_change_label": ah_change_label,
                "week52_high": week52_high,
                "week52_low": week52_low,
                "week52_high_date": week52_high_date,
                "week52_low_date": week52_low_date,
                "drawdown": drawdown,
                "distance_low_pct": distance_low_pct,
                "pe_ratio": pe_ratio,
                "sector": sector,
                "market_status": DataFetcher.get_market_status(drawdown),
                "last_updated": now.isoformat(),
            }
        except Exception:
            logger.warning("Finnhub quote exception for %s", ticker, exc_info=True)
            return None

    # ── 东方财富 A 股 ─────────────────────────────────────────

    @staticmethod
    def _get_eastmoney_quote(ticker: str) -> Optional[Dict[str, Any]]:
        """从东方财富获取 A 股行情，通过 K 线接口计算 52 周高低点。

        fltt=1 → 价格单位为分（需 /100）
        """
        try:
            # 确定 secid: 6xxxx / 9xxxx → 沪市 (1), 其他 → 深市 (0)
            if ticker[0] in ("6", "9"):
                secid = f"1.{ticker}"
            else:
                secid = f"0.{ticker}"

            # ── 实时报价 ──
            resp = _SESSION.get(
                EASTMONEY_QUOTE_URL,
                params={
                    "secid": secid,
                    "fields": "f43,f57,f58,f162,f170,f171",
                    "invt": "2",
                    "fltt": "1",
                },
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"},
            )
            if resp.status_code != 200:
                return None
            data = resp.json().get("data")
            if not data:
                return None

            # fltt=1: f43 是价格(分), f170 是涨跌幅(百分比*100), f162 是 PE(*100)
            current = data.get("f43")
            if current is None:
                return None
            current_price = current / 100
            change_pct_raw = data.get("f170")
            change_pct = (change_pct_raw / 100) if change_pct_raw is not None else None
            # f58 是名称, f57 是代码（备用回退）, 最后用静态映射兜底
            name = data.get("f58") or data.get("f57") or _NAME_MAP.get(ticker, ticker)
            pe_raw = data.get("f162")
            pe_ratio = (pe_raw / 100) if pe_raw is not None and pe_raw != "-" else None

            # ── K 线: 52 周高低点 ──
            week52_high = None
            week52_low = None
            week52_high_date = None
            week52_low_date = None

            try:
                kresp = _SESSION.get(
                    EASTMONEY_KLINE_URL,
                    params={
                        "secid": secid,
                        "fields1": "f1,f2,f3,f4,f5,f6",
                        "fields2": "f51,f52,f53,f54,f55,f56,f57",
                        "klt": "101",
                        "fqt": "1",
                        "end": "20500101",
                        "lmt": "300",
                    },
                    timeout=15,
                    headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"},
                )
                if kresp.status_code == 200:
                    kdata = kresp.json().get("data")
                    if kdata and kdata.get("klines"):
                        # 格式: date,open,close,high,low,volume,amount,amplitude
                        #        parts[0]   [1]   [2]  [3]  [4]   [5]    [6]     [7]
                        max_high = -float("inf")
                        min_low = float("inf")
                        h_date = ""
                        l_date = ""
                        for line in kdata["klines"]:
                            parts = line.split(",")
                            if len(parts) < 5:
                                continue
                            try:
                                h = float(parts[3])
                                lo = float(parts[4])
                            except ValueError:
                                continue
                            if h > max_high:
                                max_high = h
                                h_date = parts[0]
                            if lo < min_low:
                                min_low = lo
                                l_date = parts[0]
                        if max_high > -float("inf"):
                            week52_high = max_high
                            week52_high_date = h_date
                        if min_low < float("inf"):
                            week52_low = min_low
                            week52_low_date = l_date
            except Exception:
                logger.debug("EastMoney K-line failed for A-share %s", ticker, exc_info=True)

            # 组装
            distance_low_pct = DataFetcher._calc_distance_low(current_price, week52_low)
            drawdown = DataFetcher.calculate_drawdown(current_price, week52_high)
            now = datetime.now()

            return {
                "ticker": ticker,
                "name": name,
                "market": "CN",
                "source": "eastmoney",
                "current_price": round(current_price, 2),
                "change_pct": round(change_pct, 2) if change_pct is not None else None,
                "week52_high": week52_high,
                "week52_low": week52_low,
                "week52_high_date": week52_high_date,
                "week52_low_date": week52_low_date,
                "drawdown": drawdown,
                "distance_low_pct": distance_low_pct,
                "pe_ratio": pe_ratio,
                "market_status": DataFetcher.get_market_status(drawdown),
                "last_updated": now.isoformat(),
            }
        except Exception:
            logger.warning("EastMoney A-share quote exception for %s", ticker, exc_info=True)
            return None

    # ── 东方财富 港股 ─────────────────────────────────────────

    @staticmethod
    def _get_eastmoney_hk_quote(ticker: str) -> Optional[Dict[str, Any]]:
        """从东方财富获取港股行情，通过日 K 线接口计算 52 周高低点。

        fltt=2 → 价格已正确缩放（无需 /100）
        fqt=1 → 前复权（与 A 股一致，保证 52 周高低点可比）
        """
        try:
            secid = DataFetcher._hk_secid(ticker)

            # ── 实时报价 ──
            resp = _SESSION.get(
                EASTMONEY_QUOTE_URL,
                params={
                    "secid": secid,
                    "fields": "f43,f57,f58,f162,f170",
                    "invt": "2",
                    "fltt": "2",
                },
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"},
            )
            if resp.status_code != 200:
                logger.warning("HK quote fetch failed for %s (secid=%s): HTTP %s",
                               ticker, secid, resp.status_code)
                return None
            data = resp.json().get("data")
            if not data:
                logger.warning("HK quote empty data for %s (secid=%s): raw=%s",
                               ticker, secid, str(resp.json())[:200])
                return None

            # fltt=2: f43 价格无需缩放, f170 涨跌幅已正确
            current_price = data.get("f43")
            if current_price is None:
                return None
            change_pct = data.get("f170")
            # f58 是名称, f57 是代码（备用回退）, 最后用静态映射兜底
            api_name = data.get("f58") or data.get("f57") or ""
            name = api_name if api_name else _NAME_MAP.get(ticker, ticker)
            # PE: 港股优先 f162（同 A 股），备用 f173
            pe_raw = data.get("f162") or data.get("f173")
            pe_ratio = pe_raw if (pe_raw is not None and pe_raw != "-") else None

            # ── K 线: 52 周高低点 ──
            week52_high = None
            week52_low = None
            week52_high_date = None
            week52_low_date = None

            try:
                kresp = _SESSION.get(
                    EASTMONEY_KLINE_URL,
                    params={
                        "secid": secid,
                        "fields1": "f1,f2,f3,f4,f5,f6",
                        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
                        "klt": "101",
                        "fqt": "1",
                        "end": "20500101",
                        "lmt": "300",
                    },
                    timeout=15,
                    headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"},
                )
                if kresp and kresp.status_code == 200:
                    kdata = kresp.json().get("data")
                    if kdata and kdata.get("klines"):
                        # 格式: date,open,close,high,low,volume,amount,amplitude,chg%,chg,turnover%
                        #        parts[0]   [1]   [2]  [3]  [4]   [5]    [6]     [7]     [8]  [9]   [10]
                        max_high = -float("inf")
                        min_low = float("inf")
                        h_date = ""
                        l_date = ""
                        for line in kdata["klines"]:
                            parts = line.split(",")
                            if len(parts) < 5:
                                continue
                            try:
                                h = float(parts[3])
                                lo = float(parts[4])
                            except ValueError:
                                continue
                            if h > max_high:
                                max_high = h
                                h_date = parts[0]
                            if lo < min_low:
                                min_low = lo
                                l_date = parts[0]
                        if max_high > -float("inf"):
                            week52_high = max_high
                            week52_high_date = h_date
                        if min_low < float("inf"):
                            week52_low = min_low
                            week52_low_date = l_date
            except Exception:
                logger.debug("EastMoney K-line failed for HK %s", ticker, exc_info=True)

            # 组装
            distance_low_pct = DataFetcher._calc_distance_low(current_price, week52_low)
            drawdown = DataFetcher.calculate_drawdown(current_price, week52_high)
            now = datetime.now()

            return {
                "ticker": ticker,
                "name": name,
                "market": "HK",
                "source": "eastmoney",
                "current_price": current_price,
                "change_pct": change_pct,
                "week52_high": week52_high,
                "week52_low": week52_low,
                "week52_high_date": week52_high_date,
                "week52_low_date": week52_low_date,
                "drawdown": drawdown,
                "distance_low_pct": distance_low_pct,
                "pe_ratio": pe_ratio,
                "market_status": DataFetcher.get_market_status(drawdown),
                "last_updated": now.isoformat(),
            }
        except Exception:
            logger.warning("EastMoney HK quote exception for %s", ticker, exc_info=True)
            return None

    # ── 工具方法 ──────────────────────────────────────────────

    @staticmethod
    def _dynamic_demo_price(ticker: str, base_price: float) -> float:
        """根据 ticker + 当前分钟生成动态价格（随机游走）。

        使用 ticker + 年月日时分 做种子，保证同 ticker 同分钟内一致，
        跨分钟变化幅度不超过 base 的 ±3%。
        """
        now = datetime.now()
        seed_str = f"{ticker}-{now.year}-{now.month}-{now.day}-{now.hour}-{now.minute}"
        seed = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % (2 ** 31)
        rng = random.Random(seed)
        # 随机游走：基础价 × [0.97, 1.03]
        jitter = rng.uniform(-0.03, 0.03)
        return round(base_price * (1 + jitter), 2)

    @staticmethod
    def calculate_drawdown(current_price: Optional[float], week52_high: Optional[float]) -> Optional[float]:
        """计算从 52 周最高点的回撤百分比。

        公式: (current - high) / high * 100。负数表示低于高点。
        """
        if current_price is None or week52_high is None or week52_high == 0:
            return None
        return round((current_price - week52_high) / week52_high * 100, 2)

    @staticmethod
    def _calc_distance_low(current: Optional[float], low: Optional[float]) -> Optional[float]:
        """计算当前价距离 52 周低点的百分比。"""
        if current is None or low is None or low == 0:
            return None
        return round((current - low) / low * 100, 2)

    @staticmethod
    def get_market_status(drawdown: Optional[float], threshold: float = 20.0) -> str:
        """根据回撤幅度返回市场状态。

        - drawdown <= -threshold → "alert" (严重回撤)
        - drawdown <= -threshold/2  → "warning" (值得关注)
        - 其他 → "normal"
        """
        if drawdown is None:
            return "normal"
        if drawdown <= -threshold:
            return "alert"
        if drawdown <= -threshold / 2:
            return "warning"
        return "normal"

    @staticmethod
    def _calc_ah_change(current: Optional[float], prev_close: Optional[float], ts_unix: int) -> tuple:
        """计算美股盘后/夜盘涨跌幅。

        美股常规交易 = 美东 9:30-16:00，对应北京时间:
          - EDT (UTC-4, 3月-11月): 21:30 - 04:00 (次日)
          - EST (UTC-5, 11月-3月): 22:30 - 05:00 (次日)
        近似判断: 北京时间 hour >= 21 或 hour < 5 为盘中，其余为盘后。

        Returns: (ah_change_pct, ah_change_label)
        """
        if current is None or prev_close is None or prev_close == 0 or ts_unix == 0:
            return None, None

        from datetime import timezone, timedelta
        beijing_tz = timezone(timedelta(hours=8))
        dt_bj = datetime.fromtimestamp(ts_unix, tz=beijing_tz)
        hour = dt_bj.hour
        weekday = dt_bj.weekday()

        # 周末不交易
        # 盘中时段（北京时间夜晚/凌晨）: hour >= 21 或 hour < 5
        if weekday < 5 and (hour >= 21 or hour < 5):
            return None, None

        # 盘后/夜盘：计算相对上一交易日收盘的涨跌幅
        ah_change_pct = round((current - prev_close) / prev_close * 100, 3)

        # 北京时间 5:00-9:00 对应美股盘前（美东夏令时 17:00-21:00 / 冬令时 18:00-22:00）
        if 5 <= hour < 9:
            label = "盘前"
        else:
            label = "盘后"

        return ah_change_pct, label


# ── 模块级测试 ───────────────────────────────────────────────

def test_fetch():
    """快速测试三个市场的数据获取（含 API 及 DEMO 回退）。"""
    api_key = os.environ.get("FINNHUB_API_KEY", "")
    print(f"Finnhub API key: {'set' if api_key else 'NOT SET (using demo fallback)'}")
    print()

    test_cases = [
        # (ticker, label)
        ("AAPL",   "美股-苹果"),
        ("TSLA",   "美股-特斯拉"),
        ("600519", "A股-茅台"),
        ("300750", "A股-宁德时代"),
        ("00700",  "港股-腾讯"),
        ("01810",  "港股-小米"),
        ("UNKNOWN","不存在-回退"),
    ]

    for ticker, label in test_cases:
        market = DataFetcher.detect_market(ticker)
        result = DataFetcher.get_stock_info(ticker, api_key=api_key or None)
        if result:
            src = result.get("source", "?")
            print(f"[{label}] market={market} source={src}")
            print(f"  价格: {result.get('current_price')}  涨跌: {result.get('change_pct')}%")
            print(f"  52高: {result.get('week52_high')}  ({result.get('week52_high_date')})")
            print(f"  52低: {result.get('week52_low')}  ({result.get('week52_low_date')})")
            print(f"  回撤: {result.get('drawdown')}%  距低点: {result.get('distance_low_pct')}%")
            print(f"  PE: {result.get('pe_ratio')}  行业: {result.get('sector', '-')}")
            print(f"  状态: {result.get('market_status')}")
        else:
            print(f"[{label}] market={market} → 无数据")
        print()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    test_fetch()
