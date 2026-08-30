import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import core

app = FastAPI()

# 開発中はFastAPI(例: :8000)とViteの開発サーバー(:5173)がポートが異なり、
# ブラウザからは別オリジン扱いになるため、フロントエンドからのアクセスを許可する
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
)


@app.get("/api/report")
def get_report(
    lat: float = 35.86,
    lon: float = 139.65,
    date: datetime.date | None = None,
    raw: bool = False,
    no_cache: bool = False,
):
    target_date = date or datetime.date.today()

    try:
        return core.build_report(lat, lon, target_date, raw=raw, force_refresh=no_cache)
    except core.RateLimitError:
        raise HTTPException(
            status_code=503,
            detail="Open-Meteo APIのレート制限(429 Too Many Requests)に達しました。しばらく時間をおいてから再実行してください。",
        )
