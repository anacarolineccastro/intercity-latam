"""Small, consistent Plotly chart constructors."""
from __future__ import annotations

import plotly.express as px
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
