import pandas as pd
import pytest

from src.metrics import (
    allocate_targets,
    experiment_metrics,
    filter_frame,
    finance_summary,
    marketplace_metrics,
    netr_bridge,
    promo_metrics,
    safe_ratio,
)


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


def test_weekly_target_is_monthly_divided_by_four():
    monthly = pd.DataFrame(
        {
            "country_name": ["Brazil"],
            "metric": ["Trips"],
            "period": [pd.Timestamp("2026-09-01")],
            "target": [400.0],
        }
    )
    weekly = allocate_targets(monthly, "Week")
    assert weekly.iloc[0]["target"] == 100.0
    assert "month" in weekly
    unchanged = allocate_targets(monthly, "Month")
    assert unchanged.iloc[0]["target"] == 400.0


def test_igbs_is_incremental_gb_over_incremental_spend():
    experiment = pd.DataFrame(
        {
            "week_start": pd.to_datetime(["2026-09-14", "2026-09-14"]),
            "country_name": ["Brazil", "Brazil"],
            "routes": ["A <> B", "A <> B"],
            "cohort": ["Treatment", "Control"],
            "requests": [1000, 100],
            "trips": [1000, 100],
            "gb_usd": [9000, 1000],
            "NETR_usd": [2000, 200],
            "vc_usd": [1500, 150],
        }
    )
    result = experiment_metrics(experiment, "Week", "Route").iloc[0]
    # Treatment averages $9.00 per trip against a $10.00 control fare.
    assert result["control_trips_scaled"] == 900
    assert result["incremental_trips"] == 100
    assert result["incremental_gb"] == 900
    assert result["gb_gap_per_trip"] == 1.0
    assert result["incremental_spend"] == 900
    assert result["IGBS"] == 1.0


def test_igbs_is_not_reported_when_fare_gap_is_too_small():
    experiment = pd.DataFrame(
        {
            "week_start": pd.to_datetime(["2026-09-14", "2026-09-14"]),
            "country_name": ["Brazil", "Brazil"],
            "routes": ["A <> B", "A <> B"],
            "cohort": ["Treatment", "Control"],
            "requests": [1000, 100],
            "trips": [1000, 100],
            "gb_usd": [9980, 1000],
            "NETR_usd": [2000, 200],
            "vc_usd": [1500, 150],
        }
    )
    result = experiment_metrics(experiment, "Week", "Route").iloc[0]
    assert result["gb_gap_per_trip"] == pytest.approx(0.02)
    assert not result["is_valid_fare_cut"]
    assert pd.isna(result["IGBS"])


def test_promo_metrics_roll_up_to_month():
    promos = pd.DataFrame(
        {
            "week_start": pd.to_datetime(["2026-09-07", "2026-09-14"]),
            "promotion_code": ["PROMO", "PROMO"],
            "redeemed_usd": [100, 150],
            "trips_redeemed": [10, 15],
        }
    )
    result = promo_metrics(promos, "Month")
    assert len(result) == 1
    assert result.iloc[0]["redeemed_usd"] == 250
