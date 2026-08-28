import test from 'node:test'
import assert from 'node:assert/strict'

import {
  getOneYearAlertState,
  getMonitoringMetric,
  getMonitoringSortValue,
  getPriceHistoryUrl,
} from '../src/lib/monitoring.js'

const stock = {
  ticker: 'AAPL',
  drawdown_windows: {
    '3m': { status: 'ok', drawdown: -6.25, high: 220, high_date: '2026-08-01' },
    '6m': { status: 'ok', drawdown: -12.5, high: 235, high_date: '2026-05-01' },
    '1y': { status: 'ok', drawdown: -20, high: 260, high_date: '2025-10-01' },
  },
}

test('uses the selected drawdown window instead of the legacy 1-year field', () => {
  assert.equal(getMonitoringMetric(stock, '3m').drawdown, -6.25)
  assert.equal(getMonitoringMetric(stock, '6m').high, 235)
  assert.equal(getMonitoringSortValue(stock, 'drawdown', '3m'), -6.25)
})

test('keeps unavailable history explicit rather than silently using another period', () => {
  const unavailable = getMonitoringMetric({ ticker: 'AAPL', drawdown_windows: {} }, '3m')

  assert.equal(unavailable.status, 'unavailable')
  assert.equal(getMonitoringSortValue({ drawdown_windows: {} }, 'drawdown', '3m'), null)
})

test('builds a local history request and derives risk only from the fixed 1-year threshold', () => {
  assert.equal(getPriceHistoryUrl('/api', 'BRK/B', '6m'), '/api/history/BRK%2FB?days=30&window=6m')
  assert.equal(getOneYearAlertState({ alert_enabled: true, threshold: 15, drawdown: -20 }), 'breached')
  assert.equal(getOneYearAlertState({ alert_enabled: true, threshold: 15, drawdown: -10 }), 'monitoring')
  assert.equal(getOneYearAlertState({ alert_enabled: true, threshold: 15, drawdown: null }), 'unavailable')
  assert.equal(getOneYearAlertState({ alert_enabled: false, threshold: 15, drawdown: -20 }), 'disabled')
})
