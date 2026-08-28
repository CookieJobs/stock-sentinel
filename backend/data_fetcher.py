"""股票数据获取封装 - Finnhub API (美股) + 东方财富 (A股/港股)"""
import os
import json
import hashlib
import logging
import random
import time
import threading
import requests
from typing import Optional, Dict, Any
from datetime import date, datetime, timedelta, timezone

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
# 东财域名与路径（https 优先，连接被重置时自动降级 http——见 _em_get）
EASTMONEY_QUOTE_HOST = "push2.eastmoney.com"
EASTMONEY_KLINE_HOST = "push2his.eastmoney.com"
EASTMONEY_QUOTE_PATH = "/api/qt/stock/get"
EASTMONEY_KLINE_PATH = "/api/qt/stock/kline/get"


def _em_get(host: str, path: str, params: dict, timeout: int) -> Optional["requests.Response"]:
    """东财 GET：https 优先，TLS 握手被重置（RemoteDisconnected）时自动降级 http。

    历史原因（2026-08-15 起）：运行环境的 Clash TUN/网络曾重置东财 https 握手，
    当时被迫固定 http（明文，安全债）。现改为自动降级——https 可用时走加密通道。
    """
    last_err = None
    for scheme in ("https", "http"):
        try:
            return _SESSION.get(
                f"{scheme}://{host}{path}",
                params=params,
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://quote.eastmoney.com/"},
            )
        except Exception as e:
            last_err = e
    logger.warning("EastMoney %s%s failed: %s", host, path, last_err)
    return None

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


def _to_float(v):
    """安全转 float，失败返回 None"""
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


class DataFetcher:
    """统一的数据获取接口 — 支持 US / CN / HK 三市场"""

    # 高频报价刷新不应重复拉取同一份日线；行情实时字段仍逐次更新。
    _DAILY_BAR_CACHE_TTL_SECONDS = 18 * 60 * 60
    _daily_bar_cache: Dict[str, tuple[float, list[dict]]] = {}
    _daily_bar_cache_lock = threading.Lock()

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

    @staticmethod
    def calculate_drawdown_windows(
        current_price: float,
        daily_bars: list[dict],
        as_of: Optional[datetime] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """按统一的日线口径计算 3 月、6 月和 1 年回撤。

        每个周期均以日历月前的同日为起点，范围包含起止两日；高点和低点
        来自该周期内的日线，实时价格若突破日线范围则计入当日高低点。
        """
        try:
            current = float(current_price)
        except (TypeError, ValueError):
            return {
                window: {"status": "unavailable"}
                for window in ("3m", "6m", "1y")
            }

        as_of_date = (as_of or datetime.now()).date()
        parsed_bars = []
        for bar in daily_bars or []:
            try:
                trade_date = datetime.fromisoformat(str(bar["trade_date"])[:10]).date()
                high = float(bar["high"])
                low = float(bar["low"])
            except (KeyError, TypeError, ValueError):
                continue
            if high <= 0 or low <= 0:
                continue
            parsed_bars.append((trade_date, high, low))

        parsed_bars.sort(key=lambda bar: bar[0])
        windows = {}
        for name, months in (("3m", 3), ("6m", 6), ("1y", 12)):
            period_start = DataFetcher._subtract_months(as_of_date, months)
            bars_in_window = [bar for bar in parsed_bars if period_start <= bar[0] <= as_of_date]
            # 周末和节假日没有日线，允许起点后最多 3 个自然日的首个交易日。
            if not bars_in_window or parsed_bars[0][0] > period_start + timedelta(days=3):
                windows[name] = {
                    "status": "insufficient_history",
                    "period_start": period_start.isoformat(),
                    "as_of": as_of_date.isoformat(),
                }
                continue

            high_date, high, low_date, low = DataFetcher._window_extremes(bars_in_window)
            if current > high:
                high, high_date = current, as_of_date
            if current < low:
                low, low_date = current, as_of_date
            windows[name] = {
                "status": "ok",
                "period_start": period_start.isoformat(),
                "as_of": as_of_date.isoformat(),
                "high": high,
                "high_date": high_date.isoformat(),
                "low": low,
                "low_date": low_date.isoformat(),
                "drawdown": round((current - high) / high * 100, 2),
                "distance_low_pct": round((current - low) / low * 100, 2),
            }
        return windows

    @staticmethod
    def _subtract_months(value: date, months: int) -> date:
        """返回 value 往前 months 个自然月的同日（月底按当月最后一天处理）。"""
        year = value.year
        month = value.month - months
        while month <= 0:
            year -= 1
            month += 12
        import calendar

        return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))

    @staticmethod
    def _window_extremes(daily_bars: list[tuple[date, float, float]]):
        """以出现日期最早的同值点作为高低点日期，结果保持确定性。"""
        high_date, high, _ = max(daily_bars, key=lambda bar: bar[1])
        low_date, _, low = min(daily_bars, key=lambda bar: bar[2])
        return high_date, high, low_date, low

    @staticmethod
    def _legacy_metrics_from_windows(windows: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """兼容既有告警和存量接口：旧 52 周字段始终映射为固定的 1 年周期。"""
        one_year = (windows or {}).get("1y") or {}
        if one_year.get("status") != "ok":
            return {
                "week52_high": None,
                "week52_low": None,
                "week52_high_date": None,
                "week52_low_date": None,
                "drawdown": None,
                "distance_low_pct": None,
            }
        return {
            "week52_high": one_year["high"],
            "week52_low": one_year["low"],
            "week52_high_date": one_year["high_date"],
            "week52_low_date": one_year["low_date"],
            "drawdown": one_year["drawdown"],
            "distance_low_pct": one_year["distance_low_pct"],
        }

    @staticmethod
    def _daily_bars_from_eastmoney(klines: list[str]) -> list[dict]:
        """将东财日 K 线标准化为回撤计算使用的最小字段。"""
        bars = []
        for line in klines or []:
            parts = line.split(",")
            if len(parts) < 5:
                continue
            try:
                bars.append({
                    "trade_date": parts[0],
                    "high": float(parts[3]),
                    "low": float(parts[4]),
                })
            except (TypeError, ValueError):
                continue
        return bars

    @staticmethod
    def _daily_bars_from_yahoo(result: Dict[str, Any]) -> list[dict]:
        """将 Yahoo chart 响应标准化为回撤计算使用的最小字段。"""
        timestamps = result.get("timestamp") or []
        quotes = (result.get("indicators") or {}).get("quote") or [{}]
        quote = quotes[0] if quotes else {}
        highs = quote.get("high") or []
        lows = quote.get("low") or []
        bars = []
        for timestamp, high, low in zip(timestamps, highs, lows):
            if high is None or low is None:
                continue
            try:
                bars.append({
                    "trade_date": datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat(),
                    "high": float(high),
                    "low": float(low),
                })
            except (OSError, TypeError, ValueError):
                continue
        return bars

    @staticmethod
    def _cached_daily_bars(cache_key: str, loader) -> list[dict]:
        """在日线有效期内复用历史数据，失败结果不缓存以便下一次刷新重试。"""
        now = time.monotonic()
        with DataFetcher._daily_bar_cache_lock:
            cached = DataFetcher._daily_bar_cache.get(cache_key)
            if cached and now - cached[0] < DataFetcher._DAILY_BAR_CACHE_TTL_SECONDS:
                return cached[1]

        bars = loader()
        if bars:
            with DataFetcher._daily_bar_cache_lock:
                DataFetcher._daily_bar_cache[cache_key] = (now, bars)
        return bars

    @staticmethod
    def _get_finnhub_daily_bars(ticker: str, api_key: str) -> list[dict]:
        """读取覆盖 1 年窗口所需的 Finnhub 日线；日内复用已有缓存。"""
        return DataFetcher._cached_daily_bars(
            f"finnhub:{ticker}",
            lambda: DataFetcher._fetch_finnhub_daily_bars(ticker, api_key),
        )

    @staticmethod
    def _fetch_finnhub_daily_bars(ticker: str, api_key: str) -> list[dict]:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=400)
        try:
            resp = _SESSION.get(
                f"{FINNHUB_BASE_URL}/stock/candle",
                params={
                    "symbol": ticker,
                    "resolution": "D",
                    "from": int(start.timestamp()),
                    "to": int(end.timestamp()),
                    "token": api_key,
                },
                timeout=12,
            )
            if resp.status_code != 200:
                return []
            payload = resp.json()
            if payload.get("s") != "ok":
                return []
            return [
                {"trade_date": datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat(),
                 "high": high, "low": low}
                for timestamp, high, low in zip(
                    payload.get("t") or [], payload.get("h") or [], payload.get("l") or []
                )
                if high is not None and low is not None
            ]
        except Exception:
            logger.debug("Finnhub /stock/candle failed for %s", ticker, exc_info=True)
            return []

    @staticmethod
    def _get_eastmoney_daily_bars(secid: str) -> list[dict]:
        """读取东财日 K 线，覆盖 1 年窗口及首尾交易日余量。"""
        return DataFetcher._cached_daily_bars(
            f"eastmoney:{secid}",
            lambda: DataFetcher._fetch_eastmoney_daily_bars(secid),
        )

    @staticmethod
    def _fetch_eastmoney_daily_bars(secid: str) -> list[dict]:
        try:
            response = _em_get(
                EASTMONEY_KLINE_HOST,
                EASTMONEY_KLINE_PATH,
                {
                    "secid": secid,
                    "fields1": "f1,f2,f3,f4,f5,f6",
                    "fields2": "f51,f52,f53,f54,f55,f56,f57",
                    "klt": "101",
                    "fqt": "1",
                    "end": "20500101",
                    "lmt": "400",
                },
                15,
            )
            if not response or response.status_code != 200:
                return []
            data = response.json().get("data") or {}
            return DataFetcher._daily_bars_from_eastmoney(data.get("klines") or [])
        except Exception:
            logger.debug("EastMoney K-line failed for %s", secid, exc_info=True)
            return []

    # ── 入口方法 ──────────────────────────────────────────────

    @staticmethod
    def get_stock_info(ticker: str, api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """获取单只股票的完整信息（自动选择数据源）。

        流程: 检测市场 → 调用对应 API（多源降级，全部失败返回 None）
        """
        clean = ticker.strip().upper().replace(".HK", "")
        market = DataFetcher.detect_market(ticker)

        result = None
        source = None

        # ── 美股 ──
        if market == "US":
            if api_key:
                result = DataFetcher._get_finnhub_quote(clean, api_key)
                if result:
                    result["market"] = "US"
                    result["source"] = "finnhub"
                    source = "finnhub"
                    # sector 优先用 API 返回的 finnhubIndustry，否则用静态映射兜底
                    if not result.get("sector"):
                        result["sector"] = _SECTOR_MAP.get(clean)
            if not result:
                # 第二源：Yahoo Finance（免费无 key）
                result = DataFetcher._get_yahoo_quote(clean)
                if result:
                    result["market"] = "US"
                    result["source"] = "yahoo"
                    source = "yahoo"
                    if not result.get("sector"):
                        result["sector"] = _SECTOR_MAP.get(clean)

        # ── A 股 ──
        elif market == "CN":
            result = DataFetcher._fetch_cn_hk(clean, "CN")

        # ── 港股 ──
        elif market == "HK":
            result = DataFetcher._fetch_cn_hk(clean, "HK")

        # 所有源都失败 → 如实返回 None（不造假数据）
        return result

    @staticmethod
    def _fetch_cn_hk(ticker: str, market: str) -> Optional[Dict[str, Any]]:
        """CN/HK 实时行情：东财 + 腾讯双源，按用户配置（datasource.realtime）排序"""
        eastmoney = (DataFetcher._get_eastmoney_quote if market == "CN"
                     else DataFetcher._get_eastmoney_hk_quote)
        try:
            from datasource_config import get_override
            override = get_override("realtime")
        except Exception:
            override = None
        if override == "tencent":
            chain = [("tencent", lambda: DataFetcher._get_tencent_quote(ticker, market)),
                     ("eastmoney", lambda: eastmoney(ticker))]
        else:
            chain = [("eastmoney", lambda: eastmoney(ticker)),
                     ("tencent", lambda: DataFetcher._get_tencent_quote(ticker, market))]
        for name, fn in chain:
            result = fn()
            if result:
                result["market"] = market
                result["source"] = name
                sector = _SECTOR_MAP.get(ticker)
                if sector:
                    result["sector"] = sector
                return result
        return None

    # ── Yahoo Finance 美股（第二源，免费无 key）────────────────

    @staticmethod
    def _get_yahoo_quote(ticker: str) -> Optional[Dict[str, Any]]:
        """Yahoo Finance 美股行情（18 个月日线）；作为 Finnhub 的降级源。"""
        try:
            resp = _SESSION.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
                params={"range": "18mo", "interval": "1d"},
                timeout=12,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if resp.status_code != 200:
                return None
            result = resp.json()["chart"]["result"][0]
            meta = result.get("meta") or {}
            current = meta.get("regularMarketPrice")
            if not current:
                return None
            prev_close = meta.get("chartPreviousClose") or current
            change_pct = round((current - prev_close) / prev_close * 100, 2) if prev_close else None
            now = datetime.now()
            drawdown_windows = DataFetcher.calculate_drawdown_windows(
                current, DataFetcher._daily_bars_from_yahoo(result), now
            )
            legacy = DataFetcher._legacy_metrics_from_windows(drawdown_windows)
            drawdown = legacy["drawdown"]
            return {
                "ticker": ticker,
                "name": meta.get("longName") or ticker,
                "market": "US",
                "source": "yahoo",
                "current_price": current,
                "change_pct": change_pct,
                **legacy,
                "drawdown_windows": drawdown_windows,
                "drawdown": drawdown,
                "pe_ratio": None,
                "market_status": DataFetcher.get_market_status(drawdown),
                "last_updated": now.isoformat(),
            }
        except Exception:
            logger.warning("Yahoo quote exception for %s", ticker, exc_info=True)
            return None

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

            # 2. 全部指标（PE 等基本面指标）
            pe_ratio = None
            try:
                resp2 = _SESSION.get(
                    f"{FINNHUB_BASE_URL}/stock/metric",
                    params={"symbol": ticker, "metric": "all", "token": api_key},
                    timeout=10,
                )
                if resp2.status_code == 200:
                    m = resp2.json().get("metric", {}) or {}
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

            now = datetime.now()
            drawdown_windows = DataFetcher.calculate_drawdown_windows(
                current, DataFetcher._get_finnhub_daily_bars(ticker, api_key), now
            )
            legacy = DataFetcher._legacy_metrics_from_windows(drawdown_windows)
            drawdown = legacy["drawdown"]

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
                **legacy,
                "drawdown_windows": drawdown_windows,
                "drawdown": drawdown,
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
            resp = _em_get(
                EASTMONEY_QUOTE_HOST, EASTMONEY_QUOTE_PATH,
                {
                    "secid": secid,
                    "fields": "f43,f57,f58,f162,f170,f171",
                    "invt": "2",
                    "fltt": "1",
                },
                10,
            )
            if not resp or resp.status_code != 200:
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

            now = datetime.now()
            drawdown_windows = DataFetcher.calculate_drawdown_windows(
                current_price, DataFetcher._get_eastmoney_daily_bars(secid), now
            )
            legacy = DataFetcher._legacy_metrics_from_windows(drawdown_windows)
            drawdown = legacy["drawdown"]

            return {
                "ticker": ticker,
                "name": name,
                "market": "CN",
                "source": "eastmoney",
                "current_price": round(current_price, 2),
                "change_pct": round(change_pct, 2) if change_pct is not None else None,
                **legacy,
                "drawdown_windows": drawdown_windows,
                "drawdown": drawdown,
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
            resp = _em_get(
                EASTMONEY_QUOTE_HOST, EASTMONEY_QUOTE_PATH,
                {
                    "secid": secid,
                    "fields": "f43,f57,f58,f162,f170",
                    "invt": "2",
                    "fltt": "2",
                },
                10,
            )
            if not resp or resp.status_code != 200:
                logger.warning("HK quote fetch failed for %s (secid=%s)", ticker, secid)
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

            now = datetime.now()
            drawdown_windows = DataFetcher.calculate_drawdown_windows(
                current_price, DataFetcher._get_eastmoney_daily_bars(secid), now
            )
            legacy = DataFetcher._legacy_metrics_from_windows(drawdown_windows)
            drawdown = legacy["drawdown"]

            return {
                "ticker": ticker,
                "name": name,
                "market": "HK",
                "source": "eastmoney",
                "current_price": current_price,
                "change_pct": change_pct,
                **legacy,
                "drawdown_windows": drawdown_windows,
                "drawdown": drawdown,
                "pe_ratio": pe_ratio,
                "market_status": DataFetcher.get_market_status(drawdown),
                "last_updated": now.isoformat(),
            }
        except Exception:
            logger.warning("EastMoney HK quote exception for %s", ticker, exc_info=True)
            return None

    # ── 腾讯行情（CN/HK 降级源）───────────────────────────────

    @staticmethod
    def _tencent_secid(ticker: str, market: str) -> str:
        """腾讯行情代码：CN → sh/sz + 6 位；HK → hk + 5 位"""
        if market == "HK":
            return "hk" + ticker.zfill(5)
        prefix = "sh" if ticker[0] in ("6", "9") else "sz"
        return prefix + ticker

    @staticmethod
    def _get_tencent_quote(ticker: str, market: str) -> Optional[Dict[str, Any]]:
        """腾讯行情：实时报价（qt.gtimg.cn，GBK）+ 周 K 计算 52 周高低点"""
        try:
            secid = DataFetcher._tencent_secid(ticker, market)
            resp = _SESSION.get(
                f"https://qt.gtimg.cn/q={secid}",
                timeout=10,
                headers={"Referer": "https://gu.qq.com/", "User-Agent": "Mozilla/5.0"},
            )
            if resp.status_code != 200:
                return None
            text = resp.content.decode("gbk", errors="ignore")
            if '="' not in text:
                return None
            parts = text.split('="', 1)[1].rstrip('";\n').split("~")
            if len(parts) < 40:
                return None
            name = parts[1] or _NAME_MAP.get(ticker, ticker)
            current_price = _to_float(parts[3])
            if current_price is None:
                return None
            change_pct = _to_float(parts[32])
            pe_ratio = _to_float(parts[39]) if market == "CN" else None

            now = datetime.now()
            drawdown_windows = DataFetcher.calculate_drawdown_windows(
                current_price, DataFetcher._get_tencent_daily_bars(secid), now
            )
            legacy = DataFetcher._legacy_metrics_from_windows(drawdown_windows)
            drawdown = legacy["drawdown"]

            return {
                "ticker": ticker,
                "name": name,
                "market": market,
                "source": "tencent",
                "current_price": current_price,
                "change_pct": change_pct,
                **legacy,
                "drawdown_windows": drawdown_windows,
                "drawdown": drawdown,
                "pe_ratio": pe_ratio,
                "market_status": DataFetcher.get_market_status(drawdown),
                "last_updated": now.isoformat(),
            }
        except Exception:
            logger.warning("Tencent quote exception for %s (%s)", ticker, market, exc_info=True)
            return None

    @staticmethod
    def _get_tencent_daily_bars(secid: str) -> list[dict]:
        """读取腾讯日 K 线，覆盖 1 年窗口及首尾交易日余量。"""
        return DataFetcher._cached_daily_bars(
            f"tencent:{secid}",
            lambda: DataFetcher._fetch_tencent_daily_bars(secid),
        )

    @staticmethod
    def _fetch_tencent_daily_bars(secid: str) -> list[dict]:
        try:
            resp = _SESSION.get(
                "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
                params={"param": f"{secid},day,,,400,qfq"},
                timeout=12,
                headers={"Referer": "https://gu.qq.com/", "User-Agent": "Mozilla/5.0"},
            )
            if resp.status_code != 200:
                return []
            data = resp.json().get("data", {}).get(secid, {})
            bars = data.get("qfqday") or data.get("day") or []
            normalized = []
            for b in bars:
                if not isinstance(b, list) or len(b) < 5:
                    continue
                try:
                    normalized.append({
                        "trade_date": b[0],
                        "high": float(b[3]),
                        "low": float(b[4]),
                    })
                except (ValueError, TypeError):
                    continue
            return normalized
        except Exception:
            logger.warning("Tencent daily kline exception for %s", secid, exc_info=True)
            return []

    @staticmethod
    def _get_tencent_kline_52w(secid: str) -> tuple:
        """兼容旧调用：返回固定 1 年窗口的高低点及日期。"""
        today = datetime.now().date()
        period_start = DataFetcher._subtract_months(today, 12)
        bars = []
        for bar in DataFetcher._get_tencent_daily_bars(secid):
            try:
                trade_date = datetime.fromisoformat(str(bar["trade_date"])[:10]).date()
                if period_start <= trade_date <= today:
                    bars.append((trade_date, float(bar["high"]), float(bar["low"])))
            except (KeyError, TypeError, ValueError):
                continue
        if not bars:
            return None, None, None, None
        high_date, high, low_date, low = DataFetcher._window_extremes(bars)
        return (
            high, low, high_date.isoformat(), low_date.isoformat(),
        )

    # ── 工具方法 ──────────────────────────────────────────────

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
