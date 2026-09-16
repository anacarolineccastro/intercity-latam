"""LATAM Intercity weekly performance dashboard."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.charts import funnel, route_bar, weekly_line
from src.data import DATASETS, load_all, normalize, read_upload, save_dataset
from src.metrics import filter_frame, finance_summary, grouped_weekly, route_summary, safe_ratio, totals

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


def show_uploads() -> None:
    st.subheader("Weekly data refresh")
    st.caption("Upload the four query exports as CSV or XLSX. Validate first, then append or replace stored data.")
    for dataset, config in DATASETS.items():
        with st.expander(dataset.replace("_", " ").title()):
            template = ROOT / "data" / "templates" / f"{dataset}_template.csv"
            st.download_button(
                "Download template",
                template.read_bytes(),
                template.name,
                "text/csv",
                key=f"template-{dataset}",
            )
            st.caption("Required: " + ", ".join(config["required"]))
            upload = st.file_uploader(
                f"Upload {dataset}", type=["csv", "xlsx", "xls"], key=f"upload-{dataset}"
            )
            mode = st.radio(
                "Save mode", ["append", "replace"], horizontal=True, key=f"mode-{dataset}"
            )
            if upload:
                try:
                    normalized, warnings = normalize(dataset, read_upload(upload))
                    st.success(
                        f"Valid: {len(normalized):,} rows, "
                        f"{normalized.week_start.min():%Y-%m-%d} to {normalized.week_start.max():%Y-%m-%d}"
                    )
                    for warning in warnings:
                        st.warning(warning)
                    st.dataframe(normalized.head(20), use_container_width=True, hide_index=True)
                    if st.button(f"Save {dataset}", key=f"save-{dataset}"):
                        metadata = save_dataset(ROOT, dataset, normalized, upload.name, mode)
                        st.cache_data.clear()
                        st.success(f"Saved {metadata['rows']:,} rows.")
                        st.rerun()
                except Exception as error:
                    st.error(str(error))


@st.cache_data(show_spinner=False)
def get_data() -> tuple[dict[str, pd.DataFrame], dict]:
    return load_all(ROOT)


with st.sidebar:
    st.header("Navigation")
    page = st.radio(
        "Page", ["Overview", "Routes", "Finance", "Reserve", "Supply & return", "Data refresh"]
    )

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

    left, right = st.columns(2)
    if not finance.empty:
        left.plotly_chart(weekly_line(weekly, "trips", "Weekly completed trips"), use_container_width=True)
        right.plotly_chart(weekly_line(weekly, "gb_usd", "Weekly gross bookings"), use_container_width=True)

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
    if funnel_values:
        st.plotly_chart(funnel(funnel_values), use_container_width=True)
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
