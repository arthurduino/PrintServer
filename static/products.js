// App style Vue.js pour la gestion des produits
class ProductApp {
    constructor() {
        this.data = {
            products: [],
            loading: false
        };
        this.init();
    }

    init() {
        console.log('🚀 Initialisation ProductApp (style Vue.js)');
        this.loadProducts();
        this.bindFormEvents();
    }

    // Réactivité simple inspirée de Vue
    setData(key, value) {
        this.data[key] = value;
        this.updateUI();
    }

    updateUI() {
        // Mise à jour automatique pour gérer les états de chargement
    }

    bindFormEvents() {
        document.getElementById('product-form').addEventListener('submit', async (event) => {
            event.preventDefault();
            console.log('📝 Soumission formulaire produit');

            const formData = new FormData(event.target);
            const file = formData.get('files');

            if (!file) {
                this.showMessage('❌ Erreur', 'Veuillez sélectionner une image');
                return;
            }

            // Créer le produit
            const productData = {
                nom: formData.get('nom'),
                description: formData.get('description') || null,
                format_type: formData.get('label_type'),
                rotation: 90 // Toujours appliquer une rotation de 90° par rapport au fichier original
            };

            const apiFormData = new FormData();
            apiFormData.append('product_json', JSON.stringify(productData));
            apiFormData.append('file', file);

            const submitBtn = event.target.querySelector('button[type="submit"]');
            submitBtn.disabled = true;
            submitBtn.textContent = '⏳ Création...';

            try {
                const response = await fetch('/api/products', {
                    method: 'POST',
                    body: apiFormData
                });

                const result = await response.json();

                if (response.ok) {
                    this.showMessage('✅ Succès', `Produit "${result.product.nom}" créé avec succès !`);
                    event.target.reset();
                    this.loadProducts();
                } else {
                    this.showMessage('❌ Erreur', result.error || 'Erreur inconnue');
                }
            } catch (error) {
                this.showMessage('❌ Erreur', 'Erreur réseau');
                console.error('❌ Erreur réseau:', error);
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = '📦 Créer le produit';
            }
        });
    }

    async loadProducts() {
        try {
            this.setData('loading', true);
            const response = await fetch('/api/products');
            const products = await response.json();

            this.setData('products', products);
            this.renderProducts();

            console.log(`📦 ${products.length} produits chargés`);
        } catch (error) {
            console.error('❌ Erreur chargement produits:', error);
            this.showError('Erreur lors du chargement des produits');
        } finally {
            this.setData('loading', false);
        }
    }

    renderProducts() {
        const productsList = document.getElementById('products-list');
        productsList.innerHTML = '';

        if (this.data.products.length === 0) {
            productsList.innerHTML = '<div style="text-align: center; padding: 40px; color: #6b7280;">Aucun produit enregistré pour le moment.</div>';
            return;
        }

        this.data.products.forEach(product => {
            const productCard = document.createElement('div');
            productCard.className = 'product-card';
            productCard.innerHTML = `
                <div class="product-image">
                    <img src="/uploads/${product.image_path}" alt="${product.nom}" style="transform: rotate(0deg);">
                </div>
                <div class="product-info">
                    <h3>${product.nom}</h3>
                    <p class="product-format">${product.format_type}mm</p>
                    ${product.description ? `<p class="product-description">${product.description}</p>` : ''}
                </div>
                <div class="product-actions">
                    <button onclick="app.useProduct(${product.id})" class="btn btn-secondary btn-card">🔄 Utiliser</button>
                    <button onclick="app.deleteProduct(${product.id})" class="btn btn-danger btn-card">🗑️ Supprimer</button>
                </div>
            `;
            productsList.appendChild(productCard);
        });
    }

    useProduct(productId) {
        window.location.href = `/new-task?product=${productId}`;
    }

    async deleteProduct(productId) {
        if (!confirm('Êtes-vous sûr de vouloir supprimer ce produit ?')) {
            return;
        }

        try {
            const response = await fetch(`/api/products/${productId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                this.showMessage('✅ Succès', 'Produit supprimé');
                this.loadProducts();
            } else {
                const result = await response.json();
                this.showMessage('❌ Erreur', result.error || 'Erreur lors de la suppression');
            }
        } catch (error) {
            this.showMessage('❌ Erreur', 'Erreur réseau');
            console.error('❌ Erreur réseau:', error);
        }
    }

    showMessage(title, message) {
        const overlay = document.getElementById('message-overlay');
        document.getElementById('message-title').textContent = title;
        document.getElementById('message-text').textContent = message;
        overlay.style.display = 'flex';
    }

    showError(message) {
        console.error('❌', message);
        alert(message);
    }
}

// Initialisation de l'application
const app = new ProductApp();

// Fonctions globales pour les boutons (pour la compatibilité)
function useProduct(productId) {
    app.useProduct(productId);
}

function deleteProduct(productId) {
    app.deleteProduct(productId);
}

function showMessage(title, message) {
    app.showMessage(title, message);
}

document.getElementById('message-close').addEventListener('click', () => {
    document.getElementById('message-overlay').style.display = 'none';
});

console.log('📜 Script products.js chargé (style Vue.js)');
