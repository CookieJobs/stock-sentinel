import assert from 'node:assert/strict'
import test from 'node:test'

async function loadHelpers() {
  try {
    return await import('./stockSearch.js')
  } catch {
    return { marketAlternatives: () => [] }
  }
}

test('groups only the selected company across distinct markets', async () => {
  const { marketAlternatives } = await loadHelpers()
  const results = [
    { ticker: '601318', name: '中国平安', market: 'CN' },
    { ticker: '02318', name: '中国平安', market: 'HK' },
    { ticker: '000001', name: '平安银行', market: 'CN' },
  ]

  assert.deepEqual(marketAlternatives(results, results[0]), [
    { ticker: '601318', name: '中国平安', market: 'CN' },
    { ticker: '02318', name: '中国平安', market: 'HK' },
  ])
})

test('does not open a market choice for a single-market result', async () => {
  const { marketAlternatives } = await loadHelpers()
  const results = [
    { ticker: 'AAPL', name: '苹果', market: 'US' },
    { ticker: '600519', name: '贵州茅台', market: 'CN' },
  ]

  assert.deepEqual(marketAlternatives(results, results[0]), [])
})
