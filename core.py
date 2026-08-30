import calendar
import datetime
import json
import os
import urllib.request
import urllib.parse
import urllib.error
from collections import defaultdict

# --- キャッシュ ---
# 目的は速度ではなく、Open-Meteo側のレート制限(429)を避けること。
# ファイル名に地点・期間を含めておけば、期間が変わったときだけ
# 自動的にキャッシュミスして再取得される(=有効期限の管理が不要)。
CACHE_DIR = "cache"

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
# ERA5は数日の遅延があるため、直近すぎる日付は取得できない
ARCHIVE_END_DATE = "2026-08-20"


class RateLimitError(Exception):
    """Open-Meteo APIのレート制限(429 Too Many Requests)に達した"""


def cache_name(kind, latitude, longitude, params):
    return f"{kind}_{latitude}_{longitude}_{params['start_date']}_{params['end_date']}.json"


def fetch_daily(base_url, params, name, force_refresh):
    """daily データを取得する。キャッシュがあれば使い、なければ取得して保存する。"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, name)

    if not force_refresh and os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)["daily"]

    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url) as response:
            raw = response.read()
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise RateLimitError() from e
        raise

    with open(cache_path, "wb") as f:
        f.write(raw)

    return json.loads(raw)["daily"]


# --- 平年値の平滑化(気象庁のKZフィルタ: 9日移動平均を3回) ---
def month_day_sequence():
    """うるう年を除いた365日分の "MM-DD" を1/1から順に返す"""
    start = datetime.date(2001, 1, 1)  # 2001年は平年
    return [(start + datetime.timedelta(days=i)).strftime("%m-%d") for i in range(365)]


def build_daily_normal_series(daily, year_start, year_end):
    """指定した年範囲(year_start〜year_end)で、365日分(2/29を除く)の
    生の平年値を、month_day_sequence()と同じ並び順で計算する"""
    buckets = defaultdict(list)
    for date, mean in zip(daily["time"], daily["temperature_2m_mean"]):
        if mean is None:
            continue
        month_day = date[5:]
        if month_day == "02-29":
            continue
        year = int(date[:4])
        if year_start <= year <= year_end:
            buckets[month_day].append(mean)

    return [sum(buckets[md]) / len(buckets[md]) for md in month_day_sequence()]


def moving_average_9(series):
    """9日移動平均。年をまたぐ部分は循環(1/1の前は12/31)として扱う"""
    n = len(series)
    return [sum(series[(i + offset) % n] for offset in range(-4, 5)) / 9 for i in range(n)]


def kz_filter(series):
    """KZ(9,3)フィルタ: 9日移動平均を3回、前の結果に対して逐次かける"""
    result = series
    for _ in range(3):
        result = moving_average_9(result)
    return result


def lookup_normal(smoothed_series, month_day):
    """平滑化済みシリーズから対象日の値を取り出す。
    2/29は統計から除外しているので、2/28と3/1の平均で埋める"""
    order = month_day_sequence()
    if month_day == "02-29":
        return (smoothed_series[order.index("02-28")] + smoothed_series[order.index("03-01")]) / 2
    return smoothed_series[order.index(month_day)]


def build_ranking(records, period_label, value_index, order_desc, label, today_value):
    """実測レコードを順位付けし、今日の値を挿入するとしたら何位に当たるかを添えて返す。
    表示の間引き(上位N件+今日周辺のみ表示等)は呼び出し側の仕事なので、ここでは全件返す"""
    ranked = sorted(records, key=lambda r: r[value_index], reverse=order_desc)
    years = sorted(int(r[0][:4]) for r in records)

    if order_desc:
        better_count = sum(1 for r in records if r[value_index] > today_value)
    else:
        better_count = sum(1 for r in records if r[value_index] < today_value)
    today_position = better_count + 1  # 今日を挿入するとしたら何位に当たるか

    return {
        "period_label": period_label,
        "label": label,
        "year_min": years[0],
        "year_max": years[-1],
        "total": len(ranked),
        "today_position": today_position,
        "today_value": today_value,
        "records": [
            {"rank": rank, "date": r[0], "value": r[value_index]}
            for rank, r in enumerate(ranked, start=1)
        ],
    }


def build_report(latitude, longitude, target_date, *, raw=False, force_refresh=False):
    """指定地点・対象日について、平年値・今日の値・ランキングをまとめて計算し、dictで返す。
    print や sys.exit は行わない(呼び出し側の責務)"""
    today_date = target_date.isoformat()
    target_month_day = today_date[5:]

    # --- 過去の気候値(ERA5アーカイブ) ---
    archive_params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": "1940-01-01",  # ERA5で取得できる最古の日付
        "end_date": ARCHIVE_END_DATE,
        "daily": "temperature_2m_mean,temperature_2m_max,temperature_2m_min",
        "timezone": "Asia/Tokyo",
    }
    archive_daily = fetch_daily(
        ARCHIVE_URL,
        archive_params,
        cache_name("archive", latitude, longitude, archive_params),
        force_refresh,
    )

    # --- この地点の気候(10年ごとの対象月平均気温) ---
    # 対象月全体の平均を使うことで、1日単位のばらつきを均して長期トレンドを見やすくする
    target_month = int(target_month_day[:2])
    month_by_year = defaultdict(list)
    for date, mean in zip(archive_daily["time"], archive_daily["temperature_2m_mean"]):
        if mean is None:
            continue
        year, month = date[:4], date[5:7]
        if int(month) == target_month:
            month_by_year[year].append(mean)

    decade_values = defaultdict(list)
    for year, values in month_by_year.items():
        expected_days = calendar.monthrange(int(year), target_month)[1]
        if len(values) < expected_days:
            continue  # その年のその月はまだ全日揃っていない(未来 or 欠損)
        decade_values[(int(year) // 10) * 10].append(sum(values) / len(values))

    climate_by_decade = [
        {"decade": d, "avg": sum(v) / len(v), "count": len(decade_values[d])}
        for d, v in sorted(decade_values.items())
    ]

    # 今日と同じ月日の過去データを抜き出す
    same_day_records = [
        (date, mean, mx, mn)
        for date, mean, mx, mn in zip(
            archive_daily["time"],
            archive_daily["temperature_2m_mean"],
            archive_daily["temperature_2m_max"],
            archive_daily["temperature_2m_min"],
        )
        if date[5:] == target_month_day
    ]

    # 平年値A: 1991-2020年の固定30年(気象庁の公式基準と同じ期間)
    normal_records_a = [r for r in same_day_records if 1991 <= int(r[0][:4]) <= 2020]
    raw_normal_a = sum(r[1] for r in normal_records_a) / len(normal_records_a)

    # 平年値B: 直近30年のローリング
    years_with_target_day = sorted(int(r[0][:4]) for r in same_day_records)
    year_end_b = years_with_target_day[-1]
    year_start_b = year_end_b - 29
    normal_records_b = [r for r in same_day_records if year_start_b <= int(r[0][:4]) <= year_end_b]
    raw_normal_b = sum(r[1] for r in normal_records_b) / len(normal_records_b)

    if raw:
        normal_a = raw_normal_a
        normal_b = raw_normal_b
    else:
        smoothed_a = kz_filter(build_daily_normal_series(archive_daily, 1991, 2020))
        smoothed_b = kz_filter(build_daily_normal_series(archive_daily, year_start_b, year_end_b))
        normal_a = lookup_normal(smoothed_a, target_month_day)
        normal_b = lookup_normal(smoothed_b, target_month_day)

    # 「平年との差」の判定基準は、最新の気候を反映するB(直近30年ローリング)を使う
    normal = normal_b

    # --- Forecast APIのバイアス(ERA5とのズレ)を計算する ---
    overlap_dates = archive_daily["time"][-7:]
    overlap_era5 = {
        date: (mean, mx, mn)
        for date, mean, mx, mn in zip(
            archive_daily["time"],
            archive_daily["temperature_2m_mean"],
            archive_daily["temperature_2m_max"],
            archive_daily["temperature_2m_min"],
        )
        if date in overlap_dates
    }

    overlap_params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": "temperature_2m_mean,temperature_2m_max,temperature_2m_min",
        "timezone": "Asia/Tokyo",
        "start_date": overlap_dates[0],
        "end_date": overlap_dates[-1],
    }
    overlap_forecast = fetch_daily(
        FORECAST_URL,
        overlap_params,
        cache_name("overlap", latitude, longitude, overlap_params),
        force_refresh,
    )

    mean_diffs, max_diffs, min_diffs = [], [], []
    for date, f_mean, f_mx, f_mn in zip(
        overlap_forecast["time"],
        overlap_forecast["temperature_2m_mean"],
        overlap_forecast["temperature_2m_max"],
        overlap_forecast["temperature_2m_min"],
    ):
        e_mean, e_mx, e_mn = overlap_era5[date]
        mean_diffs.append(f_mean - e_mean)
        max_diffs.append(f_mx - e_mx)
        min_diffs.append(f_mn - e_mn)

    bias_mean = sum(mean_diffs) / len(mean_diffs)
    bias_max = sum(max_diffs) / len(max_diffs)
    bias_min = sum(min_diffs) / len(min_diffs)

    # --- 今日の値(Forecast API) ---
    # ERA5にはまだ今日のデータがないので、Forecast APIから取得し、バイアス分を補正する
    forecast_params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": "temperature_2m_mean,temperature_2m_max,temperature_2m_min",
        "timezone": "Asia/Tokyo",
        "start_date": today_date,
        "end_date": today_date,
    }
    forecast_daily = fetch_daily(
        FORECAST_URL,
        forecast_params,
        cache_name("forecast", latitude, longitude, forecast_params),
        force_refresh,
    )
    raw_today_mean = forecast_daily["temperature_2m_mean"][0]
    raw_today_max = forecast_daily["temperature_2m_max"][0]
    raw_today_min = forecast_daily["temperature_2m_min"][0]

    # ERA5基準に揃えるため、バイアス分を差し引く
    today_mean = raw_today_mean - bias_mean
    today_max = raw_today_max - bias_max
    today_min = raw_today_min - bias_min

    deviation = today_mean - normal

    # --- 平年より暑ければ最高気温、寒ければ最低気温でランキング ---
    if deviation >= 0:
        value_index = 2  # (date, mean, mx, mn) の mx
        today_value = today_max
        order_desc = True
        label = "暑さ"
    else:
        value_index = 3  # (date, mean, mx, mn) の mn
        today_value = today_min
        order_desc = False
        label = "寒さ"

    # --- ERA5のみの過去分布(データソースを混ぜない) ---
    # 1940-1978年は衛星観測が本格化する前で信頼度が下がるため、
    # 「全期間(1940年以降)」と「衛星観測時代(1979年以降)」の2種類を出す
    records_1940 = same_day_records
    records_1979 = [r for r in same_day_records if int(r[0][:4]) >= 1979]

    rankings = [
        build_ranking(records_1940, "ERA5 1940年以降・全期間", value_index, order_desc, label, today_value),
        build_ranking(records_1979, "ERA5 1979年以降・衛星観測時代", value_index, order_desc, label, today_value),
    ]

    return {
        "location": {"lat": latitude, "lon": longitude},
        "target_date": today_date,
        "raw_mode": raw,
        "climate_by_decade": climate_by_decade,
        "normals": {
            "a": {
                "year_start": 1991, "year_end": 2020,
                "count": len(normal_records_a),
                "raw": raw_normal_a,
                "smoothed": normal_a,
            },
            "b": {
                "year_start": year_start_b, "year_end": year_end_b,
                "count": len(normal_records_b),
                "raw": raw_normal_b,
                "smoothed": normal_b,
            },
            "diff_b_minus_a": normal_b - normal_a,
        },
        "bias": {
            "mean": bias_mean, "max": bias_max, "min": bias_min,
            "overlap_days": len(overlap_dates),
        },
        "today": {
            "raw": {"mean": raw_today_mean, "max": raw_today_max, "min": raw_today_min},
            "corrected": {"mean": today_mean, "max": today_max, "min": today_min},
            "deviation": deviation,
            "label": label,
        },
        "rankings": rankings,
    }
