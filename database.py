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

    # Création de la table produits (autocollants enregistrés)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            description TEXT,
            format_type TEXT NOT NULL CHECK(format_type IN ('62', '48', '30')),
            rotation INTEGER NOT NULL CHECK(rotation IN (0, 90, 180, 270)),
            image_path TEXT NOT NULL,
            date_creation TEXT DEFAULT CURRENT_TIMESTAMP,
            actif BOOLEAN DEFAULT 1
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

# Fonctions CRUD pour produits (autocollants enregistrés)

def create_product(nom: str, description: Optional[str], format_type: str, rotation: int, image_path: str) -> int:
    """Crée un nouveau produit et retourne l'id."""
    if format_type not in ['62', '48', '30']:
        raise ValueError("Format invalide")
    if rotation not in [0, 90, 180, 270]:
        raise ValueError("Rotation invalide")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO products (nom, description, format_type, rotation, image_path, actif)
        VALUES (?, ?, ?, ?, ?, 1)
    ''', (nom, description, format_type, rotation, image_path))
    product_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return product_id

def get_products(actif_only: bool = True) -> List[Tuple]:
    """Retourne tous les produits (actifs seulement par défaut)."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if actif_only:
        cursor.execute('SELECT id, nom, description, format_type, rotation, image_path, date_creation FROM products WHERE actif = 1 ORDER BY date_creation DESC')
    else:
        cursor.execute('SELECT id, nom, description, format_type, rotation, image_path, date_creation, actif FROM products ORDER BY date_creation DESC')
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_product(product_id: int) -> Tuple:
    """Retourne un produit par id."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, nom, description, format_type, rotation, image_path, date_creation, actif FROM products WHERE id = ?', (product_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_product(product_id: int, nom: str, description: Optional[str], format_type: str, rotation: int):
    """Met à jour un produit."""
    if format_type not in ['62', '48', '30']:
        raise ValueError("Format invalide")
    if rotation not in [0, 90, 180, 270]:
        raise ValueError("Rotation invalide")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE products
        SET nom = ?, description = ?, format_type = ?, rotation = ?
        WHERE id = ?
    ''', (nom, description, format_type, rotation, product_id))
    conn.commit()
    conn.close()

def delete_product(product_id: int):
    """Supprime (désactive) un produit au lieu de le supprimer vraiment."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE products SET actif = 0 WHERE id = ?', (product_id,))
    conn.commit()
    conn.close()

def get_product_image_path(product_id: int) -> str:
    """Retourne le chemin de l'image d'un produit."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT image_path FROM products WHERE id = ? AND actif = 1', (product_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

# Fonction utilitaire pour parser config_json
def parse_config_json(config_json: str) -> dict:
    """Parse la config JSON."""
    return json.loads(config_json) if config_json else {}
