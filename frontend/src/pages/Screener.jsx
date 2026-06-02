/**
 * Screener - 选股器（M3 充实）
 */
import { useEffect, useState } from 'react'
import { factors as factorsApi } from '../lib/api'

export default function Screener() {
  const [factorList, setFactorList] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    factorsApi.list().then(d => setFactorList(d.factors || [])).catch(e => setError(e.message))
  }, [])

  // 按 category 分组
  const grouped = factorList.reduce((acc, f) => {
    (acc[f.category] = acc[f.category] || []).push(f)
    return acc
  }, {})

  return (
    <div className="space-y-4">
      <div className="bg-sent-card border border-sent-border rounded-lg p-6">
        <h2 className="text-lg font-bold text-white mb-2">🔍 选股器</h2>
        <p className="text-sent-dim text-sm mb-4">M3 阶段将实现完整的多因子选股：多条件筛选 + 截面排名 + Top N 选股。</p>

        {error && <div className="text-sent-red text-sm mb-4">{error}</div>}

        <div className="space-y-4">
          {Object.entries(grouped).map(([cat, list]) => (
            <div key={cat}>
              <h3 className="text-sm font-bold text-sent-blue mb-2">{cat}</h3>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                {list.map(f => (
                  <div key={f.name} className="bg-sent-bg border border-sent-border rounded px-3 py-2">
                    <div className="font-mono text-sm text-white">{f.name}</div>
                    <div className="text-xs text-sent-dim mt-0.5">
                      {f.direction === 'asc' ? '↑ 越大越好' : '↓ 越小越好'}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-6 text-xs text-sent-dim">
          ✅ 后端 15 因子 ready（估值/成长/质量/动量/波动）<br />
          🚧 前端选股 UI + Tushare 财务入库：M3 实现
        </div>
      </div>
    </div>
  )
}
