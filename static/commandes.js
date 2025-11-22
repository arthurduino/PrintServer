// Gestionnaire pour la page Commandes
document.addEventListener('DOMContentLoaded', function() {
    // État global
    let availableProducts = [];
    let commandProducts = [];

    // Événements principaux
    document.getElementById('new-command-btn').addEventListener('click', showCommandModal);
    document.getElementById('cancel-btn').addEventListener('click', hideCommandModal);
    document.querySelector('.modal-close').addEventListener('click', hideCommandModal);
    document.getElementById('save-btn').addEventListener('click', saveCommand);

    // Recherche de produits
    document.getElementById('product-search').addEventListener('input', searchProducts);

    // Fermeture du modal en cliquant en dehors
    document.getElementById('command-modal').addEventListener('click', function(e) {
        if (e.target === this) {
            hideCommandModal();
        }
    });

    // Chargement initial
    loadCommands();
    loadProducts();

    // Mise à jour périodique des commandes
    setInterval(loadCommands, 5000);
});

// Chargement des commandes
async function loadCommands() {
    try {
        const response = await fetch('/api/jobs');
        const commands = await response.json();

        const container = document.getElementById('commands-list');
        if (commands.length === 0) {
            container.innerHTML = '<p>Aucune commande trouvée</p>';
            return;
        }

        const html = commands.map(cmd => `
            <div class="command-card">
                <div class="command-header">
                    <h4>Commande #${cmd.id}</h4>
                    <span class="command-status status-${cmd.statut.toLowerCase()}">${cmd.statut}</span>
                </div>
                <div class="command-info">
                    <p><strong>Client:</strong> ${cmd.nom_client}</p>
                    ${cmd.reference_externe ? `<p><strong>Référence:</strong> ${cmd.reference_externe}</p>` : ''}
                    <p><strong>Date:</strong> ${new Date(cmd.date_creation).toLocaleDateString('fr-FR')}</p>
                    <p><strong>Tâches:</strong> ${cmd.taches.length} (${getCommandProgress(cmd.taches)})</p>
                </div>
                <div class="command-actions">
                    <button onclick="viewCommandDetails(${cmd.id})" class="btn btn-secondary btn-small">Détails</button>
                    ${cmd.statut === 'PENDING' ? `<button onclick="cancelCommand(${cmd.id})" class="btn btn-danger btn-small">Annuler</button>` : ''}
                </div>
            </div>
        `).join('');

        container.innerHTML = html;
    } catch (error) {
        console.error('Erreur chargement commandes:', error);
        document.getElementById('commands-list').innerHTML = '<p>Erreur de chargement</p>';
    }
}

// Chargement des produits disponibles
async function loadProducts() {
    try {
        const response = await fetch('/api/products');
        availableProducts = await response.json();
        console.log('Produits chargés:', availableProducts.length);
    } catch (error) {
        console.error('Erreur chargement produits:', error);
    }
}

// Calcul de la progression d'une commande
function getCommandProgress(tasks) {
    if (tasks.length === 0) return '0%';

    const totalTasks = tasks.length;
    const completedTasks = tasks.filter(t => t.statut === 'DONE').length;

    return `${completedTasks}/${totalTasks} terminées`;
}

// Recherche de produits
function searchProducts(event) {
    const query = event.target.value.toLowerCase().trim();
    const resultsContainer = document.getElementById('product-search-results');

    if (query.length < 2) {
        resultsContainer.style.display = 'none';
        return;
    }

    const filteredProducts = availableProducts.filter(p =>
        p.nom.toLowerCase().includes(query) ||
        (p.description && p.description.toLowerCase().includes(query))
    );

    if (filteredProducts.length === 0) {
        resultsContainer.innerHTML = '<div class="search-result">Aucun produit trouvé</div>';
    } else {
        const html = filteredProducts.slice(0, 10).map(p => `
            <div class="search-result" onclick="selectProduct(${p.id})">
                <div class="search-result-image">
                    <img src="/uploads/${p.image_path}" alt="${p.nom}">
                </div>
                <div class="search-result-info">
                    <div class="search-result-name">${p.nom}</div>
                    <div class="search-result-details">${p.format_type}mm - Rotation ${p.rotation}°</div>
                    ${p.description ? `<div class="search-result-desc">${p.description}</div>` : ''}
                </div>
            </div>
        `).join('');
        resultsContainer.innerHTML = html;
    }

    resultsContainer.style.display = 'block';
}

// Sélection d'un produit depuis la recherche
function selectProduct(productId) {
    const product = availableProducts.find(p => p.id === productId);
    if (!product) return;

    // Vérifier si déjà ajouté
    if (commandProducts.find(p => p.id === productId)) {
        showMessage('Erreur', 'Ce produit est déjà dans la commande');
        return;
    }

    // Ajouter à la commande
    commandProducts.push({
        ...product,
        quantity: 1 // Quantité par défaut
    });

    // Masquer la recherche
    document.getElementById('product-search-results').style.display = 'none';
    document.getElementById('product-search').value = '';

    // Mettre à jour l'affichage
    updateCommandProducts();
}

// Mise à jour de l'affichage des produits de la commande
function updateCommandProducts() {
    const container = document.getElementById('command-products');

    if (commandProducts.length === 0) {
        container.innerHTML = '<p class="no-products">Aucun produit ajouté à la commande</p>';
        return;
    }

    const html = commandProducts.map((product, index) => `
        <div class="command-product-item">
            <div class="command-product-image">
                <img src="/uploads/${product.image_path}" alt="${product.nom}">
            </div>
            <div class="command-product-info">
                <h4>${product.nom}</h4>
                <p>${product.format_type}mm - Rotation ${product.rotation}°</p>
                ${product.description ? `<p class="small-text">${product.description}</p>` : ''}
            </div>
            <div class="command-product-controls">
                <div class="quantity-control">
                    <button onclick="changeQuantity(${index}, -1)" class="qty-btn">-</button>
                    <input type="number" value="${product.quantity}" min="1" onchange="setQuantity(${index}, this.value)">
                    <button onclick="changeQuantity(${index}, 1)" class="qty-btn">+</button>
                </div>
                <button onclick="removeProduct(${index})" class="btn btn-danger btn-small">Supprimer</button>
            </div>
        </div>
    `).join('');

    container.innerHTML = html;
}

// Modification de quantité
function changeQuantity(index, delta) {
    const product = commandProducts[index];
    product.quantity = Math.max(1, product.quantity + delta);
    updateCommandProducts();
}

function setQuantity(index, value) {
    const product = commandProducts[index];
    product.quantity = Math.max(1, parseInt(value) || 1);
    updateCommandProducts();
}

// Suppression d'un produit
function removeProduct(index) {
    commandProducts.splice(index, 1);
    updateCommandProducts();
}

// Affichage du modal de commande
function showCommandModal() {
    commandProducts = []; // Reset
    updateCommandProducts();

    document.getElementById('nom_client').value = '';
    document.getElementById('reference_externe').value = '';
    document.getElementById('product-search').value = '';

    document.getElementById('modal-title').textContent = 'Nouvelle commande';
    document.getElementById('save-btn').textContent = 'Créer la commande';

    document.getElementById('command-modal').style.display = 'block';
}

// Masquage du modal de commande
function hideCommandModal() {
    document.getElementById('command-modal').style.display = 'none';
}

// Sauvegarde de la commande
async function saveCommand() {
    const nomClient = document.getElementById('nom_client').value.trim();
    const referenceExterne = document.getElementById('reference_externe').value.trim();

    if (!nomClient) {
        showMessage('Erreur', 'Veuillez saisir le nom du client');
        return;
    }

    if (commandProducts.length === 0) {
        showMessage('Erreur', 'Veuillez ajouter au moins un produit à la commande');
        return;
    }

    // Préparer les données
    const commandData = {
        nom_client: nomClient,
        reference_externe: referenceExterne || null,
        taches: commandProducts.map(product => ({
            type: "BATCH",
            quantite: product.quantity,
            config: {
                product_id: product.id,
                label_type: product.format_type,
                rotate: product.rotation.toString()
            }
        }))
    };

    document.getElementById('save-btn').disabled = true;
    document.getElementById('save-btn').textContent = 'Création...';

    try {
        const response = await fetch('/api/jobs', {
            method: 'POST',
            body: new FormData() // Vide car on utilise des produits existants
        });

        // On doit simuler l'appel existant qui utilise FormData
        const formData = new FormData();
        formData.append('command_json', JSON.stringify(commandData));

        const response2 = await fetch('/api/jobs', {
            method: 'POST',
            body: formData
        });

        const result = await response2.json();

        if (response2.ok) {
            showMessage('Succès', `Commande créée (ID: ${result.job_id})`);
            hideCommandModal();
            loadCommands();
        } else {
            showMessage('Erreur', result.error || 'Erreur inconnue');
        }
    } catch (error) {
        showMessage('Erreur', 'Erreur réseau');
    } finally {
        document.getElementById('save-btn').disabled = false;
        document.getElementById('save-btn').textContent = 'Créer la commande';
    }
}

// Affichage des détails d'une commande
function viewCommandDetails(commandId) {
    // TODO: Implémenter la vue détaillée
    showMessage('Info', 'Vue détaillée non implémentée');
}

// Annulation d'une commande
async function cancelCommand(commandId) {
    if (!confirm('Êtes-vous sûr de vouloir annuler cette commande ?')) {
        return;
    }

    try {
        // TODO: Implémenter l'annulation
        showMessage('Info', 'Annulation non implémentée');
    } catch (error) {
        showMessage('Erreur', 'Erreur lors de l\'annulation');
    }
}

// Message overlay (fonction partagée)
function showMessage(title, message) {
    const overlay = document.getElementById('message-overlay');
    document.getElementById('message-title').textContent = title;
    document.getElementById('message-text').textContent = message;
    overlay.style.display = 'flex';

    document.getElementById('message-close').addEventListener('click', () => {
        overlay.style.display = 'none';
    });
}
