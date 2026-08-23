"""事件日历服务 — Tushare 分红送转 + 限售解禁

数据源：Tushare Pro（需 TUSHARE_TOKEN）
- dividend   : 分红送转，按除权除息日（ex_date）落日历
- share_float: 限售解禁，按解禁日（float_date）落日历

限流防御：先按事件日区间查询；接口不支持区间参数时退化为公告日宽窗口 + 客户端过滤。
"""
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import requests

from .db import get_quant_db

logger = logging.getLogger(__name__)

TUSHARE_URL = "http://api.tushare.pro"


def _token() -> str:
    return os.environ.get("TUSHARE_TOKEN", "")


def _ts_call(api_name: str, params: dict, fields: str = ""):
    """调用 Tushare 接口，成功返回 (fields, items)，失败返回 None"""
    if not _token():
        return None
    try:
        resp = requests.post(
            TUSHARE_URL,
            json={"api_name": api_name, "token": _token(), "params": params, "fields": fields},
            timeout=30,
        )
        data = resp.json()
    except Exception as e:
        logger.warning("Tushare %s request failed: %s", api_name, e)
        return None
    if data.get("code") != 0:
        logger.warning("Tushare %s failed: %s", api_name, data.get("msg"))
        return None
    df = data.get("data", {})
    return df.get("fields", []), df.get("items", [])


def _norm_date(d: Optional[str]) -> Optional[str]:
    """YYYYMMDD → YYYY-MM-DD；无法识别返回原值"""
    if not d:
        return None
    d = str(d).strip()
    if len(d) == 8 and d.isdigit():
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    return d


def _fetch_dividend(start: str, end: str) -> list:
    """分红送转事件 → [(event_date, ticker, title, detail_json), ...]"""
    fields = "ts_code,end_date,ann_date,div_proc,stk_div,record_date,ex_date,pay_date"
    ss = start.replace("-", "")
    ee = end.replace("-", "")
    result = None
    # 策略 1：按 ex_date 区间查
    result = _ts_call("dividend", {"ex_date": f"{ss},{ee}"}, fields)
    # 策略 2：退化按 ann_date 宽窗口查 + 客户端过滤
    if result is None:
        wide_start = (datetime.strptime(start, "%Y-%m-%d") - timedelta(days=180)).strftime("%Y%m%d")
        result = _ts_call("dividend", {"ann_date": f"{wide_start},{ee}"}, fields)
    if not result:
        return []
    fields_list, items = result
    fmap = {f: i for i, f in enumerate(fields_list)}

    def g(item, key):
        i = fmap.get(key)
        return item[i] if i is not None and i < len(item) else None

    out = []
    for item in items:
        ex_date = _norm_date(g(item, "ex_date") or g(item, "record_date") or g(item, "end_date"))
        if not ex_date or not (start <= ex_date <= end):
            continue
        ticker = str(g(item, "ts_code") or "").split(".")[0]
        stk_div = g(item, "stk_div")
        div_proc = g(item, "div_proc") or ""
        if stk_div:
            title = f"分红送转：每股派息 {stk_div} 元（{div_proc}）"
        else:
            title = f"分红送转：{div_proc}"
        detail = json.dumps({
            "stk_div": stk_div, "div_proc": div_proc,
            "record_date": _norm_date(g(item, "record_date")),
            "pay_date": _norm_date(g(item, "pay_date")),
        }, ensure_ascii=False)
        out.append((ex_date, ticker, title, detail))
    return out


def _fetch_share_float(start: str, end: str) -> list:
    """限售解禁事件 → [(event_date, ticker, title, detail_json), ...]"""
    fields = "ts_code,float_date,float_share,float_ratio,holder_name,share_type"
    ss = start.replace("-", "")
    ee = end.replace("-", "")
    result = None
    # 策略 1：按 float_date 区间查
    result = _ts_call("share_float", {"float_date": f"{ss},{ee}"}, fields)
    # 策略 2：退化按公告日宽窗口查 + 客户端过滤
    if result is None:
        wide_start = (datetime.strptime(start, "%Y-%m-%d") - timedelta(days=180)).strftime("%Y%m%d")
        result = _ts_call("share_float", {"start_date": wide_start, "end_date": ee}, fields)
    if not result:
        return []
    fields_list, items = result
    fmap = {f: i for i, f in enumerate(fields_list)}

    def g(item, key):
        i = fmap.get(key)
        return item[i] if i is not None and i < len(item) else None

    out = []
    for item in items:
        f_date = _norm_date(g(item, "float_date"))
        if not f_date or not (start <= f_date <= end):
            continue
        ticker = str(g(item, "ts_code") or "").split(".")[0]
        float_share = g(item, "float_share")
        float_ratio = g(item, "float_ratio")
        share_type = g(item, "share_type") or ""
        holder = g(item, "holder_name") or ""
        ratio_txt = f"（占流通 {float_ratio}%）" if float_ratio is not None else ""
        share_txt = f"{float_share} 股" if float_share is not None else ""
        title = f"限售解禁：{share_txt}{ratio_txt}，{share_type}"
        detail = json.dumps({
            "float_share": float_share, "float_ratio": float_ratio,
            "holder_name": holder, "share_type": share_type,
        }, ensure_ascii=False)
        out.append((f_date, ticker, title, detail))
    return out


def _fetch_ths_corporate_actions(start: str, end: str) -> list:
    """同花顺公司行为（分红/送股，监控股票，无配额依赖）
    → [(event_date, ticker, title, detail_json), ...]"""
    if not os.environ.get("THS_API_KEY"):
        return []
    from .data_source.ths_source import THSApiClient, ticker_to_thscode
    from .ths_service import get_monitored_tickers
    tickers = get_monitored_tickers()
    if not tickers or len(tickers) > 300:
        return []
    client = THSApiClient()
    out = []
    for ticker in tickers:
        try:
            data = client._get(
                "/api/a-share/corporate-actions/adjustment-factors",
                {"thscode": ticker_to_thscode(ticker), "from": start, "to": end},
            )
        except ValueError as e:
            logger.debug("THS corp-actions %s failed: %s", ticker, e)
            continue
        for it in data.get("item") or []:
            ex_ms = it.get("ex_date_ms")
            if not ex_ms:
                continue
            event_date = datetime.fromtimestamp(ex_ms / 1000).strftime("%Y-%m-%d")
            if not (start <= event_date <= end):
                continue
            div = it.get("dividend_per_share")
            bonus = it.get("per_share_bonus")
            parts = []
            if div:
                parts.append(f"每股派息 {div} 元")
            if bonus:
                parts.append(f"每股送转 {bonus} 股")
            title = "分红送转：" + "、".join(parts) if parts else "分红送转"
            detail = json.dumps({
                "dividend_per_share": div, "per_share_bonus": bonus, "source": "ths",
            }, ensure_ascii=False)
            out.append((event_date, ticker, title, detail))
    logger.info("THS corporate-actions: %d events", len(out))
    return out


def refresh_events(start: str, end: str) -> dict:
    """拉取 [start, end] 区间的事件并入库存，返回 {inserted, dividend, share_float, ths_dividend}"""
    if not _token():
        logger.warning("TUSHARE_TOKEN not set, skip events refresh")
        return {"inserted": 0, "dividend": 0, "share_float": 0, "ths_dividend": 0,
                "error": "TUSHARE_TOKEN not set"}

    dividend_rows = _fetch_dividend(start, end)
    float_rows = _fetch_share_float(start, end)
    ths_rows = _fetch_ths_corporate_actions(start, end)
    rows = [(d, t, "dividend", title, detail) for d, t, title, detail in dividend_rows]
    rows += [(d, t, "share_float", title, detail) for d, t, title, detail in float_rows]
    rows += [(d, t, "dividend", title, detail) for d, t, title, detail in ths_rows]
    if not rows:
        return {"inserted": 0, "dividend": len(dividend_rows),
                "share_float": len(float_rows), "ths_dividend": len(ths_rows)}

    now = datetime.now().isoformat()
    db = get_quant_db()
    try:
        db.executemany(
            """INSERT OR REPLACE INTO quant_events
               (event_date, ticker, name, event_type, title, detail, updated_at)
               VALUES (?, ?, NULL, ?, ?, ?, ?)""",
            [(d, t, et, title, detail, now) for d, t, et, title, detail in rows],
        )
        db.commit()
    finally:
        db.close()
    return {"inserted": len(rows), "dividend": len(dividend_rows),
            "share_float": len(float_rows), "ths_dividend": len(ths_rows)}


def list_events(start: str, end: str, event_type: Optional[str] = None, limit: int = 300) -> list:
    """查询事件列表（按日期升序）"""
    sql = ("SELECT id, event_date, ticker, name, event_type, title, detail "
           "FROM quant_events WHERE event_date >= ? AND event_date <= ?")
    params: list = [start, end]
    if event_type:
        sql += " AND event_type = ?"
        params.append(event_type)
    sql += " ORDER BY event_date ASC, event_type, ticker LIMIT ?"
    params.append(limit)
    db = get_quant_db()
    try:
        rows = db.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()
