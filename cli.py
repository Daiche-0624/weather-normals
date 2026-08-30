import argparse
import datetime
import sys

import core

TOP_N = 5  # デフォルト表示で必ず見せる上位件数
AROUND = 2  # 今日の順位の前後、実測レコードで何件ずつ見せるか


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

    return args.lat, args.lon, date, args.no_cache, args.raw, args.full


def print_climate_by_decade(report, latitude, longitude):
    decades = report["climate_by_decade"]
    base = min(d["avg"] for d in decades)
    target_month = int(report["target_date"][5:7])

    print(f"--- この地点の気候(10年ごとの{target_month}月平均気温、{latitude}, {longitude}) ---")
    for d in decades:
        avg = d["avg"]
        count = d["count"]
        bar = "■" * (int((avg - base) * 10) + 1)
        note = f"  ※{count}年分" if count != 10 else ""  # 10年に満たない区切りは母数を明記する
        print(f"  {d['decade']}年代: {avg:5.2f}℃ {bar}{note}")
    print()


def print_normals(report, target_month_day):
    a = report["normals"]["a"]
    b = report["normals"]["b"]

    if report["raw_mode"]:
        print(f"{target_month_day} の平年値A(1991-2020年固定、{a['count']}年分、生データ): {a['smoothed']:.1f}℃")
        print(f"{target_month_day} の平年値B(直近{b['count']}年ローリング、生データ): {b['smoothed']:.1f}℃")
    else:
        print(f"{target_month_day} の平年値A(1991-2020年固定): "
              f"生データ {a['raw']:.1f}℃ → 平滑化後(9日移動平均×3回) {a['smoothed']:.1f}℃")
        print(f"{target_month_day} の平年値B(直近{b['count']}年ローリング): "
              f"生データ {b['raw']:.1f}℃ → 平滑化後(9日移動平均×3回) {b['smoothed']:.1f}℃")

    print(f"AとBの差(B-A、温暖化の目安): {report['normals']['diff_b_minus_a']:+.1f}℃")


def print_bias_and_today(report, today_date):
    bias = report["bias"]
    today = report["today"]

    print(f"\n直近{bias['overlap_days']}日間のバイアス(Forecast - ERA5の平均): "
          f"平均 {bias['mean']:+.1f}℃ / 最高 {bias['max']:+.1f}℃ / 最低 {bias['min']:+.1f}℃")

    raw_today = today["raw"]
    corrected = today["corrected"]
    print(f"今日({today_date})の値(生データ): "
          f"平均 {raw_today['mean']}℃ / 最高 {raw_today['max']}℃ / 最低 {raw_today['min']}℃")
    print(f"今日({today_date})の値(ERA5基準に補正後): "
          f"平均 {corrected['mean']:.1f}℃ / 最高 {corrected['max']:.1f}℃ / 最低 {corrected['min']:.1f}℃")

    print(f"平年との差: {today['deviation']:+.1f}℃")
    if today["label"] == "暑さ":
        print("→ 平年より暑いので、最高気温でランキングします")
    else:
        print("→ 平年より寒いので、最低気温でランキングします")


def print_ranking(ranking, today_date, full_mode):
    records = ranking["records"]
    position = ranking["today_position"]
    today_value = ranking["today_value"]
    label = ranking["label"]
    n = ranking["total"]

    def print_record_row(record):
        print(f"  {record['rank']:2d}位: {record['date']}  {record['value']:.1f} ℃")

    def print_today_row():
        print(f"      →  {today_date}(今日)  {today_value:.1f} ℃")

    def print_rows(start, end):
        """1-indexedでstart〜end位までを表示し、今日の順位に当たる位置に矢印を挟む"""
        for rank in range(start, end + 1):
            if rank == position:
                print_today_row()
            print_record_row(records[rank - 1])
        if position == end + 1:
            print_today_row()

    print(f"\n{today_date[5:]} の{label}ランキング({ranking['period_label']}、"
          f"{ranking['year_min']}〜{ranking['year_max']}年、全{n}件):")

    if full_mode:
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

    print(f"今日({today_date})の値は Forecast API 由来(ERA5基準にバイアス補正済み)の推定値です: {today_value:.1f}℃")
    print(f"{ranking['period_label']}の過去{n}年({ranking['year_min']}〜{ranking['year_max']}年)の{label}分布に当てはめると、"
          f"{position}番目に位置します(過去の実測{n}件中で数えた場合)")


def main():
    latitude, longitude, target_date, no_cache, raw, full = parse_args()

    try:
        report = core.build_report(latitude, longitude, target_date, raw=raw, force_refresh=no_cache)
    except core.RateLimitError:
        print("エラー: Open-Meteo APIのレート制限(429 Too Many Requests)に達しました。")
        print("しばらく時間をおいてから再実行してください。")
        sys.exit(1)

    today_date = report["target_date"]
    target_month_day = today_date[5:]

    print_climate_by_decade(report, latitude, longitude)
    print_normals(report, target_month_day)
    print_bias_and_today(report, today_date)

    for ranking in report["rankings"]:
        print_ranking(ranking, today_date, full)


if __name__ == "__main__":
    main()
