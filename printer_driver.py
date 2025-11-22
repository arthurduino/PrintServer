import usb.core
import usb.util
import time
from typing import Dict

# Constantes pour l'imprimante Brother QL-700
VENDOR_ID = 0x04f9
PRODUCT_ID = 0x2042

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

    def attendre_buffer_libre(self):
        """Attend que l'imprimante soit prête (buffer libre) - Flow Control manuel."""
        timeout_start = time.time()
        max_timeout = 30.0  # 30 secondes maximum

        while True:
            # Timeout global
            if time.time() - timeout_start > max_timeout:
                raise Exception("Timeout: Imprimante toujours occupée après 30 secondes")

            # Envoie commande statut ESC i S
            try:
                self.ep_out.write(b'\x1B\x69\x53', timeout=5000)
                response = self.ep_in.read(32, timeout=5000)
            except usb.core.USBError as e:
                raise Exception(f"Erreur USB lors de la requête statut: {e}")

            # Vérification de la taille de réponse
            if len(response) < 32:
                raise Exception(f"Réponse statut incomplète: {len(response)} octets reçus au lieu de 32")

            # Vérifie octet d'erreur (index 8)
            if response[8] != 0:
                erreur_code = response[8]
                raise Exception(f"Erreur imprimante détectée (code: {erreur_code})")

            # Vérifie octet de statut (index 18) - bit 0 pour BUSY/IDLE
            is_busy = (response[18] & 0x01) != 0

            if not is_busy:
                print("✅ Imprimante prête (buffer libre)")
                return True
            else:
                print("⏳ Imprimante occupée, attente 0.5s...")
                time.sleep(0.5)

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

        try:
            # Configure l'appareil
            self.dev.set_configuration()
            print("Configuration USB définie")

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

        except Exception as e:
            # FORCE CLEANUP même en cas d'erreur d'initialisation
            if self.dev:
                usb.util.dispose_resources(self.dev)
            raise

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

    def send_data_with_chunking(self, data: bytes) -> bool:
        """Envoie des données binaires avec chunking pour éviter timeout USB et contrôle de flux."""
        try:
            # VALIDATION - contrôles préalables
            if not data:
                raise ValueError("Données vides reçues")

            # 1. ATTENDRE QUE LE BUFFER SOIT LIBRE avant tout envoi
            print(f"📤 Envoi de {len(data)} octets avec contrôle de flux...")
            self.attendre_buffer_libre()

            # 2. ENVOI COMMANDE INVALIDATE avant l'image (200 octets nuls)
            invalidate_cmd = b'\x00' * 200
            self.safe_write(invalidate_cmd, timeout=10000)
            print("✅ Commande INVALIDATE envoyée (buffer vidé)")

            # 3. ENVOI PAR CHUNKS DE 4096 OCTETS
            chunk_size = 4096
            total_chunks = (len(data) + chunk_size - 1) // chunk_size  # Division avec arrondi supérieur

            for i in range(total_chunks):
                start_idx = i * chunk_size
                end_idx = min(start_idx + chunk_size, len(data))
                chunk = data[start_idx:end_idx]

                # Timeout augmenté à 10 secondes pour gérer ralentissements thermiques
                success = self.safe_write(chunk, timeout=10000)
                if not success:
                    raise Exception(f"Échec envoi chunk {i+1}/{total_chunks}")

                print(f"✅ Chunk {i+1}/{total_chunks} envoyé ({len(chunk)} octets)")

            print(f"✅ Envoi complet réussi: {len(data)} octets en {total_chunks} chunks")
            return True

        except Exception as e:
            print(f"❌ Erreur lors de l'envoi avec chunking: {e}")
            raise

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
