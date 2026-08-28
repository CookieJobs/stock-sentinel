import assert from 'node:assert/strict'
import test from 'node:test'

import { MODE_DEFAULTS, addStock, buildRunPayload, validateSelection } from './backtest-flow.js'

test('single mode maps to the existing moving-average strategy', () => {
  assert.deepEqual(MODE_DEFAULTS.single, {
    strategy: 'ma_cross',
    params: { fast: 5, slow: 20 },
    rebalance_freq: 'none',
  })
})

test('adds a stock once and keeps its searchable metadata', () => {
  const stock = { ticker: '600519', name: '贵州茅台', market: 'CN' }
  assert.deepEqual(addStock([], stock), [stock])
  assert.deepEqual(addStock([stock], stock), [stock])
})

test('rejects a portfolio with fewer than two stocks', () => {
  assert.deepEqual(
    validateSelection('portfolio', [{ ticker: '600519', name: '贵州茅台', market: 'CN' }]),
    { error: '组合回测请至少选择两只同市场股票' },
  )
})

test('rejects stocks from different markets', () => {
  assert.deepEqual(
    validateSelection('single', [
      { ticker: '600519', name: '贵州茅台', market: 'CN' },
      { ticker: 'AAPL', name: '苹果', market: 'US' },
    ]),
    { error: '同一次回测请选择同一市场的股票' },
  )
})

test('builds the existing API payload from selected stocks', () => {
  const form = { name: '贵州茅台趋势回测', strategy: 'ma_cross', params: { fast: 5, slow: 20 } }
  const stocks = [{ ticker: '600519', name: '贵州茅台', market: 'CN' }]
  assert.deepEqual(buildRunPayload(form, stocks), {
    name: '贵州茅台趋势回测',
    strategy: 'ma_cross',
    params: { fast: 5, slow: 20 },
    tickers: ['600519'],
    market: 'CN',
  })
})
