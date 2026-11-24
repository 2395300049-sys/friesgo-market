#!/usr/bin/env python3
"""
FriesGo Global - Daily Global Industrial Opportunity Radar Fetcher
Runs via GitHub Actions (daily 08:00 Beijing time / 00:00 UTC) or locally.
Zero third-party dependencies (Python 3 standard library only).

Sources:
  1. GDACS Official RSS (Global Tropical Cyclones / Floods / Earthquakes / Droughts)
  2. World Bank Official Projects API v2 (Newly approved global infrastructure/industrial/energy/water/agri/mining loans)
  3. Global Project Financing, EIA/New Factory & Chinese EPC News RSS

Optional Environment Variables (GitHub Secrets):
  - GEMINI_API_KEY       : Free Google AI Studio key for Chinese summaries & B2B angle extraction
  - WXPUSHER_APP_TOKEN   : WxPusher app token for personal WeChat morning brief
  - WXPUSHER_TOPIC_ID    : WxPusher topic ID (all colleagues who scan QR receive brief)
  - PUSHPLUS_TOKEN       : PushPlus token (alternative personal WeChat push)
  - PUSHPLUS_TOPIC       : Optional PushPlus group topic code
  - WECOM_WEBHOOK        : WeCom (企业微信) group bot webhook URL
  - FEISHU_WEBHOOK       : Feishu (飞书) group bot webhook URL
  - DINGTALK_WEBHOOK     : DingTalk (钉钉) group bot webhook URL
"""

import datetime
import html as html_lib
import json
import os
import re
import ssl
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")
JSON_OUT = os.path.join(DATA_DIR, "radar_feed.json")
JS_OUT = os.path.join(DATA_DIR, "radar_feed.js")
SITE_URL = "https://jasunmr389-ship-it.github.io/friesgo-market/#tab=radar"

USER_AGENT = "Mozilla/5.0 (compatible; FriesGoRadarBot/2.0; +https://jasunmr389-ship-it.github.io/friesgo-market/)"

# Country Chinese names & region mapping for global high-potential & emerging markets
COUNTRY_INFO = {
    "Vietnam": ("越南", "东南亚", "vi"),
    "Viet Nam": ("越南", "东南亚", "vi"),
    "Indonesia": ("印尼", "东南亚", "id"),
    "Thailand": ("泰国", "东南亚", "th"),
    "Philippines": ("菲律宾", "东南亚", "en"),
    "Malaysia": ("马来西亚", "东南亚", "en"),
    "Cambodia": ("柬埔寨", "东南亚", "en"),
    "Myanmar": ("缅甸", "东南亚", "en"),
    "Lao": ("老挝", "东南亚", "en"),
    "Singapore": ("新加坡", "东南亚", "en"),
    "India": ("印度", "南亚", "en"),
    "Bangladesh": ("孟加拉国", "南亚", "en"),
    "Pakistan": ("巴基斯坦", "南亚", "en"),
    "Sri Lanka": ("斯里兰卡", "南亚", "en"),
    "Nepal": ("尼泊尔", "南亚", "en"),
    "Saudi Arabia": ("沙特阿拉伯", "中东", "ar"),
    "United Arab Emirates": ("阿联酋", "中东", "en"),
    "UAE": ("阿联酋", "中东", "en"),
    "Egypt": ("埃及", "中东/北非", "ar"),
    "Iraq": ("伊拉克", "中东", "ar"),
    "Oman": ("阿曼", "中东", "ar"),
    "Qatar": ("卡塔尔", "中东", "ar"),
    "Kuwait": ("科威特", "中东", "ar"),
    "Jordan": ("约旦", "中东", "ar"),
    "Morocco": ("摩洛哥", "中东/北非", "fr"),
    "Algeria": ("阿尔及利亚", "中东/北非", "fr"),
    "Tunisia": ("突尼斯", "中东/北非", "fr"),
    "Turkey": ("土耳其", "欧亚", "en"),
    "Türkiye": ("土耳其", "欧亚", "en"),
    "Turkiye": ("土耳其", "欧亚", "en"),
    "Kazakhstan": ("哈萨克斯坦", "中亚", "ru"),
    "Uzbekistan": ("乌兹别克斯坦", "中亚", "ru"),
    "Mexico": ("墨西哥", "拉美", "es"),
    "Brazil": ("巴西", "拉美", "pt"),
    "Chile": ("智利", "拉美", "es"),
    "Peru": ("秘鲁", "拉美", "es"),
    "Colombia": ("哥伦比亚", "拉美", "es"),
    "Argentina": ("阿根廷", "拉美", "es"),
    "Ecuador": ("厄瓜多尔", "拉美", "es"),
    "Panama": ("巴拿马", "拉美", "es"),
    "Dominican Republic": ("多米尼加", "拉美", "es"),
    "Guatemala": ("危地马拉", "拉美", "es"),
    "Honduras": ("洪都拉斯", "拉美", "es"),
    "Paraguay": ("巴拉圭", "拉美", "es"),
    "Bolivia": ("玻利维亚", "拉美", "es"),
    "Nigeria": ("尼日利亚", "非洲", "en"),
    "South Africa": ("南非", "非洲", "en"),
    "Kenya": ("肯尼亚", "非洲", "en"),
    "Ethiopia": ("埃塞俄比亚", "非洲", "en"),
    "Tanzania": ("坦桑尼亚", "非洲", "en"),
    "Ghana": ("加纳", "非洲", "en"),
    "Angola": ("安哥拉", "非洲", "pt"),
    "Mozambique": ("莫桑比克", "非洲", "pt"),
    "Zambia": ("赞比亚", "非洲", "en"),
    "Senegal": ("塞内加尔", "非洲", "fr"),
    "Cote d'Ivoire": ("科特迪瓦", "非洲", "fr"),
    "Côte d'Ivoire": ("科特迪瓦", "非洲", "fr"),
    "Congo": ("刚果", "非洲", "fr"),
    "Uganda": ("乌干达", "非洲", "en"),
    "Cameroon": ("喀麦隆", "非洲", "fr"),
    "Madagascar": ("马达加斯加", "非洲", "fr"),
    "Poland": ("波兰", "欧洲", "en"),
    "Romania": ("罗马尼亚", "欧洲", "en"),
    "Hungary": ("匈牙利", "欧洲", "en"),
    "Serbia": ("塞尔维亚", "欧洲", "en"),
    "Germany": ("德国", "欧洲", "de"),
    "Spain": ("西班牙", "欧洲", "es"),
    "Italy": ("意大利", "欧洲", "en"),
    "France": ("法国", "欧洲", "fr"),
    "United Kingdom": ("英国", "欧洲", "en"),
    "United States": ("美国", "北美", "en"),
    "Canada": ("加拿大", "北美", "en"),
    "Australia": ("澳大利亚", "大洋洲", "en"),
    "Papua New Guinea": ("巴布亚新几内亚", "大洋洲", "en"),
    "Fiji": ("斐济", "大洋洲", "en"),
    "Japan": ("日本", "东亚", "en"),
    "South Korea": ("韩国", "东亚", "en"),
    "Kyrgyz": ("吉尔吉斯斯坦", "中亚", "ru"),
    "Tajikistan": ("塔吉克斯坦", "中亚", "ru"),
    "Mongolia": ("蒙古", "东亚", "en"),
    "Azerbaijan": ("阿塞拜疆", "中亚", "ru"),
    "Georgia": ("格鲁吉亚", "欧亚", "en"),
    "Armenia": ("亚美尼亚", "欧亚", "ru"),
    "Rwanda": ("卢旺达", "非洲", "en"),
    "Malawi": ("马拉维", "非洲", "en"),
    "Benin": ("贝宁", "非洲", "fr"),
    "Togo": ("多哥", "非洲", "fr"),
    "Mali": ("马里", "非洲", "fr"),
    "Niger": ("尼日尔", "非洲", "fr"),
    "Burkina Faso": ("布基纳法索", "非洲", "fr"),
    "DRC": ("刚果(金)", "非洲", "fr"),
    "Sierra Leone": ("塞拉利昂", "非洲", "en"),
    "Liberia": ("利比里亚", "非洲", "en"),
    "Mauritania": ("毛里塔尼亚", "非洲", "fr"),
    "Namibia": ("纳米比亚", "非洲", "en"),
    "Botswana": ("博茨瓦纳", "非洲", "en"),
    "Zimbabwe": ("津巴布韦", "非洲", "en"),
    "Uruguay": ("乌拉圭", "拉美", "es"),
    "Costa Rica": ("哥斯达黎加", "拉美", "es"),
    "El Salvador": ("萨尔瓦多", "拉美", "es"),
    "Jamaica": ("牙买加", "拉美", "en"),
}

# Canonical country names matching index.html DATA.country
CANONICAL_COUNTRY = {
    "Viet Nam": "Vietnam",
    "UAE": "United Arab Emirates",
    "Turkey": "Turkey (Türkiye)",
    "Türkiye": "Turkey (Türkiye)",
    "Turkiye": "Turkey (Türkiye)",
    "Lao": "Lao PDR",
    "Kyrgyz": "Kyrgyz Republic",
    "DRC": "Congo, Dem. Rep.",
    "Côte d'Ivoire": "Cote d'Ivoire",
    "Egypt, Arab Republic of": "Egypt",
    "Arab Republic of Egypt": "Egypt",
    "Republic of Indonesia": "Indonesia",
    "Federal Republic of Nigeria": "Nigeria",
    "Kingdom of Saudi Arabia": "Saudi Arabia",
    "United Mexican States": "Mexico",
    "Federative Republic of Brazil": "Brazil",
    "Republic of the Philippines": "Philippines",
    "Republic of Peru": "Peru",
    "Republic of Colombia": "Colombia",
    "Republic of Kenya": "Kenya",
    "United Republic of Tanzania": "Tanzania",
    "Republic of Zambia": "Zambia",
    "Democratic Republic of the Congo": "Congo, Dem. Rep.",
    "Republic of India": "India",
    "People's Republic of Bangladesh": "Bangladesh",
    "Islamic Republic of Pakistan": "Pakistan",
}

# Industrial sector keywords -> FriesGo recommended bundle (specific verticals BEFORE generic factory/infra)
PRODUCT_RULES = [
    (
        r"mining|nickel|copper|lithium|smelter|mineral|oil|gas|refinery|petrochemical|矿山|冶炼|油气",
        "矿用渣浆泵、高压油气阀门、耐磨管件 & 矿用电缆",
        "mining slurry pumps, high-pressure valves, wear-resistant pipes & mining cables",
    ),
    (
        r"power|energy|solar|photovoltaic|wind|grid|substation|electric|transmission|battery|generator|electricity|电力|电站|光伏|电网|储能",
        "电力电缆、配电变压器、开关柜 & 柴油发电机组",
        "power cables, distribution transformers, switchgear & backup diesel generators",
    ),
    (
        r"water|sanitation|sewage|desalination|pipeline|flood|drainage|dam|irrigation|hydropower|供水|水务|排水|灌溉",
        "工业阀门、离心/排涝水泵、管道法兰 & 控制柜",
        "industrial waterworks valves, heavy-duty pumps, pipe fittings & control panels",
    ),
    (
        r"agricult|farm|food|grain|livestock|cold storage|fisheries|rural|drought|农业|农机|冷链|粮仓",
        "农业机械、光伏/柴油灌溉泵、钢构粮仓/冷库 & 维修工具",
        "agricultural machinery, irrigation pumps, cold-storage steel structures & tools",
    ),
    (
        r"steel|warehouse|factory|industrial park|manufacturing|roof|structural|cyclone|typhoon|hurricane|earthquake|reconstruction|shelter|钢结构|厂房|工业园|建材",
        "钢结构厂房、彩钢板、高强紧固件 & 厂房机电",
        "prefabricated steel structures, structural fasteners & factory MEP equipment",
    ),
    (
        r"port|transport|road|rail|bridge|airport|logistics|highway|infrastructure|corridor|urban|港口|铁路|基建|物流",
        "基建钢结构、施工机电、工业泵阀、照明电缆 & 五金工具",
        "steel structures, construction hardware, industrial pumps/valves & power cables",
    ),
]


def http_get(url, timeout=25, headers=None):
    import subprocess
    hdrs = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if headers:
        hdrs.update(headers)
    ctx = ssl.create_default_context()
    last_err = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                raw = resp.read()
                if raw:
                    return raw.decode("utf-8", errors="replace")
        except Exception as e:
            last_err = e
    # Fallback to system curl (rock-solid HTTP/2 & chunked handling on Ubuntu Actions & macOS)
    try:
        cmd = ["curl", "-sSL", "--retry", "2", "--max-time", str(timeout), "-A", USER_AGENT, url]
        raw = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        if raw:
            return raw.decode("utf-8", errors="replace")
    except Exception as e2:
        last_err = e2
    raise last_err


def http_post_json(url, payload, timeout=20, headers=None):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    hdrs = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/json; charset=utf-8",
    }
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return resp.read().decode("utf-8", errors="replace")


def clean_text(s):
    if not s:
        return ""
    s = html_lib.unescape(str(s))
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_country(raw):
    if not raw:
        return "", "", "全球", "en"
    raw_clean = clean_text(raw)
    if raw_clean in CANONICAL_COUNTRY:
        c = CANONICAL_COUNTRY[raw_clean]
        if c in COUNTRY_INFO:
            cn, reg, lang = COUNTRY_INFO[c]
            return c, cn, reg, lang
    for key, (cn, reg, lang) in COUNTRY_INFO.items():
        if key.lower() == raw_clean.lower() or key.lower() in raw_clean.lower():
            canon = CANONICAL_COUNTRY.get(key, key)
            return canon, cn, reg, lang
    # Also check Chinese country mentions
    for key, (cn, reg, lang) in COUNTRY_INFO.items():
        if cn and cn in raw_clean:
            canon = CANONICAL_COUNTRY.get(key, key)
            return canon, cn, reg, lang
    return raw_clean, raw_clean, "其他", "en"


def match_products(text):
    t = (text or "").lower()
    for pat, cn_rec, en_rec in PRODUCT_RULES:
        if re.search(pat, t, re.I):
            return cn_rec, en_rec
    return (
        "工业泵阀、电力电缆、钢结构与工业五金配套",
        "industrial valves, pumps, power cables & structural hardware",
    )


def fetch_gdacs():
    """Fetch live global disaster/typhoon/flood alerts from GDACS RSS."""
    items = []
    try:
        xml_text = http_get("https://www.gdacs.org/xml/rss.xml", timeout=20)
        root = ET.fromstring(xml_text)
        ns = {
            "gdacs": "http://www.gdacs.org",
            "geo": "http://www.w3.org/2003/01/geo/wgs84_pos#",
        }
        type_cn = {
            "TC": "🌀 热带气旋 / 台风",
            "FL": "🌊 洪涝灾害",
            "EQ": "🌋 强地震",
            "DR": "☀️ 干旱预警",
            "VO": "🌋 火山",
            "WF": "🔥 山火",
        }
        level_rank = {"Red": 0, "Orange": 1, "Green": 2}
        level_cn = {"Red": "🔴 红色高危", "Orange": "🟠 橙色预警", "Green": "🟢 常规关注"}

        for it in root.findall("./channel/item"):
            title = clean_text(it.findtext("title"))
            link = clean_text(it.findtext("link"))
            desc = clean_text(it.findtext("description"))
            pub = clean_text(it.findtext("pubDate"))
            ev_type = clean_text(it.findtext("gdacs:eventtype", "", ns)) or "TC"
            alert = clean_text(it.findtext("gdacs:alertlevel", "", ns)) or "Green"
            country_raw = clean_text(it.findtext("gdacs:country", "", ns))

            # Prioritize typhoons, floods, earthquakes, droughts; skip minor green EQ/WF to keep signal sharp
            if alert == "Green" and ev_type not in ("TC", "FL", "DR"):
                continue

            c_en, c_cn, reg, lang = normalize_country(country_raw or title)
            if ev_type == "TC":
                rec_cn = "抗风钢结构厂房、彩钢瓦、排水泵、应急柴油发电机"
                rec_en = "wind-resistant steel structures, metal roofing, dewatering pumps & emergency generators"
                angle = "台风/飓风路径区：灾前推防风加固钢构与备电，灾后 7–15 天急推厂房抢修钢材与排水泵"
            elif ev_type == "FL":
                rec_cn = "大流量排涝水泵、球墨阀门、防水电力电缆、应急发电机"
                rec_en = "high-flow dewatering pumps, industrial valves, waterproof cables & diesel generators"
                angle = "洪涝受损区：重点跟进当地市政排涝、工业园恢复供电与水泵管件急单"
            elif ev_type == "DR":
                rec_cn = "光伏/柴油灌溉水泵、喷灌阀门管件、农机设备"
                rec_en = "solar/diesel irrigation pumps, agricultural valves & farm equipment"
                angle = "干旱农区：重点切入农场抗旱打井、光伏灌溉水泵与水管配件"
            else:
                rec_cn = "快装预制钢结构、应急发电机、水泵阀门与建筑五金"
                rec_en = "prefabricated steel structures, emergency generators, water pumps & construction hardware"
                angle = "灾后重建刚需：对接当地基建承包商与 NGO/政府应急采购"

            # Parse date cleanly
            date_str = ""
            try:
                dt = datetime.datetime.strptime(pub[:25].strip(), "%a, %d %b %Y %H:%M:%S")
                date_str = dt.strftime("%Y-%m-%d")
            except Exception:
                date_str = pub[:16]

            safe_link = (link or "https://www.gdacs.org/").replace("http://", "https://")
            items.append({
                "id": f"gdacs_{len(items)}_{ev_type}",
                "cat": "weather",
                "catLabel": type_cn.get(ev_type, "⚠️ 灾害预警"),
                "severity": alert,
                "severityLabel": level_cn.get(alert, alert),
                "_rank": (level_rank.get(alert, 9), 0 if ev_type == "TC" else (1 if ev_type == "FL" else 2)),
                "country": c_en or "Global",
                "countryCn": c_cn or "全球多国",
                "region": reg,
                "lang": lang,
                "date": date_str,
                "title": title,
                "titleCn": f"{level_cn.get(alert, '')} {type_cn.get(ev_type, '')}：{c_cn or country_raw or title}",
                "summary": desc[:220],
                "amount": "",
                "entity": "",
                "productsCn": rec_cn,
                "productsEn": rec_en,
                "angleCn": angle,
                "source": "GDACS 国际灾害预警",
                "url": safe_link,
            })

        # Sort by alert severity + TC/FL priority, then newest date descending
        items.sort(key=lambda x: (x["_rank"][0], x["_rank"][1], -(int(x["date"].replace("-", "")[:8]) if re.match(r"^\d{4}-\d{2}-\d{2}$", x["date"]) else 0)))
        for x in items:
            x.pop("_rank", None)
        return items[:14]
    except Exception as e:
        print(f"[WARN] GDACS fetch failed: {e}")
        return []


def fetch_worldbank():
    """Fetch newest global active infrastructure/energy/water/mining/agri/industrial projects from World Bank official API."""
    items = []
    # Official World Bank Projects API v2: active projects sorted by newest board approval date
    url = (
        "https://search.worldbank.org/api/v2/projects?"
        "format=json&rows=70&os=0&status_exact=Active&srt=boardapprovaldate&order=desc"
        "&fl=id,project_name,countryname,countryshortname,regionname,boardapprovaldate,"
        "totalamt,status,url,impagency,borrower,sector1,mjsector,lendinginstr"
    )
    industrial_kw = re.compile(
        r"energy|power|water|sanitation|transport|road|rail|port|agricult|irrigat|"
        r"mining|extract|industry|manufactur|trade|urban|housing|construct|infra|"
        r"telecom|digital|climate|resilience|grid|solar|hydro|factory|industrial",
        re.I,
    )
    try:
        raw = http_get(url, timeout=22)
        data = json.loads(raw)
        projs = data.get("projects", {})
        if not isinstance(projs, dict):
            return []

        for pid, p in projs.items():
            if not isinstance(p, dict):
                continue
            pname = clean_text(p.get("project_name"))
            if not pname:
                continue

            # Extract sector string
            sec1 = p.get("sector1")
            sec_name = ""
            if isinstance(sec1, dict):
                sec_name = clean_text(sec1.get("Name", ""))
            elif isinstance(sec1, str):
                sec_name = clean_text(sec1)
            mj = p.get("mjsector")
            mj_txt = ""
            if isinstance(mj, list):
                mj_txt = " ".join(clean_text(x.get("Name", "") if isinstance(x, dict) else str(x)) for x in mj)

            combined_sec = f"{pname} {sec_name} {mj_txt}"
            if not industrial_kw.search(combined_sec):
                continue

            # Country normalization
            c_raw = p.get("countryshortname") or p.get("countryname") or ""
            if isinstance(c_raw, list):
                c_raw = c_raw[0] if c_raw else ""
            c_en, c_cn, reg, lang = normalize_country(c_raw)
            if not c_en or c_en.lower() in ("world", "africa"):
                c_en = clean_text(c_raw) or "Regional"
                c_cn = c_cn or c_en

            # Amount formatting
            amt_raw = str(p.get("totalamt", "") or "").replace(",", "").strip()
            amt_disp = ""
            try:
                amt_num = float(amt_raw)
                if amt_num >= 1_000_000_000:
                    amt_disp = f"${amt_num/1e9:.2f}bn"
                elif amt_num >= 1_000_000:
                    amt_disp = f"${amt_num/1e6:.1f}M"
                elif amt_num > 0:
                    amt_disp = f"${amt_num:,.0f}"
            except Exception:
                amt_disp = amt_raw

            # Date
            dt_raw = clean_text(p.get("boardapprovaldate", ""))
            date_str = dt_raw[:10] if len(dt_raw) >= 10 else dt_raw

            # Implementing agency / borrower (WHO actually buys!)
            imp = clean_text(p.get("impagency", ""))
            bor = clean_text(p.get("borrower", ""))
            entity = imp or bor or ""
            if len(entity) > 90:
                entity = entity[:87] + "..."

            prod_cn, prod_en = match_products(combined_sec)
            proj_url = clean_text(p.get("url", "")) or f"https://projects.worldbank.org/en/projects-operations/project-detail/{pid}"

            items.append({
                "id": f"wb_{pid}",
                "cat": "loan",
                "catLabel": "🏦 世行批准项目",
                "severity": "High" if amt_disp else "Normal",
                "severityLabel": f"💰 {amt_disp}" if amt_disp else "🏦 多边放款",
                "country": c_en,
                "countryCn": c_cn,
                "region": reg,
                "lang": lang,
                "date": date_str,
                "title": pname,
                "titleCn": f"【{c_cn}】{pname}",
                "summary": f"行业：{sec_name or '基建/工业'} ｜ 执行/借款方：{entity or '当地项目部'} ｜ 状态：{clean_text(p.get('status','Active'))}",
                "amount": amt_disp,
                "entity": entity,
                "productsCn": prod_cn,
                "productsEn": prod_en,
                "angleCn": f"大银行已批资金项目！优先查执行机构「{entity or c_cn+'项目办'}」及中标 EPC 总包商，切入 {prod_cn}",
                "source": "世界银行 World Bank API",
                "url": proj_url,
            })

            if len(items) >= 22:
                break

        return items
    except Exception as e:
        print(f"[WARN] World Bank API fetch failed: {e}")
        return []


def fetch_news_rss():
    """Fetch fresh project financing, factory expansion & Chinese EPC wins via Google News RSS."""
    queries = [
        (
            "🏦 银行放款/融资",
            "https://news.google.com/rss/search?q="
            + urllib.parse.quote(
                '("IFC" OR "ADB" OR "AfDB" OR "IDB" OR "EBRD") ("loan" OR "financing") ("factory" OR "power" OR "water" OR "steel" OR "industrial" OR "mining") when:14d'
            )
            + "&hl=en-US&gl=US&ceid=US:en",
        ),
        (
            "🏗️ 新建厂房/扩产",
            "https://news.google.com/rss/search?q="
            + urllib.parse.quote(
                '("breaks ground" OR "new factory" OR "industrial park" OR "plant expansion") (Vietnam OR Indonesia OR Mexico OR "Saudi Arabia" OR Brazil OR Thailand OR India OR Chile OR Egypt OR Nigeria OR "South Africa") when:14d'
            )
            + "&hl=en-US&gl=US&ceid=US:en",
        ),
        (
            "🇨🇳 中资EPC顺风车",
            "https://news.google.com/rss/search?q="
            + urllib.parse.quote(
                '("中标" OR "签约" OR "开工") ("钢结构" OR "电站" OR "工业园" OR "矿山" OR "水务" OR "厂房") ("越南" OR "印尼" OR "沙特" OR "阿联酋" OR "墨西哥" OR "巴西" OR "尼日利亚" OR "智利" OR "埃及" OR "泰国") when:21d'
            )
            + "&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
        ),
    ]

    items = []
    seen = set()
    for label, url in queries:
        try:
            xml_text = http_get(url, timeout=16)
            root = ET.fromstring(xml_text)
            count = 0
            for it in root.findall("./channel/item"):
                title = clean_text(it.findtext("title"))
                link = clean_text(it.findtext("link"))
                pub = clean_text(it.findtext("pubDate"))
                src = clean_text(it.findtext("source")) or "财经/工程快讯"
                if not title or title.lower() in seen:
                    continue
                seen.add(title.lower())

                c_en, c_cn, reg, lang = normalize_country(title)
                if reg == "其他":
                    c_en, c_cn, reg, lang = "Global", "全球新兴市场", "全球", "en"

                date_str = ""
                try:
                    dt = datetime.datetime.strptime(pub[:25].strip(), "%a, %d %b %Y %H:%M:%S")
                    date_str = dt.strftime("%Y-%m-%d")
                except Exception:
                    date_str = pub[:16]

                prod_cn, prod_en = match_products(title)
                # Extract dollar amount if mentioned in title
                m_amt = re.search(r"(\$\s?\d+(?:\.\d+)?\s?(?:billion|million|bn|m|B|M)|\d+(?:\.\d+)?\s?(?:亿美元|亿元))", title, re.I)
                amt = m_amt.group(1) if m_amt else ""

                items.append({
                    "id": f"news_{len(items)}",
                    "cat": "news",
                    "catLabel": label,
                    "severity": "High" if amt else "Normal",
                    "severityLabel": f"💰 {amt}" if amt else label,
                    "country": c_en,
                    "countryCn": c_cn,
                    "region": reg,
                    "lang": lang,
                    "date": date_str,
                    "title": title,
                    "titleCn": title,
                    "summary": f"来源：{src}",
                    "amount": amt,
                    "entity": "",
                    "productsCn": prod_cn,
                    "productsEn": prod_en,
                    "angleCn": f"近期高意向动态！立刻在「背调与合规」查新闻里的业主/总包商官网，切入 {prod_cn}",
                    "source": src,
                    "url": link,
                })
                count += 1
                if count >= 8:
                    break
        except Exception as e:
            print(f"[WARN] News RSS ({label}) failed: {e}")
    return items


def enrich_with_gemini(items):
    """Optionally translate English titles & extract concise Chinese B2B angles via free Gemini API."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key or not items:
        return False

    # Prioritize English loan & news items (weather alerts already have crisp Chinese titles)
    targets = []
    for cat_prio in ("loan", "news"):
        for idx, it in enumerate(items):
            if it["cat"] != cat_prio:
                continue
            zh_chars = len(re.findall(r"[\u4e00-\u9fff]", it["title"]))
            if zh_chars < 6 and len(targets) < 48:
                targets.append({
                    "i": idx,
                    "cat": it["cat"],
                    "country": it["countryCn"],
                    "title": it["title"],
                    "entity": it["entity"],
                    "amount": it["amount"],
                })
    if not targets:
        return True

    import time
    endpoints = [
        ("https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent", {"x-goog-api-key": api_key}),
        ("https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent", {"x-goog-api-key": api_key}),
        ("https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent", {"x-goog-api-key": api_key}),
        ("https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent", {"x-goog-api-key": api_key}),
    ]

    enriched_total = 0
    working_ep = None
    # Process in clean batches of 16 with polite pause so free-tier RPM/timeout never drops batch 2
    for start in range(0, len(targets), 16):
        if start > 0:
            time.sleep(4)
        batch = targets[start : start + 16]
        prompt = (
            "你是中国全品类工业品外贸总监（主营钢结构、阀门、水泵、电缆、机械、农机、五金）。\n"
            "请把下面每条海外商机翻译成精炼易懂的中文标题（带国别，28字以内），并给一句实战外贸切入建议（30字以内）。\n"
            "严格返回纯 JSON 数组，每个对象只含字段：i（原整数索引）、titleCn（中文标题）、angleCn（外贸切入建议）。不要输出任何多余文字。\n"
            + json.dumps(batch, ensure_ascii=False)
        )
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
        }
        try_list = ([working_ep] + [e for e in endpoints if e != working_ep]) if working_ep else endpoints
        resp_txt = None
        for ep_url, ep_hdrs in try_list:
            try:
                resp_txt = http_post_json(ep_url, body, timeout=55, headers=ep_hdrs)
                working_ep = (ep_url, ep_hdrs)
                break
            except Exception as e_ep:
                print(f"[WARN] Gemini endpoint failed ({ep_url.split('?')[0]}): {e_ep}")
                time.sleep(2)
        if not resp_txt:
            continue
        try:
            resp_json = json.loads(resp_txt)
            text = resp_json["candidates"][0]["content"]["parts"][0]["text"]
            text = re.sub(r"^```json\s*|\s*```$", "", text.strip())
            arr = json.loads(text)
            if isinstance(arr, list):
                for obj in arr:
                    i = obj.get("i")
                    if isinstance(i, int) and 0 <= i < len(items):
                        if obj.get("titleCn"):
                            items[i]["titleCn"] = clean_text(obj["titleCn"])
                        if obj.get("angleCn"):
                            items[i]["angleCn"] = clean_text(obj["angleCn"])
                        enriched_total += 1
        except Exception as e_parse:
            print(f"[WARN] Gemini batch parse failed: {e_parse}")

    if enriched_total > 0:
        print(f"[INFO] Gemini enriched {enriched_total} items successfully.")
        return True
    return False


def build_brief_markdown(feed):
    """Build crisp Chinese morning brief for WeChat / WxPusher / WeCom / Feishu / DingTalk."""
    stats = feed["stats"]
    lines = [
        f"🌍 FriesGo 全球工业商机早报（{feed['updatedCn']}）",
        f"今日抓取 {stats['total']} 条：🌀 台风/灾害 {stats['weather']} ｜ 🏦 世行放款项目 {stats['loan']} ｜ 📰 融资/扩产/EPC {stats['news']}",
        "",
    ]
    weathers = [x for x in feed["items"] if x["cat"] == "weather"][:3]
    loans = [x for x in feed["items"] if x["cat"] == "loan"][:4]
    news = [x for x in feed["items"] if x["cat"] == "news"][:4]

    if weathers:
        lines.append("【🌀 台风/灾害预警（钢构/排水泵/备电抢修机会）】")
        for x in weathers:
            lines.append(f"• {x['titleCn']} → 推：{x['productsCn']}")
        lines.append("")
    if loans:
        lines.append("【🏦 世界银行最新基建/工业获批项目】")
        for x in loans:
            amt = f"（{x['amount']}）" if x["amount"] else ""
            lines.append(f"• {x['titleCn']}{amt} → 推：{x['productsCn']}")
        lines.append("")
    if news:
        lines.append("【📰 全球放款 / 建厂扩产 / 中资EPC动态】")
        for x in news:
            lines.append(f"• [{x['countryCn']}] {x['titleCn']}")
        lines.append("")
    lines.append(f"👉 点击进入作战地图查看全文、一键背调与生成开发信：\n{SITE_URL}")
    return "\n".join(lines)


def push_notifications(feed):
    """Send daily morning brief to whichever optional channel secrets are configured."""
    title = f"🌍 全球工业商机早报 ({feed['updatedDate']})"
    md = build_brief_markdown(feed)

    # 0. Native Tencent WeChat Official Test Account (Zero App download! Auto-sends to all followers!)
    wx_appid = os.environ.get("WX_APP_ID", "").strip()
    wx_secret = os.environ.get("WX_APP_SECRET", "").strip()
    wx_tpl = os.environ.get("WX_TEMPLATE_ID", "").strip()
    if wx_appid and wx_secret and wx_tpl:
        try:
            tok_url = (
                "https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential"
                + "&appid=" + urllib.parse.quote(wx_appid)
                + "&secret=" + urllib.parse.quote(wx_secret)
            )
            tok_data = json.loads(http_get(tok_url, timeout=15))
            access_token = tok_data.get("access_token", "")
            if not access_token:
                raise RuntimeError(f"Failed to get WeChat access_token: {tok_data}")

            # Use explicit WX_OPENIDS if provided, otherwise auto-fetch ALL followers who scanned QR!
            raw_openids = os.environ.get("WX_OPENIDS", "").strip()
            if raw_openids:
                openids = [o.strip() for o in raw_openids.split(",") if o.strip()]
            else:
                usr_url = f"https://api.weixin.qq.com/cgi-bin/user/get?access_token={urllib.parse.quote(access_token)}"
                usr_data = json.loads(http_get(usr_url, timeout=15))
                openids = (usr_data.get("data") or {}).get("openid") or []

            if not openids:
                print("[WARN] WeChat Test Account has 0 followers yet — scan QR first!")
            else:
                stats = feed["stats"]
                weathers = [x for x in feed["items"] if x["cat"] == "weather"][:2]
                loans = [x for x in feed["items"] if x["cat"] == "loan"][:2]
                news = [x for x in feed["items"] if x["cat"] == "news"][:2]
                w_txt = "；".join(x["titleCn"] for x in weathers) if weathers else "全球主要航线今日无红橙台风预警"
                l_parts = []
                for x in loans + news:
                    amt = f"({x['amount']})" if x.get("amount") else ""
                    l_parts.append(f"• {x['titleCn']}{amt}")
                l_txt = "\n".join(l_parts) if l_parts else "点击下方详情查看今日 60 条全球商机"

                send_url = f"https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={urllib.parse.quote(access_token)}"
                sent_ok = 0
                for oid in openids:
                    payload = {
                        "touser": oid,
                        "template_id": wx_tpl,
                        "url": SITE_URL,
                        "data": {
                            "date": {"value": feed["updatedCn"]},
                            "stats": {"value": f"共 {stats['total']} 条（灾害 {stats['weather']}｜世行放款 {stats['loan']}｜扩产EPC {stats['news']}）"},
                            "weather": {"value": w_txt[:180]},
                            "leads": {"value": l_txt[:180] + "\n👉 点击本卡片直达作战地图！"},
                        },
                    }
                    res_j = json.loads(http_post_json(send_url, payload, timeout=15))
                    if res_j.get("errcode") == 0:
                        sent_ok += 1
                    else:
                        print(f"[WARN] WeChat send to {oid[:8]}... failed: {res_j}")
                print(f"[INFO] Pushed native WeChat morning brief to {sent_ok}/{len(openids)} colleague(s).")
        except Exception as e:
            print(f"[WARN] WeChat Official Test Account push failed: {e}")

    # 1. WxPusher (Optional legacy channel)
    wx_token = os.environ.get("WXPUSHER_APP_TOKEN", "").strip()
    wx_topic = os.environ.get("WXPUSHER_TOPIC_ID", "").strip()
    if wx_token and wx_topic:
        try:
            topic_ids = [int(t.strip()) for t in wx_topic.split(",") if t.strip().isdigit()]
            html_body = "<br>".join(html_lib.escape(line) for line in md.splitlines())
            html_body += f'<br><br><a href="{SITE_URL}">🚀 立即打开全球工业品出海作战地图</a>'
            http_post_json(
                "https://wxpusher.zjiecode.com/api/send/message",
                {
                    "appToken": wx_token,
                    "content": html_body,
                    "summary": title,
                    "contentType": 2,
                    "topicIds": topic_ids,
                    "url": SITE_URL,
                },
            )
            print("[INFO] Pushed morning brief via WxPusher.")
        except Exception as e:
            print(f"[WARN] WxPusher push failed: {e}")

    # 2. PushPlus (Alternative Personal WeChat push)
    pp_token = os.environ.get("PUSHPLUS_TOKEN", "").strip()
    if pp_token:
        try:
            payload = {"token": pp_token, "title": title, "content": md, "template": "markdown"}
            pp_topic = os.environ.get("PUSHPLUS_TOPIC", "").strip()
            if pp_topic:
                payload["topic"] = pp_topic
            http_post_json("https://www.pushplus.plus/send", payload)
            print("[INFO] Pushed morning brief via PushPlus.")
        except Exception as e:
            print(f"[WARN] PushPlus push failed: {e}")

    # 3. WeCom (企业微信群机器人)
    wecom = os.environ.get("WECOM_WEBHOOK", "").strip()
    if wecom:
        try:
            http_post_json(wecom, {"msgtype": "text", "text": {"content": md}})
            print("[INFO] Pushed morning brief via WeCom.")
        except Exception as e:
            print(f"[WARN] WeCom push failed: {e}")

    # 4. Feishu (飞书群机器人)
    feishu = os.environ.get("FEISHU_WEBHOOK", "").strip()
    if feishu:
        try:
            http_post_json(feishu, {"msg_type": "text", "content": {"text": md}})
            print("[INFO] Pushed morning brief via Feishu.")
        except Exception as e:
            print(f"[WARN] Feishu push failed: {e}")

    # 5. DingTalk (钉钉群机器人)
    ding = os.environ.get("DINGTALK_WEBHOOK", "").strip()
    if ding:
        try:
            http_post_json(ding, {"msgtype": "text", "text": {"content": md}})
            print("[INFO] Pushed morning brief via DingTalk.")
        except Exception as e:
            print(f"[WARN] DingTalk push failed: {e}")


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_cn = now_utc + datetime.timedelta(hours=8)

    print("[INFO] Fetching GDACS global weather/disaster alerts...")
    weather_items = fetch_gdacs()
    print(f"       -> {len(weather_items)} weather/disaster items")

    print("[INFO] Fetching World Bank newly approved industrial/infra projects...")
    wb_items = fetch_worldbank()
    print(f"       -> {len(wb_items)} World Bank project items")

    print("[INFO] Fetching global financing / new factory / EPC news RSS...")
    news_items = fetch_news_rss()
    print(f"       -> {len(news_items)} news items")

    all_items = weather_items + wb_items + news_items
    ai_used = enrich_with_gemini(all_items)

    feed = {
        "updatedIso": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "updatedCn": now_cn.strftime("%Y-%m-%d %H:%M 北京时间"),
        "updatedDate": now_cn.strftime("%Y-%m-%d"),
        "aiEnriched": ai_used,
        "stats": {
            "total": len(all_items),
            "weather": len(weather_items),
            "loan": len(wb_items),
            "news": len(news_items),
        },
        "items": all_items,
    }

    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(feed, f, ensure_ascii=False, indent=2)

    with open(JS_OUT, "w", encoding="utf-8") as f:
        f.write("window.RADAR_FEED_INLINE = ")
        json.dump(feed, f, ensure_ascii=False)
        f.write(";\n")

    print(f"[SUCCESS] Wrote {len(all_items)} items to {JSON_OUT} and {JS_OUT}")
    push_notifications(feed)


if __name__ == "__main__":
    main()
