// Mise à jour périodique des données
setInterval(async () => {
    try {
        // Mise à jour du status de l'imprimante avec fréquence adaptée
        const statusResponse = await fetch('/api/printer/status');
        const statusData = await statusResponse.json();
        updatePrinterStatus(statusData);

        // Mise à jour des jobs/tâches moins fréquemment pour éviter surcharge
        if (Math.random() < 0.3) {  // ~30% de chance à chaque intervalle = ~3 secondes en moyenne
            const jobsResponse = await fetch('/api/jobs');
            const jobs = await jobsResponse.json();
            updateCurrentJob(jobs);
            updateJobList(jobs);
        }
    } catch (error) {
        console.error('Erreur mise à jour:', error);
        document.getElementById('printer-status').textContent = 'Erreur de connexion';
    }
}, 2000);  // Intervalle doublé pour réduire la charge USB

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
    } else if (statusData.status === 'Error') {
        // Gestion spéciale pour les erreurs USB/réseau
        statusEl.textContent = 'Status: Erreur de communication USB';
        statusEl.style.color = '#e74c3c';
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
        jobDisplay.innerHTML = `
            <div style="margin-bottom: 10px;">
                <strong>${currentJob.id}</strong> - ${calculateQuantity(currentJob)} exemplaires
            </div>
            <progress max="100" value="${progress}"></progress>
            <div style="margin-top: 5px; text-align: center;">
                ${progress.toFixed(1)}% complété
            </div>
        `;
    } else {
        jobDisplay.innerHTML = '<p>Aucune tâche en cours</p>';
    }
}

// Mise à jour de la file d'attente
function updateJobList(jobs) {
    const queueList = document.getElementById('job-list');
    const pendingJobs = jobs.filter(job => job.statut === 'PENDING');

    if (pendingJobs.length === 0) {
        queueList.innerHTML = '<p>File vide</p>';
        return;
    }

    queueList.innerHTML = pendingJobs.map(job => `
        <div class="queue-item">
            <div class="info">
                <strong>${job.id}</strong> - ${calculateQuantity(job)} exemplaires
                <br><small>${new Date(job.date_creation).toLocaleString()}</small>
            </div>
            <span class="quantity">${calculateQuantity(job)}</span>
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

document.getElementById('message-close').addEventListener('click', () => {
    document.getElementById('message-overlay').style.display = 'none';
});
