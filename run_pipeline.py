"""
Script orquestador principal del Índice de Humor Social Argentino (IHSA).
Ejecuta la ingesta de las 10 fuentes, Google Trends, X, tapas impresas,
calcula el índice ponderado y almacena los resultados en la base de datos.
"""

import argparse
from datetime import date, datetime, timezone, timedelta
from typing import Dict, List, Any

# Zona horaria oficial de la República Argentina (ART = UTC-3)
ART_TIMEZONE = timezone(timedelta(hours=-3))

from config import MEDIA_SOURCES, DB_PATH
from collectors.rss_collector import fetch_rss_feed
from collectors.web_collector import fetch_portal_headlines
from collectors.trends_collector import fetch_google_trends, fetch_x_trends
from collectors.covers_collector import download_all_front_pages
from engine.analyzer import analyze_source_with_llm, analyze_digital_trends
from engine.scoring import compute_daily_ihsa
from engine.models import DailySnapshot, EmotionalAxesScores, SourceSentimentScore
from storage.db import init_db, save_snapshot

def run_pipeline(target_date_str: str = None) -> DailySnapshot:
    """Ejecuta el ciclo diario completo del IHSA fijando siempre la hora oficial de Argentina."""
    if target_date_str:
        today = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    else:
        # Calcular fecha en hora de Argentina independientemente del huso horario del servidor
        today = datetime.now(ART_TIMEZONE).date()
    date_str = today.isoformat()

    print(f"\n=======================================================")
    print(f"  ÍNDICE DE HUMOR SOCIAL ARGENTINO (IHSA) - {date_str} ")
    print(f"=======================================================\n")

    init_db()

    # 1. Recolección de Tapas de Diarios
    print("[1/4] Descargando tapas de diarios impresos...")
    covers_map = download_all_front_pages(target_date=today)
    print(f"      -> {len(covers_map)} tapas descargadas exitosamente.")

    # 2. Recolección de Titulares de Medios
    print("\n[2/4] Recolectando titulares de los 10 medios principales...")
    raw_items_by_source: Dict[str, List[Dict[str, Any]]] = {}

    for source_id, meta in MEDIA_SOURCES.items():
        name = meta["name"]
        rss_url = meta.get("rss")
        web_url = meta.get("web")

        items = []
        if rss_url:
            items = fetch_rss_feed(source_id, name, rss_url, max_items=25)
        
        # Si RSS no arrojó o no tiene, usar scraper web
        if not items and web_url:
            items = fetch_portal_headlines(source_id, name, web_url, max_items=25)

        raw_items_by_source[source_id] = items
        print(f"      [{name}] {len(items)} titulares obtenidos.")

    # 3. Recolección de Tendencias Digitales (X y Google Trends)
    print("\n[3/4] Monitoreando pulso de redes sociales y búsquedas...")
    x_trends = fetch_x_trends(max_items=25)
    g_trends = fetch_google_trends(max_items=15)
    print(f"      -> {len(x_trends)} tendencias en X / Twitter.")
    print(f"      -> {len(g_trends)} temas en Google Trends Argentina.")

    # 4. Análisis Analítico y Ponderación
    print("\n[4/4] Procesando análisis de sentimiento y cálculo del índice...")
    source_evaluations: List[SourceSentimentScore] = []

    for source_id, items in raw_items_by_source.items():
        meta = MEDIA_SOURCES[source_id]
        name = meta["name"]
        cover_path = covers_map.get(source_id)

        if items:
            score_obj = analyze_source_with_llm(
                source_id=source_id,
                source_name=name,
                headlines=items,
                cover_image_path=cover_path
            )
            source_evaluations.append(score_obj)
            print(f"      -> {name}: {score_obj.composite_score:+0.1f} ({score_obj.scores.optimismo:+0.1f} Opt, {score_obj.scores.calma:+0.1f} Cal)")

    digital_analysis = analyze_digital_trends(x_trends, g_trends)
    print(f"      -> Pulso Digital (Redes): {digital_analysis['composite']:+0.1f}")

    # Cálculo consolidado
    ihsa_score, axes_avg, category_label = compute_daily_ihsa(
        source_evaluations=source_evaluations,
        digital_scores=digital_analysis
    )

    summary_text = (
        f"El Humor Social del día se ubica en {ihsa_score:+0.1f} pts ({category_label}). "
        f"Ejes promedio: Optimismo {axes_avg.optimismo:+0.1f}, Calma {axes_avg.calma:+0.1f}, "
        f"Confianza {axes_avg.confianza:+0.1f}, Alegría {axes_avg.alegria:+0.1f}."
    )

    snapshot = DailySnapshot(
        date=date_str,
        ihsa_score=ihsa_score,
        ihsa_category=category_label,
        axes_averages=axes_avg,
        sources=source_evaluations,
        top_trends_x=[x.get("term", "") for x in x_trends[:10]],
        top_trends_google=[g.get("term", "") for g in g_trends[:10]],
        summary_of_the_day=summary_text
    )

    # Guardar en Base de Datos
    save_snapshot(snapshot, raw_items_by_source, covers_map)

    # Generar informe ejecutivo diario (Fase 2 y 3)
    from storage.db import get_previous_snapshot
    from engine.reports import generate_daily_report
    prev_snap = get_previous_snapshot(date_str)
    report_md = generate_daily_report(snapshot, prev_snap)

    print("\n=======================================================")
    print(f"  RESULTADO FINAL IHSA: {ihsa_score:+0.1f} / 100")
    print(f"  ESTADO: {category_label}")
    print(f"  Base de datos actualizada en: {DB_PATH}")
    print(f"  Boletín diario generado en: data/reports/informe_{date_str}.md")
    print("=======================================================\n")

    return snapshot

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ejecutar medición del Índice de Humor Social Argentino")
    parser.add_argument("--date", type=str, help="Fecha en formato YYYY-MM-DD (por defecto hoy)", default=None)
    args = parser.parse_args()

    run_pipeline(args.date)
