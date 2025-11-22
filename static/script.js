// Mise à jour périodique adaptative selon l'activité d'impression
async function updateInterface(delay = 1000) {
    console.log(`🔄 [UPDATE] Mise à jour programmée dans ${delay}ms`);

    setTimeout(async () => {
        console.log('🔄 [UPDATE] Lancement de la mise à jour...');

        try {
            // Mise à jour du statut de l'imprimante en parallèle
            console.log('🔄 [UPDATE] Récupération du statut de l\'imprimante...');
            const statusResponse = await fetch('/api/printer/status');
            console.log(`🔄 [UPDATE] Statut HTTP: ${statusResponse.status}`);

            const statusData = await statusResponse.json();
            console.log(`🔄 [UPDATE] Données statut reçues:`, statusData);

            updatePrinterStatus(statusData);

            console.log('🔄 [UPDATE] Récupération des tâches...');
            const jobsResponse = await fetch('/api/jobs');
            console.log(`🔄 [UPDATE] Jobs HTTP: ${jobsResponse.status}`);

            const jobs = await jobsResponse.json();
            console.log(`🔄 [UPDATE] ${jobs.length} tâches reçues`);

            updateCurrentJob(jobs);
            console.log('🔄 [UPDATE] Tâches disponibles:', jobs);
            updateJobList(jobs);

            // Programmer la prochaine mise à jour : plus fréquent si impression en cours
            const isPrinting = statusData.status === 'Busy' || jobs.some(job => job.statut === 'PROCESSING');
            const nextDelay = isPrinting ? 500 : 1000; // 0.5s en impression, 1s sinon
            console.log(`🔄 [UPDATE] Prochaine mise à jour dans ${nextDelay}ms (${isPrinting ? 'impression' : 'attente'})`);
            updateInterface(nextDelay);

        } catch (error) {
            console.error('❌ [UPDATE] Erreur mise à jour:', error);
            // En cas d'erreur, attendre 2 secondes avant de réessayer
            updateInterface(2000);
        }
    }, delay);
}

// Attendre le chargement du DOM avant de démarrer
document.addEventListener('DOMContentLoaded', () => {
    // Démarrer les mises à jour
    updateInterface();
});

// Mise à jour du statut de l'imprimante
function updatePrinterStatus(statusData) {
    const statusEl = document.getElementById('printer-status');

    if (statusData.status === 'Ready') {
        statusEl.textContent = 'Status: Prêt à imprimer';
        statusEl.style.color = '#2ecc71';
    } else if (statusData.status === 'Cooling') {
        statusEl.textContent = 'Status: Refroidissement';
        statusEl.style.color = '#f39c12';
        document.getElementById('pause-btn').disabled = true;
        document.getElementById('resume-btn').disabled = true;
    } else if (statusData.status === 'Busy') {
        statusEl.textContent = 'Status: Impression en cours';
        statusEl.style.color = '#3498db';
    } else if (statusData.status === 'Error' || statusData.is_error) {
        // Gestion spéciale pour les erreurs USB/réseau vs erreurs normales
        if (statusData.phase === 'COOLING') {
            statusEl.textContent = 'Status: Refroidissement en cours';
            statusEl.style.color = '#f39c12';
        } else {
            statusEl.textContent = 'Status: Erreur de communication USB';
            statusEl.style.color = '#e74c3c';
        }
    } else {
        statusEl.textContent = `Status: ${statusData.detail || statusData.status}`;
        statusEl.style.color = '#e74c3c';
    }

    // Gérer les boutons selon le statut
    const pauseBtn = document.getElementById('pause-btn');
    const resumeBtn = document.getElementById('resume-btn');

    if (statusData.status === 'Cooling') {
        pauseBtn.disabled = true;
        resumeBtn.disabled = true;
    } else {
        pauseBtn.disabled = false;
        resumeBtn.disabled = false;
    }
}

// Mise à jour de la tâche en cours
function updateCurrentJob(jobs) {
    const jobDisplay = document.getElementById('current-job');
    const currentJob = jobs.find(job => job.statut === 'PROCESSING');

    if (currentJob) {
        const progress = calculateProgress(currentJob);
        const progressText = calculateProgressText(currentJob);
        jobDisplay.innerHTML = `
            <div style="margin-bottom: 10px;">
                <strong>${currentJob.id}</strong> - ${calculateQuantity(currentJob)} exemplaires
            </div>
            <progress max="100" value="${progress}"></progress>
            <div style="margin-top: 5px; text-align: center;">
                ${progressText} (${progress.toFixed(1)}%)
            </div>
        `;
    } else {
        jobDisplay.innerHTML = '<p>Aucune tâche en cours</p>';
    }
}

// Mise à jour de la file d'attente
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

    queueList.innerHTML = pendingTasks.map(task => `
        <div class="queue-item" data-job-id="${task.jobId}" data-task-id="${task.taskId}">
            <div class="info">
                <strong>Tâche #${task.taskId}</strong> - ${task.clientName}
                <br><small>${task.quantity} exemplaires - ${task.taskType} - ${new Date(task.date).toLocaleString()}</small>
            </div>
            <div class="queue-actions">
                <span class="quantity">${task.quantity}</span>
                <button class="delete-btn" onclick="deleteTask(${task.taskId})" title="Supprimer cette tâche">🗑️</button>
            </div>
        </div>
    `).join('');
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
    await fetch('/api/control/pause', { method: 'POST' });
    showMessage('Info', 'Worker mis en pause');
});

document.getElementById('resume-btn').addEventListener('click', async () => {
    await fetch('/api/control/resume', { method: 'POST' });
    showMessage('Info', 'Worker relancé');
});

// Message overlay
function showMessage(title, message) {
    const overlay = document.getElementById('message-overlay');
    document.getElementById('message-title').textContent = title;
    document.getElementById('message-text').textContent = message;
    overlay.style.display = 'flex';
}

// Fonction de suppression de tâche individuelle
async function deleteTask(taskId) {
    if (confirm(`Voulez-vous vraiment supprimer la tâche #${taskId} ?`)) {
        showMessage('Info', 'Suppression individuelle en développement - Utilisez la page Commandes pour supprimer toute la commande');
    }
}

document.getElementById('message-close').addEventListener('click', () => {
    document.getElementById('message-overlay').style.display = 'none';
});
