import { getTemperatureTheme } from '../theme'

function formatSigned(value) {
  const rounded = value.toFixed(1)
  return value >= 0 ? `+${rounded}` : rounded
}

// 今日の気温・平年値・その差を一番大きく見せるセクション。
// 「今日の値の出自(ERA5実測 or Forecast API推定)」「平年値A・Bの両方」という
// データの出自を隠さないため、注記も一緒に表示する。
//
// 背景は平年差(deviation)に応じた色のぼかし楕円("雲")で演出する。
// firstReveal は「このセッションで最初に表示されたときだけtrue」というフラグで、
// 地点・日付を変えて再表示するときはfalseになり、CSSアニメーションは発火しない
// (クラス名が最初から付かないため、CSSの再生条件そのものに乗らない)
function TodaySummary({ report, firstReveal }) {
  const { today, normals, target_date: targetDate } = report
  const isHot = today.deviation >= 0
  const isEra5 = today.source === 'era5'
  const mainValue = isEra5 ? today.value.mean : today.corrected.mean
  const theme = getTemperatureTheme(today.deviation)

  return (
    <section
      className={`today-summary theme-${theme.key} ${firstReveal ? 'first-reveal' : ''}`}
      style={{
        '--card-bg': theme.base,
        '--blob-1': theme.blobs[0],
        '--blob-2': theme.blobs[1],
        '--blob-3': theme.blobs[2],
      }}
    >
      <div className="today-summary-bg" aria-hidden="true">
        <span className="blob blob-1" />
        <span className="blob blob-2" />
        <span className="blob blob-3" />
      </div>

      <div className="today-summary-content">
        <p className="target-date">{targetDate} の気温</p>

        <div className="today-main">
          <div className="today-value">
            <span className="today-value-number">{mainValue.toFixed(1)}</span>
            <span className="today-value-unit">℃</span>
          </div>
          <div className={`deviation ${isHot ? 'deviation-hot' : 'deviation-cold'}`}>
            平年より {formatSigned(today.deviation)}℃({isHot ? '暑い' : '寒い'})
          </div>
        </div>

        {isEra5 ? (
          <p className="data-note">
            この日はERA5の実測値です(推定・補正なし: 平均 {today.value.mean}℃ /
            最高 {today.value.max}℃ / 最低 {today.value.min}℃)
          </p>
        ) : (
          <p className="data-note">
            対象日の値は Forecast API 由来の推定値です(ERA5基準にバイアス補正済み、
            生データ: 平均 {today.raw.mean}℃ / 最高 {today.raw.max}℃ / 最低 {today.raw.min}℃)
          </p>
        )}

        <div className="normals-grid">
          <div className="normal-card">
            <p className="normal-label">平年値A(1991-2020年固定)</p>
            <p className="normal-value">{normals.a.smoothed.toFixed(1)}℃</p>
          </div>
          <div className="normal-card">
            <p className="normal-label">
              平年値B(直近{normals.b.count}年ローリング、{normals.b.year_start}-{normals.b.year_end})
            </p>
            <p className="normal-value">{normals.b.smoothed.toFixed(1)}℃</p>
          </div>
        </div>
        <p className="data-note">
          AとBの差: {formatSigned(normals.diff_b_minus_a)}℃
          (A: 1991-2020年 / B: {normals.b.year_start}-{normals.b.year_end}年の基準期間の違いを含む)
          ・「平年との差」の判定にはBを使用
        </p>
      </div>
    </section>
  )
}

export default TodaySummary
