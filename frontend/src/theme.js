// 気温表示エリアの背景を、平年差(deviation)に応じて5段階で切り替えるための
// 色定義。彩度低め・明度高めの、インテリアに馴染むトーンでまとめている。
// 表示だけの話なので、ここでの閾値・配色は計算ロジック(core.py側)には影響しない。
const THEMES = [
  {
    key: 'cold-strong',
    threshold: -3,
    label: '大きくマイナス',
    base: '#ccd6e0',
    blobs: ['#b9c7d4', '#dfe7ee', '#a9bccb'],
  },
  {
    key: 'cold-mild',
    threshold: -1,
    label: 'ややマイナス',
    base: '#dcebee',
    blobs: ['#cfe2e6', '#eaf4f6', '#bfd9de'],
  },
  {
    key: 'normal',
    threshold: 1,
    label: '平年並み',
    base: '#f2ece0',
    blobs: ['#ebe2d0', '#f8f3e9', '#e3d7bf'],
  },
  {
    key: 'warm-mild',
    threshold: 3,
    label: 'ややプラス',
    base: '#eed7bd',
    blobs: ['#e5c49f', '#f5e7d2', '#dcb98e'],
  },
  {
    key: 'warm-strong',
    threshold: Infinity,
    label: '大きくプラス',
    base: '#dcae95',
    blobs: ['#cf9877', '#e8c2a8', '#c08563'],
  },
]

export function getTemperatureTheme(deviation) {
  return THEMES.find((t) => deviation < t.threshold) ?? THEMES[THEMES.length - 1]
}
