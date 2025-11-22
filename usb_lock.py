import threading

# Verrou central thread-safe unique pour tous les accès USB
# Ce lock protège contre les race conditions entre l'API Web et le Worker d'impression
printer_lock = threading.Lock()
