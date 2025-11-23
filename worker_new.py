import sqlite3
import json
import time
import threading
import os
from typing import Optional
from database import DB_FILE, parse_config_json

# Import de brother_ql pour la rasterisation (nécessite installation de brother_ql)
try:
    import brother_ql
    from brother_ql.raster import BrotherQLRaster
    from brother_ql.backends.helpers import send
    from brother_ql.conversion import convert
    print("brother_ql importé avec succès")
except ImportError as e:
    print(f"Erreur: brother_ql n'est pas installé: {e}")
    brother_ql = None

# Import de la nouvelle architecture asynchrone
try:
    from printer_driver import (
        start_async_printer,
        stop_async_printer,
        add_print_job,
        printer_state
    )
    print("✅ Architecture asynchrone importée")
except ImportError as e:
    print(f"❌ Erreur importation architecture asynchrone: {e}")
    start_async_printer = None
    stop_async_printer = None
    add_print_job = None
    printer_state = None

# Import de la fonction de détection d'orientation
try:
    from print_service import detect_image_orientation
    print("✅ Fonction de détection d'orientation importée")
except ImportError as e:
    print(f"⚠️ Fonction de détection d'orientation non disponible: {e}")
    detect_image_orientation = None

# Modèle QL-700 comme string
MODEL = 'QL-700'
print(f"Modèle Brother QL-700: {MODEL}")

# État global du worker
paused = True  # True = actif, False = mis en pause

def run_worker():
    """Lance le worker en daemon thread et démarre l'architecture asynchrone."""
    # RÉCUPÉRATION APRÈS REDÉMARRAGE : remettre les tâches IN_PROGRESS orphelines en PENDING
    _recover_orphaned_tasks_on_startup()

    # ✅ DÉMARRER L'ARCHITECTURE ASYNCHRONE (remplace polling direct)
    if start_async_printer:
        start_async_printer()
        print("✅ Architecture asynchrone Brother QL-700 démarrée")
    else:
        print("❌ Impossible de démarrer l'architecture asynchrone")

    thread = threading.Thread(target=_worker_loop, daemon=True)
    thread.start()
    print("Worker démarré en thread daemon avec architecture asynchrone - récupération d'état activée.")

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
    """Traite une tâche BATCH : ajoute les étiquettes à imprimer dans la file asynchrone."""
    if not brother_ql or not add_print_job:
        raise ImportError("brother_ql ou architecture asynchrone non disponible")

    image_path = config.get('image_path')
    if not image_path:
        raise ValueError("Config BATCH manquante: image_path")

    print(f"📁 [WORKER] Image path reçu: {image_path}")
    print(f"📁 [WORKER] Fichier existe: {os.path.exists(image_path)}")

    # Récupération des paramètres d'optimisation (valeurs par défaut sécurisées)
    label_type = str(config.get('label_type', '62'))
    dpi = config.get('dpi', 300)
    print(f"⚙️ [CONFIG] dpi={dpi}, label='{label_type}'")

    # 🔥 RÉCUPÉRATION DE LA PROGRESSION SAUVEGARDÉE 🔥
    qty_done = _get_task_progress(task_id)
    print(f"🔥 [RECOVERY] Reprise tâche {task_id} depuis impression #{qty_done + 1}")

    try:
        # 1. PRÉ-TRAITEMENT DE L'IMAGE (Redimensionnement automatique)
        processed_image_path = _preprocess_image(image_path, task_id, config)
        print(f"🔧 [WORKER] Image pré-traitée: {processed_image_path}")

        # 2. CONFIGURATION DE LA ROTATION (priorité au config explicite)
        # Vérifier d'abord si une rotation explicite est demandée dans la config
        config_rotation = config.get('rotate')
        if config_rotation and config_rotation != 0:
            rotation = str(config_rotation)  # Respect des paramètres explicites
            print(f"⚙️ Rotation explicite {config_rotation}° depuis la config")
        else:
            # Sinon, appliquer la logique automatique basée sur l'orientation
            rotation = '0'  # Pas de rotation par défaut
            if detect_image_orientation:
                orientation = detect_image_orientation(processed_image_path)
                print(f"📐 Image {os.path.basename(processed_image_path)}: {orientation}")
                if orientation == "portrait":
                    rotation = '90'  # Rotation uniquement pour les images portrait
                    print("🔄 Rotation automatique 90° appliquée pour image portrait")
                else:
                    rotation = '0'  # Pas de rotation pour les images paysage
                    print("📐 Image paysage - pas de rotation automatique")
            else:
                print("⚠️ Fonction de détection d'orientation non disponible - aucune rotation appliquée")

        # 3. CONVERSION OPTIMISÉE AVEC DITHER FORCÉ
        qlr = BrotherQLRaster(MODEL)
        instructions = convert(
            qlr, [processed_image_path], label_type,
            cut=True, dither=True, compress=False,
            rotate=rotation, red=False, dpi_600=(dpi==600)
        )

        # 3. AJOUT DES TÂCHES D'IMPRESSION À LA FILE ASYNCHRONE
        # (l'architecture asynchrone gère automatiquement les pauses de refroidissement)
        total_jobs_added = 0

        for i in range(qty_done, qty_tot):
            label_num = i + 1
            print(f"📋 [ASYNC] Ajout étiquette #{label_num}/{qty_tot} à la file (tâche {task_id})")

            # Ajouter à la file d'attente asynchrone
            add_print_job(instructions, label_num, task_id)
            total_jobs_added += 1

            # Mise à jour immédiate de la progression en base
            _update_task_progress(task_id, label_num)

        print(f"✅ [ASYNC] {total_jobs_added} étiquettes ajoutées à la file pour tâche {task_id}")

    except Exception as e:
        print(f"❌ Erreur dans _process_batch_task (tâche {task_id}): {e}")
        _update_task_status(task_id, 'ERROR')
        _update_command_status(cmd_id, 'ERROR')
        import traceback
        traceback.print_exc()
        raise

def _process_series_task(task_id: int, cmd_id: int, config: dict, qty_tot: int):
    """Traite une tâche SERIES : ajoute les étiquettes à imprimer dans la file asynchrone."""
    if not brother_ql or not add_print_job:
        raise ImportError("brother_ql ou architecture asynchrone non disponible")

    images = config.get('images', [])
    if not images:
        raise ValueError("Config SERIES manquante: images (liste de chemins)")

    # Récupération des paramètres d'optimisation (valeurs par défaut sécurisées)
    label_type = str(config.get('label_type', '62'))
    dpi = config.get('dpi', 300)
    cut = config.get('cut', True)
    print(f"⚙️ [CONFIG-SERIES] dpi={dpi}, label='{label_type}'")

    # 🔥 RÉCUPÉRATION DE LA PROGRESSION SAUVEGARDÉE 🔥
    qty_done = _get_task_progress(task_id)
    print(f"🔥 [RECOVERY] Reprise tâche SÉRIE {task_id} depuis image #{qty_done + 1}")

    # On ne traite que les images restantes
    images_to_print = images[qty_done:]

    try:
        total_jobs_added = 0

        for i, img_path in enumerate(images_to_print):
            current_label_num = qty_done + i + 1
            print(f"📋 [ASYNC] Traitement image #{current_label_num}/{qty_tot}: {os.path.basename(img_path)}")

            # 1. Pré-traitement de chaque image
            processed_image_path = _preprocess_image(img_path, task_id, config)

            # 2. CONFIGURATION DE LA ROTATION (priorité au config explicite)
            # Vérifier d'abord si une rotation explicite est demandée dans la config
            config_rotation = config.get('rotate')
            if config_rotation and config_rotation != 0:
                rotation = str(config_rotation)  # Respect des paramètres explicites
                print(f"⚙️ Rotation explicite {config_rotation}° depuis la config")
            else:
                # Sinon, appliquer la logique automatique basée sur l'orientation
                rotation = '0'  # Pas de rotation par défaut
                if detect_image_orientation:
                    orientation = detect_image_orientation(processed_image_path)
                    print(f"📐 Image {os.path.basename(processed_image_path)}: {orientation}")
                    if orientation == "portrait":
                        rotation = '90'  # Rotation uniquement pour les images portrait
                        print("🔄 Rotation automatique 90° appliquée pour image portrait")
                    else:
                        rotation = '0'  # Pas de rotation pour les images paysage
                        print("📐 Image paysage - pas de rotation automatique")
                else:
                    print("⚠️ Fonction de détection d'orientation non disponible - aucune rotation appliquée")

            # 3. Conversion de chaque image
            qlr = BrotherQLRaster(MODEL)
            instructions = convert(
                qlr, [processed_image_path], label_type,
                cut=cut, dither=True, compress=False,
                rotate=rotation, red=False, dpi_600=(dpi==600)
            )

            # 3. Ajouter à la file d'attente asynchrone
            add_print_job(instructions, current_label_num, task_id)
            total_jobs_added += 1

            # Mise à jour de la progression
            _update_task_progress(task_id, current_label_num)

        print(f"✅ [ASYNC] {total_jobs_added} images ajoutées à la file pour tâche série {task_id}")

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
