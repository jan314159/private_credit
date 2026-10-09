"""Altair charts for the Charts and Sensitivity pages."""
import altair as alt
import pandas as pd
import streamlit as st

# APS corporate colors (Color1 red, Color2/3 teal), checked for contrast and colorblind separation.
# "main" and "second" are the series colors; "pos" is the strong (better) end of the heatmap.
_PALETTE = {
    "light": {"main": "#468e99", "second": "#e83e33", "red": "#e83e33", "pos": "#005864", "ink": "#0b0b0b",
              "ink2": "#52514e", "mid": "#f0efec", "rule": "#c3c2b7", "bg": "#ffffff"},
    "dark": {"main": "#468e99", "second": "#e83e33", "red": "#e83e33", "pos": "#468e99", "ink": "#ffffff",
             "ink2": "#c3c2b7", "mid": "#383835", "rule": "#383835", "bg": "#0e1117"},
}

MONEY = ",.0f"
HEIGHT = 300


def palette():
    theme = getattr(getattr(st.context, "theme", None), "type", None)
    return _PALETTE["dark" if theme == "dark" else "light"]


def _month_hover():
    return alt.selection_point(fields=["Month"], nearest=True, on="pointerover", clear="pointerout", empty=False)


def cumulative_cf(cf, payback_month):
    """Cumulative net cash flow after all costs; crosses zero at payback."""
    c = palette()
    data = pd.DataFrame({
        "Month": pd.to_datetime(cf["Month (calendar)"]),
        "Cumulative": cf["Cumulative Net CF after all taxes"],
        "Monthly": cf["Net CF after all taxes"],
    })
    hover = _month_hover()
    base = alt.Chart(data).encode(
        x=alt.X("Month:T", title=None, axis=alt.Axis(format="%b %Y")),
        y=alt.Y("Cumulative:Q", title="Cumulative net cash flow", axis=alt.Axis(format="~s")),
    )
    layers = [
        base.mark_area(color=c["main"], opacity=0.1, interpolate="step-after"),
        base.mark_line(color=c["main"], strokeWidth=2, interpolate="step-after"),
        alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=c["rule"], strokeWidth=1).encode(y="y:Q"),
        base.mark_rule(color=c["ink2"], strokeWidth=1).encode(
            opacity=alt.condition(hover, alt.value(1), alt.value(0)),
            tooltip=[alt.Tooltip("Month:T", format="%b %Y"),
                     alt.Tooltip("Monthly:Q", format=MONEY, title="Net cash flow"),
                     alt.Tooltip("Cumulative:Q", format=MONEY, title="Cumulative")],
        ).add_params(hover),
    ]
    if payback_month is not None:
        point = data.iloc[[payback_month]].assign(Label="Payback")
        dot = alt.Chart(point).encode(x="Month:T", y="Cumulative:Q")
        layers += [
            dot.mark_point(filled=True, size=90, color=c["main"], stroke=c["mid"], strokeWidth=2, opacity=1),
            dot.mark_text(align="right", dx=-10, dy=-4, color=c["ink2"]).encode(text="Label:N"),
        ]
    return alt.layer(*layers).properties(height=HEIGHT)


def waterfall(steps):
    """Gross collections down to the net gain."""
    c = palette()
    data = steps.assign(Order=range(len(steps)), Label=steps["Amount"].map(lambda v: f"{v:,.0f}"))
    data["Top"] = data[["Start", "End"]].max(axis=1)
    x = alt.X("Step:N", sort=alt.SortField("Order"), title=None, axis=alt.Axis(labelAngle=0))
    color = alt.Color("Type:N", title=None,
                      scale=alt.Scale(domain=["Inflow", "Deduction", "Result"], range=[c["main"], c["red"], c["ink2"]]),
                      legend=alt.Legend(orient="top"))
    bars = alt.Chart(data).mark_bar(width=alt.RelativeBandSize(0.6), cornerRadius=2).encode(
        x=x,
        y=alt.Y("Start:Q", title="Amount", axis=alt.Axis(format="~s")),
        y2="End:Q",
        color=color,
        tooltip=["Step:N", alt.Tooltip("Amount:Q", format=MONEY)],
    )
    labels = alt.Chart(data).mark_text(dy=-6, color=c["ink2"], fontSize=11).encode(
        x=x, y="Top:Q", text="Label:N")
    zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=c["rule"]).encode(y="y:Q")
    return alt.layer(bars, zero, labels).properties(height=HEIGHT)


def outstanding_balance(gc):
    """Principal outstanding with accrued unpaid interest stacked on top."""
    c = palette()
    data = pd.DataFrame({
        "Month": pd.to_datetime(gc["Month (calendar)"]),
        "Principal": gc["Principal Left"],
        "Accrued interest": gc["Interest Left"].fillna(0),
    })
    data["Total"] = data["Principal"] + data["Accrued interest"]
    hover = _month_hover()
    x = alt.X("Month:T", title=None, axis=alt.Axis(format="%b %Y"))
    y_axis = alt.Axis(format="~s")
    base = alt.Chart(data).encode(x=x)

    long = data.melt(id_vars=["Month", "Total"], value_vars=["Principal", "Accrued interest"], var_name="Part")
    legend = alt.Chart(long).mark_line(strokeWidth=2).encode(
        x=x, y=alt.Y("value:Q", stack=True, title="Outstanding", axis=y_axis),
        color=alt.Color("Part:N", title=None, sort=["Principal", "Accrued interest"],
                        scale=alt.Scale(domain=["Principal", "Accrued interest"], range=[c["main"], c["second"]]),
                        legend=alt.Legend(orient="top")),
        opacity=alt.value(0),
    )
    layers = [
        legend,
        base.mark_area(color=c["main"], opacity=0.1, interpolate="step-after").encode(y=alt.Y("Principal:Q", axis=y_axis)),
        base.mark_line(color=c["main"], strokeWidth=2, interpolate="step-after").encode(y="Principal:Q"),
        base.mark_area(color=c["second"], opacity=0.15, interpolate="step-after").encode(y="Principal:Q", y2="Total:Q"),
        base.mark_line(color=c["second"], strokeWidth=2, interpolate="step-after").encode(y="Total:Q"),
        base.mark_rule(color=c["ink2"], strokeWidth=1).encode(
            opacity=alt.condition(hover, alt.value(1), alt.value(0)),
            tooltip=[alt.Tooltip("Month:T", format="%b %Y"),
                     alt.Tooltip("Principal:Q", format=MONEY),
                     alt.Tooltip("Accrued interest:Q", format=MONEY),
                     alt.Tooltip("Total:Q", format=MONEY, title="Total exposure")],
        ).add_params(hover),
    ]
    return alt.layer(*layers).properties(height=HEIGHT)


def interest_by_month(gc):
    """Interest collected per month (principal repayments show in the outstanding balance)."""
    c = palette()
    data = pd.DataFrame({
        "Month": pd.to_datetime(gc["Month (calendar)"]),
        "Interest": gc["Interest Paid"],
    }).iloc[1:]
    data = data[data["Interest"] > 0]
    return alt.Chart(data).mark_bar(width=alt.RelativeBandSize(0.7), cornerRadiusTopLeft=4, cornerRadiusTopRight=4,
                                    color=c["main"]).encode(
        x=alt.X("yearmonth(Month):T", title=None, axis=alt.Axis(format="%b %Y")),
        y=alt.Y("Interest:Q", title="Interest collected", axis=alt.Axis(format="~s")),
        tooltip=[alt.Tooltip("yearmonth(Month):T", format="%b %Y", title="Month"),
                 alt.Tooltip("Interest:Q", format=MONEY)],
    ).properties(height=HEIGHT)


def fees_by_year(fees):
    """Agent fee per year with the upfront fees on top in the funding year."""
    c = palette()
    long = fees.melt(id_vars="Year", var_name="Fee", value_name="Amount")
    long = long[long["Amount"] > 0]
    return alt.Chart(long).mark_bar(width=alt.RelativeBandSize(0.3), stroke=c["bg"], strokeWidth=2).encode(
        x=alt.X("Year:O", title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("Amount:Q", stack=True, title="Fees", axis=alt.Axis(format="~s")),
        color=alt.Color("Fee:N", title=None, sort=["Agent fee", "Upfront fees"],
                        scale=alt.Scale(domain=["Agent fee", "Upfront fees"], range=[c["main"], c["second"]]),
                        legend=alt.Legend(orient="top")),
        order=alt.Order("Fee:N"),
        tooltip=["Year:O", "Fee:N", alt.Tooltip("Amount:Q", format=MONEY)],
    ).properties(height=HEIGHT)


def xirr_heatmap(grid, x_title, y_title, reference, x_order, y_order):
    """XIRR for each combination, diverging around the reference XIRR (gray = same as reference)."""
    c = palette()
    data = grid.copy()
    spread = max((data["XIRR"] - reference).abs().max(), 1e-6)
    # Strong colors near the poles need white text; light cells near the reference keep the ink color
    data["Text"] = (data["XIRR"] - reference).abs() / spread > 0.6
    data["Label"] = data["XIRR"].map(lambda v: "n/a" if pd.isna(v) else f"{v:.1%}")
    x = alt.X("X:O", title=x_title, sort=x_order, axis=alt.Axis(labelAngle=0))
    y = alt.Y("Y:O", title=y_title, sort=y_order)
    cells = alt.Chart(data).mark_rect(stroke=c["mid"], strokeWidth=2, cornerRadius=2).encode(
        x=x, y=y,
        color=alt.Color("XIRR:Q", title="XIRR",
                        scale=alt.Scale(domain=[reference - spread, reference, reference + spread],
                                        range=[c["red"], c["mid"], c["pos"]], interpolate="rgb"),
                        legend=alt.Legend(format=".1%", orient="right")),
        tooltip=[alt.Tooltip("X:O", title=x_title), alt.Tooltip("Y:O", title=y_title),
                 alt.Tooltip("XIRR:Q", format=".2%")],
    )
    base_cell = alt.Chart(data[data["Base"]]).mark_rect(fill=None, stroke=c["ink"], strokeWidth=2, cornerRadius=2).encode(x=x, y=y)
    text = alt.Chart(data).mark_text(fontSize=12).encode(
        x=x, y=y, text="Label:N",
        color=alt.condition(alt.datum.Text, alt.value("#ffffff"), alt.value(c["ink"])),
    )
    return alt.layer(cells, base_cell, text).properties(height=40 * data["Y"].nunique() + 40)


def scenario_bars(results):
    """XIRR per scenario, with the base case marked by a rule."""
    c = palette()
    data = results.dropna(subset=["XIRR"]).assign(Label=lambda d: d["XIRR"].map(lambda v: f"{v:.2%}"))
    y = alt.Y("Scenario:N", sort=None, title=None, axis=alt.Axis(labelLimit=300))
    bars = alt.Chart(data).mark_bar(height=alt.RelativeBandSize(0.6), cornerRadiusEnd=4, color=c["main"]).encode(
        x=alt.X("XIRR:Q", title="XIRR (after tax)", axis=alt.Axis(format="%", tickCount=8),
                # Room past the longest bars for their value labels
                scale=alt.Scale(domain=[min(data["XIRR"].min(), 0) * 1.25, max(data["XIRR"].max(), 0) * 1.15])),
        y=y,
        tooltip=["Scenario:N", alt.Tooltip("XIRR:Q", format=".2%")],
    )
    # Value just past the end of each bar, on whichever side the bar grows
    above = bars.mark_text(align="left", dx=6, color=c["ink2"]).encode(text="Label:N").transform_filter("datum.XIRR >= 0")
    below = bars.mark_text(align="right", dx=-6, color=c["ink2"]).encode(text="Label:N").transform_filter("datum.XIRR < 0")
    layers = [bars, above, below]
    base = data.loc[data["Scenario"] == "Base case", "XIRR"]
    if len(base):
        layers.append(alt.Chart(pd.DataFrame({"x": [base.iloc[0]]})).mark_rule(color=c["ink2"], strokeDash=[]).encode(x="x:Q"))
    return alt.layer(*layers).properties(height=45 * len(data) + 30)
