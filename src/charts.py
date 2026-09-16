"""Small, consistent Plotly chart constructors."""
from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

PALETTE = ["#276EF1", "#00A88F", "#9A66FF", "#FF8A00", "#E83E8C"]


def weekly_line(frame: pd.DataFrame, y: str, title: str, color: str | None = None):
    return px.line(
        frame, x="week_start", y=y, color=color, markers=True, title=title,
        color_discrete_sequence=PALETTE,
    ).update_layout(margin=dict(l=8, r=8, t=42, b=8), legend_title_text="")


def route_bar(frame: pd.DataFrame, value: str, title: str):
    display = frame.nlargest(12, value).sort_values(value)
    return px.bar(
        display, x=value, y="routes", color="country_name", orientation="h",
        title=title, color_discrete_sequence=PALETTE,
    ).update_layout(margin=dict(l=8, r=8, t=42, b=8), legend_title_text="")


def funnel(values: dict[str, float]):
    frame = pd.DataFrame({"stage": list(values), "count": list(values.values())})
    return px.funnel(frame, y="stage", x="count", title="Intercity funnel").update_layout(
        margin=dict(l=8, r=8, t=42, b=8)
    )


def metric_trend(frame: pd.DataFrame, metric: str, color: str, title: str):
    return px.line(
        frame,
        x="period",
        y=metric,
        color=color,
        markers=True,
        title=title,
        color_discrete_sequence=PALETTE,
    ).update_layout(margin=dict(l=8, r=8, t=42, b=8), legend_title_text="")


def netr_waterfall(values: dict[str, float]):
    labels = list(values)
    amounts = list(values.values())
    measures = ["absolute", "relative", "relative", "relative", "relative", "total"]
    figure = go.Figure(
        go.Waterfall(
            orientation="v",
            measure=measures,
            x=labels,
            y=amounts,
            connector={"line": {"color": "#7A7A7A"}},
            text=[f"${value:,.0f}" for value in amounts],
            textposition="outside",
        )
    )
    return figure.update_layout(
        title="NETR funnel: Gross Bookings to Net Effective Take Rate",
        showlegend=False,
        margin=dict(l=8, r=8, t=48, b=8),
        yaxis_title="USD",
    )
