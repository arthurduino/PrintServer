import sqlite3
import json
import time
import threading
import os
from typing import Optional
from printer_driver import PrinterDriver
from database import DB_FILE, parse_config_json

# Import de brother_ql pour la rasterisation (nécessite installation de brother_ql)
try:
    import brother_ql
    from brother_ql.raster import BrotherQLRaster
    from brother_ql.backends.helpers import send
    from brother_ql.conversion import convert
    print("brother_ql importé avec succès")
    # Note: send n'est pas utilisé car on utilise notre propre driver bas niveau
except ImportError as e:
    print(f"Erreur: brother_ql n'est pas installé: {e}")
    # Fallback ou simulation pour tests
    brother_ql = None

# Modèle QL-700 comme string (many examples use this)
MODEL = 'QL-700'
print(f"ModèleBrother QL-700: {MODEL}")

# État global du worker
paused = True  # True = actif, False = mis en pause

def run_worker(printer: PrinterDriver):
    """Lance le worker en daemon thread."""
    thread = threading.Thread(target=_worker_loop, args=(printer,), daemon=True)
    thread.start()
    print("Worker démarré en thread daemon.")

def _worker_loop(printer: PrinterDriver):
    """Boucle principale du worker pour traiter les tâches."""
    while True:
        # Vérifier si le worker est en pause - plus fréquemment pour une réponse instantanée
        if not paused:
            time.sleep(0.01)  # Sleep très court quand en pause pour réponse instantanée
            continue

        task_data = _get_next_pending_task()
        if not task_data:
            time.sleep(0.01)  # Délai très court pour une meilleure réactivité du statut
            continue

        task_id, cmd_id, type_t, config_json, qty_tot, qty_done = task_data
        config = parse_config_json(config_json)

        # Vérifier si l'imprimante est en phase de refroidissement
        printer_status = printer.get_status()
        if printer_status.get('is_cooling', False):
            _set_task_cooling_wait(task_id)
            print(f"🧊 Imprimante en refroidissement - tâche {task_id} mise en attente")
            time.sleep(0.1)
            continue

        # Vérifier si cette tâche attend encore la fin du refroidissement
        if _is_task_waiting_cooling(task_id):
            # Vérifier si l'imprimante n'est plus en refroidissement
            printer_status = printer.get_status()
            if not printer_status.get('is_cooling', False):
                # Imprimante plus en refroidissement - ajouter un petit buffering de sécurité
                _set_task_buffering_time(task_id, 3)  # 3 secondes de buffering
                print(f"🧊 Imprimante sortie de refroidissement - tâche {task_id} en buffering 3s")
            else:
                print(f"🧊 Tâche {task_id} en attente - imprimante encore en refroidissement")
                time.sleep(0.1)
                continue

            remaining_buffering = _get_task_buffering_seconds(task_id)
            if remaining_buffering > 0:
                print(f"🧊 Tâche {task_id} en buffering post-refroidissement ({remaining_buffering:.1f}s)")
                time.sleep(0.1)
                continue
            else:
                _clear_task_cooling_wait(task_id)
                print(f"✅ Tâche {task_id} prête à reprendre après refroidissement")

        _set_processing(task_id, cmd_id)

        try:
            if type_t == 'BATCH':
                _process_batch_task(printer, task_id, cmd_id, config, qty_tot)
            elif type_t == 'SERIES':
                _process_series_task(printer, task_id, cmd_id, config, qty_tot)
            else:
                raise ValueError(f"Type de tâche inconnu: {type_t}")

            # Après succès, marque la tâche comme DONE
            _update_task_status(task_id, 'DONE')
            _check_command_completion(cmd_id)

        except Exception as e:
            print(f"Erreur lors du traitement de la tâche {task_id}: {e}")
            # Si c'est une erreur temporaire (timeout, USB), on peut essayer de paused ou retry, mais pour simplicité, ERROR
            _update_task_status(task_id, 'ERROR')
            _update_command_status(cmd_id, 'ERROR')
            # Log détaillé pour debug
            if 'Timeout' in str(e) or 'Operation timed out' in str(e):
                print(f"Tâche {task_id} échouée à cause d'un timeout - vérifier connexion USB ou imprimerie")
            elif 'Papier vide' in str(e):
                print(f"Tâche {task_id} échouée : papier vide - recharger le rouleau d'étiquettes")
            elif 'Erreur USB' in str(e):
                print(f"Tâche {task_id} échouée : problème USB - vérifier câble et permissions")
            # Continuer immédiatement au lieu de dormir (auto-recovery gérera la reconnexion)

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

def _update_task_progress(task_id: int, qty_done: int):
    """Incrémente la quantité faite."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE taches SET quantite_faite = ? WHERE id = ?", (qty_done, task_id))
    conn.commit()
    conn.close()

def _set_task_cooling_until(task_id: int, cooling_until_timestamp: float):
    """Définit le timestamp de fin de refroidissement pour une tâche."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE taches SET cooling_until = ? WHERE id = ?", (cooling_until_timestamp, task_id))
    conn.commit()
    conn.close()

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

def _process_batch_task(printer: PrinterDriver, task_id: int, cmd_id: int, config: dict, qty_tot: int):
    """Traite une tâche BATCH : imprime multiples copies de la même étiquette."""
    if not brother_ql:
        raise ImportError("brother_ql non disponible")

    image_path = config.get('image_path')
    if not image_path:
        raise ValueError("Config BATCH manquante: image_path")

    print(f"📁 [WORKER] Image path reçu: {image_path}")
    print(f"📁 [WORKER] Fichier existe: {os.path.exists(image_path)}")

    # Configuration des options par défaut, ajustée pour gros transferts
    options = {
        'cut': config.get('cut', True),
        'copies': 1,  # On gère les copies dans la boucle
        'model': MODEL,
        'label': str(config.get('label_type', '62')),
        'rotate': '90',  # Toujours appliquer une rotation de 90° par rapport au fichier original
        'print_script': None,
        # Options spéciales pour gros fichiers sombres
        'compress': True,  # Activer la compression
        'red': False,      # Désactiver traitement rouge pour simplifier
        '600dpi': False,   # Utiliser 300dpi au lieu de 600dpi si possible
    }

    # Rasterise une seule fois
    qlr = BrotherQLRaster(options['model'])
    form = convert(qlr, [image_path], label=options['label'], rotate=options['rotate'], cut=options['cut'])

    # Gestion des différentes versions de brother_ql API
    if hasattr(form, 'render'):
        binary_data = form.render(options['print_script'])
    else:
        binary_data = form

    qty_done = 0
    for _ in range(qty_tot):
        # Vérifier si l'imprimante est entrée en mode refroidissement entre les impressions
        printer_status = printer.get_status()
        if printer_status.get('is_cooling', False):
            _set_task_cooling_wait(task_id)
            print(f"🧊 Imprimante entrée en refroidissement pendant tâche {task_id} - mise en attente dynamique")
            # Ne pas marquer la tâche en erreur, juste la mettre en pause
            return

        print(f"Impression #{qty_done + 1}/{qty_tot} avec brother_ql...")

        try:
            # Utiliser seulement la méthode brother_ql.send() - pas de méthode manuelle
            send(
                instructions=form,  # Données raster déjà préparées
                printer_identifier="usb://04f9:2042",  # VID:PID de la QL-700
                blocking=True  # Attendre la fin de l'impression
            )
            print(f"Impression #{qty_done + 1} terminée avec succès via brother_ql")
            qty_done += 1
            _update_task_progress(task_id, qty_done)

        except Exception as e:
            error_msg = str(e)
            print(f"Échec de l'impression #{qty_done + 1}: {error_msg}")

            # Gestion spéciale pour les erreurs de ressource busy (imprimante occupée/verrouillée)
            if "Resource busy" in error_msg or "[Errno 16]" in error_msg:
                print(f"🔒 Linux a volé l'imprimante pour {task_id} ! Récupération en cours...")
                # Tenter une récupération gentle (pas de reset destructif)
                if printer.recuperer_connexion():
                    print("✅ Récupération connexion réussie, nouvelle tentative d'impression...")
                    # Réessaie immédiatement sans délai
                    try:
                        send(
                            instructions=form,
                            printer_identifier="usb://04f9:2042",
                            blocking=True
                        )
                        print(f"Impression #{qty_done + 1} réussie après récupération gentle")
                        qty_done += 1
                        _update_task_progress(task_id, qty_done)
                    except Exception as retry_e:
                        print(f"💥 Échec même après récupération gentle: {retry_e}")
                        _update_task_status(task_id, 'ERROR')
                        _update_command_status(cmd_id, 'ERROR')
                        return
                else:
                    print("⚠️ Récupération échouée, nouvel essai avec attente classique...")
                    # Attente un peu plus courte maintenant que nous avons la bonne logique
                    time.sleep(3)
                    try:
                        send(
                            instructions=form,
                            printer_identifier="usb://04f9:2042",
                            blocking=True
                        )
                        print(f"Impression #{qty_done + 1} réussie au deuxième essai")
                        qty_done += 1
                        _update_task_progress(task_id, qty_done)
                    except Exception as retry_e:
                        print(f"💥 Échec définitif même après attente: {retry_e}")
                        _update_task_status(task_id, 'ERROR')
                        _update_command_status(cmd_id, 'ERROR')
                        return
            else:
                # Autre type d'erreur - marquer comme erreur immédiatement
                print(f"Tâche {task_id} marquée en erreur - passage à la suivante")
                _update_task_status(task_id, 'ERROR')
                _update_command_status(cmd_id, 'ERROR')
                return

        # Délai entre impressions pour éviter surcharge
        if qty_done < qty_tot:
            time.sleep(0.2)

def _process_series_task(printer: PrinterDriver, task_id: int, cmd_id: int, config: dict, qty_tot: int):
    """Traite une tâche SERIES : imprime une série d'images différentes."""
    if not brother_ql:
        raise ImportError("brother_ql non disponible")

    images = config.get('images', [])
    if not images:
        raise ValueError("Config SERIES manquante: images (liste de chemins)")

    if len(images) != qty_tot:
        raise ValueError(f"Nombre d'images ({len(images)}) ne correspond pas à quantité totale ({qty_tot})")

    qty_done = 0
    for img_path in images:
        # Vérifier si l'imprimante est entrée en mode refroidissement entre les impressions
        printer_status = printer.get_status()
        if printer_status.get('is_cooling', False):
            _set_task_cooling_wait(task_id)
            print(f"🧊 Imprimante entrée en refroidissement pendant série {task_id} - mise en attente dynamique")
            # Ne pas marquer la tâche en erreur, juste la mettre en pause
            return

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
            print(f"Impression série #{qty_done + 1} terminée avec succès")
            qty_done += 1
            _update_task_progress(task_id, qty_done)

        except Exception as e:
            error_msg = str(e)
            print(f"Échec de l'impression série #{qty_done + 1}: {error_msg}")

            # Gestion spéciale pour les erreurs de ressource busy
            if "Resource busy" in error_msg or "[Errno 16]" in error_msg:
                print(f"Imprimante occupée pour série {task_id} - récupération connexion...")
                if printer.recuperer_connexion():
                    print("Récupération connexion réussie pour série, nouvelle tentative...")
                    time.sleep(1)  # Petite pause de sécurité
                    try:
                        send(
                            instructions=form,
                            printer_identifier="usb://04f9:2042",
                            blocking=True
                        )
                        print(f"Impression série #{qty_done + 1} réussie après récupération")
                        qty_done += 1
                        _update_task_progress(task_id, qty_done)
                    except Exception as retry_e:
                        print(f"Échec de la série même après récupération: {retry_e}")
                        _update_task_status(task_id, 'ERROR')
                        _update_command_status(cmd_id, 'ERROR')
                        return
                else:
                    print("Récupération échouée pour série, nouvel essai avec attente classique...")
                    time.sleep(10)
                    try:
                        send(
                            instructions=form,
                            printer_identifier="usb://04f9:2042",
                            blocking=True
                        )
                        print(f"Impression série #{qty_done + 1} réussie au deuxième essai classique")
                        qty_done += 1
                        _update_task_progress(task_id, qty_done)
                    except Exception as retry_e:
                        print(f"Échec définitif de la série même après attente classique: {retry_e}")
                        _update_task_status(task_id, 'ERROR')
                        _update_command_status(cmd_id, 'ERROR')
                        return
            else:
                # Autre type d'erreur
                print(f"Tâche série {task_id} marquée en erreur - passage à la suivante")
                _update_task_status(task_id, 'ERROR')
                _update_command_status(cmd_id, 'ERROR')
                return

        # Délai entre impressions pour éviter surcharge
        if qty_done < qty_tot:
            time.sleep(0.2)

# Exemple d'utilisation (dans main.py plus tard) :
# printer = PrinterDriver()
# run_worker(printer)
# # Puis lancer FastAPI et l'interface web
