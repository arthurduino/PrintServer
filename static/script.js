// Initialisation immédiate comme les autres pages
console.log('Homepage script loaded');

document.addEventListener('DOMContentLoaded', () => {
    console.log('Homepage DOM loaded, initializing interface...');
    loadInitialData();
});

async function loadInitialData() {
    console.log('Loading initial data...');
    try {
        // Charger les données statiques immédiatement
        await updatePrinterStatusFromAPI();
        await updateJobsFromAPI();

        // Démarrer les mises à jour périodiques
        startPeriodicUpdates();
    } catch (error) {
        console.error('Error loading initial data:', error);
    }
}

function startPeriodicUpdates() {
    console.log('Starting periodic updates');
    setInterval(async () => {
        try {
            await updatePrinterStatusFromAPI();
            await updateJobsFromAPI();
        } catch (error) {
            console.error('Error in periodic update:', error);
        }
    }, 2000); // Toutes les 2 secondes au lieu de 1-3
}

// Fonctions séparées pour les appels API
async function updatePrinterStatusFromAPI() {
    try {
        console.log('Fetching printer status...');
        const response = await fetch('/api/printer/status');
        if (response.ok) {
            const statusData = await response.json();
            console.log('Printer status:', statusData);
            updatePrinterStatus(statusData);
        } else {
            console.warn('Printer status API failed:', response.status);
        }
    } catch (error) {
        console.error('Error fetching printer status:', error);
    }
}

async function updateJobsFromAPI() {
    try {
        console.log('Fetching jobs...');
        const response = await fetch('/api/jobs');
        if (response.ok) {
            const jobs = await response.json();
            console.log('Jobs received:', jobs.length, 'total jobs');
            updateJobList(jobs);
        } else {
            console.warn('Jobs API failed:', response.status);
        }
    } catch (error) {
        console.error('Error fetching jobs:', error);
    }
}

// Statut de l'imprimante
function updatePrinterStatus(statusData) {
    const statusEl = document.getElementById('printer-status');

    let mainStatus = '❌ Déconnectée';
    let description = 'Imprimante non détectée';

    if (!statusData.is_error && statusData.status !== 'Disconnected') {
        switch (statusData.status) {
            case 'Ready':
                mainStatus = '🟢 Prêt';
                description = 'Imprimante opérationnelle';
                break;
            case 'Busy':
                mainStatus = '🔵 Impression en cours';
                description = 'Tâche active';
                break;
            case 'Cooling':
                mainStatus = '🟠 Refroidissement';
                description = 'Pause technique';
                break;
            case 'Cover Open':
                mainStatus = '🟡 Couvercle ouvert';
                description = 'Fermez le capot';
                break;
            case 'Paper Empty':
                mainStatus = '🟡 Papier épuisé';
                description = 'Recharge nécessaire';
                break;
        }
    }

    statusEl.innerHTML = `<div>${mainStatus}</div><div>${description}</div>`;
}

// File d'attente
function updateJobList(jobs) {
    const queueList = document.getElementById('job-list');
    const pendingTasks = [];

    // Traiter toutes les commandes (pas seulement celles en PENDING)
    jobs.forEach(job => {
        // Pour chaque tâche de chaque commande, vérifier si elle a encore du travail à faire
        job.taches.forEach(task => {
            if (task.quantite_faite < task.quantite_totale && task.statut !== 'DONE') {
                pendingTasks.push({
                    jobId: job.id,
                    clientName: job.nom_client,
                    taskId: task.id,
                    quantity: task.quantite_totale,
                    progress: task.quantite_faite || 0,
                    config: task.config
                });
            }
        });
    });

    queueList.innerHTML = pendingTasks.length === 0 ?
        '<p>File vide</p>' :
        pendingTasks.map(task => createTaskHTML(task)).join('');
}

// Affichage minimaliste des tâches
function createTaskHTML(task) {
    const clientName = task.clientName || 'Client';
    const progress = task.progress > 0 ? ` (${task.progress}/${task.quantity})` : '';

    let imagePart = '📄';
    if (task.config && task.config.image_path) {
        const filename = task.config.image_path.split('/').pop();
        imagePart = `<img src="/uploads/${filename}" style="width: 40px; height: 30px; object-fit: cover; border-radius: 3px;">`;
    }

    return `<div style="display: flex; align-items: center; padding: 10px; border: 1px solid #ddd; margin-bottom: 5px; border-radius: 5px; background: white;">
        <div style="width: 50px; text-align: center; margin-right: 10px;">${imagePart}</div>
        <div style="flex: 1;">
            <div><strong>Tâche #${task.taskId}</strong> - ${clientName}</div>
            <div style="font-size: 0.9em; color: #666;">Quantité: ${task.quantity}${progress}</div>
        </div>
        <button onclick="deleteTask(${task.taskId})" style="background: #dc3545; color: white; border: none; width: 25px; height: 25px; border-radius: 50%; cursor: pointer; font-size: 14px;">×</button>
    </div>`;
}

// Suppression de tâche
async function deleteTask(taskId) {
    if (confirm(`Supprimer la tâche #${taskId} ?`)) {
        try {
            const response = await fetch(`/api/taches/${taskId}`, { method: 'DELETE' });
            if (response.ok) {
                location.reload();
            }
        } catch (error) {
            alert('Erreur réseau');
        }
    }
}
