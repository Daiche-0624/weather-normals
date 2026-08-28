import datetime

from fastapi import FastAPI, HTTPException

import core

app = FastAPI()


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
