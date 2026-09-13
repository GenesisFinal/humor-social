"""
Motor de análisis de sentimiento con rúbrica rigurosa para el Humor Social Argentino.
Soporta evaluación avanzada con Google Gemini (LLM) y motor heurístico argentino de respaldo.
"""

import json
import re
from typing import List, Dict, Any, Optional
from config import GEMINI_API_KEY, GEMINI_MODEL, MEDIA_SOURCES, EMOTIONAL_AXES
from engine.models import EmotionalAxesScores, SourceSentimentScore
from engine.scoring import calculate_source_composite

# Diccionario semántico específico para el contexto argentino (utilizado en modo autónomo/heurístico)
LEXICON_AR = {
    "optimismo_pos": [
        "crecimiento", "recuperación", "superávit", "inversión", "inversiones", "acuerdo",
        "récord", "baja la inflación", "desacelera la inflación", "suba de bonos", "baja riesgo país",
        "estabilidad", "crédito", "obra", "aprobado", "aumento de reservas", "aumento salarial"
    ],
    "optimismo_neg": [
        "crisis", "recesión", "caída", "estancamiento", "pobreza", "ajuste", "despidos", "quiebra",
        "incertidumbre", "déficit", "cae el consumo", "freno", "deuda", "conflicto", "alerta"
    ],
    "calma_pos": [
        "acuerdo", "diálogo", "paz", "consenso", "orden", "tranquilidad", "solución", "negociación",
        "levantan el paro", "conciliación", "normalidad", "descomprime"
    ],
    "calma_neg": [
        "paro", "huelga", "piquete", "marcha", "protesta", "tensión", "bronca", "furia", "represión",
        "violencia", "crimen", "inseguridad", "asesinato", "escándalo", "denuncia", "choque", "amenaza"
    ],
    "confianza_pos": [
        "estabilidad", "dólar calmo", "previsibilidad", "baja del dólar", "confianza", "certeza",
        "apoyo", "respaldo del fmi", "metas cumplidas", "garantía", "transparencia"
    ],
    "confianza_neg": [
        "corrida", "suba del dólar", "devaluación", "miedo", "riesgo país récord", "desconfianza",
        "fuga", "cepo", "falta de dólares", "desabastecimiento", "disparada", "descontrol"
    ],
    "alegria_pos": [
        "triunfo", "victoria", "campeón", "colapinto", "fórmula 1", "festejo", "gol", "premio",
        "orgullo", "reconocimiento", "fiesta", "medalla", "récord histórico", "alegría"
    ],
    "alegria_neg": [
        "muerte", "tragedia", "falleció", "duelo", "luto", "víctimas", "accidente fatal",
        "dolor", "conmoción", "masacre", "tristeza", "desgracia"
    ]
}

# Palabras clave de relleno, trucos domésticos y clickbait que NO inciden en el humor social nacional
JUNK_KEYWORDS = [
    "papel aluminio", "receta", "recetas", "truco casero", "trucos caseros", "cómo limpiar",
    "horóscopo", "signo", "zodíaco", "astrología", "viral", "look", "moda", "dieta",
    "belleza", "consejos para", "cómo hacer para", "descuentos", "ofertas", "farándula",
    "romance", "separación", "novia de", "novio de", "chimento", "astrológico"
]

# Palabras clave de alto impacto sociopolítico y económico
HIGH_IMPACT_KEYWORDS = [
    "milei", "gobierno", "dólar", "inflación", "jubilados", "salarios", "anses", "fmi",
    "congreso", "paso", "gobernadores", "precios", "tarifas", "justicia", "seguridad",
    "crimen", "colapinto", "fórmula 1", "selección", "pobreza", "bonos", "riesgo país",
    "reservas", "recesión", "marcha", "paro", "veto", "malvinas"
]

def filter_relevant_headlines(headlines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filtra titulares irrelevantes (recetas, trucos, horóscopos) y los ordena por relevancia de impacto."""
    cleaned = []
    for h in headlines:
        title = h.get("title", "")
        low = title.lower()
        # Descartar ruido evidente
        if any(junk in low for junk in JUNK_KEYWORDS):
            continue
        if len(title.strip()) < 22:
            continue

        # Asignar peso de relevancia
        weight = 1
        for kw in HIGH_IMPACT_KEYWORDS:
            if kw in low:
                weight += 2

        cleaned.append((weight, h))

    # Ordenar por mayor peso de impacto primero
    cleaned.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in cleaned]

def analyze_headlines_heuristic(
    source_id: str,
    source_name: str,
    headlines: List[Dict[str, Any]]
) -> SourceSentimentScore:
    """Evalúa los titulares usando análisis léxico contextual argentino con filtro de relevancia."""
    relevant_headlines = filter_relevant_headlines(headlines)
    if not relevant_headlines:
        relevant_headlines = headlines  # Fallback si todo fue filtrado

    titles = [h.get("title", "") for h in relevant_headlines]
    full_text = " ".join(titles).lower()
    
    pos_drivers = []
    neg_drivers = []
    
    # Evaluar eje por eje
    def evaluate_axis(pos_terms, neg_terms) -> float:
        pos_count = 0
        neg_count = 0
        for term in pos_terms:
            matches = [t for t in titles if term in t.lower()]
            if matches:
                pos_count += len(matches)
                for m in matches[:1]:
                    if m not in pos_drivers and len(pos_drivers) < 3:
                        pos_drivers.append(m)
                        
        for term in neg_terms:
            matches = [t for t in titles if term in t.lower()]
            if matches:
                neg_count += len(matches)
                for m in matches[:1]:
                    if m not in neg_drivers and len(neg_drivers) < 3:
                        neg_drivers.append(m)

        total = pos_count + neg_count
        if total == 0:
            return 0.0
        # Balance neto escalado a [-10, 10]
        net = (pos_count - neg_count) / max(total, 2) * 10.0
        return max(-10.0, min(10.0, round(net, 1)))

    opt = evaluate_axis(LEXICON_AR["optimismo_pos"], LEXICON_AR["optimismo_neg"])
    cal = evaluate_axis(LEXICON_AR["calma_pos"], LEXICON_AR["calma_neg"])
    conf = evaluate_axis(LEXICON_AR["confianza_pos"], LEXICON_AR["confianza_neg"])
    ale = evaluate_axis(LEXICON_AR["alegria_pos"], LEXICON_AR["alegria_neg"])

    # Extraer temas clave (palabras más frecuentes significativas)
    words = re.findall(r"\b[a-záéíóúñ]{4,}\b", full_text)
    stopwords = {"para", "como", "este", "esta", "sobre", "entre", "tras", "desde", "pero", "hacer", "todo", "diario", "noticias"}
    meaningful_words = [w for w in words if w not in stopwords]
    freq = {}
    for w in meaningful_words:
        freq[w] = freq.get(w, 0) + 1
    top_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:5]
    key_themes = [w[0].capitalize() for w in top_words]

    scores = EmotionalAxesScores(optimismo=opt, calma=cal, confianza=conf, alegria=ale)
    composite = calculate_source_composite(scores)
    category = MEDIA_SOURCES.get(source_id, {}).get("category", "general")

    justification = (
        f"Evaluación heurística de {len(titles)} titulares de {source_name}. "
        f"Se detectaron {len(pos_drivers)} focos positivos y {len(neg_drivers)} focos de preocupación o conflicto. "
        f"Temas dominantes: {', '.join(key_themes) if key_themes else 'Agenda mixta'}."
    )

    return SourceSentimentScore(
        source_id=source_id,
        source_name=source_name,
        category=category,
        scores=scores,
        composite_score=composite,
        key_themes=key_themes,
        positive_drivers=pos_drivers[:3],
        negative_drivers=neg_drivers[:3],
        editorial_bias_detected=f"Encuadre centrado en agenda {category}",
        justification=justification
    )

def analyze_source_with_llm(
    source_id: str,
    source_name: str,
    headlines: List[Dict[str, Any]],
    cover_image_path: Optional[str] = None
) -> SourceSentimentScore:
    """Evalúa los titulares y/o portada con Gemini si la API key está disponible."""
    if not GEMINI_API_KEY:
        return analyze_headlines_heuristic(source_id, source_name, headlines)

    titles_text = "\n".join([f"- {h.get('title', '')}" for h in headlines[:25]])
    prompt = f"""
Eres un sociólogo y analista de opinión pública experto en medios de comunicación argentinos.
Debes evaluar con máxima neutralidad, rigor y objetividad el HUMOR SOCIAL que transmiten los titulares de hoy de: {source_name}.

Titulares a evaluar:
{titles_text}

Rúbrica de evaluación rigurosa:
1. Optimismo vs. Pesimismo (-10.0 a +10.0): Esperanza, futuro, reactivación (+10) vs crisis sin salida, decadencia (-10).
2. Calma vs. Conflicto / Bronca (-10.0 a +10.0): Paz, acuerdos (+10) vs marchas, tensión, crispación, inseguridad (-10).
3. Confianza vs. Incertidumbre (-10.0 a +10.0): Previsibilidad, estabilidad (+10) vs miedo al dólar, devaluación, quiebra (-10).
4. Alegría vs. Tristeza (-10.0 a +10.0): Triunfos colectivos, orgullo (+10) vs duelo colectivo, tragedias, pérdidas (-10).

Responde EXCLUSIVAMENTE con un JSON válido con este formato exacto:
{{
  "optimismo": <float entre -10.0 y 10.0>,
  "calma": <float entre -10.0 y 10.0>,
  "confianza": <float entre -10.0 y 10.0>,
  "alegria": <float entre -10.0 y 10.0>,
  "key_themes": ["tema 1", "tema 2", "tema 3"],
  "positive_drivers": ["titular positivo 1"],
  "negative_drivers": ["titular negativo 1"],
  "editorial_bias_detected": "breve descripción del enfoque",
  "justification": "análisis conciso y fundamentado del humor transmitido"
}}
"""
    try:
        from google import genai
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        content_text = response.text.strip()
        # Limpiar markdown si vino encerrado en ```json
        content_text = re.sub(r"^```json\s*", "", content_text)
        content_text = re.sub(r"\s*```$", "", content_text)
        data = json.loads(content_text)

        scores = EmotionalAxesScores(
            optimismo=float(data["optimismo"]),
            calma=float(data["calma"]),
            confianza=float(data["confianza"]),
            alegria=float(data["alegria"])
        )
        composite = calculate_source_composite(scores)
        category = MEDIA_SOURCES.get(source_id, {}).get("category", "general")

        return SourceSentimentScore(
            source_id=source_id,
            source_name=source_name,
            category=category,
            scores=scores,
            composite_score=composite,
            key_themes=data.get("key_themes", []),
            positive_drivers=data.get("positive_drivers", []),
            negative_drivers=data.get("negative_drivers", []),
            editorial_bias_detected=data.get("editorial_bias_detected", ""),
            justification=data.get("justification", "")
        )
    except Exception as exc:
        print(f"[WARN] Falló el análisis LLM para {source_name} ({exc}). Aplicando análisis heurístico.")
        return analyze_headlines_heuristic(source_id, source_name, headlines)

def analyze_digital_trends(
    x_trends: List[Dict[str, Any]],
    google_trends: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Evalúa el humor reflejado en las tendencias de búsqueda y redes sociales."""
    terms = [x.get("term", "") for x in x_trends] + [g.get("term", "") for g in google_trends]
    text = " ".join(terms).lower()

    # Análisis de tendencias
    pos_score = 0
    neg_score = 0
    
    for category in ["optimismo_pos", "calma_pos", "confianza_pos", "alegria_pos"]:
        for word in LEXICON_AR[category]:
            if word in text:
                pos_score += 1
    for category in ["optimismo_neg", "calma_neg", "confianza_neg", "alegria_neg"]:
        for word in LEXICON_AR[category]:
            if word in text:
                neg_score += 1

    net_score = (pos_score - neg_score) * 10.0
    composite = max(-100.0, min(100.0, round(net_score, 2)))

    return {
        "composite": composite,
        "x_count": len(x_trends),
        "google_count": len(google_trends),
        "top_x": [x.get("term", "") for x in x_trends[:10]],
        "top_google": [g.get("term", "") for g in google_trends[:10]]
    }
