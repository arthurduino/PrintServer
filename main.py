# Point d'entrée pour lancer le serveur (si exécuté directement)
if __name__ == "__main__":
    import uvicorn
    print("Démarrage du Print Server...")
    print("Accès via : http://localhost:8000")
    print("Appuyez Ctrl+C pour arrêter")
    uvicorn.run(app, host="0.0.0.0", port=8000)
