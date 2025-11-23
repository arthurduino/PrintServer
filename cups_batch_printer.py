import cups
import time

class CupsBatchPrinter:
    def __init__(self, printer_name="Brother_QL-700"):
        self.conn = cups.Connection()
        self.printer_name = printer_name

    def send_batch(self, image_paths, job_name_prefix="Batch"):
        """
        Envoie toutes les images et retourne la liste des Job IDs pour suivi.
        """
        job_ids = []
        # Options pour forcer le continu et l'orientation
        options = {
            "orientation-requested": "3",  # Portrait (Pas de rotation driver)
            "fit-to-page": "True"          # Adapter aux 62mm
        }

        print(f"🚀 Envoi de {len(image_paths)} étiquettes au spooler...")

        for i, img in enumerate(image_paths):
            title = f"{job_name_prefix}_{i+1}/{len(image_paths)}"
            try:
                job_id = self.conn.printFile(self.printer_name, img, title, options)
                job_ids.append(job_id)
            except Exception as e:
                print(f"❌ Erreur envoi {img}: {e}")

        return job_ids

    def track_progress(self, job_ids):
        """
        Fonction bloquante qui affiche la progression en temps réel.
        À exécuter dans un thread séparé si besoin.
        """
        total = len(job_ids)
        pending_ids = set(job_ids)

        print("⏳ Démarrage du suivi d'impression...")

        while pending_ids:
            # Récupère tous les jobs actifs (Processing ou Pending)
            # which_jobs='not-completed' est le défaut
            current_jobs = self.conn.getJobs(my_jobs=True, which_jobs='not-completed')

            # Les jobs encore dans 'current_jobs' ne sont pas finis
            active_ids = set(current_jobs.keys())

            # Intersection : Quels sont NOS jobs qui sont encore actifs ?
            still_running = pending_ids.intersection(active_ids)

            # Ceux qui ne sont plus actifs sont finis
            finished_count = total - len(still_running)

            # Calcul du pourcentage
            percent = (finished_count / total) * 100

            # Affichage (ou mise à jour via WebSocket pour votre interface Web)
            # \r permet de réécrire la ligne
            print(f"🔄 Progression : {finished_count}/{total} ({percent:.1f}%) - En cours: {list(still_running)[:3]}...", end="\r")

            # Si tout est fini, on sort
            if not still_running:
                break

            # Mise à jour de la liste locale pour le prochain tour
            # (Optionnel, ici on recalcul tout à chaque fois pour être sûr)

            time.sleep(1) # Pause pour ne pas spammer CUPS

        print(f"\n✅ Impression terminée ! ({total} étiquettes)")

# --- EXEMPLE D'UTILISATION ---
if __name__ == "__main__":
    printer = CupsBatchPrinter()
    # Simulation de fichiers
    files = ["/home/admin/img.png"] * 10 # 10 fois la même image
    # 1. Envoi
    ids = printer.send_batch(files, "MonLot")
    # 2. Suivi
    printer.track_progress(ids)
