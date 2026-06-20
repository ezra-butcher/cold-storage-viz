"""
USDA Cold Storage Dashboard
Run: python app.py
"""

import pathlib
import pandas as pd
import plotly.graph_objects as go
import plotly.colors as pc
from dash import Dash, dcc, html, Input, Output, State, callback

import fetch_data

# ── Data ──────────────────────────────────────────────────────────────────────

df = fetch_data.load_cache()

FORECAST_PATH = pathlib.Path("data/forecasts.parquet")
FITTED_PATH = pathlib.Path("data/fitted.parquet")
forecasts = pd.read_parquet(FORECAST_PATH) if FORECAST_PATH.exists() else pd.DataFrame()
fitted = pd.read_parquet(FITTED_PATH) if FITTED_PATH.exists() else pd.DataFrame()

COMMODITIES = sorted(df["commodity_desc"].unique())
DATE_MIN = df["date"].min()
DATE_MAX = df["date"].max()

# Commodities where all series are equal-standing varieties (no meaningful total)
# — default to showing all series when selected
_ALL_SERIES_DEFAULT = {
    "BEANS", "BROCCOLI", "CARROTS", "CHERRIES", "ONIONS",
    "PEAS", "PECANS", "POTATOES", "RASPBERRIES", "SWEET CORN",
}

def default_series(commodity_list):
    """Return the default selected series for a list of commodities."""
    defaults = []
    for commodity in commodity_list:
        labels = sorted(df[df["commodity_desc"] == commodity]["series_label"].unique())
        if commodity in _ALL_SERIES_DEFAULT:
            defaults.extend(labels)
        else:
            # Pick the shortest label — the true total series
            defaults.append(min(labels, key=len))
    return defaults

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
MONTH_OPTIONS = [{"label": m, "value": i + 1} for i, m in enumerate(MONTHS)]
YEAR_OPTIONS = [{"label": str(y), "value": y} for y in range(DATE_MAX.year, DATE_MIN.year - 1, -1)]

# ── Helpers ───────────────────────────────────────────────────────────────────

_COLOR_SEQUENCE = pc.qualitative.Plotly

def series_color(label: str, all_labels: list) -> str:
    idx = all_labels.index(label) if label in all_labels else 0
    return _COLOR_SEQUENCE[idx % len(_COLOR_SEQUENCE)]

def capacity_series(series: pd.Series, dates: pd.Series) -> pd.Series:
    """3-year rolling max by calendar month using the 3 preceding years (excludes current)."""
    s = series.copy()
    s.index = dates
    cap = s.groupby(s.index.month).transform(lambda g: g.shift(1).rolling(3, min_periods=1).max())
    cap.index = range(len(cap))
    return cap

def apply_unit(series: pd.Series, unit: str, dates: pd.Series = None) -> pd.Series:
    if unit == "delta":
        return series.diff()
    if unit == "pct":
        return series.pct_change() * 100
    if unit == "yoy":
        return series.diff(12)
    if unit == "yoy_pct":
        return series.pct_change(12) * 100
    if unit in ("capacity", "utilization") and dates is not None:
        cap = capacity_series(series, dates)
        if unit == "capacity":
            return cap
        return (series.reset_index(drop=True) / cap.reset_index(drop=True)) * 100
    return series

def remove_outliers(series: pd.Series) -> pd.Series:
    mean, std = series.mean(), series.std()
    return series.where((series - mean).abs() <= 3 * std)

def y_axis_label(unit: str, base_unit: str = "LB") -> str:
    if unit == "delta":
        return f"MoM change ({base_unit})"
    if unit == "pct":
        return "MoM % change"
    if unit == "yoy":
        return f"YoY change ({base_unit})"
    if unit == "yoy_pct":
        return "YoY % change"
    if unit == "capacity":
        return f"3-yr capacity ({base_unit})"
    if unit == "utilization":
        return "Capacity utilization (%)"
    return base_unit

def hex_to_rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"

_btn_style = {
    "fontSize": "12px", "padding": "5px 10px", "cursor": "pointer",
    "border": "1px solid #ccc", "borderRadius": "4px", "background": "#fff",
}
_btn_active = {**_btn_style, "background": "#e8f0fe", "borderColor": "#4a7cf7", "color": "#1a3fc7"}

# ── Layout ────────────────────────────────────────────────────────────────────

_label = {"fontSize": "11px", "fontWeight": "600", "color": "#444", "display": "block", "marginBottom": "3px"}
_card = {"background": "#fff", "borderRadius": "6px", "boxShadow": "0 1px 3px rgba(0,0,0,.08)"}
_dd_sm = {"width": "100px", "fontSize": "12px"}
_dd_yr = {"width": "80px", "fontSize": "12px"}

app = Dash(__name__, title="USDA Cold Storage")

app.layout = html.Div(
    style={"fontFamily": "system-ui, sans-serif", "padding": "12px 16px", "backgroundColor": "#f5f5f5", "minHeight": "100vh"},
    children=[
        html.H2("USDA Cold Storage Stocks", style={"marginBottom": "2px", "fontSize": "20px"}),
        html.P(
            "Source: USDA NASS Quick Stats — monthly end-of-month cold storage inventory",
            style={"color": "#777", "fontSize": "12px", "marginTop": 0, "marginBottom": "12px"},
        ),

        # ── Controls card ─────────────────────────────────────────────────────
        html.Div(
            style={**_card, "display": "flex", "flexWrap": "wrap", "gap": "20px",
                   "alignItems": "flex-end", "marginBottom": "14px", "padding": "12px 14px"},
            children=[
                # Commodity
                html.Div([
                    html.Label("Commodity", style=_label),
                    dcc.Dropdown(
                        id="commodity-select",
                        options=[{"label": c.title(), "value": c} for c in COMMODITIES],
                        value=["BEEF", "PORK"],
                        multi=True,
                        clearable=False,
                        style={"width": "280px", "fontSize": "13px"},
                    ),
                ]),
                # Series
                html.Div([
                    html.Label("Series (sub-commodity)", style=_label),
                    dcc.Dropdown(
                        id="series-select",
                        multi=True,
                        placeholder="All series",
                        style={"width": "360px", "fontSize": "12px"},
                    ),
                ]),
                # Unit
                html.Div([
                    html.Label("Unit", style=_label),
                    dcc.RadioItems(
                        id="unit-toggle",
                        options=[
                            {"label": " Actual", "value": "actual"},
                            {"label": " MoM Δ", "value": "delta"},
                            {"label": " MoM %Δ", "value": "pct"},
                            {"label": " YoY Δ", "value": "yoy"},
                            {"label": " YoY %Δ", "value": "yoy_pct"},
                            {"label": " Capacity", "value": "capacity"},
                            {"label": " Utilization %", "value": "utilization"},
                        ],
                        value="actual",
                        inline=True,
                        inputStyle={"marginRight": "3px"},
                        labelStyle={"marginRight": "14px", "fontSize": "13px"},
                    ),
                ]),
                # Start date
                html.Div([
                    html.Label("Start date", style=_label),
                    html.Div(
                        style={"display": "flex", "gap": "6px"},
                        children=[
                            dcc.Dropdown(id="start-month", options=MONTH_OPTIONS,
                                         value=1, clearable=False, style=_dd_sm),
                            dcc.Dropdown(id="start-year", options=YEAR_OPTIONS,
                                         value=1990, clearable=False, style=_dd_yr),
                        ],
                    ),
                ]),
                # End date
                html.Div([
                    html.Label("End date", style=_label),
                    html.Div(
                        style={"display": "flex", "gap": "6px"},
                        children=[
                            dcc.Dropdown(id="end-month", options=MONTH_OPTIONS,
                                         value=DATE_MAX.month, clearable=False, style=_dd_sm),
                            dcc.Dropdown(id="end-year", options=YEAR_OPTIONS,
                                         value=DATE_MAX.year, clearable=False, style=_dd_yr),
                        ],
                    ),
                ]),
                # Outliers
                html.Div([
                    html.Label("Outliers", style=_label),
                    html.Button("Remove outliers (>3σ)", id="outlier-btn", n_clicks=0, style=_btn_style),
                ]),
                # Y-axis
                html.Div([
                    html.Label("Y-axis", style=_label),
                    html.Button("Zero baseline", id="zero-btn", n_clicks=0, style=_btn_style),
                ]),
                # Forecast controls
                html.Div([
                    html.Label("Forecast horizon (months)", style=_label),
                    html.Div(
                        style={"display": "flex", "alignItems": "center", "gap": "10px"},
                        children=[
                            html.Div(
                                dcc.Slider(
                                    id="forecast-slider",
                                    min=0, max=12, step=1, value=0,
                                    marks={i: str(i) for i in range(0, 13, 3)},
                                    tooltip={"placement": "bottom", "always_visible": False},
                                ),
                                style={"width": "200px"},
                            ),
                            html.Button("Show historical fit", id="fitted-btn", n_clicks=0, style=_btn_style),
                        ],
                    ),
                ]),
            ],
        ),

        # ── Line chart + order description ────────────────────────────────────
        html.Div(
            style={**_card, "marginBottom": "12px"},
            children=[
                dcc.Graph(id="line-chart", style={"height": "440px"}),
                html.Div(id="forecast-orders", style={
                    "fontSize": "11px", "color": "#888",
                    "padding": "0 16px 10px", "lineHeight": "1.7",
                }),
            ],
        ),
        html.Div(style=_card, children=[dcc.Graph(id="histogram", style={"height": "300px"})]),
    ],
)

# ── Callbacks ─────────────────────────────────────────────────────────────────

@callback(
    Output("series-select", "options"),
    Output("series-select", "value"),
    Input("commodity-select", "value"),
)
def update_series_options(commodities):
    if not commodities:
        return [], []
    commodities = commodities if isinstance(commodities, list) else [commodities]
    labels = sorted(df[df["commodity_desc"].isin(commodities)]["series_label"].unique())
    return [{"label": s, "value": s} for s in labels], default_series(commodities)


@callback(Output("outlier-btn", "style"), Input("outlier-btn", "n_clicks"))
def toggle_outlier_style(n):
    return _btn_active if (n or 0) % 2 == 1 else _btn_style


@callback(Output("fitted-btn", "style"), Input("fitted-btn", "n_clicks"))
def toggle_fitted_style(n):
    return _btn_active if (n or 0) % 2 == 1 else _btn_style


@callback(Output("zero-btn", "style"), Input("zero-btn", "n_clicks"))
def toggle_zero_style(n):
    return _btn_active if (n or 0) % 2 == 1 else _btn_style


@callback(
    Output("line-chart", "figure"),
    Output("histogram", "figure"),
    Output("forecast-orders", "children"),
    Input("commodity-select", "value"),
    Input("series-select", "value"),
    Input("unit-toggle", "value"),
    Input("start-month", "value"),
    Input("start-year", "value"),
    Input("end-month", "value"),
    Input("end-year", "value"),
    Input("outlier-btn", "n_clicks"),
    Input("forecast-slider", "value"),
    Input("fitted-btn", "n_clicks"),
    Input("zero-btn", "n_clicks"),
)
def update_charts(commodities, series_vals, unit,
                  start_month, start_year, end_month, end_year,
                  outlier_clicks, forecast_horizon, fitted_clicks, zero_clicks):

    filter_outliers = (outlier_clicks or 0) % 2 == 1
    show_fitted = (fitted_clicks or 0) % 2 == 1
    zero_baseline = (zero_clicks or 0) % 2 == 1

    if not commodities:
        commodities = []
    if not isinstance(commodities, list):
        commodities = [commodities]

    start_date = pd.Timestamp(year=start_year, month=start_month, day=1)
    end_date = pd.Timestamp(year=end_year, month=end_month, day=1)

    mask = (df["commodity_desc"].isin(commodities)) & (df["date"] >= start_date) & (df["date"] <= end_date)
    subset = df[mask].copy()
    if series_vals:
        subset = subset[subset["series_label"].isin(series_vals)]

    base_unit = subset["unit_desc"].mode()[0] if "unit_desc" in subset.columns and not subset.empty else "LB"
    ylabel = y_axis_label(unit, base_unit)
    groups = sorted(subset["series_label"].unique()) if not subset.empty else []
    all_labels = sorted(df[df["commodity_desc"].isin(commodities)]["series_label"].unique().tolist())

    show_forecast = bool(forecast_horizon) and forecast_horizon > 0 and not forecasts.empty and unit not in ("capacity", "utilization", "yoy", "yoy_pct")

    # ── Line chart ────────────────────────────────────────────────────────────
    line_fig = go.Figure()
    order_lines = []

    for grp in groups:
        color = series_color(grp, all_labels)
        grp_df = subset[subset["series_label"] == grp].sort_values("date").drop_duplicates("date")
        y = apply_unit(grp_df["Value"], unit, grp_df["date"])
        if filter_outliers:
            y = remove_outliers(y)

        line_fig.add_trace(go.Scatter(
            x=grp_df["date"], y=y,
            mode="lines", name=grp,
            line=dict(color=color),
            hovertemplate="%{x|%b %Y}: %{y:,.0f}<extra>%{fullData.name}</extra>",
        ))

        # Historical fitted values (not shown for derived units)
        if show_fitted and not fitted.empty and unit not in ("capacity", "utilization", "yoy", "yoy_pct"):
            fit_rows = (
                fitted[(fitted["commodity_desc"].isin(commodities)) & (fitted["series_label"] == grp)
                       & (fitted["date"] >= start_date) & (fitted["date"] <= end_date)]
                .sort_values("date")
            )
            if not fit_rows.empty:
                fit_y = apply_unit(fit_rows["fitted"].reset_index(drop=True), unit, fit_rows["date"].reset_index(drop=True))
                line_fig.add_trace(go.Scatter(
                    x=fit_rows["date"], y=fit_y,
                    mode="lines", name=f"{grp} (fitted)",
                    line=dict(color=color, dash="dot", width=1),
                    hovertemplate="%{x|%b %Y}: %{y:,.0f}<extra>fitted</extra>",
                    showlegend=True,
                ))
                # CI band only meaningful in level (actual) space
                if unit == "actual" and "ci_lower" in fit_rows.columns:
                    line_fig.add_trace(go.Scatter(
                        x=list(fit_rows["date"]) + list(fit_rows["date"])[::-1],
                        y=list(fit_rows["ci_upper"]) + list(fit_rows["ci_lower"])[::-1],
                        fill="toself", fillcolor=hex_to_rgba(color, 0.07),
                        mode="lines", line=dict(width=0),
                        hoverinfo="skip", showlegend=False,
                        name=f"{grp} fitted CI",
                    ))

        # Forward forecast
        if show_forecast:
            fc_rows = (
                forecasts[(forecasts["commodity_desc"].isin(commodities)) & (forecasts["series_label"] == grp)]
                .sort_values("date").head(forecast_horizon)
            )
            if not fc_rows.empty:
                if unit == "actual":
                    fc_y = fc_rows["forecast"]
                    fc_ci_lower = fc_rows["ci_lower"]
                    fc_ci_upper = fc_rows["ci_upper"]
                else:
                    # Compute MoM transform across the actual→forecast boundary
                    actual_vals = grp_df["Value"].copy()
                    if filter_outliers:
                        actual_vals = remove_outliers(actual_vals)
                    combined = pd.concat(
                        [actual_vals.reset_index(drop=True),
                         fc_rows["forecast"].reset_index(drop=True)],
                        ignore_index=True,
                    )
                    if unit == "delta":
                        transformed = combined.diff()
                    else:
                        transformed = combined.pct_change() * 100
                    fc_y = transformed.iloc[len(actual_vals):].reset_index(drop=True)
                    fc_ci_lower = None
                    fc_ci_upper = None

                line_fig.add_trace(go.Scatter(
                    x=fc_rows["date"], y=fc_y,
                    mode="lines", name=f"{grp} (forecast)",
                    line=dict(color=color, dash="dash"),
                    hovertemplate="%{x|%b %Y}: %{y:,.0f}<extra>forecast</extra>",
                    showlegend=True,
                ))
                if fc_ci_lower is not None:
                    line_fig.add_trace(go.Scatter(
                        x=list(fc_rows["date"]) + list(fc_rows["date"])[::-1],
                        y=list(fc_ci_upper) + list(fc_ci_lower)[::-1],
                        fill="toself", fillcolor=hex_to_rgba(color, 0.1),
                        mode="lines", line=dict(width=0),
                        hoverinfo="skip", showlegend=False,
                        name=f"{grp} 95% CI",
                    ))
                if "arima_order" in fc_rows.columns:
                    ao, so = fc_rows["arima_order"].iloc[0], fc_rows["seasonal_order"].iloc[0]
                    short = grp.replace(", COLD STORAGE", "").replace(", FROZEN", "").replace(", CHILLED", "").strip()
                    order_lines.append(f"{short}: SARIMA{ao}{so}")

    line_fig.update_layout(
        title=dict(text=f"{', '.join(c.title() for c in commodities)} — Cold Storage Stocks", x=0.01, font_size=14),
        xaxis_title="Date", yaxis_title=ylabel,
        legend=dict(orientation="h", y=-0.22, font_size=11),
        margin=dict(l=70, r=20, t=40, b=90),
        plot_bgcolor="#fff", paper_bgcolor="#fff", hovermode="x unified",
        xaxis=dict(showgrid=True, gridcolor="#eee"),
        yaxis=dict(showgrid=True, gridcolor="#eee",
                   rangemode="tozero" if zero_baseline and unit in ("actual", "capacity", "utilization") else "normal"),
    )

    order_children = []
    if order_lines:
        order_children.append(html.Div([
            html.Span("Forecast models — ", style={"fontWeight": "600"}),
            html.Span("  |  ".join(order_lines)),
        ]))
    if unit in ("capacity", "utilization"):
        order_children.append(html.Div(
            "Capacity = max of the same calendar month over the prior 3 years. "
            "Utilization % = current ÷ capacity × 100.",
        ))

    # ── Histogram ─────────────────────────────────────────────────────────────
    hist_fig = go.Figure()
    for grp in groups:
        color = series_color(grp, all_labels)
        grp_df = subset[subset["series_label"] == grp].sort_values("date").drop_duplicates("date")
        y = apply_unit(grp_df["Value"], unit, grp_df["date"])
        if filter_outliers:
            y = remove_outliers(y)
        hist_fig.add_trace(go.Histogram(x=y.dropna(), name=grp, marker_color=color, opacity=0.72, nbinsx=40))

    hist_fig.update_layout(
        barmode="overlay",
        title=dict(text=f"{', '.join(c.title() for c in commodities)} — Distribution of {ylabel}", x=0.01, font_size=14),
        xaxis_title=ylabel, yaxis_title="Count",
        legend=dict(orientation="h", y=-0.28, font_size=11),
        margin=dict(l=70, r=20, t=40, b=90),
        plot_bgcolor="#fff", paper_bgcolor="#fff",
        xaxis=dict(showgrid=True, gridcolor="#eee"),
        yaxis=dict(showgrid=True, gridcolor="#eee"),
    )

    return line_fig, hist_fig, order_children


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8050)
