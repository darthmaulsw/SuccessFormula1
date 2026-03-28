"""
Fetch and cache historical Japan GP race data from FastF1.
Saves processed feature CSVs to data/historical/ for offline training.

Usage:
    python scripts/fetch_historical_data.py
    python scripts/fetch_historical_data.py --years 2018 2019 2022 2023 2024
    python scripts/fetch_historical_data.py --force   # re-download even if cached

Japan GP at Suzuka was cancelled in 2020 (COVID) and run at Fuji in 2007-2008.
This script targets 2015-2024 (all Suzuka, skipping 2020).
"""

import argparse
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
from pathlib import Path

# Japan GP years at Suzuka (skip 2020 — cancelled)
DEFAULT_YEARS = [2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024]

CACHE_DIR = Path("fastf1_cache")
OUTPUT_DIR = Path("data/historical")

from modal_ml.features import FEATURE_COLUMNS, COMPOUND_MAP


def engineer_features(session, year: int) -> pd.DataFrame:
    laps = session.laps.copy()
    if laps.empty:
        print(f"  [!] No lap data for {year}")
        return pd.DataFrame()

    laps = laps[laps["LapNumber"] > 1].copy()

    laps["tire_compound"] = (
        laps["Compound"].fillna("MEDIUM").str.upper().map(COMPOUND_MAP).fillna(1).astype(int)
    )
    laps["tire_age"] = laps["TyreLife"].fillna(1).astype(int)
    laps["pit_stops"] = laps.groupby("DriverNumber")["PitOutTime"].transform(
        lambda x: x.notna().cumsum()
    )

    total_laps = laps["LapNumber"].max()
    laps["laps_remaining"] = total_laps - laps["LapNumber"]
    laps["position"] = laps["Position"].ffill().fillna(20).astype(int)

    laps["gap_to_leader"] = (
        laps["GapToLeader"]
        .apply(lambda x: x.total_seconds() if pd.notna(x) and hasattr(x, "total_seconds") else 0.0)
        .fillna(0.0)
    )

    # Safety car from track status
    laps["safety_car"] = 0
    laps["vsc"] = 0
    try:
        if hasattr(session, "track_status") and session.track_status is not None:
            ts = session.track_status
            for lap_idx, lap in laps.iterrows():
                sc = ts[(ts["Status"] == "4") & (ts["Time"] >= lap["LapStartTime"]) & (ts["Time"] <= lap["Time"])]
                vsc = ts[(ts["Status"] == "6") & (ts["Time"] >= lap["LapStartTime"]) & (ts["Time"] <= lap["Time"])]
                if not sc.empty:
                    laps.loc[lap_idx, "safety_car"] = 1
                if not vsc.empty:
                    laps.loc[lap_idx, "vsc"] = 1
    except Exception:
        pass  # track_status not always available in older sessions

    # Radio features not available historically — default to neutral
    laps["radio_sentiment"] = 0.0
    laps["radio_pit_keyword"] = 0

    # Rolling 3-lap metrics
    laps = laps.sort_values(["DriverNumber", "LapNumber"])
    laps["position_change_3lap"] = (
        laps.groupby("DriverNumber")["position"]
        .transform(lambda x: x.shift(3) - x)
        .fillna(0).astype(int)
    )
    laps["gap_delta_3lap"] = (
        laps.groupby("DriverNumber")["gap_to_leader"]
        .transform(lambda x: x - x.shift(3))
        .fillna(0.0)
    )

    # Label: did this driver finish P1?
    final_positions = laps.groupby("DriverNumber")["position"].last()
    laps["won"] = laps["DriverNumber"].map(lambda d: int(final_positions.get(d, 20) == 1))

    # Metadata columns useful for analysis
    laps["year"] = year
    laps["driver_number"] = laps["DriverNumber"]
    laps["lap_number"] = laps["LapNumber"]

    keep = FEATURE_COLUMNS + ["won", "year", "driver_number", "lap_number"]
    return laps[keep].dropna()


def fetch_year(year: int, force: bool = False) -> Path | None:
    import fastf1

    out_path = OUTPUT_DIR / f"japan_gp_{year}.csv"
    if out_path.exists() and not force:
        print(f"  [skip] {year} already cached at {out_path}")
        return out_path

    try:
        print(f"  Loading {year} Japan GP Race...")
        session = fastf1.get_session(year, "Japan", "R")
        session.load(telemetry=False, weather=False, messages=False)
        df = engineer_features(session, year)
        if df.empty:
            print(f"  [!] {year}: empty dataframe, skipping")
            return None
        df.to_csv(out_path, index=False)
        print(f"  [ok] {year}: {len(df)} lap rows → {out_path}")
        return out_path
    except Exception as e:
        print(f"  [err] {year}: {e}")
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", nargs="+", type=int, default=DEFAULT_YEARS,
                        help="Years to fetch (default: 2015-2024 excl. 2020)")
    parser.add_argument("--force", action="store_true",
                        help="Re-download even if CSV already exists")
    args = parser.parse_args()

    import fastf1
    CACHE_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(CACHE_DIR))

    print(f"Fetching Japan GP data for years: {args.years}")
    print(f"Output directory: {OUTPUT_DIR.resolve()}\n")

    success, skipped, failed = [], [], []
    for year in sorted(args.years):
        result = fetch_year(year, force=args.force)
        if result:
            success.append(year)
        else:
            failed.append(year)

    # Merge all CSVs into a single combined file for training
    all_csvs = sorted(OUTPUT_DIR.glob("japan_gp_*.csv"))
    if all_csvs:
        combined = pd.concat([pd.read_csv(f) for f in all_csvs], ignore_index=True)
        combined_path = OUTPUT_DIR / "japan_gp_combined.csv"
        combined.to_csv(combined_path, index=False)
        print(f"\nCombined dataset: {len(combined)} rows across {combined['year'].nunique()} years")
        print(f"Saved → {combined_path}")
        print(f"\nYear breakdown:")
        for yr, cnt in combined.groupby("year").size().items():
            winners = combined[(combined["year"] == yr) & (combined["won"] == 1)]["driver_number"].nunique()
            print(f"  {yr}: {cnt} lap rows  |  winner driver(s): {combined[(combined['year']==yr)&(combined['won']==1)]['driver_number'].unique()}")

    print(f"\nDone. Success: {success}  |  Failed: {failed}")


if __name__ == "__main__":
    main()
