from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from typing import List
import json
import os
import sqlite3
from database import (
    init_db, add_missing_columns_if_needed, create_commande, get_commande, delete_commande, create_tache, get_commandes, get_taches_by_commande, parse_config_json,
    create_product, get_products, get_product, update_product, delete_product, get_product_image_path, DB_FILE
)
from printer_driver import PrinterDriver
from worker import run_worker
from usb_lock import printer_lock

app = FastAPI(title="Print Server API")

# Gestion CORS pour l'interface frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # À restreindre en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir les fichiers statiques (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Servir les fichiers uploads (images des produits et tâches)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Instances globales
printer: PrinterDriver = None
worker_running: bool = False

def get_printer_instance() -> PrinterDriver:
    """Accesseur thread-safe pour l'instance de l'imprimante."""
    return printer

def set_worker_pause(state: bool):
    """Modifie l'état de pause du worker."""
    import worker
    worker.paused = state

@app.on_event("startup")
async def startup_event():
    """Initialise la base de données, le dossier uploads, la connexion à l'imprimante et démarre le worker."""
    global printer, worker_running
    try:
        # Créer le dossier uploads s'il n'existe pas
        os.makedirs("uploads", exist_ok=True)
        print("Dossier uploads vérifié/créé.")

        # Initialiser la base de données
        init_db()
        add_missing_columns_if_needed()
        print("Base de données initialisée et mise à jour.")

        printer = PrinterDriver()
        run_worker(printer)
        worker_running = True
        print("Imprimante connectée et worker démarré.")
    except Exception as e:
        print(f"Erreur lors de l'initialisation: {e}")
        printer = None
        worker_running = False

@app.on_event("shutdown")
async def shutdown_event():
    """Déconnexion propre."""
    global printer
    if printer:
        printer.disconnect()
        print("Imprimante déconnectée.")

@app.get("/", response_class=HTMLResponse)
async def get_index():
    """Sert la page d'accueil du dashboard."""
    with open("templates/index.html") as f:
        return f.read()

@app.get("/new-task", response_class=HTMLResponse)
async def get_new_task():
    """Sert la page de création de nouvelle tâche."""
    with open("templates/new_task.html") as f:
        return f.read()

@app.get("/archive", response_class=HTMLResponse)
async def get_archive():
    """Sert la page d'archive des tâches terminées."""
    with open("templates/archive.html") as f:
        return f.read()

@app.get("/products", response_class=HTMLResponse)
async def get_products_page():
    """Sert la page de gestion des produits (autocollants enregistrés)."""
    with open("templates/products.html") as f:
        return f.read()

@app.get("/commandes", response_class=HTMLResponse)
async def get_commandes_page():
    """Sert la page de gestion des commandes."""
    with open("templates/commandes.html") as f:
        return f.read()

@app.get("/api/jobs")
async def get_jobs():
    """Renvoie la liste des commandes avec leurs tâches imbriquées."""
    commands = get_commandes()
    jobs = []
    for cmd in commands:
        cmd_id = cmd[0]
        tasks_raw = get_taches_by_commande(cmd_id)
        tasks = []
        for t in tasks_raw:
            tasks.append({
                "id": t[0],
                "ordre": t[2],
                "type_tache": t[3],
                "config": parse_config_json(t[4]),
                "quantite_totale": t[5],
                "quantite_faite": t[6],
                "statut": t[7]
            })
        jobs.append({
            "id": cmd_id,
            "nom_client": cmd[1],
            "reference_externe": cmd[2],
            "date_creation": cmd[3],
            "statut": cmd[4],
            "taches": tasks
        })
    return jobs

@app.get("/api/commandes")
async def get_commandes_list():
    """Renvoie la liste des vraies commandes (pas les tâches simples)."""
    commands = get_commandes(type_commande='REGULAR')
    jobs = []
    for cmd in commands:
        cmd_id = cmd[0]
        tasks_raw = get_taches_by_commande(cmd_id)
        tasks = []
        for t in tasks_raw:
            tasks.append({
                "id": t[0],
                "ordre": t[2],
                "type_tache": t[3],
                "config": parse_config_json(t[4]),
                "quantite_totale": t[5],
                "quantite_faite": t[6],
                "statut": t[7]
            })
        jobs.append({
            "id": cmd_id,
            "nom_client": cmd[1],
            "reference_externe": cmd[2],
            "date_creation": cmd[3],
            "statut": cmd[4],
            "taches": tasks
        })
    return jobs

@app.post("/api/commandes")
async def create_commande_from_form(
    command_json: str = Form(..., description="JSON de la commande"),
    files: List[UploadFile] = File(None, description="Fichiers images à uploader")
):
    """Crée une nouvelle commande depuis le formulaire (toujours REGULAR)."""
    return await _create_job_with_type(command_json, files, 'REGULAR')

@app.post("/api/jobs")
async def create_job(
    command_json: str = Form(..., description="JSON de la commande sous forme de string"),
    files: List[UploadFile] = File(None, description="Fichiers images à uploader")
):
    """Crée une nouvelle commande avec ses tâches - détecte automatiquement le type."""
    data = json.loads(command_json)

    # Si c'est une tâche simple (généralement de la page "nouvelle tâche"), ou si une seule tâche avec nom_client générique
    if len(data.get("taches", [])) == 1 and (data.get("nom_client", "").startswith("Tâche simple") or not data.get("reference_externe")):
        type_commande = 'SIMPLE_TASK'
    else:
        type_commande = 'REGULAR'

    return await _create_job_with_type(command_json, files, type_commande)

async def _create_job_with_type(command_json: str, files: List[UploadFile], type_commande: str):
    """Fonction commune pour créer une commande avec un type spécifique."""
    print(f"🚀 [ENTRYPOINT] create_job appelée (type: {type_commande})")
    print(f"📨 [DEBUG] command_json: {command_json[:200]}...")  # Debug limité

    # Debugger les paramètres reçus
    print(f"📨 [DEBUG] files count: {len(files) if files else 0}")  # Debug
    for i, file in enumerate(files or []):
        print(f"📨 [DEBUG] File {i}: {file.filename}, size: {getattr(file, 'size', 'unknown')}")  # Debug

    try:
        command_data = json.loads(command_json)
        print(f"📋 [DEBUG] Données parsées: {json.dumps(command_data, indent=2)}")  # Debug

        # Validation des données
        if "taches" not in command_data:
            print("❌ [DEBUG] Erreur: pas de 'taches' dans les données")
            return {"error": "Données manquantes: taches"}

        for i, task in enumerate(command_data["taches"]):
            print(f"📋 [DEBUG] Tâche {i}: {task}")
            required_fields = ["type", "quantite", "config"]
            for field in required_fields:
                if field not in task:
                    print(f"❌ [DEBUG] Erreur: tâche {i} manque le champ '{field}'")
                    return {"error": f"Tâche {i} manquante champ: {field}"}

    except json.JSONDecodeError as e:
        print(f"❌ [DEBUG] Erreur JSON parsing: {e}")  # Debug
        return {"error": f"JSON invalide pour la commande: {str(e)}"}

    # Créer le dossier uploads s'il n'existe pas
    os.makedirs("uploads", exist_ok=True)

    # Sauvegarder les fichiers uploadés et mapper les noms
    saved_files = {}
    if files:  # Vérifier que files n'est pas None (cas des produits existants)
        for file in files:
            if file.filename:
                file_path = f"uploads/{file.filename}"
                try:
                    with open(file_path, "wb") as f:
                        content = await file.read()
                        f.write(content)
                    saved_files[file.filename] = os.path.abspath(file_path)  # Chemin absolu
                except Exception as e:
                    return {"error": f"Erreur sauvegarde fichier {file.filename}: {str(e)}"}

    # Pour les produits existants, ajouter leur chemin aux saved_files
    # Vérifier si on a des produits existants (product_id présent dans config)
    has_products = any("product_id" in task["config"] and task["config"]["product_id"]
                      for task in command_data.get("taches", []))

    if has_products:  # On utilise des produits existants
        for task in command_data.get("taches", []):
            config = task["config"]
            if "product_id" in config and config["product_id"]:
                # Récupérer les infos du produit depuis la BDD
                product_raw = get_product(config["product_id"])
                if product_raw:
                    image_filename = product_raw[5]  # image_path de la BDD (nom seulement)
                    image_abs_path = os.path.abspath(f"uploads/{image_filename}")

                    # Ajouter à saved_files pour que le mapping fonctionne
                    saved_files[image_filename] = image_abs_path
                    print(f"📁 [DEBUG] Produit {config['product_id']} - fichier: {image_filename}, chemin: {image_abs_path}")

                    # Vérifier que le fichier existe réellement
                    if not os.path.exists(image_abs_path):
                        print(f"❌ [DEBUG] Fichier manquant: {image_abs_path}")
                        return {"error": f"Fichier image manquant pour le produit {config['product_id']}: {image_filename}"}
                    else:
                        print(f"✅ [DEBUG] Fichier trouvé: {image_abs_path}")

    # Modifier les chemins d'images dans les configs des tâches
    for task in command_data.get("taches", []):
        config = task["config"]
        if task["type"] == "BATCH" and "image_path" in config:
            # Remplacer le nom de fichier par le chemin sauvegardé
            old_path = config["image_path"]
            config["image_path"] = saved_files.get(config["image_path"], config["image_path"])
            print(f"📁 [DEBUG] Mapping image_path: {old_path} -> {config['image_path']}")
        elif task["type"] == "SERIES" and "images" in config:
            config["images"] = [saved_files.get(img, img) for img in config["images"]]
        elif task["type"] == "BATCH" and "product_id" in config:
            # Pour les produits existants, récupérer le chemin de l'image depuis saved_files
            product_id = config["product_id"]
            product_raw = get_product(product_id)
            if product_raw:
                image_filename = product_raw[5]  # image_path de la BDD
                config["image_path"] = saved_files.get(image_filename, os.path.abspath(f"uploads/{image_filename}"))
                print(f"📁 [DEBUG] Produit {product_id}: ajouté image_path {config['image_path']}")

    # Créer la commande en BDD avec le type spécifié
    cmd_id = create_commande(
        command_data["nom_client"],
        command_data.get("reference_externe"),
        type_commande
    )

    # Créer les tâches pour cette commande
    ordre = 0
    tasks_created = []
    for task_data in command_data.get("taches", []):
        ordre += 1
        print(f"🛠️ [TASK_CREATION] Création tâche {ordre}/{len(command_data.get('taches', []))}:")
        print(f"🛠️ [TASK_CREATION]   Type: {task_data['type']}")
        print(f"🛠️ [TASK_CREATION]   Quantité: {task_data['quantite']}")
        print(f"🛠️ [TASK_CREATION]   Config: {task_data['config']}")

        task_id = create_tache(
            cmd_id,
            ordre,
            task_data["type"],
            task_data["config"],
            task_data["quantite"]
        )
        tasks_created.append(task_id)
        print(f"🛠️ [TASK_CREATION]   ID créé: {task_id}")

    print(f"✅ [BATCH] Commande {cmd_id} créée avec {len(tasks_created)} tâches: {tasks_created}")
    return {"job_id": cmd_id, "message": "Commande créée avec succès", "type": type_commande}

@app.post("/api/control/pause")
async def pause_worker():
    """Met le worker en pause (ex: changement de papier)."""
    set_worker_pause(False)
    return {"status": "Worker mis en pause"}

@app.post("/api/control/resume")
async def resume_worker():
    """Relance le worker après pause."""
    set_worker_pause(True)
    return {"status": "Worker relancé"}

@app.get("/api/printer/status")
async def get_printer_status():
    """Renvoie l'état détaillé actuel de l'imprimante avec tous les codes de statut."""
    # CONTRAINTE CRITIQUE : L'API ne doit JAMAIS bloquer
    # Utilise printer_lock.acquire(blocking=False) pour ne pas attendre le worker

    if not printer:
        return {"status": "Disconnected", "detail": "Imprimante non initialisée", "is_error": True}

    # Si le verrou est disponible (worker ne travaille pas), on peut accéder à l'USB
    if printer_lock.acquire(blocking=False):
        try:
            # Le worker n'utilise pas l'imprimante, on peut lire le statut réel
            status = printer.get_status()

            # Retourner TOUTES les informations du driver pour précision maximale
            result = {
                "status": "Ready", # Valeur par défaut
                "detail": "",
                "phase": status['phase'],
                "raw_phase": status['raw_phase'],
                "is_busy": status['is_busy'],
                "is_cooling": status['is_cooling'],
                "paper_empty": status['paper_empty'],
                "cover_open": status['cover_open'],
                "is_error": status['is_error']
            }

            # Déterminer le statut principal basé sur les flags les plus prioritaires
            if status['cover_open']:
                result["status"] = "Cover Open"
                result["detail"] = "Couvercle ouvert - Ouvrez le capot pour accéder à l'imprimante"
            elif status['paper_empty']:
                result["status"] = "Paper Empty"
                result["detail"] = "Papier épuisé - Insérez de nouveaux étiquettes"
            elif status['phase'] == 'COOLING':
                result["status"] = "Cooling"
                result["detail"] = f"Refroidissement en cours (phase brute: {status['raw_phase']}) - L'imprimante chauffe, veuillez patienter"
            elif status['is_busy']:
                result["status"] = "Busy"
                result["detail"] = f"Impression en cours (phase brute: {status['raw_phase']}) - Tâche active"
            else:
                result["status"] = "Ready"
                result["detail"] = f"Prêt à imprimer (phase brute: {status['raw_phase']}) - Prêt pour nouvelle tâche"

            return result

        except Exception as e:
            return {
                "status": "Error",
                "detail": f"Erreur de communication: {str(e)}",
                "phase": "UNKNOWN",
                "is_error": True
            }
        finally:
            printer_lock.release()
    else:
        # Le verrou est pris par le worker - retourner immédiatement un statut BUSY simulé
        # Cela évite tout accès concurrent à l'USB qui pourrait causer des erreurs
        return {
            "status": "Busy",
            "detail": "Worker is printing - Real-time status temporarily unavailable",
            "phase": "WORKER_BUSY",
            "raw_phase": 0,
            "is_busy": True,
            "is_cooling": False,
            "paper_empty": False,
            "cover_open": False,
            "is_error": False
        }

# API Routes pour les produits (autocollants enregistrés)

@app.get("/api/products")
async def get_products_list():
    """Renvoie la liste des produits actifs."""
    products_raw = get_products(actif_only=True)
    products = []
    for p in products_raw:
        products.append({
            "id": p[0],
            "nom": p[1],
            "description": p[2],
            "format_type": p[3],
            "rotation": p[4],
            "image_path": p[5],
            "date_creation": p[6]
        })
    return products

@app.get("/api/products/{product_id}")
async def get_product_detail(product_id: int):
    """Renvoie les détails d'un produit spécifique."""
    product_raw = get_product(product_id)
    if not product_raw:
        return {"error": "Produit non trouvé"}

    return {
        "id": product_raw[0],
        "nom": product_raw[1],
        "description": product_raw[2],
        "format_type": product_raw[3],
        "rotation": product_raw[4],
        "image_path": product_raw[5],
        "date_creation": product_raw[6],
        "actif": product_raw[7]
    }

@app.post("/api/products")
async def create_product_api(
    product_json: str = Form(..., description="JSON du produit"),
    file: UploadFile = File(..., description="Fichier image")
):
    """Crée un nouveau produit."""
    try:
        product_data = json.loads(product_json)
    except json.JSONDecodeError:
        return {"error": "JSON invalide pour le produit"}

    # Créer le dossier uploads s'il n'existe pas
    os.makedirs("uploads", exist_ok=True)

    # Sauvegarder le fichier uploadé
    file_path = f"uploads/{file.filename}"
    try:
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        return {"error": f"Erreur sauvegarde fichier: {str(e)}"}

    # Créer le produit en BDD
    product_id = create_product(
        product_data["nom"],
        product_data.get("description"),
        product_data["format_type"],
        product_data["rotation"],
        file.filename  # On sauvegarde seulement le nom du fichier, pas le chemin complet
    )

    return {
        "product": {
            "id": product_id,
            "nom": product_data["nom"],
            "description": product_data.get("description"),
            "format_type": product_data["format_type"],
            "rotation": product_data["rotation"],
            "image_path": file.filename
        }
    }

@app.delete("/api/products/{product_id}")
async def delete_product_api(product_id: int):
    """Supprime (désactive) un produit."""
    try:
        delete_product(product_id)
        return {"message": "Produit supprimé"}
    except Exception as e:
        return {"error": str(e)}

@app.delete("/api/commandes/{commande_id}")
async def delete_commande_api(commande_id: int):
    """Supprime une commande (seulement si elle n'est pas en cours d'impression)."""
    try:
        # Vérifier si la commande peut être supprimée (pas en cours d'impression)
        commande_data = get_commande(commande_id)
        if not commande_data:
            return {"error": "Commande non trouvée"}

        print(f"🗑️ [DELETE] Tentative suppression commande {commande_id}, statut: {commande_data[4]}")

        if commande_data[4] in ['PROCESSING']:  # statut_global
            print(f"🗑️ [DELETE] Commande {commande_id} en cours d'impression, suppression refusée")
            return {"error": "Impossible de supprimer une commande en cours d'impression"}

        print(f"🗑️ [DELETE] Suppression commande {commande_id} autorisée")
        delete_commande(commande_id)
        print(f"🗑️ [DELETE] Commande {commande_id} supprimée avec succès")
        return {"message": "Commande supprimée"}
    except Exception as e:
        print(f"🗑️ [DELETE] Erreur suppression commande {commande_id}: {e}")
        return {"error": str(e)}

@app.delete("/api/taches/{tache_id}")
async def delete_tache_api(tache_id: int):
    """Supprime une tâche individuelle (seulement si elle n'est pas en cours d'impression)."""
    import time

    max_retries = 3

    def _execute_with_retry(query, params=None, retry_delay=0.1):
        """Exécute une requête SQL avec retry automatique en cas de database locked."""
        for attempt in range(max_retries):
            try:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                return True
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    print(f"🔄 [DB_LOCK] Tentative {attempt + 1}/{max_retries} - database locked, retry dans {retry_delay}s")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Backoff exponentiel
                else:
                    raise e
        return False

    try:
        print(f"🗑️ [TASK_DELETE] Tentative suppression tâche {tache_id}")

        # Utiliser une seule connexion pour toutes les opérations
        conn = sqlite3.connect(DB_FILE, timeout=10.0)  # Timeout plus long
        cursor = conn.cursor()

        try:
            # Récupérer les infos de la tâche pour vérification
            _execute_with_retry("""
                SELECT t.statut, t.commande_id, c.statut_global
                FROM taches t
                JOIN commandes c ON t.commande_id = c.id
                WHERE t.id = ?
            """, (tache_id,))

            task_data = cursor.fetchone()

            if not task_data:
                print(f"🗑️ [TASK_DELETE] Tâche {tache_id} non trouvée")
                return {"error": "Tâche non trouvée"}

            task_status, command_id, command_status = task_data
            print(f"🗑️ [TASK_DELETE] Tâche {tache_id}: statut='{task_status}', commande={command_id} (statut='{command_status}')")

            # Vérifier si la tâche peut être supprimée
            if task_status in ['PROCESSING', 'IN_PROGRESS']:
                print(f"🗑️ [TASK_DELETE] Tâche {tache_id} en cours d'impression, suppression refusée")
                return {"error": "Impossible de supprimer une tâche en cours d'impression"}

            if command_status == 'PROCESSING':
                print(f"🗑️ [TASK_DELETE] La commande {command_id} est en cours d'impression, suppression de tâche refusée")
                return {"error": "Impossible de supprimer une tâche tant que la commande est en cours d'impression"}

            # Marquer la tâche comme DONE (logiquement supprimée)
            _execute_with_retry("UPDATE taches SET statut = 'DONE' WHERE id = ?", (tache_id,))

            # Vérifier si c'était la dernière tâche en attente de la commande
            _execute_with_retry("""
                SELECT COUNT(*) FROM taches
                WHERE commande_id = ? AND statut IN ('PENDING', 'IN_PROGRESS')
            """, (command_id,))

            remaining_tasks = cursor.fetchone()[0]

            if remaining_tasks == 0:
                # Plus de tâches actives - marquer la commande comme DONE
                _execute_with_retry("UPDATE commandes SET statut_global = 'DONE' WHERE id = ?", (command_id,))
                print(f"🗑️ [TASK_DELETE] Dernière tâche supprimée - commande {command_id} marquée DONE")

            conn.commit()
            print(f"🗑️ [TASK_DELETE] Tâche {tache_id} supprimée avec succès (statut=CANCELLED)")
            return {"message": f"Tâche {tache_id} supprimée"}

        finally:
            conn.close()

    except sqlite3.OperationalError as e:
        if "database is locked" in str(e):
            print(f"🗑️ [TASK_DELETE] Erreur suppression tâche {tache_id}: database is locked après {max_retries} tentatives")
            return {"error": "Base de données occupée, veuillez réessayer dans quelques instants"}
        else:
            print(f"🗑️ [TASK_DELETE] Erreur opérationnelle suppression tâche {tache_id}: {e}")
            return {"error": str(e)}
    except Exception as e:
        print(f"🗑️ [TASK_DELETE] Erreur suppression tâche {tache_id}: {e}")
        return {"error": str(e)}

# Point d'entrée pour lancer le serveur (si exécuté directement)
if __name__ == "__main__":
    import uvicorn
    print("Démarrage du Print Server...")
    print("Accès via : http://localhost:8000")
    print("Appuyez Ctrl+C pour arrêter")
    uvicorn.run(app, host="0.0.0.0", port=8000)
