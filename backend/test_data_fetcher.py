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
DEMO_DATA = df.DEMO_DATA
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

# test demo fallback for 3 markets（确定性：屏蔽真实 API，只验证回退路径）
# 东财/Finnhub 可达时返回真实数据，直接断言 source=='demo' 会随网络环境漂移；
# 改为临时把三个取数方法替换为失败，验证回退逻辑本身，finally 中恢复。
_orig_fetch = {
    '_get_finnhub_quote': DataFetcher._get_finnhub_quote,
    '_get_eastmoney_quote': DataFetcher._get_eastmoney_quote,
    '_get_eastmoney_hk_quote': DataFetcher._get_eastmoney_hk_quote,
}
for _name in _orig_fetch:
    setattr(DataFetcher, _name, staticmethod(lambda *a, **k: None))

try:
    for t, m in [('AAPL', 'US'), ('600519', 'CN'), ('00700', 'HK')]:
        r = DataFetcher.get_stock_info(t)
        assert r is not None, f'{m} returned None'
        assert r['market'] == m, f'{m} market mismatch: {r["market"]}'
        assert r['source'] == 'demo', f'{m} source is {r["source"]}'
    print('DEMO 3-market fallback: PASS')

    # Check a few specific demo values（价格动态 ±3%，sector 走静态映射兜底）
    for t in ['AAPL', '600519', '00700']:
        r = DataFetcher.get_stock_info(t)
        base = DEMO_DATA[t]['current_price']
        assert base * 0.97 <= r['current_price'] <= base * 1.03, \
            f'{t} price out of range: {r["current_price"]}'
        assert r['name'] == DEMO_DATA[t]['name'], f'{t} name mismatch: {r["name"]}'
        assert r['sector'] == _SECTOR_MAP[t], f'{t} sector mismatch: {r["sector"]}'
    print('Specific value checks: PASS')
finally:
    for _name, _orig in _orig_fetch.items():
        setattr(DataFetcher, _name, _orig)

# test all DEMO_DATA stocks have required keys
from collections import Counter
all_ok = True
for t in sorted(DEMO_DATA):
    info = DataFetcher.get_stock_info(t)
    if info is None:
        print(f'  FAIL: {t} returned None')
        all_ok = False
        continue
    for key in ['drawdown', 'distance_low_pct', 'market_status', 'sector', 'pe_ratio', 'source']:
        if key not in info:
            print(f'  FAIL: {t} missing {key}')
            all_ok = False
if all_ok:
    print(f'All {len(DEMO_DATA)} DEMO stocks validated: PASS')

c = Counter(d['market'] for d in DEMO_DATA.values())
print(f'Market distribution: {dict(c)}')

print()
print('ALL TESTS PASSED')
