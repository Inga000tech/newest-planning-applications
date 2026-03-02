"""
MAPlanning Retail Lead Dashboard — Streamlit App
=================================================
Reads live from Google Sheets. Mark filters, sorts, and
adds comments. Nothing is scraped here — just display.

SETUP:
  pip install streamlit gspread google-auth pandas
  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import json, re

# ── PAGE CONFIG ─────────────────────────────────────────────
st.set_page_config(
    page_title="MAPlanning Lead Tracker",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── STYLING ──────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500;600&display=swap');

  html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
  }

  /* Dark sidebar */
  section[data-testid="stSidebar"] {
    background: #0f1117;
    border-right: 1px solid #1e2130;
  }
  section[data-testid="stSidebar"] * {
    color: #c9d1d9 !important;
  }
  section[data-testid="stSidebar"] .stSelectbox label,
  section[data-testid="stSidebar"] .stMultiSelect label,
  section[data-testid="stSidebar"] .stSlider label,
  section[data-testid="stSidebar"] .stDateInput label {
    color: #8b949e !important;
    font-size: 0.75rem !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  /* Main background */
  .main .block-container {
    background: #0d1117;
    padding-top: 1.5rem;
  }

  /* Metric cards */
  [data-testid="metric-container"] {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 1rem 1.25rem;
  }
  [data-testid="metric-container"] label {
    color: #8b949e !important;
    font-size: 0.72rem !important;
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }
  [data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-family: 'DM Mono', monospace;
    font-size: 2rem !important;
    color: #f0f6fc !important;
  }
  [data-testid="metric-container"] [data-testid="stMetricDelta"] {
    font-size: 0.8rem !important;
  }

  /* Score badge */
  .score-badge {
    display: inline-block;
    font-family: 'DM Mono', monospace;
    font-size: 0.8rem;
    font-weight: 500;
    padding: 2px 8px;
    border-radius: 20px;
    min-width: 40px;
    text-align: center;
  }
  .score-high   { background: #1f4a2e; color: #3fb950; border: 1px solid #2ea043; }
  .score-mid    { background: #3d2800; color: #e3b341; border: 1px solid #9e6a03; }
  .score-low    { background: #2d1317; color: #f85149; border: 1px solid #b22222; }

  /* Lead cards */
  .lead-card {
    background: #161b22;
    border: 1px solid #21262d;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
    transition: border-color 0.15s;
  }
  .lead-card:hover { border-color: #388bfd; }
  .lead-card .council-tag {
    display: inline-block;
    background: #1c2d3f;
    color: #79c0ff;
    border: 1px solid #1f6feb;
    border-radius: 4px;
    font-size: 0.7rem;
    font-weight: 600;
    padding: 2px 7px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-right: 6px;
  }
  .lead-card .ref {
    font-family: 'DM Mono', monospace;
    font-size: 0.85rem;
    color: #8b949e;
  }
  .lead-card .desc {
    font-size: 0.95rem;
    color: #c9d1d9;
    margin: 0.5rem 0 0.3rem;
    line-height: 1.5;
  }
  .lead-card .meta {
    font-size: 0.78rem;
    color: #6e7681;
    margin-top: 0.4rem;
  }
  .lead-card .triggers {
    display: inline-block;
    background: #1a2535;
    color: #58a6ff;
    border: 1px solid #1f4060;
    border-radius: 4px;
    font-size: 0.7rem;
    padding: 1px 6px;
    margin: 2px 2px 0 0;
  }
  .lead-card .link-btn {
    display: inline-block;
    background: #21262d;
    color: #79c0ff;
    border: 1px solid #30363d;
    border-radius: 6px;
    font-size: 0.75rem;
    padding: 3px 10px;
    text-decoration: none;
    margin-right: 6px;
    margin-top: 6px;
  }
  .lead-card .link-btn:hover { border-color: #388bfd; }

  /* Header */
  .app-header {
    padding: 0 0 1.5rem;
    border-bottom: 1px solid #21262d;
    margin-bottom: 1.5rem;
  }
  .app-header h1 {
    font-size: 1.6rem;
    font-weight: 600;
    color: #f0f6fc;
    margin: 0;
  }
  .app-header p {
    color: #6e7681;
    font-size: 0.85rem;
    margin: 0.3rem 0 0;
  }

  /* Table */
  .stDataFrame { border-radius: 10px; overflow: hidden; }

  /* Divider */
  hr { border-color: #21262d; }

  /* Buttons */
  .stButton > button {
    background: #21262d;
    color: #c9d1d9;
    border: 1px solid #30363d;
    border-radius: 6px;
    font-size: 0.8rem;
  }
  .stButton > button:hover {
    background: #30363d;
    border-color: #58a6ff;
    color: #f0f6fc;
  }

  /* Hide default streamlit branding */
  #MainMenu { visibility: hidden; }
  footer    { visibility: hidden; }
  header    { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── CONSTANTS ────────────────────────────────────────────────
SHEET_ID = "172bpv-b2_nK5ENE1XPk5rWeokvnr1sjHvLBfVzHWh6c"
SHEET_NAME = "Leads"

COLS = [
    "Council", "Reference", "Address", "Description", "App Type",
    "Applicant", "Agent", "Date Received", "Date Decided", "Decision",
    "Trigger Words", "Score", "Keyword", "Portal Link", "Decision Doc URL",
    "Date Found", "Mark's Comments",
]

# ── GOOGLE SHEETS CONNECTION ─────────────────────────────────
@st.cache_resource(ttl=300)   # refresh every 5 min
def get_gspread_client():
    """
    Connects to Sheets using service account credentials stored in
    Streamlit secrets (st.secrets["gcp_service_account"]).
    See SETUP GUIDE below for how to set this up.
    """
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes,
    )
    return gspread.authorize(creds)

@st.cache_data(ttl=300)   # cache data for 5 minutes
def load_data():
    try:
        client = get_gspread_client()
        ws     = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
        rows   = ws.get_all_values()
        if len(rows) < 2:
            return pd.DataFrame(columns=COLS)
        headers = rows[0]
        df = pd.DataFrame(rows[1:], columns=headers)

        # Clean + type-cast
        df["Score"] = pd.to_numeric(df["Score"], errors="coerce").fillna(0).astype(int)

        # Parse Date Decided
        def parse_date(s):
            for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d %b %Y",
                        "%a %d %b %Y", "%d-%m-%Y"]:
                try: return datetime.strptime(s.strip(), fmt)
                except: pass
            return None

        df["_date_decided"] = df["Date Decided"].apply(parse_date)

        # Parse Date Found
        df["_date_found"] = pd.to_datetime(df["Date Found"], errors="coerce")

        return df
    except Exception as e:
        st.error(f"❌ Could not load data: {e}")
        return pd.DataFrame(columns=COLS)

def save_comment(reference, comment):
    try:
        client = get_gspread_client()
        ws     = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
        refs   = ws.col_values(2)  # Column B = Reference
        if reference in refs:
            row_idx = refs.index(reference) + 1
            ws.update_cell(row_idx, 17, comment)  # Column Q = Mark's Comments
            st.cache_data.clear()
            return True
    except Exception as e:
        st.error(f"❌ Could not save: {e}")
    return False

# ── SCORE BADGE HTML ─────────────────────────────────────────
def score_badge(score):
    cls = "score-high" if score >= 75 else "score-mid" if score >= 55 else "score-low"
    return f'<span class="score-badge {cls}">{score}</span>'

# ── MAIN APP ─────────────────────────────────────────────────
def main():
    # Header
    st.markdown("""
    <div class="app-header">
      <h1>🏗️ MAPlanning Retail Lead Tracker</h1>
      <p>Refused retail planning applications with sequential test / retail impact grounds</p>
    </div>
    """, unsafe_allow_html=True)

    # Load data
    with st.spinner("Loading leads from Google Sheets..."):
        df = load_data()

    if df.empty:
        st.warning("No leads found in the sheet yet. Run the Colab scraper first.")
        return

    # ── SIDEBAR FILTERS ──────────────────────────────────────
    with st.sidebar:
        st.markdown("### 🔍 Filters")
        st.markdown("---")

        # Date range
        st.markdown("**Decision Date Range**")
        valid_dates = df["_date_decided"].dropna()
        if not valid_dates.empty:
            min_date = valid_dates.min().date()
            max_date = valid_dates.max().date()
            default_from = max(min_date, (datetime.now() - timedelta(weeks=12)).date())
            col1, col2 = st.columns(2)
            with col1:
                date_from = st.date_input("From", value=default_from,
                                          min_value=min_date, max_value=max_date, label_visibility="collapsed")
            with col2:
                date_to   = st.date_input("To",   value=max_date,
                                          min_value=min_date, max_value=max_date, label_visibility="collapsed")
            st.caption(f"{date_from.strftime('%d %b %Y')} → {date_to.strftime('%d %b %Y')}")
        else:
            date_from = date_to = None

        st.markdown("---")

        # Score range
        st.markdown("**Min Score**")
        min_score = st.slider("", 0, 100, 50, 5, label_visibility="collapsed")

        st.markdown("---")

        # Council filter
        councils = sorted(df["Council"].dropna().unique().tolist())
        st.markdown("**Councils**")
        selected_councils = st.multiselect("", councils, default=[],
                                           placeholder="All councils",
                                           label_visibility="collapsed")

        st.markdown("---")

        # Keyword filter
        keywords = sorted(df["Keyword"].dropna().unique().tolist())
        st.markdown("**Keywords**")
        selected_keywords = st.multiselect("", keywords, default=[],
                                           placeholder="All keywords",
                                           label_visibility="collapsed")

        st.markdown("---")

        # Trigger word filter
        all_triggers = set()
        for t in df["Trigger Words"].dropna():
            for w in t.split(","):
                w = w.strip()
                if w: all_triggers.add(w)
        all_triggers = sorted(all_triggers)
        st.markdown("**Trigger Words**")
        selected_triggers = st.multiselect("", all_triggers, default=[],
                                           placeholder="Any trigger",
                                           label_visibility="collapsed")

        st.markdown("---")

        # Sort
        st.markdown("**Sort By**")
        sort_by = st.selectbox("", ["Score (high→low)", "Date Decided (newest)", "Council A→Z"],
                               label_visibility="collapsed")

        st.markdown("---")

        # View mode
        st.markdown("**View Mode**")
        view_mode = st.radio("", ["Cards", "Table"], horizontal=True,
                             label_visibility="collapsed")

        st.markdown("---")
        if st.button("🔄 Refresh data"):
            st.cache_data.clear()
            st.rerun()
        st.caption("Data refreshes every 5 min automatically")

    # ── APPLY FILTERS ────────────────────────────────────────
    filtered = df.copy()

    if date_from and date_to and not valid_dates.empty:
        dt_from = datetime.combine(date_from, datetime.min.time())
        dt_to   = datetime.combine(date_to,   datetime.max.time())
        filtered = filtered[
            filtered["_date_decided"].apply(
                lambda d: d is not None and dt_from <= d <= dt_to
            )
        ]

    filtered = filtered[filtered["Score"] >= min_score]

    if selected_councils:
        filtered = filtered[filtered["Council"].isin(selected_councils)]

    if selected_keywords:
        filtered = filtered[filtered["Keyword"].isin(selected_keywords)]

    if selected_triggers:
        def has_trigger(t):
            if not t: return False
            parts = [x.strip() for x in t.split(",")]
            return any(sel in parts for sel in selected_triggers)
        filtered = filtered[filtered["Trigger Words"].apply(has_trigger)]

    # Sort
    if sort_by == "Score (high→low)":
        filtered = filtered.sort_values("Score", ascending=False)
    elif sort_by == "Date Decided (newest)":
        filtered = filtered.sort_values("_date_decided", ascending=False, na_position="last")
    else:
        filtered = filtered.sort_values("Council")

    filtered = filtered.reset_index(drop=True)

    # ── METRICS ROW ──────────────────────────────────────────
    total_all    = len(df)
    total_shown  = len(filtered)
    avg_score    = int(filtered["Score"].mean()) if total_shown else 0
    top_councils = filtered["Council"].value_counts().head(3).index.tolist()
    top_str      = ", ".join(top_councils) if top_councils else "—"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Leads", total_all)
    c2.metric("Showing", total_shown, delta=f"{total_shown - total_all} vs total" if total_shown != total_all else None)
    c3.metric("Avg Score", f"{avg_score}/100")
    c4.metric("Top Councils", top_str)

    st.markdown("---")

    if total_shown == 0:
        st.info("No leads match your filters. Try widening the date range or lowering the score threshold.")
        return

    # ── CARD VIEW ────────────────────────────────────────────
    if view_mode == "Cards":
        st.markdown(f"**{total_shown} lead{'s' if total_shown != 1 else ''}**")

        for _, row in filtered.iterrows():
            triggers_html = "".join(
                f'<span class="triggers">{t.strip()}</span>'
                for t in str(row["Trigger Words"]).split(",") if t.strip()
            )
            portal_btn = (f'<a class="link-btn" href="{row["Portal Link"]}" target="_blank">🔗 Portal</a>'
                          if row.get("Portal Link") else "")
            doc_btn    = (f'<a class="link-btn" href="{row["Decision Doc URL"]}" target="_blank">📄 Decision PDF</a>'
                          if row.get("Decision Doc URL") else "")
            date_str = row["Date Decided"] or "—"
            addr_str = row["Address"][:80] + "..." if len(str(row["Address"])) > 80 else row["Address"]

            st.markdown(f"""
            <div class="lead-card">
              <div>
                <span class="council-tag">{row["Council"]}</span>
                <span class="ref">{row["Reference"]}</span>
                {score_badge(int(row["Score"]))}
              </div>
              <div class="desc">{row["Description"][:200]}</div>
              <div class="meta">
                📍 {addr_str}&nbsp;&nbsp;
                📅 Decided: {date_str}&nbsp;&nbsp;
                👤 {row["Applicant"] or "—"}
              </div>
              <div style="margin-top:0.5rem">{triggers_html}</div>
              <div>{portal_btn}{doc_btn}</div>
            </div>
            """, unsafe_allow_html=True)

            # Comment box (inline, collapsed by default)
            with st.expander(f"💬 Mark's comment — {row['Reference']}"):
                existing = str(row["Mark's Comments"]) if row.get("Mark's Comments") else ""
                new_comment = st.text_area("Comment", value=existing,
                                           key=f"comment_{row['Reference']}",
                                           label_visibility="collapsed",
                                           height=80)
                if st.button("Save", key=f"save_{row['Reference']}"):
                    if save_comment(row["Reference"], new_comment):
                        st.success("✅ Saved")

    # ── TABLE VIEW ───────────────────────────────────────────
    else:
        display_cols = ["Score", "Council", "Reference", "Address",
                        "Description", "Date Decided", "Trigger Words",
                        "Applicant", "Keyword", "Mark's Comments"]
        show_df = filtered[[c for c in display_cols if c in filtered.columns]].copy()

        # Truncate long text
        for col in ["Description", "Address", "Trigger Words"]:
            if col in show_df.columns:
                show_df[col] = show_df[col].apply(
                    lambda x: str(x)[:80] + "…" if len(str(x)) > 80 else x
                )

        st.dataframe(
            show_df,
            use_container_width=True,
            height=600,
            column_config={
                "Score": st.column_config.ProgressColumn(
                    "Score", min_value=0, max_value=100, format="%d"
                ),
                "Council": st.column_config.TextColumn("Council", width="small"),
                "Reference": st.column_config.TextColumn("Ref", width="medium"),
            },
            hide_index=True,
        )

        # CSV download
        csv = filtered.drop(columns=["_date_decided","_date_found"], errors="ignore").to_csv(index=False)
        st.download_button(
            "⬇️ Download CSV",
            csv,
            f"maplanning_leads_{datetime.now().strftime('%Y%m%d')}.csv",
            "text/csv",
        )

if __name__ == "__main__":
    main()
