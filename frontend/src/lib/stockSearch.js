function companyKey(name) {
  return String(name || '')
    .trim()
    .toLocaleLowerCase('zh-CN')
    .replace(/[\s·.()（）[]【】-]/g, '')
    .replace(/(?:w|sw)$/i, '')
}

export function marketAlternatives(results, selected) {
  const selectedKey = companyKey(selected?.name)
  if (!selectedKey) return []

  const matching = results.filter((item) => companyKey(item.name) === selectedKey)
  const markets = new Set(matching.map((item) => item.market))
  if (markets.size < 2) return []

  const seen = new Set()
  return matching.filter((item) => {
    const key = `${item.market}:${item.ticker}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}
