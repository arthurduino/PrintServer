import sqlite3
import json
import os
from datetime import datetime
from typing import List, Optional, Dict, Any

# Configuration de la base de données
DB_FILE = "printserver.db"

def init_db():
    """Initialise la base de données avec toutes les tables nécessaires."""
    print("Initialisation de la base de données...")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Table commandes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commandes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom_client TEXT NOT NULL,
            reference_externe TEXT,
            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            statut_global TEXT DEFAULT 'PENDING',
            type_commande TEXT DEFAULT 'SIMPLE_TASK'
        )
    ''')

    # Table taches
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS taches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            commande_id INTEGER NOT NULL,
            ordre INTEGER NOT NULL,
            type_tache TEXT NOT NULL,
            config_json TEXT NOT NULL,
            quantite_totale INTEGER NOT NULL,
            quantite_faite INTEGER DEFAULT 0,
            statut TEXT DEFAULT 'PENDING',
            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            priorite INTEGER DEFAULT 1,
            cooling_until REAL DEFAULT 0,
            FOREIGN KEY (commande_id) REFERENCES commandes (id)
        )
    ''')

    # Table produits (autocollants enregistrés)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS produits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            description TEXT,
            format_type TEXT NOT NULL,
            rotation INTEGER DEFAULT 0,
            image_path TEXT NOT NULL,
            date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            actif BOOLEAN DEFAULT 1
        )
    ''')

    conn.commit()
    conn.close()
    print("Base de données initialisée avec succès.")

def add_missing_columns_if_needed():
    """Ajoute les colonnes manquantes à la base de données si elles n'existent pas."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        # Vérifier si la colonne priorite existe
        cursor.execute("PRAGMA table_info(taches)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        if 'priorite' not in column_names:
            print("Ajout de la colonne 'priorite' à la table taches...")
            cursor.execute("ALTER TABLE taches ADD COLUMN priorite INTEGER DEFAULT 1")
            print("Colonne 'priorite' ajoutée.")

        # Vérifier si la colonne cooling_until existe
        if 'cooling_until' not in column_names:
            print("Ajout de la colonne 'cooling_until' à la table taches...")
            cursor.execute("ALTER TABLE taches ADD COLUMN cooling_until REAL DEFAULT 0")
            print("Colonne 'cooling_until' ajoutée.")

        conn.commit()

    except Exception as e:
        print(f"Erreur lors de l'ajout des colonnes: {e}")
    finally:
        conn.close()

# Fonctions de gestion des commandes
def create_commande(nom_client: str, reference_externe: Optional[str] = None, type_commande: str = 'SIMPLE_TASK') -> int:
    """Crée une nouvelle commande et retourne son ID."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO commandes (nom_client, reference_externe, type_commande, statut_global) VALUES (?, ?, ?, ?)",
        (nom_client, reference_externe, type_commande, 'PENDING')
    )
    cmd_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return cmd_id

def get_commandes(type_commande: Optional[str] = None) -> List[tuple]:
    """Récupère toutes les commandes, optionnellement filtrées par type."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    if type_commande:
        cursor.execute("SELECT * FROM commandes WHERE type_commande = ? ORDER BY id DESC", (type_commande,))
    else:
        cursor.execute("SELECT * FROM commandes ORDER BY id DESC")

    commands = cursor.fetchall()
    conn.close()
    return commands

def get_commande(commande_id: int) -> Optional[tuple]:
    """Récupère une commande spécifique par son ID."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM commandes WHERE id = ?", (commande_id,))
    commande = cursor.fetchone()
    conn.close()
    return commande

def delete_commande(commande_id: int):
    """Supprime une commande et toutes ses tâches associées."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM taches WHERE commande_id = ?", (commande_id,))
    cursor.execute("DELETE FROM commandes WHERE id = ?", (commande_id,))
    conn.commit()
    conn.close()

# Fonctions de gestion des tâches
def create_tache(commande_id: int, ordre: int, type_tache: str, config: Dict[str, Any], quantite: int) -> int:
    """Crée une nouvelle tâche pour une commande donnée."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO taches (commande_id, ordre, type_tache, config_json, quantite_totale) VALUES (?, ?, ?, ?, ?)",
        (commande_id, ordre, type_tache, json.dumps(config), quantite)
    )
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id

def get_taches_by_commande(commande_id: int) -> List[tuple]:
    """Récupère toutes les tâches d'une commande."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM taches WHERE commande_id = ? ORDER BY ordre", (commande_id,))
    tasks = cursor.fetchall()
    conn.close()
    return tasks

def parse_config_json(config_json: str) -> Dict[str, Any]:
    """Parse le JSON de configuration d'une tâche."""
    try:
        return json.loads(config_json)
    except json.JSONDecodeError:
        return {}

# Fonctions de gestion des produits
def create_product(nom: str, description: Optional[str], format_type: str, rotation: int, image_path: str) -> int:
    """Crée un nouveau produit."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO produits (nom, description, format_type, rotation, image_path) VALUES (?, ?, ?, ?, ?)",
        (nom, description, format_type, rotation, image_path)
    )
    product_id = cursor.lastrowid
    conn.commit()
    conn.close()
    print(f"Produit créé avec ID: {product_id}")
    return product_id

def get_products(actif_only: bool = True) -> List[tuple]:
    """Récupère tous les produits."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    if actif_only:
        cursor.execute("SELECT * FROM produits WHERE actif = 1 ORDER BY date_creation DESC")
    else:
        cursor.execute("SELECT * FROM produits ORDER BY date_creation DESC")

    products = cursor.fetchall()
    conn.close()
    return products

def get_product(product_id: int) -> Optional[tuple]:
    """Récupère un produit spécifique."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM produits WHERE id = ?", (product_id,))
    product = cursor.fetchone()
    conn.close()
    return product

def get_product_image_path(product_id: int) -> Optional[str]:
    """Récupère le chemin d'image d'un produit."""
    product = get_product(product_id)
    return product[5] if product else None

def update_product(product_id: int, nom: str, description: Optional[str], format_type: str, rotation: int) -> bool:
    """Met à jour un produit existant."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE produits SET nom = ?, description = ?, format_type = ?, rotation = ? WHERE id = ?",
        (nom, description, format_type, rotation, product_id)
    )
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success

def delete_product(product_id: int) -> bool:
    """Désactive un produit (soft delete)."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE produits SET actif = 0 WHERE id = ?", (product_id,))
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return success
