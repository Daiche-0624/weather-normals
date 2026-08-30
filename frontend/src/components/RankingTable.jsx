import { selectRankingRows } from '../ranking'

// 1つの期間(1940年以降 or 1979年以降)分のランキングを表示する。
// 上位5件+対象日の前後2件のみ表示する(cli.pyと同じ間引き)。
// Forecast推定のときは対象日を順位番号を持たない矢印行として挿入し、
// ERA5実測のときは対象日自身が既に通常の行として含まれているので、
// その行をハイライトするだけにする。
function RankingTable({ ranking, todaySource, todayDate }) {
  const rows = selectRankingRows(ranking, { source: todaySource, todayDate })
  // 見出しの大きな数字は平均気温だが、ランキングは暑さなら最高気温、
  // 寒さなら最低気温を使っている(別の指標であることを明示する)
  const metric = ranking.label === '暑さ' ? '最高気温' : '最低気温'

  return (
    <div className="ranking-card">
      <h3>{ranking.period_label}({metric})</h3>
      <p className="ranking-meta">
        {ranking.year_min}〜{ranking.year_max}年・全{ranking.total}件中
        <strong> {ranking.today_position}番目</strong>の{ranking.label}
      </p>
      <table className="ranking-table">
        <tbody>
          {rows.map((row, i) => {
            if (row.type === 'today') {
              return (
                <tr key={`today-${i}`} className="ranking-row-today">
                  <td>→</td>
                  <td>対象日</td>
                  <td>{ranking.today_value.toFixed(1)} ℃</td>
                </tr>
              )
            }
            if (row.type === 'ellipsis') {
              return (
                <tr key={`ellipsis-${i}`} className="ranking-row-ellipsis">
                  <td colSpan={3}>...({row.from}〜{row.to}位省略)...</td>
                </tr>
              )
            }
            return (
              <tr key={row.rank} className={row.isToday ? 'ranking-row-today' : undefined}>
                <td>{row.isToday ? '→ ' : ''}{row.rank}位</td>
                <td>{row.record.date}</td>
                <td>{row.record.value.toFixed(1)} ℃</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export default RankingTable
