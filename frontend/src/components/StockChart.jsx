/**
 * StockChart - lightweight-charts 封装
 * 支持：K 线 + 成交量 + 多个叠加指标
 */
import { useEffect, useRef, useState } from 'react'
import { createChart, ColorType, CrosshairMode, LineSeries, HistogramSeries, CandlestickSeries } from 'lightweight-charts'

// 颜色常量（与项目 design system 对齐）
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
  macd: '#60a5fa',
  signal: '#fbbf24',
  rsi: '#a78bfa',
}

const LINE_COLORS = [COLORS.ma5, COLORS.ma10, COLORS.ma20, COLORS.ma60]

export default function StockChart({
  kline = [],         // [{time, open, high, low, close, volume}]
  indicators = {},    // {name: {values, params, ...}}
  height = 480,
  loading = false,
}) {
  const containerRef = useRef(null)
  const chartRef = useRef(null)
  const seriesRef = useRef({})  // {candle, volume, line_<name>, ...}
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

    // 十字光标联动
    chart.subscribeCrosshairMove((param) => {
      if (!param || !param.time) {
        setLegend(null)
        return
      }
      const candleData = param.seriesData?.get(seriesRef.current.candle)
      if (!candleData) return
      setLegend({
        time: param.time,
        open: candleData.open,
        high: candleData.high,
        low: candleData.low,
        close: candleData.close,
        // 抓所有 line 系列的当前值
        lines: Object.entries(seriesRef.current)
          .filter(([k]) => k.startsWith('line_'))
          .map(([k, s]) => {
            const v = param.seriesData?.get(s)
            return { name: k.replace('line_', ''), value: v?.value }
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

  // 渲染 K 线 + 成交量
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
    candleSeries.setData(kline.map(k => ({
      time: k.time, open: k.open, high: k.high, low: k.low, close: k.close,
    })))

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: '',
    })
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

    chart.timeScale().fitContent()
  }, [kline])

  // 渲染叠加指标（line series）
  useEffect(() => {
    const chart = chartRef.current
    if (!chart) return
    // 清理旧的 line series
    Object.entries(seriesRef.current)
      .filter(([k]) => k.startsWith('line_'))
      .forEach(([, s]) => chart.removeSeries(s))
    Object.keys(seriesRef.current)
      .filter(k => k.startsWith('line_'))
      .forEach(k => delete seriesRef.current[k])

    let colorIdx = 0
    Object.entries(indicators).forEach(([name, ind]) => {
      // 跳过非价格类指标（MACD/RSI 用 pane 而不是主图叠加）
      if (name.startsWith('MACD') || name.startsWith('RSI') || name.startsWith('KDJ') || name.startsWith('WR') || name.startsWith('CCI') || name.startsWith('ATR') || name === 'OBV') return
      if (!ind.values || !ind.values.length) return
      const color = LINE_COLORS[colorIdx % LINE_COLORS.length]
      colorIdx++
      const lineSeries = chart.addSeries(LineSeries, {
        color,
        lineWidth: 2,
        title: name,
        priceLineVisible: false,
        lastValueVisible: true,
      })
      lineSeries.setData(ind.values.map(v => ({ time: v.time, value: v.value })))
      seriesRef.current[`line_${name}`] = lineSeries
    })
  }, [indicators])

  return (
    <div className="relative">
      {/* Legend overlay */}
      {legend && (
        <div className="absolute top-2 left-2 z-10 bg-sent-bg/90 border border-sent-border rounded px-3 py-2 text-xs font-mono">
          <div className="text-sent-dim">{legend.time}</div>
          <div className="flex gap-3 mt-1">
            <span>O <span className="text-white">{legend.open?.toFixed(2)}</span></span>
            <span>H <span className="text-sent-green">{legend.high?.toFixed(2)}</span></span>
            <span>L <span className="text-sent-red">{legend.low?.toFixed(2)}</span></span>
            <span>C <span className="text-white font-bold">{legend.close?.toFixed(2)}</span></span>
          </div>
          {legend.lines.length > 0 && (
            <div className="flex gap-3 mt-1">
              {legend.lines.map(l => (
                <span key={l.name} className="text-sent-yellow">
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
