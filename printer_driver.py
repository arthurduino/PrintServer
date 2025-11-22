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
        self._lock = threading.Lock()

    def set_cooling(self, active: bool):
        with self._lock:
            self.cooling_active = active
            print(f"🔄 [STATE] Cooling {'ACTIVÉ' if active else 'DÉSACTIVÉ'}")

    def set_error(self, error_type: str, message: str):
        with self._lock:
            self.error_message = f"{error_type}: {message}"
            print(f"❌ [STATE] Erreur définie: {self.error_message}")

    def clear_error(self):
        with self._lock:
            self.error_message = None
            print("✅ [STATE] Erreur effacée")

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
    """Thread d'écoute passive USB pour les messages spontanés de l'imprimante."""

    def __init__(self, vendor_id=VENDOR_ID, product_id=PRODUCT_ID):
        super().__init__(daemon=True, name="USB-Listener")
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.dev = None
        self.ep_in = None
        self.running = True
        self.initialized = False

    def run(self):
        """Boucle principale d'écoute."""
        print("👂 [LISTENER] Démarrage du thread d'écoute USB")

        while self.running:
            try:
                if not self.initialized:
                    self._initialize_connection()
                    if not self.initialized:
                        time.sleep(1)  # Réessaie dans 1 seconde
                        continue

                # Lecture passive des messages spontanés
                try:
                    # Timeout de 1000ms comme spécifié dans les exigences
                    response = self.ep_in.read(32, timeout=1000)

                    if len(response) == 32:
                        # Message complet - traiter silencieusement
                        self._process_status_message(response)
                    # Note: Les messages incomplets sont ignorés silencieusement (comportement normal)

                except usb.core.USBError as e:
                    if "timeout" in str(e).lower():
                        # Timeout normal - l'imprimante est silencieuse pendant le refroidissement
                        continue
                    else:
                        print(f"❌ [LISTENER] Erreur USB critique: {e}")
                        self.initialized = False
                        time.sleep(1)

            except Exception as e:
                print(f"❌ [LISTENER] Erreur critique: {e}")
                self.initialized = False
                time.sleep(2)  # Attendre plus longtemps après une erreur critique

        print("🛑 [LISTENER] Thread d'écoute arrêté")

    def _initialize_connection(self):
        """Initialise la connexion USB et effectue une seule requête de statut autorisée."""
        try:
            print("🔌 [LISTENER] Initialisation connexion USB...")

            # Recherche de l'imprimante
            self.dev = usb.core.find(idVendor=self.vendor_id, idProduct=self.product_id)
            if self.dev is None:
                return

            # Détache kernel driver si nécessaire
            try:
                if self.dev.is_kernel_driver_active(0):
                    self.dev.detach_kernel_driver(0)
            except (AttributeError, NotImplementedError):
                pass

            # Configuration
            self.dev.set_configuration()
            cfg = self.dev.get_active_configuration()
            intf = cfg[(0,0)]

            # Trouve l'endpoint IN
            self.ep_in = usb.util.find_descriptor(
                intf,
                custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
            )

            if not self.ep_in:
                print("❌ [LISTENER] Endpoint IN non trouvé")
                return

            # UNE SEULE REQUÊTE DE STATUT AUTORISÉE AU DÉMARRAGE (ESC i S)
            try:
                ep_out = usb.util.find_descriptor(
                    intf,
                    custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
                )
                if ep_out:
                    print("📡 [LISTENER] Envoi requête initiale de statut (autorisée)")
                    ep_out.write(b'\x1B\x69\x53', timeout=5000)
                    response = self.ep_in.read(32, timeout=5000)

                    if len(response) == 32:
                        self._process_status_message(response)
                        print("✅ [LISTENER] Statut initial obtenu - prêt pour écoute passive")
                        self.initialized = True
                    else:
                        print(f"⚠️ [LISTENER] Réponse initiale incomplète: {len(response)} octets")
                else:
                    print("❌ [LISTENER] Endpoint OUT non trouvé pour requête initiale")
            except Exception as e:
                print(f"⚠️ [LISTENER] Impossible d'envoyer requête initiale: {e}")

        except Exception as e:
            print(f"❌ [LISTENER] Erreur initialisation: {e}")
            self.initialized = False

    def _process_status_message(self, response):
        """Traite un message de statut selon les spécifications Brother."""
        try:
            status_type = response[18]  # Octet 18: Status Type
            notification_num = response[22] if len(response) > 22 else 0  # Octet 22: Notification Number
            error_info_1 = response[8] if len(response) > 8 else 0  # Octet 8: Error Info 1
            error_info_2 = response[9] if len(response) > 9 else 0  # Octet 9: Error Info 2

            current_time = time.strftime('%H:%M:%S')

            # Gestion des erreurs bloquantes (Octet 18 == 0x02)
            if status_type == 0x02:
                error_msg = ""
                if error_info_1 & 0x02:  # Bit 0: No media
                    error_msg = "Papier absent"
                    printer_state.set_error("MEDIA_ERROR", error_msg)
                elif error_info_1 & 0x04:  # Bit 2: Cutter jam
                    error_msg = "Bourrage cutter"
                    printer_state.set_error("CUTTER_JAM", error_msg)
                elif error_info_2 & 0x10:  # Bit 4: Cover open
                    error_msg = "Couvercle ouvert"
                    printer_state.set_error("COVER_OPEN", error_msg)
                else:
                    error_msg = f"Erreur inconnue (E1:{error_info_1:02X}, E2:{error_info_2:02X})"
                    printer_state.set_error("UNKNOWN_ERROR", error_msg)
                print(f"[{current_time}] ❌ [LISTENER] Erreur détectée: {error_msg}")
                return

            # Gestion des notifications (Octet 18 == 0x05)
            elif status_type == 0x05:
                if notification_num == 0x03:  # Cooling start
                    printer_state.set_cooling(True)
                    print(f"[{current_time}] ❄️ [LISTENER] Début de refroidissement détecté")

                elif notification_num == 0x04:  # Cooling finish
                    printer_state.set_cooling(False)
                    printer_state.clear_error()
                    print(f"[{current_time}] 🔥 [LISTENER] Fin de refroidissement détectée")

                else:
                    print(f"[{current_time}] ℹ️ [LISTENER] Notification {notification_num:02X}")

            # Autres types de statut
            elif status_type == 0x01:  # Printing completed
                print(f"[{current_time}] ✅ [LISTENER] Impression terminée")
            elif status_type == 0x06:  # Phase change
                print(f"[{current_time}] 🔄 [LISTENER] Changement de phase")
            else:
                print(f"[{current_time}] 🔍 [LISTENER] Statut inconnu: {status_type:02X}")

        except Exception as e:
            print(f"❌ [LISTENER] Erreur traitement message: {e}")

    def stop(self):
        """Arrête le thread d'écoute."""
        self.running = False
        if self.dev:
            usb.util.dispose_resources(self.dev)

class USBWriter(threading.Thread):
    """Thread d'écriture pour l'envoi séquentiel des données raster."""

    def __init__(self, vendor_id=VENDOR_ID, product_id=PRODUCT_ID):
        super().__init__(daemon=True, name="USB-Writer")
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.dev = None
        self.ep_out = None
        self.running = True
        self.initialized = False

    def run(self):
        """Boucle principale d'écriture."""
        print("✍️ [WRITER] Démarrage du thread d'écriture USB")

        while self.running:
            try:
                if not self.initialized:
                    self._initialize_connection()
                    if not self.initialized:
                        time.sleep(1)
                        continue

                # Attendre une tâche d'impression
                try:
                    task_data = write_queue.get(timeout=1)

                    # Vérifier l'état de refroidissement AVANT chaque envoi
                    state = printer_state.get_state()
                    if state['cooling_active']:
                        print("❄️ [WRITER] Refroidissement actif - mise en pause")
                        # Remettre la tâche dans la file pour la traiter plus tard
                        write_queue.put(task_data)
                        time.sleep(0.5)  # Attendre avant de revérifier
                        continue

                    # Vérifier les erreurs
                    if state['error']:
                        print(f"❌ [WRITER] Erreur active: {state['error']} - attente résolution")
                        write_queue.put(task_data)  # Remettre en file
                        time.sleep(1)
                        continue

                    # Envoyer les données
                    self._send_raster_data(task_data)

                except queue.Empty:
                    continue  # Pas de données à envoyer

            except Exception as e:
                print(f"❌ [WRITER] Erreur critique: {e}")
                self.initialized = False
                time.sleep(2)

        print("🛑 [WRITER] Thread d'écriture arrêté")

    def _initialize_connection(self):
        """Initialise la connexion USB pour l'écriture."""
        try:
            print("🔌 [WRITER] Initialisation connexion USB...")

            self.dev = usb.core.find(idVendor=self.vendor_id, idProduct=self.product_id)
            if self.dev is None:
                return

            try:
                if self.dev.is_kernel_driver_active(0):
                    self.dev.detach_kernel_driver(0)
            except (AttributeError, NotImplementedError):
                pass

            self.dev.set_configuration()
            cfg = self.dev.get_active_configuration()
            intf = cfg[(0,0)]

            self.ep_out = usb.util.find_descriptor(
                intf,
                custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
            )

            if self.ep_out:
                self.initialized = True
                print("✅ [WRITER] Connexion USB établie pour écriture")
            else:
                print("❌ [WRITER] Endpoint OUT non trouvé")

        except Exception as e:
            print(f"❌ [WRITER] Erreur initialisation: {e}")
            self.initialized = False

    def _send_raster_data(self, task_data):
        """Envoie les données raster à l'imprimante."""
        try:
            raster_data, label_num, task_id = task_data
            current_time = time.strftime('%H:%M:%S')

            print(f"[{current_time}] 📤 [WRITER] Envoi données étiquette #{label_num} (tâche {task_id})")

            # Envoyer les données
            self.ep_out.write(raster_data, timeout=10000)

            print(f"[{current_time}] ✅ [WRITER] Données étiquette #{label_num} envoyées")

        except usb.core.USBError as e:
            error_msg = f"Erreur USB écriture: {e}"
            print(f"❌ [WRITER] {error_msg}")
            printer_state.set_error("USB_WRITE_ERROR", error_msg)
            self.initialized = False
        except Exception as e:
            error_msg = f"Erreur inattendue: {e}"
            print(f"❌ [WRITER] {error_msg}")
            printer_state.set_error("UNKNOWN_ERROR", error_msg)

    def stop(self):
        """Arrête le thread d'écriture."""
        self.running = False
        if self.dev:
            usb.util.dispose_resources(self.dev)

def start_async_printer():
    """Démarre les threads asynchrones pour l'imprimante."""
    global listener_thread, writer_thread

    if listener_thread and listener_thread.is_alive():
        print("ℹ️ [ASYNC] Thread Listener déjà actif")
        return

    if writer_thread and writer_thread.is_alive():
        print("ℹ️ [ASYNC] Thread Writer déjà actif")
        return

    print("🚀 [ASYNC] Démarrage architecture asynchrone Brother QL-700")

    listener_thread = USBListener()
    writer_thread = USBWriter()

    listener_thread.start()
    writer_thread.start()

    printer_state.listener_running = True
    printer_state.writer_running = True

    print("✅ [ASYNC] Threads démarrés - architecture asynchrone active")

def stop_async_printer():
    """Arrête les threads asynchrones."""
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

    print("✅ [ASYNC] Threads arrêtés")

def add_print_job(raster_data, label_num, task_id):
    """Ajoute une tâche d'impression à la file."""
    write_queue.put((raster_data, label_num, task_id))
    print(f"📋 [QUEUE] Tâche ajoutée: étiquette #{label_num}, tâche {task_id}")

class PrinterDriver:
    """Driver bas niveau pour la Brother QL-700 utilisant pyusb."""

    def __init__(self):
        self.dev = None
        self.ep_out = None
        self.ep_in = None
        self.connect_usb()

    def recuperer_connexion(self):
        """Force le détachement du driver si Linux a repris la main sans reset destructif."""
        try:
            if self.dev and self.dev.is_kernel_driver_active(0):
                self.dev.detach_kernel_driver(0)
                print("✅ Driver Linux détaché de force (récupération gentle).")
                # Attendre un peu pour que le détachement soit effectif
                time.sleep(0.1)
                return True
            else:
                print("ℹ️ Pas de driver kernel actif - tentative de réinitialisation USB légère...")
                # Même si pas de kernel driver actif, forcer une réinitialisation légère
                if self.dev:
                    try:
                        # Essayer de resetter seulement l'interface (plus doux)
                        self.dev.set_configuration()
                        time.sleep(0.1)
                        return True
                    except Exception as e:
                        print(f"⚠️ Réinitialisation légère impossible: {e}")
                        return False
        except Exception as e:
            print(f"⚠️ Impossible de détacher le driver: {e}")
            return False

    def connect_usb(self):
        """Trouve et connecte la QL-700, détache kernel_driver si nécessaire."""
        print(f"Recherche de l'imprimante Brother QL-700 (VID:{VENDOR_ID:04x}, PID:{PRODUCT_ID:04x})...")

        # Lister tous les périphériques pour debug
        import usb.core
        devices = list(usb.core.find(find_all=True))
        print(f"Périphériques USB connectés: {len(devices)}")
        for dev in devices:
            print(f"  - VID:{dev.idVendor:04x}, PID:{dev.idProduct:04x}, Interface: {getattr(dev, 'product', 'N/A')}")

        self.dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)

        if self.dev is None:
            raise Exception("Imprimante Brother QL-700 non trouvée ou droits insufisants. Vérifiez USB et permissions.")

        print(f"Imprimante trouvée ! Configuration en cours...")

        # Détache le kernel driver sur Linux (pas nécessaire sur Windows)
        try:
            if self.dev.is_kernel_driver_active(0):
                print("Détachement du kernel driver...")
                self.dev.detach_kernel_driver(0)
        except (AttributeError, NotImplementedError):
            # Non disponible sur certaines plate-formes (Windows)
            print("Kernel driver: non applicable ou déjà détaché")
            pass

        # Configure l'appareil
        try:
            self.dev.set_configuration()
            print("Configuration USB définie")
        except usb.core.USBError as e:
            print(f"Erreur configuration USB: {e}")
            raise

        # Obtient la configuration active
        cfg = self.dev.get_active_configuration()
        intf = cfg[(0,0)]

        # Trouve les endpoints IN et OUT
        self.ep_out = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
        )
        self.ep_in = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
        )

        if not self.ep_out or not self.ep_in:
            raise Exception("Endpoints USB non trouvés - vérifiez le modèle d'imprimante")

        print("Connexion USB établie avec succès")

    def get_status(self) -> Dict:
        """Envoie la commande ESC i S et lit la réponse sans connexion persistante."""
        # Ouvrir/fermer une connexion fresh pour éviter de monopoliser l'imprimante
        dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        if dev is None:
            print("⚠️ Imprimante introuvable pour statut - connexion temporaire impossible")
            return {
                'is_busy': False,
                'paper_empty': False,
                'cover_open': False,
                'is_cooling': False,
                'phase': 'DISCONNECTED',
                'raw_phase': 0,
                'is_error': True
            }

        try:
            # Détacher kernel si actif
            if dev.is_kernel_driver_active(0):
                dev.detach_kernel_driver(0)

            # Configuration temporaire
            dev.set_configuration()
            cfg = dev.get_active_configuration()
            intf = cfg[(0,0)]

            # Trouver les endpoints
            ep_out = usb.util.find_descriptor(
                intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
            )
            ep_in = usb.util.find_descriptor(
                intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
            )

            if not ep_out or not ep_in:
                return {
                    'is_busy': False,
                    'paper_empty': False,
                    'cover_open': False,
                    'is_cooling': False,
                    'phase': 'ENDPOINT_ERROR',
                    'raw_phase': 0,
                    'is_error': True
                }

            # Envoyer la commande
            ep_out.write(b'\x1B\x69\x53', timeout=5000)  # ESC i S

            # Lire réponse
            response = ep_in.read(32, timeout=5000)

        finally:
            # 🔥 CLÉ DE LA STABILITÉ : relâcher l'imprimante pour que d'autres processus puissent l'utiliser
            usb.util.dispose_resources(dev)

        # Vérifier que la réponse fait bien 32 octets (évite array index out of range)
        if len(response) < 32:
            print(f"Réponse USB tronquée: {len(response)} octets reçus au lieu de 32")
            # Retourner un statut d'erreur générique en cas de réponse incomplète
            return {
                'is_busy': False,
                'paper_empty': False,
                'cover_open': False,
                'is_cooling': False,
                'phase': 'ERROR',
                'raw_phase': 0,
                'is_error': True
            }

        # Parsing selon la spécification Brother (adapté pour QL-700)
        is_busy = (response[18] & 0x01) != 0  # bit 0 de l'octet 18

        # Octet 8 pour les erreurs (parsing approximatif - à ajuster selon documentation)
        media_status = response[8]
        paper_empty = (media_status & 0x02) != 0  # Hypotèse : bit 1 pour papier vide
        cover_open = (media_status & 0x40) != 0   # Hypotèse : bit 6 pour couvercle ouvert

        # Octet 9 pour détecter le refroidissement (Bit 4)
        is_cooling = (response[9] & 0x10) != 0

        # Phase logique étendue
        if is_cooling:
            phase = 'COOLING'
        elif is_busy:
            phase = 'PRINTING'
        else:
            phase = 'IDLE'

        # Phase sur les octets 10-11 (en little-endian) - conservé pour compatibilité
        raw_phase = response[10] + (response[11] << 8)

        return {
            'is_busy': is_busy,
            'paper_empty': paper_empty,
            'cover_open': cover_open,
            'is_cooling': is_cooling,
            'phase': phase,
            'raw_phase': raw_phase,
            'is_error': False  # Cooling n'est pas une erreur bloquante
        }

    def reconnect_usb(self):
        """Reconnecte à l'imprimante après une déconnexion, nettoie les ressources et réinitialise."""
        print("Tentative de reconnexion à l'imprimante après erreur USB...")
        try:
            # Libère les ressources de l'ancienne connexion
            if self.dev:
                usb.util.dispose_resources(self.dev)
                self.dev = None
            # Recherche à nouveau l'imprimante
            self.dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
            if self.dev is None:
                raise Exception("Imprimante Brother QL-700 non retrouvée après déconnexion.")
            print("Imprimante retrouvée, reconfiguration USB...")
            # Détache kernel driver si nécessaire
            try:
                if self.dev.is_kernel_driver_active(0):
                    self.dev.detach_kernel_driver(0)
            except (AttributeError, NotImplementedError):
                pass
            # Configure la nouvelle connexion
            self.dev.set_configuration()
            cfg = self.dev.get_active_configuration()
            intf = cfg[(0,0)]
            self.ep_out = usb.util.find_descriptor(
                intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
            )
            self.ep_in = usb.util.find_descriptor(
                intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
            )
            if not self.ep_out or not self.ep_in:
                raise Exception("Endpoints USB non trouvés après reconnexion.")
            # Envoie commande d'initialisation pour nettoyer le buffer de l'imprimante
            self.ep_out.write(b'\x1B\x40')  # ESC @ - Initialize printer
            print("Reconnexion USB réussie et imprimante initialisée.")
        except Exception as e:
            raise Exception(f"Échec de la reconnexion USB: {e}")

    def reset_usb_device(self):
        """Récupère gentiment la connexion sans reset destructif (OBSOLÈTE - utiliser recuperer_connexion)."""
        print("⚠️ Ancienne méthode reset appelée - utilisation récupération gentle...")
        return self.recuperer_connexion()

    def safe_write(self, data, timeout=5000):
        """Écrit des données avec récupération automatique en cas d'erreur Resource busy."""
        try:
            self.ep_out.write(data, timeout=timeout)
            return True
        except usb.core.USBError as e:
            if e.errno == 16:  # Resource Busy - Linux a repris le contrôle
                print("🔒 Linux a volé l'imprimante ! Récupération en cours...")
                if self.recuperer_connexion():
                    try:
                        # Réessaie après récupération
                        self.ep_out.write(data, timeout=timeout)
                        print("✅ Écriture réussie après récupération connexion")
                        return True
                    except usb.core.USBError as retry_e:
                        print(f"❌ Échec même après récupération: {retry_e}")
                        return False
                else:
                    print("❌ Impossible de récupérer la connexion")
                    return False
            else:
                # Autre erreur USB - attend un peu avant de signaler
                print(f"⚠️ Erreur USB noncritique: {e} - pause 1s...")
                time.sleep(1)
                return False

    def cut_label(self, copies: int = 1):
        """Effectue une coupe manuelle d'étiquettes.

        Args:
            copies: Nombre d'étiquettes à couper (par défaut: 1)
        """
        try:
            # Commande ESC i A pour coupe automatique
            # Format: ESC i A <copies>
            cmd = b'\x1B\x69\x41' + bytes([copies])
            self.safe_write(cmd, timeout=5000)
            print(f"✅ Coupe de {copies} étiquette(s) effectuée")
            # Attendre un peu pour que la coupe se complète
            time.sleep(2)
            return True
        except Exception as e:
            print(f"⚠️ Échec de la coupe manuelle: {e}")
            return False

    def disconnect(self):
        """Déconnecte l'imprimante (reset USB et remise du kernel driver)."""
        if self.dev:
            usb.util.dispose_resources(self.dev)
            # Remet le kernel driver si nécessaire (Linux)
            try:
                self.dev.attach_kernel_driver(0)
            except (AttributeError, NotImplementedError):
                pass
            self.dev = None

# Note : Sur Raspberry Pi, pyusb nécessite des permissions root ou des règles udev appropriées.
        usb.util.dispose_resources(self.dev)
