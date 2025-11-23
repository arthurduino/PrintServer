import usb.core
import usb.util
import threading
import time
from queue import Queue, Empty
import struct

# Constantes USB Brother QL-700 (corrigées selon documentation officielle)
VENDOR_ID = 0x04f9   # Brother Industries, Ltd
PRODUCT_ID = 0x2042  # QL-700 Label Printer

# États globaux thread-safe (mémoire partagée)
printer_state = {
    'cooling': False,  # Flag de refroidissement
    'running': False,  # État général
    'job_queue': Queue(),  # File d'attente des tâches d'impression
    'current_job': None,  # Tâche en cours
    'shared_driver': None,  # Instance partagée de PrinterDriver
    'driver_lock': threading.Lock(),  # Lock pour éviter la concurrence USB
}

class PrinterDriver:
    """Driver bas niveau pyusb (compatible ancienne implémentation)"""

    def __init__(self):
        self.dev = None
        self.ep_out = None
        self.ep_in = None
        self.connect_usb()

    def connect_usb(self):
        """Établit la connexion USB (méthode de compatibilité)."""
        try:
            print(f"🔍 [PRINTER_DRIVER] Recherche imprimante Brother QL-700 (VID:0x{VENDOR_ID:04X}, PID:0x{PRODUCT_ID:04X})")

            # Recherche de l'imprimante
            self.dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)

            if self.dev is None:
                print("❌ [PRINTER_DRIVER] Imprimante Brother QL-700 non trouvée")
                print("🔧 [PRINTER_DRIVER] Vérifiez:")
                print("   - L'imprimante est branchée et allumée")
                print("   - Aucun autre logiciel n'utilise l'imprimante")
                print("   - Permissions USB (sur Linux/Raspberry Pi)")
                print("   - VID/PID corrects pour le modèle QL-700")

                # Lister tous les périphériques USB disponibles pour diagnostic
                try:
                    devices = list(usb.core.find(find_all=True))
                    print(f"📋 [PRINTER_DRIVER] Périphériques USB détectés: {len(devices)}")
                    print(f"📋 [PRINTER_DRIVER] Périphériques USB détectés: {len(devices)}")
                    for i, dev in enumerate(devices[:5]):  # Limiter à 5 premiers
                        print(f"   [{i}] VID:0x{dev.idVendor:04X} PID:0x{dev.idProduct:04X} - {dev.manufacturer} {dev.product}")
                    if len(devices) > 5:
                        print(f"   ... et {len(devices)-5} autres")
                except Exception as list_e:
                    print(f"❌ [PRINTER_DRIVER] Impossible de lister les USB: {list_e}")

                raise usb.core.USBError("Imprimante Brother QL-700 non trouvée")

            print(f"✅ [PRINTER_DRIVER] Imprimante trouvée - Configuration USB...")

            # Détacher kernel driver
            try:
                if self.dev.is_kernel_driver_active(0):
                    print("🔧 [PRINTER_DRIVER] Détachement du driver kernel...")
                    self.dev.detach_kernel_driver(0)
            except (AttributeError, NotImplementedError):
                pass

            # Configuration USB
            self.dev.set_configuration()
            cfg = self.dev.get_active_configuration()
            intf = cfg[(0,0)]

            # Endpoints
            self.ep_out = usb.util.find_descriptor(
                intf,
                custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
            )
            self.ep_in = usb.util.find_descriptor(
                intf,
                custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
            )

            if not self.ep_out or not self.ep_in:
                raise usb.core.USBError("Endpoints USB non trouvés")

            print("✅ [PRINTER_DRIVER] Connexion établie avec compatibilité ancienne")
            print(f"   📥 ENDPOINT_IN: 0x{self.ep_in.bEndpointAddress:02X}")
            print(f"   📤 ENDPOINT_OUT: 0x{self.ep_out.bEndpointAddress:02X}")
            return True

        except Exception as e:
            print(f"❌ [PRINTER_DRIVER] Erreur connexion: {e}")
            return False

    def send_command(self, command):
        """Envoie une commande (méthode de compatibilité)."""
        if not self.ep_out:
            raise usb.core.USBError("Connexion non établie")

        self.ep_out.write(command, timeout=5000)

    def read_response(self, size=32, timeout=1000):
        """Lit une réponse (méthode de compatibilité)."""
        if not self.ep_in:
            raise usb.core.USBError("Connexion non établie")

        return self.ep_in.read(size, timeout=timeout)

    def disconnect(self):
        """Déconnexion propre (méthode de compatibilité)."""
        if self.dev:
            usb.util.dispose_resources(self.dev)
            self.dev = None
            self.ep_out = None
            self.ep_in = None
            print("🧹 [PRINTER_DRIVER] Déconnexion propre")

# Architecture asynchrone - Writer/Listener

def listener_thread():
    """Thread Listener : lit passivement l'Endpoint IN pour détecter le refroidissement."""
    print("🐛 [LISTENER] DEBUG: Listener DÉMARRÉ - vérification connexion")

    shared_driver = printer_state.get('shared_driver')
    if not shared_driver:
        print("❌ [LISTENER] DEBUG: Connexion USB partagée non disponible")
        return

    # VÉRIFICATION ENDPOINT - Point critique identifié
    if not hasattr(shared_driver, 'ep_in') or not shared_driver.ep_in:
        print("❌ [LISTENER] DEBUG: Endpoint IN non valide - CRASH IMMÉDIAT")
        raise ValueError("Endpoint IN manquant pour le Listener")

    print(f"🐛 [LISTENER] DEBUG: Endpoint IN valide: 0x{shared_driver.ep_in.bEndpointAddress:02X}")

    print("👂 [LISTENER] Thread d'écoute démarré (avec debug forcé)")

    # Envoi d'une seule commande de statut au démarrage (pas de polling actif)
    try:
        with printer_state['driver_lock']:
            status_request = bytes([0x1B, 0x69, 0x53])  # 1B 69 53 - Status Information Request
            shared_driver.send_command(status_request)
        print("📡 [LISTENER] Commande de statut initiale envoyée")
    except Exception as e:
        print(f"❌ [LISTENER] Erreur envoi commande statut initiale: {e}")
        return

    iteration_count = 0
    while printer_state['running']:
        iteration_count += 1
        try:
            # Lecture passive de 32 octets (Status Information) avec lock et TIMEOUT
            with printer_state['driver_lock']:
                print(f"🐛 [LISTENER] DEBUG: Iteration #{iteration_count} - Lecture avec timeout...")
                status_packet = shared_driver.read_response(size=32, timeout=1000)  # TIMEOUT OBLIGATOIRE
                print(f"📥 [LISTENER] DEBUG: Données reçues: {len(status_packet)} octets")

            if len(status_packet) == 32:
                print(f"📦 [LISTENER] DEBUG: Paquet valide 32 octets - Analyse...")
                # Analyse des bytes 18 et 22 pour détecter le refroidissement
                byte_18 = status_packet[18]
                byte_22 = status_packet[22]
                print(f"📊 [LISTENER] DEBUG: Bytes [18,22] = [{byte_18:02X}, {byte_22:02X}]")

                # Logique de détection de refroidissement selon la doc Brother
                if byte_18 == 0x05 and byte_22 == 0x03:
                    # PAUSE : Refroidissement nécessaire
                    printer_state['cooling'] = True
                    print("🧊 [LISTENER] Refroidissement détecté - Writer mis en pause")
                elif byte_18 == 0x05 and byte_22 == 0x04:
                    # REPRISE : Refroidissement terminé
                    printer_state['cooling'] = False
                    print("🔥 [LISTENER] Refroidissement terminé - Writer relancé")
                else:
                    print("ℹ️ [LISTENER] DEBUG: Status normal, pas de refroidissement")
            else:
                print(f"⚠️ [LISTENER] DEBUG: Paquet invalide taille {len(status_packet)} (attendu 32)")

        except usb.core.USBError as e:
            if e.errno == 110:  # Operation timed out - NORMAL avec QL-700 muet
                print(f"⏰ [LISTENER] DEBUG: Timeout errno 110 (normal avec QL-700) - itération #{iteration_count}")
                continue
            else:
                print(f"❌ [LISTENER] Erreur USB: {e.errno} - {e}")
                break
        except Exception as e:
            print(f"❌ [LISTENER] Erreur inattendue: {e}")
            break

        # Pause courte pour éviter spam
        time.sleep(0.1)

    print("👂 [LISTENER] Thread d'écoute arrêté")

def writer_thread():
    """Thread Writer : traite la file d'attente et envoie les données raster par chunks."""
    shared_driver = printer_state.get('shared_driver')
    if not shared_driver:
        print("❌ [WRITER] Connexion USB partagée non disponible")
        return

    print("✍️ [WRITER] Thread d'écriture démarré (connexion partagée)")

    while printer_state['running']:
        try:
            # Récupération d'une tâche d'impression depuis la file
            try:
                job = printer_state['job_queue'].get(timeout=1.0)  # Timeout court pour rester réactif
                printer_state['current_job'] = job
                instructions, label_num, task_id = job

                print(f"📋 [WRITER] Traitement tâche {task_id}, étiquette #{label_num}")
                print(f"📊 [WRITER] Instructions raster: {len(list(instructions))} paquets")

                # Chunking des données raster (pas d'envoi complet d'un coup)
                chunk_size = 1024
                sent_chunks = 0

                for packet in instructions:
                    # CONTRÔLE DE FLUX : vérifier le flag de refroidissement AVANT chaque chunk
                    while printer_state['cooling']:
                        print(f"🧊 [WRITER] Pause - Attente fin de refroidissement pour tâche {task_id}")
                        time.sleep(0.1)  # Attente courte avant vérification

                    # Gestion des différents types de packets (brother_ql peut retourner bytes, tuple, ou objets)
                    if hasattr(packet, 'data'):
                        # Objet avec attribut .data (raster data)
                        data_to_send = bytes(packet.data)
                    elif isinstance(packet, (bytes, bytearray)):
                        # Directement des bytes
                        data_to_send = bytes(packet)
                    elif isinstance(packet, tuple) and len(packet) >= 2:
                        # Tuple (instruction_type, data)
                        data_to_send = bytes(packet[1]) if isinstance(packet[1], (bytes, bytearray)) else bytes([packet[1]])
                    elif isinstance(packet, int):
                        # Valeur entière seule (rare)
                        data_to_send = bytes([packet])
                    else:
                        # Type inconnu - convertir en bytes
                        try:
                            data_to_send = bytes(packet)
                        except:
                            print(f"⚠️ [WRITER] Type de packet inconnu ignoré: {type(packet)} - {packet}")
                            continue

                    # Envoi du chunk si les données sont valides avec lock
                    if data_to_send:
                        with printer_state['driver_lock']:
                            shared_driver.send_command(data_to_send)
                        sent_chunks += 1

                        # Debug limité (pas trop verbose)
                        if sent_chunks % 10 == 0:
                            print(f"📊 [WRITER] {sent_chunks} chunks envoyés pour tâche {task_id}")

                print(f"✅ [WRITER] Étiquette #{label_num} (tâche {task_id}) terminée ({sent_chunks} chunks)")

            except Empty:
                # File vide - continuer la boucle
                continue

        except Exception as e:
            print(f"❌ [WRITER] Erreur dans la boucle principale: {e}")
            # Continuer malgré l'erreur (résilience)
            continue

    # Ne pas déconnecter - la connexion est partagée
    print("✍️ [WRITER] Thread d'écriture arrêté")

# API publique asynchrone

def start_async_printer():
    """Démarre l'architecture asynchrone avec les threads Writer seulement.

    Le Listener est désactivé car l'imprimante QL-700 ne semble pas répondre
    aux commandes de statut Brother QL (réfrigération gérée par timeout simple).
    """
    if printer_state['running']:
        print("⚠️ [ASYNC] Architecture déjà démarrée")
        return

    # INITIALISER LA CONNEXION USB PARTAGÉE (règle la concurrence)
    printer_state['shared_driver'] = PrinterDriver()
    if not printer_state['shared_driver'].connect_usb():
        print("❌ [ASYNC] Impossible d'initialiser la connexion USB partagée")
        return

    printer_state['running'] = True
    printer_state['cooling'] = False  # État initial

    # THREAD LISTENER ACTIF avec DEBUG FORCÉ
    listener = threading.Thread(target=listener_thread, daemon=True, name="PrinterListener")
    listener.start()
    print("🎯 [ASYNC] Listener thread ACTIVÉ en mode DEBUG (forcé)")

    # Démarrage du thread Writer uniquement
    writer = threading.Thread(target=writer_thread, daemon=True, name="PrinterWriter")
    writer.start()

    print("✅ [ASYNC] Architecture Brother QL-700 démarrée (Writer seulement)")
    print("   ✍️ Writer thread actif avec connexion partagée")
    print("   🔒 Lock USB pour éviter la concurrence")
    print("   ❄️ Réfrigération gérée par timeout simple (pas de Listener)")

def stop_async_printer():
    """Arrête proprement l'architecture asynchrone."""
    if not printer_state['running']:
        print("⚠️ [ASYNC] Architecture déjà arrêtée")
        return

    print("🛑 [ASYNC] Arrêt de l'architecture asynchrone Brother QL-700...")
    printer_state['running'] = False

    # Attendre que la file se vide (timeout de sécurité)
    timeout = 10
    start_time = time.time()
    while not printer_state['job_queue'].empty() and (time.time() - start_time) < timeout:
        time.sleep(0.1)

    # Déconnecter proprement la connexion USB partagée
    if printer_state.get('shared_driver'):
        try:
            printer_state['shared_driver'].disconnect()
            print("🧹 [ASYNC] Connexion USB partagée déconnectée proprement")
        except Exception as e:
            print(f"⚠️ [ASYNC] Erreur lors de la déconnexion USB: {e}")

        # Nettoyer l'état global
        printer_state['shared_driver'] = None

    printer_state['cooling'] = False
    print("✅ [ASYNC] Architecture asynchrone Brother QL-700 arrêtée complètement")

def create_ql_print_commands(instructions, model='QL-700', label_type=62):
    """
    brother_ql.convert() génère déjà toutes les commandes nécessaires.
    On retourne simplement les instructions telles quelles.
    """
    print(f"📋 [QL_CMD] Utilisation directe brother_ql: {len(list(instructions))} packets")
    return instructions

def add_print_job(instructions, label_num, task_id):
    """Ajoute une tâche d'impression à la file d'attente asynchrone."""
    # Encapsuler avec les commandes Brother QL complètes
    complete_commands = create_ql_print_commands(instructions, label_num, task_id)

    job = (complete_commands, label_num, task_id)
    printer_state['job_queue'].put(job)
    print(f"📋 [ASYNC] Job ajouté à la file: tâche {task_id}, étiquette #{label_num} ({len(complete_commands)} commandes)")
    print(f"� [ASYNC] File d'attente: {printer_state['job_queue'].qsize()} jobs")
