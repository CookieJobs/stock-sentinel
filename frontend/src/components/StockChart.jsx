/**
 * StockChart - lightweight-charts 封装
 * 多 pane 结构：
 *   pane 0 (主图): K 线 + 成交量 + 价格类指标 (MA / EMA / BOLL / BBI / SAR)
 *   pane 1 (振荡器): 单一选择 (MACD / RSI / KDJ / WR / CCI / ATR)
 *
 * Legend: 十字光标移动显示 OHLC + 主图指标 + 振荡器
 */
import { useEffect, useRef, useState } from 'react'
import { createChart, ColorType, CrosshairMode, LineSeries, HistogramSeries, CandlestickSeries } from 'lightweight-charts'

const COLORS = {
  background: '#161822',
  text: '#d1d5db',
  grid: '#1e2130',
  upColor: '#34d399',
  downColor: '#f87171',
  volume: '#60a5fa',
  ma5: '#fbbf24',
  ma10: '#a78bfa',
  ma20: '#f472b6',
  ma60: '#34d399',
  bollUpper: '#a78bfa',
  bollLower: '#a78bfa',
  bollMid: '#fbbf24',
  sar: '#f87171',
  macdDif: '#60a5fa',
  macdDea: '#fbbf24',
  macdBar: '#a78bfa',
  rsi: '#a78bfa',
  kdjK: '#60a5fa',
  kdjD: '#fbbf24',
  kdjJ: '#f472b6',
}

const PRICE_LINE_COLORS = [COLORS.ma5, COLORS.ma10, COLORS.ma20, COLORS.ma60]

const OSCILLATOR_COLORS = {
  MACD: { dif: COLORS.macdDif, dea: COLORS.macdDea, bar: COLORS.macdBar },
  RSI:  { line: COLORS.rsi },
  KDJ:  { k: COLORS.kdjK, d: COLORS.kdjD, j: COLORS.kdjJ },
  WR:   { line: '#fbbf24' },
  CCI:  { line: '#a78bfa' },
  ATR:  { line: '#34d399' },
}

export default function StockChart({
  kline = [],
  indicators = {},
  oscillator = null,         // 振荡器选择: 'MACD' / 'RSI' / 'KDJ' / null
  height = 520,
  loading = false,
}) {
  const containerRef = useRef(null)
  const chartRef = useRef(null)
  const paneCountRef = useRef(0)
  const seriesRef = useRef({})  // {candle, volume, line_<name>, osc_<sub>}
  const [legend, setLegend] = useState(null)

  // 初始化图表
  useEffect(() => {
    if (!containerRef.current) return
    const chart = createChart(containerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: COLORS.background },
        textColor: COLORS.text,
        fontSize: 12,
      },
      grid: {
        vertLines: { color: COLORS.grid, style: 2 },
        horzLines: { color: COLORS.grid, style: 2 },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: { borderColor: COLORS.grid },
      timeScale: { borderColor: COLORS.grid, timeVisible: true, secondsVisible: false },
      autoSize: true,
    })
    chartRef.current = chart
    paneCountRef.current = 0

    chart.subscribeCrosshairMove((param) => {
      if (!param || !param.time) { setLegend(null); return }
      const candleData = param.seriesData?.get(seriesRef.current.candle)
      if (!candleData) { setLegend(null); return }
      setLegend({
        time: param.time,
        open: candleData.open,
        high: candleData.high,
        low: candleData.low,
        close: candleData.close,
        priceLines: Object.entries(seriesRef.current)
          .filter(([k]) => k.startsWith('line_'))
          .map(([k, s]) => {
            const v = param.seriesData?.get(s)
            return { name: k.replace('line_', ''), value: v?.value }
          })
          .filter(x => x.value != null),
        oscLines: Object.entries(seriesRef.current)
          .filter(([k]) => k.startsWith('osc_'))
          .map(([k, s]) => {
            const v = param.seriesData?.get(s)
            return { name: k.replace('osc_', ''), value: v?.value }
          })
          .filter(x => x.value != null),
      })
    })

    return () => {
      chart.remove()
      chartRef.current = null
      seriesRef.current = {}
    }
  }, [])

  // 渲染 K 线 + 成交量（主图 pane 0）
  useEffect(() => {
    const chart = chartRef.current
    if (!chart || !kline.length) return
    if (seriesRef.current.candle) chart.removeSeries(seriesRef.current.candle)
    if (seriesRef.current.volume) chart.removeSeries(seriesRef.current.volume)

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: COLORS.upColor, downColor: COLORS.downColor,
      borderUpColor: COLORS.upColor, borderDownColor: COLORS.downColor,
      wickUpColor: COLORS.upColor, wickDownColor: COLORS.downColor,
    })
    candleSeries.setData(kline.map(bar => ({
      time: bar.time, open: bar.open, high: bar.high, low: bar.low, close: bar.close,
    })))

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    }, 0)
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    })
    volumeSeries.setData(kline.map(bar => ({
      time: bar.time,
      value: bar.volume || 0,
      color: bar.close >= bar.open ? `${COLORS.upColor}66` : `${COLORS.downColor}66`,
    })))

    seriesRef.current.candle = candleSeries
    seriesRef.current.volume = volumeSeries
  }, [kline])

  // 渲染主图价格类指标（MA / EMA / BOLL / BBI / SAR）— 都加在 pane 0
  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return
    // 清理旧 price line series
    Object.entries(seriesRef.current)
      .filter(([k]) => k.startsWith('line_'))
      .forEach(([, s]) => chart.removeSeries(s))
    Object.keys(seriesRef.current)
      .filter(k => k.startsWith('line_'))
      .forEach(k => delete seriesRef.current[k])

    let colorIdx = 0
    Object.entries(indicators).forEach(([name, ind]) => {
      // 跳过振荡器（它们渲染到 pane 1）
      if (isOscillatorName(name)) return
      if (!ind.values || !ind.values.length) return
      const color = pickColor(name, colorIdx)
      colorIdx++
      const lineSeries = chart.addSeries(LineSeries, {
        color,
        lineWidth: 2,
        title: name,
        priceLineVisible: false,
        lastValueVisible: true,
      }, 0)
      lineSeries.setData(ind.values.map(v => ({ time: v.time, value: v.value })))
      seriesRef.current[`line_${name}`] = lineSeries
    })
  }, [indicators])

  // 渲染振荡器（pane 1）
  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return
    // 清理旧 osc series
    Object.entries(seriesRef.current)
      .filter(([k]) => k.startsWith('osc_'))
      .forEach(([, s]) => chart.removeSeries(s))
    Object.keys(seriesRef.current)
      .filter(k => k.startsWith('osc_'))
      .forEach(k => delete seriesRef.current[k])

    if (!oscillator) {
      // 没有选振荡器 → 删除 pane 1
      // 简化：保留 pane 1 占位（不显示内容），避免抖动
      return
    }

    // 创建 pane 1
    if (paneCountRef.current < 2) {
      chart.addPane()
      paneCountRef.current = 2
      // 设置 pane 高度比例：主图 70%, 振荡器 30%
      try { chart.panes()[1].setStretchFactor(0.4) } catch { /* ignore */ }
    }

    const oscKeys = oscillatorKeys(oscillator)
    oscKeys.forEach(({ key, color, type }) => {
      const ind = indicators[key]
      if (!ind || !ind.values) return
      const seriesType = type === 'bar' ? HistogramSeries : LineSeries
      const series = chart.addSeries(seriesType, {
        color,
        lineWidth: 2,
        title: key,
        priceLineVisible: false,
        lastValueVisible: true,
      }, 1)
      // HistogramSeries 数据只需 {time, value}（MACD 柱正确类型；BarSeries 需 high/low 会触发 v5 断言崩溃）
      series.setData(ind.values.map(v => ({ time: v.time, value: v.value })))
      seriesRef.current[`osc_${key}`] = series
    })
  }, [oscillator, indicators])

  return (
    <div className="relative">
      {legend && (
        <div className="absolute top-2 left-2 z-10 bg-sent-bg/90 border border-sent-border rounded px-3 py-2 text-xs font-mono">
          <div className="text-sent-dim">{legend.time}</div>
          <div className="flex gap-3 mt-1">
            <span>O <span className="text-white">{legend.open?.toFixed(2)}</span></span>
            <span>H <span className="text-sent-green">{legend.high?.toFixed(2)}</span></span>
            <span>L <span className="text-sent-red">{legend.low?.toFixed(2)}</span></span>
            <span>C <span className="text-white font-bold">{legend.close?.toFixed(2)}</span></span>
          </div>
          {legend.priceLines.length > 0 && (
            <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1 max-w-md">
              {legend.priceLines.map(l => (
                <span key={l.name} className="text-sent-yellow">
                  {l.name} {l.value.toFixed(2)}
                </span>
              ))}
            </div>
          )}
          {legend.oscLines.length > 0 && (
            <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1 max-w-md">
              {legend.oscLines.map(l => (
                <span key={l.name} className="text-sent-blue">
                  {l.name} {l.value.toFixed(2)}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
      {loading && (
        <div className="absolute inset-0 z-20 bg-sent-bg/50 flex items-center justify-center">
          <div className="text-sent-blue">加载中...</div>
        </div>
      )}
      <div ref={containerRef} style={{ width: '100%', height }} />
    </div>
  )
}

// ── Helpers ─────────────────────────────────────────────────

function isOscillatorName(name) {
  if (name === 'OBV') return true  // OBV 量价类
  if (name.startsWith('MACD')) return true
  if (name === 'RSI' || name === 'WR' || name === 'CCI' || name === 'ATR') return true
  if (name.startsWith('KDJ')) return true
  return false
}

function pickColor(name, idx) {
  if (name === 'SAR') return COLORS.sar
  if (name.startsWith('BOLL')) {
    if (name.includes('upper')) return COLORS.bollUpper
    if (name.includes('lower')) return COLORS.bollLower
    return COLORS.bollMid
  }
  return PRICE_LINE_COLORS[idx % PRICE_LINE_COLORS.length]
}

function oscillatorKeys(oscName) {
  if (oscName === 'MACD') return [
    { key: 'MACD.dif', color: OSCILLATOR_COLORS.MACD.dif, type: 'line' },
    { key: 'MACD.dea', color: OSCILLATOR_COLORS.MACD.dea, type: 'line' },
    { key: 'MACD.bar', color: OSCILLATOR_COLORS.MACD.bar, type: 'bar' },
  ]
  if (oscName === 'RSI') return [{ key: 'RSI', color: OSCILLATOR_COLORS.RSI.line, type: 'line' }]
  if (oscName === 'KDJ') return [
    { key: 'KDJ.k', color: OSCILLATOR_COLORS.KDJ.k, type: 'line' },
    { key: 'KDJ.d', color: OSCILLATOR_COLORS.KDJ.d, type: 'line' },
    { key: 'KDJ.j', color: OSCILLATOR_COLORS.KDJ.j, type: 'line' },
  ]
  if (oscName === 'WR') return [{ key: 'WR', color: OSCILLATOR_COLORS.WR.line, type: 'line' }]
  if (oscName === 'CCI') return [{ key: 'CCI', color: OSCILLATOR_COLORS.CCI.line, type: 'line' }]
  if (oscName === 'ATR') return [{ key: 'ATR', color: OSCILLATOR_COLORS.ATR.line, type: 'line' }]
  return []
}
