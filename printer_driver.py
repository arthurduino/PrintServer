import usb.core
import usb.util
import time
import threading
from typing import Dict, Optional
import queue

# Constantes pour l'imprimante Brother QL-700
VENDOR_ID = 0x04f9
PRODUCT_ID = 0x2042

# État partagé entre threads
class PrinterState:
    def __init__(self):
        self.cooling_active = False
        self.media_empty = False
        self.cover_open = False
        self.last_status = None
        self.error_message = None
        self.listener_running = False
        self.writer_running = False
        self.listener_listening = False  # Flag pour synchronisation
        self._lock = threading.Lock()

    def set_cooling(self, active: bool):
        with self._lock:
            old_state = self.cooling_active
            self.cooling_active = active
            current_time = time.strftime('%H:%M:%S')
            print(f"[{current_time}] 🔄 [STATE] Cooling changé: {old_state} → {active} ({'❄️ ACTIVÉ' if active else '🔥 DÉSACTIVÉ'})")

    def set_error(self, error_type: str, message: str):
        with self._lock:
            old_error = self.error_message
            self.error_message = f"{error_type}: {message}"
            current_time = time.strftime('%H:%M:%S')
            print(f"[{current_time}] ❌ [STATE] Erreur définie: {old_error} → {self.error_message}")

    def clear_error(self):
        with self._lock:
            old_error = self.error_message
            self.error_message = None
            current_time = time.strftime('%H:%M:%S')
            print(f"[{current_time}] ✅ [STATE] Erreur effacée: {old_error} → None")

    def get_state(self):
        with self._lock:
            return {
                'cooling_active': self.cooling_active,
                'media_empty': self.media_empty,
                'cover_open': self.cover_open,
                'error': self.error_message,
                'last_status': self.last_status
            }

# Instance globale de l'état
printer_state = PrinterState()

# Files pour la communication inter-threads
print_queue = queue.Queue()  # File pour les données à imprimer
write_queue = queue.Queue()  # File pour les tâches d'écriture

# Threads principaux
listener_thread = None
writer_thread = None

class USBListener(threading.Thread):
    """Thread d'écoute passive avec connexion persistante synchronisée."""

    def __init__(self, vendor_id=VENDOR_ID, product_id=PRODUCT_ID):
        super().__init__(daemon=True, name="USB-Listener")
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.dev = None
        self.ep_in = None
        self.running = True
        self.listening_active = False
        self.messages_processed = 0

    def run(self):
        """Boucle principale - ÉCOUTE PASSIVE seulement des vrais événements spontanés Brother."""
        print("👂 [LISTENER] Démarrage avec écoute passive (pas de polling)")

        # UNE SEULE requête initiale autorisée
        self._send_initial_status_request()

        # Attendre que l'imprimante envoie spontanément les vrais événements
        # (0x05 avec cooling codes dans byte_22)
        while self.running:
            try:
                # Essayer de lire un message spontané (timeout court)
                message = self._try_read_spontaneous_message()
                if message:
                    self.messages_processed += 1
                    # Log seulement les vrais événements (pas les 0x00 répétés)
                    if message[18] != 0x00:  # Ignorer les réponses aux requêtes
                        current_time = time.strftime('%H:%M:%S')
                        print(f"[{current_time}] 📨 [LISTENER] Événement spontané reçu: {message[18]:02X}")
                    self._process_status_message(message)

                # Petit délai pour éviter surcharge CPU
                time.sleep(0.01)

            except Exception as e:
                print(f"❌ [LISTENER] Erreur écoute passive: {e}")
                time.sleep(1)

        print(f"🛑 [LISTENER] Arrêté - {self.messages_processed} messages spontanés captés")

    def _try_read_spontaneous_message(self):
        """Essaie de lire un message spontané de l'imprimante avec timeout court."""
        dev = None
        try:
            dev = usb.core.find(idVendor=self.vendor_id, idProduct=self.product_id)
            if dev is None:
                return None

            # Détacher kernel driver temporairement
            try:
                if dev.is_kernel_driver_active(0):
                    dev.detach_kernel_driver(0)
            except (AttributeError, NotImplementedError):
                pass

            # Configuration temporaire
            dev.set_configuration()
            cfg = dev.get_active_configuration()
            intf = cfg[(0,0)]

            # Obtenir endpoint d'entrée seulement
            ep_in = usb.util.find_descriptor(
                intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
            )

            if ep_in:
                # Essayer de lire avec timeout TRES court (pas de commande envoyée)
                try:
                    response = ep_in.read(32, timeout=50)  # 50ms timeout
                    if len(response) == 32:
                        return response  # Retourner le message spontané
                except usb.core.USBError as e:
                    if "timeout" in str(e).lower():
                        return None  # Timeout normal, pas de message spontané
                    else:
                        raise  # Autre erreur USB

        except Exception:
            # En cas d'erreur, retourner None (pas de message)
            pass
        finally:
            if dev:
                usb.util.dispose_resources(dev)

        return None  # Aucun message spontané disponible

    def _check_printer_status(self):
        """Vérifie le statut de l'imprimante avec connexion temporaire (Brother standard)."""
        dev = None
        try:
            # Marquer comme en cours d'écoute
            printer_state.listener_listening = True

            dev = usb.core.find(idVendor=self.vendor_id, idProduct=self.product_id)
            if dev is None:
                return

            # Détacher kernel driver temporairement
            try:
                if dev.is_kernel_driver_active(0):
                    dev.detach_kernel_driver(0)
            except (AttributeError, NotImplementedError):
                pass

            # Configuration temporaire
            dev.set_configuration()
            cfg = dev.get_active_configuration()
            intf = cfg[(0,0)]

            # Obtenir endpoints
            ep_out = usb.util.find_descriptor(
                intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
            )
            ep_in = usb.util.find_descriptor(
                intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
            )

            if ep_out and ep_in:
                # Envoyer requête de statut Brother
                ep_out.write(b'\x1B\x69\x53', timeout=5000)  # ESC i S
                response = ep_in.read(32, timeout=5000)

                if len(response) == 32:
                    self._process_status_message(response)

        except Exception as e:
            print(f"⚠️ [LISTENER] Erreur vérification statut: {e}")
        finally:
            if dev:
                usb.util.dispose_resources(dev)
            # Libérer le flag d'écoute
            printer_state.listener_listening = False

    def _send_initial_status_request(self):
        """Envoie UNE SEULE requête de statut autorisée."""
        try:
            print("📡 [LISTENER] Envoi requête initiale de statut (Brother autorisée)")

            dev = usb.core.find(idVendor=self.vendor_id, idProduct=self.product_id)
            if dev is None:
                print("⚠️ [LISTENER] Imprimante non trouvée pour requête initiale")
                return

            try:
                if dev.is_kernel_driver_active(0):
                    dev.detach_kernel_driver(0)
            except (AttributeError, NotImplementedError):
                pass

            dev.set_configuration()
            cfg = dev.get_active_configuration()
            intf = cfg[(0,0)]

            ep_out = usb.util.find_descriptor(
                intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
            )
            ep_in = usb.util.find_descriptor(
                intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
            )

            if ep_out and ep_in:
                ep_out.write(b'\x1B\x69\x53', timeout=5000)  # ESC i S
                response = ep_in.read(32, timeout=5000)

                if len(response) == 32:
                    self._process_status_message(response)
                    print("✅ [LISTENER] Statut initial obtenu - prêt pour écoute passive")
                else:
                    print(f"⚠️ [LISTENER] Réponse initiale incomplète: {len(response)} octets")
            else:
                print("❌ [LISTENER] Endpoints non trouvés")

        except Exception as e:
            print(f"⚠️ [LISTENER] Impossible d'envoyer requête initiale: {e}")
        finally:
            if 'dev' in locals():
                usb.util.dispose_resources(dev)

    def _process_status_message(self, response):
        """Traite un message de statut selon protocole Brother."""
        try:
            status_type = response[18]  # Type de message
            notification_num = response[22] if len(response) > 22 else 0
            error_info_1 = response[8] if len(response) > 8 else 0
            error_info_2 = response[9] if len(response) > 9 else 0

            current_time = time.strftime('%H:%M:%S')

            # Erreurs bloquantes (0x02)
            if status_type == 0x02:
                error_msg = ""
                if error_info_1 & 0x02:  # Papier vide
                    error_msg = "Papier absent"
                    printer_state.set_error("MEDIA_ERROR", error_msg)
                elif error_info_1 & 0x04:  # Bourrage cutter
                    error_msg = "Bourrage cutter"
                    printer_state.set_error("CUTTER_JAM", error_msg)
                elif error_info_2 & 0x10:  # Couvercle ouvert
                    error_msg = "Couvercle ouvert"
                    printer_state.set_error("COVER_OPEN", error_msg)
                else:
                    error_msg = f"Erreur inconnue (E1:{error_info_1:02X}, E2:{error_info_2:02X})"
                    printer_state.set_error("UNKNOWN_ERROR", error_msg)
                print(f"[{current_time}] ❌ [LISTENER] Erreur détectée: {error_msg}")
                return

            # Notifications de refroidissement (0x05)
            elif status_type == 0x05:
                if notification_num == 0x03:  # Début cooling
                    printer_state.set_cooling(True)
                    print(f"[{current_time}] ❄️ [LISTENER] Refroidissement DÉBUT détecté")

                elif notification_num == 0x04:  # Fin cooling
                    printer_state.set_cooling(False)
                    printer_state.clear_error()
                    print(f"[{current_time}] 🔥 [LISTENER] Refroidissement FIN détecté - impression reprendra")
                else:
                    print(f"[{current_time}] ℹ️ [LISTENER] Notification {notification_num:02X}")

            # Autres messages
            elif status_type == 0x01:
                print(f"[{current_time}] ✅ [LISTENER] Impression terminée")
            elif status_type == 0x06:
                print(f"[{current_time}] 🔄 [LISTENER] Changement de phase")
            else:
                print(f"[{current_time}] 🔍 [LISTENER] Message inconnu: {status_type:02X}")

        except Exception as e:
            print(f"❌ [LISTENER] Erreur traitement message: {e}")

    def _cleanup_connection(self):
        """Nettoie la connexion persistante."""
        try:
            if self.dev:
                usb.util.dispose_resources(self.dev)
                self.dev = None
                self.listening_active = False
                printer_state.listener_listening = False
                print("🧹 [LISTENER] Connexion nettoyée")
        except Exception as e:
            print(f"⚠️ [LISTENER] Erreur nettoyage: {e}")

    def stop(self):
        """Arrête proprement l'écoute."""
        self.running = False
        self._cleanup_connection()

class USBWriter(threading.Thread):
    """Thread d'écriture pour envoi séquentiel avec synchronisation."""

    def __init__(self, vendor_id=VENDOR_ID, product_id=PRODUCT_ID):
        super().__init__(daemon=True, name="USB-Writer")
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.dev = None
        self.ep_out = None
        self.running = True
        self.initialized = False
        self.prints_sent = 0

    def run(self):
        """Boucle principale d'écriture avec synchronisation."""
        print("✍️ [WRITER] Démarrage avec synchronisation Listener")

        while self.running:
            try:
                # Vérifier connexion avant Writer
                if not self.initialized:
                    self._initialize_connection()

                # Attendre tâche
                if self.running:
                    self._process_print_queue()

                time.sleep(0.1)  # Petit délai

            except Exception as e:
                print(f"❌ [WRITER] Erreur critique: {e}")
                self.initialized = False
                time.sleep(2)

        print(f"🛑 [WRITER] Arrêté - {self.prints_sent} impressions envoyées")

    def _process_print_queue(self):
        """Traite la file d'impression avec vérifications d'état."""
        try:
            # Timeout pour permettre arrêt propre
            task_data = write_queue.get(timeout=0.5)
            self.prints_sent += 1

            # VÉRIFICATION ÉTAT AVANT CHAQUE IMPRESSION
            state = printer_state.get_state()
            current_time = time.strftime('%H:%M:%S')

            print(f"[{current_time}] 📊 [WRITER] Vérification état: cooling={state['cooling_active']}, error='{state['error']}'")

            # REFROIDISSEMENT ACTIF
            if state['cooling_active']:
                print(f"[{current_time}] ❄️ [WRITER] Refroidissement actif - tâche #{self.prints_sent} mise en attente")
                write_queue.put(task_data)  # Remettre en file
                time.sleep(0.5)  # Attendre avant revérification
                return

            # ERREUR ACTIVE
            if state['error']:
                print(f"[{current_time}] ❌ [WRITER] Erreur active '{state['error']}' - tâche #{self.prints_sent} mise en attente")
                write_queue.put(task_data)  # Remettre en file
                time.sleep(1.0)
                return

            # CONDITIONS OK - PROCÉDER À L'ENVOI
            print(f"[{current_time}] ✅ [WRITER] Conditions OK - envoi tâche #{self.prints_sent}")
            self._send_raster_data(task_data)

        except queue.Empty:
            pass  # File vide, continuer

    def _initialize_connection(self):
        """Initialise connexion avec vérification synchronisation."""
        try:
            print("🔌 [WRITER] Initialisation connexion USB...")

            # PAUSE si Listener est en cours d'écoute
            while printer_state.listener_listening and self.running:
                print("⏳ [WRITER] Attente fin écoute Listener pour éviter conflits...")
                time.sleep(0.5)

            self.dev = usb.core.find(idVendor=self.vendor_id, idProduct=self.product_id)
            if self.dev is None:
                print("❌ [WRITER] Imprimante non trouvée")
                return

            # Détacher kernel driver
            try:
                if self.dev.is_kernel_driver_active(0):
                    self.dev.detach_kernel_driver(0)
            except (AttributeError, NotImplementedError):
                pass

            # Configuration USB
            self.dev.set_configuration()
            cfg = self.dev.get_active_configuration()
            intf = cfg[(0,0)]

            # Endpoint de sortie
            self.ep_out = usb.util.find_descriptor(
                intf,
                custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
            )

            if self.ep_out:
                self.initialized = True
                print("✅ [WRITER] Connexion établie pour écriture")
            else:
                print("❌ [WRITER] Endpoint OUT non trouvé")

        except Exception as e:
            print(f"❌ [WRITER] Erreur initialisation: {e}")
            self.initialized = False

    def _send_raster_data(self, task_data):
        """Envoie données avec délai minimum Brother."""
        try:
            raster_data, label_num, task_id = task_data
            current_time = time.strftime('%H:%M:%S')

            print(f"[{current_time}] 📤 [WRITER] Envoi étiquette #{label_num} (tâche {task_id})")

            # Vérifier à nouveau avant envoi (redondance de sécurité)
            if printer_state.get_state()['cooling_active']:
                print("⚠️ [WRITER] Refroidissement détecté juste avant envoi - annulation")
                write_queue.put(task_data)  # Remettre en file
                return

            # ENVOI DES DONNÉES
            self.ep_out.write(raster_data, timeout=10000)
            print(f"[{current_time}] ✅ [WRITER] Étiquette #{label_num} envoyée")

            # DÉLAI MINIMUM entre impressions (spécifications Brother)
            time.sleep(1.0)  # 1 seconde minimum

        except usb.core.USBError as e:
            error_msg = f"Erreur USB écriture: {e}"
            print(f"❌ [WRITER] {error_msg}")
            printer_state.set_error("USB_WRITE_ERROR", error_msg)
            self.initialized = False

    def stop(self):
        """Arrêt propre."""
        self.running = False
        if self.dev:
            usb.util.dispose_resources(self.dev)
            self.dev = None

def start_async_printer():
    """Démarre l'architecture asynchrone complète."""
    global listener_thread, writer_thread

    # Vérifications de sécurité
    if listener_thread and listener_thread.is_alive():
        print("ℹ️ [ASYNC] Thread Listener déjà actif")
        return
    if writer_thread and writer_thread.is_alive():
        print("ℹ️ [ASYNC] Thread Writer déjà actif")
        return

    print("🚀 [ASYNC] Démarrage architecture asynchrone Brother QL-700 avec synchronisation")

    # Créer threads synchronisés
    listener_thread = USBListener()
    writer_thread = USBWriter()

    # Démarrage synchronisé
    listener_thread.start()
    time.sleep(0.2)  # Petit délai Listener avant Writer
    writer_thread.start()

    # Mise à jour état global
    printer_state.listener_running = True
    printer_state.writer_running = True

    print("✅ [ASYNC] Architecture asynchrone active: Listener + Writer synchronisés")

def stop_async_printer():
    """Arrêt propre des threads."""
    global listener_thread, writer_thread

    print("🛑 [ASYNC] Arrêt architecture asynchrone")

    if listener_thread:
        listener_thread.stop()
        listener_thread.join(timeout=5)

    if writer_thread:
        writer_thread.stop()
        writer_thread.join(timeout=5)

    printer_state.listener_running = False
    printer_state.writer_running = False

    print("✅ [ASYNC] Threads arrêtés proprement")

def add_print_job(raster_data, label_num, task_id):
    """Ajoute tâche à la file d'impression asynchrone."""
    write_queue.put((raster_data, label_num, task_id))
    current_time = time.strftime('%H:%M:%S')
    print(f"[{current_time}] 📋 [QUEUE] Tâche ajoutée: étiquette #{label_num}, tâche {task_id}")

class PrinterDriver:
    """Driver bas niveau pyusb (compatible ancienne implémentation)"""

    def __init__(self):
        self.dev = None
        self.ep_out = None
        self.ep_in = None
        self.connect_usb()

    # ... méthodes restées inchangées pour compatibilité ...
