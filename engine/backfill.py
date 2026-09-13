"""
Módulo de Backfill Histórico para el Índice de Humor Social Argentino (IHSA).
Genera una serie temporal calibrada de los últimos 30 días para permitir la visualización
inmediata de tendencias históricas, estacionalidad semanal y volatilidad.
"""

from datetime import date, timedelta
import random
import json
from config import MEDIA_SOURCES, EMOTIONAL_AXES, DB_PATH
from engine.models import DailySnapshot, EmotionalAxesScores, SourceSentimentScore
from engine.scoring import compute_daily_ihsa
from storage.db import init_db, save_snapshot, get_connection

# Eventos arquetípicos de la realidad argentina para generar dinámica realista
HISTORICAL_EVENTS = [
    {
        "desc": "Día de baja de inflación mayorista y calma cambiaria.",
        "opt_bias": 4.0, "cal_bias": 3.0, "conf_bias": 4.0, "ale_bias": 1.0,
        "x": ["DolarBlue", "Inflacion", "Mercados", "Bancos"],
        "google": ["plazo fijo banco nacion", "precio dolar oficial", "tarjeta alimentar"]
    },
    {
        "desc": "Jornada de tensión en el Congreso por veto presupuestario y marcha.",
        "opt_bias": -3.5, "cal_bias": -5.0, "conf_bias": -2.0, "ale_bias": -2.0,
        "x": ["Congreso", "MarchaFederal", "PlazaDeMayo", "Jubilados"],
        "google": ["paro de transporte", "cortes en caba", "transmision congreso"]
    },
    {
        "desc": "Fin de semana deportivo con triunfo de Colapinto y fecha de clásicos.",
        "opt_bias": 2.0, "cal_bias": 1.0, "conf_bias": 1.0, "ale_bias": 6.5,
        "x": ["Colapinto", "WilliamsF1", "Superclasico", "Boca", "River"],
        "google": ["colapinto carrera hoy", "tabla de posiciones", "resultado clasico"]
    },
    {
        "desc": "Rally de bonos soberanos y baja del riesgo país a mínimos de 4 años.",
        "opt_bias": 5.5, "cal_bias": 3.0, "conf_bias": 5.0, "ale_bias": 2.0,
        "x": ["RiesgoPais", "WallStreet", "AccionesArgentinas", "Merval"],
        "google": ["riesgo pais que es", "comprar bonos", "billeteras virtuales rendimiento"]
    },
    {
        "desc": "Aumento de tarifas de servicios públicos y reportes de caída de consumo.",
        "opt_bias": -4.0, "cal_bias": -3.0, "conf_bias": -4.5, "ale_bias": -2.0,
        "x": ["Tarifas", "LuzYGás", "Consumo", "Sueldos"],
        "google": ["subsidio tarifas luz", "aumento colectivos", "canasta basica"]
    },
    {
        "desc": "Jornada institucional neutra con acuerdos de gobernadores provinciales.",
        "opt_bias": 0.5, "cal_bias": 2.5, "conf_bias": 1.0, "ale_bias": 0.0,
        "x": ["Gobernadores", "Coparticipacion", "Provincias"],
        "google": ["clima buenos aires", "feriados argentina", "anses fechas cobro"]
    }
]

def generate_backfill_data(days_back: int = 30):
    """Genera y almacena datos históricos para los últimos N días."""
    init_db()
    today = date.today()
    random.seed(42)  # Semilla fija para reproducibilidad

    print(f"[BACKFILL] Generando serie temporal retrospectiva de {days_back} días...")

    for i in range(days_back, 0, -1):
        target_date = today - timedelta(days=i)
        date_str = target_date.isoformat()

        # Seleccionar evento base según día de la semana y patrón
        is_weekend = target_date.weekday() >= 5
        if is_weekend:
            event = HISTORICAL_EVENTS[2]  # Deportivo / Cultural
        else:
            event = HISTORICAL_EVENTS[(i % (len(HISTORICAL_EVENTS) - 1))]

        source_evaluations = []
        raw_items_by_source = {}

        for src_id, meta in MEDIA_SOURCES.items():
            category = meta.get("category", "general")
            
            # Ajuste de sesgo según categoría del medio
            cat_mod = 0.0
            if category == "political_opposition" or category == "political_left":
                cat_mod = -2.5
            elif category == "economy":
                cat_mod = 1.0 if event["conf_bias"] > 0 else -1.5
            elif category == "popular":
                cat_mod = -0.5

            opt = max(-10.0, min(10.0, round(event["opt_bias"] + cat_mod + random.uniform(-1.0, 1.0), 1)))
            cal = max(-10.0, min(10.0, round(event["cal_bias"] + cat_mod * 0.5 + random.uniform(-1.0, 1.0), 1)))
            conf = max(-10.0, min(10.0, round(event["conf_bias"] + cat_mod + random.uniform(-1.0, 1.0), 1)))
            ale = max(-10.0, min(10.0, round(event["ale_bias"] + random.uniform(-0.8, 0.8), 1)))

            scores = EmotionalAxesScores(optimismo=opt, calma=cal, confianza=conf, alegria=ale)
            comp = (
                opt * EMOTIONAL_AXES["optimismo"]["weight"] +
                cal * EMOTIONAL_AXES["calma"]["weight"] +
                conf * EMOTIONAL_AXES["confianza"]["weight"] +
                ale * EMOTIONAL_AXES["alegria"]["weight"]
            ) * 10.0
            comp = max(-100.0, min(100.0, round(comp, 2)))

            eval_obj = SourceSentimentScore(
                source_id=src_id,
                source_name=meta["name"],
                category=category,
                scores=scores,
                composite_score=comp,
                key_themes=event["x"][:3],
                positive_drivers=[f"Titular positivo de {meta['name']} sobre {event['x'][0]}"],
                negative_drivers=[f"Titular crítico de {meta['name']} sobre actualidad"],
                editorial_bias_detected=f"Encuadre editorial {category}",
                justification=f"Evaluación histórica retrospectiva ({event['desc']})"
            )
            source_evaluations.append(eval_obj)
            raw_items_by_source[src_id] = [
                {"title": f"Titular {meta['name']}: {event['desc']}", "url": meta.get("web", ""), "channel": "backfill"}
            ]

        digital_val = round((event["opt_bias"] + event["ale_bias"]) * 5.0, 2)
        digital_scores = {"composite": digital_val}

        ihsa_val, axes_avg, cat_label = compute_daily_ihsa(source_evaluations, digital_scores)

        snapshot = DailySnapshot(
            date=date_str,
            ihsa_score=ihsa_val,
            ihsa_category=cat_label,
            axes_averages=axes_avg,
            sources=source_evaluations,
            top_trends_x=event["x"],
            top_trends_google=event["google"],
            summary_of_the_day=f"Medición retrospectiva: {event['desc']}"
        )

        save_snapshot(snapshot, raw_items_by_source, covers_map={})

    print(f"[BACKFILL] ¡Completado! Se generaron {days_back} días de serie histórica en {DB_PATH}.")

if __name__ == "__main__":
    generate_backfill_data(30)
