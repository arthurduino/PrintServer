#!/bin/bash

# Installation des dépendances Python pour CUPS
echo "Installation de python3-cups (interface Python pour CUPS)..."
pip3 install pycups

# Vérification de l'installation
echo "Vérification de l'installation pycups..."
python3 -c "import cups; print('✅ pycups importé avec succès')"

echo "Installation terminée. Vous pouvez maintenant redémarrer le service PrintServer."
