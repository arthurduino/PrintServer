// Initialisation de la page création tâche
document.addEventListener('DOMContentLoaded', () => {
    console.log('Page création tâche chargée');
    loadProducts();
    checkProductParameter();
});



// Gestionnaire pour la sélection de produit
document.getElementById('select-product').addEventListener('change', handleProductChange);

// Fonction pour charger la liste des produits dans le select
async function loadProducts() {
    try {
        const response = await fetch('/api/products');
        const products = await response.json();

        const select = document.getElementById('select-product');
        // Garder seulement l'option par défaut
        select.innerHTML = '<option value="">Sélectionner un produit existant...</option>';

        products.forEach(product => {
            const option = document.createElement('option');
            option.value = product.id;
            option.textContent = `${product.nom} (${product.format_type}mm - ${product.rotation}°)`;
            option.dataset.product = JSON.stringify(product);
            select.appendChild(option);
        });

        console.log(`${products.length} produits chargés`);
    } catch (error) {
        console.error('Erreur lors du chargement des produits:', error);
    }
}

// Fonction pour vérifier si un produit est passé en paramètre URL
function checkProductParameter() {
    const urlParams = new URLSearchParams(window.location.search);
    const productId = urlParams.get('product');

    if (productId) {
        console.log('Produit spécifié dans l\'URL:', productId);
        // Attendre que les produits soient chargés puis sélectionner
        setTimeout(() => {
            const select = document.getElementById('select-product');
            select.value = productId;
            handleProductChange.call(select);
        }, 500);
    }
}

// Fonction pour gérer le changement de sélection de produit
function handleProductChange() {
    const selectedOption = this.options[this.selectedIndex];
    const productPreview = document.getElementById('product-preview');
    const customImageSection = document.getElementById('custom-image-section');
    const fileInput = document.getElementById('files');
    const labelTypeSelect = document.getElementById('label_type');
    const rotateSelect = document.getElementById('rotate');

    if (this.value) {
        // Un produit est sélectionné
        const productData = JSON.parse(selectedOption.dataset.product);

        // Afficher la prévisualisation
        document.getElementById('preview-image').src = `/uploads/${productData.image_path}`;
        document.getElementById('preview-image').style.transform = `rotate(${productData.rotation}deg)`;
        document.getElementById('preview-name').textContent = productData.nom;
        document.getElementById('preview-format').textContent = `${productData.format_type}mm - ${productData.rotation}°`;
        document.getElementById('preview-description').textContent = productData.description || 'Aucune description';

        productPreview.style.display = 'block';

        // Masquer/cacher la section image personnalisée et rendre certains champs non obligatoires
        customImageSection.style.display = 'none';
        fileInput.required = false;
        labelTypeSelect.required = false;
        labelTypeSelect.value = '';
        rotateSelect.required = false;
        rotateSelect.value = '';

        console.log('Produit sélectionné:', productData.nom);
    } else {
        // Aucun produit sélectionné
        productPreview.style.display = 'none';

        // Afficher la section image personnalisée et rendre les champs obligatoires
        customImageSection.style.display = 'flex';
        fileInput.required = true;
        labelTypeSelect.required = true;
        rotateSelect.required = true;

        console.log('Aucun produit sélectionné');
    }
}

// Gestion du formulaire de création de tâche (modifiée pour supporter les produits)
document.getElementById('job-form').addEventListener('submit', async (event) => {
    event.preventDefault();

    const formData = new FormData(event.target);
    const selectedProductId = document.getElementById('select-product').value;

    let files;
    let imagePath;

    if (selectedProductId) {
        // Utiliser un produit existant
        try {
            const response = await fetch(`/api/products/${selectedProductId}`);
            const product = await response.json();

            if (!response.ok) {
                showMessage('Erreur', 'Produit introuvable');
                return;
            }

            // Pour les produits existants, on utilise directement l'image du produit
            files = []; // Pas de fichiers à uploader
            imagePath = product.image_path;

            console.log('Utilisation du produit:', product.nom);
        } catch (error) {
            showMessage('Erreur', 'Erreur lors de la récupération du produit');
            return;
        }
    } else {
        // Utiliser une image personnalisée
        files = formData.getAll('files');

        if (files.length === 0) {
            showMessage('Erreur', 'Sélectionnez une image ou choisissez un produit');
            return;
        }

        imagePath = files[0].name;
    }

    // Créer la tâche
    const taskData = {
        nom_client: "Tâche simple",
        reference_externe: null,
        taches: [{
            type: "BATCH",
            quantite: parseInt(formData.get('quantity')) || 1,
            config: {
                image_path: imagePath,
                cut: formData.get('cut') === 'on',
                label_type: selectedProductId ? '' : (formData.get('label_type') || '62'), // Vide si produit, sinon valeur formulaire
                rotate: selectedProductId ? 0 : parseInt(formData.get('rotate') || '0'), // 0 si produit (rotation déjà appliquée), sinon valeur formulaire
                product_id: selectedProductId ? parseInt(selectedProductId) : null // ID du produit si utilisé
            }
        }]
    };

    const apiFormData = new FormData();
    apiFormData.append('command_json', JSON.stringify(taskData));
    files.forEach(file => apiFormData.append('files', file));

    // Désactiver le bouton pendant l'envoi
    const submitBtn = event.target.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = 'Création...';

    try {
        const response = await fetch('/api/jobs', {
            method: 'POST',
            body: apiFormData
        });

        const result = await response.json();

        if (response.ok) {
            showMessage('Succès', `Tâche créée (ID: ${result.job_id})`);
            event.target.reset();
            // Rafraîchir la page pour remettre à zéro le formulaire
            setTimeout(() => {
                window.location.href = '/new-task';
            }, 2000);
        } else {
            showMessage('Erreur', result.error || 'Erreur inconnue');
        }
    } catch (error) {
        showMessage('Erreur', 'Erreur réseau');
        console.error('Erreur réseau:', error);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Créer la tâche';
    }
});

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

console.log('Script create_task.js chargé');
