"""股票品牌 Logo 的本地缓存与上传内容校验。"""
from __future__ import annotations

import base64
import binascii
import re
from typing import Optional
from urllib.parse import urlparse

import requests

from database import get_db


MAX_LOGO_BYTES = 512 * 1024
_ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp"}
_DATA_URL_PATTERN = re.compile(r"^data:([^;,]+);base64,([A-Za-z0-9+/]*={0,2})$")
_FINNHUB_LOGO_HOSTS = {"static.finnhub.io", "static2.finnhub.io"}


def _detect_content_type(content: bytes) -> Optional[str]:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return None


def _validate_logo_bytes(content: bytes, declared_content_type: str) -> str:
    if declared_content_type not in _ALLOWED_CONTENT_TYPES:
        raise ValueError("仅支持 PNG、JPEG 或 WebP 图片")
    if not content:
        raise ValueError("Logo 图片不能为空")
    if len(content) > MAX_LOGO_BYTES:
        raise ValueError("Logo 图片不能超过 512 KiB")
    detected_content_type = _detect_content_type(content)
    if detected_content_type is None:
        raise ValueError("图片内容与声明格式不一致")
    if detected_content_type != declared_content_type:
        raise ValueError("图片内容与声明格式不一致")
    return detected_content_type


def parse_logo_data_url(data_url: str) -> tuple[bytes, str]:
    """解析并校验手动上传的 base64 图片 data URL。"""
    if not isinstance(data_url, str):
        raise ValueError("Logo 上传格式无效")
    match = _DATA_URL_PATTERN.fullmatch(data_url.strip())
    if not match:
        raise ValueError("Logo 上传格式无效")
    content_type = match.group(1).lower()
    encoded = match.group(2)
    try:
        content = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Logo 图片编码无效") from exc
    return content, _validate_logo_bytes(content, content_type)


def save_logo(market: str, ticker: str, content: bytes, content_type: str, source: str) -> None:
    """以市场与代码为键覆盖保存一个已验证的本地 Logo。"""
    validated_content_type = _validate_logo_bytes(content, content_type)
    db = get_db()
    try:
        db.execute(
            """INSERT INTO stock_logos (market, ticker, content, content_type, source, updated_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(market, ticker) DO UPDATE SET
                   content = excluded.content,
                   content_type = excluded.content_type,
                   source = excluded.source,
                   updated_at = excluded.updated_at""",
            (market.upper(), ticker.upper(), content, validated_content_type, source),
        )
        db.commit()
    finally:
        db.close()


def get_logo(market: str, ticker: str) -> Optional[dict]:
    """读取图片二进制和元数据；未缓存时返回 None。"""
    db = get_db()
    try:
        row = db.execute(
            """SELECT content, content_type, source, updated_at
               FROM stock_logos WHERE market = ? AND ticker = ?""",
            (market.upper(), ticker.upper()),
        ).fetchone()
        return dict(row) if row else None
    finally:
        db.close()


def get_logo_metadata(market: str, ticker: str) -> Optional[dict]:
    """只返回构造股票响应所需的缓存元数据，不读取 Blob。"""
    db = get_db()
    try:
        row = db.execute(
            """SELECT content_type, source, updated_at
               FROM stock_logos WHERE market = ? AND ticker = ?""",
            (market.upper(), ticker.upper()),
        ).fetchone()
        return dict(row) if row else None
    finally:
        db.close()


def delete_logo(market: str, ticker: str) -> bool:
    """删除本地缓存，调用方据此回到文字占位。"""
    db = get_db()
    try:
        cursor = db.execute(
            "DELETE FROM stock_logos WHERE market = ? AND ticker = ?",
            (market.upper(), ticker.upper()),
        )
        db.commit()
        return cursor.rowcount > 0
    finally:
        db.close()


def cache_finnhub_logo(market: str, ticker: str, remote_url: Optional[str]) -> bool:
    """从白名单 Finnhub 静态域名缓存未曾保存的美股 Logo。"""
    if (market or "").upper() != "US" or not remote_url:
        return False
    parsed = urlparse(remote_url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in _FINNHUB_LOGO_HOSTS:
        return False
    if get_logo_metadata(market, ticker):
        return False

    response = None
    try:
        response = requests.get(remote_url, timeout=5, stream=True, allow_redirects=False)
        if response.status_code != 200:
            return False
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        chunks = []
        size = 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            chunks.append(chunk)
            size += len(chunk)
            if size > MAX_LOGO_BYTES:
                return False
        save_logo(market, ticker, b"".join(chunks), content_type, "finnhub")
        return True
    except (requests.RequestException, ValueError, TypeError):
        return False
    finally:
        if response is not None:
            response.close()
