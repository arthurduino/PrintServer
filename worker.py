import sqlite3
import json
import time
import threading
import os
from typing import Optional
from database import DB_FILE, parse_config_json

# Import du nouveau service d'impression CUPS
try:
    from print_service import print_batch_cups
    print("✅ Service CUPS importé avec succès")
except ImportError as e:
    print(f"❌ Erreur importation service CUPS: {e}")
    print_batch_cups = None

# Modèle QL-700 comme string
MODEL = 'QL-700'
print(f"Modèle Brother QL-700: {MODEL}")

# État global du worker
paused = True  # True = actif, False = mis en pause

def run_worker():
    """Lance le worker en daemon thread pour traiter les tâches d'impression via CUPS."""
    # RÉCUPÉRATION APRÈS REDÉMARRAGE : remettre les tâches IN_PROGRESS orphelines en PENDING
    _recover_orphaned_tasks_on_startup()

    print("✅ Architecture CUPS - plus de gestion manuelle du refroidissement")

    thread = threading.Thread(target=_worker_loop, daemon=True)
    thread.start()
    print("Worker démarré en thread daemon avec CUPS - récupération d'état activée.")

def _worker_loop():
    """Boucle principale du worker pour traiter les tâches avec Brother_QL uniquement."""
    while True:
        # Vérifier si le worker est en pause
        if not paused:
            time.sleep(0.01)  # Sleep très court quand en pause
            continue

        task_data = _get_next_pending_task()
        if not task_data:
            time.sleep(0.01)  # Délai court pour réactivité
            continue

        task_id, cmd_id, type_t, config_json, qty_tot, qty_done = task_data
        config = parse_config_json(config_json)

        _set_processing(task_id, cmd_id)

        try:
            if type_t == 'BATCH':
                _process_batch_task(task_id, cmd_id, config, qty_tot)
            elif type_t == 'SERIES':
                _process_series_task(task_id, cmd_id, config, qty_tot)
            else:
                raise ValueError(f"Type de tâche inconnu: {type_t}")

            # Après succès, marque la tâche comme DONE
            _update_task_status(task_id, 'DONE')
            _check_command_completion(cmd_id)

        except Exception as e:
            print(f"Erreur lors du traitement de la tâche {task_id}: {e}")
            _update_task_status(task_id, 'ERROR')
            _update_command_status(cmd_id, 'ERROR')
            # Continuer immédiatement

def _get_next_pending_task() -> Optional[tuple]:
    """Récupère la prochaine tâche PENDING triée par priorité + ID commande + ordre."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT t.id, t.commande_id, t.type_tache, t.config_json, t.quantite_totale, t.quantite_faite
        FROM taches t
        JOIN commandes c ON t.commande_id = c.id
        WHERE t.statut = 'PENDING'
        ORDER BY t.priorite DESC, c.id, t.ordre
        LIMIT 1
    ''')
    task = cursor.fetchone()
    conn.close()
    return task

def _set_processing(task_id: int, cmd_id: int):
    """Marque la tâche et la commande en PROCESSING."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE taches SET statut = 'IN_PROGRESS' WHERE id = ?", (task_id,))
    cursor.execute("UPDATE commandes SET statut_global = 'PROCESSING' WHERE id = ?", (cmd_id,))
    conn.commit()
    conn.close()

def _update_task_status(task_id: int, status: str):
    """Met à jour le statut d'une tâche."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE taches SET statut = ? WHERE id = ?", (status, task_id))
    conn.commit()
    conn.close()

def _update_command_status(cmd_id: int, status: str):
    """Met à jour le statut global d'une commande."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE commandes SET statut_global = ? WHERE id = ?", (status, cmd_id))
    conn.commit()
    conn.close()

def _recover_orphaned_tasks_on_startup():
    """Remet les tâches IN_PROGRESS orphelines en PENDING après un redémarrage du process."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Trouver les tâches IN_PROGRESS (qui ont été interrompues par un crash/redémarrage)
    cursor.execute("SELECT id, commande_id, quantite_faite FROM taches WHERE statut = 'IN_PROGRESS'")
    orphaned_tasks = cursor.fetchall()

    if orphaned_tasks:
        print(f"🔄 RECOVERY: {len(orphaned_tasks)} tâches IN_PROGRESS orphelines trouvées au démarrage")

        for task_id, cmd_id, qty_done in orphaned_tasks:
            # Remettre la tâche en PENDING pour qu'elle soit reprise
            cursor.execute("UPDATE taches SET statut = 'PENDING' WHERE id = ?", (task_id,))
            cursor.execute("UPDATE commandes SET statut_global = 'PROCESSING' WHERE id = ? AND statut_global = 'DONE'", (cmd_id,))

            print(f"🔄 RECOVERY: Tâche {task_id} (commande {cmd_id}) - {qty_done} impressions déjà faites - remise en PENDING")

        conn.commit()
        print(f"✅ RECOVERY: {len(orphaned_tasks)} tâches récupérées avec succès")
    else:
        print("ℹ️  RECOVERY: Aucune tâche orpheline au démarrage")

    conn.close()

def _update_task_progress(task_id: int, qty_done: int):
    """Incrémente la quantité faite."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE taches SET quantite_faite = ? WHERE id = ?", (qty_done, task_id))
    conn.commit()
    conn.close()

def _get_task_progress(task_id: int) -> int:
    """Récupère la quantité déjà faite pour une tâche (pour reprise après redémarrage)."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT quantite_faite FROM taches WHERE id = ?", (task_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def _preprocess_image(image_path: str, task_id: int, config: dict) -> str:
    """Pré-traite l'image : redimensionnement automatique pour compatibilité Brother QL-700."""
    try:
        from PIL import Image
        print(f"🔧 [PREPROCESS] Analyse image: {image_path}")

        # Récupération des paramètres d'optimisation depuis la config
        dpi = config.get('dpi', 300)
        label_type = config.get('label_type', '62')

        # Ouvrir l'image pour analyse
        with Image.open(image_path) as img:
            original_width, original_height = img.size
            print(f"🔧 [PREPROCESS] Dimensions originales: {original_width}x{original_height}")

            # Dimensions cibles basées sur le DPI et le type d'étiquette
            target_width = int(696 * (dpi / 300))
            target_height = int((original_height * target_width) / original_width)

            # Limiter la hauteur maximale pour éviter les timeouts
            max_height = 1200  # ~100mm max pour éviter surcharge
            if target_height > max_height:
                target_height = max_height
                target_width = int((original_width * target_height) / original_height)

            print(f"🔧 [PREPROCESS] Dimensions cibles: {target_width}x{target_height}")

            # Redimensionner seulement si nécessaire
            if original_width != target_width or original_height > max_height:
                # Créer le répertoire temporaire s'il n'existe pas
                temp_dir = os.path.join(os.path.dirname(image_path), 'temp_processed')
                os.makedirs(temp_dir, exist_ok=True)

                # Générer le nouveau nom de fichier
                filename = f"processed_{task_id}_{int(time.time())}.png"
                processed_path = os.path.join(temp_dir, filename)

                # Redimensionner l'image
                resized_img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
                resized_img.save(processed_path, 'PNG')

                print(f"🔧 [PREPROCESS] Image redimensionnée sauvegardée: {processed_path}")
                return processed_path
            else:
                print(f"🔧 [PREPROCESS] Image déjà aux bonnes dimensions - utilisation directe")
                return image_path

    except ImportError:
        print("⚠️ [PREPROCESS] PIL/Pillow non installé - utilisation image originale")
        return image_path
    except Exception as e:
        print(f"⚠️ [PREPROCESS] Erreur lors du pré-traitement: {e} - utilisation image originale")
        return image_path

def _check_command_completion(cmd_id: int):
    """Vérifie si toutes les tâches de la commande sont DONE, si oui marque commande DONE."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM taches WHERE commande_id = ? AND statut != 'DONE'", (cmd_id,))
    pending_count = cursor.fetchone()[0]
    if pending_count == 0:
        cursor.execute("UPDATE commandes SET statut_global = 'DONE' WHERE id = ?", (cmd_id,))
        conn.commit()
    conn.close()

def _process_batch_task(task_id: int, cmd_id: int, config: dict, qty_tot: int):
    """Traite une tâche BATCH : envoie les étiquettes à CUPS et suit leur progression réelle."""
    if not print_batch_cups:
        raise ImportError("Service CUPS non disponible")

    image_path = config.get('image_path')
    if not image_path:
        raise ValueError("Config BATCH manquante: image_path")

    print(f"📁 [WORKER] Image path reçu: {image_path}")
    print(f"📁 [WORKER] Fichier existe: {os.path.exists(image_path)}")

    try:
        from print_service import PRINTER_NAME
        import cups

        # 1. PRÉ-TRAITEMENT DE L'IMAGE (Redimensionnement automatique)
        processed_image_path = _preprocess_image(image_path, task_id, config)
        print(f"🔧 [WORKER] Image pré-traitée: {processed_image_path}")

        # 2. CRÉATION DE LA LISTE DES FICHIERS À IMPRIMER
        image_paths = [processed_image_path] * qty_tot  # qty_tot copies du même fichier
        print(f"📋 [CUPS] Préparation {qty_tot} étiquettes identiques pour tâche {task_id}")

        # 3. ENVOI À CUPS AVEC SUIVI DES JOBS CUPS
        qty_done = _get_task_progress(task_id)  # Récupérer la progression actuelle
        success = print_batch_cups_with_tracking(image_paths, f"TASK_{task_id}", task_id, qty_tot, qty_done)
        if success:
            print(f"✅ [CUPS] Tous les {qty_tot} étiquettes envoyées et confirmées terminées pour tâche {task_id}")
        else:
            raise Exception("Échec d'envoi à CUPS")

    except Exception as e:
        print(f"❌ Erreur dans _process_batch_task (tâche {task_id}): {e}")
        _update_task_status(task_id, 'ERROR')
        _update_command_status(cmd_id, 'ERROR')
        import traceback
        traceback.print_exc()
        raise

def print_batch_cups_with_tracking(image_paths, job_id, task_id, qty_tot, qty_done=0):
    """
    Envoie un batch d'images à CUPS et attend la fin réelle de chaque impression.
    Met à jour la progression en temps réel basé sur les jobs CUPS terminés.
    qty_done permet de reprendre une tâche déjà commencée.
    """
    try:
        import cups
        from print_service import PRINTER_NAME
    except ImportError:
        print("❌ Impossible d'importer CUPS ou print_service")
        return False

    conn = cups.Connection()

    # Vérification présence imprimante
    printers = conn.getPrinters()
    if PRINTER_NAME not in printers:
        print(f"ERREUR: L'imprimante '{PRINTER_NAME}' n'est pas installée dans CUPS.")
        return False

    print(f"🚀 Début du job suivi {job_id} via CUPS ({len(image_paths)} étiquettes)")
    print(f"📊 [TRACKING] Déjà {qty_done} fait(s), suivi en temps réel pour tâche {task_id}")

    # Configuration des options d'impression Brother
    options = {
        "PageSize": "62x29mm",
        "BrPriority": "BrQuality",
        "BrBrightness": "7",
        "BrCutAtEnd": "ON"
    }

    cups_job_ids = []  # Liste des job IDs CUPS créés

    # 1. ENVOI DE TOUS LES FICHIERS À CUPS (seulement ceux pas encore faits)
    images_remaining = qty_tot - qty_done
    print(f"📋 [BATCH] Envoi de {images_remaining} étiquettes restantes ({qty_done} déjà faites)")

    for index, img_path in enumerate(image_paths[:images_remaining]):
        if not os.path.exists(img_path):
            print(f"⚠️ Fichier manquant : {img_path}")
            continue

        try:
            img_options = options.copy()
            img_options["orientation-requested"] = "4"  # 90° clockwise

            # Envoi à CUPS avec les options appropriées
            cups_job_id = conn.printFile(PRINTER_NAME, img_path, f"Job_{job_id}_{index+1}", img_options)
            cups_job_ids.append(cups_job_id)
            print(f"✅ Étiquette {index+1}/{images_remaining} envoyé (ID CUPS: {cups_job_id})")

            time.sleep(0.1)  # Petit délai pour éviter la surcharge

        except cups.IPPError as e:
            print(f"❌ Erreur CUPS sur l'image {img_path}: {e}")
            return False

    if not cups_job_ids:
        print(f"⚠️ [TRACKING] Aucune nouvelle étiquette à envoyer - déjà {qty_done}/{qty_tot} fait(es)")
        return True  # Rien à faire, considérer succès

    print(f"📋 Tous les {len(cups_job_ids)} nouveaux fichiers transmis au spooler système")
    print(f"⏳ [TRACKING] Attente de la fin réelle des impressions...")

    # 2. SUIVI DES JOBS CUPS EN TEMPS RÉEL
    completed_count = qty_done  # Commencer avec la quantité déjà faite
    pending_jobs = cups_job_ids.copy()  # Copie pour éviter les problèmes de modification pendant l'itération
    max_wait_time = 300  # 5 minutes timeout maximum
    start_time = time.time()

    while completed_count < qty_tot and (time.time() - start_time) < max_wait_time:
        try:
            # Récupération de l'état de tous les jobs CUPS
            jobs_status = conn.getJobs(which_jobs='all', requested_attributes=['id', 'job-state'])

            # Vérification de nos jobs en cours
            jobs_to_remove = []  # Collecter les jobs à retirer

            for job_id in pending_jobs:
                if job_id in jobs_status:
                    state = jobs_status[job_id].get('job-state', 0)
                    # États terminés : 7=canceled, 8=aborted, 9=completed
                    if state in [7, 8, 9]:
                        completed_count += 1
                        jobs_to_remove.append(job_id)
                        print(f"📊 [TRACKING] Job CUPS {job_id} terminé (état: {state})")
                        print(f"📊 [TRACKING] Progression cumulée: {completed_count}/{qty_tot} étiquettes terminées")

            # Retirer les jobs terminés
            for job_id in jobs_to_remove:
                pending_jobs.remove(job_id)

            # MISE À JOUR RÉELLE DE LA PROGRESSION si il y a du nouveau
            if jobs_to_remove and completed_count > qty_done:
                _update_task_progress(task_id, completed_count)
                print(f"📊 [TRACKING] Base mise à jour: {completed_count}/{qty_tot} étiquettes terminées")

            if completed_count >= qty_tot:
                print(f"✅ [TRACKING] Toutes les {qty_tot} étiquettes confirmées terminées!")
                break

        except Exception as e:
            print(f"⚠️ [TRACKING] Erreur lors de la vérification: {e}")

        time.sleep(1)  # Vérification chaque seconde

    if completed_count >= qty_tot:
        print(f"🏁 [TRACKING] Job {job_id} (tâche {task_id}) terminé avec succès")
        return True
    elif completed_count >= qty_tot // 2:
        # Au moins la moitié terminée = considérer comme succès partiel
        print(f"⚠️ [TRACKING] Succès partiel: {completed_count}/{qty_tot} étiquettes terminées")
        return True
    else:
        print(f"❌ [TRACKING] Échec: seulement {completed_count}/{qty_tot} terminés dans le timeout")
        return False

def _process_series_task(task_id: int, cmd_id: int, config: dict, qty_tot: int):
    """Traite une tâche SERIES : envoie les étiquettes à CUPS pour impression."""
    print("⚠️ [SERIES] Fonction series pas encore implémentée avec le tracking CUPS")
    print("Utilisant la méthode simple pour l'instant...")

    if not print_batch_cups:
        raise ImportError("Service CUPS non disponible")

    images = config.get('images', [])
    if not images:
        raise ValueError("Config SERIES manquante: images (liste de chemins)")

    print(f"⚙️ [CONFIG-SERIES] {len(images)} images à traiter")

    try:
        # PRÉ-TRAITEMENT DE TOUTES LES IMAGES
        processed_image_paths = []
        for img_path in images:
            processed_path = _preprocess_image(img_path, task_id, config)
            processed_image_paths.append(processed_path)

        print(f"🔧 [WORKER] {len(processed_image_paths)} images pré-traitées pour tâche série {task_id}")

        # ENVOI À CUPS - toutes les images d'un coup
        success = print_batch_cups(processed_image_paths, f"TASK_{task_id}")
        if success:
            # Mise à jour de la progression - tout envoyé d'un coup
            _update_task_progress(task_id, qty_tot)
            print(f"✅ [CUPS] {qty_tot} étiquettes de série envoyées au spooler CUPS pour tâche {task_id}")
        else:
            raise Exception("Échec d'envoi à CUPS")

    except Exception as e:
        print(f"❌ Erreur dans _process_series_task (tâche {task_id}): {e}")
        _update_task_status(task_id, 'ERROR')
        _update_command_status(cmd_id, 'ERROR')
        import traceback
        traceback.print_exc()
        raise

# Exemple d'utilisation (dans main.py plus tard) :
# run_worker()
# # Puis lancer FastAPI et l'interface web
