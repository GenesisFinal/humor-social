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

    from engine.analyzer import is_irrelevant_or_foreign_headline, is_local_sports_headline

    for d in dates:
        snap = get_snapshot_by_date(d)
        evals = get_source_evaluations(d)

        # Sanitizar retroactivamente drivers para eliminar noticias foráneas o clickbait
        for e in evals:
            if "positive_drivers" in e and isinstance(e["positive_drivers"], list):
                e["positive_drivers"] = [
                    t for t in e["positive_drivers"]
                    if not is_irrelevant_or_foreign_headline(t) and not is_local_sports_headline(t)
                ]
            if "negative_drivers" in e and isinstance(e["negative_drivers"], list):
                e["negative_drivers"] = [
                    t for t in e["negative_drivers"]
                    if not is_irrelevant_or_foreign_headline(t)
                ]

        evaluations_map[d] = evals

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

            # Calcular brecha editorial y amortiguador patriótico retroactivamente si no existen
            trad_ids = {"lanacion", "clarin", "infobae"}
            crit_ids = {"pagina12", "eldestape", "c5n"}
            trad_scores = [e["composite_score"] for e in evals if e.get("source_id") in trad_ids]
            crit_scores = [e["composite_score"] for e in evals if e.get("source_id") in crit_ids]
            gap = 0.0
            if trad_scores and crit_scores:
                gap = round(abs((sum(trad_scores)/len(trad_scores)) - (sum(crit_scores)/len(crit_scores))), 1)

            opt = snap.get("optimismo", 0.0)
            conf = snap.get("confianza", 0.0)
            ale = snap.get("alegria", 0.0)
            base_socio = (opt + conf) / 2.0
            buff = round(max(0.0, ale - base_socio), 1)

            snap["editorial_divergence"] = gap
            snap["decompression_buffer"] = buff

            # 3 Subíndices Especializados y Termómetro de Estrés Colectivo
            from engine.scoring import compute_specialized_subindices
            from engine.models import EmotionalAxesScores
            axes_obj = EmotionalAxesScores(
                optimismo=snap.get("optimismo", 0.0),
                calma=snap.get("calma", 0.0),
                confianza=snap.get("confianza", 0.0),
                alegria=snap.get("alegria", 0.0)
            )
            # Recrear SourceSentimentScore mínimos para el cálculo si hace falta
            from engine.models import SourceSentimentScore
            eval_objs = [
                SourceSentimentScore(
                    source_id=e.get("source_id", ""),
                    source_name=e.get("source_name", ""),
                    category=e.get("category", "general"),
                    scores=EmotionalAxesScores(
                        optimismo=e.get("optimismo", 0.0),
                        calma=e.get("calma", 0.0),
                        confianza=e.get("confianza", 0.0),
                        alegria=e.get("alegria", 0.0)
                    ),
                    composite_score=e.get("composite_score", 0.0),
                    key_themes=e.get("key_themes", []),
                    positive_drivers=e.get("positive_drivers", []),
                    negative_drivers=e.get("negative_drivers", []),
                    editorial_bias_detected="",
                    justification=e.get("justification", "")
                )
                for e in evals
            ]
            subindices_data = compute_specialized_subindices(axes_obj, eval_objs, gap)
            snap.update(subindices_data)

            # Adjuntar tapas impresas si existen en disco
            covers_dir = BASE_DIR / "data" / "covers" / d
            covers_list = []
            if covers_dir.exists():
                for cf in sorted(covers_dir.iterdir()):
                    if cf.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
                        src_id = cf.stem.lower()
                        src_meta = MEDIA_SOURCES.get(src_id, {})
                        covers_list.append({
                            "source_id": src_id,
                            "name": src_meta.get("name", src_id.capitalize()),
                            "path": f"data/covers/{d}/{cf.name}"
                        })
            snap["covers"] = covers_list

            # Adjuntar reporte diario en markdown si existe
            rep_file = REPORTS_DIR / f"informe_{d}.md"
            if rep_file.exists():
                with open(rep_file, "r", encoding="utf-8") as rf:
                    snap["report_md"] = rf.read()
            else:
                snap["report_md"] = ""

            snapshots_map[d] = snap

        # Guardar titulares para el buscador
        heads = get_raw_headlines_for_date(d)
        headlines_map[d] = [
            {"s": h.get("source_id", ""), "n": h.get("source_name", ""), "t": h.get("title", ""), "u": h.get("url", "")}
            for h in heads
        ]

    # Enriquecer serie histórica con los nuevos subíndices
    raw_history = get_historical_snapshots(days=60)
    history_series = []
    for h in raw_history:
        d = h.get("date")
        s = snapshots_map.get(d, {})
        h_copy = dict(h)
        h_copy["editorial_divergence"] = s.get("editorial_divergence", 0.0)
        h_copy["decompression_buffer"] = s.get("decompression_buffer", 0.0)
        h_copy["icb"] = s.get("icb", 0.0)
        h_copy["igi"] = s.get("igi", 0.0)
        h_copy["icps"] = s.get("icps", 0.0)
        h_copy["stress"] = s.get("stress", 0.0)
        history_series.append(h_copy)

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
