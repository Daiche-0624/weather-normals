import { useId } from 'react'

// 気温表示エリアの背景に敷く、雲のようなムラをSVGのfeTurbulence(パーリンノイズ)で
// 作る。単純なぼかし円(filter: blur)だと輪郭が幾何学的すぎて雲に見えなかったため、
// ノイズの濃淡をfeColorMatrixで「アルファマスク」に変換し、feCompositeで色の板に
// 重ねるという手順にしている(ノイズが薄い部分は透明になり、地の「空」の色が透ける)。
//
// baseFrequencyは固定値で、ノイズのパターン自体は静的(1回生成したら変化しない)。
// 動きはCSS側(App.cssの.cloud-layer/.cloud-drift)のtransformだけで作っている。
// 以前はfeTurbulenceのbaseFrequencyをSMILで揺らしていたが、これは毎フレーム
// ノイズを再計算し直す重い処理でカクついていた。静的なノイズをtransformで
// ゆっくり移動・拡大縮小させるほうが、ブラウザがGPU合成できるぶん軽く滑らかになる
//
// 雲そのものは常に白系で固定している(色は空側=theme.baseで表現するため)。
// 3枚重ねているのは、白一色だとのっぺりするため、明るい本体(a)・影になる下側(b、
// 空の色をわずかに拾わせて自然な陰影にする)・薄いもや(c)で奥行きを出すため。
// 最初に平年差テーマの色そのもので雲を塗ったところ地の色と近すぎて知覚できず、
// 白の割合を下げすぎたのが原因だった。この反省から、白は必ず75%以上を保っている
const LAYERS = [
  {
    className: 'cloud-layer cloud-layer-a',
    seed: 2,
    baseFrequency: '0.014 0.018',
    fillMix: '#ffffff',
    opacity: 1,
    // tableValuesは「下位67%のノイズは透明・上位33%は不透明」という階段関数。
    // 単純な一次式(matrix)でしきい値を作ると、ノイズの分散が小さいときに
    // ほぼ全域が閾値の内側/外側どちらかに寄ってしまい、雲がまったく
    // 見えなくなる(実際に3回失敗した)。discreteのテーブルで明示的に
    // 「上位何%を雲にするか」を指定する方が確実に効く
    tableValues: '0 0 0 1 1',
  },
  {
    className: 'cloud-layer cloud-layer-b',
    seed: 11,
    baseFrequency: '0.011 0.015',
    fillMix: 'color-mix(in srgb, white 72%, var(--theme-base))',
    opacity: 0.85,
    tableValues: '0 0 0 0 1 1',
  },
  {
    className: 'cloud-layer cloud-layer-c',
    seed: 19,
    baseFrequency: '0.018 0.012',
    fillMix: 'color-mix(in srgb, white 85%, var(--theme-base))',
    opacity: 0.6,
    tableValues: '0 0 0 1 1 1',
  },
]

function CloudBackground() {
  // フィルターidが複数インスタンス間で衝突しないようにuseIdで一意化する
  const uid = useId().replace(/:/g, '')

  return (
    <svg
      className="cloud-bg"
      aria-hidden="true"
      viewBox="0 0 400 200"
      preserveAspectRatio="xMidYMid slice"
    >
      {LAYERS.map((layer, i) => {
        const filterId = `${uid}-cloud-${i}`
        return (
          <g key={filterId} className={layer.className}>
            <filter id={filterId} x="-30%" y="-40%" width="160%" height="180%">
              <feTurbulence
                type="fractalNoise"
                baseFrequency={layer.baseFrequency}
                numOctaves={4}
                seed={layer.seed}
                stitchTiles="stitch"
                result="noise"
              />
              <feColorMatrix in="noise" type="luminanceToAlpha" result="luminance" />
              <feComponentTransfer in="luminance" result="mask">
                <feFuncA type="discrete" tableValues={layer.tableValues} />
              </feComponentTransfer>
              <feGaussianBlur in="mask" stdDeviation="1.5" result="softMask" />
              <feComposite in="SourceGraphic" in2="softMask" operator="in" />
            </filter>
            <rect
              x="-120"
              y="-80"
              width="640"
              height="360"
              fill={layer.fillMix}
              opacity={layer.opacity}
              filter={`url(#${filterId})`}
            />
          </g>
        )
      })}
    </svg>
  )
}

export default CloudBackground
