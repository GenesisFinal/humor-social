"""
Compilador del dataset central para el Tablero Web Online (GitHub Pages).
Extrae la base de datos SQLite y genera un archivo master_dataset.json ligero y optimizado.
"""

import json
from datetime import datetime
from pathlib import Path
from config import BASE_DIR, MEDIA_SOURCES, REPORTS_DIR
from storage.db import (
    get_available_dates,
    get_snapshot_by_date,
    get_source_evaluations,
    get_raw_headlines_for_date,
    get_historical_snapshots
)

def build_dataset() -> Path:
    target_file = BASE_DIR / "master_dataset.json"
    print("[BUILD] Extrayendo datos de SQLite para el tablero online...")

    dates = get_available_dates()
    snapshots_map = {}
    evaluations_map = {}
    headlines_map = {}

    for d in dates:
        snap = get_snapshot_by_date(d)
        if snap:
            # Parsear JSONs de trends si vienen serializados
            try:
                snap["top_trends_x"] = json.loads(snap.get("top_trends_x", "[]"))
            except Exception:
                pass
            try:
                snap["top_trends_google"] = json.loads(snap.get("top_trends_google", "[]"))
            except Exception:
                pass

            # Adjuntar reporte diario en markdown si existe
            rep_file = REPORTS_DIR / f"informe_{d}.md"
            if rep_file.exists():
                with open(rep_file, "r", encoding="utf-8") as rf:
                    snap["report_md"] = rf.read()
            else:
                snap["report_md"] = ""

            snapshots_map[d] = snap

        evals = get_source_evaluations(d)
        evaluations_map[d] = evals

        # Guardar titulares para el buscador
        heads = get_raw_headlines_for_date(d)
        headlines_map[d] = [
            {"s": h.get("source_id", ""), "n": h.get("source_name", ""), "t": h.get("title", ""), "u": h.get("url", "")}
            for h in heads
        ]

    history_series = get_historical_snapshots(days=60)

    dataset = {
        "metadata": {
            "title": "Índice de Humor Social Argentino (IHSA)",
            "updated_at": datetime.now().isoformat(),
            "latest_date": dates[0] if dates else None,
            "total_days": len(dates),
            "sources_count": len(MEDIA_SOURCES)
        },
        "media_catalog": MEDIA_SOURCES,
        "available_dates": dates,
        "snapshots": snapshots_map,
        "evaluations": evaluations_map,
        "headlines": headlines_map,
        "history_series": history_series
    }

    with open(target_file, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

    size_kb = target_file.stat().st_size / 1024
    print(f"[OK] master_dataset.json generado exitosamente ({size_kb:.1f} KB con {len(dates)} fechas).")
    return target_file

if __name__ == "__main__":
    build_dataset()
