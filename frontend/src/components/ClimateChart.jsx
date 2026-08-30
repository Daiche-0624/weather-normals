import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

// SVGの<text>は"\n"では改行されないため、"年代"と"※n年分"を別のtspanに分けて
// 2行で描画する(1行のままだと、特に右端の棒でラベルが表示領域からはみ出す)
function DecadeTick({ x, y, payload }) {
  const [main, note] = payload.value.split('\n')
  return (
    <g transform={`translate(${x},${y})`}>
      <text textAnchor="middle" fontSize={12} fill="#666">
        <tspan x={0} dy="0.9em">{main}</tspan>
        {note && (
          <tspan x={0} dy="1.2em" fontSize={10}>
            {note}
          </tspan>
        )}
      </text>
    </g>
  )
}

// 10年ごとの対象月平均気温を棒グラフで表示する。
// 気温の絶対値ではなく差が見たいグラフなので、Y軸は0からではなく
// データの最小値付近から始める(そうしないと横ばい部分の変化が見えない)
function ClimateChart({ climateByDecade, targetMonth }) {
  const data = climateByDecade.map((d) => ({
    label: `${d.decade}年代${d.count < 10 ? `\n(※${d.count}年分)` : ''}`,
    avg: Number(d.avg.toFixed(2)),
  }))
  const minAvg = Math.min(...data.map((d) => d.avg))
  const maxAvg = Math.max(...data.map((d) => d.avg))
  const domainMin = Math.floor(minAvg - 0.5)
  const domainMax = Math.ceil(maxAvg + 0.5)

  return (
    <section className="climate-chart">
      <h2>10年ごとの{targetMonth}月平均気温の推移</h2>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} margin={{ top: 8, right: 24, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" height={40} interval={0} tick={<DecadeTick />} />
          <YAxis domain={[domainMin, domainMax]} unit="℃" tick={{ fontSize: 12 }} />
          <Tooltip formatter={(value) => [`${value} ℃`, '平均気温']} />
          <Bar dataKey="avg" fill="#4c78a8" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </section>
  )
}

export default ClimateChart
