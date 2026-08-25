/**
 * ErrorBoundary — 页面级错误边界
 * 任一页面/组件在渲染或 effect 中抛异常时，显示错误卡片而非卸载整棵组件树白屏
 */
import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="bg-sent-red/10 border border-sent-red/40 text-sent-red rounded-lg p-6">
          <div className="text-lg font-bold">⚠️ 页面出错了</div>
          <div className="text-sm mt-2 font-mono break-all opacity-80">
            {String(this.state.error)}
          </div>
          <button
            className="mt-4 px-4 py-1.5 rounded bg-sent-blue text-sent-bg text-sm font-bold hover:opacity-80"
            onClick={() => this.setState({ error: null })}
          >
            重试
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
