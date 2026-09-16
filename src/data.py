"""Upload, normalize, and persist the weekly query exports."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pandas as pd

DATASETS = {
    "finance": {
        "week": "month",
        "required": ["month", "country_name", "routes", "requests", "trips", "gb_usd", "vc_usd"],
        "numeric": ["requests", "trips", "gb_usd", "vc_usd", "driver_payment_usd", "NETR_usd",
                    "ri_usd", "net_ufp_usd", "net_subscriber_discounts_usd",
                    "existing_driver_incentives_usd", "taxes_and_fees_disbursed_usd",
                    "total_trip_distance_km", "total_eta_min", "promo_redeemed_ri"],
        "keys": ["week_start", "country_name", "routes", "is_reserve", "car_type", "airport_type"],
    },
    "reserve_rate": {
        "week": "Timeperiod",
        "required": ["Timeperiod", "country_name", "routes", "requests", "completed_trips",
                     "relevant_requests", "reliable_requests"],
        "numeric": ["requests", "completed_trips", "relevant_requests", "reliable_requests", "time_to_book_min"],
        "keys": ["week_start", "country_name", "routes", "car_type", "airport_type", "taxonomy"],
    },
    "return_rate": {
        "week": "month",
        "required": ["month", "country_name", "routes", "onward_trips", "return_trips"],
        "numeric": ["onward_trips", "return_trips", "time_to_return_min",
                    "return_not_attempted_30", "return_not_attempted_60"],
        "keys": ["week_start", "country_name", "routes"],
    },
    "sessions": {
        "week": "week",
        "required": ["week", "country_name", "routes", "sessions", "requesting_sessions", "shopping_sessions"],
        "numeric": ["sessions", "requesting_sessions", "shopping_sessions"],
        "keys": ["week_start", "country_name", "routes"],
    },
}


def read_upload(upload) -> pd.DataFrame:
    """Read a Streamlit UploadedFile as CSV or Excel."""
    content = BytesIO(upload.getvalue())
    if upload.name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(content)
    return pd.read_csv(content)


def normalize(dataset: str, frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    config = DATASETS[dataset]
    frame = frame.copy()
    frame.columns = [str(column).strip() for column in frame.columns]
    missing = [column for column in config["required"] if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    source_week = config["week"]
    frame["week_start"] = pd.to_datetime(frame[source_week], errors="coerce").dt.normalize()
    if frame["week_start"].isna().any():
        raise ValueError(f"Invalid week values in '{source_week}'.")
    for column in config["numeric"]:
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)
    for column in frame.select_dtypes(include="object"):
        frame[column] = frame[column].fillna("").astype(str).str.strip()

    keys = [key for key in config["keys"] if key in frame]
    before = len(frame)
    frame = frame.drop_duplicates(subset=keys, keep="last")
    warnings = [f"Removed {before - len(frame):,} duplicate rows."] if before != len(frame) else []
    return frame, warnings


def storage_dir(root: Path) -> Path:
    path = root / "data" / "stored"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_dataset(root: Path, dataset: str, frame: pd.DataFrame, filename: str, mode: str) -> dict:
    directory = storage_dir(root)
    destination = directory / f"{dataset}.parquet"
    if mode == "append" and destination.exists():
        existing = pd.read_parquet(destination)
        frame = pd.concat([existing, frame], ignore_index=True)
        frame, _ = normalize(dataset, frame)
    try:
        frame.to_parquet(destination, index=False)
        manifest_path = directory / "manifest.json"
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        manifest[dataset] = {
            "filename": filename,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "rows": len(frame),
            "week_min": str(frame["week_start"].min().date()),
            "week_max": str(frame["week_start"].max().date()),
        }
        manifest_path.write_text(json.dumps(manifest, indent=2))
    except OSError as error:
        raise OSError(
            f"Could not write {dataset} to disk ({error}). "
            "On Streamlit Cloud the filesystem can be read-only or reset after reboot."
        ) from error
    return manifest[dataset]


def load_all(root: Path) -> tuple[dict[str, pd.DataFrame], dict]:
    directory = storage_dir(root)
    frames = {
        name: pd.read_parquet(directory / f"{name}.parquet")
        for name in DATASETS if (directory / f"{name}.parquet").exists()
    }
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    return frames, manifest
