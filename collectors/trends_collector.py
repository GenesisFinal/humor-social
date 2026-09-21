"""
Recolector de tendencias en tiempo real para Argentina:
- Google Trends Argentina (búsquedas espontáneas)
- X / Twitter Argentina (temas de conversación e indignación/celebración en redes)
"""

import urllib.request
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict, Any
import re
import html
from config import DIGITAL_TRENDS_EXCLUSION_TERMS
from engine.analyzer import LOCAL_SPORTS_CLUBS, NATIONAL_SPORTS_REPRESENTATION

def is_excluded_trend(term: str, extra_text: str = "") -> bool:
    """Verifica si una tendencia corresponde a farándula, entretenimiento o partidos de fútbol doméstico (suma cero)."""
    combined = f"{term} {extra_text}".lower()
    
    # 1. Chequear términos de exclusión de farándula / entretenimiento
    if any(exc in combined for exc in DIGITAL_TRENDS_EXCLUSION_TERMS):
        return True

    # 2. Si es logro de representación nacional (Selección, Colapinto, Messi), NO excluir
    if any(nat in combined for nat in NATIONAL_SPORTS_REPRESENTATION):
        return False

    # 3. Excluir clubes de fútbol doméstico o liga local (suma cero)
    if any(club in combined for club in LOCAL_SPORTS_CLUBS):
        return True

    return False

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

def fetch_google_trends(max_items: int = 15) -> List[Dict[str, Any]]:
    """Descarga los temas con mayor aceleración de búsqueda en Google Argentina."""
    trends = []
    url = "https://trends.google.com/trending/rss?geo=AR"

    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)
        items = root.findall(".//item")

        for item in items[:max_items]:
            title_elem = item.find("title")
            title = title_elem.text.strip() if title_elem is not None and title_elem.text else ""

            # Tráfico aproximado (ej: 50K+)
            traffic_elem = item.find("{https://trends.google.com/trending/rss}approx_traffic")
            traffic = traffic_elem.text.strip() if traffic_elem is not None and traffic_elem.text else ""

            # Titular de noticia vinculada
            news_title = ""
            news_item = item.find("{https://trends.google.com/trending/rss}news_item")
            if news_item is not None:
                nt_elem = news_item.find("{https://trends.google.com/trending/rss}news_item_title")
                if nt_elem is not None and nt_elem.text:
                    news_title = html.unescape(nt_elem.text.strip())

            if title and not is_excluded_trend(title, news_title):
                trends.append({
                    "platform": "google_trends",
                    "term": title,
                    "traffic": traffic,
                    "related_headline": news_title,
                    "timestamp": datetime.now().isoformat(),
                    "channel": "digital_trends"
                })

    except Exception as exc:
        print(f"[WARN] Error al obtener Google Trends Argentina: {exc}")

    return trends

def fetch_x_trends(max_items: int = 25) -> List[Dict[str, Any]]:
    """Extrae los Trending Topics de X (Twitter) en Argentina a través de Trends24."""
    trends = []
    url = "https://trends24.in/argentina/"

    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as response:
            html_content = response.read()

        soup = BeautifulSoup(html_content, "html.parser")
        
        # Extraer los enlaces de tendencias directamente de la lista
        trend_links = soup.select(".trend-card__list li a")
        seen = set()
        for a_tag in trend_links:
            term = a_tag.text.strip()
            if term and term not in seen:
                seen.add(term)
                if is_excluded_trend(term):
                    continue

                li = a_tag.find_parent("li")
                span_count = li.find(class_=re.compile("count", re.I)) if li else None
                tweet_count = span_count.text.strip() if span_count else ""

                trends.append({
                    "platform": "x_twitter",
                    "term": term,
                    "tweet_count": tweet_count,
                    "timestamp": datetime.now().isoformat(),
                    "channel": "digital_trends"
                })

                if len(trends) >= max_items:
                    break

    except Exception as exc:
        print(f"[WARN] Error al obtener tendencias de X / Twitter Argentina: {exc}")

    return trends
