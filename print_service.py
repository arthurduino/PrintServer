import cups
import os
import time

# Nom de l'imprimante défini dans CUPS
PRINTER_NAME = "Brother_QL-700"

def detect_image_orientation(image_path):
    """
    Détecte l'orientation d'une image (portrait/landscape).
    """
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            width, height = img.size
            return "portrait" if height > width else "landscape"
    except:
        # En cas d'erreur, considérer comme paysage
        return "landscape"

def print_batch_cups(image_paths, job_id):
    """
    Envoie une liste d'images à l'imprimante via CUPS.
    Tourne automatiquement les images portrait à 90°.

    Args:
        image_paths (list): Liste des chemins absolus des fichiers images (.png, .jpg).
        job_id (str): Identifiant unique de la tâche pour le suivi.
    """
    conn = cups.Connection()

    # Vérification présence imprimante
    printers = conn.getPrinters()
    if PRINTER_NAME not in printers:
        print(f"ERREUR: L'imprimante '{PRINTER_NAME}' n'est pas installée dans CUPS.")
        return False

    print(f"🚀 Début du job {job_id} via CUPS ({len(image_paths)} étiquettes)")

    # Configuration des options d'impression Brother
    # Utilise les options spécifiques du driver brother-ql-700.ppd
    options = {
        "PageSize": "62x29mm",
        "BrPriority": "BrQuality",    # Priorité qualité
        "BrBrightness": "7",          # Luminosité optimale
        "BrCutAtEnd": "ON"            # Découpe automatique
    }

    job_ids = []

    for index, img_path in enumerate(image_paths):
        if not os.path.exists(img_path):
            print(f"⚠️ Fichier manquant : {img_path}")
            continue

        try:
            # Détection orientation et configuration des options
            orientation = detect_image_orientation(img_path)
            print(f"📐 Image {index+1}: {orientation} - {os.path.basename(img_path)}")

            # Copier les options de base
            img_options = options.copy()

            # Appliquer la rotation pour les images portrait
            if orientation == "portrait":
                img_options["orientation-requested"] = "4"  # 90° clockwise
                print(f"🔄 Rotation 90° appliquée pour image portrait")
            else:
                img_options["orientation-requested"] = "3"  # Pas de rotation (landscape)

            # Envoi à CUPS avec les options appropriées
            cups_job_id = conn.printFile(PRINTER_NAME, img_path, f"Job_{job_id}_{index+1}", img_options)
            job_ids.append(cups_job_id)
            print(f"✅ Étiquette {index+1}/{len(image_paths)} envoyée au spooler (ID CUPS: {cups_job_id})")

            # Petit délai optionnel pour ne pas saturer le spooler CPU du Pi
            # (L'imprimante gérera elle-même sa pause refroidissement)
            time.sleep(0.1)

        except cups.IPPError as e:
            print(f"❌ Erreur CUPS sur l'image {img_path}: {e}")

    print(f"🏁 Tous les fichiers ont été transmis au spooler système.")
    return True

# --- EXEMPLE D'USAGE ---
if __name__ == "__main__":
    # Liste de fichiers images générés
    labels = [
        "/home/pi/labels/label_001.png",
        "/home/pi/labels/label_002.png",
        # ... jusqu'à 100
    ]

    print_batch_cups(labels, "TASK_123")
