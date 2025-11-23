#!/usr/bin/env python3
"""
Script de correction pour le bug my_jobs=True dans worker.py
Corrige la fonction _track_progress_with_db_updates qui utilise aussi my_jobs=True
"""

import re

def fix_worker_my_jobs():
    """Corrige le paramètre my_jobs=True en my_jobs=False dans worker.py"""

    # Lire le fichier
    with open('worker.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Chercher et remplacer la ligne problématique
    pattern = r"current_jobs = conn\.getJobs\(my_jobs=True, which_jobs='not-completed'\)"
    replacement = "current_jobs = conn.getJobs(my_jobs=False, which_jobs='not-completed')"

    if re.search(pattern, content):
        # Appliquer la correction
        corrected_content = re.sub(pattern, replacement, content)

        # Écrire le fichier corrigé
        with open('worker.py', 'w', encoding='utf-8') as f:
            f.write(corrected_content)

        print("✅ [FIX] Correction appliquée : my_jobs=True → my_jobs=False dans _track_progress_with_db_updates")
        print("📋 La fonction verra maintenant tous les jobs système, pas seulement ceux de l'utilisateur actuel")
        return True
    else:
        print("⚠️ [FIX] Pattern non trouvé - vérifiez que le fichier n'a pas déjà été corrigé")
        return False

if __name__ == "__main__":
    print("🔧 Correction du bug my_jobs dans worker.py")
    print("=" * 50)
    print("PROBLÈME : getJobs(my_jobs=True) ne voit que les jobs de l'utilisateur actuel")
    print("           Si l'API Web envoie les jobs sous un autre utilisateur, le worker ne les voit pas")
    print("           → Résultat : {\"success\":true,\"printer_name\":\"Brother_QL-700\",\"total_jobs\":0,\"jobs\":[]}")
    print("")
    print("SOLUTION : Changer my_jobs=True en my_jobs=False pour voir TOUS les jobs système")

    success = fix_worker_my_jobs()

    if success:
        print("\n🎉 Correction terminée !")
        print("💡 Le travailleur verra maintenant tous les jobs CUPS, même ceux soumis par d'autres utilisateurs")
    else:
        print("\n❌ Correction non appliquée - vérifier le fichier manuellement")
