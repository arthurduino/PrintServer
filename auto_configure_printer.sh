#!/bin/bash

# Script automatique de configuration CUPS + Imprimante Brother QL-700
# À exécuter au démarrage du système

LOG_FILE="/var/log/printer_setup.log"
PRINTER_NAME="Brother_QL-700"
USB_URI="usb://Brother/QL-700?serial=000H7Z771314"

# Fonction de logging
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a $LOG_FILE
}

log "=== Démarrage configuration automatique imprimante ==="

# Vérifier si CUPS est installé
if ! command -v cupsd &> /dev/null; then
    log "❌ CUPS n'est pas installé. Installation..."
    sudo apt update && sudo apt install -y cups printer-driver-ptouch
fi

# Vérifier si pycups est disponible dans le venv
VENV_PYTHON="/home/admin/PrintServer/venv/bin/python3"
if [ ! -f "$VENV_PYTHON" ]; then
    log "❌ Environnement virtuel non trouvé"
    exit 1
fi

# Installer pycups dans le venv si nécessaire
$VENV_PYTHON -c "import cups" 2>/dev/null
if [ $? -ne 0 ]; then
    log "📦 Installation de pycups dans le venv..."
    sudo apt install -y libcups2-dev
    source /home/admin/PrintServer/venv/bin/activate
    pip install pycups
    deactivate
fi

# Démarrer CUPS
sudo systemctl start cups 2>/dev/null
sudo systemctl enable cups 2>/dev/null
sudo cupsctl --remote-any

# Attendre que CUPS soit prêt
sleep 2

# Vérifier si l'imprimante existe déjà
if lpstat -p "$PRINTER_NAME" &>/dev/null; then
    log "✅ Imprimante $PRINTER_NAME déjà configurée"
else
    log "🔍 Recherche imprimante USB..."

    # Essayer l'URI spécifique d'abord
    if sudo lpadmin -p "$PRINTER_NAME" -E -v "$USB_URI" -m "brother-ql-700.ppd" 2>/dev/null; then
        log "✅ Imprimante ajoutée avec URI spécifique"
    else
        # Chercher automatiquement l'URI USB du Brother QL-700
        USB_DEVICE=$(lpinfo -v | grep -i "brother.*ql" | head -1)
        if [ -n "$USB_DEVICE" ]; then
            URI=$(echo $USB_DEVICE | cut -d' ' -f2)
            if sudo lpadmin -p "$PRINTER_NAME" -E -v "$URI" -m "brother-ql-700.ppd"; then
                log "✅ Imprimante ajoutée automatiquement: $URI"
            else
                log "❌ Échec ajout imprimante automatique"
                exit 1
            fi
        else
            log "❌ Imprimante Brother QL-700 non trouvée"
            exit 1
        fi
    fi
fi

# Configurer les options Brother optimisées
log "⚙️ Configuration des optionsBrother..."
sudo lpoptions -p "$PRINTER_NAME" \
    -o PageSize=62x29mm \
    -o BrPriority=BrQuality \
    -o BrBrightness=7 \
    -o BrCutAtEnd=ON

# Attendre et vérifier
sleep 1
if lpstat -p "$PRINTER_NAME" | grep -q "enabled"; then
    log "🎉 Configuration imprimante terminée avec succès!"
    log "📊 État: $(lpstat -p "$PRINTER_NAME")"
else
    log "❌ Problème avec la configuration finale"
    exit 1
fi

log "=== Fin configuration automatique ==="
