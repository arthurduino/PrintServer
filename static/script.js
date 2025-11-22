// État global pour les mises à jour différentielles
let currentJobsState = {
    currentJob: null,
    pendingTasks: []
};

// Mise à jour périodique adaptative selon l'activité d'impression
async function updateInterface(delay = 1000) {
    console.log(`🔄 [UPDATE] Mise à jour programmée dans ${delay}ms`);

    setTimeout(async () => {
        console.log('🔄 [UPDATE] Lancement de la mise à jour...');

        try {
            // Mise à jour du statut de l'imprimante en parallèle
            console.log('🔄 [UPDATE] Récupération du statut de l\'imprimante...');
            const statusResponse = await fetch('/api/printer/status');

            if (!statusResponse.ok) {
                throw new Error(`Statut erreur HTTP: ${statusResponse.status}`);
            }

            console.log(`🔄 [UPDATE] Statut HTTP: ${statusResponse.status}`);
            const statusData = await statusResponse.json();
            console.log(`🔄 [UPDATE] Données statut reçues:`, statusData);

            // Récupération des tâches - si ça échoue, ne pas mettre à jour l'interface
            console.log('🔄 [UPDATE] Récupération des tâches...');
            const jobsResponse = await fetch('/api/jobs');

            if (!jobsResponse.ok) {
                throw new Error(`Jobs erreur HTTP: ${jobsResponse.status}`);
            }

            console.log(`🔄 [UPDATE] Jobs HTTP: ${jobsResponse.status}`);
            const jobs = await jobsResponse.json();
            console.log(`🔄 [UPDATE] ${jobs.length} tâches reçues`);

            // TOUTES les requêtes ont réussi - on peut maintenant mettre à jour l'interface
            updatePrinterStatus(statusData);
            updateCurrentJobDiff(jobs);
            console.log('🔄 [UPDATE] Tâches disponibles:', jobs);
            updateJobListDiff(jobs);

            // Programmer la prochaine mise à jour : plus fréquent si impression en cours
            const isPrinting = statusData.status === 'Busy' || jobs.some(job => job.statut === 'PROCESSING');
            const nextDelay = isPrinting ? 500 : 1000; // 0.5s en impression, 1s sinon
            console.log(`🔄 [UPDATE] Prochaine mise à jour dans ${nextDelay}ms (${isPrinting ? 'impression' : 'attente'})`);
            updateInterface(nextDelay);

        } catch (error) {
            console.error('❌ [UPDATE] Erreur de requête API - Interface conservée telle quelle:', error.message);
            // ⚠️ IMPORTANT: En cas d'erreur, NE PAS modifier l'interface
            // Attendre plus longtemps avant de réessayer (pour éviter spam)
            updateInterface(3000);
        }
    }, delay);
}

// Attendre le chargement du DOM avant de démarrer
document.addEventListener('DOMContentLoaded', () => {
    // Démarrer les mises à jour
    updateInterface();
});

// Variable globale pour l'état du worker
let workerPausedState = false;

// Mise à jour du statut de l'imprimante avec informations essentielles
function updatePrinterStatus(statusData) {
    const statusEl = document.getElementById('printer-status');

    // Supprimer les classes précédentes
    statusEl.classList.remove('status-ready', 'status-busy', 'status-cooling', 'status-cover-open', 'status-paper-empty', 'status-error', 'status-disconnected');

    let mainStatus = '';
    let description = '';

    if (statusData.status === 'Disconnected') {
        statusEl.classList.add('status-disconnected');
        mainStatus = '❌ Déconnectée';
        description = 'Imprimante non détectée';
    } else if (statusData.is_error) {
        statusEl.classList.add('status-error');
        mainStatus = '⚠️ Erreur';
        description = 'Problème de communication';
    } else {
        // Déterminer le statut principal avec détails essentiels
        switch (statusData.status) {
            case 'Ready':
                statusEl.classList.add('status-ready');
                mainStatus = '🟢 Prêt';
                description = 'Imprimante opérationnelle - Prêt à imprimer';
                break;
            case 'Busy':
                statusEl.classList.add('status-busy');
                mainStatus = '🔵 Impression en cours';
                description = 'Tâche active sur l\'imprimante';
                break;
            case 'Cooling':
                statusEl.classList.add('status-cooling');
                mainStatus = '🟠 Refroidissement';
                description = 'Imprimante en pause technique (température élevée)';
                break;
            case 'Cover Open':
                statusEl.classList.add('status-cover-open');
                mainStatus = '🟡 Couvercle ouvert';
                description = 'Veuillez fermer le capot pour continuer';
                break;
            case 'Paper Empty':
                statusEl.classList.add('status-paper-empty');
                mainStatus = '🟡 Papier épuisé';
                description = 'Recharge nécessaire pour continuer';
                break;
            default:
                statusEl.classList.add('status-error');
                mainStatus = '🔴 Statut inconnu';
                description = 'Vérifiez la connexion de l\'imprimante';
        }
    }

    // HTML simple avec le statut et la description essentielle
    statusEl.innerHTML = `
        <div>${mainStatus}</div>
        <div>${description}</div>
    `;

    // Contrôle des boutons selon l'état
    const pauseBtn = document.getElementById('pause-btn');
    const resumeBtn = document.getElementById('resume-btn');

    // Désactiver les boutons en cas d'erreur ou problème matériel
    if (statusData.is_error || statusData.status === 'Disconnected' || statusData.status === 'Cooling') {
        pauseBtn.disabled = true;
        resumeBtn.disabled = true;
    } else {
        resumeBtn.disabled = false;
        resumeBtn.disabled = false;
    }
}

// Génère l'affichage principal du statut avec couleur appropriée
function getMainStatusDisplay(statusData) {
    const status = statusData.status;
    const color = getStatusColor(status);

    let icon = '🔴';
    if (status === 'Ready') icon = '🟢';
    else if (status === 'Busy') icon = '🔵';
    else if (status === 'Cooling') icon = '🟠';
    else if (status === 'Cover Open') icon = '🟡';
    else if (status === 'Paper Empty') icon = '🟡';

    return `<span style="color: ${color};">${icon} ${status.toUpperCase()}</span>`;
}

// Détermine la couleur selon le statut
function getStatusColor(status) {
    switch (status) {
        case 'Ready': return '#2ecc71';      // Vert
        case 'Busy': return '#3498db';       // Bleu
        case 'Cooling': return '#f39c12';    // Orange
        case 'Cover Open': return '#f1c40f'; // Jaune
        case 'Paper Empty': return '#f1c40f'; // Jaune
        default: return '#e74c3c';           // Rouge
    }
}

// Construit l'affichage des flags détaillés
function buildFlagsDisplay(statusData) {
    const flags = [];

    // Flags de statut prioritaires
    if (statusData.cover_open) {
        flags.push('<span style="color: #f1c40f;">📖 Couvercle ouvert</span>');
    }
    if (statusData.paper_empty) {
        flags.push('<span style="color: #f1c40f;">📄 Papier vide</span>');
    }
    if (statusData.is_cooling) {
        flags.push('<span style="color: #f39c12;">🌡️ Refroidissement actif</span>');
    }
    if (statusData.is_busy) {
        flags.push('<span style="color: #3498db;">🖨️ Imprimante active</span>');
    }

    if (flags.length === 0) {
        return '<div style="font-size: 0.8em; margin-top: 3px; color: #888;">• Aucune condition spéciale</div>';
    }

    return `
        <div style="font-size: 0.8em; margin-top: 3px;">
            ${flags.join(' • ')}
        </div>
    `;
}

// Mise à jour différentielle de la tâche en cours
function updateCurrentJobDiff(jobs) {
    const newCurrentJob = jobs.find(job => job.statut === 'PROCESSING');

    // Comparer avec l'état actuel
    const currentJobChanged = !currentJobsState.currentJob ||
                             !newCurrentJob ||
                             (currentJobsState.currentJob && currentJobsState.currentJob.id !== (newCurrentJob ? newCurrentJob.id : null));

    // Si pas de changement, vérifier si la tâche en cours d'impression a progressé
    if (!currentJobChanged && currentJobsState.currentJob) {
        const currentlyPrintingTask = currentJobsState.currentJob.taches?.find(task => task.statut === 'IN_PROGRESS');
        const newCurrentlyPrintingTask = newCurrentJob?.taches?.find(task => task.statut === 'IN_PROGRESS');

        // Mise à jour seulement si progression ou tâche différente
        if (currentlyPrintingTask && newCurrentlyPrintingTask &&
            (currentlyPrintingTask.id === newCurrentlyPrintingTask.id) &&
            (currentlyPrintingTask.quantite_faite === newCurrentlyPrintingTask.quantite_faite)) {
            console.log('🔄 [CURRENTJOB] Pas de changement détecté dans la tâche en cours');
            return;
        }
    }

    // Mise à jour nécessaire, utiliser la logique d'origine
    updateCurrentJob(jobs);

    // Mettre à jour l'état
    currentJobsState.currentJob = newCurrentJob ? { ...newCurrentJob } : null;
    console.log('🔄 [CURRENTJOB] Mise à jour effectuée');
}

// Mise à jour de la tâche en cours (fonction originale refactorisée)
function updateCurrentJob(jobs) {
    const jobDisplay = document.getElementById('current-job');
    const currentJob = jobs.find(job => job.statut === 'PROCESSING');

    if (currentJob) {
        // Afficher SEULEMENT la tâche réellement en cours d'impression (IN_PROGRESS)
        const currentlyPrintingTask = currentJob.taches.find(task => task.statut === 'IN_PROGRESS');

        if (currentlyPrintingTask) {
            const taskProgress = currentlyPrintingTask.quantite_totale > 0 ? (currentlyPrintingTask.quantite_faite / currentlyPrintingTask.quantite_totale) * 100 : 0;

            jobDisplay.innerHTML = `
                <div class="current-task-item" style="border: 2px solid #f59e0b; padding: 10px; border-radius: 8px;">
                    <div style="font-weight: bold; margin-bottom: 5px;">
                        Commande ${currentJob.id} - Impression en cours
                    </div>
                    <div style="margin-bottom: 8px;">
                        Tâche #${currentlyPrintingTask.id} • ${currentlyPrintingTask.type_tache} • ${currentlyPrintingTask.quantite_faite}/${currentlyPrintingTask.quantite_totale} exemplaires
                    </div>
                    <progress max="100" value="${taskProgress}" style="width: 100%; height: 8px;"></progress>
                    <div style="margin-top: 5px; text-align: center; font-size: 0.9em;">
                        ${currentlyPrintingTask.quantite_faite}/${currentlyPrintingTask.quantite_totale} (${taskProgress.toFixed(0)}%)
                    </div>
                    ${currentlyPrintingTask.config && currentlyPrintingTask.config.image_path ?
                        (() => {
                            const filename = currentlyPrintingTask.config.image_path.split('/').pop();
                            return `
                                <div class="task-image-preview" style="margin-top: 8px; text-align: center;">
                                    <img src="/uploads/${filename}" alt="Image en cours - ${filename}"
                                         style="max-width: 120px; max-height: 60px; border: 1px solid #ddd; border-radius: 4px;"
                                         onerror="this.style.display='none'; this.parentNode.innerHTML='<div style=font-size:0.8em;color:#666;>📄 ${filename}</div>'">
                                </div>
                            `;
                        })() : ''}
                </div>
            `;
        } else {
            // Commande PROCESSING mais aucune tâche IN_PROGRESS (en préparation)
            const pendingTasksCount = currentJob.taches.filter(task => task.statut === 'PENDING').length;
            const completedTasksCount = currentJob.taches.filter(task => task.statut === 'DONE').length;

            jobDisplay.innerHTML = `
                <div class="current-task-item" style="border: 2px solid #6b7280; padding: 10px; border-radius: 8px;">
                    <div style="font-weight: bold; margin-bottom: 5px;">
                        Commande ${currentJob.id} en préparation
                    </div>
                    <div style="font-size: 0.9em; color: #6b7280;">
                        ${pendingTasksCount} tâche(s) en attente • ${completedTasksCount} terminée(s)
                    </div>
                </div>
            `;
        }
    } else {
        jobDisplay.innerHTML = '<p>Aucune tâche en cours</p>';
    }
}

// Mise à jour différentielle de la file d'attente
function updateJobListDiff(jobs) {
    const queueList = document.getElementById('job-list');

    // Collecter toutes les tâches individuelles en attente
    const newPendingTasks = [];
    jobs.filter(job => job.statut === 'PENDING').forEach(job => {
        job.taches.forEach(task => {
            // Pour les tâches d'un job PENDING, toutes sont considérées comme PENDING sauf si déjà complétées
            const taskIsPending = task.quantite_faite < task.quantite_totale;

            if (taskIsPending) {
                newPendingTasks.push({
                    jobId: job.id,
                    clientName: job.nom_client,
                    taskId: task.id,
                    taskType: task.type_tache,
                    quantity: task.quantite_totale,
                    progress: task.quantite_faite || 0,  // Pour la reprise automatique
                    date: job.date_creation,
                    config: task.config
                });
            }
        });
    });

    // Comparer avec l'état actuel pour détecter les changements
    const changes = compareTaskLists(currentJobsState.pendingTasks, newPendingTasks);

    // Si des changements détectés
    if (changes.hasChanges) {
        console.log('🔄 [JOBLIST] Changements détectés:', changes);

        // Appliquer seulement les changements nécessaires
        applyQueueChanges(queueList, changes, newPendingTasks);

        // Mettre à jour l'état
        currentJobsState.pendingTasks = newPendingTasks.map(task => ({ ...task }));
        console.log('🔄 [JOBLIST] Mise à jour différentielle effectuée');
    } else {
        console.log('🔄 [JOBLIST] Aucune modification détectée dans la file d\'attente');
    }
}

// Comparer deux listes de tâches et identifier les changements
function compareTaskLists(oldTasks, newTasks) {
    const changes = {
        hasChanges: false,
        added: [],
        removed: [],
        updated: [],
        orderChanged: false
    };

    // Créer des maps pour une recherche rapide
    const oldTaskMap = new Map(oldTasks.map(task => [task.taskId, task]));
    const newTaskMap = new Map(newTasks.map(task => [task.taskId, task]));

    // Détecter les tâches supprimées
    oldTasks.forEach((oldTask, index) => {
        if (!newTaskMap.has(oldTask.taskId)) {
            changes.removed.push({ taskId: oldTask.taskId, index });
            changes.hasChanges = true;
        }
    });

    // Détecter les tâches ajoutées et mises à jour
    newTasks.forEach((newTask, index) => {
        const oldTask = oldTaskMap.get(newTask.taskId);

        if (!oldTask) {
            // Nouvelle tâche
            changes.added.push({ task: newTask, index });
            changes.hasChanges = true;
        } else {
            // Vérifier si la tâche a changé
            if (hasTaskChanged(oldTask, newTask)) {
                changes.updated.push({ taskId: newTask.taskId, oldIndex: oldTasks.findIndex(t => t.taskId === newTask.taskId), newIndex: index });
                changes.hasChanges = true;
            }
        }
    });

    // Vérifier si l'ordre a changé (si pas d'ajouts/suppressions)
    if (!changes.hasChanges && oldTasks.length === newTasks.length) {
        changes.orderChanged = !oldTasks.every((task, index) => task.taskId === newTasks[index].taskId);
        changes.hasChanges = changes.orderChanged;
    }

    return changes;
}

// Vérifier si une tâche a changé de manière significative
function hasTaskChanged(oldTask, newTask) {
    return oldTask.progress !== newTask.progress ||
           oldTask.quantity !== newTask.quantity ||
           oldTask.taskType !== newTask.taskType;
}

// Appliquer les changements à la liste des tâches
function applyQueueChanges(queueList, changes, newTasks) {
    // Si trop de changements ou file vide/vide devenue, faire une mise à jour complète
    if (changes.added.length + changes.removed.length + changes.updated.length > newTasks.length / 2 ||
        newTasks.length === 0 || currentJobsState.pendingTasks.length === 0) {
        console.log('🔄 [JOBLIST] Trop de changements, mise à jour complète');

        // Créer des objets job simulés pour la mise à jour complète
        const simulatedJobs = newTasks.map(task => ({
            statut: 'PENDING',
            taches: [{
                id: task.taskId,
                quantite_totale: task.quantity,
                quantite_faite: task.progress || 0,
                type_tache: task.taskType,
                config: task.config
            }]
        }));

        updateJobList(simulatedJobs);
        return;
    }

    // Appliquer les suppressions
    changes.removed.sort((a, b) => b.index - a.index).forEach(({ taskId }) => {
        const element = queueList.querySelector(`[data-task-id="${taskId}"]`);
        if (element) {
            element.remove();
        }
    });

    // Appliquer les mises à jour
    changes.updated.forEach(({ taskId, oldIndex, newIndex }) => {
        const element = queueList.querySelector(`[data-task-id="${taskId}"]`);
        const task = newTasks.find(t => t.taskId === taskId);

        if (element && task) {
            element.outerHTML = createTaskHTML(task);
        }
    });

    // Appliquer les ajouts
    changes.added.forEach(({ task, index }) => {
        const taskHTML = createTaskHTML(task);
        const referenceElement = queueList.children[index];

        if (referenceElement) {
            referenceElement.insertAdjacentHTML('beforebegin', taskHTML);
        } else {
            queueList.insertAdjacentHTML('beforeend', taskHTML);
        }
    });

    // Si pas de tâches, afficher "File vide"
    if (newTasks.length === 0) {
        queueList.innerHTML = '<p>File vide</p>';
    }
}

// Créer le HTML pour une tâche - Version ultra-simplifiée et ergonomique
function createTaskHTML(task) {
    const isRecovery = task.progress && task.progress > 0;
    const taskProgressText = isRecovery ? ` (${task.progress}/${task.quantity})` : '';

    // Gérer nom client default si undefined
    const clientName = task.clientName || 'Client anonyme';

    // Job ID avec fallback
    const jobId = task.jobId || 'N/A';

    // Gérer date avec parsing robuste
    let formattedDate = '--/-- --:--';
    try {
        if (task.date && typeof task.date === 'string') {
            const dateStr = task.date.replace(' ', 'T');
            const dateObj = new Date(dateStr);
            if (!isNaN(dateObj.getTime())) {
                formattedDate = dateObj.toLocaleString('fr-FR', {
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit'
                });
            }
        }
    } catch (e) {
        console.warn(`Erreur parsing date pour tâche ${task.taskId}:`, task.date);
    }

    // Extraire nom du fichier pour la source seulement
    let filename = '';
    if (task.config && task.config.image_path) {
        const pathParts = task.config.image_path.split('/');
        filename = pathParts[pathParts.length - 1];
    }

    return `
    <div class="queue-item simple-queue-item ${isRecovery ? 'recovery-task' : ''}" data-job-id="${jobId}" data-task-id="${task.taskId}">
        <div class="task-image-container">
            ${task.config && task.config.image_path ?
                `<img src="/uploads/${filename}" alt="Aperçu tâche" class="task-image"
                     onerror="this.style.display='none'; this.parentNode.innerHTML='<div class="no-image">📄</div>'">` :
                '<div class="no-image">📄</div>'
            }
        </div>
        <div class="task-info">
            <div class="task-primary">
                <strong>Tâche #${task.taskId}</strong>
                ${isRecovery ? '<span class="recovery-icon">🔄</span>' : ''}
                <span class="quantity-display">${task.quantity}${taskProgressText ? ` <em>(${taskProgressText})</em>` : ''}</span>
            </div>
            <div class="task-secondary">
                <span class="client">${clientName}</span>
                <span class="separator">•</span>
                <span class="timestamp">${formattedDate}</span>
            </div>
        </div>
        <div class="task-actions">
            <span class="quantity-count">${task.quantity}</span>
            <button class="delete-button" onclick="deleteTask(${task.taskId})" title="Supprimer">×</button>
        </div>
    </div>
    `;
}

// Mise à jour de la file d'attente (fonction originale, maintenant utilisée seulement pour mise à jour complète)
function updateJobList(jobs) {
    const queueList = document.getElementById('job-list');

    // Collecter toutes les tâches individuelles en attente
    console.log('🔄 [JOBLIST] Collecte des tâches individuelles...');
    const pendingTasks = [];
    jobs.filter(job => job.statut === 'PENDING').forEach(job => {
        console.log(`🔄 [JOBLIST] Job ${job.id} (${job.statut}) avec ${job.taches.length} tâches`);
        job.taches.forEach(task => {
            // Pour les tâches d'un job PENDING, toutes sont considérées comme PENDING sauf si déjà complétées
            const taskIsPending = task.quantite_faite < task.quantite_totale;
            console.log(`🔄 [JOBLIST] Tâche ${task.id}: ${task.quantite_faite}/${task.quantite_totale} (${taskIsPending ? 'PENDING' : 'DONE'})`);

            if (taskIsPending) {
                pendingTasks.push({
                    jobId: job.id,
                    clientName: job.nom_client,
                    taskId: task.id,
                    taskType: task.type_tache,
                    quantity: task.quantite_totale,
                    progress: task.quantite_faite || 0,  // Pour la reprise automatique
                    date: job.date_creation,
                    config: task.config
                });
            }
        });
    });

    // Afficher chaque tâche individuelle
    if (pendingTasks.length === 0) {
        queueList.innerHTML = '<p>File vide</p>';
        return;
    }

    queueList.innerHTML = pendingTasks.map(task => createTaskHTML(task)).join('');
}

// Calcul de la progression
function calculateProgress(job) {
    let total = 0;
    let done = 0;

    job.taches.forEach(task => {
        total += task.quantite_totale;
        done += task.quantite_faite;
    });

    return total > 0 ? (done / total) * 100 : 0;
}

// Calcul de la quantité totale
function calculateQuantity(job) {
    return job.taches.reduce((sum, task) => sum + task.quantite_totale, 0);
}

// Calcul du texte de progression numérique (ex: "31/50")
function calculateProgressText(job) {
    let total = 0;
    let done = 0;

    job.taches.forEach(task => {
        total += task.quantite_totale;
        done += task.quantite_faite;
    });

    return `${done}/${total} complété`;
}

// Gestion du formulaire de création de tâche
document.getElementById('job-form').addEventListener('submit', async (event) => {
    event.preventDefault();

    const formData = new FormData(event.target);
    const files = formData.getAll('files');

    if (files.length === 0) {
        showMessage('Erreur', 'Sélectionnez une image');
        return;
    }

    // Créer la tâche directement
    const taskData = {
        nom_client: "Tâche simple",
        reference_externe: null,
        taches: [{
            type: "BATCH",
            quantite: parseInt(formData.get('quantity')) || 1,
            config: {
                image_path: files[0].name,
                cut: formData.get('cut') === 'on',
                label_type: formData.get('label_type') || '62',
                rotate: formData.get('rotate') || '0'
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
        } else {
            showMessage('Erreur', result.error || 'Erreur inconnue');
        }
    } catch (error) {
        showMessage('Erreur', 'Erreur réseau');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Créer la tâche';
    }
});

// Contrôles worker
document.getElementById('pause-btn').addEventListener('click', async () => {
    try {
        const response = await fetch('/api/control/pause', { method: 'POST' });
        if (response.ok) {
            workerPausedState = true;
            showMessage('Info', '⏸️ Worker mis en pause');
            updateWorkerStatusIndicator();
        } else {
            showMessage('Erreur', 'Impossible de mettre le worker en pause');
        }
    } catch (error) {
        showMessage('Erreur', 'Erreur réseau lors de la mise en pause');
    }
});

document.getElementById('resume-btn').addEventListener('click', async () => {
    try {
        const response = await fetch('/api/control/resume', { method: 'POST' });
        if (response.ok) {
            workerPausedState = false;
            showMessage('Info', '▶️ Worker relancé');
            updateWorkerStatusIndicator();
        } else {
            showMessage('Erreur', 'Impossible de relancer le worker');
        }
    } catch (error) {
        showMessage('Erreur', 'Erreur réseau lors du relancement');
    }
});

// Met à jour l'indicateur visuel de l'état du worker
function updateWorkerStatusIndicator() {
    // Cette fonction est appelée quand on change manuellement l'état
    // L'indicateur sera rafraîchi à la prochaine mise à jour automatique
}

// Message overlay
function showMessage(title, message) {
    const overlay = document.getElementById('message-overlay');
    document.getElementById('message-title').textContent = title;
    document.getElementById('message-text').textContent = message;
    overlay.style.display = 'flex';
}

// Fonction de suppression de tâche individuelle
async function deleteTask(taskId) {
    if (confirm(`Voulez-vous vraiment supprimer la tâche #${taskId} ?\n\n⚠️ Cette action est irréversible.`)) {

        console.log(`🗑️ [UI] Suppression de tâche ${taskId} demandée`);

        try {
            const response = await fetch(`/api/taches/${taskId}`, {
                method: 'DELETE'
            });

            const result = await response.json();

            if (response.ok) {
                console.log(`✅ [UI] Tâche ${taskId} supprimée avec succès`);
                showMessage('Succès', result.message || `Tâche ${taskId} supprimée avec succès`);
                // Rafraîchir l'interface
                setTimeout(() => {
                    location.reload();
                }, 1500);
            } else {
                console.error(`❌ [UI] Erreur suppression tâche ${taskId}:`, result);
                showMessage('Erreur', result.error || `Impossible de supprimer la tâche ${taskId}`);
            }

        } catch (error) {
            console.error(`❌ [UI] Erreur réseau lors suppression tâche ${taskId}:`, error);
            showMessage('Erreur', 'Erreur réseau - Impossible de supprimer la tâche');
        }
    }
}

document.getElementById('message-close').addEventListener('click', () => {
    document.getElementById('message-overlay').style.display = 'none';
});
