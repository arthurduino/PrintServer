// Initialisation immédiate comme les autres pages
console.log('Homepage script loaded');

document.addEventListener('DOMContentLoaded', () => {
    console.log('Homepage DOM loaded, initializing interface...');
    loadInitialData();
    setupEventListeners();
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

// Mise à jour de la tâche en cours et de la file d'attente
function updateJobList(jobs) {
    const currentJobEl = document.getElementById('current-job');
    const queueList = document.getElementById('job-list');

    // Tâche en cours (PROCESSING)
    const processingJobs = jobs.filter(job => job.statut === 'PROCESSING');
    if (processingJobs.length > 0) {
        const currentJob = processingJobs[0]; // Première tâche en cours
        const currentTask = currentJob.taches.find(task => task.statut === 'IN_PROGRESS') || currentJob.taches[0];

        if (currentTask) {
            const progress = Math.round((currentTask.quantite_faite / currentTask.quantite_totale) * 100);
            const imageHtml = currentTask.config?.image_path ?
                `<img src="/uploads/${currentTask.config.image_path.split('/').pop()}" style="width: 60px; height: 40px; object-fit: cover; border-radius: 5px; margin-right: 15px;">` :
                '📄';

            currentJobEl.innerHTML = `
                <div style="display: flex; align-items: center; padding: 15px; border: 1px solid #28a745; background: #f8fff9; border-radius: 8px;">
                    ${imageHtml}
                    <div style="flex: 1;">
                        <div><strong>${currentJob.nom_client}</strong></div>
                        <div>Tâche #${currentTask.id} - ${currentTask.type_tache}</div>
                        <div style="margin-top: 5px;">
                            <div style="background: #e9ecef; border-radius: 10px; height: 10px; width: 200px;">
                                <div style="background: #28a745; height: 100%; border-radius: 10px; width: ${progress}%;"></div>
                            </div>
                            <div style="font-size: 0.9em; margin-top: 5px; color: #666;">
                                ${currentTask.quantite_faite}/${currentTask.quantite_totale} (${progress}%)
                            </div>
                        </div>
                    </div>
                </div>
            `;
        } else {
            currentJobEl.innerHTML = '<p>Aucune tâche en cours</p>';
        }
    } else {
        currentJobEl.innerHTML = '<p>Aucune tâche en cours</p>';
    }

    // File d'attente (PENDING)
    const pendingTasks = [];
    jobs.filter(job => job.statut === 'PENDING').forEach(job => {
        job.taches.forEach(task => {
            if (task.quantite_faite < task.quantite_totale) {
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

// Affichage amélioré des tâches avec plus de détails
function createTaskHTML(task) {
    const clientName = task.clientName || 'Client';
    const progress = task.progress > 0 ? ` (${task.progress}/${task.quantity})` : '';

    let imagePart = '📄';
    if (task.config && task.config.image_path) {
        const filename = task.config.image_path.split('/').pop();
        imagePart = `<img src="/uploads/${filename}" style="width: 40px; height: 30px; object-fit: cover; border-radius: 3px;">`;
    }

    // Informations supplémentaires
    let taskType = 'BATCH';
    let formatType = '';
    if (task.config) {
        taskType = task.config.type || 'BATCH';
        formatType = task.config.format_type ? ` - Format: ${task.config.format_type}` : '';
    }

    return `<div style="display: flex; align-items: center; padding: 12px; border: 1px solid #ddd; margin-bottom: 8px; border-radius: 8px; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
        <div style="width: 50px; text-align: center; margin-right: 12px;">${imagePart}</div>
        <div style="flex: 1;">
            <div style="display: flex; align-items: center; margin-bottom: 4px;">
                <strong>Tâche #${task.taskId}</strong>
                <span style="background: #007bff; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; margin-left: 8px;">${taskType}</span>
            </div>
            <div style="color: #333; margin-bottom: 2px;">${clientName}${formatType}</div>
            <div style="font-size: 0.9em; color: #666;">
                Quantité: ${task.quantity}${progress}
                ${task.config && task.config.dpi ? ` - DPI: ${task.config.dpi}` : ''}
            </div>
        </div>
        <div style="display: flex; gap: 5px;">
            <button onclick="deleteCommande(${task.jobId})" title="Supprimer la commande entière" style="background: #ffc107; color: black; border: none; width: 25px; height: 25px; border-radius: 50%; cursor: pointer; font-size: 14px;">🗑️</button>
            <button onclick="deleteTask(${task.taskId})" title="Supprimer cette tâche" style="background: #dc3545; color: white; border: none; width: 25px; height: 25px; border-radius: 50%; cursor: pointer; font-size: 14px;">×</button>
        </div>
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

// Suppression de commande entière
async function deleteCommande(commandeId) {
    if (confirm(`Supprimer la commande #${commandeId} et toutes ses tâches ? Cette action est irréversible.`)) {
        try {
            const response = await fetch(`/api/commandes/${commandeId}`, { method: 'DELETE' });
            if (response.ok) {
                showMessage(`Commande #${commandeId} supprimée`, 'success');
                // Recharger la liste des tâches après un court délai
                setTimeout(() => location.reload(), 500);
            } else {
                const errorData = await response.json();
                showMessage(errorData.error || 'Erreur lors de la suppression', 'error');
            }
        } catch (error) {
            showMessage('Erreur réseau', 'error');
        }
    }
}

function setupEventListeners() {
    // Ajouter les event listeners pour les boutons pause/resume
    const pauseBtn = document.getElementById('pause-btn');
    const resumeBtn = document.getElementById('resume-btn');
    const closeBtn = document.getElementById('message-close');

    if (pauseBtn) {
        pauseBtn.addEventListener('click', async () => {
            try {
                const response = await fetch('/api/control/pause', { method: 'POST' });
                if (response.ok) {
                    pauseBtn.style.display = 'none';
                    resumeBtn.style.display = 'inline-block';
                    showMessage('Worker mis en pause', 'success');
                } else {
                    showMessage('Erreur lors de la mise en pause', 'error');
                }
            } catch (error) {
                showMessage('Erreur réseau', 'error');
            }
        });
    }

    if (resumeBtn) {
        resumeBtn.addEventListener('click', async () => {
            try {
                const response = await fetch('/api/control/resume', { method: 'POST' });
                if (response.ok) {
                    resumeBtn.style.display = 'none';
                    pauseBtn.style.display = 'inline-block';
                    showMessage('Worker relancé', 'success');
                } else {
                    showMessage('Erreur lors du redémarrage', 'error');
                }
            } catch (error) {
                showMessage('Erreur réseau', 'error');
            }
        });
    }

    // Message overlay close
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            document.getElementById('message-overlay').style.display = 'none';
        });
    }

    // Initialiser l'état des boutons en fonction du statut du worker
    updateControlButtons();
}

async function updateControlButtons() {
    try {
        const response = await fetch('/api/printer/status');
        if (response.ok) {
            const statusData = await response.json();
            const pauseBtn = document.getElementById('pause-btn');
            const resumeBtn = document.getElementById('resume-btn');

            // Par défaut, montrer le bouton pause (worker actif)
            pauseBtn.style.display = 'inline-block';
            resumeBtn.style.display = 'none';

            // Cette logique peut être ajustée selon votre implémentation
            // Pour l'instant, on garde la logique simple
        }
    } catch (error) {
        console.error('Error fetching worker status for button update:', error);
    }
}

// Fonction pour afficher les messages de feedback
function showMessage(text, type = 'info') {
    const overlay = document.getElementById('message-overlay');
    const titleEl = document.getElementById('message-title');
    const textEl = document.getElementById('message-text');
    const content = overlay.querySelector('.message-content');

    titleEl.textContent = type === 'error' ? 'Erreur' : 'Succès';
    textEl.textContent = text;
    content.className = `message-content ${type}`;

    overlay.style.display = 'flex';

    // Auto-hide après 3 secondes
    setTimeout(() => {
        overlay.style.display = 'none';
    }, 3000);
}
