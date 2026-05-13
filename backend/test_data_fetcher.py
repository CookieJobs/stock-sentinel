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

# test demo fallback for 3 markets
us = DataFetcher.get_stock_info('AAPL')
cn = DataFetcher.get_stock_info('600519')
hk = DataFetcher.get_stock_info('00700')
for r, m in [(us, 'US'), (cn, 'CN'), (hk, 'HK')]:
    assert r is not None, f'{m} returned None'
    assert r['market'] == m, f'{m} market mismatch: {r["market"]}'
    assert r['source'] == 'demo', f'{m} source is {r["source"]}'
print('DEMO 3-market fallback: PASS')

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

# Check a few specific values
aapl = DataFetcher.get_stock_info('AAPL')
assert aapl['current_price'] == 273.17
assert aapl['sector'] == 'Technology'

moutai = DataFetcher.get_stock_info('600519')
assert moutai['current_price'] == 1371.72
assert moutai['sector'] == '白酒'

tencent = DataFetcher.get_stock_info('00700')
assert tencent['current_price'] == 485.00
assert tencent['sector'] == '互联网'

print('Specific value checks: PASS')
print()
print('ALL TESTS PASSED')
