#!/usr/bin/env python3
"""
Script de test pour vérifier la détection d'orientation et la rotation automatique.
"""

import os
import sys
from PIL import Image

# Ajouter le répertoire courant au path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importer la fonction de détection
from print_service import detect_image_orientation

def create_test_images():
    """Crée des images de test pour vérifier la rotation."""
    # Créer un répertoire de test
    test_dir = "test_images"
    os.makedirs(test_dir, exist_ok=True)

    # Image paysage (plus large que haute)
    landscape = Image.new('RGB', (200, 100), color='red')
    landscape_path = os.path.join(test_dir, "landscape.png")
    landscape.save(landscape_path)

    # Image portrait (plus haute que large)
    portrait = Image.new('RGB', (100, 200), color='blue')
    portrait_path = os.path.join(test_dir, "portrait.png")
    portrait.save(portrait_path)

    # Image carrée (test edge case)
    square = Image.new('RGB', (150, 150), color='green')
    square_path = os.path.join(test_dir, "square.png")
    square.save(square_path)

    return [landscape_path, portrait_path, square_path]

def test_orientation_detection():
    """Teste la détection d'orientation."""
    print("🔍 Test de détection d'orientation...")

    test_images = create_test_images()

    for img_path in test_images:
        orientation = detect_image_orientation(img_path)
        filename = os.path.basename(img_path)
        print(f"📐 {filename}: {orientation}")

    print("✅ Test terminé!")

    # Nettoyer
    import shutil
    shutil.rmtree("test_images", ignore_errors=True)

if __name__ == "__main__":
    test_orientation_detection()
    print("\n🎯 Test de rotation : Les images portrait seront automatiquement tournées à 90°")
    print("   - orientation-requested=4 (90° clockwise) pour portrait")
    print("   - orientation-requested=3 (pas de rotation) pour landscape")

    print("\n🚀 Prochaines étapes :")
    print("   1. Transférez les fichiers sur votre Raspberry Pi")
    print("   2. Exécutez la configuration automatique :")
    print("      scp auto_configure_printer.sh printer-setup.service admin@raspberrypi:~/PrintServer/")
    print("      chmod +x ~/PrintServer/auto_configure_printer.sh")
    print("      sudo cp ~/PrintServer/printer-setup.service /etc/systemd/system/")
    print("      sudo systemctl daemon-reload && sudo systemctl enable printer-setup.service")
    print("   3. Redémarrez et testez - tout sera automatique ! 🎊")
