"""股票自选分组的持久化服务。"""
import sqlite3

from database import get_db
from models import StockGroupResponse


class StockGroupService:
    """管理可多重归属的自选股票分组。"""

    @staticmethod
    def _normalize_name(name: str) -> str:
        normalized = name.strip()
        if not normalized:
            raise ValueError("分组名称不能为空")
        return normalized

    @staticmethod
    def _response_from_row(row: sqlite3.Row) -> StockGroupResponse:
        stock_ids = [int(value) for value in (row["stock_ids"] or "").split(",") if value]
        return StockGroupResponse(
            id=row["id"],
            name=row["name"],
            stock_ids=stock_ids,
            stock_count=len(stock_ids),
            created_at=row["created_at"],
        )

    def list_groups(self) -> list[StockGroupResponse]:
        db = get_db()
        try:
            rows = db.execute(
                """
                SELECT g.id, g.name, g.created_at,
                       GROUP_CONCAT(m.stock_id) AS stock_ids
                FROM stock_groups AS g
                LEFT JOIN stock_group_members AS m ON m.group_id = g.id
                GROUP BY g.id
                ORDER BY g.id
                """
            ).fetchall()
            return [self._response_from_row(row) for row in rows]
        finally:
            db.close()

    def _get_group(self, db: sqlite3.Connection, group_id: int) -> StockGroupResponse:
        row = db.execute(
            """
            SELECT g.id, g.name, g.created_at,
                   GROUP_CONCAT(m.stock_id) AS stock_ids
            FROM stock_groups AS g
            LEFT JOIN stock_group_members AS m ON m.group_id = g.id
            WHERE g.id = ?
            GROUP BY g.id
            """,
            (group_id,),
        ).fetchone()
        if not row:
            raise KeyError("分组未找到")
        return self._response_from_row(row)

    def create_group(self, name: str) -> StockGroupResponse:
        normalized = self._normalize_name(name)
        db = get_db()
        try:
            try:
                cursor = db.execute("INSERT INTO stock_groups (name) VALUES (?)", (normalized,))
                db.commit()
            except sqlite3.IntegrityError as exc:
                raise ValueError("分组名称已存在") from exc
            row = db.execute(
                "SELECT id, name, created_at, '' AS stock_ids FROM stock_groups WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
            return self._response_from_row(row)
        finally:
            db.close()

    def add_stocks(self, group_id: int, stock_ids: list[int]) -> StockGroupResponse:
        """向分组添加股票；已有成员保持幂等。"""
        unique_ids = list(dict.fromkeys(stock_ids))
        db = get_db()
        try:
            self._get_group(db, group_id)
            placeholders = ", ".join("?" for _ in unique_ids)
            rows = db.execute(
                f"SELECT id FROM stocks WHERE id IN ({placeholders})", unique_ids
            ).fetchall()
            existing_ids = {row["id"] for row in rows}
            missing_ids = sorted(set(unique_ids) - existing_ids)
            if missing_ids:
                raise KeyError(f"股票未找到: {', '.join(str(value) for value in missing_ids)}")
            db.executemany(
                "INSERT OR IGNORE INTO stock_group_members (group_id, stock_id) VALUES (?, ?)",
                [(group_id, stock_id) for stock_id in unique_ids],
            )
            db.commit()
            return self._get_group(db, group_id)
        finally:
            db.close()

    def rename_group(self, group_id: int, name: str) -> StockGroupResponse:
        """重命名分组，并保持成员关系不变。"""
        normalized = self._normalize_name(name)
        db = get_db()
        try:
            self._get_group(db, group_id)
            try:
                db.execute("UPDATE stock_groups SET name = ? WHERE id = ?", (normalized, group_id))
                db.commit()
            except sqlite3.IntegrityError as exc:
                raise ValueError("分组名称已存在") from exc
            return self._get_group(db, group_id)
        finally:
            db.close()

    def remove_stocks(self, group_id: int, stock_ids: list[int]) -> StockGroupResponse:
        """只移除当前分组归属，不影响股票或其他分组。"""
        unique_ids = list(dict.fromkeys(stock_ids))
        db = get_db()
        try:
            self._get_group(db, group_id)
            placeholders = ", ".join("?" for _ in unique_ids)
            db.execute(
                f"DELETE FROM stock_group_members WHERE group_id = ? AND stock_id IN ({placeholders})",
                [group_id, *unique_ids],
            )
            db.commit()
            return self._get_group(db, group_id)
        finally:
            db.close()

    def delete_group(self, group_id: int) -> bool:
        """删除分组和归属；外键级联确保股票记录不受影响。"""
        db = get_db()
        try:
            cursor = db.execute("DELETE FROM stock_groups WHERE id = ?", (group_id,))
            db.commit()
            return cursor.rowcount > 0
        finally:
            db.close()
