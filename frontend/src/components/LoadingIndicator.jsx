import { useEffect, useState } from 'react'

// Renderの無料プランはスリープからの復帰に50秒ほどかかることがあり、
// その間「読み込み中...」のまま止まって見えると壊れたと誤解されやすい。
// 経過時間に応じてメッセージを変え、今何が起きているかを伝える
const MESSAGES = [
  { after: 0, text: '読み込み中...' },
  { after: 5, text: 'データを取得しています...' },
  { after: 10, text: 'サーバーを起動しています。初回は50秒ほどかかることがあります' },
  { after: 40, text: 'もう少しお待ちください...' },
]

function LoadingIndicator() {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const start = Date.now()
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - start) / 1000))
    }, 1000)
    return () => clearInterval(id)
  }, [])

  const message = MESSAGES.filter((m) => elapsed >= m.after).at(-1).text

  return (
    <div className="loading">
      <span className="spinner" aria-hidden="true" />
      <p className="status-message">{message}</p>
    </div>
  )
}

export default LoadingIndicator
