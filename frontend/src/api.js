// Viteはビルド時に環境変数を埋め込む(実行時にはos.environ的な読み方はできない)。
// クライアントに渡してよい変数だけ公開するため、VITE_ 接頭辞が付いたものだけが
// import.meta.env経由で見える。本番(Vercel)ではVITE_API_BASEにRenderのURLを
// 設定する。ローカル開発では未設定のままでよく、その場合は右側の既定値を使う
const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export async function fetchReport({ lat, lon, date }) {
  const params = new URLSearchParams({ lat, lon, date })
  const res = await fetch(`${API_BASE}/api/report?${params}`)

  if (!res.ok) {
    // FastAPI側は422(不正な入力)や503(レート制限)のときdetailにメッセージを入れて返す
    const body = await res.json().catch(() => null)
    const detail = body?.detail
    // 422(入力バリデーションエラー)のときはdetailが配列で返ってくる
    const message = typeof detail === 'string'
      ? detail
      : Array.isArray(detail)
        ? detail.map((d) => d.msg).join(' / ')
        : res.statusText
    throw new Error(`APIエラー(${res.status}): ${message}`)
  }

  return res.json()
}
