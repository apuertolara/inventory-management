// CSV export utility

// Quote a single cell per RFC 4180. String cells starting with a spreadsheet
// formula trigger (= + - @ tab CR) are prefixed with ' so Excel/Sheets don't
// evaluate them (CSV injection). Numbers are left untouched so negatives still
// import as numbers.
function escapeCell(value) {
  if (value === null || value === undefined) return ''
  if (typeof value === 'number') return Number.isFinite(value) ? String(value) : ''
  let text = String(value)
  if (/^[=+\-@\t\r]/.test(text)) {
    text = `'${text}`
  }
  if (/[",\r\n]/.test(text)) {
    text = `"${text.replace(/"/g, '""')}"`
  }
  return text
}

export function toCsv(headers, rows) {
  const lines = [headers, ...rows].map(row => row.map(escapeCell).join(','))
  return lines.join('\r\n')
}

export function downloadCsv(filename, csv) {
  // Leading BOM so Excel detects UTF-8 (needed for Japanese product names)
  const blob = new Blob(['\uFEFF', csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
