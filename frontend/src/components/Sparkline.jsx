// 纯 SVG 回撤趋势 sparkline — 不引入图表库
// points: drawdown 数值序列（负数表示回撤，值越小越深）
const TREND_COLORS = {
  alert: '#f87171',
  warning: '#fbbf24',
  normal: '#34d399',
  unknown: '#6b7280',
}

export default function Sparkline({ points, status, width = 96, height = 28 }) {
  const vals = Array.isArray(points) ? points.filter((v) => v != null) : []
  if (vals.length < 2) {
    return <span className="text-sent-dim text-xs whitespace-nowrap">暂无趋势</span>
  }

  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const range = max - min || 1
  const pad = 2
  const stepX = width / (vals.length - 1)
  const coords = vals.map((v, i) => {
    const x = (i * stepX).toFixed(1)
    const y = (height - pad - ((v - min) / range) * (height - 2 * pad)).toFixed(1)
    return `${x},${y}`
  })
  const color = TREND_COLORS[status] || TREND_COLORS.unknown

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="inline-block align-middle"
      aria-label="回撤趋势"
      role="img"
    >
      <polyline
        points={coords.join(' ')}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  )
}
