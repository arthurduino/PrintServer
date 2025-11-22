// Variables globales pour la recherche de produits
let availableProducts = [];
let searchResults = []; // Pour la navigation clavier
let currentSearchIndex = -1;

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

        // Recherche de produits
        const searchInput = document.getElementById('product-search');
        searchInput.addEventListener('input', searchProducts);
        searchInput.addEventListener('keydown', handleSearchKeydown);

        // Ajouter les événements de sélection pour les résultats de recherche
        this.bindSearchEvents();
    }

    bindSearchEvents() {
        // Délégation d'événements pour les résultats de recherche
        document.addEventListener('click', (e) => {
            if (e.target.closest('.selectable-product')) {
                const productId = e.target.closest('.selectable-product').dataset.productId;
                if (productId) {
                    selectProduct(parseInt(productId));
                }
            }
        });
    }

    async loadProducts() {
        try {
            this.setData('loading', true);
            const response = await fetch('/api/products');
            const products = await response.json();

            // Stocker dans la variable globale pour la recherche
            availableProducts = products;

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
            option.textContent = `${product.nom} (${product.format_type}mm)`;
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
        document.getElementById('preview-image').style.transform = `rotate(0deg)`;
        document.getElementById('preview-name').textContent = product.nom;
        document.getElementById('preview-format').textContent = `${product.format_type}mm`;
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

        if (productSelected) {
            customImageSection.style.display = 'none';
            fileInput.required = false;
            labelTypeSelect.required = false;
        } else {
            customImageSection.style.display = 'flex';
            fileInput.required = true;
            labelTypeSelect.required = true;
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

    let files, imagePath, product;

    if (selectedProductId) {
        const response = await fetch(`/api/products/${selectedProductId}`);
        product = await response.json();

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
        nom_client: formData.get('client_name') || "Tâche simple",
        reference_externe: formData.get('reference') || null,
        taches: [{
            type: "BATCH",
            quantite: parseInt(formData.get('quantity')) || 1,
            config: {
                image_path: imagePath,
                cut: true,  // Toujours activée
                label_type: selectedProductId ? parseInt(product.format_type) : parseInt(formData.get('label_type') || '62'),
                rotate: 90,  // Toujours appliquer 90° de rotation
                product_id: selectedProductId ? parseInt(selectedProductId) : null
            }
        }]
    };

    const apiFormData = new FormData();
    const taskDataJson = JSON.stringify(taskData);
    apiFormData.append('command_json', taskDataJson);

    // Toujours ajouter au moins un champ files, même vide pour les produits existants
    if (files && files.length > 0) {
        files.forEach(file => apiFormData.append('files', file));
    } else {
        // Pour les produits existants, ajouter un champ vide mais existant
        apiFormData.append('files', new Blob(), '');
    }

    // Debug côté client
    console.log('📤 [CLIENT DEBUG] Envoi vers /api/jobs:');
    console.log('📤 [CLIENT DEBUG] taskData:', taskData);
    console.log('📤 [CLIENT DEBUG] taskDataJson:', taskDataJson);
    console.log('📤 [CLIENT DEBUG] files count:', files.length);
    files.forEach((file, i) => {
        console.log(`📤 [CLIENT DEBUG] File ${i}: ${file.name}, size: ${file.size} bytes`);
    });

    const submitBtn = event.target.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = '⏳ Création...';

    try {
        const response = await fetch('/api/jobs', {
            method: 'POST',
            body: apiFormData
        });

        const result = await response.json();

        console.log('📥 [CLIENT DEBUG] Réponse HTTP:', response.status, response.statusText);
        console.log('📥 [CLIENT DEBUG] Réponse body:', result);

        if (response.ok) {
            showMessage('✅ Succès', `Tâche créée (ID: ${result.job_id})`);
            event.target.reset();
            setTimeout(() => window.location.href = '/new-task', 2000);
        } else {
            showMessage('❌ Erreur', result.error || 'Erreur inconnue');
            console.error('❌ [CLIENT DEBUG] Erreur détaillée:', result);
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

// Recherche de produits
function searchProducts(event) {
    const query = event.target.value.trim();
    const resultsContainer = document.getElementById('product-search-results');

    console.log('Recherche lancée avec query:', query);

    // Vérifier si les produits sont chargés
    if (!availableProducts || availableProducts.length === 0) {
        console.warn('Aucun produit chargé pour la recherche');
        resultsContainer.innerHTML = '<div class="search-result">Chargement des produits...</div>';
        resultsContainer.style.display = 'block';
        return;
    }

    // Recherche améliorée : commence après 1 caractère, plus flexible
    if (query.length < 1) {
        resultsContainer.style.display = 'none';
        return;
    }

    const queryLower = query.toLowerCase();
    console.log('Query normalisée:', queryLower);

    const filteredProducts = availableProducts.filter(p => {
        const nomLower = (p.nom || '').toLowerCase();
        const descLower = (p.description || '').toLowerCase();

        // Recherche flexible : contient la chaîne OU commence par la chaîne
        const matches = nomLower.includes(queryLower) ||
                       nomLower.startsWith(queryLower) ||
                       descLower.includes(queryLower);

        if (matches) {
            console.log('Produit trouvé:', { id: p.id, nom: p.nom, nomLower, matches: { contains: nomLower.includes(queryLower), startsWith: nomLower.startsWith(queryLower), descContains: descLower.includes(queryLower) } });
        }

        return matches;
    });

    console.log('Nombre de produits filtrés:', filteredProducts.length);

    if (filteredProducts.length === 0) {
        resultsContainer.innerHTML = '<div class="search-result">Aucun produit trouvé</div>';
    } else {
        // Stocker les résultats pour la navigation clavier
        searchResults = filteredProducts.slice(0, 10);
        currentSearchIndex = -1;

        const html = searchResults.map((p, index) => `
            <div class="search-result selectable-product" data-search-index="${index}" data-product-id="${p.id}">
                <div class="search-result-content" onclick="selectProduct(${p.id})">
                    <div class="search-result-image">
                        <img src="/uploads/${p.image_path}" alt="${p.nom}"
                             onerror="this.onerror=null; this.style.display='none'; this.parentNode.innerHTML='<div class=\\'no-image\\'>📋</div>'">
                    </div>
                    <div class="search-result-info">
                        <div class="search-result-name">${p.nom}</div>
                        <div class="search-result-details">${p.format_type}mm</div>
                        ${p.description ? `<div class="search-result-desc">${p.description}</div>` : ''}
                    </div>
                </div>
                <div class="search-result-actions">
                    <button type="button" onclick="selectProduct(${p.id})" class="btn btn-primary btn-small">
                        ✓ Sélectionner
                    </button>
                </div>
        `).join('');
        resultsContainer.innerHTML = html;
    }

    resultsContainer.style.display = 'block';
}

// Sélection d'un produit depuis la recherche (adapté pour la page tâche)
function selectProduct(productId) {
    const product = availableProducts.find(p => p.id === productId);
    if (!product) return;

    // Sélectionner dans le dropdown caché
    document.getElementById('select-product').value = productId;

    // Déclencher la sélection via l'app
    app.handleProductSelection(productId);

    // Masquer la recherche et remplir le champ de recherche
    document.getElementById('product-search-results').style.display = 'none';
    document.getElementById('product-search').value = product.nom;

    console.log('Produit sélectionné via recherche:', product.nom);
}

// Navigation clavier pour la recherche de produits
function handleSearchKeydown(event) {
    const resultsContainer = document.getElementById('product-search-results');
    const isVisible = resultsContainer.style.display !== 'none';

    if (!isVisible || searchResults.length === 0) return;

    const key = event.key;

    // Supprimer la mise en évidence précédente
    const currentHighlighted = resultsContainer.querySelector('.search-result.highlighted');
    if (currentHighlighted) {
        currentHighlighted.classList.remove('highlighted');
    }

    if (key === 'ArrowDown') {
        event.preventDefault();
        currentSearchIndex = Math.min(currentSearchIndex + 1, searchResults.length - 1);
    } else if (key === 'ArrowUp') {
        event.preventDefault();
        currentSearchIndex = Math.max(currentSearchIndex - 1, 0);
    } else if (key === 'Enter') {
        event.preventDefault();
        if (currentSearchIndex >= 0 && currentSearchIndex < searchResults.length) {
            const selectedProduct = searchResults[currentSearchIndex];
            selectProduct(selectedProduct.id);
        }
        return;
    } else if (key === 'Escape') {
        event.preventDefault();
        resultsContainer.style.display = 'none';
        return;
    }

    // Mettre en évidence le résultat actuel
    if (currentSearchIndex >= 0) {
        const currentElement = resultsContainer.querySelector(`[data-search-index="${currentSearchIndex}"]`);
        if (currentElement) {
            currentElement.classList.add('highlighted');
            currentElement.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }
    }
}

// Initialisation de l'application
const app = new CreateTaskApp();

console.log('📜 Script create_task.js chargé (style Vue.js)');
