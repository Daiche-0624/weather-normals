import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from collections import defaultdict

# さいたま市付近の座標
LATITUDE = 35.86
LONGITUDE = 139.65

TODAY_DATE = "2026-08-27"
TARGET_MONTH_DAY = TODAY_DATE[5:]

# --- キャッシュ ---
# 目的は速度ではなく、Open-Meteo側のレート制限(429)を避けること。
# ファイル名に地点・期間を含めておけば、期間が変わったときだけ
# 自動的にキャッシュミスして再取得される(=有効期限の管理が不要)。
CACHE_DIR = "cache"
FORCE_REFRESH = "--no-cache" in sys.argv  # このオプションを付けるとキャッシュを無視する


def cache_name(kind, params):
    return f"{kind}_{LATITUDE}_{LONGITUDE}_{params['start_date']}_{params['end_date']}.json"


def fetch_daily(base_url, params, name):
    """daily データを取得する。キャッシュがあれば使い、なければ取得して保存する。"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, name)

    if not FORCE_REFRESH and os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            return json.load(f)["daily"]

    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url) as response:
            raw = response.read()
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print("エラー: Open-Meteo APIのレート制限(429 Too Many Requests)に達しました。")
            print("しばらく時間をおいてから再実行してください。")
            sys.exit(1)
        raise

    with open(cache_path, "wb") as f:
        f.write(raw)

    return json.loads(raw)["daily"]


# --- 過去の気候値(ERA5アーカイブ) ---
# ERA5は数日の遅延があるため、直近すぎる日付は取得できない
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

archive_params = {
    "latitude": LATITUDE,
    "longitude": LONGITUDE,
    "start_date": "1940-01-01",  # ERA5で取得できる最古の日付
    "end_date": "2026-08-20",
    "daily": "temperature_2m_mean,temperature_2m_max,temperature_2m_min",
    "timezone": "Asia/Tokyo",
}

archive_daily = fetch_daily(ARCHIVE_URL, archive_params, cache_name("archive", archive_params))

# --- この地点の気候(10年ごとの8月平均気温) ---
# 8/27単日ではなく8月全体の平均を使うことで、1日単位のばらつきを均して
# 長期トレンド(70年ほぼ横ばい→直近15年で急上昇)を見やすくする
august_by_year = defaultdict(list)
for date, mean in zip(archive_daily["time"], archive_daily["temperature_2m_mean"]):
    if mean is None:
        continue
    year, month = date[:4], date[5:7]
    if month == "08":
        august_by_year[year].append(mean)

decade_values = defaultdict(list)
for year, values in august_by_year.items():
    if int(year) == 2026:
        continue  # 2026年8月はまだ全日揃っていないので除外
    decade_values[(int(year) // 10) * 10].append(sum(values) / len(values))

decade_avgs = {d: sum(v) / len(v) for d, v in decade_values.items()}
base = min(decade_avgs.values())

print(f"--- この地点の気候(10年ごとの8月平均気温、{LATITUDE}, {LONGITUDE}) ---")
for d in sorted(decade_avgs):
    avg = decade_avgs[d]
    count = len(decade_values[d])
    bar = "■" * (int((avg - base) * 10) + 1)
    note = f"  ※{count}年分" if count != 10 else ""  # 10年に満たない区切りは母数を明記する
    print(f"  {d}年代: {avg:5.2f}℃ {bar}{note}")
print()

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

# 平年値A: 1991-2020年の固定30年(気象庁の公式基準と同じ期間)
normal_records_a = [r for r in same_day_records if 1991 <= int(r[0][:4]) <= 2020]
normal_a = sum(r[1] for r in normal_records_a) / len(normal_records_a)

# 平年値B: 直近30年のローリング(same_day_recordsは日付順なので末尾30件)
normal_records_b = same_day_records[-30:]
normal_b = sum(r[1] for r in normal_records_b) / len(normal_records_b)

print(f"{TARGET_MONTH_DAY} の平年値A(1991-2020年固定、{len(normal_records_a)}年分): {normal_a:.1f}℃")
print(f"{TARGET_MONTH_DAY} の平年値B(直近{len(normal_records_b)}年ローリング): {normal_b:.1f}℃")
print(f"AとBの差(B-A、温暖化の目安): {normal_b - normal_a:+.1f}℃")

# 「平年との差」の判定基準は、最新の気候を反映するB(直近30年ローリング)を使う
normal = normal_b

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

overlap_forecast = fetch_daily(FORECAST_URL, overlap_params, cache_name("overlap", overlap_params))

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

forecast_daily = fetch_daily(FORECAST_URL, forecast_params, cache_name("forecast", forecast_params))
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
# 1940-1978年は衛星観測が本格化する前で信頼度が下がるため、
# 「全期間(1940年以降)」と「衛星観測時代(1979年以降)」の2種類を出す
def print_ranking(records, period_label):
    ranked = sorted(records, key=lambda r: r[value_index], reverse=order_desc)
    years = sorted(int(r[0][:4]) for r in records)
    year_min, year_max = years[0], years[-1]

    print(f"\n{TARGET_MONTH_DAY} の{label}ランキング({period_label}、{year_min}〜{year_max}年、全{len(ranked)}件):")
    for rank, (date, mean, mx, mn) in enumerate(ranked, start=1):
        value = mx if order_desc else mn
        print(f"  {rank:2d}位: {date}  {value:.1f} ℃")

    if order_desc:
        better_count = sum(1 for r in records if r[value_index] > today_value)
    else:
        better_count = sum(1 for r in records if r[value_index] < today_value)
    position = better_count + 1

    print(f"今日({TODAY_DATE})の値は Forecast API 由来(ERA5基準にバイアス補正済み)の推定値です: {today_value:.1f}℃")
    print(f"{period_label}の過去{len(records)}年({year_min}〜{year_max}年)の{label}分布に当てはめると、"
          f"{position}番目に位置します(過去の実測{len(records)}件中で数えた場合)")


records_1940 = same_day_records
records_1979 = [r for r in same_day_records if int(r[0][:4]) >= 1979]

print_ranking(records_1940, "ERA5 1940年以降・全期間")
print_ranking(records_1979, "ERA5 1979年以降・衛星観測時代")
