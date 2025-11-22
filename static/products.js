// Configuration des formats d'étiquettes
const LABEL_CONFIGS = {
    '62': { width: 62, height: 29, name: '62mm' },
    '48': { width: 48, height: 25, name: '48mm' },
    '30': { width: 30, height: 21, name: '30mm' }
};

// Variables globales pour l'aperçu
let currentImage = null;
let currentFile = null;
let originalImageDimensions = null;

// Initialisation de la page produits
document.addEventListener('DOMContentLoaded', () => {
    console.log('Page produits chargée');
    updatePreview();
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
                    <img src="/uploads/${product.image_path}" alt="${product.nom}">
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

// Gestionnaire pour le changement d'image
document.getElementById('files').addEventListener('change', async (event) => {
    const file = event.target.files[0];

    if (!file) {
        currentImage = null;
        currentFile = null;
        updatePreview();
        return;
    }

    if (!file.type.startsWith('image/')) {
        showMessage('Erreur', 'Veuillez sélectionner un fichier image valide');
        return;
    }

    currentFile = file;

    // Lire le fichier en tant que Data URL pour l'aperçu
    const reader = new FileReader();
    reader.onload = (e) => {
        currentImage = e.target.result;
        console.log('Image chargée, mise à jour de l\'aperçu produit');
        updatePreview();
    };
    reader.readAsDataURL(file);
});

// Gestionnaire pour le changement de format
document.getElementById('label_type').addEventListener('change', () => {
    if (currentImage) {
        console.log('Format changé, mise à jour de l\'aperçu produit');
        updatePreview();
    }
});

// Gestionnaire pour le changement de rotation
document.getElementById('rotate').addEventListener('change', () => {
    if (currentImage) {
        console.log('Rotation changée, mise à jour de l\'aperçu produit');
        updatePreview();
    }
});

// Fonction principale pour mettre à jour l'aperçu
function updatePreview() {
    const previewCanvas = document.getElementById('preview-canvas');
    const formatSelect = document.getElementById('label_type');
    const rotateSelect = document.getElementById('rotate');

    // Nettoyer le canvas
    previewCanvas.innerHTML = '';

    if (!currentImage) {
        previewCanvas.innerHTML = '<div class="preview-placeholder"><span>Sélectionnez une image pour voir l\'aperçu</span></div>';
        updateDimensionInfo('--', '--', '0');
        return;
    }

    // Créer une image temporaire pour obtenir les dimensions naturelles
    const tempImg = new Image();
    tempImg.onload = function() {
        console.log('Dimensions originales:', tempImg.naturalWidth, 'x', tempImg.naturalHeight);

        // Stocker les dimensions naturelles
        originalImageDimensions = {
            width: tempImg.naturalWidth,
            height: tempImg.naturalHeight
        };

        // Calculer les dimensions en millimètres - hauteur toujours = format sélectionné
        const formatValue = parseInt(formatSelect.value);
        const heightMm = formatValue; // Hauteur fixe selon le format
        const widthMm = (tempImg.naturalWidth / tempImg.naturalHeight) * heightMm; // Largeur proportionnelle

        console.log('Dimensions calculées:', widthMm.toFixed(1), 'x', heightMm, 'mm');

        // Créer et ajouter l'image à l'aperçu AVEC rotation appliquée visuellement
        const imgElement = document.createElement('img');
        imgElement.src = currentImage;
        imgElement.className = 'preview-image';

        // Appliquer la rotation visuellement dans l'aperçu
        const currentRotation = parseInt(rotateSelect.value) || 0;
        imgElement.style.transform = `rotate(${currentRotation}deg)`;

        // Calculer la taille d'affichage avec les dimensions physiques réelles
        const canvasWidth = 380;
        const canvasHeight = 280;

        // Dimensions d'affichage en pixels (conversion mm vers pixels à 300 DPI)
        const displayWidthPx = widthMm * (300 / 25.4);
        const displayHeightPx = heightMm * (300 / 25.4);

        // Calculer l'échelle pour adapter au canvas
        const scaleX = canvasWidth / displayWidthPx;
        const scaleY = canvasHeight / displayHeightPx;
        const scale = Math.min(scaleX, scaleY, 1);

        imgElement.style.width = (displayWidthPx * scale) + 'px';
        imgElement.style.height = (displayHeightPx * scale) + 'px';
        imgElement.style.maxWidth = '100%';
        imgElement.style.maxHeight = '100%';

        previewCanvas.appendChild(imgElement);

        // Mettre à jour les informations de dimension
        updateDimensionInfo(widthMm, heightMm, currentRotation.toString());
    };

    tempImg.src = currentImage;
}

// Fonction pour mettre à jour les informations de dimensions
function updateDimensionInfo(widthMm, heightMm, rotation) {
    const formatSelect = document.getElementById('label_type');

    if (widthMm === '--' || heightMm === '--') {
        document.getElementById('current-format').textContent = 'Format: --mm';
        document.getElementById('rotation-info').textContent = 'Rotation: 0°';
        document.getElementById('actual-size').textContent = 'Taille réelle: -- x -- mm';
        return;
    }

    // Trouver le format actuel sélectionné
    const labelConfig = LABEL_CONFIGS[formatSelect.value];

    document.getElementById('current-format').textContent = `Format: ${labelConfig.name}`;
    document.getElementById('rotation-info').textContent = `Rotation: ${rotation}°`;

    // Pour l'affichage, tenir compte de la rotation
    const isRotated = parseInt(rotation) === 90 || parseInt(rotation) === 270;
    const displayWidth = isRotated ? parseFloat(heightMm) : parseFloat(widthMm);
    const displayHeight = isRotated ? parseFloat(widthMm) : parseFloat(heightMm);

    document.getElementById('actual-size').textContent = `Taille réelle: ${displayWidth.toFixed(1)} x ${displayHeight.toFixed(1)} mm`;
}

// Gestionnaire pour fermer le message
document.getElementById('message-close').addEventListener('click', () => {
    document.getElementById('message-overlay').style.display = 'none';
});

console.log('Script products.js chargé');
