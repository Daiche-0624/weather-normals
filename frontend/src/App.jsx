import { useEffect, useState } from 'react'
import { fetchReport } from './api'
import ClimateChart from './components/ClimateChart'
import LocationForm from './components/LocationForm'
import RankingTable from './components/RankingTable'
import TodaySummary from './components/TodaySummary'
import './App.css'

// toISOString()はUTCに変換されるため、JST(UTC+9)では日付が変わってから
// 朝9時までの間、1日前の日付になってしまう。ローカル日時の年月日をそのまま使う
function todayIsoDate() {
  const d = new Date()
  const yyyy = d.getFullYear()
  const mm = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

// バックエンド(main.py)のデフォルト値と合わせている(さいたま市付近・今日)
const DEFAULT_PARAMS = {
  lat: '35.86',
  lon: '139.65',
  date: todayIsoDate(),
}

function App() {
  const [params, setParams] = useState(DEFAULT_PARAMS)
  const [report, setReport] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    setLoading(true)
    setError(null)
    fetchReport(params)
      .then((data) => {
        if (!cancelled) setReport(data)
      })
      .catch((e) => {
        if (!cancelled) setError(e.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [params])

  return (
    <div className="app">
      <header className="app-header">
        <h1>weather-normals</h1>
        <LocationForm {...params} onSubmit={setParams} />
      </header>

      {loading && <p className="status-message">読み込み中...</p>}

      {error && (
        <p className="status-message status-error">
          データの取得に失敗しました: {error}
        </p>
      )}

      {report && !loading && !error && (
        <>
          <TodaySummary report={report} />

          <section className="rankings">
            <h2>過去の記録との比較</h2>
            <p className="rankings-note">
              平年より{report.today.label === '暑さ' ? '暑い' : '寒い'}ので、
              {report.today.label === '暑さ' ? '最高' : '最低'}気温でランキングします
            </p>
            <div className="rankings-grid">
              {report.rankings.map((ranking) => (
                <RankingTable
                  key={ranking.period_label}
                  ranking={ranking}
                  todaySource={report.today.source}
                  todayDate={report.target_date}
                />
              ))}
            </div>
          </section>

          <ClimateChart
            climateByDecade={report.climate_by_decade}
            targetMonth={Number(report.target_date.slice(5, 7))}
          />
        </>
      )}
    </div>
  )
}

export default App
