// frontend/src/lib/api.js
// 量化引擎 API 客户端（v1.0 — M1/M3/M4/M5）
//
// 设计：
// - 开发模式：Vite proxy 转发 /api → :8000，BASE = ''
// - 生产模式：FastAPI 直接服务前端，BASE = ''（相对路径）
// - 自定义后端地址：VITE_API_BASE 环境变量（如 http://api.example.com）
//
// 重构记录：
// - 2026-06-05 重建：M1b commit 漏提交此文件（页面 import 一直指向不存在的模块）
// - 用 fetch（不引 axios），保持依赖最小

const BASE = import.meta.env.VITE_API_BASE || ''

// ── 基础请求 ──────────────────────────────────────
async function request(path, options = {}) {
  const url = `${BASE}${path}`
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (!res.ok) {
    let detail
    try {
      const body = await res.json()
      detail = body.detail || JSON.stringify(body)
    } catch {
      try { detail = await res.text() } catch { detail = res.statusText }
    }
    throw new Error(`API ${res.status} ${path}: ${detail || '请求失败'}`)
  }
  if (res.status === 204) return null
  return res.json()
}

function qs(params) {
  if (!params) return ''
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v != null) sp.append(k, v)
  }
  const s = sp.toString()
  return s ? `?${s}` : ''
}

const get    = (path, params)       => request(path + qs(params))
const post   = (path, body, params) => request(path + qs(params), { method: 'POST', body: JSON.stringify(body || {}) })
const put    = (path, body)         => request(path, { method: 'PUT',  body: JSON.stringify(body || {}) })
const del    = (path)               => request(path, { method: 'DELETE' })

// ── Backtest（M4） ────────────────────────────────
export const backtest = {
  strategies:    ()                              => get('/api/quant/backtest/strategies'),
  templates:     ()                              => get('/api/quant/backtest/templates'),
  listRecent:    (limit = 20)                    => get('/api/quant/backtest/list/recent', { limit }),
  run:           (payload)                       => post('/api/quant/backtest/run', payload),
  get:           (id)                            => get(`/api/quant/backtest/${id}`),
}

// ── Factors（M3） ─────────────────────────────────
export const factors = {
  list:          ()                              => get('/api/quant/factors/list'),
  universeStats: ()                              => get('/api/quant/factors/universe/stats'),
  refresh:       ()                              => post('/api/quant/factors/refresh'),
  industries:    ()                              => get('/api/quant/factors/industries'),
  screen:        (filters, rankBy, topN)         => post('/api/quant/factors/screen', {
                                                     filters,
                                                     rank_by: rankBy,
                                                     top_n:   topN,
                                                   }),
}

// ── K-line（M1） ──────────────────────────────────
//
// withIndicators(ticker, opts, specs):
//   ticker: str                 — 股票代码（"sh600519" / "AAPL"）
//   opts:   { market, period, adj, start?, end? } — 查询参数
//   specs:  [{name, params}]    — 指标规格
//
// 后端 payload: { "indicators": specs }
export const kline = {
  withIndicators: (ticker, opts = {}, specs = []) => {
    const { market = 'CN', period = '1d', adj = 'qfq', start, end } = opts
    return post(
      `/api/quant/kline/${encodeURIComponent(ticker)}/with-indicators`,
      { indicators: specs },
      { market, period, adj, start, end },
    )
  },
}

// ── Portfolios（M5） ──────────────────────────────
export const portfolios = {
  list:           ()                              => get('/api/quant/portfolios/'),
  get:            (id)                            => get(`/api/quant/portfolios/${id}`),
  create:         (payload)                       => post('/api/quant/portfolios/', payload),
  delete:         (id)                            => del(`/api/quant/portfolios/${id}`),
  valuation:      (id)                            => get(`/api/quant/portfolios/${id}/valuation`),
  addHolding:     (id, holding)                   => post(`/api/quant/portfolios/${id}/holdings`, holding),
  updateHolding:  (id, ticker, holding)           => put(`/api/quant/portfolios/${id}/holdings/${encodeURIComponent(ticker)}`, holding),
  removeHolding:  (id, ticker)                    => del(`/api/quant/portfolios/${id}/holdings/${encodeURIComponent(ticker)}`),
  rebalance:      (id, threshold, capital)        => get(`/api/quant/portfolios/${id}/rebalance`, { threshold, capital }),
  runBacktest:    (id, payload)                   => post(`/api/quant/portfolios/${id}/run-backtest`, payload),
}

// ── Risk（M5） ────────────────────────────────────
export const risk = {
  benchmarks:     ()                              => get('/api/quant/risk/benchmarks'),
  compute:        (equityCurve, initialCapital)   => post('/api/quant/risk/compute', {
                                                       equity_curve:    equityCurve,
                                                       initial_capital: initialCapital,
                                                     }),
}

export default { backtest, factors, kline, portfolios, risk }
