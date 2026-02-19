import streamlit as st
import asyncio
import re
import time
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import gspread
from google.oauth2.service_account import Credentials

# ════════════════════════════════════════════════════════════
# PAGE CONFIG
# ════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="MAPlanning Lead Engine",
    page_icon="🏗️",
    layout="wide"
)

# ════════════════════════════════════════════════════════════
# COUNCILS — add more as you build scrapers for them
# ════════════════════════════════════════════════════════════
COUNCILS = {
    "Manchester": "https://pa.manchester.gov.uk/online-applications",
    # "Leeds":      "https://publicaccess.leeds.gov.uk/online-applications",
    # "Bristol":    "https://planningonline.bristol.gov.uk/online-applications",
    # Add more here as you build their scrapers
}

# ════════════════════════════════════════════════════════════
# FILTERS
# ════════════════════════════════════════════════════════════
EXCLUDE = [
    "conservatory","porch","rear extension","loft conversion",
    "replacement window","solar panel","fence","fencing",
    "signage","advertisement","tree preservation","tree works",
    "garage alteration","internal alteration","lawful development",
    "single storey rear","garden shed","satellite dish",
    "dropped kerb","bin store","bicycle store","prior approval",
    "permitted development","tpo","ev charger","householder",
    "listed building consent","discharge of condition",
    "non-material amendment","s73","section 73",
    "ancillary storage","outbuilding","storage building",
]
INCLUDE = [
    "residential development","mixed use","mixed-use",
    "commercial","industrial","warehouse","logistics",
    "student accommodation","build to rent","build-to-rent",
    "new build","residential units","apartments","dwellings",
    "regeneration","retail development","office","outline",
    "hybrid","supermarket","hotel","care home","extra care",
    "demolition and erection","major",
]

# ════════════════════════════════════════════════════════════
# SCORING
# ════════════════════════════════════════════════════════════
def score_lead(description, status, app_type):
    score = 0
    desc  = description.lower()
    stat  = status.lower()
    atype = app_type.lower()
    if any(k in desc for k in ["mixed use","mixed-use","regeneration"]):       score += 35
    if any(k in desc for k in ["residential","apartments","dwellings"]):       score += 20
    if any(k in desc for k in ["commercial","office","retail","supermarket"]): score += 25
    if any(k in desc for k in ["industrial","warehouse","logistics"]):         score += 25
    if any(k in desc for k in ["student","build to rent","hotel"]):            score += 30
    if any(k in desc for k in ["care home","extra care"]):                     score += 20
    units = re.findall(r'(\d+)\s*(?:dwelling|apartment|unit|flat|house|home|bed)', desc)
    if units:
        n = max(int(x) for x in units)
        if   n >= 100: score += 40
        elif n >= 50:  score += 30
        elif n >= 20:  score += 20
        elif n >= 5:   score += 10
        else:          score -= 15
    if any(k in stat for k in ["refused","refusal","dismissed"]): score += 45
    if "appeal"    in stat:                                        score += 40
    if any(k in stat for k in ["pending","submitted","validated"]): score += 20
    if "withdrawn" in stat:                                        score += 10
    if "major"     in atype:                                       score += 30
    if "outline"   in atype:                                       score += 20
    return score

def is_qualifying(description, score, min_score, refused_only):
    desc     = description.lower()
    is_noise = any(k in desc for k in EXCLUDE)
    has_sig  = any(k in desc for k in INCLUDE)
    if is_noise and not has_sig: return False
    if not has_sig and score < 20: return False
    if score < min_score: return False
    if refused_only and "refus" not in desc and "refused" not in desc: return False
    return True

# ════════════════════════════════════════════════════════════
# GOOGLE SHEETS
# ════════════════════════════════════════════════════════════
def write_to_sheets(leads):
    try:
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://spreadsheets.google.com/feeds",
                    "https://www.googleapis.com/auth/drive"]
        )
        gc = gspread.authorize(creds)
        ws = gc.open_by_key(st.secrets["gcp"]["sheet_id"]).worksheet("Leads")
        existing = ws.col_values(2)
        written = 0
        for lead in leads:
            if lead["reference"] in existing:
                continue
            ws.append_row([
                lead["council"], lead["reference"],
                lead["date_received"], lead["date_validated"],
                lead["address"], lead["applicant"], lead["agent"],
                lead["description"], lead["app_type"],
                lead["status"], lead["decision"],
                lead["score"], lead["url"],
                datetime.now().strftime("%Y-%m-%d %H:%M"),
            ])
            existing.append(lead["reference"])
            written += 1
            time.sleep(0.3)
        return written
    except Exception as e:
        st.warning(f"Sheets write error: {e}")
        return 0

# ════════════════════════════════════════════════════════════
# SCRAPER FUNCTIONS (same logic as your Colab script)
# ════════════════════════════════════════════════════════════
def parse_page(html):
    soup  = BeautifulSoup(html, "html.parser")
    items = []
    for r in soup.select("li.searchresult"):
        a = r.select_one("a")
        if not a: continue
        desc_el = r.select_one(".proposal") or r.select_one(".description") or r.select_one("p")
        addr_el = r.select_one(".address") or r.select_one(".addressCol")
        items.append({
            "ref":  a.get_text(strip=True),
            "href": a.get("href",""),
            "desc": desc_el.get_text(strip=True) if desc_el else "",
            "addr": addr_el.get_text(strip=True) if addr_el else "",
        })
    has_next = bool(
        soup.find("a", string=re.compile(r"Next", re.I)) or
        soup.find("a", href=re.compile(r"page="))
    )
    return items, has_next

async def get_details(page, detail_url, back_url):
    d = {}
    try:
        await page.goto(detail_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)
        soup = BeautifulSoup(await page.content(), "html.parser")
        for row in soup.select("tr"):
            th = row.find("th"); td = row.find("td")
            if not th or not td: continue
            label = th.get_text(strip=True).lower()
            value = td.get_text(strip=True)
            if "proposal"    in label:                                                        d["proposal"]       = value
            elif "address"   in label:                                                        d["address"]        = value
            elif "status"    in label:                                                        d["status"]         = value
            elif "received"  in label:                                                        d["date_received"]  = value
            elif "validated" in label:                                                        d["date_validated"] = value
            elif "decision"  in label and "level" not in label and "expected" not in label:  d["decision"]       = value
        further = detail_url.replace("activeTab=summary","activeTab=details")
        await page.goto(further, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(1.5)
        soup2 = BeautifulSoup(await page.content(), "html.parser")
        for row in soup2.select("tr"):
            th = row.find("th"); td = row.find("td")
            if not th or not td: continue
            label = th.get_text(strip=True).lower()
            value = td.get_text(strip=True)
            if "applicant name"   in label and not d.get("applicant"): d["applicant"] = value
            if "agent"            in label and not d.get("agent"):     d["agent"]     = value
            if "application type" in label and not d.get("app_type"): d["app_type"]  = value
    except Exception as e:
        pass
    try:
        await page.goto(back_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)
    except:
        pass
    return d

async def process_html_leads(page, html, label, week_text, back_url, min_score, refused_only, council_name):
    leads = []
    items, _ = parse_page(html)
    for item in items:
        qs = score_lead(item["desc"], label, "")
        q  = is_qualifying(item["desc"], qs, min_score, refused_only)
        if not q:
            continue
        href = item["href"]
        kv   = href.split("keyVal=")[-1].split("&")[0] if "keyVal=" in href else ""
        base = COUNCILS[council_name]
        det  = f"{base}/applicationDetails.do?activeTab=summary&keyVal={kv}" if kv else f"{base}/{href.lstrip('/')}"
        await asyncio.sleep(2)
        details     = await get_details(page, det, back_url)
        fd          = details.get("proposal",  item["desc"])
        fs          = details.get("status",    label)
        ft          = details.get("app_type",  "")
        final_score = score_lead(fd, fs, ft)
        if not is_qualifying(fd, final_score, min_score, refused_only):
            continue
        leads.append({
            "council": council_name, "reference": item["ref"],
            "date_received": details.get("date_received",""),
            "date_validated": details.get("date_validated", week_text),
            "address": details.get("address", item["addr"]),
            "applicant": details.get("applicant",""), "agent": details.get("agent",""),
            "description": fd, "app_type": ft, "status": fs,
            "decision": details.get("decision",""), "score": final_score, "url": det,
        })
    return leads

async def scrape_council(council_name, weeks_back, min_score, refused_only, status_container):
    base_url = COUNCILS[council_name]
    all_leads = []

    async with async_playwright() as p:
        # Get week list
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox","--disable-setuid-sandbox","--disable-dev-shm-usage"]
        )
        tmp = await browser.new_page()
        await tmp.goto(f"{base_url}/search.do?action=weeklyList",
                       wait_until="networkidle", timeout=60000)
        await asyncio.sleep(2)
        weeks = await tmp.eval_on_selector(
            'select[name="week"]',
            'el => Array.from(el.options).map(o=>({value:o.value,text:o.text.trim()}))'
        )
        weeks = [w for w in weeks if w["value"].strip()][:weeks_back]
        await browser.close()

        for i, week in enumerate(weeks):
            status_container.info(f"🔍 {council_name} — Week {i+1}/{len(weeks)}: {week['text']}")

            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox","--disable-setuid-sandbox",
                      "--disable-dev-shm-usage",
                      "--disable-blink-features=AutomationControlled"]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()
            await page.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            # Validated
            try:
                await page.goto(f"{base_url}/search.do?action=weeklyList",
                                wait_until="networkidle", timeout=60000)
                await asyncio.sleep(3)
                await page.check('input[name="dateType"][value="DC_Validated"]')
                await asyncio.sleep(0.5)
                await page.select_option('select[name="week"]', value=week["value"])
                await asyncio.sleep(1)
                await page.click('input[type="submit"][value="Search"]')
                landed = False
                for _ in range(30):
                    await asyncio.sleep(1)
                    if "weeklyListResults" in page.url or "pagedSearchResults" in page.url:
                        landed = True; break
                if landed:
                    page_num = 1
                    while True:
                        await page.wait_for_load_state("networkidle")
                        html = await page.content()
                        items_on_page, has_next = parse_page(html)
                        if not items_on_page: break
                        back_url = page.url
                        batch = await process_html_leads(page, html, "Validated", week["text"], back_url, min_score, refused_only, council_name)
                        all_leads.extend(batch)
                        if not has_next: break
                        page_num += 1
                        await page.goto(f"{base_url}/pagedSearchResults.do?action=page&searchCriteria.page={page_num}", wait_until="networkidle", timeout=30000)
                        await asyncio.sleep(2)
            except Exception as e:
                status_container.warning(f"Validated error: {e}")

            # Decided via browser fetch()
            try:
                await page.goto(f"{base_url}/search.do?action=weeklyList",
                                wait_until="networkidle", timeout=30000)
                await asyncio.sleep(2)
                csrf = await page.eval_on_selector('input[name="_csrf"]', 'el => el.value')
                week_val = week["value"].replace("'", "\\'")
                decided_html = await page.evaluate(f"""
                    async () => {{
                        const params = new URLSearchParams();
                        params.append('_csrf', '{csrf}');
                        params.append('dateType', 'DC_Decided');
                        params.append('week', '{week_val}');
                        params.append('searchType', 'Application');
                        const resp = await fetch('{base_url}/weeklyListResults.do?action=firstPage', {{
                            method: 'POST',
                            headers: {{'Content-Type': 'application/x-www-form-urlencoded',
                                      'Referer': '{base_url}/search.do?action=weeklyList'}},
                            body: params.toString(),
                            credentials: 'include'
                        }});
                        return await resp.text();
                    }}
                """)
                if decided_html and "searchresult" in decided_html.lower():
                    results_url = f"{base_url}/weeklyListResults.do?action=firstPage"
                    batch = await process_html_leads(page, decided_html, "Decided", week["text"], results_url, min_score, refused_only, council_name)
                    all_leads.extend(batch)
                    _, has_next = parse_page(decided_html)
                    pnum = 2
                    while has_next:
                        next_url = f"{base_url}/pagedSearchResults.do?action=page&searchCriteria.page={pnum}"
                        next_html = await page.evaluate(f"""
                            async () => {{
                                const resp = await fetch('{next_url}', {{credentials: 'include'}});
                                return await resp.text();
                            }}
                        """)
                        if not next_html or "searchresult" not in next_html.lower(): break
                        more = await process_html_leads(page, next_html, "Decided", week["text"], next_url, min_score, refused_only, council_name)
                        all_leads.extend(more)
                        _, has_next = parse_page(next_html)
                        pnum += 1
                        await asyncio.sleep(2)
            except Exception as e:
                status_container.warning(f"Decided error: {e}")

            await browser.close()
            await asyncio.sleep(5)

    return all_leads

# ════════════════════════════════════════════════════════════
# UI
# ════════════════════════════════════════════════════════════
st.title("🏗️ MAPlanning Lead Engine")
st.caption("Automated qualified lead generation for Urban Planning consultancy")
st.divider()

# Sidebar
with st.sidebar:
    st.header("⚙️ Search Settings")

    selected_councils = st.multiselect(
        "Active councils:",
        options=list(COUNCILS.keys()),
        default=list(COUNCILS.keys()),
    )

    unavailable = ["Leeds","Bristol","Birmingham","Cardiff","Liverpool","Sheffield"]
    with st.expander("❌ Unavailable Councils (coming soon)"):
        for c in unavailable:
            st.caption(f"• {c}")

    weeks_back = st.slider("Weeks to look back:", 1, 12, 4)
    min_score  = st.slider("Minimum score:", 1, 80, 20)
    refused_only = st.checkbox("🚫 Refused applications only", value=False)

    avg_fee = 2000
    target  = len(selected_councils) * weeks_back * 2
    st.info(f"**Target: ~{target} leads/month**\nAvg Fee: £{avg_fee:,}")

    search_btn = st.button("🔍 Search for Leads", type="primary", use_container_width=True)

# Main area
if search_btn:
    if not selected_councils:
        st.error("Select at least one council.")
        st.stop()

    status_box  = st.empty()
    progress    = st.progress(0)
    all_results = []

    for idx, council in enumerate(selected_councils):
        status_box.info(f"🔍 Scraping {council}...")
        progress.progress((idx) / len(selected_councils))

        try:
            loop    = asyncio.new_event_loop()
            leads   = loop.run_until_complete(
                scrape_council(council, weeks_back, min_score, refused_only, status_box)
            )
            loop.close()
            all_results.extend(leads)
        except Exception as e:
            st.error(f"Error scraping {council}: {e}")

    progress.progress(1.0)
    all_results.sort(key=lambda x: x["score"], reverse=True)

    # Write to Sheets
    try:
        written = write_to_sheets(all_results)
        status_box.success(f"✅ Done — {len(all_results)} leads found, {written} new rows added to Google Sheets")
    except:
        status_box.success(f"✅ Done — {len(all_results)} leads found")

    # Display metrics
    high   = [l for l in all_results if l["score"] >= 60]
    medium = [l for l in all_results if 30 <= l["score"] < 60]
    avg_s  = round(sum(l["score"] for l in all_results) / len(all_results), 1) if all_results else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Leads",  len(all_results))
    c2.metric("A-Priority",   len(high))
    c3.metric("B-Priority",   len(medium))
    c4.metric("Avg Score",    avg_s)

    st.divider()

    # Lead cards
    for i, lead in enumerate(all_results):
        score = lead["score"]
        if score >= 60:
            badge = "🟢 A — HIGH PRIORITY"
            color = "#d4edda"
        elif score >= 30:
            badge = "🟡 B — MEDIUM PRIORITY"
            color = "#fff3cd"
        else:
            badge = "⚪ C — LOW PRIORITY"
            color = "#f8f9fa"

        with st.container():
            st.markdown(f"""
            <div style="background:{color};padding:16px;border-radius:8px;margin-bottom:12px;border-left:4px solid {'#28a745' if score>=60 else '#ffc107' if score>=30 else '#6c757d'}">
                <h4>{i+1}. {badge} (Score: {score})</h4>
                <p><b>Address:</b> {lead['address']} &nbsp;|&nbsp; <b>Council:</b> {lead['council']}</p>
                <p><b>Applicant:</b> {lead['applicant'] or '—'} &nbsp;|&nbsp; <b>Agent:</b> {lead['agent'] or '—'}</p>
                <p><b>Status:</b> {lead['status']} &nbsp;|&nbsp; <b>Type:</b> {lead['app_type'] or '—'}</p>
                <p><b>Description:</b> {lead['description'][:200]}{'...' if len(lead['description'])>200 else ''}</p>
                <p><b>Ref:</b> {lead['reference']} &nbsp;|&nbsp; <b>Validated:</b> {lead['date_validated']}</p>
            </div>
            """, unsafe_allow_html=True)

            col1, col2 = st.columns([1, 4])
            with col1:
                st.link_button("🔗 View Application", lead["url"])

else:
    st.info("👈 Configure your search settings and click **Search for Leads** to begin.")
    st.markdown("""
    **How it works:**
    - Select which councils to monitor
    - Set how many weeks back to search
    - Set minimum lead score threshold
    - Optionally filter to refused applications only (appeal opportunities for Mark)
    - Results are automatically saved to Google Sheets
    """)
```

---

## Deploying It — Step by Step

**Step 1:** Go to `github.com` → New repo → `maplanning-leads` → Public

**Step 2:** Create `requirements.txt` in the repo with:
```
playwright==1.41.0
beautifulsoup4
gspread
google-auth
streamlit
