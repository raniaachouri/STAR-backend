import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "data.db")
os.makedirs(DATA_DIR, exist_ok=True)

def get_connection():
    return sqlite3.connect(DB_PATH)

def _ensure_columns(conn, table, required_cols):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    existing = {row[1] for row in cur.fetchall()}  # row[1] = column name

    for col, col_def in required_cols.items():
        if col not in existing:
            # Add missing column
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")

def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    # 1) Create base tables if they don't exist
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS extractions (
        id INTEGER PRIMARY KEY AUTOINCREMENT
        -- other columns may be added later via migration
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS repair_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        extraction_id INTEGER,
        designation TEXT,
        montant REAL,
        FOREIGN KEY (extraction_id) REFERENCES extractions(id) ON DELETE CASCADE
    );
    """)

    # 2) Auto-migrate columns for `extractions`
    required_extractions = {
        "assure": "TEXT",
        "tiers": "TEXT",
        "contrat": "TEXT",
        "numero_dossier": "TEXT",
        "expert": "TEXT",
        "observation": "TEXT",
        "date_examen": "TEXT",
        "date_accident": "TEXT",
        "marque": "TEXT",
        "puissance": "TEXT",
        "energie": "TEXT",
        "couleur": "TEXT",
        "date_1_mc": "TEXT",
        "numero_serie": "TEXT",
        "total_mo_ttc": "REAL",
        "total_four_ht": "REAL",
        "total_net": "REAL",
        "created_at": "TIMESTAMP"
    }
    _ensure_columns(conn, "extractions", required_extractions)

    conn.commit()
    conn.close()

def save_extraction_to_db(result: dict) -> int:
    conn = get_connection()
    cursor = conn.cursor()

    infos = result.get("Informations Générales", {}) or {}
    details = result.get("Détails du Véhicule", {}) or {}
    reparations = result.get("Réparations et Désignations", {}) or {}

    cursor.execute("""
    INSERT INTO extractions (
        assure, tiers, contrat, numero_dossier, expert, observation,
        date_examen, date_accident, marque, puissance, energie, couleur,
        date_1_mc, numero_serie, total_mo_ttc, total_four_ht, total_net, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        infos.get("Assuré", ""),
        infos.get("Tiers", ""),
        infos.get("Contrat", ""),
        infos.get("N° Dossier", ""),
        infos.get("Expert", ""),
        infos.get("Observation", ""),
        infos.get("Date d'examen", ""),
        infos.get("Date d'accident", ""),
        details.get("Marque", ""),
        details.get("Puissance", ""),
        details.get("Énergie", ""),
        details.get("Couleur", ""),
        details.get("Date 1ère mise en circulation", ""),
        details.get("N° Série", ""),
        reparations.get("Total M.O TTC", None),
        reparations.get("Total FOUR HT", None),
        reparations.get("Total Net", None),
        datetime.now()
    ))

    extraction_id = cursor.lastrowid

    designations = reparations.get("Désignations", []) or []
    montants = reparations.get("Montants", []) or []
    for designation, montant in zip(designations, montants):
        cursor.execute("""
        INSERT INTO repair_items (extraction_id, designation, montant)
        VALUES (?, ?, ?)
        """, (extraction_id, designation, montant))

    conn.commit()
    conn.close()
    return extraction_id

def fetch_all_extractions():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM extractions ORDER BY created_at DESC")
    rows = cursor.fetchall()
    cols = [c[0] for c in cursor.description]
    conn.close()
    return [dict(zip(cols, r)) for r in rows]

def fetch_extraction_by_id(extraction_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM extractions WHERE id = ?", (extraction_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    cols = [c[0] for c in cursor.description]
    extraction = dict(zip(cols, row))

    cursor.execute("SELECT designation, montant FROM repair_items WHERE extraction_id = ?", (extraction_id,))
    repairs = cursor.fetchall()
    conn.close()

    extraction["reparations"] = [{"designation": r[0], "montant": r[1]} for r in repairs]
    return extraction
