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
        """Envoie la commande ESC i S et lit la réponse de 32 octets de manière bloquante.

        Retourne un dict avec l'état de l'imprimante.
        """
        cmd = b'\x1B\x69\x53'  # ESC i S
        self.ep_out.write(cmd)

        # Lit 32 octets de réponse de manière bloquante
        response = self.ep_in.read(32)

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
