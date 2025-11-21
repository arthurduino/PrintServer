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

    # Création de la table products
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            sku TEXT,
            rotation INTEGER DEFAULT 0,
            image_path TEXT
        )
    ''')

    # Création de la table tasks (nouvelle table pour gestion des tâches avec priorités)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            priority INTEGER DEFAULT 0,  -- 0:Normal, 1:Haut, 2:Urgent, 3:Critique
            status TEXT NOT NULL CHECK(status IN ('TODO', 'IN_PROGRESS', 'DONE', 'ARCHIVED')),
            linked_type TEXT CHECK(linked_type IN ('IMAGE', 'BATCH', 'PRODUCT')),  -- Type d'élément lié
            linked_id TEXT,  -- ID ou chemin de l'élément lié (image_path, batch_id, product_id)
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            archived_at TEXT
        )
    ''')

    # Création de la table printer_stats pour les compteurs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS printer_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stat_type TEXT NOT NULL,  -- 'PRINT_COUNT', 'ERROR_COUNT', 'PAPER_CHANGES', etc.
            count INTEGER DEFAULT 0,
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Insertion des stats par défaut si elles n'existent pas
    cursor.execute('INSERT OR IGNORE INTO printer_stats (stat_type, count) VALUES (?, ?)', ('PRINT_COUNT', 0))
    cursor.execute('INSERT OR IGNORE INTO printer_stats (stat_type, count) VALUES (?, ?)', ('ERROR_COUNT', 0))
    cursor.execute('INSERT OR IGNORE INTO printer_stats (stat_type, count) VALUES (?, ?)', ('PAPER_CHANGES', 0))

    conn.commit()
    conn.close()

# Fonctions CRUD pour produits

def create_product(nom: str, sku: Optional[str] = None, rotation: int = 0, image_path: Optional[str] = None) -> int:
    """Crée un nouveau produit et retourne l'id."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO products (nom, sku, rotation, image_path)
        VALUES (?, ?, ?, ?)
    ''', (nom, sku, rotation, image_path))
    product_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return product_id

def get_products() -> List[Tuple]:
    """Retourne tous les produits."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, nom, sku, rotation, image_path FROM products ORDER BY nom')
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_product(product_id: int) -> Tuple:
    """Retourne un produit par id."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, nom, sku, rotation, image_path FROM products WHERE id = ?', (product_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_product(product_id: int, nom: str, sku: Optional[str] = None, rotation: int = 0, image_path: Optional[str] = None):
    """Met à jour un produit."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE products SET nom = ?, sku = ?, rotation = ?, image_path = ? WHERE id = ?
    ''', (nom, sku, rotation, image_path, product_id))
    conn.commit()
    conn.close()

def delete_product(product_id: int):
    """Supprime un produit."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
    conn.commit()
    conn.close()

# Fonctions CRUD pour tâches (nouvelle gestion des tâches)

def create_task(title: str, description: Optional[str] = None, priority: int = 0,
                linked_type: Optional[str] = None, linked_id: Optional[str] = None) -> int:
    """Crée une nouvelle tâche et retourne l'id."""
    if priority not in [0, 1, 2, 3]:
        raise ValueError("Priorité invalide (0-3)")
    if linked_type and linked_type not in ['IMAGE', 'BATCH', 'PRODUCT']:
        raise ValueError("Type de liaison invalide")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tasks (title, description, priority, status, linked_type, linked_id)
        VALUES (?, ?, ?, 'TODO', ?, ?)
    ''', (title, description, priority, linked_type, linked_id))
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id

def get_tasks(include_archived: bool = False) -> List[Tuple]:
    """Retourne toutes les tâches (archivées ou non selon le paramètre)."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    if include_archived:
        cursor.execute('''SELECT id, title, description, priority, status, linked_type, linked_id, created_at, updated_at, archived_at
                         FROM tasks ORDER BY priority DESC, created_at DESC''')
    else:
        cursor.execute('''SELECT id, title, description, priority, status, linked_type, linked_id, created_at, updated_at, archived_at
                         FROM tasks WHERE status != 'ARCHIVED' ORDER BY priority DESC, created_at DESC''')
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_task(task_id: int) -> Tuple:
    """Retourne une tâche par id."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, title, description, priority, status, linked_type, linked_id, created_at, updated_at, archived_at FROM tasks WHERE id = ?', (task_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def update_task_status(task_id: int, status: str):
    """Met à jour le statut d'une tâche."""
    if status not in ['TODO', 'IN_PROGRESS', 'DONE', 'ARCHIVED']:
        raise ValueError("Statut invalide")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    if status == 'ARCHIVED':
        cursor.execute("UPDATE tasks SET status = ?, archived_at = ? WHERE id = ?", (status, now, task_id))
    else:
        cursor.execute("UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?", (status, now, task_id))
    conn.commit()
    conn.close()

def update_task(task_id: int, title: str, description: Optional[str] = None, priority: int = 0,
                linked_type: Optional[str] = None, linked_id: Optional[str] = None):
    """Met à jour une tâche."""
    if priority not in [0, 1, 2, 3]:
        raise ValueError("Priorité invalide (0-3)")
    if linked_type and linked_type not in ['IMAGE', 'BATCH', 'PRODUCT']:
        raise ValueError("Type de liaison invalide")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute('''
        UPDATE tasks SET title = ?, description = ?, priority = ?, linked_type = ?, linked_id = ?, updated_at = ? WHERE id = ?
    ''', (title, description, priority, linked_type, linked_id, now, task_id))
    conn.commit()
    conn.close()

def delete_task(task_id: int):
    """Supprime une tâche."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()

# Fonctions pour les statistiques d'imprimante

def get_printer_stats() -> List[Tuple]:
    """Retourne toutes les statistiques d'imprimante."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, stat_type, count, last_updated FROM printer_stats')
    rows = cursor.fetchall()
    conn.close()
    return rows

def update_printer_stat(stat_type: str, increment: int = 1):
    """Incrémente un compteur de statistiques."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now = datetime.utcnow().isoformat()
    cursor.execute('''
        UPDATE printer_stats SET count = count + ?, last_updated = ? WHERE stat_type = ?
    ''', (increment, now, stat_type))

    # Si aucune ligne n'a été mise à jour, créer la stat
    if cursor.rowcount == 0:
        cursor.execute('INSERT INTO printer_stats (stat_type, count, last_updated) VALUES (?, ?, ?)',
                      (stat_type, increment, now))

    conn.commit()
    conn.close()

def get_printer_stat(stat_type: str) -> int:
    """Retourne la valeur d'une statistique."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT count FROM printer_stats WHERE stat_type = ?', (stat_type,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

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
