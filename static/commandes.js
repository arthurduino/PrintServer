// État global pour les commandes
let availableProducts = [];
let commandProducts = [];

// Gestionnaire pour la page Commandes
document.addEventListener('DOMContentLoaded', function() {

    // Événements principaux
    document.getElementById('command-form').addEventListener('submit', handleCommandSubmit);

    // Recherche de produits
    document.getElementById('product-search').addEventListener('input', searchProducts);

    // Modal détails
    document.getElementById('close-details-btn').addEventListener('click', hideDetailsModal);
    document.getElementById('delete-command-btn').addEventListener('click', deleteSelectedCommand);

    // Fermeture du modal en cliquant sur la croix
    document.querySelectorAll('.modal-close').forEach(closeBtn => {
        closeBtn.addEventListener('click', function() {
            this.closest('.modal').style.display = 'none';
        });
    });

    // Fermeture du modal en cliquant en dehors
    document.getElementById('command-details-modal').addEventListener('click', function(e) {
        if (e.target === this) {
            hideDetailsModal();
        }
    });

    // Chargement initial
    loadCommands();
    loadProducts();
});

// Chargement des commandes
async function loadCommands() {
    try {
        const response = await fetch('/api/commandes');
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
                    ${cmd.statut === 'PENDING' ? `<button onclick="deleteCommand(${cmd.id})" class="btn btn-danger btn-small">Supprimer</button>` : ''}
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
        console.log('Exemples de produits:', availableProducts.slice(0, 3).map(p => ({ id: p.id, nom: p.nom, description: p.description })));
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

// Gestionnaire de soumission du formulaire de commande
async function handleCommandSubmit(event) {
    event.preventDefault();

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
                rotate: "90" // Toujours appliquer 90° de rotation
            }
        }))
    };

    document.querySelector('#command-form button[type="submit"]').disabled = true;
    document.querySelector('#command-form button[type="submit"]').textContent = 'Création...';

    try {
        const formData = new FormData();
        formData.append('command_json', JSON.stringify(commandData));

        const response = await fetch('/api/commandes', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (response.ok) {
            showMessage('Succès', `Commande créée (ID: ${result.job_id})`);
            // Reset le formulaire
            event.target.reset();
            commandProducts = [];
            updateCommandProducts();
            // Recharger la liste
            loadCommands();
        } else {
            showMessage('Erreur', result.error || 'Erreur inconnue');
        }
    } catch (error) {
        showMessage('Erreur', 'Erreur réseau');
    } finally {
        document.querySelector('#command-form button[type="submit"]').disabled = false;
        document.querySelector('#command-form button[type="submit"]').textContent = 'Créer la commande';
    }
}

// Recherche de produits
function searchProducts(event) {
    const query = event.target.value.trim();
    const resultsContainer = document.getElementById('product-search-results');

    console.log('Recherche lancée avec query:', query);

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
        const html = filteredProducts.slice(0, 10).map(p => `
            <div class="search-result selectable-product">
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
                        ➕ Ajouter à la commande
                    </button>
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
        quantity: 50 // Quantité par défaut
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
                <p>${product.format_type}mm</p>
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

// Vue détaillée d'une commande
async function viewCommandDetails(commandeId) {
    try {
        // Comme on a déjà les données dans loadCommands, on peut les récupérer
        // Mais pour plus de fraîcheur, on va les recharger depuis l'API
        const response = await fetch('/api/commandes');
        const commands = await response.json();
        const command = commands.find(c => c.id === commandeId);

        if (!command) {
            showMessage('Erreur', 'Commande non trouvée');
            return;
        }

        // Remplir les détails de la commande
        document.getElementById('details-command-id').textContent = command.id;
        document.getElementById('command-info-details').innerHTML = `
            <p><strong>Client:</strong> ${command.nom_client}</p>
            ${command.reference_externe ? `<p><strong>Référence:</strong> ${command.reference_externe}</p>` : ''}
            <p><strong>Date de création:</strong> ${new Date(command.date_creation).toLocaleString('fr-FR')}</p>
            <p><strong>Statut:</strong> <span class="command-status status-${command.statut.toLowerCase()}">${command.statut}</span></p>
            <p><strong>Nombre de tâches:</strong> ${command.taches.length}</p>
        `;

        // Lister les tâches
        const tasksHtml = command.taches.map(task => `
            <div class="task-item">
                <h5>Tâche #${task.id} - ${task.type_tache}</h5>
                <div class="task-details">
                    <p><strong>Quantité:</strong> ${task.quantite_faite}/${task.quantite_totale}</p>
                    <p><strong>Statut:</strong> <span class="command-status status-${task.statut.toLowerCase()}">${task.statut}</span></p>
                    <p><strong>Configuration:</strong> ${formatTaskConfig(task.config)}</p>
                </div>
            </div>
        `).join('');

        document.getElementById('command-tasks-list').innerHTML = tasksHtml;

        // Stocker l'ID de la commande sélectionnée pour la suppression
        document.getElementById('delete-command-btn').setAttribute('data-command-id', commandeId);

        // Afficher le modal
        document.getElementById('command-details-modal').style.display = 'block';

    } catch (error) {
        console.error('Erreur chargement détails:', error);
        showMessage('Erreur', 'Impossible de charger les détails de la commande');
    }
}

function formatTaskConfig(config) {
    if (!config) return 'N/A';

    if (config.product_id) {
        return `Produit #${config.product_id} (${config.label_type}mm)`;
    }

    return JSON.stringify(config).substring(0, 100) + '...';
}

// Masquage du modal de détails
function hideDetailsModal() {
    document.getElementById('command-details-modal').style.display = 'none';
}

// Suppression d'une commande
function deleteSelectedCommand() {
    const commandeId = document.getElementById('delete-command-btn').getAttribute('data-command-id');
    if (commandeId) {
        deleteCommand(commandeId);
    }
}

// Suppression d'une commande (fonction appelée depuis les boutons)
async function deleteCommand(commandeId) {
    if (!confirm('Êtes-vous sûr de vouloir supprimer cette commande ? Toutes les tâches associées seront aussi supprimées.')) {
        return;
    }

    try {
        const response = await fetch(`/api/commandes/${commandeId}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (response.ok) {
            showMessage('Succès', 'Commande supprimée');
            loadCommands(); // Recharger la liste
            hideDetailsModal(); // Fermer le modal si ouvert
        } else {
            showMessage('Erreur', result.error || 'Erreur lors de la suppression');
        }
    } catch (error) {
        showMessage('Erreur', 'Erreur réseau');
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
