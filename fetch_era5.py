import json
import urllib.request
import urllib.parse

# さいたま市付近の座標
LATITUDE = 35.86
LONGITUDE = 139.65

TODAY_DATE = "2026-08-27"
TARGET_MONTH_DAY = TODAY_DATE[5:]

# --- 過去の気候値(ERA5アーカイブ) ---
# ERA5は数日の遅延があるため、直近すぎる日付は取得できない
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

archive_params = {
    "latitude": LATITUDE,
    "longitude": LONGITUDE,
    "start_date": "1996-08-27",
    "end_date": "2026-08-20",
    "daily": "temperature_2m_mean,temperature_2m_max,temperature_2m_min",
    "timezone": "Asia/Tokyo",
}

archive_url = f"{ARCHIVE_URL}?{urllib.parse.urlencode(archive_params)}"

with urllib.request.urlopen(archive_url) as response:
    archive_data = json.loads(response.read())

archive_daily = archive_data["daily"]

# 今日と同じ月日(8月27日)の過去データを抜き出す
same_day_records = [
    (date, mean, mx, mn)
    for date, mean, mx, mn in zip(
        archive_daily["time"],
        archive_daily["temperature_2m_mean"],
        archive_daily["temperature_2m_max"],
        archive_daily["temperature_2m_min"],
    )
    if date[5:] == TARGET_MONTH_DAY
]

normal = sum(r[1] for r in same_day_records) / len(same_day_records)

print(f"{TARGET_MONTH_DAY} の平年値(過去{len(same_day_records)}年の平均気温の平均): {normal:.1f}℃")

# --- Forecast APIのバイアス(ERA5とのズレ)を計算する ---
# ERA5データがある直近7日分を、Forecast APIでも同じ日付で取得して比較する
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

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
    "latitude": LATITUDE,
    "longitude": LONGITUDE,
    "daily": "temperature_2m_mean,temperature_2m_max,temperature_2m_min",
    "timezone": "Asia/Tokyo",
    "start_date": overlap_dates[0],
    "end_date": overlap_dates[-1],
}

overlap_url = f"{FORECAST_URL}?{urllib.parse.urlencode(overlap_params)}"

with urllib.request.urlopen(overlap_url) as response:
    overlap_forecast_data = json.loads(response.read())

overlap_forecast = overlap_forecast_data["daily"]

# 各日の「Forecast - ERA5」の差を集めて平均する = バイアス
mean_diffs = []
max_diffs = []
min_diffs = []
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

print(f"\n直近{len(overlap_dates)}日間のバイアス(Forecast - ERA5の平均): "
      f"平均 {bias_mean:+.1f}℃ / 最高 {bias_max:+.1f}℃ / 最低 {bias_min:+.1f}℃")

# --- 今日の値(Forecast API) ---
# ERA5にはまだ今日のデータがないので、Forecast APIから取得し、バイアス分を補正する
forecast_params = {
    "latitude": LATITUDE,
    "longitude": LONGITUDE,
    "daily": "temperature_2m_mean,temperature_2m_max,temperature_2m_min",
    "timezone": "Asia/Tokyo",
    "start_date": TODAY_DATE,
    "end_date": TODAY_DATE,
}

forecast_url = f"{FORECAST_URL}?{urllib.parse.urlencode(forecast_params)}"

with urllib.request.urlopen(forecast_url) as response:
    forecast_data = json.loads(response.read())

forecast_daily = forecast_data["daily"]
raw_today_mean = forecast_daily["temperature_2m_mean"][0]
raw_today_max = forecast_daily["temperature_2m_max"][0]
raw_today_min = forecast_daily["temperature_2m_min"][0]

# ERA5基準に揃えるため、バイアス分を差し引く
today_mean = raw_today_mean - bias_mean
today_max = raw_today_max - bias_max
today_min = raw_today_min - bias_min

print(f"今日({TODAY_DATE})の値(生データ): 平均 {raw_today_mean}℃ / 最高 {raw_today_max}℃ / 最低 {raw_today_min}℃")
print(f"今日({TODAY_DATE})の値(ERA5基準に補正後): 平均 {today_mean:.1f}℃ / 最高 {today_max:.1f}℃ / 最低 {today_min:.1f}℃")

deviation = today_mean - normal
print(f"平年との差: {deviation:+.1f}℃")

# --- 平年より暑ければ最高気温、寒ければ最低気温でランキング ---
if deviation >= 0:
    print("→ 平年より暑いので、最高気温でランキングします")
    value_index = 2  # (date, mean, mx, mn) の mx
    today_value = today_max
    order_desc = True
    label = "暑さ"
else:
    print("→ 平年より寒いので、最低気温でランキングします")
    value_index = 3  # (date, mean, mx, mn) の mn
    today_value = today_min
    order_desc = False
    label = "寒さ"

# --- ERA5のみの過去分布(データソースを混ぜない) ---
historical_ranked = sorted(same_day_records, key=lambda r: r[value_index], reverse=order_desc)
years = sorted(int(r[0][:4]) for r in same_day_records)
year_min, year_max = years[0], years[-1]

print(f"\n{TARGET_MONTH_DAY} の{label}ランキング(ERA5のみ、{year_min}〜{year_max}年、全{len(historical_ranked)}件):")
for rank, (date, mean, mx, mn) in enumerate(historical_ranked, start=1):
    value = mx if order_desc else mn
    print(f"  {rank:2d}位: {date}  {value:.1f} ℃")

# --- 今日(Forecast API由来)の値を、ERA5の分布に当てはめた場合の位置 ---
if order_desc:
    better_count = sum(1 for r in same_day_records if r[value_index] > today_value)
else:
    better_count = sum(1 for r in same_day_records if r[value_index] < today_value)
position = better_count + 1

print(f"\n今日({TODAY_DATE})の値は Forecast API 由来(ERA5基準にバイアス補正済み)の推定値です: {today_value:.1f}℃")
print(f"ERA5ベースの過去{len(same_day_records)}年({year_min}〜{year_max}年)の{label}分布に当てはめると、"
      f"{position}番目に位置します(過去の実測{len(same_day_records)}件中で数えた場合)")
