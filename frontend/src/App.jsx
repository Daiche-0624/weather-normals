import { useEffect, useRef, useState } from 'react'
import { fetchReport } from './api'
import ClimateChart from './components/ClimateChart'
import LoadingIndicator from './components/LoadingIndicator'
import LocationForm from './components/LocationForm'
import RankingTable from './components/RankingTable'
import TodaySummary from './components/TodaySummary'
import { selectRankingRows } from './ranking'
import { getTemperatureTheme } from './theme'
import './App.css'

// ランキング表の行が初回だけ1行ずつパラパラと現れる演出の速さ。
// 50〜80msの間で、多すぎる行数でも体感1秒前後に収まるよう控えめに50msにしている
const ROW_REVEAL_DELAY_MS = 50
// 気温側の登場演出(平年差が1秒前後でフェードインし終わる)と被らないよう、
// ランキングの行めくりはそのあとから始める
const RANKING_REVEAL_BASE_DELAY_MS = 1600

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
  const [isFirstReveal, setIsFirstReveal] = useState(false)
  // セッション中で一度でも表示演出をしたかどうかのフラグ。stateにすると
  // 演出のたびに再レンダーが走ってしまうため、演出の可否判定だけならrefで十分
  const hasRevealedRef = useRef(false)

  useEffect(() => {
    let cancelled = false

    setLoading(true)
    setError(null)
    fetchReport(params)
      .then((data) => {
        if (!cancelled) {
          setReport(data)
          setIsFirstReveal(!hasRevealedRef.current)
          hasRevealedRef.current = true
        }
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

  // ボタンやランキングのハイライトなど、サイト全体のアクセントカラーを
  // 気温表示エリアと同じ平年差テーマから派生させる(「背景は青系なのに
  // ボタンは紫」のような系統のバラつきをなくすため)。既存の--accent系
  // 変数(index.css)をここで上書きすることで、LocationFormやRankingTable
  // 側のCSSは変更せずに色だけ追従させている。データ取得前はテーマが
  // 決まらないので、index.css側の既定値にフォールバックする
  const theme = report ? getTemperatureTheme(report.today.deviation) : null

  return (
    <div
      className="app"
      style={
        theme
          ? {
              '--theme-base': theme.base,
              '--accent': theme.accent,
              '--accent-bg': `color-mix(in srgb, ${theme.accent} 14%, transparent)`,
              '--accent-border': `color-mix(in srgb, ${theme.accent} 45%, transparent)`,
            }
          : undefined
      }
    >
      <header className="app-header">
        <div className="app-title">
          <h1>weather-normals</h1>
          <p className="app-subtitle">Today vs. the last 30 years</p>
        </div>
        <LocationForm {...params} onSubmit={setParams} />
      </header>

      {loading && <LoadingIndicator />}

      {error && (
        <p className="status-message status-error">
          データの取得に失敗しました: {error}
        </p>
      )}

      {report && !loading && !error && (
        <div className="app-main">
          <TodaySummary report={report} firstReveal={isFirstReveal} />

          <div className="app-details">
            <section className="rankings">
              <h2>過去の記録との比較</h2>
              <p className="rankings-note">
                平年より{report.today.label === '暑さ' ? '暑い' : '寒い'}ので、
                {report.today.label === '暑さ' ? '最高' : '最低'}気温でランキングします
              </p>
              <div className="rankings-grid">
                {report.rankings.reduce((acc, ranking) => {
                  // 表が2つあるので、上の表の行がすべて出終わった直後から
                  // 下の表が始まるよう、行数から開始遅延を積み上げて計算する
                  const rowCount = selectRankingRows(ranking, {
                    source: report.today.source,
                    todayDate: report.target_date,
                  }).length
                  const startDelay = acc.cumulativeDelay
                  acc.cumulativeDelay += rowCount * ROW_REVEAL_DELAY_MS
                  acc.elements.push(
                    <RankingTable
                      key={ranking.period_label}
                      ranking={ranking}
                      todaySource={report.today.source}
                      todayDate={report.target_date}
                      firstReveal={isFirstReveal}
                      rowStartDelay={startDelay}
                      rowDelayMs={ROW_REVEAL_DELAY_MS}
                    />,
                  )
                  return acc
                }, { cumulativeDelay: RANKING_REVEAL_BASE_DELAY_MS, elements: [] }).elements}
              </div>
            </section>

            <ClimateChart
              climateByDecade={report.climate_by_decade}
              targetMonth={Number(report.target_date.slice(5, 7))}
            />
          </div>
        </div>
      )}
    </div>
  )
}

export default App
