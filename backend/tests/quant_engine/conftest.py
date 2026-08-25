"""量化测试套件共享 fixture — 临时 DB 隔离

防止跑测试读写真实 `data/sentinel.db`：
- `test_api.py` 的 `test_factors_refresh` 会跑真实数据源链（BaoStock/AkShare/Mock），
  把 Mock 因子数据（3853 只 × 6 因子）写进真实库；
- `test_portfolio.py` 的组合 CRUD 也会往真实库插 portfolios / holdings。

与 `backend/test_briefing.py` / `backend/test_price_history.py` 的临时库模式保持一致。

注意：`quant_engine/db.py` 通过 `from database import DB_PATH` 在 import 时取值绑定，
所以必须**同时**重定向 `database.DB_PATH` 与 `quant_engine.db.DB_PATH`；
前者影响 `database.get_db()`（调用时解析模块全局），后者影响 `get_quant_db()`。
"""
import sys
import tempfile
from pathlib import Path

# 保证 backend 在 sys.path 中（与各测试文件相同约定）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import database
import quant_engine.db as qdb

_TMP_DIR = tempfile.mkdtemp(prefix="sentinel_quant_test_")
_TEST_DB = Path(_TMP_DIR) / "sentinel_test.db"

# 所有 get_db() / get_quant_db() 走临时库，真实库保持只读不动
database.DB_PATH = _TEST_DB
qdb.DB_PATH = _TEST_DB
