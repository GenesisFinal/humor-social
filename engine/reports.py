"""
Generador de informes y boletines ejecutivos diarios del Índice de Humor Social Argentino (IHSA).
Produce reportes estructurados en Markdown y detecta alertas de volatilidad abrupta.
"""

from pathlib import Path
from typing import Optional, Dict, Any
from config import REPORTS_DIR, VOLATILITY_ALERT_THRESHOLD
from engine.models import DailySnapshot
import json

def generate_daily_report(
    snapshot: DailySnapshot,
    prev_snapshot: Optional[Dict[str, Any]] = None
) -> str:
    """Genera el contenido Markdown del informe diario y lo guarda en disco."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_file = REPORTS_DIR / f"informe_{snapshot.date}.md"

    # Cálculo de variación con respecto al día anterior
    delta_text = "Sin registro previo (primera medición)"
    volatility_alert = ""
    
    if prev_snapshot:
        prev_score = prev_snapshot["ihsa_score"]
        diff = snapshot.ihsa_score - prev_score
        sign = "+" if diff > 0 else ""
        delta_text = f"{sign}{diff:.1f} pts respecto a ayer ({prev_score:.1f} pts)"

        if abs(diff) >= VOLATILITY_ALERT_THRESHOLD:
            volatility_alert = f"""
> [!WARNING]
> **ALERTA DE VOLATILIDAD SOCIAL BRUSCA**  
> Se detectó un movimiento de **{abs(diff):.1f} puntos** en 24 horas. 
> {'Un shock de optimismo / alivio repentino' if diff > 0 else 'Un shock de crispación / pesimismo abrupto'} ha impactado de forma directa en el clima de opinión pública.
"""

    # Ordenar fuentes de mayor a menor optimismo
    sorted_sources = sorted(snapshot.sources, key=lambda s: s.composite_score, reverse=True)

    sources_table_rows = []
    for s in sorted_sources:
        pos_txt = s.positive_drivers[0] if s.positive_drivers else "Sin focos destacados"
        neg_txt = s.negative_drivers[0] if s.negative_drivers else "Sin focos destacados"
        sources_table_rows.append(
            f"| **{s.source_name}** | `{s.category}` | **{s.composite_score:+.1f}** | {pos_txt[:45]} | {neg_txt[:45]} |"
        )
    sources_table = "\n".join(sources_table_rows)

    trends_x_str = ", ".join([f"#{t}" for t in snapshot.top_trends_x[:8]]) if snapshot.top_trends_x else "No disponible"
    trends_g_str = ", ".join(snapshot.top_trends_google[:8]) if snapshot.top_trends_google else "No disponible"

    content = f"""# 🇦🇷 Boletín Ejecutivo de Humor Social — {snapshot.date}

**Índice IHSA Consolidado:** **`{snapshot.ihsa_score:+.1f} / 100`**  
**Diagnóstico:** **{snapshot.ihsa_category}**  
**Variación 24h:** {delta_text}  
{volatility_alert}

### 📊 Ejes Emocionales del Día (Escala -10 a +10)
- **🌱 Optimismo vs. Pesimismo:** `{snapshot.axes_averages.optimismo:+.1f}`
- **🕊️ Calma vs. Conflicto / Bronca:** `{snapshot.axes_averages.calma:+.1f}`
- **⚓ Confianza vs. Incertidumbre:** `{snapshot.axes_averages.confianza:+.1f}`
- **☀️ Alegría vs. Tristeza / Duelo:** `{snapshot.axes_averages.alegria:+.1f}`

### 🔬 Indicadores Avanzados y Metodología Internacional
- **⚡ Brecha de Polarización Editorial ("Brecha de Grieta"):** `{snapshot.editorial_divergence or 0.0:.1f} pts` {'— *(Alerta: Fuerte polarización ideológica)*' if (snapshot.editorial_divergence or 0.0) >= 40.0 else '— *(Banda de convergencia normal)*'}
- **🏎️ Amortiguador Deportivo Patriótico (Decompression Buffer):** `+{snapshot.decompression_buffer or 0.0:.1f} pts` *(Alivio emocional provisto por hitos patrios frente a la tensión socioeconómica)*

### 💡 Diagnóstico y Síntesis Analítica
{snapshot.summary_of_the_day}

### 📰 Matriz Comparativa de Medios Monitoreados
| Medio | Enfoque | Score IHSA | Principal Foco Positivo | Principal Foco de Tensión |
| :--- | :--- | :---: | :--- | :--- |
{sources_table}

### 🌐 Pulso Espontáneo en Redes y Búsquedas
- **Tendencias en X (Twitter Argentina):** {trends_x_str}
- **Mayor Aceleración en Google Trends:** {trends_g_str}

*Informe generado automáticamente por el Sistema de Monitoreo de Humor Social Argentino (IHSA).*
"""

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(content)

    return content
