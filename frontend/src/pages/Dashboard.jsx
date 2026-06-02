/* eslint-disable react-hooks/preserve-manual-memoization */
// v0.2.0 历史代码：空依赖 useCallback + setState，React Compiler 严格模式不匹配
// M6 打磨时统一重构；现在保持行为不变
import { useState, useEffect, useMemo, useCallback, useRef } from 'react'

const API_BASE = '/api'

function getCurrency(market) {
  if (market === 'CN') return '¥'
  if (market === 'HK') return 'HK$'
  return '$'
}

function getMarketLabel(market) {
  if (market === 'CN') return '🇨🇳 A股'
  if (market === 'HK') return '🇭🇰 港股'
  return '🇺🇸 美股'
}

function getMarketBadgeClass(market) {
  if (market === 'US') return 'bg-sent-blue/20 text-sent-blue'
  if (market === 'CN') return 'bg-sent-yellow/20 text-sent-yellow'
  if (market === 'HK') return 'bg-sent-green/20 text-sent-green'
  return 'bg-sent-blue/20 text-sent-blue'
}

function getChangeClass(val) {
  if (val == null) return 'text-sent-dim'
  return val >= 0 ? 'text-sent-green' : 'text-sent-red'
}

function getDrawdownClass(val) {
  if (val == null) return 'text-sent-dim'
  if (val >= 5) return 'text-sent-red font-bold'
  if (val >= 0) return 'text-sent-yellow'
  return 'text-sent-green'
}

function SortIcon({ column, sortConfig }) {
  if (sortConfig.key !== column) return <span className="text-sent-dim ml-1">↕</span>
  return <span className="text-sent-blue ml-1">{sortConfig.direction === 'asc' ? '↑' : '↓'}</span>
}

export default function Dashboard() {
  const [stocks, setStocks] = useState([])
  const [searchTerm, setSearchTerm] = useState('')
  const [marketFilter, setMarketFilter] = useState('all')
  const [sortConfig, setSortConfig] = useState({ key: 'drawdown', direction: 'desc' })
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [refreshProgress, setRefreshProgress] = useState(null)
  const [lastUpdated, setLastUpdated] = useState(null)
  const [refreshingStock, setRefreshingStock] = useState(null)

  // Toast 通知 — 队列堆叠，每条独立计时
  const [toasts, setToasts] = useState([]) // [{ id, type, message }]
  const toastIdRef = useRef(0)

  const showToast = (type, message) => {
    const id = ++toastIdRef.current
    setToasts((prev) => {
      const next = [...prev, { id, type, message }]
      return next.length > 5 ? next.slice(-5) : next
    })
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 5000)
  }

  // Alert panel
  const [alertCount, setAlertCount] = useState(0)
  const [alerts, setAlerts] = useState([])
  const [alertHistory, setAlertHistory] = useState([])
  const [showAlerts, setShowAlerts] = useState(false)
  const [alertTab, setAlertTab] = useState('unread') // 'unread' | 'history'

  // Add stock modal
  const [showAddModal, setShowAddModal] = useState(false)
  const [newTicker, setNewTicker] = useState('')
  const [newName, setNewName] = useState('')
  const [newThreshold, setNewThreshold] = useState('-15')
  const [addLoading, setAddLoading] = useState(false)
  const [addError, setAddError] = useState('')

  // Edit stock modal
  const [editingStock, setEditingStock] = useState(null)
  const [editThreshold, setEditThreshold] = useState('')
  const [editLoading, setEditLoading] = useState(false)
  const [editError, setEditError] = useState('')

  // Delete confirmation
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(null)
  const [deletingStock, setDeletingStock] = useState(false)

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/stocks/`)
      if (!res.ok) throw new Error('Failed to fetch')
      const data = await res.json()
      setStocks(data)
      setLastUpdated(new Date())
    } catch (err) {
      console.error('Fetch error:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchAlertCount = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/alerts/count`)
      if (!res.ok) return
      const data = await res.json()
      setAlertCount(data.count)
    } catch (err) {
      console.error('Alert count error:', err)
    }
  }, [])

  const fetchAlertList = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/alerts/`)
      if (!res.ok) return
      const data = await res.json()
      setAlerts(data)
    } catch (err) {
      console.error('Alert list error:', err)
    }
  }, [])

  const fetchAlertHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/alerts/history`)
      if (!res.ok) return
      const data = await res.json()
      setAlertHistory(data)
    } catch (err) {
      console.error('Alert history error:', err)
    }
  }, [])

  useEffect(() => {
    fetchData()
    fetchAlertCount()
    const interval = setInterval(fetchAlertCount, 30000)
    return () => clearInterval(interval)
  }, [fetchData, fetchAlertCount])

  const handleRefresh = async () => {
    setRefreshing(true)
    setRefreshProgress({ total: 0, done: 0, current: '', status: 'starting' })
    try {
      const startRes = await fetch(`${API_BASE}/stocks/refresh`, { method: 'POST' })
      if (!startRes.ok) throw new Error('启动刷新失败')
      const { task_id } = await startRes.json()

      const poll = async () => {
        const res = await fetch(`${API_BASE}/stocks/refresh/progress?task_id=${task_id}`)
        if (!res.ok) return null
        return res.json()
      }

      let lastDone = 0
      let progress = null
      while (true) {
        progress = await poll()
        if (!progress) break
        setRefreshProgress(progress)

        // 有新股票刷新完成 → 实时更新列表 + Toast
        if (progress.done > lastDone && progress.last_stock) {
          lastDone = progress.done
          const s = progress.last_stock
          setStocks((prev) => {
            const idx = prev.findIndex((item) => item.ticker === s.ticker)
            if (idx >= 0) {
              const next = [...prev]
              next[idx] = { ...next[idx], ...s }
              return next
            }
            return [...prev, s]
          })
          if (progress.last_status === 'ok') {
            showToast('success', `${s.name || s.ticker} 刷新成功`)
          } else {
            showToast('error', `${progress.current_name || progress.current} 刷新失败`)
          }
        }

        if (progress.status === 'completed' || progress.status === 'error') break
        await new Promise((r) => setTimeout(r, 300))
      }

      // 最终兜底一次全量同步
      if (progress?.status === 'completed') {
        await fetchData()
      } else if (progress?.status === 'error') {
        showToast('error', `刷新异常: ${progress.error || '未知错误'}`)
      }
    } catch {
      showToast('error', '启动刷新失败，请检查后端服务')
    } finally {
      setRefreshing(false)
      setTimeout(() => setRefreshProgress(null), 1200)
    }
  }

  const handleAddStock = async (e) => {
    e.preventDefault()
    setAddError('')
    if (!newTicker.trim()) {
      setAddError('请输入股票代码')
      return
    }
    setAddLoading(true)
    try {
      const res = await fetch(`${API_BASE}/stocks/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: newTicker.trim().toUpperCase(),
          name: newName.trim() || undefined,
          threshold: parseFloat(newThreshold) || -15,
        }),
      })
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || '添加失败')
      }
      setShowAddModal(false)
      setNewTicker('')
      setNewName('')
      setNewThreshold('-15')
      await fetchData()
    } catch (err) {
      setAddError(err.message)
    } finally {
      setAddLoading(false)
    }
  }

  const handleRefreshStock = async (ticker, stockName) => {
    setRefreshingStock(ticker)
    const label = stockName || ticker
    try {
      const res = await fetch(`${API_BASE}/stocks/${ticker}/refresh`)
      const data = await res.json()
      if (res.ok && data.success) {
        // 直接更新单只股票，不等全量刷新
        setStocks((prev) => {
          const idx = prev.findIndex((item) => item.ticker === ticker)
          if (idx >= 0) {
            const next = [...prev]
            next[idx] = { ...next[idx], ...data.stock }
            return next
          }
          return prev
        })
        showToast('success', `${data.stock?.name || label} 刷新成功`)
      } else {
        showToast('error', `${label} ${data.detail || '刷新失败'}`)
      }
    } catch {
      showToast('error', `${label} 网络错误，请重试`)
    } finally {
      setRefreshingStock(null)
    }
  }

  const handleEditStock = async (e) => {
    e.preventDefault()
    setEditError('')
    setEditLoading(true)
    try {
      const res = await fetch(`${API_BASE}/stocks/${editingStock.ticker}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          threshold: parseFloat(editThreshold) || -15,
        }),
      })
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || '更新失败')
      }
      setEditingStock(null)
      setEditThreshold('')
      await fetchData()
    } catch (err) {
      setEditError(err.message)
    } finally {
      setEditLoading(false)
    }
  }

  const handleDeleteStock = async () => {
    if (!showDeleteConfirm) return
    setDeletingStock(true)
    try {
      const res = await fetch(`${API_BASE}/stocks/${showDeleteConfirm.id}`, { method: 'DELETE' })
      if (!res.ok) throw new Error('删除失败')
      setShowDeleteConfirm(null)
      await fetchData()
    } catch (err) {
      console.error('Delete error:', err)
    } finally {
      setDeletingStock(false)
    }
  }

  const handleSort = (key) => {
    setSortConfig((prev) => ({
      key,
      direction: prev.key === key && prev.direction === 'desc' ? 'asc' : 'desc',
    }))
  }

  const filteredStocks = useMemo(() => {
    return stocks.filter((s) => {
      const matchMarket = marketFilter === 'all' || s.market === marketFilter
      const term = searchTerm.toLowerCase()
      const matchSearch =
        !term ||
        (s.ticker && s.ticker.toLowerCase().includes(term)) ||
        (s.name && s.name.toLowerCase().includes(term))
      return matchMarket && matchSearch
    })
  }, [stocks, marketFilter, searchTerm])

  const sortedStocks = useMemo(() => {
    const sorted = [...filteredStocks]
    sorted.sort((a, b) => {
      const aVal = a[sortConfig.key]
      const bVal = b[sortConfig.key]
      if (aVal == null && bVal == null) return 0
      if (aVal == null) return 1
      if (bVal == null) return -1
      if (typeof aVal === 'string') {
        return sortConfig.direction === 'asc'
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal)
      }
      return sortConfig.direction === 'asc' ? aVal - bVal : bVal - aVal
    })
    return sorted
  }, [filteredStocks, sortConfig])

  const stats = useMemo(() => {
    const total = stocks.length
    const usCount = stocks.filter((s) => s.market === 'US').length
    const cnCount = stocks.filter((s) => s.market === 'CN').length
    const hkCount = stocks.filter((s) => s.market === 'HK').length

    const drawdowns = stocks.map((s) => s.drawdown).filter((v) => v != null)
    const avgDrawdown =
      drawdowns.length > 0
        ? (drawdowns.reduce((a, b) => a + b, 0) / drawdowns.length).toFixed(2)
        : '--'

    const overThreshold = stocks.filter((s) => {
      if (s.drawdown == null || s.threshold == null) return false
      if (s.threshold >= 0) return false
      return Math.abs(s.drawdown) >= Math.abs(s.threshold)
    }).length

    let maxStock = null
    let maxDrawdown = -Infinity
    stocks.forEach((s) => {
      if (s.drawdown != null && s.drawdown > maxDrawdown) {
        maxDrawdown = s.drawdown
        maxStock = s
      }
    })

    return { total, usCount, cnCount, hkCount, avgDrawdown, overThreshold, maxStock, maxDrawdown }
  }, [stocks])

  const handleExportCSV = () => {
    const headers = ['代码', '名称', '市场', '板块', '现价', '涨跌%', '52W高', '52W高日期', '回撤%', '阈值%', 'P/E', '距低%']
    const rows = sortedStocks.map((s) => [
      s.ticker,
      s.name || '',
      s.market || '',
      s.sector || '',
      s.current_price != null ? Number(s.current_price).toFixed(2) : '',
      s.change_pct != null ? Number(s.change_pct).toFixed(2) : '',
      s.week52_high != null ? Number(s.week52_high).toFixed(2) : '',
      s.week52_high_date || '',
      s.drawdown != null ? Number(s.drawdown).toFixed(2) : '',
      s.threshold != null ? Math.abs(s.threshold).toFixed(2) : '',
      s.pe_ratio != null ? Number(s.pe_ratio).toFixed(1) : '',
      s.distance_low_pct != null ? Number(s.distance_low_pct).toFixed(1) : '',
    ])
    const csvContent = [headers, ...rows].map((r) => r.map((c) => `"${c}"`).join(',')).join('\n')
    const bom = '﻿'
    const blob = new Blob([bom + csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `stock-sentinel-export-${new Date().toISOString().slice(0, 10)}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <div className="animate-spin rounded-full h-10 w-10 border-2 border-sent-blue border-t-transparent" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Toast 通知 — 堆叠显示 */}
      {toasts.length > 0 && (
        <div className="fixed top-4 right-4 z-50 flex flex-col gap-2" style={{ maxWidth: 320 }}>
          {toasts.map((t) => (
            <div
              key={t.id}
              className={`px-4 py-2.5 rounded-lg shadow-lg text-sm font-medium ${
                t.type === 'success'
                  ? 'bg-green-600 text-white'
                  : 'bg-red-600 text-white'
              }`}
              style={{ animation: 'slideIn 0.3s ease' }}
            >
              {t.type === 'success' ? '✅' : '❌'} {t.message}
            </div>
          ))}
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        <div className="bg-sent-card border border-sent-border rounded-lg p-4">
          <div className="text-xs text-sent-dim mb-1">监控股票</div>
          <div className="text-2xl font-bold">{stats.total}</div>
          <div className="text-xs text-sent-dim mt-1">
            🇺🇸{stats.usCount} 🇨🇳{stats.cnCount} 🇭🇰{stats.hkCount}
          </div>
        </div>
        <div className="bg-sent-card border border-sent-border rounded-lg p-4">
          <div className="text-xs text-sent-dim mb-1">平均回撤</div>
          <div className="text-2xl font-bold text-sent-yellow">{stats.avgDrawdown}%</div>
        </div>
        <div className="bg-sent-card border border-sent-border rounded-lg p-4">
          <div className="text-xs text-sent-dim mb-1">超过阈值</div>
          <div className="text-2xl font-bold text-sent-red">{stats.overThreshold}</div>
        </div>
        <div className="bg-sent-card border border-sent-border rounded-lg p-4">
          <div className="text-xs text-sent-dim mb-1">最高回撤</div>
          {stats.maxStock ? (
            <>
              <div className="text-lg font-bold text-sent-red">{stats.maxStock.ticker}</div>
              <div className="text-sm text-sent-red">{stats.maxDrawdown.toFixed(2)}%</div>
            </>
          ) : (
            <div className="text-lg text-sent-dim">--</div>
          )}
        </div>
        <div className="bg-sent-card border border-sent-border rounded-lg p-4">
          <div className="text-xs text-sent-dim mb-1">市场分布</div>
          <div className="space-y-1 mt-1">
            <div className="flex justify-between text-xs">
              <span className="text-sent-blue">🇺🇸 美股</span>
              <span>{stats.usCount}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-sent-yellow">🇨🇳 A股</span>
              <span>{stats.cnCount}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-sent-green">🇭🇰 港股</span>
              <span>{stats.hkCount}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Table */}
      <div className="bg-sent-card border border-sent-border rounded-lg">
        {/* Header */}
        <div className="px-4 py-3 border-b border-sent-border flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-4">
            <h2 className="text-lg font-semibold">📈 股票监控</h2>
            {lastUpdated && (
              <span className="text-xs text-sent-dim">
                更新于 {lastUpdated.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {/* Market filter tabs */}
            <div className="flex bg-sent-border/30 rounded-lg p-0.5">
              {[
                { key: 'all', label: '全部' },
                { key: 'US', label: '🇺🇸 美股' },
                { key: 'CN', label: '🇨🇳 A股' },
                { key: 'HK', label: '🇭🇰 港股' },
              ].map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setMarketFilter(tab.key)}
                  className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
                    marketFilter === tab.key
                      ? 'bg-sent-blue text-white'
                      : 'text-sent-dim hover:text-white'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <button
              onClick={() => setShowAddModal(true)}
              className="px-3 py-1.5 text-xs bg-sent-blue/20 text-sent-blue rounded-lg hover:bg-sent-blue/30 transition-colors"
            >
              ＋ 添加
            </button>
            <button
              onClick={() => {
                fetchAlertList()
                fetchAlertHistory()
                setShowAlerts(true)
              }}
              className="relative px-3 py-1.5 text-xs bg-sent-border/50 text-sent-dim rounded-lg hover:text-white hover:bg-sent-border transition-colors"
            >
              🔔 告警
              {alertCount > 0 && (
                <span className="absolute -top-1 -right-1 bg-sent-red text-white text-xs rounded-full w-4 h-4 flex items-center justify-center font-bold">
                  {alertCount > 9 ? '9+' : alertCount}
                </span>
              )}
            </button>
            <button
              onClick={handleExportCSV}
              disabled={stocks.length === 0}
              className="px-3 py-1.5 text-xs bg-sent-border/50 text-sent-dim rounded-lg hover:text-white hover:bg-sent-border transition-colors disabled:opacity-50"
            >
              📥 导出 CSV
            </button>
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="px-3 py-1.5 text-xs bg-sent-border/50 text-sent-dim rounded-lg hover:text-white hover:bg-sent-border transition-colors disabled:opacity-50"
            >
              {refreshing ? '⏳ 刷新中...' : '🔄 刷新数据'}
            </button>
          </div>
        </div>

        {/* Refresh Progress Bar */}
        {refreshProgress && (
          <div className="px-4 py-2 border-b border-sent-border bg-sent-bg/50">
            <div className="flex items-center gap-3">
              <div className="flex-1">
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="text-sent-dim">
                    {refreshProgress.status === 'starting'
                      ? '⏳ 正在连接 API...'
                      : refreshProgress.status === 'completed'
                        ? '✅ 刷新完成'
                        : refreshProgress.status === 'error'
                          ? '❌ 刷新出错'
                          : `🔄 正在刷新 ${refreshProgress.current_name || refreshProgress.current || ''}`}
                  </span>
                  <span className="text-sent-blue font-mono">
                    {refreshProgress.done}/{refreshProgress.total}
                  </span>
                </div>
                <div className="w-full h-1.5 bg-sent-border/30 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-300 ${
                      refreshProgress.status === 'error'
                        ? 'bg-sent-red'
                        : refreshProgress.status === 'completed'
                          ? 'bg-sent-green'
                          : 'bg-sent-blue'
                    }`}
                    style={{
                      width: `${refreshProgress.total > 0
                        ? (refreshProgress.done / refreshProgress.total) * 100
                        : 0}%`,
                    }}
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Search */}
        <div className="px-4 py-2.5 border-b border-sent-border">
          <input
            type="text"
            placeholder="搜索股票代码或名称..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full max-w-xs bg-sent-bg border border-sent-border rounded-lg px-3 py-2 text-sm text-white placeholder-sent-dim focus:outline-none focus:border-sent-blue"
          />
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-sent-border text-sent-dim text-xs">
                <th className="px-3 py-2.5 text-left cursor-pointer hover:text-white" onClick={() => handleSort('ticker')}>代码 <SortIcon column="ticker" sortConfig={sortConfig} /></th>
                <th className="px-3 py-2.5 text-left cursor-pointer hover:text-white" onClick={() => handleSort('name')}>名称 <SortIcon column="name" sortConfig={sortConfig} /></th>
                <th className="px-3 py-2.5 text-left whitespace-nowrap">市场</th>
                <th className="px-3 py-2.5 text-left whitespace-nowrap">板块</th>
                <th className="px-3 py-2.5 text-right cursor-pointer hover:text-white" onClick={() => handleSort('current_price')}>现价 <SortIcon column="current_price" sortConfig={sortConfig} /></th>
                <th className="px-3 py-2.5 text-right cursor-pointer hover:text-white" onClick={() => handleSort('change_pct')}>涨跌 <SortIcon column="change_pct" sortConfig={sortConfig} /></th>
                <th className="px-3 py-2.5 text-right whitespace-nowrap">52W高</th>
                <th className="px-3 py-2.5 text-right whitespace-nowrap">52W高日期</th>
                <th className="px-3 py-2.5 text-right whitespace-nowrap cursor-pointer hover:text-white" onClick={() => handleSort('drawdown')}>回撤 <SortIcon column="drawdown" sortConfig={sortConfig} /></th>
                <th className="px-3 py-2.5 text-right whitespace-nowrap">阈值</th>
                <th className="px-3 py-2.5 text-right whitespace-nowrap cursor-pointer hover:text-white" onClick={() => handleSort('pe_ratio')}>P/E</th>
                <th className="px-3 py-2.5 text-right whitespace-nowrap">距低</th>
                <th className="px-3 py-2.5 text-center">操作</th>
              </tr>
            </thead>
            <tbody>
              {sortedStocks.length === 0 ? (
                <tr>
                  <td colSpan={13} className="px-4 py-12 text-center text-sent-dim">
                    暂无数据
                  </td>
                </tr>
              ) : (
                sortedStocks.map((stock) => (
                  <tr
                    key={stock.id}
                    className="border-b border-sent-border/50 hover:bg-white/[0.02] transition-colors"
                  >
                    <td className="px-3 py-2.5 font-mono text-white whitespace-nowrap">{stock.ticker}</td>
                    <td className="px-3 py-2.5 text-white whitespace-nowrap">{stock.name || '--'}</td>
                    <td className="px-3 py-2.5 whitespace-nowrap">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-xs ${getMarketBadgeClass(
                          stock.market
                        )}`}
                      >
                        {getMarketLabel(stock.market)}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 whitespace-nowrap">
                      {stock.sector ? (
                        <span className="inline-block px-2 py-0.5 rounded text-xs bg-sent-border/50 text-sent-dim">
                          {stock.sector}
                        </span>
                      ) : (
                        <span className="text-sent-dim">--</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 text-right font-mono whitespace-nowrap">
                      {stock.current_price != null
                        ? `${getCurrency(stock.market)}${Number(stock.current_price).toFixed(2)}`
                        : '--'}
                    </td>
                    <td className={`px-3 py-2.5 text-right font-mono whitespace-nowrap ${getChangeClass(stock.change_pct)}`}>
                      {stock.change_pct != null
                        ? (stock.market === 'US' && stock.ah_change_label
                            ? <span className="inline-flex items-center gap-1"><span className="text-sent-dim">[{stock.ah_change_label}]</span><span className={stock.ah_change_pct >= 0 ? 'text-sent-green' : 'text-sent-red'}>{stock.ah_change_pct >= 0 ? '+' : ''}{Number(stock.ah_change_pct).toFixed(2)}%</span></span>
                            : `${stock.change_pct >= 0 ? '+' : ''}${Number(stock.change_pct).toFixed(2)}%`)
                        : '--'}
                    </td>
                    <td className="px-3 py-2.5 text-right font-mono text-sent-dim whitespace-nowrap">
                      {stock.week52_high != null
                        ? `${getCurrency(stock.market)}${Number(stock.week52_high).toFixed(2)}`
                        : '--'}
                    </td>
                    <td className="px-3 py-2.5 text-right text-sent-dim text-xs whitespace-nowrap">
                      {stock.week52_high_date || '--'}
                    </td>
                    <td className={`px-3 py-2.5 text-right font-mono whitespace-nowrap ${getDrawdownClass(stock.drawdown)}`}>
                      {stock.drawdown != null
                        ? `${Number(stock.drawdown).toFixed(2)}%`
                        : '--'}
                    </td>
                    <td className="px-3 py-2.5 text-right text-sent-dim whitespace-nowrap">
                      {stock.threshold != null ? `${Math.abs(stock.threshold)}%` : '--'}
                    </td>
                    <td className="px-3 py-2.5 text-right text-sent-dim whitespace-nowrap">
                      {stock.pe_ratio != null ? Number(stock.pe_ratio).toFixed(1) : '--'}
                    </td>
                    <td className="px-3 py-2.5 text-right text-sent-dim whitespace-nowrap">
                      {stock.distance_low_pct != null
                        ? `${Number(stock.distance_low_pct).toFixed(1)}%`
                        : '--'}
                    </td>
                    <td className="px-3 py-2.5 text-center whitespace-nowrap">
                      <button
                        onClick={() => handleRefreshStock(stock.ticker, stock.name)}
                        disabled={refreshingStock === stock.ticker}
                        className="text-sent-dim hover:text-sent-blue transition-colors p-1 disabled:opacity-50"
                        title="刷新"
                      >
                        {refreshingStock === stock.ticker ? '⏳' : '🔄'}
                      </button>
                      <button
                        onClick={() => {
                          setEditingStock(stock)
                          setEditThreshold(String(Math.abs(stock.threshold) || 15))
                          setEditError('')
                        }}
                        className="text-sent-dim hover:text-sent-yellow transition-colors p-1"
                        title="编辑阈值"
                      >
                        ✎
                      </button>
                      <button
                        onClick={() => setShowDeleteConfirm(stock)}
                        className="text-sent-dim hover:text-sent-red transition-colors p-1"
                        title="删除"
                      >
                        🗑
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add Stock Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60" onClick={() => setShowAddModal(false)} />
          <div className="relative bg-sent-card border border-sent-border rounded-xl p-6 w-full max-w-md mx-4">
            <h3 className="text-lg font-semibold mb-4">添加股票</h3>
            <form onSubmit={handleAddStock} className="space-y-4">
              <div>
                <label className="block text-xs text-sent-dim mb-1">股票代码 *</label>
                <input
                  type="text"
                  value={newTicker}
                  onChange={(e) => setNewTicker(e.target.value)}
                  placeholder="例如: AAPL, 600519.SS, 0700.HK"
                  className="w-full bg-sent-bg border border-sent-border rounded-lg px-3 py-2 text-sm text-white placeholder-sent-dim focus:outline-none focus:border-sent-blue"
                  autoFocus
                />
                <p className="text-xs text-sent-dim mt-1">
                  美股直接输入代码，A股加.SS(上)/.SZ(深)，港股加.HK
                </p>
              </div>
              <div>
                <label className="block text-xs text-sent-dim mb-1">名称 (可选)</label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="如: Apple Inc."
                  className="w-full bg-sent-bg border border-sent-border rounded-lg px-3 py-2 text-sm text-white placeholder-sent-dim focus:outline-none focus:border-sent-blue"
                />
              </div>
              <div>
                <label className="block text-xs text-sent-dim mb-1">回撤阈值 (%)</label>
                <input
                  type="number"
                  value={newThreshold}
                  onChange={(e) => setNewThreshold(e.target.value)}
                  className="w-full bg-sent-bg border border-sent-border rounded-lg px-3 py-2 text-sm text-white placeholder-sent-dim focus:outline-none focus:border-sent-blue"
                />
              </div>
              {addError && (
                <div className="text-xs text-sent-red bg-sent-red/10 px-3 py-2 rounded-lg">{addError}</div>
              )}
              <div className="flex gap-3 pt-2">
                <button
                  type="submit"
                  disabled={addLoading}
                  className="flex-1 px-4 py-2 bg-sent-blue text-white rounded-lg hover:bg-sent-blue/80 transition-colors disabled:opacity-50 text-sm"
                >
                  {addLoading ? '添加中...' : '确认添加'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 border border-sent-border text-sent-dim rounded-lg hover:text-white hover:border-sent-dim transition-colors text-sm"
                >
                  取消
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Alert Panel Modal */}
      {showAlerts && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60" onClick={() => setShowAlerts(false)} />
          <div className="relative bg-sent-card border border-sent-border rounded-xl p-6 w-full max-w-lg mx-4 max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">🔔 告警通知</h3>
              <button
                onClick={() => setShowAlerts(false)}
                className="text-sent-dim hover:text-white text-xl"
              >
                ×
              </button>
            </div>

            {/* Tab switcher */}
            <div className="flex bg-sent-border/30 rounded-lg p-0.5 mb-4">
              <button
                onClick={() => setAlertTab('unread')}
                className={`flex-1 px-3 py-1.5 text-xs rounded-md transition-colors ${
                  alertTab === 'unread'
                    ? 'bg-sent-blue text-white'
                    : 'text-sent-dim hover:text-white'
                }`}
              >
                未读 ({alertCount})
              </button>
              <button
                onClick={() => setAlertTab('history')}
                className={`flex-1 px-3 py-1.5 text-xs rounded-md transition-colors ${
                  alertTab === 'history'
                    ? 'bg-sent-blue text-white'
                    : 'text-sent-dim hover:text-white'
                }`}
              >
                历史
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3">
              {alertTab === 'unread' ? (
                alerts.length === 0 ? (
                  <p className="text-sent-dim text-center py-8">暂无未读告警</p>
                ) : (
                  alerts.map((alert, i) => {
                    const currency = alert.market === 'CN' ? '¥' : alert.market === 'HK' ? 'HK$' : '$'
                    return (
                      <div key={alert.id || i} className="bg-sent-bg border border-sent-border rounded-lg p-4">
                        <div className="flex items-center justify-between mb-2">
                          <span className="font-mono font-bold text-white">{alert.ticker}</span>
                          <span className="text-xs text-sent-dim">
                            {alert.created_at ? new Date(alert.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) : '--'}
                          </span>
                        </div>
                        <div className="text-sm text-sent-dim space-y-1">
                          <div>{alert.name || alert.ticker}</div>
                          <div className="flex gap-4">
                            <span>回撤：<span className="text-sent-red font-mono">{alert.drawdown_pct != null ? `${Number(alert.drawdown_pct).toFixed(2)}%` : '--'}</span></span>
                            <span>阈值：<span className="text-sent-yellow font-mono">{alert.threshold != null ? `${Math.abs(alert.threshold).toFixed(2)}%` : '--'}</span></span>
                          </div>
                          <div>现价：{currency}{alert.current_price != null ? Number(alert.current_price).toFixed(2) : '--'}</div>
                        </div>
                      </div>
                    )
                  })
                )
              ) : (
                alertHistory.length === 0 ? (
                  <p className="text-sent-dim text-center py-8">暂无历史记录</p>
                ) : (
                  alertHistory.map((h, i) => (
                    <div key={h.id || i} className="bg-sent-bg border border-sent-border rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-mono font-bold text-white">{h.ticker}</span>
                        <span className="text-xs text-sent-dim">
                          {h.sent_date || h.sent_at || '--'}
                        </span>
                      </div>
                      <div className="text-sm text-sent-dim">
                        触发时间：{h.sent_at ? new Date(h.sent_at).toLocaleString('zh-CN') : '--'}
                      </div>
                    </div>
                  ))
                )
              )}
            </div>

            <div className="pt-4 border-t border-sent-border flex gap-3">
              {alertTab === 'unread' && alertCount > 0 && (
                <button
                  onClick={async () => {
                    try {
                      await fetch(`${API_BASE}/alerts/clear`, { method: 'POST' })
                      setAlertCount(0)
                      setAlerts([])
                    } catch (err) {
                      console.error('Clear alerts error:', err)
                    }
                  }}
                  className="flex-1 px-4 py-2 bg-sent-red/20 text-sent-red rounded-lg hover:bg-sent-red/30 transition-colors text-sm"
                >
                  清除所有
                </button>
              )}
              {alertTab === 'history' && alertHistory.length > 0 && (
                <button
                  onClick={async () => {
                    try {
                      await fetch(`${API_BASE}/alerts/history`, { method: 'DELETE' })
                      setAlertHistory([])
                    } catch (err) {
                      console.error('Clear history error:', err)
                    }
                  }}
                  className="flex-1 px-4 py-2 bg-sent-border/50 text-sent-dim rounded-lg hover:text-white hover:bg-sent-border transition-colors text-sm"
                >
                  清除历史
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Edit Threshold Modal */}
      {editingStock && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60" onClick={() => setEditingStock(null)} />
          <div className="relative bg-sent-card border border-sent-border rounded-xl p-6 w-full max-w-md mx-4">
            <h3 className="text-lg font-semibold mb-4">编辑阈值 - {editingStock.ticker}</h3>
            <form onSubmit={handleEditStock} className="space-y-4">
              <div className="flex items-center gap-3 text-sm text-sent-dim mb-2">
                <span>{editingStock.name || editingStock.ticker}</span>
                <span>现价: {editingStock.current_price != null ? getCurrency(editingStock.market) + Number(editingStock.current_price).toFixed(2) : '--'}</span>
                <span>当前回撤: <span className={getDrawdownClass(editingStock.drawdown)}>{editingStock.drawdown != null ? Number(editingStock.drawdown).toFixed(2) + '%' : '--'}</span></span>
              </div>
              <div>
                <label className="block text-xs text-sent-dim mb-1">回撤阈值 (%)</label>
                <input
                  type="number"
                  value={editThreshold}
                  onChange={(e) => setEditThreshold(e.target.value)}
                  className="w-full bg-sent-bg border border-sent-border rounded-lg px-3 py-2 text-sm text-white placeholder-sent-dim focus:outline-none focus:border-sent-blue"
                  step="0.5"
                  min="0"
                  autoFocus
                />
                <p className="text-xs text-sent-dim mt-1">当前回撤超过此值时触发告警</p>
              </div>
              {editError && (
                <div className="text-xs text-sent-red bg-sent-red/10 px-3 py-2 rounded-lg">{editError}</div>
              )}
              <div className="flex gap-3 pt-2">
                <button
                  type="submit"
                  disabled={editLoading}
                  className="flex-1 px-4 py-2 bg-sent-blue text-white rounded-lg hover:bg-sent-blue/80 transition-colors disabled:opacity-50 text-sm"
                >
                  {editLoading ? '保存中...' : '保存'}
                </button>
                <button
                  type="button"
                  onClick={() => setEditingStock(null)}
                  className="px-4 py-2 border border-sent-border text-sent-dim rounded-lg hover:text-white hover:border-sent-dim transition-colors text-sm"
                >
                  取消
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60" onClick={() => setShowDeleteConfirm(null)} />
          <div className="relative bg-sent-card border border-sent-border rounded-xl p-6 w-full max-w-sm mx-4">
            <h3 className="text-lg font-semibold mb-2">确认删除</h3>
            <p className="text-sm text-sent-dim mb-6">
              确定要删除 <span className="text-white font-mono">{showDeleteConfirm.ticker}</span>
              {showDeleteConfirm.name ? ` (${showDeleteConfirm.name})` : ''} 吗？
              此操作不可撤销。
            </p>
            <div className="flex gap-3">
              <button
                onClick={handleDeleteStock}
                disabled={deletingStock}
                className="flex-1 px-4 py-2 bg-sent-red text-white rounded-lg hover:bg-sent-red/80 transition-colors disabled:opacity-50 text-sm"
              >
                {deletingStock ? '删除中...' : '确认删除'}
              </button>
              <button
                onClick={() => setShowDeleteConfirm(null)}
                className="px-4 py-2 border border-sent-border text-sent-dim rounded-lg hover:text-white hover:border-sent-dim transition-colors text-sm"
              >
                取消
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}