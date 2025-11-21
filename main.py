from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from typing import List
import json
import os
from database import create_commande, create_tache, get_commandes, get_taches_by_commande, parse_config_json
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
    """Initialise la connexion à l'imprimante et démarre le worker."""
    global printer, worker_running
    try:
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
            with open(file_path, "wb") as f:
                content = await file.read()
                f.write(content)
            saved_files[file.filename] = file_path

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

# Point d'entrée pour lancer le serveur (si exécuté directement)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
