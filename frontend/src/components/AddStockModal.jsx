import { useEffect, useState } from 'react'
import { search } from '../lib/api'
import { marketAlternatives } from '../lib/stockSearch'

function candidateKey(candidate) {
  return `${candidate.market}:${candidate.ticker}`
}

function marketLabel(market) {
  if (market === 'CN') return '🇨🇳 A股'
  if (market === 'HK') return '🇭🇰 港股'
  return '🇺🇸 美股'
}

function marketClass(market) {
  if (market === 'CN') return 'bg-sent-yellow/20 text-sent-yellow'
  if (market === 'HK') return 'bg-sent-green/20 text-sent-green'
  return 'bg-sent-blue/20 text-sent-blue'
}

export default function AddStockModal({ onClose, onAdded }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [searchState, setSearchState] = useState('idle')
  const [searchError, setSearchError] = useState('')
  const [marketChoices, setMarketChoices] = useState(null)
  const [selectedKeys, setSelectedKeys] = useState(new Set())
  const [adding, setAdding] = useState(false)
  const [addError, setAddError] = useState('')

  useEffect(() => {
    const keyword = query.trim()
    setMarketChoices(null)
    setAddError('')
    if (!keyword) {
      setResults([])
      setSearchState('idle')
      setSearchError('')
      return undefined
    }

    let active = true
    const timer = setTimeout(async () => {
      setSearchState('loading')
      setSearchError('')
      try {
        const data = await search.stocks(keyword, { limit: 10 })
        if (!active) return
        setResults(data.results || [])
        setSearchState('ready')
      } catch {
        if (!active) return
        setResults([])
        setSearchState('error')
        setSearchError('搜索暂时不可用，请稍后重试')
      }
    }, 280)

    return () => {
      active = false
      clearTimeout(timer)
    }
  }, [query])

  const addCandidates = async (candidates) => {
    if (!candidates.length) return
    setAdding(true)
    setAddError('')
    const outcomes = await Promise.all(candidates.map(async (candidate) => {
      try {
        const response = await fetch('/api/stocks/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ticker: candidate.ticker, name: candidate.name }),
        })
        const body = await response.json().catch(() => ({}))
        if (!response.ok) {
          return { candidate, error: body.detail || '添加失败' }
        }
        return { candidate, stock: body }
      } catch {
        return { candidate, error: '网络错误，请重试' }
      }
    }))
    setAdding(false)

    const added = outcomes.filter((outcome) => outcome.stock)
    const failed = outcomes.filter((outcome) => outcome.error)
    if (added.length) await onAdded({ added, failed })

    if (failed.length) {
      const details = failed.map(({ candidate, error }) => `${candidate.name}（${candidate.ticker}）：${error}`)
      setAddError(`已添加 ${added.length} 只；${details.join('；')}`)
      return
    }
    onClose()
  }

  const chooseCandidate = (candidate) => {
    const alternatives = marketAlternatives(results, candidate)
    if (!alternatives.length) {
      addCandidates([candidate])
      return
    }
    setMarketChoices(alternatives)
    setSelectedKeys(new Set([candidateKey(candidate)]))
  }

  const toggleChoice = (candidate) => {
    const key = candidateKey(candidate)
    setSelectedKeys((previous) => {
      const next = new Set(previous)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  const selectedChoices = (marketChoices || []).filter((candidate) => selectedKeys.has(candidateKey(candidate)))

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" role="dialog" aria-modal="true" aria-labelledby="add-stock-title">
      <div className="absolute inset-0 bg-black/60" onClick={adding ? undefined : onClose} />
      <div className="relative bg-sent-card border border-sent-border rounded-xl p-6 w-full max-w-md mx-4">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <h3 id="add-stock-title" className="text-lg font-semibold">添加股票</h3>
            <p className="text-xs text-sent-dim mt-1">输入公司名称，选中后自动加入监控。</p>
          </div>
          <button type="button" onClick={onClose} disabled={adding} className="text-sent-dim hover:text-white disabled:opacity-50" aria-label="关闭添加股票">✕</button>
        </div>

        {!marketChoices ? (
          <>
            <label className="block text-xs text-sent-dim mb-1" htmlFor="stock-name-search">股票名称</label>
            <input
              id="stock-name-search"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="例如：茅台、腾讯、苹果"
              className="w-full bg-sent-bg border border-sent-border rounded-lg px-3 py-2 text-sm text-white placeholder-sent-dim focus:outline-none focus:border-sent-blue"
              autoFocus
            />
            <div className="mt-3 min-h-8">
              {searchState === 'loading' && <p className="text-xs text-sent-dim">正在搜索…</p>}
              {searchState === 'error' && <p className="text-xs text-sent-red">{searchError}</p>}
              {searchState === 'ready' && results.length === 0 && <p className="text-xs text-sent-dim">没有找到匹配的股票，请换个名称试试。</p>}
              {results.length > 0 && (
                <div className="max-h-64 overflow-y-auto border border-sent-border rounded-lg divide-y divide-sent-border">
                  {results.map((candidate) => (
                    <button
                      key={candidateKey(candidate)}
                      type="button"
                      onClick={() => chooseCandidate(candidate)}
                      disabled={adding}
                      className="w-full px-3 py-2.5 flex items-center gap-3 text-left hover:bg-sent-bg transition-colors disabled:opacity-50"
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm text-white truncate">{candidate.name}</span>
                        <span className="block text-xs text-sent-dim font-mono mt-0.5">{candidate.ticker}</span>
                      </span>
                      <span className={`shrink-0 text-xs px-2 py-0.5 rounded ${marketClass(candidate.market)}`}>{marketLabel(candidate.market)}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </>
        ) : (
          <div>
            <h4 className="text-sm font-semibold text-white">发现多个市场的同名股票</h4>
            <p className="text-xs text-sent-dim mt-1">选择要加入监控的市场，也可以一键全选。</p>
            <div className="mt-3 space-y-2">
              {marketChoices.map((candidate) => {
                const key = candidateKey(candidate)
                return (
                  <label key={key} className="flex items-center gap-3 px-3 py-2.5 bg-sent-bg rounded-lg cursor-pointer">
                    <input type="checkbox" checked={selectedKeys.has(key)} onChange={() => toggleChoice(candidate)} className="accent-sent-blue" />
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm text-white truncate">{candidate.name}</span>
                      <span className="block text-xs text-sent-dim font-mono mt-0.5">{candidate.ticker}</span>
                    </span>
                    <span className={`shrink-0 text-xs px-2 py-0.5 rounded ${marketClass(candidate.market)}`}>{marketLabel(candidate.market)}</span>
                  </label>
                )
              })}
            </div>
            <button type="button" onClick={() => setSelectedKeys(new Set(marketChoices.map(candidateKey)))} className="mt-3 text-xs text-sent-blue hover:text-white">全选市场</button>
          </div>
        )}

        {addError && <p className="mt-3 text-xs text-sent-red bg-sent-red/10 px-3 py-2 rounded-lg">{addError}</p>}
        <div className="flex gap-3 pt-5">
          {marketChoices && (
            <button
              type="button"
              onClick={() => addCandidates(selectedChoices)}
              disabled={adding || selectedChoices.length === 0}
              className="flex-1 px-4 py-2 bg-sent-blue text-white rounded-lg hover:bg-sent-blue/80 transition-colors disabled:opacity-50 text-sm"
            >
              {adding ? '添加中…' : `添加已选（${selectedChoices.length}）`}
            </button>
          )}
          <button type="button" onClick={marketChoices ? () => setMarketChoices(null) : onClose} disabled={adding} className="px-4 py-2 border border-sent-border text-sent-dim rounded-lg hover:text-white hover:border-sent-dim transition-colors disabled:opacity-50 text-sm">
            {marketChoices ? '返回搜索' : '取消'}
          </button>
        </div>
      </div>
    </div>
  )
}
