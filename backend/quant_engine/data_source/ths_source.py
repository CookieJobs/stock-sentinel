"""同花顺金融数据 API 客户端与因子源（fuyao.aicubes.cn）

调研结论（2026-08-20，见 .scratch/ths-integration/PRD.md）：
- REST Base URL: https://fuyao.aicubes.cn，请求头 `X-api-key` 鉴权
- 统一信封 ApiResponse：HTTP 恒 200，业务状态码经 code 表达（0=成功，2001=无/无效 key，
  2003=无权限，1001/1002=参数错误，5002/5003=上游异常）
- 已确认对我们有用的接口：
  * /api/a-share/valuations/snapshot  —— 批量估值快照（≤100 thscodes/次，PE-TTM/MRQ、PB、PS、PCF）
  * /api/a-share/financials/indicators —— 单股五类财务指标（成长/盈利/偿债/营运/现金流）
  * /api/a-share/prices/snapshot       —— 行情快照（批量或全市场分页）

当前接入：THSValuationFactorSource 走因子降级链（估值因子，官方数据）；
财务指标留作个股级 enrichment（5552 只逐股调用太重，先做按需）。
"""
import logging
import os
from typing import Dict, List, Optional

import pandas as pd
import requests

from .base import FactorSourceBase

logger = logging.getLogger(__name__)

THS_BASE_URL = "https://fuyao.aicubes.cn"
BATCH_SIZE = 100          # valuations/snapshot 单次最多 100 个 thscode

# 财务指标 index_id → 我们的因子列（FACTOR_REGISTRY 键）
INDICATOR_MAP = {
    # growth 成长
    "operating_income_yoy_growth_ratio": "revenue_yoy",
    "net_profit_yoy_growth_ratio": "profit_yoy",
    # profitability 盈利
    "index_weighted_avg_roe": "roe",
    "total_assets_net_ratio": "roa",
    "sale_gross_margin": "gross_margin",
    "sale_net_interest_ratio": "net_margin",
    # solvency 偿债
    "assets_debt_ratio": "debt_ratio",
}
# 反查：我们的因子列 → 报告期能力块
_INDICATOR_ABILITY = {
    "revenue_yoy": "growth", "profit_yoy": "growth",
    "roe": "profitability", "roa": "profitability",
    "gross_margin": "profitability", "net_margin": "profitability",
    "debt_ratio": "solvency",
}


class THSApiClient:
    """同花顺数据 API 客户端（信封解析 + 错误码翻译）"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key if api_key is not None else os.environ.get("THS_API_KEY", "")
        self.session = requests.Session()
        self.session.headers.update({
            "X-api-key": self.api_key,
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        })

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        """GET 并解析 ApiResponse 信封；code!=0 抛 ValueError"""
        if not self.api_key:
            raise ValueError("THS_API_KEY 未配置（.env 中设置）")
        resp = self.session.get(f"{THS_BASE_URL}{path}", params=params, timeout=20)
        try:
            data = resp.json()
        except ValueError:
            raise ValueError(f"THS {path} 响应非 JSON: HTTP {resp.status_code}")
        if data.get("code") != 0:
            raise ValueError(
                f"THS {path} 失败 code={data.get('code')} msg={data.get('message')} "
                f"(2001=无/无效key 2003=无权限 5002/5003=上游异常)"
            )
        return data.get("data") or {}

    # ── 估值快照（批量，≤100/次） ─────────────────────────────

    def valuations_snapshot(self, thscodes: List[str]) -> List[dict]:
        out: List[dict] = []
        for i in range(0, len(thscodes), BATCH_SIZE):
            batch = thscodes[i:i + BATCH_SIZE]
            data = self._get("/api/a-share/valuations/snapshot",
                             {"thscodes": ",".join(batch)})
            out.extend(data.get("item") or [])
        return out

    # ── 财务指标（单股，按报告期） ────────────────────────────

    def financial_indicators(self, thscode: str, report: str) -> dict:
        """返回 {index_id: value} 扁平字典（value 为原始字符串或 None）"""
        data = self._get("/api/a-share/financials/indicators",
                         {"thscode": thscode, "report": report})
        flat: Dict[str, Optional[str]] = {}
        for ability in data.get("abilities") or []:
            for ind in ability.get("indicators") or []:
                flat[ind["index_id"]] = ind.get("value")
        return flat

    def financial_indicators_mapped(self, thscode: str, report: str) -> Dict[str, Optional[float]]:
        """财务指标 → 我们的因子列（INDICATOR_MAP），数值化，None 保留"""
        flat = self.financial_indicators(thscode, report)
        out: Dict[str, Optional[float]] = {}
        for index_id, col in INDICATOR_MAP.items():
            v = flat.get(index_id)
            if v is None:
                out[col] = None
            else:
                try:
                    out[col] = float(v)
                except (TypeError, ValueError):
                    out[col] = None
        return out


def latest_report(year: int, month: int) -> str:
    """按当前年月推断最近报告期（yyyy-1 一季报 / 2 中报 / 3 三季报 / 4 年报）"""
    quarter = (month - 1) // 3 + 1
    return f"{year}-{quarter}"


def ticker_to_thscode(ticker: str, exchange: Optional[str] = None) -> str:
    """6 位代码 → thscode；exchange 可显式给（SSE/SZSE/BSE），否则按前缀推断"""
    ticker = ticker.strip().upper()
    if exchange:
        ex = exchange.upper()
        if ex in ("SSE", "SH"):
            return f"{ticker}.SH"
        if ex in ("SZSE", "SZ"):
            return f"{ticker}.SZ"
        if ex in ("BSE", "BJ"):
            return f"{ticker}.BJ"
    if ticker.startswith(("6", "9")):
        return f"{ticker}.SH"
    if ticker.startswith(("4", "8")):
        return f"{ticker}.BJ"
    return f"{ticker}.SZ"


class THSValuationFactorSource(FactorSourceBase):
    """同花顺估值因子源：全 A 股 PE/PB/PS 快照（官方数据，批量 ≤100/次）

    代码列表复用本地 ts_universe_cache（Tushare stock_basic 缓存）；
    无缓存或无 THS_API_KEY 时返回空 df，让降级链继续。
    """

    name = "ths_valuations"
    required_env = "THS_API_KEY"

    def __init__(self):
        self.client = THSApiClient()

    def get_universe(self) -> pd.DataFrame:
        from ..db import get_quant_db
        db = get_quant_db()
        try:
            rows = db.execute(
                "SELECT ticker, exchange FROM ts_universe_cache ORDER BY ticker"
            ).fetchall()
        finally:
            db.close()
        if not rows:
            logger.warning("ts_universe_cache 为空，THS 估值源无法取代码表")
            return pd.DataFrame()
        thscodes = [ticker_to_thscode(r["ticker"], r["exchange"]) for r in rows]

        try:
            items = self.client.valuations_snapshot(thscodes)
        except ValueError as e:
            logger.warning("THS valuations failed: %s", e)
            return pd.DataFrame()
        if not items:
            return pd.DataFrame()

        df = pd.DataFrame(items)
        if "ticker" not in df.columns:
            # 响应字段可能是 thscode；统一产出 ticker
            df["ticker"] = df.get("thscode", "").astype(str).str.split(".").str[0]
        df["ticker"] = df["ticker"].astype(str).str.zfill(6)
        df["market"] = "CN"
        keep = ["ticker", "market"]
        for src, dst in (("pe_ttm", "pe_ttm"), ("pe_mrq", "pe_mrq"),
                         ("pb", "pb"), ("ps_ttm", "ps_ttm"), ("pcf_ttm", "pcf_ttm")):
            if src in df.columns:
                df[dst] = pd.to_numeric(df[src], errors="coerce")
                keep.append(dst)
        logger.info("THS valuations universe: %d rows", len(df))
        return df[[c for c in keep if c in df.columns]].reset_index(drop=True)
