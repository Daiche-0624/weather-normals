// 気温表示エリアの「空」の色(および、そこから派生させるボタンやハイライトなど
// サイト全体のアクセントカラー)を、平年差(deviation)に応じて5段階で切り替える
// ための色定義。
//
// 雲そのものは常に白系で固定し(CloudBackground.jsx参照)、この base(空の色)側を
// 平年差でグラデーションさせる: 寒いほど青みが強く、暑いほど夕焼けのような
// オレンジ〜ピンクに近づく。accent(ボタン・ハイライトなど強調色)は同じ空の色を
// 濃くした値にして、系統が揃うようにしている。
//
// 表示だけの話なので、ここでの閾値・配色は計算ロジック(core.py側)には影響しない。
const THEMES = [
  {
    key: 'cold-strong',
    threshold: -3,
    label: '大きくマイナス',
    base: '#82a7cc',
    accent: '#3c6690',
  },
  {
    key: 'cold-mild',
    threshold: -1,
    label: 'ややマイナス',
    base: '#b3d0e3',
    accent: '#3a7a9c',
  },
  {
    key: 'normal',
    threshold: 1,
    label: '平年並み',
    base: '#d7ecf3',
    accent: '#4f92b0',
  },
  {
    key: 'warm-mild',
    threshold: 3,
    label: 'ややプラス',
    base: '#f3dcc0',
    accent: '#c07a3a',
  },
  {
    key: 'warm-strong',
    threshold: Infinity,
    label: '大きくプラス',
    base: '#eebfa4',
    accent: '#b85a2e',
  },
]

export function getTemperatureTheme(deviation) {
  return THEMES.find((t) => deviation < t.threshold) ?? THEMES[THEMES.length - 1]
}
