/**
 * Backtest - 回测页面（M4 充实）
 */
import { useEffect, useState } from 'react'
import { backtest as backtestApi } from '../lib/api'

export default function Backtest() {
  const [strategies, setStrategies] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    backtestApi.strategies()
      .then(d => setStrategies(d.strategies || []))
      .catch(e => setError(e.message))
  }, [])

  return (
    <div className="space-y-4">
      <div className="bg-sent-card border border-sent-border rounded-lg p-6">
        <h2 className="text-lg font-bold text-white mb-2">📈 回测中心</h2>
        <p className="text-sent-dim text-sm mb-4">M4 阶段将实现完整的回测工作流：策略选择 + 参数配置 + 历史回放 + 业绩归因。</p>

        {error && <div className="text-sent-red text-sm mb-4">{error}</div>}

        <div className="space-y-2">
          <h3 className="text-sm font-bold text-sent-blue">已实现的内置策略（M0 阶段）</h3>
          {strategies.map(s => (
            <div key={s.name} className="bg-sent-bg border border-sent-border rounded p-3">
              <div className="flex justify-between items-center">
                <span className="font-mono text-white">{s.name}</span>
                <span className="text-xs text-sent-dim">默认参数：{JSON.stringify(s.default_params)}</span>
              </div>
              <p className="text-sm text-sent-dim mt-1">{s.description}</p>
            </div>
          ))}
        </div>

        <div className="mt-6 text-xs text-sent-dim">
          ✅ 后端回测引擎 ready（事件驱动 + 滑点 + 涨跌停 + 完整 metrics）<br />
          🚧 前端回测工作流：M4 实现
        </div>
      </div>
    </div>
  )
}
