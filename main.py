from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from typing import List
import json
import os
from database import (init_db, create_commande, create_tache, get_commandes, get_taches_by_commande, parse_config_json,
                     create_product, get_products, get_product, update_product, delete_product,
                     create_task, get_tasks, get_task, update_task, update_task_status, delete_task,
                     get_printer_stats, get_printer_stat, update_printer_stat)
from printer_driver import PrinterDriver
from worker import run_worker

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
    """Initialise la base de données, la connexion à l'imprimante et démarre le worker."""
    global printer, worker_running
    try:
        # Initialiser la base de données
        init_db()
        print("Base de données initialisée.")

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

@app.post("/api/jobs")
async def create_job(
    command_json: str = Form(..., description="JSON de la commande sous forme de string"),
    files: List[UploadFile] = File(..., description="Fichiers images à uploader")
):
    """Crée une nouvelle commande avec ses tâches, gère l'upload des images."""
    try:
        command_data = json.loads(command_json)
    except json.JSONDecodeError:
        return {"error": "JSON invalide pour la commande"}

    # Créer le dossier uploads s'il n'existe pas
    os.makedirs("uploads", exist_ok=True)

    # Sauvegarder les fichiers uploadés et mapper les noms
    saved_files = {}
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

    # Modifier les chemins d'images dans les configs des tâches
    for task in command_data.get("taches", []):
        config = task["config"]
        if task["type"] == "BATCH" and "image_path" in config:
            # Remplacer le nom de fichier par le chemin sauvegardé
            config["image_path"] = saved_files.get(config["image_path"], config["image_path"])
        elif task["type"] == "SERIES" and "images" in config:
            config["images"] = [saved_files.get(img, img) for img in config["images"]]

    # Créer la commande en BDD
    cmd_id = create_commande(
        command_data["nom_client"],
        command_data.get("reference_externe")
    )

    # Créer les tâches pour cette commande
    ordre = 0
    for task_data in command_data.get("taches", []):
        ordre += 1
        create_tache(
            cmd_id,
            ordre,
            task_data["type"],
            task_data["config"],
            task_data["quantite"]
        )

    return {"job_id": cmd_id, "message": "Commande créée avec succès"}

@app.post("/api/control/pause")
async def pause_worker():
    """Met le worker en pause (ex: changement de papier)."""
    set_worker_pause(True)
    return {"status": "Worker mis en pause"}

@app.post("/api/control/resume")
async def resume_worker():
    """Relance le worker après pause."""
    set_worker_pause(False)
    return {"status": "Worker relancé"}

@app.get("/api/printer/status")
async def get_printer_status():
    """Renvoie l'état actuel de l'imprimante via une requête USB rapide."""
    if not printer:
        return {"status": "Disconnected", "detail": "Imprimante non initialisée"}

    try:
        status = printer.get_status()
        if status['cover_open']:
            return {"status": "Cover Open", "detail": "Couvercle ouvert", "phase": status['phase']}
        elif status['paper_empty']:
            return {"status": "Paper Empty", "detail": "Papier vide", "phase": status['phase']}
        elif status['phase'] == 'COOLING':
            return {"status": "Cooling", "detail": "Refroidissement en cours", "phase": status['phase']}
        elif status['is_busy']:
            return {"status": "Busy", "detail": "Impression en cours", "phase": status['phase']}
        else:
            return {"status": "Ready", "detail": "Prêt à imprimer", "phase": status['phase']}
    except Exception as e:
        return {"status": "Error", "detail": str(e), "phase": "UNKNOWN"}

# ===== API ROUTES POUR LES PRODUITS =====

@app.get("/products", response_class=HTMLResponse)
async def get_products_page():
    """Page de gestion des produits."""
    with open("templates/products.html") as f:
        return f.read()

@app.get("/api/products")
async def api_get_products():
    """Renvoie la liste de tous les produits."""
    products = get_products()
    return [{"id": p[0], "nom": p[1], "sku": p[2], "rotation": p[3], "image_path": p[4]} for p in products]

@app.get("/api/products/{product_id}")
async def api_get_product(product_id: int):
    """Renvoie un produit spécifique."""
    product = get_product(product_id)
    if not product:
        return {"error": "Produit non trouvé"}
    return {"id": product[0], "nom": product[1], "sku": product[2], "rotation": product[3], "image_path": product[4]}

@app.post("/api/products")
async def api_create_product(
    nom: str = Form(...),
    sku: str = Form(""),
    rotation: int = Form(0),
    image: UploadFile = File(None)
):
    """Crée un nouveau produit."""
    image_path = None
    if image and image.filename:
        os.makedirs("uploads/products", exist_ok=True)
        image_path = f"uploads/products/{image.filename}"
        with open(image_path, "wb") as f:
            content = await image.read()
            f.write(content)
        image_path = os.path.abspath(image_path)

    product_id = create_product(nom, sku if sku else None, rotation, image_path)
    return {"product_id": product_id, "message": "Produit créé avec succès"}

@app.put("/api/products/{product_id}")
async def api_update_product(
    product_id: int,
    nom: str = Form(...),
    sku: str = Form(""),
    rotation: int = Form(0),
    image: UploadFile = File(None)
):
    """Met à jour un produit."""
    image_path = None
    if image and image.filename:
        os.makedirs("uploads/products", exist_ok=True)
        image_path = f"uploads/products/{image.filename}"
        with open(image_path, "wb") as f:
            content = await image.read()
            f.write(content)
        image_path = os.path.abspath(image_path)
    else:
        # Conserver l'image existante si aucune nouvelle image n'est fournie
        existing = get_product(product_id)
        if existing:
            image_path = existing[4]

    update_product(product_id, nom, sku if sku else None, rotation, image_path)
    return {"message": "Produit mis à jour avec succès"}

@app.delete("/api/products/{product_id}")
async def api_delete_product(product_id: int):
    """Supprime un produit."""
    delete_product(product_id)
    return {"message": "Produit supprimé avec succès"}

# ===== API ROUTES POUR LES TÂCHES =====

@app.get("/tasks", response_class=HTMLResponse)
async def get_tasks_page():
    """Page de gestion des tâches."""
    with open("templates/tasks.html") as f:
        return f.read()

@app.get("/api/tasks")
async def api_get_tasks(include_archived: bool = False):
    """Renvoie la liste de toutes les tâches."""
    tasks = get_tasks(include_archived)
    return [{
        "id": t[0], "title": t[1], "description": t[2], "priority": t[3],
        "status": t[4], "linked_type": t[5], "linked_id": t[6],
        "created_at": t[7], "updated_at": t[8], "archived_at": t[9]
    } for t in tasks]

@app.get("/api/tasks/{task_id}")
async def api_get_task(task_id: int):
    """Renvoie une tâche spécifique."""
    task = get_task(task_id)
    if not task:
        return {"error": "Tâche non trouvée"}
    return {
        "id": task[0], "title": task[1], "description": task[2], "priority": task[3],
        "status": task[4], "linked_type": task[5], "linked_id": task[6],
        "created_at": task[7], "updated_at": task[8], "archived_at": task[9]
    }

@app.post("/api/tasks")
async def api_create_task(
    title: str = Form(...),
    description: str = Form(""),
    priority: int = Form(0),
    linked_type: str = Form(""),
    linked_id: str = Form("")
):
    """Crée une nouvelle tâche."""
    task_id = create_task(
        title,
        description if description else None,
        priority,
        linked_type if linked_type else None,
        linked_id if linked_id else None
    )
    return {"task_id": task_id, "message": "Tâche créée avec succès"}

@app.put("/api/tasks/{task_id}")
async def api_update_task(
    task_id: int,
    title: str = Form(...),
    description: str = Form(""),
    priority: int = Form(0),
    linked_type: str = Form(""),
    linked_id: str = Form("")
):
    """Met à jour une tâche."""
    update_task(
        task_id,
        title,
        description if description else None,
        priority,
        linked_type if linked_type else None,
        linked_id if linked_id else None
    )
    return {"message": "Tâche mise à jour avec succès"}

@app.put("/api/tasks/{task_id}/status")
async def api_update_task_status(task_id: int, status: str = Form(...)):
    """Met à jour le statut d'une tâche."""
    update_task_status(task_id, status)
    return {"message": f"Statut de la tâche mis à jour: {status}"}

@app.delete("/api/tasks/{task_id}")
async def api_delete_task(task_id: int):
    """Supprime une tâche."""
    delete_task(task_id)
    return {"message": "Tâche supprimée avec succès"}

# ===== API ROUTES POUR LA FILE D'ATTENTE/QUEUE =====

@app.get("/queue", response_class=HTMLResponse)
async def get_queue_page():
    """Page de la file d'attente des travaux."""
    with open("templates/queue.html") as f:
        return f.read()

@app.get("/api/queue")
async def api_get_queue():
    """Renvoie la file d'attente complète avec progression."""
    commands = get_commandes()
    taches_data = []

    # Récupérer toutes les tâches de toutes les commandes
    for cmd in commands:
        cmd_id = cmd[0]
        tasks_raw = get_taches_by_commande(cmd_id)
        for t in tasks_raw:
            taches_data.append({
                "id": t[0],
                "commande_id": cmd_id,
                "nom_client": cmd[1],
                "reference_externe": cmd[2],
                "ordre": t[2],
                "type_tache": t[3],
                "config": parse_config_json(t[4]),
                "quantite_totale": t[5],
                "quantite_faite": t[6],
                "statut": t[7],
                "date_creation": cmd[3],
                "statut_commande": cmd[4],
                "progress_percentage": (t[6] / t[5] * 100) if t[5] > 0 else 0
            })

    return taches_data

# ===== API ROUTES POUR LES STATISTIQUES =====

@app.get("/stats", response_class=HTMLResponse)
async def get_stats_page():
    """Page des statistiques."""
    with open("templates/stats.html") as f:
        return f.read()

@app.get("/api/stats")
async def api_get_stats():
    """Renvoie toutes les statistiques."""
    stats = get_printer_stats()
    printer_status = await get_printer_status()

    # Compter les tâches par statut
    tasks = get_tasks()
    task_stats = {
        "total": len(tasks),
        "todo": len([t for t in tasks if t[4] == 'TODO']),
        "in_progress": len([t for t in tasks if t[4] == 'IN_PROGRESS']),
        "done": len([t for t in tasks if t[4] == 'DONE']),
        "archived": len([t for t in tasks if t[4] == 'ARCHIVED'])
    }

    # Compter les produits
    products = get_products()
    product_count = len(products)

    # Compter les commandes par statut
    commands = get_commandes()
    command_stats = {
        "total": len(commands),
        "pending": len([c for c in commands if c[4] == 'PENDING']),
        "processing": len([c for c in commands if c[4] == 'PROCESSING']),
        "done": len([c for c in commands if c[4] == 'DONE']),
        "error": len([c for c in commands if c[4] == 'ERROR'])
    }

    return {
        "printer": printer_status,
        "printer_counters": [{"type": s[1], "count": s[2], "last_updated": s[3]} for s in stats],
        "tasks": task_stats,
        "products": product_count,
        "commands": command_stats
    }

# Point d'entrée pour lancer le serveur (si exécuté directement)
if __name__ == "__main__":
    import uvicorn
    print("Démarrage du Print Server...")
    print("Accès via : http://localhost:8000")
    print("Appuyez Ctrl+C pour arrêter")
    uvicorn.run(app, host="0.0.0.0", port=8000)
