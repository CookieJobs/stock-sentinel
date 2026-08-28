export const MODE_DEFAULTS = {
  single: {
    strategy: 'ma_cross',
    params: { fast: 5, slow: 20 },
    rebalance_freq: 'none',
  },
  portfolio: {
    strategy: 'equal_weight',
    params: {},
    rebalance_freq: 'monthly',
  },
}

export function addStock(stocks, stock) {
  const ticker = stock?.ticker?.trim().toUpperCase()
  if (!ticker) return stocks
  const normalized = { ...stock, ticker, market: stock.market || 'CN' }
  if (stocks.some(item => item.ticker === normalized.ticker && item.market === normalized.market)) {
    return stocks
  }
  return [...stocks, normalized]
}

export function validateSelection(mode, stocks) {
  if (!stocks.length) return { error: '请先选择要回测的股票' }

  const markets = new Set(stocks.map(stock => stock.market || 'CN'))
  if (markets.size > 1) return { error: '同一次回测请选择同一市场的股票' }

  if (mode === 'single' && stocks.length !== 1) {
    return { error: '趋势回测请只选择一只股票' }
  }
  if (mode === 'portfolio' && stocks.length < 2) {
    return { error: '组合回测请至少选择两只同市场股票' }
  }
  return { market: stocks[0].market || 'CN' }
}

export function buildRunPayload(form, stocks) {
  const payload = { ...form }
  delete payload.tickers
  delete payload.market
  return {
    ...payload,
    params: Object.fromEntries(
      Object.entries(payload.params || {}).map(([key, value]) => [key, Number(value) || value]),
    ),
    tickers: stocks.map(stock => stock.ticker),
    market: stocks[0]?.market || 'CN',
  }
}
