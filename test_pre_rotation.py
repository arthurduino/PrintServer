#!/usr/bin/env python3
"""
Script de test pour la pré-rotation des images paysage.
Ce script applique directement la logique de pré-rotation sur une image test.
"""

import os
import sys
from PIL import Image

def pre_rotate_landscape_image(image_path: str) -> bool:
    """
    PRÉ-ROTATION PHYSIQUE : Version de test pour debug
    """
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            print(f"📏 Dimensions d'origine: {width}x{height}")

            # Si l'image est paysage (plus large que haute)
            if width > height:
                print(f"🔄 [TEST] Image paysage détectée - Application rotation 90°...")

                # Rotation 90° dans le sens horaire
                rotated_img = img.rotate(90, expand=True)
                rotated_img.save(image_path, 'PNG')

                # Log des nouvelles dimensions
                new_width, new_height = rotated_img.size
                print(f"✅ [TEST] Image tournée sauvegardée: {new_width}x{new_height}")

                # Vérifier si maintenant c'est portrait
                if new_height > new_width:
                    print("✅ [TEST] Conversion paysage→portrait réussie!")
                else:
                    print("❌ [TEST] Problème: l'image n'est toujours pas portrait")

                return True  # Rotation effectuée

            else:
                print(f"📐 [TEST] Image déjà portrait ou carrée (H={height}, L={width}) - Pas de rotation")
                return False

    except Exception as e:
        print(f"❌ [TEST] Erreur lors de la pré-rotation: {e}")
        return False

def test_image_dimensions(image_path: str) -> bool:
    """Vérifie simplement les dimensions d'une image"""
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            print(f"📏 Image {os.path.basename(image_path)}: {width}x{height}")

            if width > height:
                print("🏞️  Cette image est PAYSAGE (plus large que haute)")
                print("🔄 Elle devrait être tournée de 90° pour corriger l'orientation")
                return True
            elif height > width:
                print("📱 Cette image est PORTRAIT (plus haute que large)")
                print("✅ Elle devrait rester telle quelle")
                return False
            else:
                print("⬜ Cette image est CARRÉE (mêmes dimensions)")
                print("✅ Elle sera traitée comme portrait")
                return False

    except Exception as e:
        print(f"❌ Erreur lors de la lecture des dimensions: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 SCRIPT DE TEST : Pré-rotation des images paysage")
    print("=" * 60)

    # Créer quelques images de test si elles n'existent pas
    os.makedirs("test_images", exist_ok=True)

    # Image paysage (comme celles qui posent problème)
    paysage_path = "test_images/test_paysage.png"
    if not os.path.exists(paysage_path):
        print("🎨 Création d'une image test paysage...")
        img_paysage = Image.new('RGB', (800, 600), color='blue')
        img_paysage.save(paysage_path)
        print(f"✅ Image paysage créée: {paysage_path}")

    # Image portrait (devrait rester inchangée)
    portrait_path = "test_images/test_portrait.png"
    if not os.path.exists(portrait_path):
        print("🎨 Création d'une image test portrait...")
        img_portrait = Image.new('RGB', (400, 800), color='red')
        img_portrait.save(portrait_path)
        print(f"✅ Image portrait créée: {portrait_path}")

    print("\n" + "=" * 40)
    print("📏 ANALYSE DES DIMENSIONS")
    print("=" * 40)

    # Tester les dimensions
    print(f"\n🔍 Test image paysage:")
    test_image_dimensions(paysage_path)

    print(f"\n🔍 Test image portrait:")
    test_image_dimensions(portrait_path)

    print("\n" + "=" * 40)
    print("🔄 TEST DE PRÉ-ROTATION")
    print("=" * 40)

    # Tester la pré-rotation sur l'image paysage
    print(f"\n🔄 Test pré-rotation sur image paysage:")
    rotated = pre_rotate_landscape_image(paysage_path)

    if rotated:
        print(f"\n🔍 Vérification après rotation:")
        test_image_dimensions(paysage_path)

    # Tester sur l'image portrait (ne devrait pas tourner)
    print(f"\n📱 Test sur image portrait (ne devrait pas tourner):")
    rotated_portrait = pre_rotate_landscape_image(portrait_path)

    print("\n" + "=" * 40)
    print("🔍 DÉTAILS TECHNIQUES POUR L'INTÉGRATION")
    print("=" * 40)
    print("La logique suivante doit être ajoutée dans worker.py :")
    print("1. Appeler _pre_rotate_landscape_image() avant _preprocess_image()")
    print("2. La fonction retourne True si l'image a été tournée")
    print("3. Continuer le traitement normal")
    print("\nSi cette logique fonctionne ici, elle fonctionnera dans le worker!")

    print("\n🧪 Test terminé. Les images dans 'test_images/' ont été modifiées pour démonstration.")
