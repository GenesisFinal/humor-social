"""
Recolector de noticias a través de canales RSS estándar de medios argentinos.
"""

import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Any
import html
import re

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

def clean_html(raw_html: str) -> str:
    """Elimina etiquetas HTML y limpia entidades de texto."""
    if not raw_html:
        return ""
    clean = re.sub(r"<[^>]+>", "", raw_html)
    return html.unescape(clean).strip()

def fetch_rss_feed(source_id: str, source_name: str, rss_url: str, max_items: int = 25) -> List[Dict[str, Any]]:
    """Descarga y parsea un feed RSS, retornando una lista de titulares estandarizados."""
    items = []
    if not rss_url:
        return items

    try:
        req = urllib.request.Request(rss_url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=12) as response:
            xml_data = response.read()

        root = ET.fromstring(xml_data)
        
        # Soportar RSS 2.0 y Atom
        xml_items = root.findall(".//item")
        if not xml_items:
            xml_items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

        for elem in xml_items[:max_items]:
            title_elem = elem.find("title")
            if title_elem is None:
                title_elem = elem.find("{http://www.w3.org/2005/Atom}title")
            
            title = clean_html(title_elem.text) if title_elem is not None and title_elem.text else ""
            if not title or len(title) < 10:
                continue

            link_elem = elem.find("link")
            if link_elem is not None:
                link = link_elem.text if link_elem.text else link_elem.get("href", "")
            else:
                link = ""

            desc_elem = elem.find("description")
            if desc_elem is None:
                desc_elem = elem.find("{http://www.w3.org/2005/Atom}summary")
            summary = clean_html(desc_elem.text) if desc_elem is not None and desc_elem.text else ""

            pub_date_elem = elem.find("pubDate")
            if pub_date_elem is None:
                pub_date_elem = elem.find("{http://www.w3.org/2005/Atom}updated")
            pub_date = pub_date_elem.text.strip() if pub_date_elem is not None and pub_date_elem.text else datetime.now().isoformat()
            position_rank = len(items) + 1

            items.append({
                "source_id": source_id,
                "source_name": source_name,
                "title": title,
                "summary": summary[:300] if summary else "",
                "url": link,
                "published_at": pub_date,
                "channel": "rss",
                "position_rank": position_rank
            })

    except Exception as exc:
        print(f"[WARN] Error al obtener RSS de {source_name} ({rss_url}): {exc}")

    return items
