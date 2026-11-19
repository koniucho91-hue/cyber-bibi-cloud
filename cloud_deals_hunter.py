"""
cloud_deals_hunter.py - Autonomiczny Łowca Okazji 24/7 w Chmurze dla Tomasza
Działa nieprzerwanie na serwerze chmurowym, nawet gdy komputer domowy jest wyłączony.
Wysyła natychmiastowe powiadomienia push na telefon przez ntfy.sh/cyber_bibi_tomasz_deals.
"""

import time
import os
import sys
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime
from bs4 import BeautifulSoup

NTFY_TOPIC = "cyber_bibi_tomasz_deals"
SENT_DEALS_FILE = "sent_deals_history.json"

# CHODLIWY SPRZĘT PREMIUM (BENCHMARKI NATYCHMIASTOWEJ ODSPRZEDAŻY W 24H)
BENCHMARKS = [
    (r"ps5\s*pro", 2950, 2350, "PlayStation 5 Pro"),
    (r"ps5\s*slim", 1500, 1150, "PlayStation 5 Slim"),
    (r"ps5|playstation\s*5", 1350, 1000, "PlayStation 5"),
    (r"steam\s*deck\s*oled", 1800, 1350, "Steam Deck OLED"),
    (r"steam\s*deck", 1100, 750, "Steam Deck LCD"),
    (r"switch\s*oled", 850, 550, "Switch OLED"),
    (r"dji\s*pocket\s*3", 1600, 1150, "DJI Pocket 3"),
    (r"dji\s*mini\s*4\s*pro", 2600, 1950, "DJI Mini 4 Pro"),
    (r"dji\s*mini\s*3\s*pro", 1800, 1350, "DJI Mini 3 Pro"),
    (r"dji\s*avata", 2500, 1850, "DJI Avata"),
    (r"garmin\s*fenix", 1950, 1400, "Garmin Fenix"),
    (r"bambu.*p1s", 2100, 1500, "Bambu Lab P1S"),
    (r"bambu.*a1", 1250, 850, "Bambu Lab A1"),
    (r"macbook.*(m2|m3)", 3200, 2400, "MacBook M2/M3"),
    (r"macbook.*m1", 2100, 1500, "MacBook M1"),
    (r"partybox\s*310", 1550, 1100, "JBL Partybox 310")
]

# ŻELAZNY ZAKAZ: ZERO ELEKTRONARZĘDZI, ZERO UŻYWANYCH ODKURZACZY, ZERO USZKODZONYCH
BANNED_TOOLS = ["milwaukee", "dewalt", "makita", "bosch", "festool", "ryobi", "wkrętark", "szlifierk", "młotowiertark"]
BANNED_JUNK = ["uszkodzon", "na czesci", "na części", "do naprawy", "pęknięt", "rozbit", "blokad", "icloud", "karton", "samo etui", "sam pad", "odkurzacz"]

def send_push_alert(title, buy_price, resale_price, profit, url, source):
    """Wysyła bezpośrednie powiadomienie push na telefon Tomasza"""
    msg = f"🔥 NOWA OKAZJA W CHMURZE: +{profit} PLN ZYSKU!\nSprzęt: {title}\nKupno: {buy_price} zł -> Odsprzedaż: {resale_price} zł\nŹródło: {source}\nLink: {url}"
    try:
        req = urllib.request.Request(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=msg.encode("utf-8")
        )
        req.add_header("Title", f"OKAZJA (+{profit} zl) - {title[:30]}")
        req.add_header("Priority", "high")
        req.add_header("Tags", "moneybag,fire,cloud")
        req.add_header("Click", url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Błąd wysyłki push: {e}")
        return False

def load_sent_history():
    if os.path.exists(SENT_DEALS_FILE):
        try:
            with open(SENT_DEALS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_sent_history(sent_set):
    try:
        with open(SENT_DEALS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(sent_set)[-1000:], f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def scan_olx(sent_urls):
    deals_found = 0
    queries = ["ps5", "steam deck", "dji mini", "pocket 3", "macbook m", "garmin fenix", "bambu lab"]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    for q in queries:
        url = f"https://www.olx.pl/d/elektronika/q-{urllib.parse.quote(q)}/?search%5Border%5D=created_at%3Adesc"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=12) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            
            marker = 'window.__PRERENDERED_STATE__= "'
            s_idx = html.find(marker)
            if s_idx == -1:
                continue
            s_idx += len(marker)
            e_idx = html.find('";', s_idx)
            if e_idx == -1:
                continue
            
            raw_json = json.loads('"' + html[s_idx:e_idx] + '"')
            data = json.loads(raw_json)
            ads = data.get("listing", {}).get("listing", {}).get("ads", [])
            
            for ad in ads:
                if ad.get("isPromoted", False):
                    continue
                ad_url = ad.get("url", "")
                if not ad_url.startswith("http"):
                    ad_url = "https://www.olx.pl" + ad_url
                if ad_url in sent_urls:
                    continue
                
                title = ad.get("title", "")
                t_low = title.lower()
                
                if any(b in t_low for b in BANNED_TOOLS) or any(j in t_low for j in BANNED_JUNK):
                    continue
                
                p_info = ad.get("price", {})
                price = (p_info.get("regularPrice") or {}).get("value") or 0
                if price <= 0:
                    continue
                
                for pattern, benchmark_resale, max_buy, cat_name in BENCHMARKS:
                    if re.search(pattern, t_low):
                        if price <= max_buy:
                            fee = int(benchmark_resale * 0.06)
                            clean_profit = int(benchmark_resale - price - fee - 20)
                            if clean_profit >= 300:
                                print(f"[{datetime.now().strftime('%H:%M:%S')}] WYKRYTO OKAZJĘ: {title} | Zysk: +{clean_profit} zł")
                                if send_push_alert(title, int(price), benchmark_resale, clean_profit, ad_url, "OLX"):
                                    sent_urls.add(ad_url)
                                    deals_found += 1
                        break
        except Exception:
            continue
    return deals_found

# Dodajemy wbudowany miniserwer HTTP dla darmowego tieru Web Service w chmurze
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("CYBER BIBI • Łowca Okazji 24/7 w Chmurze DZIAŁA STABILNIE!".encode("utf-8"))
    def log_message(self, format, *args):
        pass

def start_http_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

def main():
    threading.Thread(target=start_http_health_server, daemon=True).start()
    print("=" * 60)
    print("CYBER BIBI • AUTONOMICZNY WORKER CHMUROWY 24/7 DLA TOMASZA")
    print(f"Kanał powiadomień: https://ntfy.sh/{NTFY_TOPIC}")
    print("=" * 60)
    
    sent_urls = load_sent_history()
    print(f"Załadowano historię {len(sent_urls)} wcześniej wysłanych ofert.")
    
    # Wyślij powitalne potwierdzenie startu workera
    send_push_alert("Start Chmurowego Łowcy Okazji 24/7", 0, 0, 0, "https://ntfy.sh/" + NTFY_TOPIC, "Cyber Bibi Cloud")
    
    while True:
        try:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Skanowanie rynku w chmurze...")
            new_deals = scan_olx(sent_urls)
            if new_deals > 0:
                save_sent_history(sent_urls)
                print(f"Wysłano {new_deals} nowych alertów na telefon.")
        except Exception as e:
            print(f"Błąd pętli: {e}")
        time.sleep(60)

if __name__ == "__main__":
    main()