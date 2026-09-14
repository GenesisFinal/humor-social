"""
Cálculos matemáticos, ponderación y clasificación para el Índice de Humor Social Argentino (IHSA).
"""

from typing import List, Dict, Tuple, Any
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

def calculate_editorial_divergence(source_evaluations: List[SourceSentimentScore]) -> Tuple[float, str]:
    """
    Calcula el Índice de Brecha Editorial ("Brecha de Grieta"):
    Diferencia absoluta entre medios de línea tradicional/liberal (La Nación, Clarín, Infobae)
    y medios de línea crítica/oposición (Página/12, El Destape, C5N).
    Retorna: (brecha_pts, descripcion_estado)
    """
    trad_ids = {"lanacion", "clarin", "infobae"}
    crit_ids = {"pagina12", "eldestape", "c5n"}

    trad_scores = [e.composite_score for e in source_evaluations if e.source_id in trad_ids]
    crit_scores = [e.composite_score for e in source_evaluations if e.source_id in crit_ids]

    if trad_scores and crit_scores:
        avg_trad = sum(trad_scores) / len(trad_scores)
        avg_crit = sum(crit_scores) / len(crit_scores)
        gap = round(abs(avg_trad - avg_crit), 1)
        if gap >= 45.0:
            status = "Polarización Extrema (Grieta Activa)"
        elif gap >= 25.0:
            status = "Divergencia Editorial Moderada"
        else:
            status = "Consenso de Agenda General"
        return gap, status
    return 0.0, "Consenso de Agenda General"

def calculate_sports_decompression_buffer(
    axes_avg: EmotionalAxesScores,
    source_evaluations: List[SourceSentimentScore]
) -> float:
    """
    Calcula el Índice de Amortiguador Deportivo / Patriótico (Sports Decompression Buffer):
    Mide cuántos puntos netos de amortiguación o alivio emocional inyectan los logros patrios
    (ej. Colapinto en F1, Selección Argentina) respecto a la línea de base socioeconómica.
    """
    socioeconomic_baseline = (axes_avg.optimismo + axes_avg.confianza) / 2.0
    buffer = max(0.0, axes_avg.alegria - socioeconomic_baseline)
    return round(float(buffer), 1)

def compute_specialized_subindices(
    axes_avg: EmotionalAxesScores,
    source_evaluations: List[SourceSentimentScore],
    editorial_gap: float
) -> Dict[str, Any]:
    """
    Calcula los 3 subíndices temáticos estratégicos y el Termómetro de Estrés Colectivo:
    1. ICB: Clima de Bolsillo (-100 a +100)
    2. IGI: Gobernabilidad e Instituciones (-100 a +100)
    3. ICPS: Convivencia y Paz Social (-100 a +100)
    4. Estrés Colectivo (0 a 100)
    """
    opt = axes_avg.optimismo
    cal = axes_avg.calma
    conf = axes_avg.confianza

    # 1. Clima de Bolsillo (ICB)
    econ_scores = [e.composite_score for e in source_evaluations if e.category == "economy"]
    avg_econ = (sum(econ_scores) / len(econ_scores)) if econ_scores else ((opt + conf) * 5.0)
    icb = round(0.6 * avg_econ + 0.4 * ((conf * 0.5 + opt * 0.5) * 10.0), 1)
    icb = max(-100.0, min(100.0, icb))

    # 2. Gobernabilidad e Instituciones (IGI)
    trad_scores = [e.composite_score for e in source_evaluations if e.source_id in {"lanacion", "clarin", "perfil", "infobae"}]
    avg_trad = (sum(trad_scores) / len(trad_scores)) if trad_scores else ((conf * 0.6 + cal * 0.4) * 10.0)
    igi = round(0.5 * avg_trad + 0.5 * ((conf * 0.6 + cal * 0.4) * 10.0), 1)
    igi = max(-100.0, min(100.0, igi))

    # 3. Convivencia y Paz Social (ICPS)
    pop_scores = [e.composite_score for e in source_evaluations if e.category == "popular" or e.source_id in {"cronica", "cadena3", "tn"}]
    avg_pop = (sum(pop_scores) / len(pop_scores)) if pop_scores else (cal * 10.0)
    icps = round(0.6 * (cal * 10.0) + 0.4 * avg_pop, 1)
    icps = max(-100.0, min(100.0, icps))

    # 4. Termómetro de Estrés Colectivo (0 a 100)
    calm_penalty = max(0.0, -cal) * 4.0
    conf_penalty = max(0.0, -conf) * 3.0
    grieta_penalty = min(30.0, editorial_gap * 0.6)
    stress = min(100.0, max(0.0, round(calm_penalty + conf_penalty + grieta_penalty, 1)))

    if stress < 25.0:
        stress_cat = "Calma Cívica / Distensión"
        stress_badge = "🟢 Distensión"
        stress_color = "emerald"
    elif stress < 50.0:
        stress_cat = "Tensión Latente / Cautela"
        stress_badge = "🟡 Cautela"
        stress_color = "yellow"
    elif stress < 75.0:
        stress_cat = "Crispación Activa / Alerta"
        stress_badge = "🟠 Alerta Activa"
        stress_color = "orange"
    else:
        stress_cat = "Ebullición / Alarma Colectiva"
        stress_badge = "🔴 Alarma Social"
        stress_color = "rose"

    return {
        "icb": icb,
        "igi": igi,
        "icps": icps,
        "stress": stress,
        "stress_category": stress_cat,
        "stress_badge": stress_badge,
        "stress_color": stress_color
    }
