import { useState } from 'react'

// 優先度としては一番低い情報(地点・日付の変更)なので、控えめな見た目にする。
// 入力中の値と、実際に検索に使われている値を分けるため、
// 送信するまで親のstateは更新しない(入力途中でAPIを叩かないようにするため)
function LocationForm({ lat, lon, date, onSubmit }) {
  const [draftLat, setDraftLat] = useState(lat)
  const [draftLon, setDraftLon] = useState(lon)
  const [draftDate, setDraftDate] = useState(date)

  function handleSubmit(e) {
    e.preventDefault()
    onSubmit({ lat: draftLat, lon: draftLon, date: draftDate })
  }

  return (
    <form className="location-form" onSubmit={handleSubmit}>
      <label>
        緯度
        <input
          type="number"
          step="0.01"
          value={draftLat}
          onChange={(e) => setDraftLat(e.target.value)}
        />
      </label>
      <label>
        経度
        <input
          type="number"
          step="0.01"
          value={draftLon}
          onChange={(e) => setDraftLon(e.target.value)}
        />
      </label>
      <label>
        日付
        <input
          type="date"
          value={draftDate}
          onChange={(e) => setDraftDate(e.target.value)}
        />
      </label>
      <button type="submit">表示する</button>
    </form>
  )
}

export default LocationForm
