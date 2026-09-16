import pandas as pd
import pytest

from src.data import load_all, normalize, save_dataset


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
