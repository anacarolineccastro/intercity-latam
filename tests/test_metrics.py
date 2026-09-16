import pandas as pd

from src.metrics import filter_frame, finance_summary, safe_ratio


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
