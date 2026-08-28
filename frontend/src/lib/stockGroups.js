export function filterStocksByGroup(stocks, groups, activeGroupId) {
  if (activeGroupId === 'all') return stocks
  const group = groups.find((item) => item.id === Number(activeGroupId))
  if (!group) return []
  const memberIds = new Set(group.stock_ids)
  return stocks.filter((stock) => memberIds.has(stock.id))
}

export function toggleVisibleSelection(selectedIds, visibleIds) {
  const next = new Set(selectedIds)
  const allSelected = visibleIds.length > 0 && visibleIds.every((id) => next.has(id))
  if (allSelected) {
    visibleIds.forEach((id) => next.delete(id))
  } else {
    visibleIds.forEach((id) => next.add(id))
  }
  return next
}
