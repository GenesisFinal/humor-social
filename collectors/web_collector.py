"""
Scraper web ligero y resiliente para portales de noticias argentinos sin RSS activo.
"""

import urllib.request
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Any
from urllib.parse import urljoin
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
}

def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()

def fetch_portal_headlines(source_id: str, source_name: str, web_url: str, max_items: int = 25) -> List[Dict[str, Any]]:
    """Extrae los titulares principales directamente de la portada web del medio."""
    items = []
    seen_titles = set()

    try:
        req = urllib.request.Request(web_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=12) as response:
            html_content = response.read()

        soup = BeautifulSoup(html_content, "html.parser")

        # Buscar elementos candidatos a titulares
        candidate_tags = soup.find_all(["h1", "h2", "h3", "article"])

        for tag in candidate_tags:
            # Buscar texto del titular
            title_text = ""
            link_url = ""

            if tag.name == "article":
                h = tag.find(["h1", "h2", "h3"])
                if h:
                    title_text = clean_text(h.text)
                a = tag.find("a")
                if a and a.get("href"):
                    link_url = a["href"]
            else:
                title_text = clean_text(tag.text)
                a = tag.find("a") or tag.find_parent("a")
                if a and a.get("href"):
                    link_url = a["href"]

            # Filtrar titulares vacíos, muy cortos o típicos botones de navegación
            if not title_text or len(title_text) < 18 or len(title_text) > 250:
                continue

            # Filtrar palabras irrelevantes de navegación
            low = title_text.lower()
            if any(junk in low for junk in ["iniciar sesión", "suscribite", "últimas noticias", "términos y condiciones", "copyright", "todos los derechos reservados", "newsletter"]):
                continue

            if title_text in seen_titles:
                continue

            seen_titles.add(title_text)
            full_url = urljoin(web_url, link_url) if link_url else web_url

            items.append({
                "source_id": source_id,
                "source_name": source_name,
                "title": title_text,
                "summary": "",
                "url": full_url,
                "published_at": datetime.now().isoformat(),
                "channel": "web_scrape"
            })

            if len(items) >= max_items:
                break

    except Exception as exc:
        print(f"[WARN] Error al scrapear portal de {source_name} ({web_url}): {exc}")

    return items
