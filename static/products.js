// Initialisation de la page produits
document.addEventListener('DOMContentLoaded', () => {
    console.log('Page produits chargée');
    loadProducts();
});

// Gestion du formulaire de création de produit
document.getElementById('product-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    console.log('Soumission du formulaire produit');

    const formData = new FormData(event.target);
    const file = formData.get('files');

    if (!file) {
        showMessage('Erreur', 'Veuillez sélectionner une image');
        return;
    }

    // Créer le produit
    const productData = {
        nom: formData.get('nom'),
        description: formData.get('description') || null,
        format_type: formData.get('label_type'),
        rotation: parseInt(formData.get('rotate')) || 0
    };

    const apiFormData = new FormData();
    apiFormData.append('product_json', JSON.stringify(productData));
    apiFormData.append('file', file);

    // Désactiver le bouton pendant l'envoi
    const submitBtn = event.target.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Création...';

    try {
        const response = await fetch('/api/products', {
            method: 'POST',
            body: apiFormData
        });

        const result = await response.json();

        if (response.ok) {
            showMessage('Succès', `Produit "${result.product.nom}" créé avec succès !`);
            event.target.reset();
            loadProducts();
            setTimeout(() => {
                // Pas de redirection pour rester sur la page produits
            }, 2000);
        } else {
            showMessage('Erreur', result.error || 'Erreur inconnue');
        }
    } catch (error) {
        showMessage('Erreur', 'Erreur réseau');
        console.error('Erreur réseau:', error);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Créer le produit';
    }
});

// Fonction pour charger la liste des produits
async function loadProducts() {
    try {
        const response = await fetch('/api/products');
        const products = await response.json();

        const productsList = document.getElementById('products-list');
        productsList.innerHTML = '';

        if (products.length === 0) {
            productsList.innerHTML = '<div style="text-align: center; padding: 40px; color: #6b7280;">Aucun produit enregistré pour le moment.</div>';
            return;
        }

        products.forEach(product => {
            const productCard = document.createElement('div');
            productCard.className = 'product-card';
            productCard.innerHTML = `
                <div class="product-image">
                    <img src="/uploads/${product.image_path}" alt="${product.nom}" style="transform: rotate(${product.rotation}deg);">
                </div>
                <div class="product-info">
                    <h3>${product.nom}</h3>
                    <p class="product-format">${product.format_type}mm - ${product.rotation}°</p>
                    ${product.description ? `<p class="product-description">${product.description}</p>` : ''}
                </div>
                <div class="product-actions">
                    <button onclick="useProduct(${product.id})" class="btn btn-secondary btn-card">Utiliser</button>
                    <button onclick="deleteProduct(${product.id})" class="btn btn-danger btn-card">Supprimer</button>
                </div>
            `;
            productsList.appendChild(productCard);
        });

    } catch (error) {
        console.error('Erreur lors du chargement des produits:', error);
        document.getElementById('products-list').innerHTML = '<div style="text-align: center; padding: 40px; color: #ef4444;">Erreur lors du chargement des produits.</div>';
    }
}

// Fonction pour utiliser un produit (redirige vers création de tâche avec le produit sélectionné)
function useProduct(productId) {
    window.location.href = `/new-task?product=${productId}`;
}

// Fonction pour supprimer un produit
async function deleteProduct(productId) {
    if (!confirm('Êtes-vous sûr de vouloir supprimer ce produit ?')) {
        return;
    }

    try {
        const response = await fetch(`/api/products/${productId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showMessage('Succès', 'Produit supprimé');
            loadProducts();
        } else {
            const result = await response.json();
            showMessage('Erreur', result.error || 'Erreur lors de la suppression');
        }
    } catch (error) {
        showMessage('Erreur', 'Erreur réseau');
        console.error('Erreur réseau:', error);
    }
}

// Fonction pour afficher les messages
function showMessage(title, message) {
    const overlay = document.getElementById('message-overlay');
    document.getElementById('message-title').textContent = title;
    document.getElementById('message-text').textContent = message;
    overlay.style.display = 'flex';
}

// Gestionnaire pour fermer le message
document.getElementById('message-close').addEventListener('click', () => {
    document.getElementById('message-overlay').style.display = 'none';
});

console.log('Script products.js chargé');
