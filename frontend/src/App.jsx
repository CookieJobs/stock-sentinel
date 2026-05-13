import Dashboard from './pages/Dashboard'

function App() {
  return (
    <div className="min-h-screen bg-sent-bg text-white">
      <header className="border-b border-sent-border bg-sent-card">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-2xl">📉</span>
            <h1 className="text-xl font-bold text-white">StockSentinel</h1>
            <span className="text-xs text-sent-dim bg-sent-border/30 px-2 py-0.5 rounded">回撤监控</span>
          </div>
          <div className="text-xs text-sent-dim">全球股票回撤监控系统</div>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-6 py-6">
        <Dashboard />
      </main>
    </div>
  )
}

export default App
