import argparse
import datetime
import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error
from collections import defaultdict


def parse_args():
    parser = argparse.ArgumentParser(description="今日の気温を平年値・過去の記録と比較する")
    parser.add_argument("--lat", type=float, default=35.86, help="緯度(省略時: さいたま市付近 35.86)")
    parser.add_argument("--lon", type=float, default=139.65, help="経度(省略時: さいたま市付近 139.65)")
    parser.add_argument("--date", type=str, default=None, help="対象日 YYYY-MM-DD(省略時: 今日)")
    parser.add_argument("--no-cache", action="store_true", help="キャッシュを無視して再取得する")
    parser.add_argument("--raw", action="store_true", help="平年値を平滑化せず、対象日1日分の生の平均をそのまま使う")
    parser.add_argument("--full", action="store_true", help="ランキングを省略せず全件表示する")
    args = parser.parse_args()

    if args.date is None:
        date = datetime.date.today()
    else:
        try:
            date = datetime.date.fromisoformat(args.date)
        except ValueError:
            parser.error(f"--date は YYYY-MM-DD 形式で指定してください(入力値: {args.date!r})")

    return args.lat, args.lon, date.isoformat(), args.no_cache, args.raw, args.full


LATITUDE, LONGITUDE, TODAY_DATE, FORCE_REFRESH, RAW_MODE, FULL_MODE = parse_args()
TARGET_MONTH_DAY = TODAY_DATE[5:]

# --- キャッシュ ---
# 目的は速度ではなく、Open-Meteo側のレート制限(429)を避けること。
# ファイル名に地点・期間を含めておけば、期間が変わったときだけ
# 自動的にキャッシュミスして再取得される(=有効期限の管理が不要)。
CACHE_DIR = "cache"


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
raw_normal_a = sum(r[1] for r in normal_records_a) / len(normal_records_a)

# 平年値B: 直近30年のローリング。対象日の最新データ年を基準に年範囲を決め、
# 365日全体でこの同じ年範囲を使う(日ごとに基準年をずらすと、9日移動平均で
# 異なる基準期間の日を混ぜて平均することになるため)
years_with_target_day = sorted(int(r[0][:4]) for r in same_day_records)
year_end_b = years_with_target_day[-1]
year_start_b = year_end_b - 29
normal_records_b = [r for r in same_day_records if year_start_b <= int(r[0][:4]) <= year_end_b]
raw_normal_b = sum(r[1] for r in normal_records_b) / len(normal_records_b)

if RAW_MODE:
    normal_a = raw_normal_a
    normal_b = raw_normal_b
    print(f"{TARGET_MONTH_DAY} の平年値A(1991-2020年固定、{len(normal_records_a)}年分、生データ): {normal_a:.1f}℃")
    print(f"{TARGET_MONTH_DAY} の平年値B(直近{len(normal_records_b)}年ローリング、生データ): {normal_b:.1f}℃")
else:
    smoothed_a = kz_filter(build_daily_normal_series(archive_daily, 1991, 2020))
    smoothed_b = kz_filter(build_daily_normal_series(archive_daily, year_start_b, year_end_b))
    normal_a = lookup_normal(smoothed_a, TARGET_MONTH_DAY)
    normal_b = lookup_normal(smoothed_b, TARGET_MONTH_DAY)

    print(f"{TARGET_MONTH_DAY} の平年値A(1991-2020年固定): "
          f"生データ {raw_normal_a:.1f}℃ → 平滑化後(9日移動平均×3回) {normal_a:.1f}℃")
    print(f"{TARGET_MONTH_DAY} の平年値B(直近{len(normal_records_b)}年ローリング): "
          f"生データ {raw_normal_b:.1f}℃ → 平滑化後(9日移動平均×3回) {normal_b:.1f}℃")

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
TOP_N = 5  # デフォルト表示で必ず見せる上位件数
AROUND = 2  # 今日の順位の前後、実測レコードで何件ずつ見せるか


def print_ranking(records, period_label):
    ranked = sorted(records, key=lambda r: r[value_index], reverse=order_desc)
    years = sorted(int(r[0][:4]) for r in records)
    year_min, year_max = years[0], years[-1]
    n = len(ranked)

    # 今日を実測レコードに混ぜて順位付けすると、既存の順位番号とズレて
    # 衝突する(例: 今日が23位に入ると元の23位が24位にずれる)ため、
    # 実測レコードの順位番号は変えず、今日は番号なしの矢印で挿入する
    if order_desc:
        better_count = sum(1 for r in records if r[value_index] > today_value)
    else:
        better_count = sum(1 for r in records if r[value_index] < today_value)
    position = better_count + 1  # 今日を挿入するとしたら何位に当たるか

    def print_record_row(rank, record):
        value = record[2] if order_desc else record[3]
        print(f"  {rank:2d}位: {record[0]}  {value:.1f} ℃")

    def print_today_row():
        print(f"      →  {TODAY_DATE}(今日)  {today_value:.1f} ℃")

    def print_rows(start, end):
        """1-indexedでstart〜end位までを表示し、今日の順位に当たる位置に矢印を挟む"""
        for rank in range(start, end + 1):
            if rank == position:
                print_today_row()
            print_record_row(rank, ranked[rank - 1])
        if position == end + 1:
            print_today_row()

    print(f"\n{TARGET_MONTH_DAY} の{label}ランキング({period_label}、{year_min}〜{year_max}年、全{n}件):")

    if FULL_MODE:
        print_rows(1, n)
    else:
        window_start = max(1, position - AROUND)
        window_end = min(n, position + AROUND)
        top_end = min(TOP_N, n)

        if window_start <= top_end + 1:
            # 上位と今日周辺の範囲が重なる/隣接するので、省略なしでつなげて表示する
            print_rows(1, max(top_end, window_end))
        else:
            print_rows(1, top_end)
            print(f"  ...({top_end + 1}〜{window_start - 1}位省略)...")
            print_rows(window_start, window_end)

    print(f"今日({TODAY_DATE})の値は Forecast API 由来(ERA5基準にバイアス補正済み)の推定値です: {today_value:.1f}℃")
    print(f"{period_label}の過去{len(records)}年({year_min}〜{year_max}年)の{label}分布に当てはめると、"
          f"{position}番目に位置します(過去の実測{len(records)}件中で数えた場合)")


records_1940 = same_day_records
records_1979 = [r for r in same_day_records if int(r[0][:4]) >= 1979]

print_ranking(records_1940, "ERA5 1940年以降・全期間")
print_ranking(records_1979, "ERA5 1979年以降・衛星観測時代")
