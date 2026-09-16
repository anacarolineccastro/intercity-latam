import pandas as pd
import pytest

from src.data import load_all, normalize, normalize_target, save_dataset


def test_finance_normalizes_week_numbers_and_duplicates():
    frame = pd.DataFrame(
        {
            "month": ["2026-09-14", "2026-09-14"],
            "country_name": ["Brazil", "Brazil"],
            "routes": ["A <> B", "A <> B"],
            "is_reserve": ["not_reserve", "not_reserve"],
            "car_type": ["UberX Intercity", "UberX Intercity"],
            "airport_type": ["Non-Airport", "Non-Airport"],
            "requests": ["10", "12"],
            "trips": ["8", "9"],
            "gb_usd": ["100", "120"],
            "vc_usd": ["20", "24"],
        }
    )
    result, warnings = normalize("finance", frame)
    assert len(result) == 1
    assert result.iloc[0]["requests"] == 12
    assert result.iloc[0]["week_start"] == pd.Timestamp("2026-09-14")
    assert warnings


def test_missing_required_columns_are_rejected():
    with pytest.raises(ValueError, match="Missing required columns"):
        normalize("sessions", pd.DataFrame({"week": ["2026-09-14"]}))


def test_invalid_week_is_rejected():
    frame = pd.DataFrame(
        {
            "week": ["not-a-date"],
            "country_name": ["Mexico"],
            "routes": ["A <> B"],
            "sessions": [10],
            "requesting_sessions": [5],
            "shopping_sessions": [8],
        }
    )
    with pytest.raises(ValueError, match="Invalid week"):
        normalize("sessions", frame)


def test_save_append_and_load(tmp_path):
    first = pd.DataFrame(
        {
            "week": ["2026-09-14"],
            "country_name": ["Mexico"],
            "routes": ["A <> B"],
            "sessions": [10],
            "requesting_sessions": [5],
            "shopping_sessions": [8],
        }
    )
    second = first.assign(sessions=12)
    save_dataset(tmp_path, "sessions", normalize("sessions", first)[0], "first.csv", "replace")
    save_dataset(tmp_path, "sessions", normalize("sessions", second)[0], "second.csv", "append")
    frames, manifest = load_all(tmp_path)
    assert len(frames["sessions"]) == 1
    assert frames["sessions"].iloc[0]["sessions"] == 12
    assert manifest["sessions"]["filename"] == "second.csv"


def test_original_planning_export_normalizes_as_target():
    source = pd.DataFrame(
        {
            "3. Country Lookup": ["Brazil", "Mexico", "United States"],
            "Metric": ["Gross Bookings", "Trips", "Trips"],
            "2026-01": ["1,234.50", "100", "999"],
            "2026-02": ["(50.00)", "110", "999"],
            "2026-Q1": ["0", "0", "0"],
        }
    )
    target = normalize_target(source)
    assert len(target) == 4
    assert set(target["country_name"]) == {"Brazil", "Mexico"}
    assert target.loc[
        (target["country_name"] == "Brazil") & (target["period"] == pd.Timestamp("2026-01-01")),
        "target",
    ].iloc[0] == 1234.5
    assert target.loc[
        (target["country_name"] == "Brazil") & (target["period"] == pd.Timestamp("2026-02-01")),
        "target",
    ].iloc[0] == -50
