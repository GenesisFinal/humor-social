"""
Cálculos matemáticos, ponderación y clasificación para el Índice de Humor Social Argentino (IHSA).
"""

from typing import List, Dict, Tuple
from engine.models import EmotionalAxesScores, SourceSentimentScore
from config import EMOTIONAL_AXES, MACRO_WEIGHTS, MEDIA_SOURCES

def calculate_source_composite(scores: EmotionalAxesScores) -> float:
    """
    Calcula el puntaje consolidado de una fuente en escala -100 a +100.
    Cada eje está entre -10 y +10, por lo que la suma ponderada multiplicada por 10
    produce un índice de -100 a +100.
    """
    weighted_sum = (
        scores.optimismo * EMOTIONAL_AXES["optimismo"]["weight"] +
        scores.calma * EMOTIONAL_AXES["calma"]["weight"] +
        scores.confianza * EMOTIONAL_AXES["confianza"]["weight"] +
        scores.alegria * EMOTIONAL_AXES["alegria"]["weight"]
    )
    # Escalar a [-100, 100]
    return round(float(weighted_sum * 10.0), 2)

def classify_ihsa(score: float) -> str:
    """Clasifica el índice numérico en una categoría cualitativa rigurosa."""
    if score >= 50.0:
        return "Euforia / Muy Alto Optimismo"
    elif score >= 20.0:
        return "Optimismo Moderado"
    elif score >= 5.0:
        return "Levemente Positivo / Esperanza"
    elif score >= -5.0:
        return "Neutro / Equilibrio"
    elif score >= -20.0:
        return "Levemente Negativo / Preocupación"
    elif score >= -50.0:
        return "Pesimismo y Tensión Moderada"
    else:
        return "Alarma / Crisis Emocional Colectiva"

def compute_daily_ihsa(
    source_evaluations: List[SourceSentimentScore],
    digital_scores: Dict[str, float]
) -> Tuple[float, EmotionalAxesScores, str]:
    """
    Calcula el IHSA global consolidado ponderando:
    1. Medios de prensa general y popular (50%)
    2. Medios económicos y de bolsillo (20%)
    3. Pulso digital y redes (Google Trends + X) (30%)
    """
    if not source_evaluations:
        neutral = EmotionalAxesScores(optimismo=0.0, calma=0.0, confianza=0.0, alegria=0.0)
        return 0.0, neutral, classify_ihsa(0.0)

    # Separar medios por categoría
    general_scores = []
    general_weights = []
    
    economy_scores = []
    economy_weights = []

    for eval_item in source_evaluations:
        src_meta = MEDIA_SOURCES.get(eval_item.source_id, {})
        category = src_meta.get("category", "general")
        weight = src_meta.get("weight", 0.10)

        if category == "economy":
            economy_scores.append(eval_item.composite_score)
            economy_weights.append(weight)
        else:
            general_scores.append(eval_item.composite_score)
            general_weights.append(weight)

    # Promedio ponderado de medios generales
    if general_scores:
        total_w = sum(general_weights) or 1.0
        avg_general = sum(s * (w / total_w) for s, w in zip(general_scores, general_weights))
    else:
        avg_general = 0.0

    # Promedio ponderado de medios económicos
    if economy_scores:
        total_w = sum(economy_weights) or 1.0
        avg_economy = sum(s * (w / total_w) for s, w in zip(economy_scores, economy_weights))
    else:
        avg_economy = avg_general

    # Pulso digital consolidado (X y Google Trends)
    digital_val = digital_scores.get("composite", 0.0)

    # Consolidación Macro
    ihsa_final = (
        avg_general * MACRO_WEIGHTS["media_headlines"] +
        avg_economy * MACRO_WEIGHTS["economy_headlines"] +
        digital_val * MACRO_WEIGHTS["digital_trends"]
    )
    ihsa_final = max(-100.0, min(100.0, round(ihsa_final, 2)))

    # Promedio de ejes individuales
    n_sources = len(source_evaluations)
    avg_axes = EmotionalAxesScores(
        optimismo=round(sum(e.scores.optimismo for e in source_evaluations) / n_sources, 2),
        calma=round(sum(e.scores.calma for e in source_evaluations) / n_sources, 2),
        confianza=round(sum(e.scores.confianza for e in source_evaluations) / n_sources, 2),
        alegria=round(sum(e.scores.alegria for e in source_evaluations) / n_sources, 2),
    )

    category_label = classify_ihsa(ihsa_final)
    return ihsa_final, avg_axes, category_label
