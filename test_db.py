#!/usr/bin/env python3
"""
Script pour initialiser la base de données et ajouter des produits de test
pour vérifier que la fonctionnalité de recherche fonctionne.
"""

import sys
import os

# Assurer que le répertoire courant est dans le PATH
sys.path.insert(0, os.path.abspath('.'))

from database import init_db, add_missing_columns_if_needed, create_product

def main():
    """Initialise la base de données et ajoute des produits de test."""
    print("🗄️ Initialisation de la base de données...")

    try:
        # Initialiser la base
        init_db()
        add_missing_columns_if_needed()

        print("✅ Base de données initialisée")

        # Créer quelques produits de test
        print("📦 Ajout de produits de test...")

        # Produit 1: Étq 62mm
        product1_id = create_product(
            nom="Étiquette Adresse 62mm",
            description="Étiquette d'adresse standard 62mm x 29mm",
            format_type="62",
            rotation=90,
            image_path="sample_address_62mm.png"
        )
        print(f"✅ Produit créé: ID {product1_id}")

        # Produit 2: Étq 29mm
        product2_id = create_product(
            nom="Étiquette Contact 29mm",
            description="Petite étiquette de contact 29mm x 29mm",
            format_type="29",
            rotation=0,
            image_path="sample_contact_29mm.png"
        )
        print(f"✅ Produit créé: ID {product2_id}")

        # Produit 3: Étq 12mm
        product3_id = create_product(
            nom="Étiquette Produit 12mm",
            description="Mini-étiquette pour produit 12mm x 53mm",
            format_type="12",
            rotation=90,
            image_path="sample_product_12mm.png"
        )
        print(f"✅ Produit créé: ID {product3_id}")

        # Produit 4: Avec "d" dans le nom pour tester la recherche
        product4_id = create_product(
            nom="Décoratif Deluxe",
            description="Étiquette décorative de luxe",
            format_type="62",
            rotation=90,
            image_path="sample_decorative.png"
        )
        print(f"✅ Produit créé: ID {product4_id}")

        # Produit 5: Avec "d" dans la description
        product5_id = create_product(
            nom="Standard XL",
            description="Étiquette standard extra large pour paquets",
            format_type="102",
            rotation=0,
            image_path="sample_xl.png"
        )
        print(f"✅ Produit créé: ID {product5_id}")

        print(f"\n🎉 Base de données prête avec {5} produits de test!")
        print("🧪 Vous pouvez maintenant tester la recherche de produits dans l'interface commandes")

    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation: {e}")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())
