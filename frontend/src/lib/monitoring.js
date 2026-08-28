export const DRAWDOWN_WINDOWS = ['3m', '6m', '1y']

export const DRAWDOWN_WINDOW_LABELS = {
  '3m': '3个月',
  '6m': '6个月',
  '1y': '1年',
}

export function getMonitoringMetric(stock, window) {
  const metric = stock?.drawdown_windows?.[window]
  if (!metric || metric.status !== 'ok') {
    return {
      status: metric?.status || 'unavailable',
      period_start: metric?.period_start || null,
      as_of: metric?.as_of || null,
      drawdown: null,
      high: null,
      high_date: null,
      low: null,
      low_date: null,
      distance_low_pct: null,
    }
  }
  return metric
}

export function getMonitoringSortValue(stock, key, window) {
  if (key === 'drawdown') return getMonitoringMetric(stock, window).drawdown
  return stock?.[key] ?? null
}

export function getOneYearAlertState(stock) {
  if (!stock?.alert_enabled || stock.threshold == null || stock.threshold <= 0) return 'disabled'
  if (stock.drawdown == null) return 'unavailable'
  return stock.drawdown <= -Math.abs(stock.threshold) ? 'breached' : 'monitoring'
}

export function getPriceHistoryUrl(apiBase, ticker, window) {
  return `${apiBase}/history/${encodeURIComponent(ticker)}?days=30&window=${encodeURIComponent(window)}`
}

export function getMetricStateLabel(metric) {
  return metric?.status === 'insufficient_history' ? '数据不足' : '暂无数据'
}
