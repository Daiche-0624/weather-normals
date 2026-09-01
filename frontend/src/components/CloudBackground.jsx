import { useId } from 'react'

// 気温表示エリアの背景に敷く、雲のようなムラをSVGのfeTurbulence(パーリンノイズ)で
// 作る。単純なぼかし円(filter: blur)だと輪郭が幾何学的すぎて雲に見えなかったため、
// ノイズの濃淡をfeColorMatrixで「アルファマスク」に変換し、feCompositeで色の板に
// 重ねるという手順にしている(ノイズが薄い部分は透明になり、地の背景色が透ける)。
// 3枚のレイヤー(白寄り・黒寄り・テーマの強調色寄り)を重ねて濃淡の差をはっきり
// 出しつつ、それぞれ違う速度でtransformをゆっくり動かして奥行きを出す
const LAYERS = [
  {
    className: 'cloud-layer cloud-layer-a',
    seed: 2,
    baseFrequency: '0.007 0.011',
    freqWobble: '0.006 0.010',
    dur: '34s',
    fillMix: 'color-mix(in srgb, white 46%, var(--theme-base))',
    opacity: 0.75,
  },
  {
    className: 'cloud-layer cloud-layer-b',
    seed: 11,
    baseFrequency: '0.011 0.016',
    freqWobble: '0.009 0.019',
    dur: '27s',
    fillMix: 'color-mix(in srgb, black 20%, var(--theme-base))',
    opacity: 0.5,
  },
  {
    className: 'cloud-layer cloud-layer-c',
    seed: 19,
    baseFrequency: '0.016 0.009',
    freqWobble: '0.020 0.007',
    dur: '22s',
    fillMix: 'color-mix(in srgb, var(--accent) 42%, var(--theme-base))',
    opacity: 0.55,
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
                numOctaves={3}
                seed={layer.seed}
                stitchTiles="stitch"
                result="noise"
              >
                <animate
                  attributeName="baseFrequency"
                  dur={layer.dur}
                  values={`${layer.baseFrequency};${layer.freqWobble};${layer.baseFrequency}`}
                  repeatCount="indefinite"
                />
              </feTurbulence>
              <feColorMatrix
                in="noise"
                type="matrix"
                values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0.5 0.5 0.5 0 -0.5"
                result="mask"
              />
              <feComposite in="SourceGraphic" in2="mask" operator="in" />
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
