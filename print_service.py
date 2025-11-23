import cups
import os
import time

# Nom de l'imprimante défini dans CUPS
PRINTER_NAME = "Brother_QL-700"

def print_batch_cups(image_paths, job_id):
    """
    Envoie une liste d'images à l'imprimante via CUPS.

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

    # Configuration des options d'impression pour CUPS
    # Options pour Brother QL-700 via le driver brother-ql-700.ppd
    options = {
        "Resolution": "300dpi",  # Qualité : 300dpi, 600dpi (plus lent mais meilleure qualité)
        "PageSize": "62x29mm",   # Format d'étiquette
        "MediaType": "continuous",   # Type de média
        "CutMedia": "true",      # Découpe automatique
        "Halftoning": "error-diffusion",  # Qualité du tramage
        "PrintSpeed": "normal"   # Vitesse : fast, normal, slow (affecte la chaleur/refroidissement)
    }

    job_ids = []

    for index, img_path in enumerate(image_paths):
        if not os.path.exists(img_path):
            print(f"⚠️ Fichier manquant : {img_path}")
            continue

        try:
            # Envoi à CUPS
            # printFile(imprimante, fichier, titre, options)
            cups_job_id = conn.printFile(PRINTER_NAME, img_path, f"Job_{job_id}_{index+1}", options)
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
