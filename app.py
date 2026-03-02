import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import re

st.set_page_config(
    page_title="MAPlanning · Retail Leads",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

*, *::before, *::after { box-sizing: border-box; }
html, body, [class*="css"], .stApp {
  font-family: 'Inter', sans-serif !important;
  background: #09090b !important;
  color: #fafafa;
}

/* ── sidebar ── */
section[data-testid="stSidebar"] {
  background: #0f0f10 !important;
  border-right: 1px solid rgba(255,255,255,0.06) !important;
}
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] .stMarkdown span,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] .stCaption,
section[data-testid="stSidebar"] small { color: #71717a !important; }

.sidebar-brand {
  padding: 22px 20px 16px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  margin-bottom: 8px;
}
.sidebar-brand h2 {
  font-size: 1rem; font-weight: 700; letter-spacing: -0.02em;
  color: #fff !important; margin: 0 0 3px;
}
.sidebar-brand p { font-size: 0.72rem; color: #52525b !important; margin: 0; }

.flabel {
  font-size: 0.66rem; font-weight: 600; letter-spacing: 0.09em;
  text-transform: uppercase; color: #52525b; margin: 16px 0 6px;
  display: block;
}

/* ── main ── */
.main .block-container {
  max-width: 1360px;
  padding: 28px 36px 80px !important;
  background: transparent;
}

/* ── top ── */
.top-row {
  display: flex; align-items: flex-start;
  justify-content: space-between;
  padding-bottom: 22px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  margin-bottom: 24px;
}
.top-row h1 {
  font-size: 1.45rem; font-weight: 700; letter-spacing: -0.025em;
  color: #fff; margin: 0 0 5px;
}
.top-row p { font-size: 0.78rem; color: #52525b; margin: 0; }
.live-badge {
  display: inline-flex; align-items: center; gap: 7px;
  background: #18181b; border: 1px solid rgba(255,255,255,0.07);
  border-radius: 8px; padding: 7px 14px;
  font-size: 0.75rem; color: #71717a; white-space: nowrap;
}
.dot {
  width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0;
  background: #22c55e; box-shadow: 0 0 7px #22c55e;
  animation: blink 2s ease infinite;
}
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.3} }

/* ── stat cards ── */
.stats {
  display: grid; grid-template-columns: repeat(4,1fr);
  gap: 12px; margin-bottom: 26px;
}
.scard {
  background: #18181b;
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 12px; padding: 16px 18px;
}
.scard .slabel {
  font-size: 0.66rem; font-weight: 600; letter-spacing: 0.09em;
  text-transform: uppercase; color: #52525b; margin-bottom: 8px;
}
.scard .sval {
  font-family: 'JetBrains Mono', monospace;
  font-size: 1.9rem; font-weight: 700; color: #fff; line-height: 1;
}
.scard .ssub { font-size: 0.71rem; color: #52525b; margin-top: 5px; }
.scard.purple { border-color: rgba(139,92,246,0.25); }
.scard.purple .sval { color: #a78bfa; }
.scard.green  { border-color: rgba(34,197,94,0.2); }
.scard.green  .sval { color: #4ade80; }

/* ── filter pill bar ── */
.pill-bar {
  display: flex; flex-wrap: wrap; align-items: center; gap: 7px;
  padding: 10px 14px;
  background: #18181b;
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 10px;
  margin-bottom: 20px;
  font-size: 0.74rem; color: #52525b;
}
.pill-bar .pill-label { color: #3f3f46; font-size: 0.68rem; margin-right: 4px; }
.pill {
  background: #27272a; border: 1px solid rgba(255,255,255,0.08);
  color: #a1a1aa; padding: 2px 10px; border-radius: 20px; font-size: 0.72rem;
}

/* ── lead cards ── */
.leads-wrap { display: flex; flex-direction: column; gap: 10px; }

.lcard {
  position: relative;
  background: #18181b;
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 14px;
  padding: 18px 22px 14px 26px;
  overflow: hidden;
  transition: border-color .15s, background .15s;
}
.lcard:hover { border-color: rgba(255,255,255,0.12); background: #1c1c1f; }
.lcard::before {
  content: '';
  position: absolute; top: 0; left: 0;
  width: 4px; height: 100%; border-radius: 14px 0 0 14px;
}
.lcard.hi::before { background: linear-gradient(180deg,#22c55e,#15803d); }
.lcard.md::before { background: linear-gradient(180deg,#f59e0b,#b45309); }
.lcard.lo::before { background: linear-gradient(180deg,#ef4444,#b91c1c); }

.lcard-top {
  display: flex; align-items: center; gap: 9px; flex-wrap: wrap;
  margin-bottom: 10px;
}
.cpill {
  background: rgba(99,102,241,0.1);
  border: 1px solid rgba(99,102,241,0.22);
  color: #818cf8;
  font-size: 0.63rem; font-weight: 700; letter-spacing: .08em;
  text-transform: uppercase; padding: 2px 8px; border-radius: 20px;
}
.rcode {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.76rem; color: #52525b;
}
.schip {
  margin-left: auto;
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.78rem; font-weight: 600;
  padding: 3px 11px; border-radius: 20px;
}
.schip.hi { background:rgba(34,197,94,.1);  color:#4ade80; border:1px solid rgba(34,197,94,.22); }
.schip.md { background:rgba(245,158,11,.1); color:#fbbf24; border:1px solid rgba(245,158,11,.22); }
.schip.lo { background:rgba(239,68,68,.1);  color:#f87171; border:1px solid rgba(239,68,68,.22); }

.ldesc {
  font-size: 0.9rem; font-weight: 500; color: #e4e4e7;
  line-height: 1.55; margin-bottom: 9px;
}
.lmeta {
  display: flex; flex-wrap: wrap; gap: 14px;
  font-size: 0.74rem; color: #52525b;
  margin-bottom: 10px;
}
.lmeta span { display: flex; align-items: center; gap: 4px; }

.tchips { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 12px; }
.tchip {
  background: rgba(59,130,246,.09);
  border: 1px solid rgba(59,130,246,.2);
  color: #60a5fa;
  font-size: 0.66rem; font-weight: 500;
  padding: 2px 8px; border-radius: 20px;
}

.lactions { display: flex; gap: 7px; }
.abtn {
  display: inline-flex; align-items: center; gap: 5px;
  background: #09090b;
  border: 1px solid rgba(255,255,255,0.07);
  color: #a1a1aa; font-size: 0.72rem; font-weight: 500;
  padding: 5px 12px; border-radius: 7px;
  text-decoration: none; transition: all .15s;
}
.abtn:hover { border-color: rgba(255,255,255,.18); color: #fff; background: #18181b; }

/* ── empty ── */
.empty {
  text-align: center; padding: 80px 0;
  color: #3f3f46;
}
.empty .eicon { font-size: 2.5rem; margin-bottom: 10px; }
.empty h3 { color: #52525b; font-size: .95rem; margin: 0 0 6px; }
.empty p { font-size: .8rem; }

/* ── misc ── */
hr { border-color: rgba(255,255,255,0.06) !important; }
#MainMenu, footer, header { visibility: hidden; }
div[data-testid="stExpander"] details summary {
  font-size: 0.74rem !important; color: #52525b !important;
}
</style>
""", unsafe_allow_html=True)

# ── CONFIG ───────────────────────────────────────────────────
SHEET_ID   = "172bpv-b2_nK5ENE1XPk5rWeokvnr1sjHvLBfVzHWh6c"
SHEET_NAME = "Leads"
EXPECTED   = [
    "Council","Reference","Address","Description","App Type",
    "Applicant","Agent","Date Received","Date Decided","Decision",
    "Trigger Words","Score","Keyword","Portal Link","Decision Doc URL",
    "Date Found","Mark's Comments",
]

# ── DATA ─────────────────────────────────────────────────────
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

@st.cache_data(ttl=300)
def load_data():
    try:
        ws   = get_client().open_by_key(SHEET_ID).worksheet(SHEET_NAME)
        rows = ws.get_all_values()
        if len(rows) < 2:
            return pd.DataFrame(columns=EXPECTED)

        # ── DEDUPLICATE COLUMN NAMES (fixes the ValueError) ──
        raw = rows[0]
        seen = {}
        headers = []
        for h in raw:
            h = h.strip()
            if h in seen:
                seen[h] += 1
                headers.append(f"__dup_{h}_{seen[h]}")   # rename duplicates
            else:
                seen[h] = 0
                headers.append(h)

        df = pd.DataFrame(rows[1:], columns=headers)

        # Drop renamed duplicate columns — keep only first occurrence
        df = df[[c for c in df.columns if not c.startswith("__dup_")]]

        # Ensure all expected columns present
        for col in EXPECTED:
            if col not in df.columns:
                df[col] = ""

        df["Score"] = pd.to_numeric(df["Score"], errors="coerce").fillna(0).astype(int)

        def parse_date(s):
            for fmt in ["%d/%m/%Y","%Y-%m-%d","%d %b %Y","%a %d %b %Y","%d-%m-%Y","%B %d, %Y"]:
                try: return datetime.strptime(str(s).strip(), fmt)
                except: pass
            return None

        df["_date_decided"] = df["Date Decided"].apply(parse_date)
        df["_date_found"]   = pd.to_datetime(df["Date Found"], errors="coerce")
        return df

    except Exception as e:
        st.error(f"❌ Could not load data: {e}")
        return pd.DataFrame(columns=EXPECTED)

def save_comment(ref, comment):
    try:
        ws   = get_client().open_by_key(SHEET_ID).worksheet(SHEET_NAME)
        refs = ws.col_values(2)
        if ref in refs:
            ws.update_cell(refs.index(ref) + 1, 17, comment)
            st.cache_data.clear()
            return True
    except Exception as e:
        st.error(f"Save failed: {e}")
    return False

# ── HELPERS ──────────────────────────────────────────────────
def cls(score):
    return "hi" if score >= 75 else "md" if score >= 55 else "lo"

def safe(v, fb="—"):
    s = str(v).strip() if v is not None else ""
    return s if s and s.lower() not in ("nan","none","") else fb

# ── MAIN ─────────────────────────────────────────────────────
def main():

    # ── SIDEBAR ──────────────────────────────────────────────
    with st.sidebar:
        st.markdown("""
        <div class="sidebar-brand">
          <h2>🏗️ MAPlanning</h2>
          <p>Retail Lead Intelligence</p>
        </div>
        """, unsafe_allow_html=True)

        df = load_data()
        if df.empty:
            st.warning("No data yet — run the scraper first.")
            return

        valid_dates = df["_date_decided"].dropna()

        # Date
        st.markdown('<span class="flabel">Decision Date</span>', unsafe_allow_html=True)
        if not valid_dates.empty:
            mn, mx = valid_dates.min().date(), valid_dates.max().date()
            dfrom  = max(mn, (datetime.now()-timedelta(weeks=12)).date())
            c1, c2 = st.columns(2)
            date_from = c1.date_input("f", dfrom, min_value=mn, max_value=mx,
                                       label_visibility="collapsed")
            date_to   = c2.date_input("t", mx,    min_value=mn, max_value=mx,
                                       label_visibility="collapsed")
            st.caption(f"{date_from.strftime('%d %b %Y')} → {date_to.strftime('%d %b %Y')}")
        else:
            date_from = date_to = None

        # Score
        st.markdown('<span class="flabel">Minimum Score</span>', unsafe_allow_html=True)
        min_score = st.slider("s", 0, 100, 50, 5, label_visibility="collapsed")

        # Councils
        st.markdown('<span class="flabel">Council</span>', unsafe_allow_html=True)
        all_councils = sorted(df["Council"].dropna().unique())
        sel_councils = st.multiselect("c", all_councils, default=[],
                                       placeholder="All councils",
                                       label_visibility="collapsed")

        # Keywords
        st.markdown('<span class="flabel">Keyword</span>', unsafe_allow_html=True)
        all_kw = sorted(df["Keyword"].dropna().unique())
        sel_kw = st.multiselect("k", all_kw, default=[],
                                 placeholder="All keywords",
                                 label_visibility="collapsed")

        # Triggers
        st.markdown('<span class="flabel">Trigger Words</span>', unsafe_allow_html=True)
        all_trig = sorted({
            w.strip()
            for t in df["Trigger Words"].dropna()
            for w in str(t).split(",")
            if w.strip()
        })
        sel_trig = st.multiselect("tr", all_trig, default=[],
                                   placeholder="Any trigger",
                                   label_visibility="collapsed")

        # Sort + view
        st.markdown('<span class="flabel">Sort By</span>', unsafe_allow_html=True)
        sort_by = st.selectbox("so", ["Score ↓","Date Decided (newest)","Council A→Z"],
                                label_visibility="collapsed")

        st.markdown('<span class="flabel">View</span>', unsafe_allow_html=True)
        view = st.radio("v", ["Cards","Table"], horizontal=True,
                         label_visibility="collapsed")

        st.markdown("---")
        if st.button("↺  Refresh data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        st.caption("Auto-refreshes every 5 min")

    # ── APPLY FILTERS ────────────────────────────────────────
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

    if sort_by == "Score ↓":
        filt = filt.sort_values("Score", ascending=False)
    elif sort_by == "Date Decided (newest)":
        filt = filt.sort_values("_date_decided", ascending=False, na_position="last")
    else:
        filt = filt.sort_values("Council")

    filt = filt.reset_index(drop=True)
    n = len(filt)

    # ── TOP BAR ──────────────────────────────────────────────
    st.markdown(f"""
    <div class="top-row">
      <div>
        <h1>Retail Lead Intelligence</h1>
        <p>Refused applications with sequential test &amp; retail impact grounds · UK-wide</p>
      </div>
      <div class="live-badge">
        <span class="dot"></span> Live · {datetime.now().strftime('%H:%M')}
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── STATS ────────────────────────────────────────────────
    total     = len(df)
    avg_score = int(filt["Score"].mean()) if n else 0
    high_n    = len(filt[filt["Score"] >= 75])
    top_c     = filt["Council"].value_counts().index[0] if n else "—"

    st.markdown(f"""
    <div class="stats">
      <div class="scard">
        <div class="slabel">Showing</div>
        <div class="sval">{n}</div>
        <div class="ssub">of {total} total leads</div>
      </div>
      <div class="scard purple">
        <div class="slabel">Avg Score</div>
        <div class="sval">{avg_score}</div>
        <div class="ssub">out of 100</div>
      </div>
      <div class="scard green">
        <div class="slabel">High Priority</div>
        <div class="sval">{high_n}</div>
        <div class="ssub">score ≥ 75</div>
      </div>
      <div class="scard">
        <div class="slabel">Top Council</div>
        <div class="sval" style="font-size:1.05rem;margin-top:6px;line-height:1.2">{top_c}</div>
        <div class="ssub">most leads</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── ACTIVE FILTER PILLS ──────────────────────────────────
    pills = []
    if date_from and date_to:
        pills.append(f"📅 {date_from.strftime('%d %b')} → {date_to.strftime('%d %b %Y')}")
    if min_score > 0:    pills.append(f"⭐ Score ≥ {min_score}")
    if sel_councils:     pills.append(f"🏛️ {', '.join(sel_councils)}")
    if sel_kw:           pills.append(f"🔎 {', '.join(sel_kw)}")
    if sel_trig:         pills.append(f"🎯 {', '.join(sel_trig)}")

    if pills:
        pills_html = "".join(f'<span class="pill">{p}</span>' for p in pills)
        st.markdown(
            f'<div class="pill-bar"><span class="pill-label">FILTERS</span>{pills_html}</div>',
            unsafe_allow_html=True)

    if n == 0:
        st.markdown("""
        <div class="empty">
          <div class="eicon">🔍</div>
          <h3>No leads match your filters</h3>
          <p>Try widening the date range, lowering the score, or clearing filters.</p>
        </div>""", unsafe_allow_html=True)
        return

    # ── CARDS VIEW ───────────────────────────────────────────
    if view == "Cards":
        st.markdown(f"<p style='font-size:.78rem;color:#52525b;margin-bottom:14px'>"
                    f"{n} lead{'s' if n!=1 else ''}</p>", unsafe_allow_html=True)

        for _, row in filt.iterrows():
            sc = int(row["Score"])
            c  = cls(sc)

            tchips = "".join(
                f'<span class="tchip">{t.strip()}</span>'
                for t in str(row["Trigger Words"]).split(",") if t.strip()
            )
            portal = safe(row.get("Portal Link"))
            doc    = safe(row.get("Decision Doc URL"))
            pbtn   = f'<a class="abtn" href="{portal}" target="_blank">🔗 Portal</a>' if portal != "—" else ""
            dbtn   = f'<a class="abtn" href="{doc}"    target="_blank">📄 Decision PDF</a>' if doc != "—" else ""

            addr  = safe(row["Address"])
            addr  = addr[:95]+"…" if len(addr)>95 else addr
            desc  = safe(row["Description"])
            appl  = safe(row["Applicant"])
            agent = safe(row["Agent"])
            dated = safe(row["Date Decided"])
            atype = safe(row["App Type"])

            agent_html = f'<span>🏢 {agent}</span>' if agent != "—" else ""
            type_html  = f'<span>📌 {atype}</span>'  if atype != "—" else ""

            st.markdown(f"""
            <div class="lcard {c}">
              <div class="lcard-top">
                <span class="cpill">{safe(row['Council'])}</span>
                <span class="rcode">{safe(row['Reference'])}</span>
                <span class="schip {c}">{sc}</span>
              </div>
              <div class="ldesc">{desc[:220]}</div>
              <div class="lmeta">
                <span>📍 {addr}</span>
                <span>📅 {dated}</span>
                <span>👤 {appl}</span>
                {agent_html}{type_html}
              </div>
              <div class="tchips">{tchips}</div>
              <div class="lactions">{pbtn}{dbtn}</div>
            </div>
            """, unsafe_allow_html=True)

            safe_key = re.sub(r'[^a-zA-Z0-9]', '_', str(row["Reference"]))
            with st.expander(f"💬 Comment — {safe(row['Reference'])}"):
                existing = safe(row.get("Mark's Comments"), "")
                new_val  = st.text_area("note", value=existing if existing != "—" else "",
                                         key=f"ta_{safe_key}",
                                         label_visibility="collapsed",
                                         placeholder="Type your notes…", height=80)
                if st.button("Save", key=f"sv_{safe_key}"):
                    if save_comment(row["Reference"], new_val):
                        st.success("✅ Saved")

    # ── TABLE VIEW ───────────────────────────────────────────
    else:
        show_cols = ["Score","Council","Reference","Address","Description",
                     "Date Decided","Trigger Words","Applicant","Agent",
                     "App Type","Keyword","Mark's Comments"]
        tdf = filt[[c for c in show_cols if c in filt.columns]].copy()
        for col in ["Description","Address"]:
            if col in tdf.columns:
                tdf[col] = tdf[col].apply(lambda x: str(x)[:95]+"…" if len(str(x))>95 else x)

        st.dataframe(
            tdf,
            use_container_width=True,
            height=640,
            column_config={
                "Score": st.column_config.ProgressColumn(
                    "Score", min_value=0, max_value=100, format="%d"),
                "Reference":   st.column_config.TextColumn("Ref",     width="medium"),
                "Council":     st.column_config.TextColumn("Council", width="small"),
                "Description": st.column_config.TextColumn("Description", width="large"),
                "Address":     st.column_config.TextColumn("Address",     width="large"),
            },
            hide_index=True,
        )

        csv = filt.drop(columns=["_date_decided","_date_found"], errors="ignore").to_csv(index=False)
        st.download_button(
            "⬇️ Export CSV", csv,
            f"maplanning_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            "text/csv")

if __name__ == "__main__":
    main()
