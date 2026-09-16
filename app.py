"""LATAM Intercity weekly performance dashboard."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.charts import funnel, metric_trend, netr_waterfall, route_bar, weekly_line
from src.data import (
    DATASETS,
    load_all,
    load_forecast,
    normalize,
    normalize_target,
    read_upload,
    save_dataset,
    save_target,
)
from src.metrics import (
    filter_frame,
    finance_summary,
    grouped_weekly,
    marketplace_metrics,
    netr_bridge,
    route_summary,
    safe_ratio,
    totals,
)

ROOT = Path(__file__).parent

st.set_page_config(page_title="LATAM Intercity", page_icon="🚘", layout="wide")
st.title("LATAM Intercity")
st.caption("Weekly performance for Brazil and Mexico")


def csv_download(frame: pd.DataFrame, label: str, filename: str) -> None:
    st.download_button(label, frame.to_csv(index=False), filename, "text/csv")


def latest_delta(weekly: pd.DataFrame, column: str) -> float | None:
    if column not in weekly or len(weekly) < 2:
        return None
    previous, current = weekly[column].iloc[-2:]
    return safe_ratio(current - previous, previous) if previous else None


def format_uploaded_at(value: str) -> str:
    stamp = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(stamp):
        return value
    return stamp.tz_convert("UTC").strftime("%Y-%m-%d %H:%M UTC")


def show_uploads() -> None:
    st.subheader("Weekly data refresh")
    st.caption("Choose a CSV or XLSX export. The app validates and saves it immediately, then shows whether it loaded.")
    frames, manifest = load_all(ROOT)

    status_rows = []
    for dataset in DATASETS:
        metadata = manifest.get(dataset, {})
        loaded = dataset in frames
        status_rows.append(
            {
                "Dataset": dataset.replace("_", " ").title(),
                "Status": "Loaded" if loaded else "Not loaded",
                "File": metadata.get("filename", "—"),
                "Rows": metadata.get("rows", 0) if loaded else 0,
                "Weeks": (
                    f"{metadata.get('week_min')} to {metadata.get('week_max')}"
                    if loaded and metadata.get("week_min")
                    else "—"
                ),
                "Last saved": format_uploaded_at(metadata["uploaded_at"]) if metadata.get("uploaded_at") else "—",
            }
        )
    target_metadata = manifest.get("target_plan", {})
    status_rows.append(
        {
            "Dataset": "Monthly Targets",
            "Status": "Uploaded" if target_metadata else "Bundled 2026 plan",
            "File": target_metadata.get("filename", "forecast_plan.csv"),
            "Rows": target_metadata.get("rows", len(load_forecast(ROOT))),
            "Weeks": (
                f"{target_metadata.get('week_min')} to {target_metadata.get('week_max')}"
                if target_metadata
                else "2026-01-01 to 2026-12-01"
            ),
            "Last saved": (
                format_uploaded_at(target_metadata["uploaded_at"])
                if target_metadata.get("uploaded_at")
                else "Bundled with app"
            ),
        }
    )
    st.dataframe(pd.DataFrame(status_rows), use_container_width=True, hide_index=True)

    for message in st.session_state.get("upload_messages", []):
        if message["level"] == "success":
            st.success(message["text"])
        else:
            st.error(message["text"])

    for dataset, config in DATASETS.items():
        loaded = dataset in frames
        with st.expander(dataset.replace("_", " ").title(), expanded=not loaded):
            template = ROOT / "data" / "templates" / f"{dataset}_template.csv"
            st.download_button(
                "Download template",
                template.read_bytes(),
                template.name,
                "text/csv",
                key=f"template-{dataset}",
            )
            st.caption("Required: " + ", ".join(config["required"]))
            if loaded:
                metadata = manifest[dataset]
                st.info(
                    f"Currently loaded: {metadata['rows']:,} rows from **{metadata['filename']}** "
                    f"({metadata['week_min']} to {metadata['week_max']})."
                )
            else:
                st.warning("No saved file yet for this dataset.")
            upload = st.file_uploader(
                f"Upload {dataset}", type=["csv", "xlsx", "xls"], key=f"upload-{dataset}"
            )
            mode = st.radio(
                "Save mode", ["append", "replace"], horizontal=True, key=f"mode-{dataset}"
            )
            if not upload:
                continue
            file_id = (upload.name, upload.size)
            already_saved = st.session_state.get(f"saved-id-{dataset}") == file_id
            try:
                with st.spinner(f"Reading {upload.name}..."):
                    normalized, warnings = normalize(dataset, read_upload(upload))
                st.success(
                    f"File accepted: **{upload.name}** — {len(normalized):,} rows, "
                    f"{normalized.week_start.min():%Y-%m-%d} to {normalized.week_start.max():%Y-%m-%d}."
                )
                for warning in warnings:
                    st.warning(warning)
                st.dataframe(normalized.head(20), use_container_width=True, hide_index=True)
                if already_saved:
                    st.info("This file is already saved.")
                    continue
                with st.spinner(f"Saving {dataset.replace('_', ' ')}..."):
                    metadata = save_dataset(ROOT, dataset, normalized, upload.name, mode)
                st.cache_data.clear()
                text = (
                    f"Saved {dataset.replace('_', ' ')}: {metadata['rows']:,} rows from {metadata['filename']} "
                    f"({metadata['week_min']} to {metadata['week_max']})."
                )
                st.session_state[f"saved-id-{dataset}"] = file_id
                st.session_state.setdefault("upload_messages", [])
                st.session_state["upload_messages"] = [
                    message for message in st.session_state["upload_messages"] if message["dataset"] != dataset
                ] + [{"dataset": dataset, "level": "success", "text": text}]
                st.toast(text, icon="✅")
                st.rerun()
            except Exception as error:
                text = f"{dataset.replace('_', ' ').title()} was not saved: {error}"
                st.session_state[f"saved-id-{dataset}"] = None
                st.session_state.setdefault("upload_messages", [])
                st.session_state["upload_messages"] = [
                    message for message in st.session_state["upload_messages"] if message["dataset"] != dataset
                ] + [{"dataset": dataset, "level": "error", "text": text}]
                st.error(text)
                st.toast(text, icon="❌")

    with st.expander("Monthly Targets", expanded=False):
        st.caption(
            "Upload the Planning export in its original wide format. It must contain a country column, "
            "a Metric column, and monthly columns such as 2026-01."
        )
        bundled = ROOT / "data" / "forecast_plan.csv"
        st.download_button(
            "Download current target template",
            bundled.read_bytes(),
            bundled.name,
            "text/csv",
            key="template-target",
        )
        if target_metadata:
            st.info(
                f"Current target: **{target_metadata['filename']}**, {target_metadata['rows']:,} values, "
                f"{target_metadata['week_min']} to {target_metadata['week_max']}."
            )
        else:
            st.info("Using the bundled 2026 plan until you upload a replacement.")
        target_upload = st.file_uploader(
            "Upload target data", type=["csv", "xlsx", "xls"], key="upload-target"
        )
        if target_upload:
            file_id = (target_upload.name, target_upload.size)
            try:
                target = normalize_target(read_upload(target_upload))
                st.success(
                    f"Target accepted: **{target_upload.name}** — {len(target):,} country/metric/month values."
                )
                st.dataframe(target.head(30), use_container_width=True, hide_index=True)
                if st.session_state.get("saved-id-target") != file_id:
                    metadata = save_target(ROOT, target, target_upload.name)
                    st.session_state["saved-id-target"] = file_id
                    text = (
                        f"Saved monthly targets from {metadata['filename']} "
                        f"({metadata['week_min']} to {metadata['week_max']})."
                    )
                    st.session_state.setdefault("upload_messages", [])
                    st.session_state["upload_messages"] = [
                        message
                        for message in st.session_state["upload_messages"]
                        if message["dataset"] != "target_plan"
                    ] + [{"dataset": "target_plan", "level": "success", "text": text}]
                    st.toast(text, icon="✅")
                    st.rerun()
                else:
                    st.info("This target file is already saved.")
            except Exception as error:
                st.error(f"Target data was not saved: {error}")


@st.cache_data(show_spinner=False)
def get_data() -> tuple[dict[str, pd.DataFrame], dict]:
    return load_all(ROOT)


with st.sidebar:
    st.header("Navigation")
    page = st.radio(
        "Page", ["Overview", "Routes", "Finance", "Reserve", "Supply & return", "Data refresh"]
    )
    sidebar_frames, _ = load_all(ROOT)
    loaded_names = [name.replace("_", " ").title() for name in DATASETS if name in sidebar_frames]
    missing_names = [name.replace("_", " ").title() for name in DATASETS if name not in sidebar_frames]
    if loaded_names:
        st.caption("Loaded: " + ", ".join(loaded_names))
    if missing_names:
        st.caption("Missing: " + ", ".join(missing_names))

if page == "Data refresh":
    show_uploads()
    st.stop()

frames, manifest = get_data()
if not frames:
    st.info("No weekly data is loaded yet. Open **Data refresh** to upload query exports.")
    st.stop()

all_weeks = pd.concat([frame[["week_start"]] for frame in frames.values()])["week_start"]
all_countries = sorted(
    set().union(*(set(frame["country_name"].dropna()) for frame in frames.values() if "country_name" in frame))
)
all_routes = sorted(set().union(*(set(frame["routes"].dropna()) for frame in frames.values() if "routes" in frame)))

with st.sidebar:
    st.header("Filters")
    date_range = st.date_input(
        "Week range",
        value=(all_weeks.min().date(), all_weeks.max().date()),
        min_value=all_weeks.min().date(),
        max_value=all_weeks.max().date(),
    )
    countries = st.multiselect("Country", all_countries, default=all_countries)
    routes = st.multiselect("Route", all_routes)
    dimension_filters = {}
    for dimension, label in (
        ("car_type", "Product / car type"),
        ("airport_type", "Airport type"),
        ("taxonomy", "Reserve taxonomy"),
    ):
        options = sorted(
            set().union(*(set(frame[dimension].dropna()) for frame in frames.values() if dimension in frame))
        )
        if options:
            dimension_filters[dimension] = st.multiselect(label, options)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = map(pd.Timestamp, date_range)
else:
    start = end = pd.Timestamp(date_range)
filters = {
    "start": start,
    "end": end,
    "country_name": countries,
    "routes": routes,
    **dimension_filters,
}
filtered = {name: filter_frame(frame, filters) for name, frame in frames.items()}

latest_upload = max((item["uploaded_at"] for item in manifest.values()), default="unknown")
st.caption(f"Data freshness: latest upload {latest_upload}")

finance = filtered.get("finance", pd.DataFrame())
sessions = filtered.get("sessions", pd.DataFrame())
reserve = filtered.get("reserve_rate", pd.DataFrame())
returns = filtered.get("return_rate", pd.DataFrame())

if page == "Overview":
    st.subheader("Executive overview")
    summary = finance_summary(finance) if not finance.empty else {}
    weekly = grouped_weekly(finance, ["requests", "trips", "gb_usd", "vc_usd"]) if not finance.empty else pd.DataFrame()
    columns = st.columns(6)
    cards = [
        ("Requests", summary.get("requests", 0), "{:,.0f}", latest_delta(weekly, "requests")),
        ("Trips", summary.get("trips", 0), "{:,.0f}", latest_delta(weekly, "trips")),
        ("Conversion", summary.get("conversion", 0), "{:.1%}", None),
        ("Gross bookings", summary.get("gb_usd", 0), "${:,.0f}", latest_delta(weekly, "gb_usd")),
        ("Variable contribution", summary.get("vc_usd", 0), "${:,.0f}", latest_delta(weekly, "vc_usd")),
        ("VC margin", summary.get("vc_margin", 0), "{:.1%}", None),
    ]
    for column, (label, value, fmt, delta) in zip(columns, cards):
        column.metric(label, fmt.format(value), f"{delta:+.1%} WoW" if delta is not None else None)

    st.subheader("Conversion and NETR funnels")
    funnel_values = {}
    if not sessions.empty:
        session_totals = totals(sessions, ["sessions", "shopping_sessions", "requesting_sessions"])
        funnel_values.update({
            "Sessions": session_totals["sessions"],
            "Shopping": session_totals["shopping_sessions"],
            "Requesting": session_totals["requesting_sessions"],
        })
    if summary:
        funnel_values.update({"Requests": summary["requests"], "Trips": summary["trips"]})
    left, right = st.columns(2)
    if funnel_values:
        left.plotly_chart(funnel(funnel_values), use_container_width=True)
    if not finance.empty:
        right.plotly_chart(netr_waterfall(netr_bridge(finance)), use_container_width=True)
        right.caption(
            "NETR = Gross Bookings − Driver Payments − Taxes & Fees − Existing User Incentives "
            "+ Other Revenue. The reconciliation line makes the bridge equal reported NETR."
        )

    st.subheader("Marketplace health")
    control_a, control_b, control_c = st.columns([1, 1, 2])
    frequency = control_a.radio("Time grain", ["Week", "Month"], horizontal=True)
    dimension = control_b.radio("Break down by", ["Country", "Route"], horizontal=True)
    metric_options = [
        "trips", "requests", "Rs/S", "C/Rs", "C/S", "C/R", "gb_usd",
        "Average Fare", "NETR_usd", "NETR Margin", "vc_usd", "VC Margin",
        "Reserve Reliability", "Return Rate",
    ]
    health = marketplace_metrics(filtered, frequency, dimension)
    available_metrics = [metric for metric in metric_options if metric in health]
    selected_metric = control_c.selectbox(
        "Metric",
        available_metrics,
        index=available_metrics.index("C/Rs") if "C/Rs" in available_metrics else 0,
    )
    breakdown = "country_name" if dimension == "Country" else "routes"
    if not health.empty and selected_metric:
        st.plotly_chart(
            metric_trend(
                health,
                selected_metric,
                breakdown,
                f"{selected_metric} by {dimension.lower()} and {frequency.lower()}",
            ),
            use_container_width=True,
        )
        percent_columns = [
            "Rs/S", "C/Rs", "C/S", "C/R", "NETR Margin", "VC Margin",
            "Reserve Reliability", "Return Rate",
        ]
        st.dataframe(
            health,
            use_container_width=True,
            hide_index=True,
            column_config={
                column: st.column_config.NumberColumn(format="percent")
                for column in percent_columns if column in health
            },
        )
        csv_download(
            health,
            f"Download {frequency.lower()}ly {dimension.lower()} metrics",
            f"latam_intercity_{frequency.lower()}_{dimension.lower()}_metrics.csv",
        )

    st.subheader("Monthly actual vs target")
    country_monthly = marketplace_metrics(filtered, "Month", "Country")
    target_mapping = {
        "Trips": "trips",
        "Gross Bookings": "gb_usd",
        "NETR": "NETR_usd",
        "VC": "vc_usd",
    }
    target_metric = st.selectbox("Target metric", list(target_mapping), key="target-metric")
    actual_column = target_mapping[target_metric]
    target_data = load_forecast(ROOT)
    target_data = target_data[
        (target_data["metric"] == target_metric)
        & (target_data["country_name"].isin(countries))
        & (target_data["period"].between(start.to_period("M").to_timestamp(), end.to_period("M").to_timestamp()))
    ]
    if not country_monthly.empty and actual_column in country_monthly:
        actual = country_monthly[["period", "country_name", actual_column]].rename(columns={actual_column: "Actual"})
        comparison = actual.merge(
            target_data[["period", "country_name", "target"]].rename(columns={"target": "Target"}),
            on=["period", "country_name"],
            how="outer",
        )
        comparison[["Actual", "Target"]] = comparison[["Actual", "Target"]].fillna(0)
        comparison["Attainment"] = comparison.apply(
            lambda row: safe_ratio(row["Actual"], row["Target"]), axis=1
        )
        comparison["Gap"] = comparison["Actual"] - comparison["Target"]
        comparison["Vs Target"] = comparison.apply(
            lambda row: safe_ratio(row["Gap"], row["Target"]), axis=1
        )
        comparison_long = comparison.melt(
            id_vars=["period", "country_name", "Attainment", "Gap", "Vs Target"],
            value_vars=["Actual", "Target"],
            var_name="Scenario",
            value_name=target_metric,
        )
        comparison_long["Line"] = (
            comparison_long["country_name"] + " · " + comparison_long["Scenario"]
        )
        monthly_total = comparison.groupby("period", as_index=False)[["Actual", "Target"]].sum()
        monthly_total["Gap"] = monthly_total["Actual"] - monthly_total["Target"]
        latest = monthly_total.sort_values("period").iloc[-1]
        latest_vs_target = safe_ratio(latest["Gap"], latest["Target"])
        cards = st.columns(4)
        prefix = "" if target_metric == "Trips" else "$"
        cards[0].metric("Latest month", latest["period"].strftime("%b %Y"))
        cards[1].metric("Actual", f"{prefix}{latest['Actual']:,.0f}")
        cards[2].metric("Target", f"{prefix}{latest['Target']:,.0f}")
        cards[3].metric(
            "Vs target",
            f"{latest_vs_target:+.1%}",
            f"{prefix}{latest['Gap']:+,.0f}",
        )
        st.plotly_chart(
            metric_trend(
                comparison_long,
                target_metric,
                "Line",
                f"{target_metric}: actual vs target",
            ),
            use_container_width=True,
        )
        st.dataframe(
            comparison,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Attainment": st.column_config.NumberColumn(format="percent"),
                "Vs Target": st.column_config.NumberColumn(format="percent"),
            },
        )
    else:
        st.info("Upload Finance data to compare actuals with the target.")
    if not finance.empty:
        csv_download(finance, "Download filtered overview data", "latam_intercity_overview.csv")

elif page == "Routes":
    st.subheader("Route performance")
    if finance.empty:
        st.info("Upload Finance data to view route performance.")
    else:
        route_data = route_summary(finance)
        st.plotly_chart(route_bar(route_data, "trips", "Top routes by trips"), use_container_width=True)
        breakdown_columns = st.columns(3)
        for column, dimension, title in zip(
            breakdown_columns,
            ("car_type", "airport_type", "is_reserve"),
            ("Product mix", "Airport mix", "Reserve mix"),
        ):
            if dimension in finance:
                mix = finance.groupby(dimension, as_index=False)["trips"].sum()
                column.bar_chart(mix, x=dimension, y="trips", use_container_width=True)
                column.caption(title)
        st.dataframe(
            route_data,
            use_container_width=True,
            hide_index=True,
            column_config={
                "conversion": st.column_config.NumberColumn(format="percent"),
                "vc_margin": st.column_config.NumberColumn(format="percent"),
            },
        )
        csv_download(route_data, "Download filtered route data", "latam_intercity_routes.csv")

elif page == "Finance":
    st.subheader("Finance")
    if finance.empty:
        st.info("Upload Finance data to view financial performance.")
    else:
        values = totals(
            finance,
            [
                "gb_usd",
                "NETR_usd",
                "vc_usd",
                "driver_payment_usd",
                "ri_usd",
                "promo_redeemed_ri",
            ],
        )
        columns = st.columns(6)
        for column, label, field in zip(
            columns,
            ("Gross bookings", "NETR", "Variable contribution", "Driver payments", "Rider incentives", "Promo redeemed"),
            ("gb_usd", "NETR_usd", "vc_usd", "driver_payment_usd", "ri_usd", "promo_redeemed_ri"),
        ):
            column.metric(label, f"${values[field]:,.0f}")
        weekly = grouped_weekly(
            finance,
            ["gb_usd", "NETR_usd", "vc_usd", "driver_payment_usd", "ri_usd", "promo_redeemed_ri"],
        )
        left, right = st.columns(2)
        left.plotly_chart(weekly_line(weekly, "gb_usd", "Gross bookings trend"), use_container_width=True)
        right.plotly_chart(weekly_line(weekly, "vc_usd", "Variable contribution trend"), use_container_width=True)
        st.dataframe(weekly, use_container_width=True, hide_index=True)
        csv_download(finance, "Download filtered finance data", "latam_intercity_finance.csv")

elif page == "Reserve":
    st.subheader("Reserve reliability")
    if reserve.empty:
        st.info("Upload Reserve Rate data to view reserve performance.")
    else:
        values = totals(
            reserve, ["requests", "relevant_requests", "completed_trips", "reliable_requests", "time_to_book_min"]
        )
        columns = st.columns(4)
        columns[0].metric("Reserve requests", f"{values['requests']:,.0f}")
        columns[1].metric("Completion", f"{safe_ratio(values['completed_trips'], values['relevant_requests']):.1%}")
        columns[2].metric("Reliability", f"{safe_ratio(values['reliable_requests'], values['relevant_requests']):.1%}")
        columns[3].metric("Avg. lead time", f"{safe_ratio(values['time_to_book_min'], values['requests']) / 60:.1f}h")
        weekly = grouped_weekly(reserve, ["requests", "completed_trips", "reliable_requests"])
        st.plotly_chart(weekly_line(weekly, "completed_trips", "Weekly reserve completed trips"), use_container_width=True)
        st.dataframe(reserve, use_container_width=True, hide_index=True)
        csv_download(reserve, "Download filtered reserve data", "latam_intercity_reserve.csv")

else:
    st.subheader("Supply & return")
    if returns.empty:
        st.info("Upload Return Rate data to view return performance.")
    else:
        values = totals(
            returns,
            ["onward_trips", "return_trips", "time_to_return_min", "return_not_attempted_30", "return_not_attempted_60"],
        )
        columns = st.columns(4)
        columns[0].metric("Onward trips", f"{values['onward_trips']:,.0f}")
        columns[1].metric("Return rate", f"{safe_ratio(values['return_trips'], values['onward_trips']):.1%}")
        columns[2].metric(
            "Avg. time to return", f"{safe_ratio(values['time_to_return_min'], values['return_trips']) / 60:.1f}h"
        )
        columns[3].metric("No attempt ≤60m", f"{values['return_not_attempted_60']:,.0f}")
        weekly = grouped_weekly(returns, ["onward_trips", "return_trips"])
        st.plotly_chart(weekly_line(weekly, "return_trips", "Weekly return trips"), use_container_width=True)
        st.dataframe(returns, use_container_width=True, hide_index=True)
        csv_download(returns, "Download filtered return data", "latam_intercity_returns.csv")
