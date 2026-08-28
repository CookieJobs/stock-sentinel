import test from 'node:test'
import assert from 'node:assert/strict'

import {
  filterStocksByGroup,
  toggleVisibleSelection,
} from '../src/lib/stockGroups.js'

const stocks = [{ id: 1, ticker: 'AAPL' }, { id: 2, ticker: 'MSFT' }, { id: 3, ticker: 'TSLA' }]
const groups = [{ id: 10, name: '核心', stock_ids: [1, 3] }]

test('filters stocks by the selected group without affecting the all-stocks view', () => {
  assert.deepEqual(filterStocksByGroup(stocks, groups, 'all'), stocks)
  assert.deepEqual(filterStocksByGroup(stocks, groups, 10), [stocks[0], stocks[2]])
})

test('select-all only toggles the currently visible stock ids', () => {
  const selected = new Set([1, 3])

  assert.deepEqual([...toggleVisibleSelection(selected, [1, 2])].sort(), [1, 2, 3])
  assert.deepEqual([...toggleVisibleSelection(new Set([1, 2, 3]), [1, 2])].sort(), [3])
})
