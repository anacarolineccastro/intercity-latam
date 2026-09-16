import pandas as pd

from src.metrics import filter_frame, finance_summary, marketplace_metrics, netr_bridge, safe_ratio


def test_safe_ratio_handles_zero():
    assert safe_ratio(10, 0) == 0
    assert safe_ratio(8, 10) == 0.8


def test_finance_summary():
    frame = pd.DataFrame(
        {"requests": [100], "trips": [75], "gb_usd": [1000], "vc_usd": [250]}
    )
    result = finance_summary(frame)
    assert result["conversion"] == 0.75
    assert result["vc_margin"] == 0.25


def test_filters_week_country_and_route():
    frame = pd.DataFrame(
        {
            "week_start": pd.to_datetime(["2026-09-07", "2026-09-14"]),
            "country_name": ["Brazil", "Mexico"],
            "routes": ["A <> B", "C <> D"],
        }
    )
    result = filter_frame(
        frame,
        {
            "start": pd.Timestamp("2026-09-14"),
            "end": pd.Timestamp("2026-09-14"),
            "country_name": ["Mexico"],
            "routes": [],
        },
    )
    assert result["routes"].tolist() == ["C <> D"]


def test_marketplace_metrics_aggregate_before_joining():
    finance = pd.DataFrame(
        {
            "week_start": pd.to_datetime(["2026-09-07", "2026-09-07"]),
            "country_name": ["Brazil", "Brazil"],
            "routes": ["A <> B", "C <> D"],
            "requests": [80, 20],
            "trips": [60, 10],
            "gb_usd": [600, 100],
            "NETR_usd": [120, 20],
            "vc_usd": [90, 10],
        }
    )
    sessions = pd.DataFrame(
        {
            "week_start": pd.to_datetime(["2026-09-07", "2026-09-07"]),
            "country_name": ["Brazil", "Brazil"],
            "routes": ["A <> B", "C <> D"],
            "sessions": [120, 40],
            "shopping_sessions": [100, 20],
            "requesting_sessions": [75, 15],
        }
    )
    result = marketplace_metrics({"finance": finance, "sessions": sessions}, "Week", "Country")
    assert len(result) == 1
    assert result.iloc[0]["trips"] == 70
    assert result.iloc[0]["C/Rs"] == 70 / 90
    assert result.iloc[0]["Rs/S"] == 90 / 120


def test_netr_bridge_omits_reconciliation():
    finance = pd.DataFrame(
        {
            "gb_usd": [1000],
            "driver_payment_usd": [700],
            "taxes_and_fees_disbursed_usd": [50],
            "existing_rider_incentives_overall_local": [20],
            "NETR_usd": [200],
        }
    )
    bridge = netr_bridge(finance)
    assert "Other Revenue / Reconciliation" not in bridge
    assert list(bridge) == [
        "Gross Bookings",
        "Driver Payments",
        "Taxes & Fees",
        "Existing User Incentives",
        "NETR",
    ]
