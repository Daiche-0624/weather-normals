// 気温表示エリア(および、そこから派生させるボタンやハイライトなどサイト全体の
// アクセントカラー)を、平年差(deviation)に応じて5段階で切り替えるための色定義。
//
// 意図的に持つ色は base(背景の基調色)と accent(ボタン・ハイライトなど強調色)の
// 2つだけにしている。雲の濃淡やページ全体のうっすらした色味は、この2色から
// CSSのcolor-mix()でその場で導出する(App.css参照)。色の元になる値を1箇所に
// 絞ることで、「背景は青系なのにボタンは紫」のような系統のバラつきを防ぐ。
//
// 表示だけの話なので、ここでの閾値・配色は計算ロジック(core.py側)には影響しない。
const THEMES = [
  {
    key: 'cold-strong',
    threshold: -3,
    label: '大きくマイナス',
    base: '#a9bccb',
    accent: '#3f6690',
  },
  {
    key: 'cold-mild',
    threshold: -1,
    label: 'ややマイナス',
    base: '#bfd9de',
    accent: '#2f7f95',
  },
  {
    key: 'normal',
    threshold: 1,
    label: '平年並み',
    base: '#e3d7bf',
    accent: '#8a6d3f',
  },
  {
    key: 'warm-mild',
    threshold: 3,
    label: 'ややプラス',
    base: '#dcb98e',
    accent: '#b5652b',
  },
  {
    key: 'warm-strong',
    threshold: Infinity,
    label: '大きくプラス',
    base: '#c08563',
    accent: '#a1451e',
  },
]

export function getTemperatureTheme(deviation) {
  return THEMES.find((t) => deviation < t.threshold) ?? THEMES[THEMES.length - 1]
}
