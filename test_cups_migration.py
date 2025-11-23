#!/usr/bin/env python3
"""
Script de test pour vérifier que la migration CUPS fonctionne correctement.
À exécuter sur le Raspberry Pi où l'imprimante Brother QL-700 est connectée.
"""

import subprocess
import sys
import os

def run_command(cmd, description):
    """Exécute une commande et affiche le résultat."""
    print(f"\n🧪 [TEST] {description}")
    print(f"Commande: {cmd}")

    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        print(f"Code de retour: {result.returncode}")

        if result.stdout:
            print(f"Sortie standard:\n{result.stdout}")

        if result.stderr:
            print(f"Erreurs:\n{result.stderr}")

        return result.returncode == 0
    except Exception as e:
        print(f"Erreur lors de l'exécution: {e}")
        return False

def test_cups_setup():
    """Teste la configuration CUPS."""
    print("🔍 [TEST] VÉRIFICATION DE LA CONFIGURATION CUPS")
    print("=" * 60)

    # Test 1: CUPS installé et démarré
    success = True
    success &= run_command("systemctl is-active cups", "Vérification que CUPS est actif")

    # Test 2: Liste des imprimantes
    success &= run_command("lpstat -p", "Liste des imprimantes configurées")

    # Test 3: Recherche d'imprimantes USB
    success &= run_command("lpinfo -v | grep -i brother", "Recherche d'imprimantes Brother USB")

    return success

def test_python_dependencies():
    """Teste les dépendances Python."""
    print("\n🐍 [TEST] VÉRIFICATION DES DÉPENDANCES PYTHON")
    print("=" * 60)

    try:
        import cups
        print("✅ [PYTHON] Module 'cups' importé avec succès")
        print(f"   Version cups: {cups.__version__ if hasattr(cups, '__version__') else 'N/A'}")
    except ImportError as e:
        print(f"❌ [PYTHON] Module 'cups' non installé: {e}")
        return False

    try:
        from print_service import print_batch_cups, PRINTER_NAME
        print("✅ [PYTHON] Module 'print_service' importé avec succès")
        print(f"   Nom de l'imprimante configuré: {PRINTER_NAME}")
    except ImportError as e:
        print(f"❌ [PYTHON] Module 'print_service' non importable: {e}")
        return False

    return True

def test_printer_connection():
    """Teste la connexion à l'imprimante."""
    print("\n🖨️ [TEST] VÉRIFICATION DE LA CONNEXION IMPRIMANTE")
    print("=" * 60)

    try:
        from print_service import print_batch_cups
        print("✅ [CONNECTION] Service CUPS accessible")

        # Essayer de se connecter à CUPS et vérifier l'imprimante
        try:
            import cups
            conn = cups.Connection()
            printers = conn.getPrinters()
            print(f"📋 [CONNECTION] Imprimantes trouvées: {list(printers.keys())}")

            from print_service import PRINTER_NAME
            if PRINTER_NAME in printers:
                print(f"✅ [CONNECTION] Imprimante '{PRINTER_NAME}' trouvée dans CUPS")
                return True
            else:
                print(f"❌ [CONNECTION] Imprimante '{PRINTER_NAME}' NON trouvée dans CUPS")
                print("   → Vérifiez que l'imprimante est connectée et la LED 'Editor Lite' éteinte")
                return False

        except cups.IPPError as e:
            print(f"❌ [CONNECTION] Erreur CUPS: {e}")
            return False

    except ImportError as e:
        print(f"❌ [CONNECTION] Impossible d'importer print_service: {e}")
        return False

def create_test_image():
    """Crée une image de test simple pour les tests."""
    print("\n🎨 [TEST] CRÉATION D'UNE IMAGE DE TEST")
    print("=" * 60)

    try:
        from PIL import Image, ImageDraw, ImageFont
        import os

        # Créer un dossier de test
        test_dir = "test_images"
        os.makedirs(test_dir, exist_ok=True)

        # Créer une image de test
        img = Image.new('RGB', (200, 100), color='white')
        draw = ImageDraw.Draw(img)

        # Essayer de charger une police, sinon utiliser la police par défaut
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        except:
            font = ImageFont.load_default()

        # Dessiner du texte
        draw.text((10, 30), "TEST CUPS MIGRATION", fill='black', font=font)
        draw.text((10, 60), f"Timestamp: {os.path.basename(__file__)}", fill='gray', font=font)

        # Sauvegarder
        test_image_path = os.path.join(test_dir, "test_cups.png")
        img.save(test_image_path)

        print(f"✅ [IMAGE] Image de test créée: {test_image_path}")
        return test_image_path

    except ImportError:
        print("❌ [IMAGE] PIL/Pillow non installé - impossible de créer l'image de test")
        return None
    except Exception as e:
        print(f"❌ [IMAGE] Erreur lors de la création de l'image: {e}")
        return None

def test_print_job():
    """Teste l'envoi d'un job d'impression."""
    print("\n📤 [TEST] TEST D'ENVOI D'UN JOB D'IMPRESSION")
    print("=" * 60)

    # Vérifier d'abord que l'imprimante est disponible
    if not test_printer_connection():
        print("⏭️ [PRINT] Test d'impression ignoré (imprimante non disponible)")
        return False

    # Créer une image de test
    test_image = create_test_image()
    if not test_image:
        print("⏭️ [PRINT] Test d'impression ignoré (image de test non créée)")
        return False

    try:
        from print_service import print_batch_cups

        print(f"📤 [PRINT] Envoi de l'image de test: {test_image}")

        # Envoyer UNE SEULE copie pour le test
        success = print_batch_cups([test_image], "TEST_MIGRATION")

        if success:
            print("✅ [PRINT] Job d'impression envoyé avec succès")
            print("   → Vérifiez que l'imprimante reçoit et imprime l'étiquette de test")
            return True
        else:
            print("❌ [PRINT] Échec de l'envoi du job d'impression")
            return False

    except Exception as e:
        print(f"❌ [PRINT] Erreur lors du test d'impression: {e}")
        return False

def main():
    """Fonction principale du script de test."""
    print("🚀 TESTS DE MIGRATION BROTHER QL → CUPS")
    print("=" * 60)
    print(f"Date/heure: {os.popen('date').read().strip()}")
    print(f"Système: {os.popen('uname -a').read().strip()}")
    print(f"Utilisateur: {os.popen('whoami').read().strip()}")
    print()

    all_tests_passed = True

    # Test 1: Configuration CUPS
    all_tests_passed &= test_cups_setup()

    # Test 2: Dépendances Python
    all_tests_passed &= test_python_dependencies()

    # Test 3: Connexion imprimante
    printer_available = test_printer_connection()

    # Test 4: Job d'impression (seulement si l'imprimante est disponible)
    if printer_available:
        all_tests_passed &= test_print_job()
    else:
        print("\n⚠️ [WARNING] Tests d'impression ignorés car l'imprimante n'est pas disponible")

    # Résumé final
    print("\n" + "=" * 60)
    if all_tests_passed:
        print("🎉 [RÉSULTAT] TOUS LES TESTS SONT PASSÉS !")
        print("   → La migration CUPS semble fonctionner correctement")
        print("   → Vous pouvez maintenant utiliser le serveur d'impression avec CUPS")
    else:
        print("⚠️ [RÉSULTAT] CERTAINS TESTS ONT ÉCHOUÉ")
        print("   → Vérifiez les erreurs ci-dessus avant de procéder")

    print("=" * 60)

    return all_tests_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
