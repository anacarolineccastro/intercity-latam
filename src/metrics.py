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


def _aggregate(frame: pd.DataFrame, dimensions: list[str], values: list[str], frequency: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=[*dimensions, "period", *values])
    data = frame.copy()
    data["period"] = pd.to_datetime(data["week_start"])
    if frequency == "Month":
        data["period"] = data["period"].dt.to_period("M").dt.to_timestamp()
    usable = [value for value in values if value in data]
    return data.groupby([*dimensions, "period"], as_index=False, dropna=False)[usable].sum()


def marketplace_metrics(frames: dict[str, pd.DataFrame], frequency: str, dimension: str) -> pd.DataFrame:
    """Combine separately aggregated datasets without creating many-to-many joins."""
    dimensions = ["country_name"] if dimension == "Country" else ["country_name", "routes"]
    specs = {
        "finance": [
            "requests", "trips", "gb_usd", "NETR_usd", "vc_usd", "driver_payment_usd",
            "taxes_and_fees_disbursed_usd", "existing_rider_incentives_overall_local",
        ],
        "sessions": ["sessions", "shopping_sessions", "requesting_sessions"],
        "reserve_rate": ["relevant_requests", "completed_trips", "reliable_requests"],
        "return_rate": ["onward_trips", "return_trips"],
    }
    merged = None
    join_keys = [*dimensions, "period"]
    for name, values in specs.items():
        source = frames.get(name, pd.DataFrame())
        if source.empty or any(key not in source for key in dimensions):
            continue
        aggregate = _aggregate(source, dimensions, values, frequency)
        merged = aggregate if merged is None else merged.merge(aggregate, on=join_keys, how="outer")
    if merged is None:
        return pd.DataFrame(columns=join_keys)
    numeric = [column for column in merged.columns if column not in join_keys]
    merged[numeric] = merged[numeric].fillna(0)
    merged["Rs/S"] = merged.apply(
        lambda row: safe_ratio(row.get("requesting_sessions", 0), row.get("shopping_sessions", 0)), axis=1
    )
    merged["C/Rs"] = merged.apply(
        lambda row: safe_ratio(row.get("trips", 0), row.get("requesting_sessions", 0)), axis=1
    )
    merged["C/S"] = merged.apply(
        lambda row: safe_ratio(row.get("trips", 0), row.get("shopping_sessions", 0)), axis=1
    )
    merged["C/R"] = merged.apply(
        lambda row: safe_ratio(row.get("trips", 0), row.get("requests", 0)), axis=1
    )
    merged["Average Fare"] = merged.apply(
        lambda row: safe_ratio(row.get("gb_usd", 0), row.get("trips", 0)), axis=1
    )
    merged["NETR Margin"] = merged.apply(
        lambda row: safe_ratio(row.get("NETR_usd", 0), row.get("gb_usd", 0)), axis=1
    )
    merged["VC Margin"] = merged.apply(
        lambda row: safe_ratio(row.get("vc_usd", 0), row.get("gb_usd", 0)), axis=1
    )
    merged["Reserve Reliability"] = merged.apply(
        lambda row: safe_ratio(row.get("reliable_requests", 0), row.get("relevant_requests", 0)), axis=1
    )
    merged["Return Rate"] = merged.apply(
        lambda row: safe_ratio(row.get("return_trips", 0), row.get("onward_trips", 0)), axis=1
    )
    return merged.sort_values(join_keys)


def netr_bridge(frame: pd.DataFrame) -> dict[str, float]:
    values = totals(
        frame,
        [
            "gb_usd", "driver_payment_usd", "taxes_and_fees_disbursed_usd",
            "existing_rider_incentives_overall_local", "NETR_usd",
        ],
    )
    return {
        "Gross Bookings": values["gb_usd"],
        "Driver Payments": -values["driver_payment_usd"],
        "Taxes & Fees": -values["taxes_and_fees_disbursed_usd"],
        "Existing User Incentives": -values["existing_rider_incentives_overall_local"],
        "NETR": values["NETR_usd"],
    }


def route_summary(finance: pd.DataFrame) -> pd.DataFrame:
    values = [v for v in ["requests", "trips", "gb_usd", "vc_usd", "total_trip_distance_km"] if v in finance]
    result = finance.groupby(["country_name", "routes"], as_index=False)[values].sum()
    result["conversion"] = result.apply(lambda row: safe_ratio(row.get("trips", 0), row.get("requests", 0)), axis=1)
    result["vc_margin"] = result.apply(lambda row: safe_ratio(row.get("vc_usd", 0), row.get("gb_usd", 0)), axis=1)
    return result.sort_values("trips", ascending=False)
