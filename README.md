# Índice de Humor Social Argentino (IHSA) 🇦🇷

Sistema automatizado para cuantificar, registrar y monitorear día tras día el clima emocional y la conversación pública en Argentina mediante análisis riguroso y objetivo de medios de comunicación masivos, portadas impresas, tendencias de búsqueda y redes sociales.

---

## 🏛️ Canasta de Fuentes Monitoreadas

### 1. Los 12 Medios de Comunicación Clave
Seleccionados para garantizar equilibrio editorial, diversidad ideológica y representatividad federal (según métricas de Comscore Argentina y Reuters Institute):

1. **Clarín**: #1 en circulación histórica tradicional y multiplataforma.
2. **La Nación**: Referente periodístico tradicional e institucional.
3. **Infobae**: #1 en alcance digital y tráfico en Argentina.
4. **Crónica**: Termómetro popular directo y consumo de sectores trabajadores.
5. **El Destape**: Referente digital de sectores de centro-izquierda / peronismo.
6. **TN (Todo Noticias)**: Líder de audiencia en breaking news y alcance audiovisual cruzado.
7. **Página/12**: Periódico histórico de izquierda/progresismo (contrapeso metodológico).
8. **Ámbito Financiero**: Diario económico líder (termómetro de inflación, dólar y expectativas de mercado).
9. **El Cronista Comercial**: Diario de finanzas, empresas y sectores productivos.
10. **Perfil**: Medio de investigación dominical, análisis a fondo y columna editorial independiente.
11. **Cadena 3**: Líder federal indiscutido del interior del país (Córdoba, Santa Fe, Cuyo, NOA).
12. **C5N**: Referente de noticias audiovisuales y portal digital de alto tráfico.

### 2. Conversación Digital Espontánea
- **X (Twitter)**: Trending Topics de Argentina en tiempo real.
- **Google Trends Argentina**: Búsquedas de mayor aceleración diaria del público.

### 3. Portadas Impresas en Alta Resolución
- Descarga y archivo visual diario de las primeras planas impresas de Clarín, La Nación, Página 12, etc.

---

## 📐 Metodología de Medición

Cada fuente es evaluada a lo largo de **4 ejes emocionales bipolares** en escala de `-10.0` a `+10.0`:

1. **Optimismo vs. Pesimismo (`-10` a `+10`)**: Sensación de futuro, recuperación y oportunidades vs. callejón sin salida y decadencia.
2. **Calma vs. Conflicto / Bronca (`-10` a `+10`)**: Paz social, acuerdos y diálogo vs. marchas, protestas, indignación e inseguridad.
3. **Confianza vs. Incertidumbre (`-10` a `+10`)**: Previsibilidad de precios y estabilidad monetaria vs. miedo al dólar, devaluación o desabastecimiento.
4. **Alegría vs. Tristeza / Duelo (`-10` a `+10`)**: Logros deportivos (ej. Colapinto, selección), eventos culturales y orgullo colectivo vs. tragedias o dolor social.

### Índice Consolidado IHSA (`-100` a `+100`)
$$\text{IHSA}_t = 0.50 \times \text{Prensa General} + 0.20 \times \text{Prensa Económica} + 0.30 \times \text{Pulso Digital}$$

- **+50 a +100**: Euforia / Muy Alto Optimismo
- **+20 a +50**: Optimismo Moderado
- **+5 a +20**: Levemente Positivo / Esperanza
- **-5 a +5**: Neutro / Equilibrio
- **-20 a -5**: Levemente Negativo / Preocupación
- **-50 a -20**: Pesimismo y Tensión Moderada
- **-100 a -50**: Alarma / Crisis Emocional Colectiva

---

## 🚀 Guía de Uso Rápido

### 1. Ejecutar una Medición Diaria
Recolecta las fuentes de hoy, calcula el índice y lo guarda en la base de datos local SQLite:

```bash
python run_pipeline.py
```

Para correr una fecha específica:
```bash
python run_pipeline.py --date 2026-09-13
```

### 2. Abrir el Dashboard Interactivo
Inicia la aplicación web visual con tacómetro, mapa de calor de medios, radar emocional y evolución temporal:

```bash
streamlit run dashboard/app.py
```
O simplemente haz doble clic en `start_dashboard.bat`.

### 3. Automatización Diaria Desatendida (Fase 3)
Puedes dejar el sistema funcionando solo de forma continua de dos formas:

- **Opción A (Recomendada - Programador de Tareas de Windows)**:
  Ejecuta PowerShell y corre el script de instalación:
  ```powershell
  powershell -ExecutionPolicy Bypass -File automation/setup_task.ps1
  ```
  Esto programará la tarea automática diaria a las **08:00 AM** en Windows.
  Para desinstalarla:
  ```powershell
  powershell -ExecutionPolicy Bypass -File automation/setup_task.ps1 -Action uninstall
  ```

- **Opción B (Servicio Daemon en segundo plano)**:
  ```bash
  python automation/scheduler.py
  ```
  Corre de forma continua en segundo plano y ejecuta la medición a las 08:00 y 20:00.

### 4. Configurar IA (Google Gemini - Opcional)
El sistema incluye un analizador léxico/contextual argentino que funciona de forma autónoma. Si deseas activar la evaluación semántica profunda con LLM:
1. Copia `.env.example` a `.env`:
   ```bash
   copy .env.example .env
   ```
2. Añade tu API key de Gemini (`GEMINI_API_KEY=tu_clave_aqui`).

---

## 📂 Estructura del Directorio

```
├── config.py                 # Configuración de medios, pesos y parámetros
├── run_pipeline.py           # Orquestador del ciclo diario
├── requirements.txt          # Dependencias de Python
├── collectors/               # Módulos de recolección
│   ├── rss_collector.py      # Lector de feeds RSS
│   ├── web_collector.py      # Scraper web para portales
│   ├── trends_collector.py   # X (Twitter) y Google Trends
│   └── covers_collector.py   # Descargador de tapas de diarios
├── engine/                   # Motor analítico y de scoring
│   ├── models.py             # Esquemas de datos Pydantic
│   ├── analyzer.py           # Motor de análisis (Gemini + Heurístico AR)
│   └── scoring.py            # Algoritmo matemático de ponderación
├── storage/                  # Persistencia
│   └── db.py                 # Base de datos SQLite y consultas
├── dashboard/                # Visualización
│   └── app.py                # Dashboard interactivo en Streamlit
├── data/                     # Almacenamiento local (generado automáticamente)
│   ├── humor_social.db       # Base de datos SQLite
│   └── covers/               # Tapas de diarios en alta resolución
└── tests/                    # Pruebas automatizadas
    └── test_system.py        # Suite de pruebas unitarias
```
