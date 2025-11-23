// Initialisation immédiate comme les autres pages
console.log('Homepage script loaded');

document.addEventListener('DOMContentLoaded', () => {
    console.log('Homepage DOM loaded, initializing interface...');
    loadInitialData();
    setupEventListeners();
});

async function loadInitialData() {
    console.log('Loading initial CUPS-synchronized data...');
    try {
        // Charger immédiatement l'état CUPS et les jobs CUPS
        await updatePrinterStatusFromAPI();
        await updateFromCUPS();

        // Démarrer les mises à jour périodiques avec CUPS
        startCUPSUpdates();
        startPrinterStatusUpdates();
    } catch (error) {
        console.error('Error loading initial CUPS data:', error);
        // Fallback vers l'ancien système
        await updateJobsFromAPI();
        startPeriodicUpdates();
    }
}

// Mises à jour périodiques des données CUPS
function startCUPSUpdates() {
    console.log('Starting CUPS-synchronized updates');
    setInterval(async () => {
        try {
            await updateFromCUPS();
        } catch (error) {
            console.warn('Error in CUPS update:', error);
        }
    }, 3000); // Mise à jour CUPS toutes les 3 secondes
}

// Mises à jour périodiques du statut imprimante
function startPrinterStatusUpdates() {
    console.log('Starting printer status updates');
    setInterval(async () => {
        try {
            await updatePrinterStatusFromAPI();
        } catch (error) {
            console.warn('Error in printer status update:', error);
        }
    }, 5000); // Statut imprimante toutes les 5 secondes
}

// Ancienne fonction gardée pour compatibilité en cas d'erreur CUPS
function startPeriodicUpdates() {
    console.log('Starting legacy periodic updates (fallback)');
    setInterval(async () => {
        try {
            await updatePrinterStatusFromAPI();
            await updateJobsFromAPI();
        } catch (error) {
            console.error('Error in legacy periodic update:', error);
        }
    }, 2000);
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

// Mise à jour des infos de debug
function updateDebugInfo(jobs, workerRunning) {
    const debugJobsCount = document.getElementById('debug-jobs-count');
    const debugWorkerStatus = document.getElementById('debug-worker-status');
    const debugLastUpdate = document.getElementById('debug-last-update');

    const totalJobs = jobs ? jobs.length : 0;
    const runningJobs = jobs ? jobs.filter(job => job.statut === 'PROCESSING').length : 0;
    const pendingJobs = jobs ? jobs.filter(job => job.statut === 'PENDING').length : 0;

    debugJobsCount.textContent = `Jobs en base: ${totalJobs} (En cours: ${runningJobs}, En attente: ${pendingJobs})`;
    debugWorkerStatus.textContent = `Worker: ${workerRunning ? '🟢 Actif' : '🔴 Inactif'}`;
    debugLastUpdate.textContent = `Dernière mise à jour: ${new Date().toLocaleTimeString()}`;
}

// Variables globales pour les données CUPS
let currentCUPSJobs = [];

// Mise à jour depuis CUPS : synchronise l'affichage avec la vraie file CUPS
async function updateFromCUPS() {
    try {
        const response = await fetch('/api/cups/jobs');
        if (response.ok) {
            const cupsData = await response.json();
            if (cupsData.success) {
                currentCUPSJobs = cupsData.jobs;
                updateCUPSDisplay(cupsData.jobs);
            }
        }
    } catch (error) {
        console.warn('Erreur récupération CUPS jobs:', error);
    }
}

// Affichage synchronisé avec CUPS exact
function updateCUPSDisplay(cupsJobs) {
    const currentJobEl = document.getElementById('current-job');
    const queueList = document.getElementById('job-list');

    // Mettre à jour les infos de debug
    updateDebugCUPSInfo(cupsJobs);

    // Filtrer les jobs CUPS
    const printingJobs = cupsJobs.filter(job => job.state === 'printing');
    const pendingJobs = cupsJobs.filter(job => job.state === 'pending');

    // Tâche en cours (vraie tâche CUPS en impression)
    if (printingJobs.length > 0) {
        const currentCUPSJob = printingJobs[0];
        const progressPercent = currentCUPSJob.total_pages > 0 ?
            Math.round((currentCUPSJob.completed_pages / currentCUPSJob.total_pages) * 100) : 0;

        currentJobEl.innerHTML = `
            <div style="display: flex; align-items: center; padding: 15px; border: 1px solid #28a745; background: #f8fff9; border-radius: 8px;">
                <div style="margin-right: 15px; font-size: 40px;">🖨️</div>
                <div style="flex: 1;">
                    <div><strong>Job CUPS #${currentCUPSJob.id}</strong></div>
                    <div>${currentCUPSJob.name} - ${currentCUPSJob.user}</div>
                    <div style="margin-top: 5px;">
                        <div style="background: #e9ecef; border-radius: 10px; height: 10px; width: 200px;">
                            <div style="background: #28a745; height: 100%; border-radius: 10px; width: ${progressPercent}%;"></div>
                        </div>
                        <div style="font-size: 0.9em; margin-top: 5px; color: #666;">
                            ${currentCUPSJob.completed_pages}/${currentCUPSJob.total_pages} pages (${progressPercent}%)
                        </div>
                    </div>
                </div>
            </div>
        `;
    } else {
        currentJobEl.innerHTML = '<p>Aucune impression en cours</p>';
    }

    // File d'attente CUPS réelle (jobs en attente)
    queueList.innerHTML = pendingJobs.length === 0 ?
        '<p>File d\'attente CUPS vide</p>' :
        pendingJobs.map(job => createCUPSJobHTML(job)).join('');
}

// HTML pour job CUPS
function createCUPSJobHTML(job) {
    const progressPercent = job.total_pages > 0 ? Math.round((job.completed_pages / job.total_pages) * 100) : 0;
    const createdDate = new Date(job.created_at * 1000).toLocaleTimeString();

    return `<div style="display: flex; align-items: center; padding: 12px; border: 1px solid #ddd; margin-bottom: 8px; border-radius: 8px; background: #fff8dd;">
        <div style="margin-right: 12px; font-size: 30px;">📋</div>
        <div style="flex: 1;">
            <div style="display: flex; align-items: center; margin-bottom: 4px;">
                <strong>Job CUPS #${job.id}</strong>
                <span style="background: #ffc107; color: black; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; margin-left: 8px;">${job.state.toUpperCase()}</span>
            </div>
            <div style="color: #333; margin-bottom: 2px;">${job.name} - ${job.user}</div>
            <div style="font-size: 0.9em; color: #666;">
                Créé: ${createdDate} • ${job.total_pages} pages
                ${job.state_reasons && job.state_reasons.length > 0 ? ` • ${job.state_reasons.join(', ')}` : ''}
            </div>
            ${job.completed_pages > 0 ? `
                <div style="margin-top: 4px;">
                    <div style="background: #e9ecef; border-radius: 5px; height: 4px; width: 100px;">
                        <div style="background: #ffc107; height: 100%; border-radius: 5px; width: ${progressPercent}%;"></div>
                    </div>
                </div>
            ` : ''}
        </div>
        <div style="display: flex; gap: 5px;">
            <button onclick="cancelCUPSJob(${job.id})" title="Annuler ce job CUPS" style="background: #dc3545; color: white; border: none; width: 25px; height: 25px; border-radius: 50%; cursor: pointer; font-size: 14px;">×</button>
        </div>
    </div>`;
}

// Mise à jour debug CUPS
function updateDebugCUPSInfo(cupsJobs) {
    const debugJobsCount = document.getElementById('debug-jobs-count');
    const debugWorkerStatus = document.getElementById('debug-worker-status');
    const debugLastUpdate = document.getElementById('debug-last-update');

    const printingJobs = cupsJobs.filter(job => job.state === 'printing');
    const pendingJobs = cupsJobs.filter(job => job.state === 'pending');
    const completedJobs = cupsJobs.filter(job => job.state === 'completed');

    debugJobsCount.textContent = `CUPS: ${cupsJobs.length} jobs (🖨️ ${printingJobs.length} impr., ⏳ ${pendingJobs.length} attente, ✅ ${completedJobs.length} term.)`;
    debugWorkerStatus.textContent = `Imprimante: ${printingJobs.length > 0 ? '🖨️ Active' : '⏸️ Prête'}`;
    debugLastUpdate.textContent = `Dernière sync CUPS: ${new Date().toLocaleTimeString()}`;
}

// Annulation job CUPS (via commande système)
async function cancelCUPSJob(jobId) {
    if (confirm(`Annuler le job CUPS #${jobId} ?`)) {
        try {
            // Note: annulation CUPS nécessiterait cups.cancelJob() si pycups l'avait
            // Pour l'instant, on peut seulement supprimer de la base logique mais pas du spooler CUPS
            // CUPS gère lui-même l'annulation via ses mécanismes internes
            showMessage(`Tentative d'annulation job CUPS #${jobId}`, 'info');

            // On peut essayer de marquer comme annulé dans notre logique, mais CUPS continuera
            // Pour un cancel réel, il faudrait modifier print_service pour utiliser cups.cancelJob()

        } catch (error) {
            showMessage('Erreur annulation job CUPS', 'error');
        }
    }
}

// Mise à jour périodique depuis CUPS
function startCUPSUpdates() {
    console.log('Starting CUPS-synchronized updates');
    setInterval(() => {
        updateFromCUPS();
    }, 3000); // Vérification CUPS toutes les 3 secondes
}

// Ancienne fonction gardée pour compatibilité
function updateJobList(jobs) {
    // Fallback vers logique ancienne si CUPS échoue
    console.log('CUPS update failed, using logical jobs as fallback');
    updateDebugInfo(jobs, true);

    const queueList = document.getElementById('job-list');
    const pendingTasks = [];

    if (jobs && Array.isArray(jobs)) {
        jobs.filter(job => job.statut === 'PENDING').forEach(job => {
            if (job.taches) {
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
            }
        });
    }

    if (pendingTasks.length === 0 && currentCUPSJobs.length === 0) {
        queueList.innerHTML = '<p>File d\'attente vide</p>';
    }
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
    // Ajouter les event listeners pour les boutons
    const testApiBtn = document.getElementById('test-api-btn');
    const pauseBtn = document.getElementById('pause-btn');
    const resumeBtn = document.getElementById('resume-btn');
    const closeBtn = document.getElementById('message-close');

    // Bouton de test API
    if (testApiBtn) {
        testApiBtn.addEventListener('click', async () => {
            console.log('🔍 [DEBUG] Test API button clicked');
            showMessage('Test de l\'API en cours...', 'info');

            try {
                // Test /api/jobs (données base de données)
                const jobsResponse = await fetch('/api/jobs');
                const jobsData = jobsResponse.ok ? await jobsResponse.json() : { error: 'Erreur HTTP ' + jobsResponse.status };

                // Test /api/printer/status (état réel CUPS)
                const statusResponse = await fetch('/api/printer/status');
                const statusData = statusResponse.ok ? await statusResponse.json() : { error: 'Erreur HTTP ' + statusResponse.status };

                // Test /api/cups/jobs (vraies tâches CUPS)
                const cupsJobsResponse = await fetch('/api/cups/jobs');
                const cupsJobsData = cupsJobsResponse.ok ? await cupsJobsResponse.json() : { error: 'Erreur HTTP ' + cupsJobsResponse.status };

                console.log('📋 [DEBUG] Jobs API response:', jobsData);
                console.log('🖨️ [DEBUG] Printer status API response:', statusData);
                console.log('🖨️ [DEBUG] CUPS Jobs API response:', cupsJobsData);

                // Afficher les résultats dans une alerte détaillée
                const debugInfo = `=== RÉSULTATS DU TEST API ===

📋 API /api/jobs (Base de données):
${jobsResponse.ok ? JSON.stringify(jobsData, null, 2) : jobsData.error}

🖨️ API /api/printer/status (État réel CUPS):
${statusResponse.ok ? JSON.stringify(statusData, null, 2) : statusData.error}

🖨️ API /api/cups/jobs (Vraies tâches CUPS):
${cupsJobsResponse.ok ? JSON.stringify(cupsJobsData, null, 2) : cupsJobsData.error}

=== SYNCHRONISATION ===
📊 Jobs logique: ${jobsData.length || 0}
🖨️ Jobs CUPS réels: ${cupsJobsData.total_jobs || 0}
🎯 Imprimante: ${statusData.status || 'N/A'} (${statusData.queued_jobs || 0} en file)
`;

                alert(debugInfo);

                // Montrer les jobs dans l'interface
                if (jobsData && jobsData.length > 0) {
                    updateJobList(jobsData);
                    showMessage(`API OK - ${jobsData.length} jobs trouvés`, 'success');
                } else {
                    showMessage('API OK mais file d\'attente vide', 'info');
                }

            } catch (error) {
                console.error('❌ [DEBUG] Erreur test API:', error);
                showMessage('Erreur lors du test API', 'error');
            }
        });
    }

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
