/**
 * App 根组件 — 加 react-router + nav 导航
 * 4 个页面：监控（保留 Dashboard）/ 图表 / 选股 / 回测 / 组合 / 风险
 */
import { BrowserRouter, Routes, Route, NavLink, Link } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Chart from './pages/Chart'
import Screener from './pages/Screener'
import Backtest from './pages/Backtest'
import Portfolio from './pages/Portfolio'
import Risk from './pages/Risk'
import EventCalendar from './pages/EventCalendar'
import PaperTrading from './pages/PaperTrading'

function NavItem({ to, label, icon }) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      className={({ isActive }) =>
        `px-3 py-1.5 rounded text-sm font-bold transition ${
          isActive
            ? 'bg-sent-blue text-sent-bg'
            : 'text-sent-dim hover:text-white hover:bg-sent-border/30'
        }`
      }
    >
      <span className="mr-1">{icon}</span>{label}
    </NavLink>
  )
}

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-sent-bg text-white">
        <header className="border-b border-sent-border bg-sent-card">
          <div className="max-w-[1600px] mx-auto px-4 py-3 flex items-center gap-6">
            <Link to="/" className="flex items-center gap-2">
              <span className="text-2xl">📉</span>
              <h1 className="text-lg font-bold text-white">StockSentinel</h1>
              <span className="text-xs text-sent-dim bg-sent-border/30 px-2 py-0.5 rounded">量化平台 v0.3</span>
            </Link>

            <nav className="flex items-center gap-1 ml-4">
              <NavItem to="/" label="监控" icon="📊" />
              <NavItem to="/chart" label="图表" icon="📈" />
              <NavItem to="/screener" label="选股" icon="🔍" />
              <NavItem to="/backtest" label="回测" icon="⚡" />
              <NavItem to="/portfolio" label="组合" icon="💼" />
              <NavItem to="/risk" label="风险" icon="⚖️" />
              <NavItem to="/events" label="事件" icon="🗓️" />
              <NavItem to="/paper" label="模拟交易" icon="🪙" />
            </nav>

            <div className="ml-auto text-xs text-sent-dim">个人投研型量化分析平台</div>
          </div>
        </header>
        <main className="max-w-[1600px] mx-auto px-4 py-6">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/chart" element={<Chart />} />
            <Route path="/screener" element={<Screener />} />
            <Route path="/backtest" element={<Backtest />} />
            <Route path="/portfolio" element={<Portfolio />} />
            <Route path="/risk" element={<Risk />} />
            <Route path="/events" element={<EventCalendar />} />
            <Route path="/paper" element={<PaperTrading />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}

export default App
