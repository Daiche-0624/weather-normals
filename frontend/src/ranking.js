// cli.py の print_ranking と同じ間引きロジック(上位N件 + 対象日の前後M件)。
// Forecast推定のときは対象日を実測レコードの順位に割り込ませず、番号なしの
// 行として挿入する。ERA5実測のときは対象日自身が既に通常のレコードとして
// 含まれているので、割り込ませず該当行にisToday:trueを付けるだけにする。
const TOP_N = 5
const AROUND = 2

// ranking: core.build_report() が返す rankings[i] の形(records, today_position, total)
// options: { source: 'era5' | 'forecast', todayDate }
// 戻り値は表示用の行の配列。行は次のいずれか:
//   { type: 'record', rank, record, isToday? }
//   { type: 'today' }              (Forecast推定のときだけ使う)
//   { type: 'ellipsis', from, to }
export function selectRankingRows(ranking, { source, todayDate }) {
  const { records, today_position: position, total: n } = ranking
  const isEra5 = source === 'era5'
  const topEnd = Math.min(TOP_N, n)
  const windowStart = Math.max(1, position - AROUND)
  // ERA5実測: 対象日自身が通常の行として1行に収まる(矢印による余分な1行が
  //   ない)ため、後ろ側はそのままposition + AROUNDまででよい
  // Forecast推定: 対象日は矢印の直後にある実測レコード(rank === position)の
  //   位置に挟まれるため、そのレコード自体が「後ろ側1件目」に相当する。
  //   後ろ側をAROUND件にするには position + AROUND - 1 までが正しい
  const windowEnd = Math.min(n, isEra5 ? position + AROUND : position + AROUND - 1)

  const rows = []

  function buildRecordRow(rank) {
    const record = records[rank - 1]
    const isToday = isEra5 && record.date === todayDate
    return { type: 'record', rank, record, isToday }
  }

  function pushRange(start, end) {
    for (let rank = start; rank <= end; rank++) {
      if (!isEra5 && rank === position) {
        rows.push({ type: 'today' })
      }
      rows.push(buildRecordRow(rank))
    }
    if (!isEra5 && position === end + 1) {
      rows.push({ type: 'today' })
    }
  }

  if (windowStart <= topEnd + 1) {
    // 上位と対象日周辺が重なる/隣接するので、省略なしでつなげる
    pushRange(1, Math.max(topEnd, windowEnd))
  } else {
    pushRange(1, topEnd)
    rows.push({ type: 'ellipsis', from: topEnd + 1, to: windowStart - 1 })
    pushRange(windowStart, windowEnd)
  }

  return rows
}
