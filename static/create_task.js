// App style Vue.js pour création de tâche
class CreateTaskApp {
    constructor() {
        this.data = {
            products: [],
            selectedProduct: null,
            loading: false
        };
        this.init();
    }

    init() {
        console.log('🚀 Initialisation CreateTaskApp (style Vue.js)');
        this.bindEvents();
        this.loadProducts();
        this.checkProductParameter();
    }

    // Réactivité simple inspirée de Vue
    setData(key, value) {
        this.data[key] = value;
        this.updateUI();
    }

    updateUI() {
        if (this.data.selectedProduct) {
            this.showProductPreview();
        } else {
            this.hideProductPreview();
        }
    }

    bindEvents() {
        document.getElementById('select-product').addEventListener('change', (e) => {
            this.handleProductSelection(e.target.value);
        });
    }

    async loadProducts() {
        try {
            this.setData('loading', true);
            const response = await fetch('/api/products');
            const products = await response.json();

            this.setData('products', products);
            this.renderProductOptions();
            console.log(`📦 ${products.length} produits chargés`);
        } catch (error) {
            console.error('❌ Erreur chargement produits:', error);
            this.showError('Erreur lors du chargement des produits');
        } finally {
            this.setData('loading', false);
        }
    }

    renderProductOptions() {
        const select = document.getElementById('select-product');
        select.innerHTML = '<option value="">Choisir un produit...</option>';

        this.data.products.forEach(product => {
            const option = document.createElement('option');
            option.value = product.id;
            option.textContent = `${product.nom} (${product.format_type}mm - ${product.rotation}°)`;
            option.dataset.product = JSON.stringify(product);
            select.appendChild(option);
        });
    }

    checkProductParameter() {
        const urlParams = new URLSearchParams(window.location.search);
        const productId = urlParams.get('product');

        if (productId) {
            console.log('🔗 Produit spécifié dans l\'URL:', productId);
            setTimeout(() => {
                document.getElementById('select-product').value = productId;
                this.handleProductSelection(productId);
            }, 300);
        }
    }

    handleProductSelection(productId) {
        if (productId) {
            const product = this.data.products.find(p => p.id == productId);
            if (product) {
                this.setData('selectedProduct', product);
                console.log('✅ Produit sélectionné:', product.nom);
                return;
            }
        }
        this.setData('selectedProduct', null);
    }

    showProductPreview() {
        const product = this.data.selectedProduct;
        if (!product) return;

        // Afficher la prévisualisation avec animation
        const productPreviewRow = document.getElementById('product-preview-row');
        productPreviewRow.style.display = 'block';
        productPreviewRow.classList.add('fade-in');

        // Mettre à jour les données
        document.getElementById('preview-image').src = `/uploads/${product.image_path}`;
        document.getElementById('preview-image').style.transform = `rotate(${product.rotation}deg)`;
        document.getElementById('preview-name').textContent = product.nom;
        document.getElementById('preview-format').textContent = `${product.format_type}mm - ${product.rotation}°`;
        document.getElementById('preview-description').textContent = product.description || 'Aucune description';

        // Ajuster les champs du formulaire
        this.adjustFormFields(true);
    }

    hideProductPreview() {
        const productPreviewRow = document.getElementById('product-preview-row');
        productPreviewRow.style.display = 'none';
        this.adjustFormFields(false);
    }

    adjustFormFields(productSelected) {
        const customImageSection = document.getElementById('custom-image-section');
        const fileInput = document.getElementById('files');
        const labelTypeSelect = document.getElementById('label_type');
        const rotateSelect = document.getElementById('rotate');

        if (productSelected) {
            customImageSection.style.display = 'none';
            fileInput.required = false;
            labelTypeSelect.required = false;
            rotateSelect.required = false;
        } else {
            customImageSection.style.display = 'flex';
            fileInput.required = true;
            labelTypeSelect.required = true;
            rotateSelect.required = true;
        }
    }

    showError(message) {
        console.error('❌', message);
        alert(message);
    }
}

// Gestionnaire de formulaire
document.getElementById('job-form').addEventListener('submit', async (event) => {
    event.preventDefault();

    const formData = new FormData(event.target);
    const selectedProductId = document.getElementById('select-product').value;

    let files, imagePath;

    if (selectedProductId) {
        const response = await fetch(`/api/products/${selectedProductId}`);
        const product = await response.json();

        if (!response.ok) {
            showMessage('Erreur', 'Produit introuvable');
            return;
        }

        files = [];
        imagePath = product.image_path;
        console.log('🔄 Utilisation produit:', product.nom);
    } else {
        files = formData.getAll('files');
        if (files.length === 0) {
            showMessage('Erreur', 'Sélectionnez une image ou choisissez un produit');
            return;
        }
        imagePath = files[0].name;
    }

    const taskData = {
        nom_client: "Tâche simple",
        reference_externe: null,
        taches: [{
            type: "BATCH",
            quantite: parseInt(formData.get('quantity')) || 1,
            config: {
                image_path: imagePath,
                cut: formData.get('cut') === 'on',
                label_type: selectedProductId ? '' : (formData.get('label_type') || '62'),
                rotate: selectedProductId ? 0 : parseInt(formData.get('rotate') || '0'),
                product_id: selectedProductId ? parseInt(selectedProductId) : null
            }
        }]
    };

    const apiFormData = new FormData();
    apiFormData.append('command_json', JSON.stringify(taskData));
    files.forEach(file => apiFormData.append('files', file));

    const submitBtn = event.target.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = '⏳ Création...';

    try {
        const response = await fetch('/api/jobs', {
            method: 'POST',
            body: apiFormData
        });

        const result = await response.json();

        if (response.ok) {
            showMessage('✅ Succès', `Tâche créée (ID: ${result.job_id})`);
            event.target.reset();
            setTimeout(() => window.location.href = '/new-task', 2000);
        } else {
            showMessage('❌ Erreur', result.error || 'Erreur inconnue');
        }
    } catch (error) {
        showMessage('❌ Erreur', 'Erreur réseau');
        console.error('❌ Erreur réseau:', error);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = '📄 Créer la tâche';
    }
});

// Fonctions utilitaires
function showMessage(title, message) {
    const overlay = document.getElementById('message-overlay');
    document.getElementById('message-title').textContent = title;
    document.getElementById('message-text').textContent = message;
    overlay.style.display = 'flex';
}

document.getElementById('message-close').addEventListener('click', () => {
    document.getElementById('message-overlay').style.display = 'none';
});

// Initialisation de l'application
const app = new CreateTaskApp();

console.log('📜 Script create_task.js chargé (style Vue.js)');
