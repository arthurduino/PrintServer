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
    import usb.core
    import usb.util
    print("brother_ql et pyusb importés avec succès")
    # Note: send n'est PLUS utilisé - connexion USB directe pour le polling
except ImportError as e:
    print(f"Erreur: brother_ql ou pyusb n'est pas installé: {e}")
    # Fallback ou simulation pour tests
    brother_ql = None
    usb = None

# Modèle QL-700 comme string (many examples use this)
MODEL = 'QL-700'
CMD_STATUS = b'\x1B\x69\x53'  # Commande interrogation statut
print(f"Modèle Brother QL-700: {MODEL}")

# État global du worker
paused = True  # True = actif, False = mis en pause

def run_worker():
    """Lance le worker en daemon thread."""
    # RÉCUPÉRATION APRÈS REDÉMARRAGE : remettre les tâches IN_PROGRESS orphelines en PENDING
    _recover_orphaned_tasks_on_startup()

    # Note: Brother_QL ne supporte pas la coupe manuelle au démarrage

    thread = threading.Thread(target=_worker_loop, daemon=True)
    thread.start()
    print("Worker démarré en thread daemon avec Brother_QL - récupération d'état activée.")

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

        # Note: Brother_QL ne supporte pas le monitoring avancé du statut (cooling, paper_empty, etc.)
        # On utilise une approche simplifiée avec délai fixe entre impressions

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
            # Logs pour debug
            if 'Timeout' in str(e) or 'Operation timed out' in str(e):
                print(f"Tâche {task_id} échouée à cause d'un timeout - vérifier connexion USB")
            elif 'Resource busy' in str(e) or '[Errno 16]' in str(e):
                print(f"Tâche {task_id} échouée : ressource USB occupée")
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
            # Remettre la commande en PROCESSING si elle était DONE (cas où le process crash après dernière tâche)
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

def _set_task_cooling_wait(task_id: int):
    """Marque une tâche comme en attente de fin de refroidissement de l'imprimante."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Utiliser le champ cooling_until comme flag négatif pour indiquer attente de cooling
    cursor.execute("UPDATE taches SET cooling_until = -1 WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

def _is_task_waiting_cooling(task_id: int) -> bool:
    """Vérifie si une tâche attend la fin du refroidissement."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT cooling_until FROM taches WHERE id = ?", (task_id,))
    result = cursor.fetchone()
    conn.close()
    return result and result[0] == -1

def _set_task_buffering_time(task_id: int, buffering_seconds: int = 5):
    """Définit un temps de buffering après fin de refroidissement."""
    buffering_until = time.time() + buffering_seconds
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE taches SET cooling_until = ? WHERE id = ?", (buffering_until, task_id))
    conn.commit()
    conn.close()

def _get_task_buffering_seconds(task_id: int) -> float:
    """Retourne le nombre de secondes restantes pour le buffering post-refroidissement."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT cooling_until FROM taches WHERE id = ?", (task_id,))
    result = cursor.fetchone()
    conn.close()
    if result and result[0] and result[0] > 0:
        remaining = result[0] - time.time()
        return max(0, remaining)
    return 0

def _clear_task_cooling_wait(task_id: int):
    """Efface tous les flags de refroidissement pour une tâche."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE taches SET cooling_until = 0 WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()

def _get_task_cooling_until(task_id: int) -> Optional[float]:
    """Récupère le timestamp de fin de refroidissement pour une tâche."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT cooling_until FROM taches WHERE id = ?", (task_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result and result[0] and result[0] > 0 else None

def _preprocess_image(image_path: str, task_id: int) -> str:
    """Pré-traite l'image : redimensionnement automatique pour compatibilité Brother QL-700."""
    try:
        from PIL import Image
        print(f"🔧 [PREPROCESS] Analyse image: {image_path}")

        # Ouvrir l'image pour analyse
        with Image.open(image_path) as img:
            original_width, original_height = img.size
            print(f"🔧 [PREPROCESS] Dimensions originales: {original_width}x{original_height}")

            # Dimensions idéales pour Brother QL-700 (62mm label)
            target_width = 696  # ~62mm à 300dpi
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
    """Traite une tâche BATCH : imprime multiples copies de la même étiquette avec contrôle de flux strict."""
    if not brother_ql or not usb:
        raise ImportError("brother_ql ou pyusb non disponible")

    image_path = config.get('image_path')
    if not image_path:
        raise ValueError("Config BATCH manquante: image_path")

    print(f"📁 [WORKER] Image path reçu: {image_path}")
    print(f"📁 [WORKER] Fichier existe: {os.path.exists(image_path)}")

    # 🔥 RÉCUPÉRATION DE LA PROGRESSION SAUVEGARDÉE 🔥
    qty_done = _get_task_progress(task_id)
    print(f"🔥 [RECOVERY] Reprise tâche {task_id} depuis impression #{qty_done + 1}")

    try:
        # 1. PRÉ-TRAITEMENT DE L'IMAGE (Redimensionnement automatique)
        processed_image_path = _preprocess_image(image_path, task_id)
        print(f"🔧 [WORKER] Image pré-traitée: {processed_image_path}")

        # 2. CONVERSION OPTIMISÉE AVEC DITHER FORCÉ (compression désactivée pour compatibilité Brother QL-700)
        qlr = BrotherQLRaster(MODEL)
        instructions = convert(qlr, [processed_image_path], '62', cut=True, dither=True, compress=False, rotate='90')

        # 2. CONNEXION PERSISTANTE - Ouverte UNE FOIS au début
        dev = usb.core.find(idVendor=0x04f9, idProduct=0x2042)
        if not dev:
            raise Exception("Imprimante Brother QL-700 introuvable - vérifier connexion USB")

        # Setup USB standard pour Brother QL-700
        dev.set_configuration()
        usb.util.claim_interface(dev, 0)

        # Récupérer les endpoints
        cfg = dev.get_active_configuration()
        intf = cfg[(0,0)]
        ep_out = usb.util.find_descriptor(intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT)
        ep_in = usb.util.find_descriptor(intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN)

        if not ep_out or not ep_in:
            raise Exception("Endpoints USB introuvables pour Brother QL-700")

        print(f"🔌 [WORKER] Connexion USB établie avec Brother QL-700 (VID:PID 04f9:2042)")

        # 3. BOUCLE D'IMPRESSION AVEC POLLING DE SÉCURITÉ
        for i in range(qty_done, qty_tot):
            start_time = time.time()  # Timer pour mesurer durée totale
            print(f"[{time.strftime('%H:%M:%S')}] 🖨️ Début impression #{i+1}/{qty_tot} (tâche {task_id})")

            # A. ENVOI DES DONNÉES AVEC TIMEOUT LARGE (10s)
            print(f"[{time.strftime('%H:%M:%S')}] 📤 Envoi données USB étiquette #{i+1} ({len(instructions)} octets)")
            try:
                dev.write(ep_out, instructions, timeout=10000)
                print(f"[{time.strftime('%H:%M:%S')}] ✅ Données USB envoyées avec succès #{i+1}")
            except usb.core.USBError as usb_e:
                error_str = str(usb_e)
                print(f"[{time.strftime('%H:%M:%S')}] ❌ Erreur USB envoi #{i+1}: {error_str}")
                if "Resource busy" in error_str or "16" in error_str:  # [Errno 16]
                    print(f"🔒 Ressource USB occupée après {i} impressions - nouvel essai après délai...")
                    time.sleep(2.0)
                    try:
                        dev.write(ep_out, instructions, timeout=10000)
                        print(f"✅ Étiquette #{i+1} réussie au deuxième essai")
                    except Exception as retry_e:
                        print(f"💥 Échec définitif de l'étiquette #{i+1} au retry: {retry_e}")
                        _update_task_status(task_id, 'ERROR')
                        _update_command_status(cmd_id, 'ERROR')
                        return
                else:
                    raise usb_e

            # B. PAUSE TECHNIQUE INITIALE (laisser le buffer se remplir)
            print(f"[{time.strftime('%H:%M:%S')}] ⏱️ Pause technique 0.5s étiquette #{i+1}")
            time.sleep(0.5)
            print(f"[{time.strftime('%H:%M:%S')}] 📋 Début polling statut étiquette #{i+1}")

            # C. POLLING DE SÉCURITÉ (CONTRÔLE DE FLUX STRICT)
            polling_attempts = 0
            max_polling_attempts = 60  # Maximum 60 tentatives (30-45 secondes max selon le cas)

            while polling_attempts < max_polling_attempts:
                try:
                    # Envoyer commande statut
                    dev.write(ep_out, CMD_STATUS, timeout=1000)

                    # Lire 32 octets de réponse statut
                    res = dev.read(ep_in, 32, timeout=1000)

                    # Analyse des 3 drapeaux critiques selon protocole Brother
                    is_busy = (res[18] & 0x01) != 0      # True si BUSY (bit 0 du byte 18 à 1)
                    is_reception_phase = res[19] == 0x00 # True si PHASE RECEPTION (byte 19 = 0x00)
                    is_cooling = (res[9] & 0x10) != 0    # True si REFROIDISSEMENT (bit 4 du byte 9 à 1)

                    # CONDITION DE SORTIE = Prête SI ET SEULEMENT SI:
                    # A. PAS BUSY: (res[18] & 0x01) == 0
                    # B. PHASE RECEPTION: res[19] == 0x00
                    # C. PAS SURCHAUFFE: (res[9] & 0x10) == 0
                    printer_ready = (not is_busy) and is_reception_phase and (not is_cooling)

                    if printer_ready:
                        # 🎯 CONDITION DE SORTIE ATTEINTE
                        elapsed = time.time() - start_time
                        print(f"[{time.strftime('%H:%M:%S')}] ✅ Étiquette #{i+1} Terminée - Imprimante prête (Idle + Reception + Froide) - Durée: {elapsed:.1f}s")
                        break  # Sortie de boucle polling - voie libre pour suivante
                    elif is_cooling:
                        print(f"❄️ Mode Refroidissement actif - Attente 1.0s avant vérification...")
                        time.sleep(1.0)
                        polling_attempts += 1
                    else:
                        print(f"⏳ Imprimante occupée (Busy:{is_busy}, Phase:{hex(res[19])}) - Attente 0.5s...")
                        time.sleep(0.5)
                        polling_attempts += 1

                except usb.core.USBError as poll_error:
                    polling_attempts += 1
                    error_str = str(poll_error)
                    if "timeout" in error_str.lower():
                        print(f"[{time.strftime('%H:%M:%S')}] ⚠️ Timeout USB lors de polling #{polling_attempts}/{max_polling_attempts} - Retry après 1.0s...")
                        time.sleep(1.0)
                    else:
                        print(f"[{time.strftime('%H:%M:%S')}] ❌ Erreur USB critique lors de polling #{polling_attempts}: {error_str}")
                        raise poll_error  # Erreur critique, sortir immédiatement

            else:
                # Si on dépasse le nombre maximum de tentatives
                raise Exception(f"💥 Polling échoué après {max_polling_attempts} tentatives - Imprimante bloquée en état inconnu (Busy:{is_busy if 'is_busy' in locals() else '?'} Phase:{hex(res[19]) if 'res' in locals() else '?'} Cooling:{is_cooling if 'is_cooling' in locals() else '?'})")

            # D. MISE À JOUR BDD APRÈS CHAQUE ÉTIQUETTE
            print(f"[{time.strftime('%H:%M:%S')}] 💾 Mise à jour BDD: {qty_done+1}/{qty_tot} impressions terminées")
            qty_done += 1
            _update_task_progress(task_id, qty_done)

    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] ❌ Erreur CRITIQUE dans _process_batch_task (tâche {task_id}): {e}")
        _update_task_status(task_id, 'ERROR')
        _update_command_status(cmd_id, 'ERROR')
        import traceback
        print(f"[{time.strftime('%H:%M:%S')}] 🔍 TRACEBACK COMPLET:")
        traceback.print_exc()
        raise  # Re-lançer pour trace complète
    finally:
        # NETTOYAGE CONNEXION PERSISTANTE
        if 'dev' in locals():
            usb.util.dispose_resources(dev)
        print(f"[{time.strftime('%H:%M:%S')}] 🔌 Connexion USB fermée pour tâche {task_id}")


def _process_series_task(task_id: int, cmd_id: int, config: dict, qty_tot: int):
    """Traite une tâche SERIES : imprime une série d'images différentes avec Brother_QL."""
    if not brother_ql:
        raise ImportError("brother_ql non disponible")

    images = config.get('images', [])
    if not images:
        raise ValueError("Config SERIES manquante: images (liste de chemins)")

    if len(images) != qty_tot:
        raise ValueError(f"Nombre d'images ({len(images)}) ne correspond pas à quantité totale ({qty_tot})")

    qty_done = 0
    for img_path in images:
        print(f"Impression série #{qty_done + 1}/{qty_tot} : {img_path}")

        # Configuration des options par défaut pour chaque image
        options = {
            'cut': config.get('cut', True),
            'model': MODEL,
            'label': config.get('label_type', '62'),
            'rotate': '90',  # Toujours appliquer une rotation de 90° par rapport au fichier original
            'print_script': None,
        }

        # Rasterise pour chaque image
        qlr = BrotherQLRaster(options['model'])
        form = convert(qlr, [img_path], label=options['label'], rotate=options['rotate'], cut=options['cut'])

        try:
            # Utiliser seulement la méthode brother_ql.send()
            send(
                instructions=form,
                printer_identifier="usb://04f9:2042",
                blocking=True
            )

            print(f"✅ Impression série #{qty_done + 1} terminée avec succès")
            qty_done += 1
            _update_task_progress(task_id, qty_done)

        except Exception as e:
            error_msg = str(e)
            print(f"Échec de l'impression série #{qty_done + 1}: {error_msg}")

            # Gestion simplifiée des erreurs (pas de récupération de connexion avancée)
            if "Resource busy" in error_msg or "[Errno 16]" in error_msg:
                print(f"🔒 Ressource USB occupée pour série {task_id} - nouvel essai après délai...")
                time.sleep(2)  # Attente simple
                try:
                    send(
                        instructions=form,
                        printer_identifier="usb://04f9:2042",
                        blocking=True
                    )
                    print(f"✅ Impression série #{qty_done + 1} réussie au deuxième essai")
                    qty_done += 1
                    _update_task_progress(task_id, qty_done)
                except Exception as retry_e:
                    print(f"💥 Échec définitif de la série: {retry_e}")
                    _update_task_status(task_id, 'ERROR')
                    _update_command_status(cmd_id, 'ERROR')
                    return
            else:
                # Autre type d'erreur - marquer en erreur
                print(f"Tâche série {task_id} marquée en erreur")
                _update_task_status(task_id, 'ERROR')
                _update_command_status(cmd_id, 'ERROR')
                return

        # Délai entre impressions pour éviter surcharge (court délai avec Brother_QL)
        if qty_done < qty_tot:
            time.sleep(0.1)

# Exemple d'utilisation (dans main.py plus tard) :
# run_worker()
# # Puis lancer FastAPI et l'interface web
