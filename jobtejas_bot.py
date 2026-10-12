import requests
from bs4 import BeautifulSoup
import time
import os
import urllib3
from urllib.parse import urljoin
import ssl

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# UPSSSC jaisi purani sites ke legacy SSL issue ko fix karne ke liye custom context
class CustomHttpAdapter (requests.adapters.HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        ctx = ssl.create_default_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
        self.poolmanager = urllib3.poolmanager.PoolManager(
                num_pools=connections,
                maxsize=maxsize,
                block=block,
                ssl_context=ctx)

# --- CONFIGURATION ---
BOT_TOKEN = "8717719463:AAGZZyVlTrzFJTkNXTUUBUod0OVRjL8Ea2o"
CHAT_ID = "985415424" 

SITES_TO_TRACK = {
    "RRB Allahabad": "https://rrbald.gov.in/",
    "UPSSSC": "https://upsssc.gov.in/",
    "BPSC": "https://bpsc.bih.nic.in/",
    "SSC": "https://ssc.gov.in/",
    "Sarkari Result": "https://www.sarkariresult.com/",
    "JobTejas 1": "https://jobtejas.blogspot.com",
    "JobTejas 2": "https://jobtejas-com.blogspot.com",
    "JobTejas 3": "http://jobtejas.great-site.net/"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}

KEYWORDS = ['notice', 'cen', 'click here', 'result', 'admit card', 'apply', 'syllabus', 'advertisement', 'recruitment']

# Custom session banana taaki sabhi sites khul jayein
session = requests.Session()
session.mount('https://', CustomHttpAdapter())

def send_telegram_message(text):
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        requests.post(api_url, data=payload, timeout=10)
    except Exception as e:
        print(f"Error sending message (Internet check karein): {e}")

def get_latest_updates(site_name, site_url):
    try:
        # Timeout 15 se badhakar 30 kar diya hai taaki BPSC jaisi slow sites load ho sakein
        response = session.get(site_url, headers=HEADERS, timeout=30, verify=False)
        soup = BeautifulSoup(response.text, "html.parser")
        links = soup.find_all("a", href=True)
        
        latest_notices = []
        for link in links:
            text = link.get_text(strip=True)
            href = link['href']
            
            if len(text) > 5 and any(keyword in text.lower() for keyword in KEYWORDS):
                full_link = urljoin(site_url, href)
                latest_notices.append((text, full_link))
                
        return latest_notices
    
    except Exception as e:
        print(f"Error fetching {site_name}: {e}")
        return []

def track_updates():
    print("Multi-Website Tracker Started! Checking for updates 4 times a day...")
    
    seen_links = set()
    file_name = "seen_links.txt"
    
    if os.path.exists(file_name):
        with open(file_name, "r", encoding="utf-8") as f:
            seen_links = set(f.read().splitlines())

        # Yahan se while True hata diya gaya hai
    for site_name, site_url in SITES_TO_TRACK.items():
        print(f"Checking {site_name}...")
        notices = get_latest_updates(site_name, site_url)
        
        for text, href in notices:
            if href not in seen_links:
                message = f"🚨 <b>{site_name} - Naya Update!</b>\n\n📌 {text}\n🔗 Link: {href}\n\nJobTejas par jaldi update karein!"
                send_telegram_message(message)
                
                seen_links.add(href)
                
                with open(file_name, "a", encoding="utf-8") as f:
                    f.write(href + "\n")
        
        time.sleep(2)
        
    print("Checking complete. GitHub action band ho raha hai.")

if __name__ == "__main__":
    track_updates()
