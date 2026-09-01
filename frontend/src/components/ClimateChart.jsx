import { useEffect, useRef, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

// スマホ幅(375px前後)だと9個の年代ラベルが横並びでは重なって読めなくなる。
// 横画面レイアウト(App.css側で気温カード+詳細の2カラムにする)だと、
// 画面自体は広くてもグラフの実際の描画幅は狭くなるため、window幅ではなく
// グラフを囲むコンテナ自身の実測幅で判定する(PCの通常レイアウトの見た目は
// 幅が十分あるので変わらない)
function useIsNarrowContainer(ref, threshold = 560) {
  const [isNarrow, setIsNarrow] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return

    const observer = new ResizeObserver((entries) => {
      setIsNarrow(entries[0].contentRect.width < threshold)
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [ref, threshold])

  return isNarrow
}

// SVGの<text>は"\n"では改行されないため、"年代"と"※n年分"を別のtspanに分けて
// 2行で描画する(1行のままだと、特に右端の棒でラベルが表示領域からはみ出す)。
// 狭い画面では2行に分ける余地すらないため、「1940年代」→「40年代」と短縮した上で
// 斜めに表示して重なりを避ける("※n年分"の注記はツールチップ側で確認できるため省略)
function DecadeTick({ x, y, payload, isNarrow }) {
  const [main, note] = payload.value.split('\n')

  if (isNarrow) {
    const shortLabel = main.replace(/^(19|20)/, '')
    return (
      <g transform={`translate(${x},${y})`}>
        <text textAnchor="end" fontSize={11} fill="#666" transform="rotate(-40)" dx={-2} dy={8}>
          {shortLabel}
        </text>
      </g>
    )
  }

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
  const containerRef = useRef(null)
  const isNarrow = useIsNarrowContainer(containerRef)
  const data = climateByDecade.map((d) => ({
    label: `${d.decade}年代${d.count < 10 ? `\n(※${d.count}年分)` : ''}`,
    avg: Number(d.avg.toFixed(2)),
  }))
  const minAvg = Math.min(...data.map((d) => d.avg))
  const maxAvg = Math.max(...data.map((d) => d.avg))
  const domainMin = Math.floor(minAvg - 0.5)
  const domainMax = Math.ceil(maxAvg + 0.5)

  return (
    <section className="climate-chart" ref={containerRef}>
      <h2>10年ごとの{targetMonth}月平均気温の推移</h2>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart
          data={data}
          margin={{ top: 8, right: 24, left: 0, bottom: isNarrow ? 20 : 8 }}
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="label"
            height={isNarrow ? 52 : 40}
            interval={0}
            tick={<DecadeTick isNarrow={isNarrow} />}
          />
          <YAxis domain={[domainMin, domainMax]} unit="℃" tick={{ fontSize: 12 }} />
          <Tooltip formatter={(value) => [`${value} ℃`, '平均気温']} />
          <Bar dataKey="avg" fill="var(--accent)" radius={[10, 10, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </section>
  )
}

export default ClimateChart
