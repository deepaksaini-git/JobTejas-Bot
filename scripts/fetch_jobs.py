"""Govt job updates: sources.json se fetch -> dedupe -> jobs.json + Telegram."""
import urllib.error, json, os, re, time, hashlib, html, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS = os.path.join(ROOT, "jobs.json")
MAX_KEEP, MAX_SEND = 400, 25
UA = {"User-Agent": "Mozilla/5.0 (JobAlertBot; +github-actions)"}

CATS = [
    ("Admit Card", r"admit card|hall ticket|call letter|प्रवेश पत्र"),
    ("Answer Key", r"answer key|उत्तर कुंजी"),
    ("Result", r"result|merit list|final list|score ?card|cut ?off|परिणाम|रिजल्ट"),
    ("Syllabus", r"syllabus|exam pattern|पाठ्यक्रम"),
    ("Admission", r"admission|counselling|प्रवेश"),
    ("Job", r"recruitment|vacanc|notification|apply|bharti|भर्ती|नौकरी|post"),
]
KEEP = re.compile("|".join(p for _, p in CATS), re.I)

def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
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
        tag = it.tag.split("}")[-1]
        if tag not in ("item", "entry"):
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
    def __init__(self, base):
        super().__init__(); self.base, self.cur, self.items, self.buf = base, None, [], []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.cur = dict(attrs).get("href"); self.buf = []
    def handle_data(self, d):
        if self.cur is not None: self.buf.append(d)
    def handle_endtag(self, tag):
        if tag == "a" and self.cur:
            text = re.sub(r"\s+", " ", "".join(self.buf)).strip()
            if len(text) > 15:
                self.items.append((text, urllib.parse.urljoin(self.base, self.cur)))
            self.cur = None

def parse_html(txt, base):
    p = Links(base); p.feed(txt)
    return [(t, l) for t, l in p.items if KEEP.search(t)]

def tg(token, chat, text):
    data = urllib.parse.urlencode({"chat_id": chat, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage", data=data), timeout=25)
    except urllib.error.HTTPError as e:
        raise RuntimeError(e.read().decode("utf-8", "ignore"))

SITE_KEYS = {"Job": "job", "Result": "result", "Admit Card": "admit_card",
             "Answer Key": "answer_key", "Syllabus": "syllabus", "Admission": "admission"}
MAX_DRAFTS = 15

def write_site(items, fresh, make_drafts):
    """A: _data/updates.json (live board). B: _posts/ draft files (published: false)."""
    data = {"updated": datetime.now(timezone.utc).isoformat(timespec="minutes")}
    for cat, key in SITE_KEYS.items():
        data[key] = [i for i in items if i["category"] == cat][:15]
    os.makedirs(os.path.join(ROOT, "_data"), exist_ok=True)
    with open(os.path.join(ROOT, "_data", "updates.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    if not make_drafts:
        return
    pdir = os.path.join(ROOT, "_posts"); os.makedirs(pdir, exist_ok=True)
    layout = os.getenv("POST_LAYOUT", "post")
    for it in fresh[:MAX_DRAFTS]:
        if it["category"] not in SITE_KEYS:
            continue
        day = it["time"][:10]
        slug = re.sub(r"[^a-z0-9]+", "-", it["title"].lower()).strip("-")[:60] or it["id"]
        path = os.path.join(pdir, f"{day}-{slug}.md")
        if os.path.exists(path):
            continue
        head = ("---\nlayout: %s\ntitle: %s\ndate: %s %s:00 +0000\ncategories: [%s]\n"
                "published: false\nsource: %s\nofficial_link: %s\n---\n\n") % (
            layout, json.dumps(it["title"], ensure_ascii=False), day, it["time"][11:16],
            it["category"].lower().replace(" ", "-"),
            json.dumps(it["source"], ensure_ascii=False), json.dumps(it["link"]))
        body = ("Is post ka poora content abhi likhna baaki hai. Official link se details dekh kar yahan likho, "
                "phir upar `published: false` ko `true` kar do.\n\n- Source: %s\n- Official link: %s\n") % (it["source"], it["link"])
        with open(path, "w", encoding="utf-8") as f:
            f.write(head + body)

def main():
    cfg = json.load(open(os.path.join(ROOT, "sources.json"), encoding="utf-8"))
    old = json.load(open(JOBS, encoding="utf-8")) if os.path.exists(JOBS) else None
    items = old["items"] if old else []
    seen = {i["id"] for i in items}
    fresh = []
    for s in cfg["sources"]:
        try:
            txt = get(s["url"])
            found = parse_rss(txt) if s["type"] == "rss" else parse_html(txt, s["url"])
        except Exception as e:
            print("FAIL", s["name"], e); continue
        for title, link in found:
            title = html.unescape(title)
            jid = hashlib.sha1(re.sub(r"\W+", "", title.lower()).encode()).hexdigest()[:16]
            if jid in seen: continue
            seen.add(jid)
            fresh.append({"id": jid, "title": title, "link": link, "source": s["name"],
                          "category": category(title),
                          "time": datetime.now(timezone.utc).isoformat(timespec="minutes")})
        print("OK", s["name"], len(found))
    items = (fresh + items)[:MAX_KEEP]
    json.dump({"updated": datetime.now(timezone.utc).isoformat(timespec="minutes"), "items": items},
              open(JOBS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    write_site(items, fresh, old is not None)
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    print("Telegram secrets mile:", bool(token and chat))
    if os.getenv("TG_TEST") == "1":
        if not (token and chat):
            print("SECRETS MISSING: TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID check karo"); return
        for it in items[:3]:
            try: tg(token, chat, f"<b>[TEST · {it['category']}]</b> {html.escape(it['title'])}\n{it['link']}"); time.sleep(1.2)
            except Exception as e: print("TG FAIL", e)
        print("Test messages bheje gaye"); return
    if old is None:
        print("Pehli run: purane items sirf save kiye, Telegram par nahi bheje."); return
    if token and chat:
        for it in fresh[:MAX_SEND]:
            msg = (f"<b>[{it['category']}]</b> {html.escape(it['title'])}\n"
                   f"{html.escape(it['source'])}\n{it['link']}")
            try: tg(token, chat, msg); time.sleep(1.2)
            except Exception as e: print("TG FAIL", e)
    print("New:", len(fresh))

if __name__ == "__main__":
    main()
