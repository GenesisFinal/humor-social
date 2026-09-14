"""
Modelos de datos Pydantic para el análisis estructurado del Índice de Humor Social Argentino.
"""

from typing import List, Dict, Optional, Literal
from pydantic import BaseModel, Field

class EmotionalAxesScores(BaseModel):
    """Puntuaciones en los 4 ejes bipolares normalizados de -10 a +10."""
    optimismo: float = Field(..., ge=-10.0, le=10.0, description="Optimismo (+10) vs Pesimismo (-10)")
    calma: float = Field(..., ge=-10.0, le=10.0, description="Calma/Paz (+10) vs Conflicto/Crispación/Bronca (-10)")
    confianza: float = Field(..., ge=-10.0, le=10.0, description="Confianza/Previsibilidad (+10) vs Incertidumbre/Miedo (-10)")
    alegria: float = Field(..., ge=-10.0, le=10.0, description="Alegría/Logro (+10) vs Tristeza/Duelo/Tragedia (-10)")

class SourceSentimentScore(BaseModel):
    """Evaluación detallada y auditable de una fuente o medio."""
    source_id: str
    source_name: str
    category: str
    scores: EmotionalAxesScores
    composite_score: float = Field(..., ge=-100.0, le=100.0, description="Score general del medio de -100 a +100")
    key_themes: List[str] = Field(default_factory=list, description="Temas principales detectados en el medio hoy")
    positive_drivers: List[str] = Field(default_factory=list, description="Titulares o hechos que sumaron al optimismo")
    negative_drivers: List[str] = Field(default_factory=list, description="Titulares o hechos que sumaron al pesimismo/tensión")
    editorial_bias_detected: Optional[str] = Field(None, description="Sesgo editorial o encuadre observado")
    justification: str = Field(..., description="Justificación analítica y rigurosa del puntaje otorgado")

class DailySnapshot(BaseModel):
    """Foto completa y consolidada del día para el Índice de Humor Social Argentino (IHSA)."""
    date: str  # YYYY-MM-DD
    ihsa_score: float = Field(..., ge=-100.0, le=100.0, description="Índice IHSA Consolidado (-100 a +100)")
    ihsa_category: Literal[
        "Euforia / Muy Alto Optimismo",
        "Optimismo Moderado",
        "Levemente Positivo / Esperanza",
        "Neutro / Equilibrio",
        "Levemente Negativo / Preocupación",
        "Pesimismo y Tensión Moderada",
        "Alarma / Crisis Emocional Colectiva"
    ]
    axes_averages: EmotionalAxesScores
    sources: List[SourceSentimentScore]
    top_trends_x: List[str] = Field(default_factory=list)
    top_trends_google: List[str] = Field(default_factory=list)
    summary_of_the_day: str
    editorial_divergence: Optional[float] = Field(default=0.0, description="Brecha de polarización entre medios tradicionales y de oposición")
    decompression_buffer: Optional[float] = Field(default=0.0, description="Amortiguador de descompresión deportiva o de orgullo nacional")
