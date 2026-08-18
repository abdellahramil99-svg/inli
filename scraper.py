#!/usr/bin/env python3
"""
Surveillance des nouvelles annonces in'li (Action Logement).
Scrape la liste des annonces de location, filtre selon tes critères,
compare aux annonces déjà vues, et envoie une notif Telegram pour
chaque nouvelle annonce correspondant à tes critères.
Config via variables d'environnement (voir README.md) :
 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID   -> obligatoires
 SEARCH_URL                             -> optionnel : colle ici une URL de
                                            recherche filtrée (région, prix,
                                            surface...) copiée depuis inli.fr.
                                            Si absent, utilise la liste générale.
 MAX_RENT, MIN_SURFACE, MIN_ROOMS       -> optionnels (filtres supplémentaires)
 CITIES                                 -> optionnel, liste séparée par des virgules
 MAX_PAGES                              -> optionnel, sécurité (def. 30)
"""
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import requests
from bs4 import BeautifulSoup
BASE_URL = "https://www.inli.fr"
DEFAULT_LIST_URL = "https://www.inli.fr/locations/offres/"
SEARCH_URL = os.environ.get("SEARCH_URL", DEFAULT_LIST_URL).strip()
STATE_FILE = Path(__file__).parent / "state" / "seen_refs.json"
HEADERS = {
   "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}
# ---------- Config (lue depuis l'environnement) ----------
MAX_RENT = os.environ.get("MAX_RENT")
MIN_SURFACE = os.environ.get("MIN_SURFACE")
MIN_ROOMS = os.environ.get("MIN_ROOMS")
CITIES = [c.strip().lower() for c in os.environ.get("CITIES", "").split(",") if c.strip()]
MAX_PAGES = int(os.environ.get("MAX_PAGES", "30"))
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def build_page_url(page_num: int) -> str:
   if page_num == 1:
       return SEARCH_URL
   parts = urlsplit(SEARCH_URL)
   separator = "&" if parts.query else "?"
   new_query = f"{parts.query}{separator}page={page_num}" if parts.query else f"page={page_num}"
   return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))

def fetch_page(page_num: int) -> str:
   url = build_page_url(page_num)
   resp = requests.get(url, headers=HEADERS, timeout=20)
   resp.raise_for_status()
   return resp.text

def parse_listings(html: str):
   soup = BeautifulSoup(html, "html.parser")
   seen_refs_on_page = set()
   listings = []
   for a in soup.find_all("a", href=re.compile(r"/locations/offre/")):
       href = a.get("href", "")
       ref = href.rstrip("/").split("/")[-1]
       if not ref or ref in seen_refs_on_page:
           continue
       seen_refs_on_page.add(ref)
       text = a.get_text(" ", strip=True)
       price_match = re.search(r"([\d\s]{3,})\s*€", text)
       surface_match = re.search(r"([\d.,]+)\s*m²", text)
       rooms_match = re.search(r"(Studio|\d+)\s*pi[eè]ces?", text, re.IGNORECASE)
       city_match = re.match(r"^([A-ZÀ-Ü' \-]{2,})", text)
       listings.append(
           {
               "ref": ref,
               "url": href if href.startswith("http") else BASE_URL + href,
               "text": text,
               "price": price_match.group(1).replace(" ", "") if price_match else None,
               "surface": surface_match.group(1) if surface_match else None,
               "rooms": rooms_match.group(1) if rooms_match else None,
               "city": city_match.group(1).strip().title() if city_match else None,
           }
       )
   return listings

def matches_criteria(listing: dict) -> bool:
   if MAX_RENT and listing["price"]:
       try:
           if float(listing["price"]) > float(MAX_RENT):
               return False
       except ValueError:
           pass
   if MIN_SURFACE and listing["surface"]:
       try:
           surf = float(listing["surface"].replace(",", "."))
           if surf < float(MIN_SURFACE):
               return False
       except ValueError:
           pass
   if MIN_ROOMS and listing["rooms"]:
       rooms_val = 1 if listing["rooms"].lower() == "studio" else int(listing["rooms"])
       try:
           if rooms_val < int(MIN_ROOMS):
               return False
       except ValueError:
           pass
   if CITIES and listing["city"]:
       if listing["city"].lower() not in CITIES:
           return False
   return True

def load_state():
   """Retourne (seen_refs: set, initialized: bool).
   Le fichier est un objet {"initialized": bool, "seen_refs": [...]}.
   Un ancien format (juste une liste) est aussi accepté, pour compatibilité,
   et traité comme déjà initialisé.
   IMPORTANT: 'initialized' est stocké séparément du contenu de seen_refs,
   pour ne jamais confondre "0 annonce dispo en ce moment" (normal, filtre
   restrictif) avec "premier lancement jamais fait" (qui, lui, doit couper
   les notifications une seule fois, au tout début).
   """
   if not STATE_FILE.exists():
       return set(), False
   data = json.loads(STATE_FILE.read_text())
   if isinstance(data, list):
       return set(data), True
   return set(data.get("seen_refs", [])), bool(data.get("initialized", False))

def save_state(refs: set, initialized: bool = True):
   STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
   STATE_FILE.write_text(
       json.dumps(
           {"initialized": initialized, "seen_refs": sorted(refs)},
           ensure_ascii=False,
           indent=2,
       )
   )

def send_telegram(message: str):
   if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
       print("⚠️  Telegram non configuré, message non envoyé:\n", message)
       return
   url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
   resp = requests.post(
       url,
       data={
           "chat_id": TELEGRAM_CHAT_ID,
           "text": message,
           "disable_web_page_preview": False,
       },
       timeout=15,
   )
   if not resp.ok:
       print("Erreur envoi Telegram:", resp.status_code, resp.text, file=sys.stderr)

def main():
   seen_refs, initialized = load_state()
   is_first_run = not initialized
   all_listings = []
   for page in range(1, MAX_PAGES + 1):
       try:
           html = fetch_page(page)
       except requests.RequestException as e:
           print(f"Erreur réseau page {page}: {e}", file=sys.stderr)
           break
       listings = parse_listings(html)
       if not listings:
           break
       all_listings.extend(listings)
       time.sleep(1)
   current_refs = {l["ref"] for l in all_listings}
   new_refs = current_refs - seen_refs
   if is_first_run:
       print(f"Premier lancement : {len(current_refs)} annonce(s) enregistrée(s) comme référence, aucune notif envoyée.")
   else:
       new_listings = [l for l in all_listings if l["ref"] in new_refs]
       matching = [l for l in new_listings if matches_criteria(l)]
       print(f"{len(current_refs)} annonce(s) actuellement en ligne sous ce filtre.")
       print(f"{len(new_listings)} nouvelle(s) annonce(s) au total, {len(matching)} correspondant à tes critères.")
       for listing in matching:
           msg = (
               f"🏠 Nouvelle annonce in'li\n"
               f"{listing['city'] or ''}\n"
               f"{listing['rooms'] or '?'} pièce(s) · {listing['surface'] or '?'} m² · {listing['price'] or '?'} €\n"
               f"{listing['url']}"
           )
           send_telegram(msg)
   # 'initialized' passe (ou reste) à True après ce run, quel que soit le
   # nombre d'annonces actuellement en ligne (même 0).
   save_state(current_refs, initialized=True)

if __name__ == "__main__":
   main()
