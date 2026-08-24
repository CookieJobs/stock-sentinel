"""Self-contained smoke test for data_fetcher.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib.util
spec = importlib.util.spec_from_file_location(
    'data_fetcher',
    os.path.join(os.path.dirname(__file__), 'data_fetcher.py'))
df = importlib.util.module_from_spec(spec)
spec.loader.exec_module(df)

DataFetcher = df.DataFetcher
_SECTOR_MAP = df._SECTOR_MAP

# test detect_market
assert DataFetcher.detect_market('AAPL') == 'US'
assert DataFetcher.detect_market('600519') == 'CN'
assert DataFetcher.detect_market('00700') == 'HK'
assert DataFetcher.detect_market('01810') == 'HK'
assert DataFetcher.detect_market('1') == 'HK'
assert DataFetcher.detect_market('AAPL.HK') == 'HK'
print('detect_market: PASS')

# test _hk_secid
assert DataFetcher._hk_secid('700') == '116.00700'
assert DataFetcher._hk_secid('1810') == '116.01810'
assert DataFetcher._hk_secid('1') == '116.00001'
print('_hk_secid: PASS')

# test calculate_drawdown
assert DataFetcher.calculate_drawdown(90, 100) == -10.0
assert DataFetcher.calculate_drawdown(50, 100) == -50.0
assert DataFetcher.calculate_drawdown(None, 100) is None
assert DataFetcher.calculate_drawdown(100, 0) is None
print('calculate_drawdown: PASS')

# test get_market_status
assert DataFetcher.get_market_status(-25) == 'alert'
assert DataFetcher.get_market_status(-20) == 'alert'
assert DataFetcher.get_market_status(-15) == 'warning'
assert DataFetcher.get_market_status(-10) == 'warning'
assert DataFetcher.get_market_status(-5) == 'normal'
assert DataFetcher.get_market_status(None) == 'normal'
print('get_market_status: PASS')

# test 全部数据源失败 → 返回 None（不造假数据）
_orig_fetch = {
    '_get_finnhub_quote': DataFetcher._get_finnhub_quote,
    '_get_eastmoney_quote': DataFetcher._get_eastmoney_quote,
    '_get_eastmoney_hk_quote': DataFetcher._get_eastmoney_hk_quote,
    '_get_tencent_quote': DataFetcher._get_tencent_quote,
}
for _name in _orig_fetch:
    setattr(DataFetcher, _name, staticmethod(lambda *a, **k: None))
try:
    for t, m in [('AAPL', 'US'), ('600519', 'CN'), ('00700', 'HK')]:
        r = DataFetcher.get_stock_info(t)
        assert r is None, f'{m} 应返回 None（无假数据），实际 {r}'
    print('No-data → None: PASS')
finally:
    for _name, _orig in _orig_fetch.items():
        setattr(DataFetcher, _name, _orig)

# test _tencent_secid（纯函数：CN sh/sz 前缀，HK hk 前缀）
assert DataFetcher._tencent_secid('600519', 'CN') == 'sh600519'
assert DataFetcher._tencent_secid('000001', 'CN') == 'sz000001'
assert DataFetcher._tencent_secid('300750', 'CN') == 'sz300750'
assert DataFetcher._tencent_secid('00700', 'HK') == 'hk00700'
assert DataFetcher._tencent_secid('1810', 'HK') == 'hk01810'
print('_tencent_secid: PASS')

# test 东财失败自动降级腾讯（确定性 mock：东财→None，腾讯→固定 dict）
_orig_em = DataFetcher._get_eastmoney_quote
_orig_emh = DataFetcher._get_eastmoney_hk_quote
_orig_tq = DataFetcher._get_tencent_quote
DataFetcher._get_eastmoney_quote = staticmethod(lambda *a, **k: None)
DataFetcher._get_eastmoney_hk_quote = staticmethod(lambda *a, **k: None)
DataFetcher._get_tencent_quote = staticmethod(
    lambda ticker, market: {"ticker": ticker, "name": "X", "current_price": 100.0,
                            "change_pct": 1.0, "drawdown": -10.0, "week52_high": 110.0,
                            "week52_low": 90.0, "pe_ratio": 10.0, "source": "tencent"}
)
try:
    cn = DataFetcher.get_stock_info('600519')
    hk = DataFetcher.get_stock_info('00700')
    assert cn['source'] == 'tencent' and cn['market'] == 'CN', cn
    assert hk['source'] == 'tencent' and hk['market'] == 'HK', hk
    print('Tencent fallback: PASS')
finally:
    DataFetcher._get_eastmoney_quote = _orig_em
    DataFetcher._get_eastmoney_hk_quote = _orig_emh
    DataFetcher._get_tencent_quote = _orig_tq

print()
print('ALL TESTS PASSED')

# test 用户钉住实时源：realtime=tencent → 腾讯优先调用
import datasource_config as _dsc
_orig_override = _dsc.get_override
_dsc.get_override = staticmethod(lambda domain: "tencent" if domain == "realtime" else None)
_orig_em3 = DataFetcher._get_eastmoney_quote
_orig_tq3 = DataFetcher._get_tencent_quote
DataFetcher._get_eastmoney_quote = staticmethod(
    lambda *a, **k: {"ticker": "600519", "name": "EM", "current_price": 1.0})
DataFetcher._get_tencent_quote = staticmethod(
    lambda *a, **k: {"ticker": "600519", "name": "TX", "current_price": 2.0})
try:
    r = DataFetcher.get_stock_info('600519')
    assert r['source'] == 'tencent', f"钉住 tencent 应优先腾讯，实际 {r['source']}"
    print('Realtime source override: PASS')
finally:
    DataFetcher._get_eastmoney_quote = _orig_em3
    DataFetcher._get_tencent_quote = _orig_tq3
    _dsc.get_override = _orig_override

print()
print('ALL TESTS PASSED')
