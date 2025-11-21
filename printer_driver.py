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

    def send_and_wait(self, data: bytes):
        """Envoie les données binaires (raster) et attend que l'impression soit terminée de manière bloquante.

        Gère automatiquement les déconnexions USB avec reconnexion.
        Lève une exception si papier vide détecté.
        """
        try:
            # Envoi bloquant des données
            self.ep_out.write(data)
            # Attente bloquante tant que l'imprimante est occupée
            while True:
                status = self.get_status()
                if not status['is_busy']:
                    break
                if status['paper_empty']:
                    raise Exception("Papier vide détecté pendant l'impression")
        except usb.core.USBError as e:
            print(f"Erreur USB détectée: {e}")
            # Tente reconnexion et retry
            self.reconnect_usb()
            try:
                # Retry l'envoi avec la nouvelle connexion
                self.ep_out.write(data)
                while True:
                    status = self.get_status()
                    if not status['is_busy']:
                        break
                    if status['paper_empty']:
                        raise Exception("Papier vide détecté après reconnexion")
                print("Reprise de l'impression réussie après reconnexion.")
            except usb.core.USBError as e2:
                raise Exception(f"Échec permanent de l'impression après reconnexion: {e2}")

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
