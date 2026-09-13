"""
Capa de persistencia SQLite para el Índice de Humor Social Argentino.
Almacena series temporales diarias, evaluaciones por medio, titulares sin procesar y tendencias.
"""

import sqlite3
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from config import DB_PATH
from engine.models import DailySnapshot, SourceSentimentScore

def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Crea las tablas de la base de datos si no existen."""
    conn = get_connection()
    cursor = conn.cursor()

    # Tabla principal de instantáneas diarias
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS daily_snapshots (
        date TEXT PRIMARY KEY,
        ihsa_score REAL NOT NULL,
        ihsa_category TEXT NOT NULL,
        optimismo REAL NOT NULL,
        calma REAL NOT NULL,
        confianza REAL NOT NULL,
        alegria REAL NOT NULL,
        summary TEXT,
        top_trends_x TEXT,
        top_trends_google TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Tabla de evaluaciones desglosadas por medio
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS source_evaluations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        source_id TEXT NOT NULL,
        source_name TEXT NOT NULL,
        category TEXT NOT NULL,
        composite_score REAL NOT NULL,
        optimismo REAL NOT NULL,
        calma REAL NOT NULL,
        confianza REAL NOT NULL,
        alegria REAL NOT NULL,
        key_themes TEXT,
        positive_drivers TEXT,
        negative_drivers TEXT,
        justification TEXT,
        cover_path TEXT,
        UNIQUE(date, source_id)
    )
    """)

    # Tabla de titulares recolectados
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS raw_headlines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        source_id TEXT NOT NULL,
        title TEXT NOT NULL,
        url TEXT,
        channel TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

def save_snapshot(
    snapshot: DailySnapshot,
    raw_items_by_source: Dict[str, List[Dict[str, Any]]],
    covers_map: Optional[Dict[str, str]] = None
):
    """Guarda la instantánea diaria, evaluaciones de medios y titulares en la base de datos."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    covers_map = covers_map or {}

    try:
        # 1. Insertar o actualizar instantánea diaria
        cursor.execute("""
        INSERT OR REPLACE INTO daily_snapshots (
            date, ihsa_score, ihsa_category, optimismo, calma, confianza, alegria,
            summary, top_trends_x, top_trends_google
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            snapshot.date,
            snapshot.ihsa_score,
            snapshot.ihsa_category,
            snapshot.axes_averages.optimismo,
            snapshot.axes_averages.calma,
            snapshot.axes_averages.confianza,
            snapshot.axes_averages.alegria,
            snapshot.summary_of_the_day,
            json.dumps(snapshot.top_trends_x, ensure_ascii=False),
            json.dumps(snapshot.top_trends_google, ensure_ascii=False)
        ))

        # 2. Insertar evaluaciones por medio
        for src in snapshot.sources:
            cover_path = covers_map.get(src.source_id, "")
            cursor.execute("""
            INSERT OR REPLACE INTO source_evaluations (
                date, source_id, source_name, category, composite_score,
                optimismo, calma, confianza, alegria, key_themes,
                positive_drivers, negative_drivers, justification, cover_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                snapshot.date,
                src.source_id,
                src.source_name,
                src.category,
                src.composite_score,
                src.scores.optimismo,
                src.scores.calma,
                src.scores.confianza,
                src.scores.alegria,
                json.dumps(src.key_themes, ensure_ascii=False),
                json.dumps(src.positive_drivers, ensure_ascii=False),
                json.dumps(src.negative_drivers, ensure_ascii=False),
                src.justification,
                cover_path
            ))

        # 3. Guardar titulares sin procesar para auditoría
        for source_id, items in raw_items_by_source.items():
            for item in items:
                cursor.execute("""
                INSERT INTO raw_headlines (date, source_id, title, url, channel)
                VALUES (?, ?, ?, ?, ?)
                """, (
                    snapshot.date,
                    source_id,
                    item.get("title", ""),
                    item.get("url", ""),
                    item.get("channel", "")
                ))

        conn.commit()
    finally:
        conn.close()

def get_latest_snapshot() -> Optional[Dict[str, Any]]:
    """Obtiene la última medición disponible."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM daily_snapshots ORDER BY date DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_historical_snapshots(days: int = 30) -> List[Dict[str, Any]]:
    """Obtiene la serie temporal histórica de mediciones."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM daily_snapshots ORDER BY date ASC LIMIT ?", (days,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_source_evaluations(target_date: str) -> List[Dict[str, Any]]:
    """Obtiene el desglose de medios para una fecha determinada."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM source_evaluations WHERE date = ? ORDER BY composite_score DESC",
        (target_date,)
    )
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for r in rows:
        d = dict(r)
        d["key_themes"] = json.loads(d["key_themes"]) if d["key_themes"] else []
        d["positive_drivers"] = json.loads(d["positive_drivers"]) if d["positive_drivers"] else []
        d["negative_drivers"] = json.loads(d["negative_drivers"]) if d["negative_drivers"] else []
        results.append(d)
    return results

def get_available_dates() -> List[str]:
    """Retorna la lista de todas las fechas registradas en orden descendente."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT date FROM daily_snapshots ORDER BY date DESC")
    rows = cursor.fetchall()
    conn.close()
    return [r["date"] for r in rows]

def get_snapshot_by_date(target_date: str) -> Optional[Dict[str, Any]]:
    """Obtiene la medición para una fecha específica."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM daily_snapshots WHERE date = ?", (target_date,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_previous_snapshot(current_date: str) -> Optional[Dict[str, Any]]:
    """Obtiene la medición inmediatamente anterior a una fecha dada."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM daily_snapshots WHERE date < ? ORDER BY date DESC LIMIT 1",
        (current_date,)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_raw_headlines_for_date(target_date: str, search_query: str = "") -> List[Dict[str, Any]]:
    """Obtiene los titulares recolectados para una fecha con filtro opcional de búsqueda."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    if search_query:
        cursor.execute(
            """
            SELECT h.*, s.source_name 
            FROM raw_headlines h
            LEFT JOIN source_evaluations s ON h.date = s.date AND h.source_id = s.source_id
            WHERE h.date = ? AND (h.title LIKE ? OR h.source_id LIKE ?)
            ORDER BY h.source_id ASC, h.id ASC
            """,
            (target_date, f"%{search_query}%", f"%{search_query}%")
        )
    else:
        cursor.execute(
            """
            SELECT h.*, s.source_name 
            FROM raw_headlines h
            LEFT JOIN source_evaluations s ON h.date = s.date AND h.source_id = s.source_id
            WHERE h.date = ?
            ORDER BY h.source_id ASC, h.id ASC
            """,
            (target_date,)
        )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
