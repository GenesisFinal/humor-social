"""
Configuración general para el Índice de Humor Social Argentino (IHSA).
Define fuentes de información, ponderaciones metodológicas y rutas de almacenamiento.
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# Cargar variables de entorno si existe .env
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
COVERS_DIR = DATA_DIR / "covers"
REPORTS_DIR = DATA_DIR / "reports"
DB_PATH = Path(os.getenv("DB_PATH", DATA_DIR / "humor_social.db"))

DATA_DIR.mkdir(exist_ok=True)
COVERS_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)

# Umbral para alerta de volatilidad abrupta (puntos IHSA de cambio vs día anterior)
VOLATILITY_ALERT_THRESHOLD = 15.0

# API Keys
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ---------------------------------------------------------
# CANASTA DE MEDIOS (10 MEDIOS PRINCIPALES DE ARGENTINA)
# ---------------------------------------------------------
MEDIA_SOURCES = {
    # Los 5 solicitados
    "clarin": {
        "name": "Clarín",
        "category": "general",
        "type": "traditional_press",
        "rss": "https://www.clarin.com/rss/politica/",
        "rss_extra": "https://www.clarin.com/rss/economia/",
        "web": "https://www.clarin.com",
        "cover_code": "ar_clarin",
        "weight": 0.12,
    },
    "lanacion": {
        "name": "La Nación",
        "category": "general",
        "type": "traditional_press",
        "rss": "https://www.lanacion.com.ar/arc/outboundfeeds/rss/?outputType=xml",
        "web": "https://www.lanacion.com.ar",
        "cover_code": "nacion",
        "weight": 0.12,
    },
    "infobae": {
        "name": "Infobae",
        "category": "general",
        "type": "digital_native",
        "rss": "https://www.infobae.com/arc/outboundfeeds/rss/?outputType=xml",
        "web": "https://www.infobae.com",
        "cover_code": None,
        "weight": 0.14,
    },
    "cronica": {
        "name": "Crónica",
        "category": "popular",
        "type": "popular_press",
        "rss": None,
        "web": "https://www.cronica.com.ar",
        "cover_code": "ar_cronica",
        "weight": 0.10,
    },
    "eldestape": {
        "name": "El Destape",
        "category": "political_opposition",
        "type": "digital_native",
        "rss": None,
        "web": "https://www.eldestapeweb.com",
        "cover_code": None,
        "weight": 0.08,
    },
    # Los 5 seleccionados por métricas objetivas (Comscore / Reuters Institute)
    "tn": {
        "name": "TN (Todo Noticias)",
        "category": "general",
        "type": "multimedia_broadcast",
        "rss": "https://tn.com.ar/rss.xml",
        "web": "https://tn.com.ar",
        "cover_code": None,
        "weight": 0.12,
    },
    "pagina12": {
        "name": "Página/12",
        "category": "political_left",
        "type": "traditional_press",
        "rss": None,
        "web": "https://www.pagina12.com.ar",
        "cover_code": "pagina12",
        "weight": 0.08,
    },
    "ambito": {
        "name": "Ámbito Financiero",
        "category": "economy",
        "type": "financial_press",
        "rss": "https://www.ambito.com/rss/pages/home.xml",
        "web": "https://www.ambito.com",
        "cover_code": "ar_ambito_financiero",
        "weight": 0.10,
    },
    "cronista": {
        "name": "El Cronista Comercial",
        "category": "economy",
        "type": "financial_press",
        "rss": "https://www.cronista.com/rss/pages/home.xml",
        "web": "https://www.cronista.com",
        "cover_code": "ar_cronista",
        "weight": 0.10,
    },
    "perfil": {
        "name": "Perfil",
        "category": "general",
        "type": "investigative_press",
        "rss": "https://www.perfil.com/feed",
        "web": "https://www.perfil.com",
        "cover_code": "perfil",
        "weight": 0.04,
    },
    # Medios complementarios de expansión federal y digital (Fase 3 & Fase 4 Federal)
    "cadena3": {
        "name": "Cadena 3",
        "category": "federal",
        "type": "federal_broadcast",
        "rss": None,
        "web": "https://www.cadena3.com",
        "cover_code": None,
        "weight": 0.05,
    },
    "lavoz": {
        "name": "La Voz del Interior",
        "category": "federal",
        "type": "federal_press",
        "rss": "https://www.lavoz.com.ar/arc/outboundfeeds/rss/?outputType=xml",
        "web": "https://www.lavoz.com.ar",
        "cover_code": "ar_lavoz",
        "weight": 0.04,
    },
    "lacapital": {
        "name": "La Capital (Rosario)",
        "category": "federal",
        "type": "federal_press",
        "rss": "https://www.lacapital.com.ar/rss/home.xml",
        "web": "https://www.lacapital.com.ar",
        "cover_code": "ar_lacapital",
        "weight": 0.04,
    },
    "c5n": {
        "name": "C5N",
        "category": "political_opposition",
        "type": "multimedia_broadcast",
        "rss": None,
        "web": "https://www.c5n.com",
        "cover_code": None,
        "weight": 0.05,
    },
}

# ---------------------------------------------------------
# PARÁMETROS METODOLÓGICOS AVANZADOS (INERCIA Y CALIBRACIÓN)
# ---------------------------------------------------------
# Factor alfa para la Media Móvil Exponencial (EMA): 65% pulso del día, 35% inercia acumulada
IHSA_EMA_ALPHA = 0.65

# Términos excluidos de tendencias digitales para evitar distorsiones por entretenimiento/farándula
DIGITAL_TRENDS_EXCLUSION_TERMS = [
    "gran hermano", "gh", "granhermano", "bake off", "masterchef", "chape", "bizarrap",
    "wanda", "tinelli", "stream", "streamer", "streamers", "twitch", "tiktok", "tiktoker",
    "ghvip", "eliminado", "gala", "nominados", "repechaje", "chisme", "romance", "espectaculo"
]

# ---------------------------------------------------------
# FUENTES DE TENDENCIAS Y CONVERSACIÓN DIGITAL
# ---------------------------------------------------------
DIGITAL_TRENDS = {
    "google_trends": {
        "name": "Google Trends Argentina",
        "rss": "https://trends.google.com/trending/rss?geo=AR",
    },
    "x_twitter": {
        "name": "X (Twitter) Trending Argentina",
        "web": "https://trends24.in/argentina/",
    }
}

# ---------------------------------------------------------
# PONDERACIÓN MACRO DEL ÍNDICE CONSOLIDADO
# ---------------------------------------------------------
MACRO_WEIGHTS = {
    "media_headlines": 0.50,    # Medios de prensa general y popular
    "economy_headlines": 0.20,  # Medios financieros y de bolsillo
    "digital_trends": 0.30,     # Google Trends y X (conversación espontánea)
}

# ---------------------------------------------------------
# EJES EMOCIONALES ANALIZADOS (Rango de cada uno: -10 a +10)
# ---------------------------------------------------------
EMOTIONAL_AXES = {
    "optimismo": {
        "name": "Optimismo vs. Pesimismo",
        "positive": "Esperanza, crecimiento, resolución de problemas, proyectos de futuro",
        "negative": "Sensación de crisis sin salida, decadencia, desaliento general",
        "weight": 0.30,
    },
    "calma": {
        "name": "Calma vs. Conflicto / Crispación",
        "positive": "Paz social, acuerdos cívicos, estabilidad y convivencia",
        "negative": "Enojo, protestas, indignación pública, violencia, inseguridad",
        "weight": 0.25,
    },
    "confianza": {
        "name": "Confianza vs. Incertidumbre / Miedo",
        "positive": "Previsibilidad económica, estabilidad monetaria, certidumbre jurídica",
        "negative": "Angustia por precios/dólar, riesgo laboral, desconfianza institucional",
        "weight": 0.30,
    },
    "alegria": {
        "name": "Alegría vs. Tristeza / Duelo",
        "positive": "Celebraciones colectivas, logros deportivos/científicos/culturales",
        "negative": "Dolor social, tragedias colectivas, pérdidas humanas o sufrimiento",
        "weight": 0.15,
    }
}
