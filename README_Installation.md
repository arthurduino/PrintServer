# 🚀 Migration CUPS - Installation Automatique

## 🎯 Objectif
Migrer automatiquement votre serveur d'impression de brother_ql vers CUPS avec configuration au démarrage.

## 📋 Prérequis
- Raspberry Pi avec Raspberry Pi OS/Debian/Ubuntu
- Imprimante Brother QL-700 connectée en USB
- **LED "Editor Lite" sur l'imprimante DOIT être éteinte**

## 🛠️ Installation Automatique (Recommandée)

### 1. Copiez les fichiers sur votre Raspberry Pi
```bash
# Depuis votre machine de développement
scp auto_configure_printer.sh admin@raspberrypi:~/PrintServer/
scp printer-setup.service admin@raspberrypi:~/PrintServer/
```

### 2. Rendez le script exécutable
```bash
chmod +x ~/PrintServer/auto_configure_printer.sh
```

### 3. Installez le service automatique
```bash
sudo cp ~/PrintServer/printer-setup.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable printer-setup.service
```

### 4. Premier test manuel (optionnel)
```bash
sudo ~/PrintServer/auto_configure_printer.sh
```

## 🔄 Comment ça fonctionne

### Au démarrage du système :
1. **Vérification CUPS** : Installe CUPS si nécessaire
2. **Vérification pycups** : Installe le module Python dans le venv
3. **Configuration CUPS** : Active l'accès réseau et démarre le service
4. **Détection imprimante** : Trouve automatiquement l'USB Brother QL-700
5. **Configuration optimisée** : Applique les options Brother de qualité

### Logs de suivi :
```bash
# Voir les logs du service
journalctl -u printer-setup -f

# Voir les logs du script dans
tail -f /var/log/printer_setup.log
```

## 🔄 Fonctionnalités Avancées

### Rotation Automatique des Images
- ✅ **Détection automatique** : portrait vs paysage
- ✅ **Rotation 90°** des images portrait
- ✅ **Optimisation Brother** : utilise les bonnes options CUPS

**Comment ça marche :**
```python
# Le code détecte automatiquement l'orientation
orientation = detect_image_orientation(image_path)
if orientation == "portrait":
    options["orientation-requested"] = "4"  # 90° clockwise
```

### Test de Rotation
```bash
# Tester la détection d'orientation
python3 test_rotation.py
```

## 🎛️ Configuration Manuelle (Si nécessaire)

Si l'auto-configuration ne fonctionne pas :

```bash
# Arrêter le service automatique
sudo systemctl disable printer-setup.service

# Configuration manuelle étape par étape
sudo apt update
sudo apt install cups printer-driver-ptouch libcups2-dev

# Installation pycups dans le venv
source ~/PrintServer/venv/bin/activate
pip install pycups
deactivate

# Configuration CUPS
sudo systemctl start cups
sudo systemctl enable cups
sudo cupsctl --remote-any

# Ajout imprimante
sudo lpadmin -p "Brother_QL-700" -E \
  -v "usb://Brother/QL-700?serial=000H7Z771314" \
  -m "brother-ql-700.ppd"

# Options optimisées
sudo lpoptions -p "Brother_QL-700" \
  -o PageSize=62x29mm \
  -o BrPriority=BrQuality \
  -o BrBrightness=7 \
  -o BrCutAtEnd=ON
```

## ✅ Vérification

```bash
# Vérifier l'état
lpstat -p Brother_QL-700
lpq -P Brother_QL-700

# Tester pycups
~/PrintServer/venv/bin/python3 -c "import cups; print('✅ CUPS OK')"

# Redémarrer le service PrintServer
sudo systemctl restart printserver
```

## 🎉 Résultat

Après installation :
- ✅ **Configuration automatique** au démarrage
- ✅ **CUPS + pycups** fonctionnels
- ✅ **Imprimante Brother** configurée avec options optimisées
- ✅ **PrintServer** utilisant CUPS exclusivement
- ✅ **Plus de gestion manuelle** du refroidissement
- ✅ **Rotation automatique** des images portrait à 90°

## 🔧 Dépannage

- **pycups ne s'installe pas** : `sudo apt install libcups2-dev` puis réessayer
- **Imprimante non trouvée** : Vérifier USB avec `lsusb | grep Brother`
- **Service qui échoue** : `journalctl -u printer-setup -n 50`

---

**Votre système d'impression est maintenant entièrement automatisé !** 🎊
