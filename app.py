# ======================================================================
# app.py — AIRLINE OPERATIONS INTELLIGENCE · Flight Delay Risk Explorer (a Streamlit web app)
# Pick an airline, a departure airport and a time of day → see how often those departures left 15+ min late in 2015,
# how that compares with other times and other airlines, what delays cost each airline, and the project's key charts.
# Reads only small files that live next to it in the GitHub repo: data/*.csv (Phases A, B, C) and images/*.png (Phase D).
# Run on your own computer with:  streamlit run app.py      (on Streamlit Community Cloud it runs automatically)
# ======================================================================
from pathlib import Path                                    # file paths that work on any computer
import pandas as pd                                         # tables
import plotly.graph_objects as go                           # interactive charts (same library as your maps)
import streamlit as st                                      # the web-app framework

st.set_page_config(page_title="Flight Delay Risk Explorer", page_icon="✈️", layout="wide")   # browser-tab title, icon, full width

AUTHOR = "Hemant Sahu"                                      # ← your name (shown in the sidebar and the About tab)
HERE = Path(__file__).parent                                # the folder this file lives in (= your GitHub repo)
NAVY, RED, BLUE, GREY = "#1f4e79", "#b2182b", "#2166ac", "#a6b1bd"   # same colours as the Phase D chart pack
BANDS = ["Overnight (00-05)", "Early morning (05-09)", "Late morning (09-12)",   # your Phase 3 bands…
         "Afternoon (12-17)", "Evening (17-21)", "Night (21-24)"]   # your Phase 3 time-of-day bands, in clock order
SHORT = {"American Airlines": "American", "Alaska Airlines": "Alaska", "JetBlue Airways": "JetBlue",   # full name → short name
         "Delta Air Lines": "Delta", "Atlantic Southeast Airlines": "Atlantic Southeast",
         "Frontier Airlines": "Frontier", "Hawaiian Airlines": "Hawaiian",
         "American Eagle Airlines": "American Eagle", "Spirit Air Lines": "Spirit",
         "Skywest Airlines": "SkyWest", "United Air Lines": "United", "US Airways": "US Airways",
         "Virgin America": "Virgin America", "Southwest Airlines": "Southwest"}   # short display names
CHARTS = {"01_airport_delay_risk_map.png": "Where: departure risk by airport (bubble size = traffic)",   # chart file → caption
          "02_worst_routes_map.png": "Where: the 20 routes most often late",
          "03_delay_risk_by_airline_and_time.png": "When: risk by airline and time of day",
          "04_riskiest_flight_windows.png": "Which: the 15 riskiest flight windows",
          "05_root_cause_of_delays.png": "Why: what really starts delays",
          "06_cost_of_delays_by_airline.png": "How much: what delays cost each airline"}   # Phase D files → captions


def find(name, folder):                                     # look in data/ (or images/) first, then next to app.py
    for path in (HERE / folder / name, HERE / name):        # both layouts work, so a "flat" upload is fine too
        if path.exists():                                   # found it
            return path                                     # use it
    return None                                             # not uploaded


def nice_band(label):                                       # "Evening (17-21)" → "Evening 17–21"
    return str(label).replace(" (", " ").replace(")", "").replace("-", "–")   # remove brackets, nicer dash


@st.cache_data                                              # read the files ONCE, then reuse them on every click (fast)
def load_data():                                            # everything the app reads from disk
    risk_path = find("delay_risk_index.csv", "data")        # the Delay Risk Index (Phase C) — required
    if risk_path is None:                                   # nothing to show without it
        return None, None, None                             # nothing loaded
    risk = pd.read_csv(risk_path, keep_default_na=False, na_values=[""])   # one row per airline × airport × time band
    risk["airline"] = risk["AIRLINE_NAME"].map(SHORT).fillna(risk["AIRLINE_NAME"])   # short airline name
    risk["airport"] = (risk["ORIGIN_AIRPORT"] + " – " + risk["CITY"].fillna("").astype(str)   # readable airport label…
                       + ", " + risk["STATE"].fillna("").astype(str))   # "ORD – Chicago, IL"
    cost_path = find("delay_cost_by_airline.csv", "data")   # cost model (Phase B) — optional
    cost = pd.read_csv(cost_path) if cost_path else None    # None = file not uploaded
    if cost is not None:                                    # only if the file exists
        cost["airline"] = cost["AIRLINE_NAME"].map(SHORT).fillna(cost["AIRLINE_NAME"])   # short names here too
    ap_path = find("airport_metrics.csv", "data")           # airport totals (Phase A) — optional
    airports = pd.read_csv(ap_path, keep_default_na=False, na_values=[""]) if ap_path else None   # None = not uploaded
    return risk, cost, airports                             # hand the 3 tables to the app


def pretty_table(t, pick=None, show_airport=True):          # turn index rows into a readable table
    out = pd.DataFrame({                                    # a new, display-only table
        "Your pick": ["👉" if pick is not None and i == pick else "" for i in t.index],   # marks the selected window
        "Airline": t["airline"],
        "Airport": t["ORIGIN_AIRPORT"] + " – " + t["CITY"].fillna("").astype(str),
        "Time of day": t["TIME_OF_DAY"].map(nice_band),
        "Late 15+ min (%)": (t["risk"] * 100).round(1),     # the headline number
        "95% range": [f"{lo:.0%}–{hi:.0%}" for lo, hi in zip(t["ci_low"], t["ci_high"])],
        "× national": t["x_national"].round(2),
        "Departures": t["departures"].astype(int),
        "Cancelled (%)": (t["cancel_rate"] * 100).round(1),
        "Avg min late (when late)": t["avg_late_min"].round(0)})
    if not show_airport:                                    # one-airport table → the column would repeat itself
        out = out.drop(columns="Airport")                   # drop the repeated column
    return out if pick is not None else out.drop(columns="Your pick")   # no marker column when nothing is picked


TABLE_CONFIG = {                                            # how st.dataframe displays some columns
    "Late 15+ min (%)": st.column_config.ProgressColumn("Late 15+ min", format="%.1f%%", min_value=0, max_value=100),
    "× national": st.column_config.NumberColumn(format="%.2f×"),
    "Departures": st.column_config.NumberColumn(format="%,d"),
    "Cancelled (%)": st.column_config.NumberColumn(format="%.1f%%"),
    "Avg min late (when late)": st.column_config.NumberColumn(format="%.0f min")}


def risk_bars(labels, r, lo, hi, chosen, base, horizontal=False):   # bar chart: red = riskier than national, blue = safer
    colors = [RED if v > base else BLUE for v in r]         # colour = above or below the national rate
    alpha = [1.0 if lab == chosen else 0.45 for lab in labels]   # the selected bar stands out
    err = dict(type="data", symmetric=False, array=list(hi - r), arrayminus=list(r - lo), color="#555555", thickness=1.2)
    text = [f"{v:.0%}" for v in r]                          # value printed on each bar
    if horizontal:                                          # airlines → horizontal bars (long names fit)
        bar = go.Bar(y=labels, x=r, orientation="h", error_x=err, text=text, textposition="inside",   # bars + whiskers + numbers
                     insidetextanchor="start", marker=dict(color=colors, opacity=alpha),
                     hovertemplate="%{y}: %{x:.1%}<extra></extra>")
    else:                                                   # time bands → vertical bars in clock order
        bar = go.Bar(x=labels, y=r, error_y=err, text=text, textposition="inside", insidetextanchor="start",   # bars + whiskers + numbers
                     marker=dict(color=colors, opacity=alpha), hovertemplate="%{x}: %{y:.1%}<extra></extra>")
    fig = go.Figure(bar)                                    # a chart with one layer of bars
    top = max(float(max(hi)), base) * 1.15                  # headroom above the tallest whisker
    line = dict(line_dash="dash", line_color=NAVY, line_width=1.5)   # dashed navy line = national rate
    if horizontal:                                          # orientation decides where the national line goes
        fig.add_vline(x=base, **line)                       # national line (vertical)
        fig.add_annotation(x=base, y=1.0, xref="x", yref="paper", yanchor="bottom", showarrow=False,
                           text=f"national {base:.0%}", font=dict(color=NAVY))   # label above the chart, not on a bar
        fig.update_xaxes(range=[0, top], tickformat=".0%")   # 0.25 → 25%
        fig.update_yaxes(autorange="reversed")              # first airline at the top
    else:                                                   # vertical bars
        fig.add_hline(y=base, annotation_text=f"national {base:.0%}", annotation_font_color=NAVY,
                      annotation_position="top left", **line)   # national line (horizontal), labelled at the left
        fig.update_yaxes(range=[0, top], tickformat=".0%")   # 0.25 → 25%
    fig.update_traces(textfont_color="white")               # white numbers inside coloured bars
    fig.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10), showlegend=False,   # size, margins, clean background
                      plot_bgcolor="white", font=dict(size=13))
    fig.update_xaxes(showgrid=horizontal, gridcolor="#eeeeee")   # light grid on the value axis only
    fig.update_yaxes(showgrid=not horizontal, gridcolor="#eeeeee")
    return fig                                              # hand the finished chart back


# ----------------------------------------------------------------------
# DATA
# ----------------------------------------------------------------------
risk, cost, airports = load_data()                          # cached → instant after the first visit
if risk is None:                                            # friendly message instead of a crash
    st.error("**data/delay_risk_index.csv** is missing. Upload it to your GitHub repo (Phase E steps), then refresh.")   # red box
    st.stop()                                               # stop drawing the page here
BASE = float((risk["risk"] / risk["x_national"]).median())  # national rate used in Phase C (every row has the same)

# ----------------------------------------------------------------------
# SIDEBAR — the 3 choices (each list only offers combinations that exist in the index)
# ----------------------------------------------------------------------
st.sidebar.title("✈️ Plan a departure")                     # sidebar heading
airline_list = sorted(risk["airline"].unique())             # every airline in the index, A → Z
airline = st.sidebar.selectbox("1 · Airline", airline_list,   # dropdown → returns the chosen airline
                               index=airline_list.index("United") if "United" in airline_list else 0)
mine = risk[risk["airline"] == airline]                     # this airline's windows only
airport_list = sorted(mine["airport"].unique())             # airports where it has ≥ 200 departures in some band
busiest = mine.groupby("airport")["departures"].sum().idxmax()   # its biggest airport = sensible default
airport = st.sidebar.selectbox("2 · Departure airport", airport_list, index=airport_list.index(busiest))   # dropdown → airport label
here = mine[mine["airport"] == airport]                     # this airline at this airport (one row per band)
band_list = [b for b in BANDS if b in set(here["TIME_OF_DAY"])]   # bands that exist, in clock order
band = st.sidebar.radio("3 · Scheduled departure time", band_list, format_func=nice_band,   # round buttons → band
                        index=band_list.index("Evening (17-21)") if "Evening (17-21)" in band_list else 0)
st.sidebar.caption("Only combinations with **at least 200 departures** in 2015 are listed, so every number is "   # small grey note
                   "reliable to about ±7 percentage points or better.")
st.sidebar.divider()                                        # thin line
st.sidebar.caption(f"Data: U.S. DOT on-time performance 2015 (Kaggle) · Built by {AUTHOR}")   # credits

pick = here[here["TIME_OF_DAY"] == band].iloc[0]            # the selected window (one row of the index)
code, city = pick["ORIGIN_AIRPORT"], pick["CITY"]            # e.g. "ORD", "Chicago"

# ----------------------------------------------------------------------
# PAGE
# ----------------------------------------------------------------------
st.title("Flight Delay Risk Explorer")                      # big page title
st.caption(f"How often did flights leave **15+ minutes late**? 2015 U.S. domestic departures (Jan–Sep & Nov–Dec) · "   # subtitle
           f"national average **{BASE:.1%}** · historical patterns, not a live forecast")
tab_risk, tab_top, tab_charts, tab_cost, tab_about = st.tabs(   # 5 tabs across the page
    ["🎯 Risk lookup", "🏆 Riskiest windows", "📊 Key charts", "💲 Cost of delays", "ℹ️ About & method"])

with tab_risk:                                              # ---- TAB 1: the lookup ----
    sentence = (f"{airline} departures from {code} ({city}) scheduled {nice_band(band)} left 15+ min late "   # the verdict sentence
                f"**{pick['risk']:.0%}** of the time — **{pick['x_national']:.1f}×** the national {BASE:.0%}.")
    if pick["ci_low"] > BASE:                               # even the low end of the 95% range is above national
        st.error("🔴 **Riskier than average.** " + sentence)   # red box
    elif pick["ci_high"] < BASE:                            # even the high end is below national
        st.success("🟢 **Safer than average.** " + sentence)   # green box
    else:                                                   # the range includes the national rate
        st.info("⚪ **About average.** " + sentence)         # grey/blue box

    c1, c2, c3, c4 = st.columns(4)                          # four headline numbers side by side
    c1.metric("Chance of leaving 15+ min late", f"{pick['risk']:.1%}",   # big number + red/green arrow
              f"{(pick['risk'] - BASE) * 100:+.1f} pts vs national", delta_color="inverse", border=True)
    c2.metric("95% confidence range", f"{pick['ci_low']:.0%} – {pick['ci_high']:.0%}", border=True,   # how firm the number is
              help="Where the true rate very likely lies, given the number of departures (Wilson interval).")
    c3.metric("Cancelled", f"{pick['cancel_rate']:.1%}", border=True)   # share cancelled
    late_min = pick["avg_late_min"]                         # minutes late, when late
    c4.metric("Average delay when late", "–" if pd.isna(late_min) else f"{late_min:.0f} min", border=True)   # how bad, when bad
    extra = ""                                              # optional airport-wide note
    if airports is not None:                                # airport-wide context from Phase A
        a = airports[airports["ORIGIN_AIRPORT"] == code]    # this airport's row
        if len(a):                                          # found it
            ranked = airports[airports["enough_flights"].astype(str).str.lower() == "true"]   # airports with ≥ 1,000 departures
            rank = int((ranked["dep_delay_rate"] > a["dep_delay_rate"].iloc[0]).sum()) + 1   # 1 = riskiest airport
            extra = (f" · All airlines at {code}: {a['dep_delay_rate'].iloc[0]:.0%} of departures left 15+ min late "   # the note
                     f"(#{rank} riskiest of {len(ranked)} airports)")
    st.caption(f"Based on {int(pick['departures']):,} departures ({int(pick['scheduled']):,} scheduled){extra}")   # sample size

    left, right = st.columns(2)                             # two charts side by side
    with left:                                              # everything indented below goes in the left column
        st.subheader("Best time to fly")                    # small heading
        t = here.set_index("TIME_OF_DAY").loc[band_list]    # this airline at this airport, every available band
        names = ["<br>".join(nice_band(b).rsplit(" ", 1)) for b in t.index]   # "Early morning<br>05–09" (2 lines)
        st.plotly_chart(risk_bars(names, t["risk"], t["ci_low"], t["ci_high"],   # draw the chart
                                  "<br>".join(nice_band(band).rsplit(" ", 1)), BASE), key="by_time")
        best = t["risk"].idxmin()                           # the safest band
        st.caption(f"Lowest risk for {airline} at {code}: **{nice_band(best)}** ({t.loc[best, 'risk']:.0%}). "   # takeaway
                   f"Bars = share late · whiskers = 95% range · faded bars = other times.")
    with right:                                             # …and this in the right column
        st.subheader("Other airlines, same airport and time")   # small heading
        o = risk[(risk["ORIGIN_AIRPORT"] == code) & (risk["TIME_OF_DAY"] == band)].sort_values("risk")   # safest first
        st.plotly_chart(risk_bars(list(o["airline"]), o["risk"], o["ci_low"], o["ci_high"], airline, BASE,   # draw the chart
                                  horizontal=True), key="by_airline")
        if len(o) > 1:                                      # at least one alternative to compare with
            safest = o.iloc[0]                              # lowest risk airline
            gap = (pick["risk"] - safest["risk"]) * 100     # difference in percentage points
            st.caption(f"Safest at {code}, {nice_band(band)}: **{safest['airline']}** ({safest['risk']:.0%})"   # takeaway
                       + (f" — {gap:.0f} points below {airline}." if safest["airline"] != airline else "."))
        else:                                               # no alternative airline
            st.caption(f"Only {airline} has 200+ departures from {code} at this time.")   # say so

    st.subheader(f"Delay-risk table — every airline and time of day at {code}")   # table heading
    rows = risk[risk["ORIGIN_AIRPORT"] == code].sort_values("risk", ascending=False)   # riskiest first
    st.dataframe(pretty_table(rows, pick=pick.name, show_airport=False), hide_index=True, column_config=TABLE_CONFIG)   # interactive table

with tab_top:                                               # ---- TAB 2: nationwide ranking ----
    st.subheader("The 20 riskiest flight windows in the U.S.")   # heading
    choose = st.multiselect("Show only these airlines (optional)", airline_list)   # empty = all airlines
    pool = risk[risk["airline"].isin(choose)] if choose else risk   # filter if airlines were chosen
    top20 = pool.nlargest(20, ["risk", "departures"])       # highest risk first; bigger sample breaks ties
    st.dataframe(pretty_table(top20), hide_index=True, column_config=TABLE_CONFIG,   # interactive table
                 height=35 * (len(top20) + 1) + 3)          # tall enough to show all 20 rows without scrolling
    after5 = top20["TIME_OF_DAY"].isin(["Evening (17-21)", "Night (21-24)"]).mean()   # share departing after 5 PM
    st.caption(f"{after5:.0%} of these windows depart after 5 PM — delays snowball through the day as late aircraft "   # takeaway
               f"pass their delay on to the next flight.")

with tab_charts:                                            # ---- TAB 3: the Phase D chart pack ----
    shown = 0                                               # how many charts were found
    for name, caption in CHARTS.items():                    # one image per chart, in story order
        path = find(name, "images")                         # where the PNG is (or None)
        if path is not None:                                # uploaded → show it
            st.image(str(path), caption=caption, width="stretch")   # full-width picture
            shown += 1                                      # count it
    if shown == 0:                                          # images not uploaded yet
        st.info("Upload the 6 PNG files from Phase D to an **images** folder in your repo to show them here.")   # friendly hint

with tab_cost:                                              # ---- TAB 4: the Phase B cost model ----
    if cost is None:                                        # cost file not uploaded
        st.info("Upload **data/delay_cost_by_airline.csv** (Phase B) to show this tab.")   # friendly hint
    else:                                                   # the cost file exists → show it
        mine_cost = cost[cost["airline"] == airline]        # the selected airline's row
        if len(mine_cost):                                  # the selected airline's numbers first
            m = mine_cost.iloc[0]                           # as a single row
            k1, k2, k3 = st.columns(3)                      # three headline numbers
            # "\\$" = a plain dollar sign: Streamlit would read the text between two "$" signs as a maths formula
            k1.metric(f"{airline}: yearly cost of delays", f"\\${m['cost_low_$M']:,.0f}M – \\${m['cost_high_$M']:,.0f}M",
                      border=True)
            k2.metric("Cost per scheduled flight", f"\\${m['cost_per_flight_$']:,.0f}", border=True)
            k3.metric("Knock-on (late-aircraft) share", f"{m['cascade_share_%']:.0f}%", border=True)   # cascade share
        table = pd.DataFrame({"Airline": cost["airline"],   # readable cost table
                              "Cost, low ($M)": cost["cost_low_$M"].round(0),
                              "Cost, high ($M)": cost["cost_high_$M"].round(0),
                              "Cost per flight ($)": cost["cost_per_flight_$"].round(0),
                              "Knock-on share (%)": cost["cascade_share_%"].round(0)}).sort_values("Cost, high ($M)", ascending=False)
        st.dataframe(table, hide_index=True, column_config={   # interactive table with $ formats
            "Cost, low ($M)": st.column_config.NumberColumn(format="$%,.0fM"),
            "Cost, high ($M)": st.column_config.NumberColumn(format="$%,.0fM"),
            "Cost per flight ($)": st.column_config.NumberColumn(format="$%,.0f"),
            "Knock-on share (%)": st.column_config.NumberColumn(format="%.0f%%")},
            height=35 * (len(table) + 1) + 3)                # tall enough for every airline
        st.caption(f"Total: \\${cost['cost_low_$M'].sum() / 1e3:.2f}–{cost['cost_high_$M'].sum() / 1e3:.2f} billion in 2015. "
                   "Assumption: \\$75–\\$100 per delay minute (Airlines for America aircraft block-time cost, today's money); "
                   "airline costs only — passengers' time excluded; cancelled flights not costed.")

with tab_about:                                             # ---- TAB 5: method, limits, credits ----
    # st.markdown = formatted text (Markdown): **bold**, *italic*, "- " starts a bullet point
    st.markdown(f"""
**What this app shows** — for each airline × departure airport × scheduled time-of-day window, the share of 2015
departures that left **15 or more minutes late** (the U.S. DOT definition of a delay). It is plain counting
(descriptive statistics), not a machine-learning prediction.

**How the numbers were built**
- Source: U.S. Department of Transportation on-time data, 2015 (Kaggle "2015 Flight Delays and Cancellations", 5.8M flights).
- October is excluded: that month's file uses numeric airport IDs that can't be matched to airport codes.
- Only windows with **at least 200 departures** are shown (worst-case margin of error ±6.9 points at 95% confidence).
- The 95% range is a Wilson confidence interval; "riskier / safer than average" means the whole range sits above / below
  the national {BASE:.1%}.
- Costs: delay minutes × \\$75–\\$100 per minute (an industry average, stated as an assumption).

**Limits** — 2015 patterns may not match today's schedules; risk is about departures (not arrivals); weather,
season and route also matter.

Built by **{AUTHOR}** as part of the *Airline Operations Intelligence* portfolio project.
""")
