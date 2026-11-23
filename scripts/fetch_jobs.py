"""Govt job updates (official-first): sources.json -> parallel fetch -> dedupe -> jobs.json + status.json + Telegram."""
import urllib.error, json, os, re, time, hashlib, html, urllib.request, urllib.parse, ssl
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS = os.path.join(ROOT, "jobs.json")
STATUS = os.path.join(ROOT, "status.json")
MAX_KEEP = 600
MAX_SEND_OFFICIAL, MAX_SEND_NEWS = 60, 15   # ek run me Telegram par maximum
FAIL_ALERT_AT = 6                           # itni lagatar fail runs (10 min x 6 = ~1 ghanta) par ek baar alert
TIMEOUT = 15
UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
}
SSL_CTX = ssl._create_unverified_context()  # govt sites ke kharab certificate ke liye (sirf site fetch me)

CATS = [
    ("Admit Card", r"admit card|hall ticket|call letter|प्रवेश पत्र"),
    ("Answer Key", r"answer key|उत्तर कुंजी"),
    ("Result", r"result|merit list|final list|score ?card|cut ?off|परिणाम|रिजल्ट"),
    ("Syllabus", r"syllabus|exam pattern|पाठ्यक्रम"),
    ("Admission", r"admission|counselling|प्रवेश"),
    ("Job", r"recruitment|vacanc|notification|apply|bharti|भर्ती|नौकरी|post"),
]
KEEP = re.compile("|".join(p for _, p in CATS), re.I)
JUNK = re.compile(r"skip to|screen reader|sitemap|site map|contact us|privacy|disclaimer|terms (of|&)|copyright|"
                  r"feedback|accessibility|about us|\bfaqs?\b|\brti\b|log ?in|sign ?in|visitor|hyperlinking|web information manager", re.I)

def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=SSL_CTX) as r:
        return r.read().decode("utf-8", "ignore")

def category(t):
    for name, pat in CATS:
        if re.search(pat, t, re.I):
            return name
    return "Update"

def parse_rss(txt):
    out = []
    root = ET.fromstring(txt)
    for it in root.iter():
        if it.tag.split("}")[-1] not in ("item", "entry"):
            continue
        title = link = ""
        for c in it:
            ct = c.tag.split("}")[-1]
            if ct == "title": title = (c.text or "").strip()
            elif ct == "link": link = (c.text or c.attrib.get("href") or "").strip()
        if title and link:
            out.append((title, link))
    return out

class Links(HTMLParser):
    def __init__(self, base, minlen):
        super().__init__(); self.base, self.minlen, self.cur, self.items, self.buf = base, minlen, None, [], []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.cur = dict(attrs).get("href"); self.buf = []
    def handle_data(self, d):
        if self.cur is not None: self.buf.append(d)
    def handle_endtag(self, tag):
        if tag == "a" and self.cur:
            href = self.cur.strip()
            text = re.sub(r"\s+", " ", "".join(self.buf)).strip()
            if len(text) >= self.minlen and not href.lower().startswith(("#", "javascript", "mailto", "tel")):
                self.items.append((text, urllib.parse.urljoin(self.base, href)))
            self.cur = None

def parse_html(txt, base, mode="keyword"):
    """mode=keyword: sirf job/result jaise words wale links. mode=all: page ka har naya link (nav/junk hata ke)."""
    p = Links(base, 12 if mode == "all" else 15); p.feed(txt)
    out, seen = [], set()
    for t, l in p.items:
        if (t, l) in seen: continue
        seen.add((t, l))
        if mode == "all":
            if not JUNK.search(t): out.append((t, l))
        elif KEEP.search(t):
            out.append((t, l))
    return out

def fetch_source(s):
    try:
        txt = get(s["url"])
        found = parse_rss(txt) if s["type"] == "rss" else parse_html(txt, s["url"], s.get("mode", "keyword"))
        return s, found, None
    except Exception as e:
        return s, [], f"{type(e).__name__}: {str(e)[:100]}"

def tg(token, chat, text):
    data = urllib.parse.urlencode({"chat_id": chat, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage", data=data), timeout=25)
    except urllib.error.HTTPError as e:
        raise RuntimeError(e.read().decode("utf-8", "ignore"))

def fmt(it):
    cat = it["category"] if it["category"] != "Update" else "NEW"
    head = f"🔴 <b>OFFICIAL · {cat}</b>" if it.get("official") else f"📰 <b>{cat}</b>"
    return (f"{head}\n{html.escape(it['title'])}\n{html.escape(it['source'])}\n"
            f"{html.escape(it['link'], quote=False)}")

def load(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default

def main():
    cfg = json.load(open(os.path.join(ROOT, "sources.json"), encoding="utf-8"))
    old = load(JOBS, None)
    status = load(STATUS, {"sources": {}, "baselined": []})
    items = old["items"] if old else []
    seen = {i["id"] for i in items}
    baselined = set(status.get("baselined", []))
    src_stat = status.get("sources", {})
    now = datetime.now(timezone.utc).isoformat(timespec="minutes")

    with ThreadPoolExecutor(max_workers=16) as ex:
        results = list(ex.map(fetch_source, cfg["sources"]))

    fresh, down = [], []
    for s, found, err in results:
        st = src_stat.setdefault(s["name"], {"fails": 0, "last_ok": ""})
        if err:
            st["fails"] += 1
            print("FAIL", s["name"], err)
            if st["fails"] == FAIL_ALERT_AT or (st["fails"] > FAIL_ALERT_AT and st["fails"] % 144 == 0):
                down.append(f"{s['name']} ({st['fails']} baar fail)")
            continue
        st["fails"], st["last_ok"] = 0, now
        official = bool(s.get("official"))
        silent = s["name"] not in baselined   # naye source ki pehli safal run Telegram par nahi jaati
        n = 0
        for title, link in found:
            title = html.unescape(title).strip()
            cat = category(title)
            if cat == "Update" and not official:
                continue
            jid = hashlib.sha1((re.sub(r"\W+", "", title.lower()) + "|" + link.strip().lower()).encode()).hexdigest()[:16]
            if jid in seen:
                continue
            seen.add(jid); n += 1
            fresh.append({"id": jid, "title": title, "link": link, "source": s["name"], "category": cat,
                          "official": official, "time": now, "_silent": silent})
        baselined.add(s["name"])
        print("OK", s["name"], len(found), "new:", n, "(baseline)" if silent else "")

    to_send = [i for i in fresh if not i["_silent"]]
    for i in fresh:
        i.pop("_silent")
    items = (fresh + items)[:MAX_KEEP]
    json.dump({"updated": now, "items": items}, open(JOBS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"sources": src_stat, "baselined": sorted(baselined)}, open(STATUS, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    print("Telegram secrets mile:", bool(token and chat))
    if os.getenv("TG_TEST") == "1":
        if not (token and chat):
            print("SECRETS MISSING: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID check karo"); return
        for it in items[:3]:
            try: tg(token, chat, "TEST\n" + fmt(it)); time.sleep(1.2)
            except Exception as e: print("TG FAIL", e)
        print("Test messages bheje gaye"); return
    if token and chat:
        official = [i for i in to_send if i["official"]][:MAX_SEND_OFFICIAL]
        news = [i for i in to_send if not i["official"]][:MAX_SEND_NEWS]
        for it in official + news:          # official sabse pehle
            try: tg(token, chat, fmt(it)); time.sleep(1.2)
            except Exception as e: print("TG FAIL", e)
        if down and old is not None:
            try: tg(token, chat, "⚠️ Source down:\n" + "\n".join(down))
            except Exception as e: print("TG FAIL", e)
    print("New (sent):", len(to_send), "| New (total, with baseline):", len(fresh))

if __name__ == "__main__":
    main()
