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

import unicodedata

def normalize_text(text: str) -> str:
    """Elimina tildes y normaliza a minúsculas para matching léxico robusto."""
    nfkd = unicodedata.normalize('NFKD', text)
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).lower()

# Gramática de vectores direccionales: matrices de Sujeto x Dirección (Solución General)
DIRECTIONAL_METRICS = {
    # Métricas que al SUBIR generan CRISPACIÓN / ANGUSTIA y al BAJAR generan ALIVIO
    "adverse_indicators": [
        "inflacion", "mora", "morosidad", "pobreza", "indigencia", "desempleo", "despidos",
        "tarifas", "riesgo pais", "dolar blue", "brecha cambiaria", "deuda", "deficit",
        "inseguridad", "homicidios", "delitos", "embargo", "cheques rechazados", "precios"
    ],
    # Métricas que al SUBIR generan ESPERANZA / ALIVIO y al BAJAR generan ANGUSTIA
    "virtuous_indicators": [
        "salarios", "jubilaciones", "reservas", "superavit", "credito", "creditos",
        "empleo", "inversion", "inversiones", "exportaciones", "produccion", "bonos",
        "actividad economica", "consumo"
    ],
    # Vectores de suba / aumento / crecimiento
    "up_vectors": [
        "sub", "aument", "crec", "record", "dispar", "trep", "alza", "escalad", "alcanz", "escalo", "maximo"
    ],
    # Vectores de caída / desaceleración / freno
    "down_vectors": [
        "baj", "cae", "caen", "cayo", "cayeron", "caida", "desaceler", "perfor", "retroced", "fren", "desplom", "derrumb", "minimo"
    ],
    # Modificadores de negación / freno que invierten polaridad
    "negation_modifiers": [
        "no cede", "no baja", "no frena", "sin freno", "lejos de", "no alcanza", "freno a", "traba", "sin piso"
    ]
}

def evaluate_headline_vector(title: str) -> tuple[float, str]:
    """
    Evalúa vectorialmente un titular aplicando álgebra de polaridad contextual:
    - Indicador Adverso + Suba = Negativo (-1.0)
    - Indicador Adverso + Baja = Positivo (+1.0)
    - Indicador Virtuoso + Suba = Positivo (+1.0)
    - Indicador Virtuoso + Baja = Negativo (-1.0)
    - Inversiones por modificadores de negación ('no cede', 'sin freno').
    Retorna: (impacto_neto_float, razon_o_categoria)
    """
    low = normalize_text(title)

    # Caso especial: alerta de morosidad o endeudamiento en familias
    if ("mora" in low or "morosidad" in low or "incumplimiento" in low) and ("credito" in low or "familia" in low or "banco" in low):
        return -1.0, "alerta_financiera_familiar"

    # Modificadores de negación
    has_negation = any(neg in low for neg in DIRECTIONAL_METRICS["negation_modifiers"])

    has_up = any(re.search(r"\b" + v, low) for v in DIRECTIONAL_METRICS["up_vectors"])
    has_down = any(re.search(r"\b" + v, low) for v in DIRECTIONAL_METRICS["down_vectors"])

    is_adverse = any(m in low for m in DIRECTIONAL_METRICS["adverse_indicators"])
    is_virtuous = any(m in low for m in DIRECTIONAL_METRICS["virtuous_indicators"])

    score = 0.0

    # Conflicto mixto (ej. salarios vs inflación): la relación de caída prima
    if is_virtuous and has_down:
        return -1.0, "caida_de_variable_virtuosa"

    if is_adverse:
        if has_up or has_negation:
            score = -1.0  # Sube la inflación, mora, pobreza o no cede
        elif has_down:
            score = 1.0   # Cae la inflación, mora, riesgo país

    elif is_virtuous:
        if has_up and not has_negation:
            score = 1.0   # Suben los salarios, reservas, créditos
        elif has_down or has_negation:
            score = -1.0  # Caen los salarios, empleo, reservas

    return score, "vectorial"

# Clubes y torneos de fútbol local (Juegos de suma cero: alegría de unos es tristeza de otros)
LOCAL_SPORTS_CLUBS = [
    "boca", "river", "independiente", "racing", "san lorenzo", "rosario central",
    "newell's", "newells", "talleres", "belgrano", "instituto", "velez", "estudiantes",
    "gimnasia", "huracan", "lanus", "banfield", "argentinos juniors", "tigre", "platense",
    "union", "colon", "godoy cruz", "central cordoba", "barracas", "riestra", "defensa y justicia",
    "liga profesional", "copa argentina", "nacional b", "primera nacional", "federal a"
]

# Logros patrios / Hitos de representación nacional unívoca (Unen a todo el país)
NATIONAL_SPORTS_REPRESENTATION = [
    "colapinto", "franco colapinto", "fórmula 1", "formula 1", "williams",
    "selección argentina", "seleccion argentina", "la scaloneta", "messi", "lionel messi",
    "leonas", "gladiadores", "oro olímpico", "medalla olímpica", "campeón del mundo", "copa américa"
]

# Matriz jerárquica de impacto y severidad poblacional (Weighting Tiers)
HIERARCHICAL_IMPACT_TIERS = {
    # TIER 1: Catástrofes masivas, atentados, crisis institucional extrema (Afectación existencial / duelo nacional)
    "tier_1_catastrophes": {
        "weight": 5.0,
        "keywords": [
            "explosión", "explosion", "atentado", "masacre", "tragedia aérea", "derrumbe",
            "terremoto", "inundación masiva", "decenas de muertos", "múltiples víctimas",
            "golpe de estado", "estado de sitio", "corrida bancaria", "hiperinflación"
        ]
    },
    # TIER 2: Bolsillo directo y subsistencia familiar (Afecta al 100% de la población)
    "tier_2_pocket_economy": {
        "weight": 3.5,
        "keywords": [
            "inflación", "inflacion", "precios", "alimentos", "jubilaciones", "jubilados", "anses",
            "salarios", "sueldos", "paritarias", "tarifas", "luz y gas", "boleto", "transporte",
            "mora", "morosidad", "endeudamiento", "pobreza", "desempleo", "despidos masivos",
            "dólar", "dolar blue", "alquileres"
        ]
    },
    # TIER 3: Macroeconomía y política nacional de alto nivel (Incidencia institucional)
    "tier_3_macro_politics": {
        "weight": 2.2,
        "keywords": [
            "milei", "gobierno", "fmi", "congreso", "senado", "diputados", "veto", "ley",
            "presupuesto", "reservas", "banco central", "bcra", "riesgo país", "bonos",
            "superávit", "gobernadores", "corte suprema", "justicia"
        ]
    },
    # TIER 4: Deportes de representación nacional
    "tier_4_national_pride": {
        "weight": 1.8,
        "keywords": NATIONAL_SPORTS_REPRESENTATION
    }
}

def is_local_sports_headline(title: str) -> bool:
    """Detecta si un titular refiere a resultados o partidos de fútbol doméstico (suma cero)."""
    low = normalize_text(title)
    
    # Si menciona un hito de representación nacional (ej. Selección o Colapinto), NO se descarta
    if any(p in low for p in NATIONAL_SPORTS_REPRESENTATION):
        return False
        
    # Verificar si refiere a clubes locales en contexto de partido/torneo
    matches_club = any(c in low for c in LOCAL_SPORTS_CLUBS)
    has_match_context = any(w in low for w in [
        "gol", "goles", "triunfo", "derrota", "empate", "vencio", "gano", "perdio",
        "campeonato", "partido", "kempes", "clasico", "penal", "fecha", "tabla", "puntos"
    ])
    return matches_club and has_match_context

def compute_headline_significance_weight(title: str) -> float:
    """Calcula el peso de impacto relativo de la noticia según su severidad social."""
    low = normalize_text(title)

    # Deporte local de suma cero: peso atenuado a casi cero
    if is_local_sports_headline(title):
        return 0.1

    # Tier 1: Catástrofe / Duelo Masivo
    for kw in HIERARCHICAL_IMPACT_TIERS["tier_1_catastrophes"]["keywords"]:
        if kw in low:
            return HIERARCHICAL_IMPACT_TIERS["tier_1_catastrophes"]["weight"]

    # Tier 2: Economía de Bolsillo Directo
    for kw in HIERARCHICAL_IMPACT_TIERS["tier_2_pocket_economy"]["keywords"]:
        if kw in low:
            return HIERARCHICAL_IMPACT_TIERS["tier_2_pocket_economy"]["weight"]

    # Tier 3: Macroeconomía y Política Institucional
    for kw in HIERARCHICAL_IMPACT_TIERS["tier_3_macro_politics"]["keywords"]:
        if kw in low:
            return HIERARCHICAL_IMPACT_TIERS["tier_3_macro_politics"]["weight"]

    # Tier 4: Orgullo Deportivo / Cultural Nacional
    for kw in HIERARCHICAL_IMPACT_TIERS["tier_4_national_pride"]["keywords"]:
        if kw in low:
            return HIERARCHICAL_IMPACT_TIERS["tier_4_national_pride"]["weight"]

    # Peso base para sucesos ordinarios o incidentes menores
    return 1.0

# Palabras clave de relleno, trucos domésticos y clickbait que NO inciden en el humor social nacional
JUNK_KEYWORDS = [
    "papel aluminio", "receta", "recetas", "truco casero", "trucos caseros", "cómo limpiar",
    "horóscopo", "signo", "zodíaco", "astrología", "viral", "look", "moda", "dieta",
    "belleza", "consejos para", "cómo hacer para", "descuentos", "ofertas", "farándula",
    "romance", "separación", "novia de", "novio de", "chimento", "astrológico"
]

def filter_relevant_headlines(headlines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filtra titulares irrelevantes y los ordena estrictamente por jerarquía de severidad e impacto nacional."""
    cleaned = []
    for h in headlines:
        title = h.get("title", "")
        low = title.lower()

        # 1. Descartar basura evidente (recetas, trucos caseros, farándula secundaria)
        if any(junk in low for junk in JUNK_KEYWORDS):
            continue
        if len(title.strip()) < 22:
            continue

        # 2. Asignar peso jerárquico según severidad y alcance social
        weight = compute_headline_significance_weight(title)

        # 3. Excluir como foco prioritario el fútbol de clubes local
        if is_local_sports_headline(title):
            weight = 0.2  # Relegado al fondo de la canasta

        cleaned.append((weight, h))

    # Ordenar de mayor a menor impacto social real
    cleaned.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in cleaned]

def analyze_headlines_heuristic(
    source_id: str,
    source_name: str,
    headlines: List[Dict[str, Any]]
) -> SourceSentimentScore:
    """Evalúa los titulares usando análisis léxico contextual, ponderación jerárquica y álgebra vectorial direccional argentina."""
    relevant_headlines = filter_relevant_headlines(headlines)
    if not relevant_headlines:
        relevant_headlines = headlines  # Fallback si todo fue filtrado

    titles = [h.get("title", "") for h in relevant_headlines]
    full_text = " ".join(titles).lower()
    
    pos_drivers = []
    neg_drivers = []

    # Paso 1: Evaluación vectorial proposicional previa con ponderación de impacto
    for t in titles:
        # Omitir resultados de liga local de fútbol en los drivers
        if is_local_sports_headline(t):
            continue

        v_score, _ = evaluate_headline_vector(t)
        weight = compute_headline_significance_weight(t)

        if v_score < 0 and weight >= 1.0:
            if t not in neg_drivers and len(neg_drivers) < 3:
                neg_drivers.append(t)
        elif v_score > 0 and weight >= 1.0:
            if t not in pos_drivers and len(pos_drivers) < 3:
                pos_drivers.append(t)

    # Evaluar eje por eje complementando con vectores y severidad
    def evaluate_axis(pos_terms, neg_terms, is_economic: bool = False, is_joy: bool = False) -> float:
        pos_weighted = 0.0
        neg_weighted = 0.0

        # Sumar pesos de los vectores direccionales ponderados por severidad
        if is_economic:
            for t in titles:
                v_score, _ = evaluate_headline_vector(t)
                w = compute_headline_significance_weight(t)
                if v_score > 0:
                    pos_weighted += 2.0 * w
                elif v_score < 0:
                    neg_weighted += 2.0 * w

        for term in pos_terms:
            matches = [t for t in titles if term in t.lower()]
            for m in matches:
                # Regla deportiva: no computar fútbol local como alegría nacional
                if is_joy and is_local_sports_headline(m):
                    continue

                w = compute_headline_significance_weight(m)
                # Evitar falso positivo si el vector determinó que es negativo
                v_sc, _ = evaluate_headline_vector(m)
                if v_sc < 0:
                    neg_weighted += 1.0 * w
                    continue

                pos_weighted += 1.0 * w
                if w >= 1.5 and m not in pos_drivers and len(pos_drivers) < 3 and not is_local_sports_headline(m):
                    pos_drivers.append(m)
                        
        for term in neg_terms:
            matches = [t for t in titles if term in t.lower()]
            for m in matches:
                w = compute_headline_significance_weight(m)
                neg_weighted += 1.0 * w
                if w >= 1.5 and m not in neg_drivers and len(neg_drivers) < 3:
                    neg_drivers.append(m)

        total_weight = pos_weighted + neg_weighted
        if total_weight == 0:
            return 0.0
        # Balance neto ponderado escalado a [-10, 10]
        net = (pos_weighted - neg_weighted) / max(total_weight, 3.0) * 10.0
        return max(-10.0, min(10.0, round(net, 1)))

    opt = evaluate_axis(LEXICON_AR["optimismo_pos"], LEXICON_AR["optimismo_neg"], is_economic=True)
    cal = evaluate_axis(LEXICON_AR["calma_pos"], LEXICON_AR["calma_neg"], is_economic=False)
    conf = evaluate_axis(LEXICON_AR["confianza_pos"], LEXICON_AR["confianza_neg"], is_economic=True)
    ale = evaluate_axis(LEXICON_AR["alegria_pos"], LEXICON_AR["alegria_neg"], is_economic=False, is_joy=True)

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

Rúbrica de evaluación rigurosa y reglas metodológicas:
1. Optimismo vs. Pesimismo (-10.0 a +10.0): Esperanza, futuro, reactivación (+10) vs crisis sin salida, decadencia (-10).
2. Calma vs. Conflicto / Bronca (-10.0 a +10.0): Paz, acuerdos (+10) vs marchas, tensión, crispación, inseguridad (-10).
3. Confianza vs. Incertidumbre (-10.0 a +10.0): Previsibilidad, estabilidad (+10) vs miedo al dólar, devaluación, quiebra (-10).
4. Alegría vs. Tristeza (-10.0 a +10.0): Triunfos de representación patrios/colectivos (+10) vs duelo colectivo, tragedias, pérdidas (-10).

REGLAS SOCIOLÓGICAS DE PONDERACIÓN:
A. JERARQUÍA DE IMPACTO: 
   - Pondera con máxima prioridad las noticias que afectan el BOLSILLO DIRECTO del 100% de la ciudadanía (inflación de alimentos, tarifas, salarios, jubilaciones, mora crediticia) y las TRAGEDIAS HUMANAS MASIVAS.
   - Un choque vial ordinario o una discusión menor tienen peso reducido; una catástrofe o una medida de poder adquisitivo mueven la aguja nacional.
B. TRATAMIENTO DEL FÚTBOL LOCAL (SUMA CERO):
   - El resultado de un partido de la liga local (ej. Boca, River, Central, Independiente) NO altera el humor social nacional porque la alegría de una hinchada se cancela con la tristeza o indiferencia del resto. Es un juego de suma cero. NUNCA lo elijas como "positive_driver" del humor nacional.
   - Solo los hitos deportivos internacionales que unen unívocamente a toda la nación (ej. Selección Argentina, Colapinto en F1, medallas olímpicas) computan como alegría colectiva genuina.

Responde EXCLUSIVAMENTE con un JSON válido con este formato exacto:
{{
  "optimismo": <float entre -10.0 y 10.0>,
  "calma": <float entre -10.0 y 10.0>,
  "confianza": <float entre -10.0 y 10.0>,
  "alegria": <float entre -10.0 y 10.0>,
  "key_themes": ["tema 1", "tema 2", "tema 3"],
  "positive_drivers": ["titular positivo de impacto nacional 1"],
  "negative_drivers": ["titular crítico o de preocupación real 1"],
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
