import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import re
import time as _time

st.set_page_config(
    page_title="MAPlanning · Retail Leads",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── lightweight CSS — keeps it clean and readable ────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

/* score bars in table */
.score-bar-wrap { width: 100%; background: #e5e7eb; border-radius: 4px; height: 8px; }
.score-bar      { height: 8px; border-radius: 4px; }

/* priority badges */
.badge {
  display: inline-block; padding: 2px 10px; border-radius: 20px;
  font-size: 0.72rem; font-weight: 600; letter-spacing: 0.04em;
}
.badge-a { background:#dcfce7; color:#15803d; }
.badge-b { background:#fef9c3; color:#854d0e; }
.badge-c { background:#fee2e2; color:#b91c1c; }

/* trigger chips */
.chip {
  display: inline-block; background: #eff6ff; color: #1d4ed8;
  border: 1px solid #bfdbfe; border-radius: 20px;
  font-size: 0.68rem; padding: 1px 8px; margin: 2px 3px 0 0;
}

/* card tweaks */
div[data-testid="stExpander"] { border: none !important; }
div[data-testid="column"] { padding: 0 6px !important; }

/* metric labels */
[data-testid="metric-container"] label {
  font-size: 0.7rem !important; text-transform: uppercase;
  letter-spacing: 0.08em; color: #6b7280 !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
  font-family: 'JetBrains Mono', monospace;
  font-size: 2rem !important;
}

/* hide streamlit chrome */
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
header    { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── CONFIG ────────────────────────────────────────────────────
SHEET_ID   = "172bpv-b2_nK5ENE1XPk5rWeokvnr1sjHvLBfVzHWh6c"
SHEET_NAME = "Leads"
EXPECTED   = [
    "Council","Reference","Address","Description","App Type",
    "Applicant","Agent","Date Received","Date Decided","Decision",
    "Trigger Words","Score","Keyword","Portal Link","Decision Doc URL",
    "Date Found","Mark's Comments",
]

# ── SHEETS ────────────────────────────────────────────────────
@st.cache_resource(ttl=300)
def get_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.readonly",
        ],
    )
    return gspread.authorize(creds)

def _retry(fn, retries=5, base_delay=8):
    for attempt in range(retries):
        try:
            return fn()
        except Exception as e:
            msg = str(e)
            transient = any(c in msg for c in
                ["500","503","quota","rate","UNAVAILABLE","internal","temporarily"])
            if transient and attempt < retries - 1:
                _time.sleep(base_delay * (2 ** attempt))
            else:
                raise

@st.cache_data(ttl=300)
def load_data():
    try:
        ws   = _retry(lambda: get_client().open_by_key(SHEET_ID).worksheet(SHEET_NAME))
        rows = _retry(lambda: ws.get_all_values())
        if len(rows) < 2:
            return pd.DataFrame(columns=EXPECTED)

        # deduplicate header columns
        raw = rows[0]
        seen = {}
        headers = []
        for h in raw:
            h = h.strip()
            if h in seen:
                seen[h] += 1
                headers.append(f"__dup_{h}_{seen[h]}")
            else:
                seen[h] = 0
                headers.append(h)
        df = pd.DataFrame(rows[1:], columns=headers)
        df = df[[c for c in df.columns if not c.startswith("__dup_")]]
        for col in EXPECTED:
            if col not in df.columns:
                df[col] = ""

        df["Score"] = pd.to_numeric(df["Score"], errors="coerce").fillna(0).astype(int)

        def parse_date(s):
            for fmt in ["%d/%m/%Y","%Y-%m-%d","%d %b %Y",
                        "%a %d %b %Y","%d-%m-%Y","%B %d, %Y"]:
                try: return datetime.strptime(str(s).strip(), fmt)
                except: pass
            return None

        df["_date_decided"] = df["Date Decided"].apply(parse_date)
        df["_date_found"]   = pd.to_datetime(df["Date Found"], errors="coerce")
        return df
    except Exception as e:
        st.error(f"❌ Could not load data: {e}\n\nGoogle's API may be temporarily unavailable — wait 30s and click Refresh.")
        return pd.DataFrame(columns=EXPECTED)

def save_comment(ref, comment):
    try:
        ws   = _retry(lambda: get_client().open_by_key(SHEET_ID).worksheet(SHEET_NAME))
        refs = _retry(lambda: ws.col_values(2))
        if ref in refs:
            _retry(lambda: ws.update_cell(refs.index(ref)+1, 17, comment))
            st.cache_data.clear()
            return True
    except Exception as e:
        st.error(f"Save failed: {e}")
    return False

# ── HELPERS ───────────────────────────────────────────────────
def priority_label(score):
    if score >= 75: return "🟢 A — HIGH PRIORITY", "badge-a"
    if score >= 55: return "🟡 B — MEDIUM",        "badge-b"
    return              "🔴 C — LOW",               "badge-c"

def safe(v, fb="—"):
    s = str(v).strip() if v is not None else ""
    return s if s and s.lower() not in ("nan","none","") else fb

# ── MAIN ──────────────────────────────────────────────────────
def main():

    # ─── SIDEBAR ─────────────────────────────────────────────
    st.sidebar.title("🏗️ MAPlanning")
    st.sidebar.markdown("**Retail Lead Intelligence**")
    st.sidebar.markdown("---")

    df = load_data()
    if df.empty:
        st.sidebar.warning("No data yet — run the scraper first.")
        st.title("🏗️ Lead Scouting Engine")
        st.info("No leads found. Paste the Colab scraper script into a new Colab cell and run it first.")
        return

    valid_dates = df["_date_decided"].dropna()

    st.sidebar.subheader("⚙️ Search Settings")

    # Date range
    if not valid_dates.empty:
        mn, mx   = valid_dates.min().date(), valid_dates.max().date()
        dfrom    = max(mn, (datetime.now()-timedelta(weeks=12)).date())
        date_from = st.sidebar.date_input("From (Decision Date)", dfrom,
                                           min_value=mn, max_value=mx)
        date_to   = st.sidebar.date_input("To (Decision Date)", mx,
                                           min_value=mn, max_value=mx)
    else:
        date_from = date_to = None

    # Min score
    min_score = st.sidebar.slider("📊 Minimum score", 0, 100, 50, 5)

    # Councils
    all_councils = sorted(df["Council"].dropna().unique())
    sel_councils = st.sidebar.multiselect("🏛️ Councils", all_councils,
                                           default=[], placeholder="All councils")

    # Keywords
    all_kw = sorted(df["Keyword"].dropna().unique())
    sel_kw = st.sidebar.multiselect("🔎 Keyword matched", all_kw,
                                     default=[], placeholder="All keywords")

    # Trigger words
    all_trig = sorted({
        w.strip()
        for t in df["Trigger Words"].dropna()
        for w in str(t).split(",") if w.strip()
    })
    sel_trig = st.sidebar.multiselect("🎯 Trigger words", all_trig,
                                       default=[], placeholder="Any trigger")

    st.sidebar.markdown("---")
    st.sidebar.subheader("📋 View")
    sort_by   = st.sidebar.selectbox("Sort by",
                    ["Score (high → low)","Date Decided (newest)","Council A → Z"])
    view_mode = st.sidebar.radio("Layout", ["Cards","Table"], horizontal=True)

    st.sidebar.markdown("---")
    st.sidebar.info("🎯 Target: 6 leads / month\n💷 Avg fee: £2,000")
    if st.sidebar.button("↺ Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.sidebar.caption(f"Last loaded: {datetime.now().strftime('%H:%M')}")

    # ─── APPLY FILTERS ────────────────────────────────────────
    filt = df.copy()
    if date_from and date_to and not valid_dates.empty:
        d0 = datetime.combine(date_from, datetime.min.time())
        d1 = datetime.combine(date_to,   datetime.max.time())
        filt = filt[filt["_date_decided"].apply(
            lambda d: d is not None and d0 <= d <= d1)]
    filt = filt[filt["Score"] >= min_score]
    if sel_councils: filt = filt[filt["Council"].isin(sel_councils)]
    if sel_kw:       filt = filt[filt["Keyword"].isin(sel_kw)]
    if sel_trig:
        filt = filt[filt["Trigger Words"].apply(
            lambda t: any(s in [x.strip() for x in str(t).split(",")]
                         for s in sel_trig))]
    if sort_by == "Score (high → low)":
        filt = filt.sort_values("Score", ascending=False)
    elif sort_by == "Date Decided (newest)":
        filt = filt.sort_values("_date_decided", ascending=False, na_position="last")
    else:
        filt = filt.sort_values("Council")
    filt = filt.reset_index(drop=True)
    n = len(filt)

    # ─── HEADER ───────────────────────────────────────────────
    st.title("🏗️ Lead Scouting Engine")
    st.markdown("**Automated qualified lead generation for MAPlanning retail consultancy**")
    st.markdown("---")

    # ─── METRICS ──────────────────────────────────────────────
    high  = len(filt[filt["Score"] >= 75])
    med   = len(filt[(filt["Score"] >= 55) & (filt["Score"] < 75)])
    avg_s = int(filt["Score"].mean()) if n else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Leads",   n)
    c2.metric("🟢 A — High",  high)
    c3.metric("🟡 B — Medium", med)
    c4.metric("Avg Score",     f"{avg_s}/100")

    st.markdown("---")

    if n == 0:
        st.info("📭 No leads match your filters. Try widening the date range, lowering the score slider, or clearing council/keyword filters.")
        return

    st.markdown(f"**{n} lead{'s' if n!=1 else ''} found**")

    # ─── CARDS VIEW ───────────────────────────────────────────
    if view_mode == "Cards":
        for idx, row in filt.iterrows():
            sc          = int(row["Score"])
            plabel, bcls = priority_label(sc)
            council     = safe(row["Council"])
            ref         = safe(row["Reference"])
            desc        = safe(row["Description"])
            addr        = safe(row["Address"])
            applicant   = safe(row["Applicant"])
            agent       = safe(row["Agent"])
            dated       = safe(row["Date Decided"])
            atype       = safe(row["App Type"])
            portal      = safe(row.get("Portal Link"))
            doc         = safe(row.get("Decision Doc URL"))
            triggers    = [t.strip() for t in str(row["Trigger Words"]).split(",") if t.strip()]

            with st.container(border=True):
                # header row: number + priority + score
                h1, h2 = st.columns([5, 1])
                with h1:
                    st.markdown(
                        f"### {idx+1}. "
                        f'<span class="badge {bcls}">{plabel}</span>'
                        f"&nbsp; Score: **{sc}**",
                        unsafe_allow_html=True,
                    )
                with h2:
                    st.markdown(f"**{council}**")

                # details
                st.write(f"**Address:** {addr}")
                st.write(f"**Applicant:** {applicant}"
                         + (f"  |  **Agent:** {agent}" if agent != "—" else "")
                         + (f"  |  **Type:** {atype}" if atype != "—" else ""))
                st.write(f"**Description:** {desc[:250]}")
                st.caption(f"📅 Decision date: {dated}  |  🔑 Ref: {ref}")

                # trigger chips
                if triggers:
                    chips = "".join(f'<span class="chip">{t}</span>' for t in triggers)
                    st.markdown(f"**Triggers:** {chips}", unsafe_allow_html=True)

                # action buttons
                btn_cols = st.columns([1, 1, 2])
                if portal != "—":
                    btn_cols[0].link_button("📄 View Application", portal)
                if doc != "—":
                    btn_cols[1].link_button("📑 Decision PDF", doc)

                # comment expander
                with st.expander("💬 Add / edit comment"):
                    safe_key    = re.sub(r'[^a-zA-Z0-9]', '_', ref)
                    existing    = safe(row.get("Mark's Comments"), "")
                    new_comment = st.text_area(
                        "Notes", value=existing if existing != "—" else "",
                        key=f"ta_{safe_key}", height=80,
                        placeholder="Type your notes here…"
                    )
                    if st.button("Save comment", key=f"sv_{safe_key}"):
                        if save_comment(ref, new_comment):
                            st.success("✅ Saved")

    # ─── TABLE VIEW ───────────────────────────────────────────
    else:
        show_cols = ["Score","Council","Reference","Address","Description",
                     "Date Decided","Trigger Words","Applicant",
                     "App Type","Keyword","Mark's Comments"]
        tdf = filt[[c for c in show_cols if c in filt.columns]].copy()
        for col in ["Description","Address"]:
            if col in tdf.columns:
                tdf[col] = tdf[col].apply(
                    lambda x: str(x)[:100]+"…" if len(str(x))>100 else x)

        st.dataframe(
            tdf,
            use_container_width=True,
            height=640,
            column_config={
                "Score": st.column_config.ProgressColumn(
                    "Score", min_value=0, max_value=100, format="%d"),
                "Reference":   st.column_config.TextColumn("Ref", width="medium"),
                "Council":     st.column_config.TextColumn("Council", width="small"),
                "Description": st.column_config.TextColumn("Description", width="large"),
                "Address":     st.column_config.TextColumn("Address", width="large"),
            },
            hide_index=True,
        )

        # CSV export
        csv = filt.drop(columns=["_date_decided","_date_found"], errors="ignore").to_csv(index=False)
        st.download_button(
            "📥 Download CSV", csv,
            f"maplanning_leads_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            "text/csv",
        )

if __name__ == "__main__":
    main()
