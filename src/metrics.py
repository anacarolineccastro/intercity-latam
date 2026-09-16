"""Metric aggregation helpers; all input frames are weekly query exports."""
from __future__ import annotations

import pandas as pd


def safe_ratio(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def filter_frame(frame: pd.DataFrame, filters: dict) -> pd.DataFrame:
    filtered = frame.copy()
    if "week_start" in filtered:
        filtered = filtered[filtered["week_start"].between(filters["start"], filters["end"])]
    for key in ("country_name", "routes", "car_type", "airport_type", "taxonomy"):
        if key in filtered and filters.get(key):
            filtered = filtered[filtered[key].isin(filters[key])]
    return filtered


def totals(frame: pd.DataFrame, columns: list[str]) -> dict[str, float]:
    return {column: float(frame[column].sum()) if column in frame else 0.0 for column in columns}


def finance_summary(frame: pd.DataFrame) -> dict[str, float]:
    values = totals(frame, ["requests", "trips", "gb_usd", "vc_usd"])
    values["conversion"] = safe_ratio(values["trips"], values["requests"])
    values["vc_margin"] = safe_ratio(values["vc_usd"], values["gb_usd"])
    return values


def grouped_weekly(frame: pd.DataFrame, values: list[str]) -> pd.DataFrame:
    usable = [value for value in values if value in frame]
    return frame.groupby("week_start", as_index=False)[usable].sum().sort_values("week_start")


def route_summary(finance: pd.DataFrame) -> pd.DataFrame:
    values = [v for v in ["requests", "trips", "gb_usd", "vc_usd", "total_trip_distance_km"] if v in finance]
    result = finance.groupby(["country_name", "routes"], as_index=False)[values].sum()
    result["conversion"] = result.apply(lambda row: safe_ratio(row.get("trips", 0), row.get("requests", 0)), axis=1)
    result["vc_margin"] = result.apply(lambda row: safe_ratio(row.get("vc_usd", 0), row.get("gb_usd", 0)), axis=1)
    return result.sort_values("trips", ascending=False)
