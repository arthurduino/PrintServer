import sqlite3
import json
from datetime import datetime
from typing import List, Tuple, Optional

DB_FILE = 'printserver.db'

def init_db():
    """Initialise la base de données et crée les tables si elles n'existent pas."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Création de la table commandes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commandes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom_client TEXT NOT NULL,
            reference_externe TEXT,
            date_creation TEXT DEFAULT CURRENT_TIMESTAMP,
            statut_global TEXT NOT NULL CHECK(statut_global IN ('PENDING', 'PROCESSING', 'DONE', 'ERROR'))
        )
    ''')

    # Création de la table taches
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS taches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            commande_id INTEGER NOT NULL,
            ordre INTEGER NOT NULL,
            type_tache TEXT NOT NULL CHECK(type_tache IN ('BATCH', 'SERIES')),
            config_json TEXT,  -- Stocké comme chaîne JSON
            quantite_totale INTEGER NOT NULL,
            quantite_faite INTEGER DEFAULT 0,
            statut TEXT NOT NULL CHECK(statut IN ('PENDING', 'IN_PROGRESS', 'DONE', 'ERROR')),
            FOREIGN KEY(commande_id) REFERENCES commandes(id) ON DELETE CASCADE
        )
    ''')

    conn.commit()
    conn.close()

# Fonctions CRUD pour commandes

def create_commande(nom_client: str, reference_externe: Optional[str] = None) -> int:
    """Crée une nouvelle commande et retourne l'id."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    date_creation = datetime.utcnow().isoformat()
    statut_global = 'PENDING'
    cursor.execute('''
        INSERT INTO commandes (nom_client, reference_externe, date_creation, statut_global)
        VALUES (?, ?, ?, ?)
    ''', (nom_client, reference_externe, date_creation, statut_global))
    commande_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return commande_id

def get_commandes() -> List[Tuple]:
    """Retourne toutes les commandes."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, nom_client, reference_externe, date_creation, statut_global FROM commandes')
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_commande(commande_id: int) -> Tuple:
    """Retourne une commande par id."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, nom_client, reference_externe, date_creation, statut_global FROM commandes WHERE id = ?', (commande_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_commande_statut(commande_id: int, statut: str):
    """Met à jour le statut d'une commande."""
    if statut not in ['PENDING', 'PROCESSING', 'DONE', 'ERROR']:
        raise ValueError("Statut invalide")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE commandes SET statut_global = ? WHERE id = ?', (statut, commande_id))
    conn.commit()
    conn.close()

def delete_commande(commande_id: int):
    """Supprime une commande (et ses tâches via CASCADE)."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM commandes WHERE id = ?', (commande_id,))
    conn.commit()
    conn.close()

# Fonctions CRUD pour taches

def create_tache(commande_id: int, ordre: int, type_tache: str, config: dict, quantite_totale: int) -> int:
    """Crée une nouvelle tâche et retourne l'id."""
    if type_tache not in ['BATCH', 'SERIES']:
        raise ValueError("Type de tâche invalide")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    config_json = json.dumps(config) if config else None
    statut = 'PENDING'
    cursor.execute('''
        INSERT INTO taches (commande_id, ordre, type_tache, config_json, quantite_totale, statut)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (commande_id, ordre, type_tache, config_json, quantite_totale, statut))
    tache_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return tache_id

def get_taches_by_commande(commande_id: int) -> List[Tuple]:
    """Retourne toutes les tâches d'une commande."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, commande_id, ordre, type_tache, config_json, quantite_totale, quantite_faite, statut FROM taches WHERE commande_id = ? ORDER BY ordre', (commande_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_tache(tache_id: int) -> Tuple:
    """Retourne une tâche par id."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, commande_id, ordre, type_tache, config_json, quantite_totale, quantite_faite, statut FROM taches WHERE id = ?', (tache_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_tache_statut(tache_id: int, statut: str):
    """Met à jour le statut d'une tâche."""
    if statut not in ['PENDING', 'IN_PROGRESS', 'DONE', 'ERROR']:
        raise ValueError("Statut invalide")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE taches SET statut = ? WHERE id = ?', (statut, tache_id))
    conn.commit()
    conn.close()

def update_tache_progress(tache_id: int, quantite_faite: int):
    """Met à jour la quantité faite d'une tâche."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE taches SET quantite_faite = ? WHERE id = ?', (quantite_faite, tache_id))
    conn.commit()
    conn.close()

def delete_tache(tache_id: int):
    """Supprime une tâche."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM taches WHERE id = ?', (tache_id,))
    conn.commit()
    conn.close()

# Fonction utilitaire pour parser config_json
def parse_config_json(config_json: str) -> dict:
    """Parse la config JSON."""
    return json.loads(config_json) if config_json else {}
