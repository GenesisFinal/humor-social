"""
Descargador de tapas de diarios argentinos en alta resolución para análisis multimodal y visualización.
"""

import urllib.request
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Optional
from config import COVERS_DIR, MEDIA_SOURCES

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_cover_url(cover_code: str, target_date: date, high_res: bool = True) -> str:
    """Genera la URL esperada de la portada en Kiosko.net."""
    year = target_date.strftime("%Y")
    month = target_date.strftime("%m")
    day = target_date.strftime("%d")
    resolution = "750" if high_res else "200"
    return f"https://img.kiosko.net/{year}/{month}/{day}/ar/{cover_code}.{resolution}.jpg"

def download_front_page(source_id: str, cover_code: str, target_date: Optional[date] = None) -> Optional[Path]:
    """Descarga la portada del diario para la fecha indicada."""
    if not cover_code:
        return None

    if target_date is None:
        target_date = date.today()

    date_dir = COVERS_DIR / target_date.isoformat()
    date_dir.mkdir(parents=True, exist_ok=True)
    target_file = date_dir / f"{source_id}.jpg"

    # Si ya fue descargada hoy, reutilizarla
    if target_file.exists() and target_file.stat().st_size > 1000:
        return target_file

    url = get_cover_url(cover_code, target_date, high_res=True)

    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                data = response.read()
                if len(data) > 5000:
                    with open(target_file, "wb") as f:
                        f.write(data)
                    return target_file
    except Exception as exc:
        # Intento con baja resolución si la de alta falló
        try:
            fallback_url = get_cover_url(cover_code, target_date, high_res=False)
            req = urllib.request.Request(fallback_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=8) as response:
                if response.status == 200:
                    data = response.read()
                    if len(data) > 2000:
                        with open(target_file, "wb") as f:
                            f.write(data)
                        return target_file
        except Exception:
            pass
        # Silencioso o log suave
        # print(f"[INFO] Tapa no disponible para {source_id} en fecha {target_date}: {exc}")

    return None

def download_all_front_pages(target_date: Optional[date] = None) -> Dict[str, str]:
    """Descarga todas las tapas disponibles para la canasta de medios y retorna sus rutas."""
    downloaded = {}
    for source_id, meta in MEDIA_SOURCES.items():
        cover_code = meta.get("cover_code")
        if cover_code:
            file_path = download_front_page(source_id, cover_code, target_date)
            if file_path:
                downloaded[source_id] = str(file_path)
    return downloaded
