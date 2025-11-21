// Variables globales
let currentStatusData = null;

// Mise à jour périodique des données
setInterval(async () => {
    try {
        // Mise à jour du status de l'imprimante
        const statusResponse = await fetch('/api/printer/status');
        const statusData = await statusResponse.json();
        currentStatusData = statusData;

        updatePrinterStatus(statusData);

        // Mise à jour des jobs
        const jobsResponse = await fetch('/api/jobs');
        const jobs = await jobsResponse.json();

        updateCurrentJob(jobs);
        updateJobList(jobs);

    } catch (error) {
        console.error('Erreur lors de la mise à jour:', error);
    }
}, 1000);

// Mise à jour du statut de l'imprimante (header et carte)
function updatePrinterStatus(statusData) {
    const statusBadge = document.getElementById('printer-status-badge');
    const statusCard = document.getElementById('printer-status');
    const phaseCard = document.getElementById('printer-phase');

    if (!statusBadge || !statusCard) return;

    let statusText = statusData.status;
    let statusClass = '';
    let badgeBg = '#6c757d';

    if (statusData.status === 'Ready') {
        statusClass = 'status-ready';
        badgeBg = '#28a745';
        statusText = 'Prêt';
    } else if (statusData.status === 'Cooling') {
        statusClass = 'status-cooling';
        badgeBg = '#17a2b8';
        statusText = 'Refroidissement';
    } else {
        statusClass = 'status-error';
        badgeBg = '#dc3545';
        statusText = 'Erreur';
    }

    // Update badge in header
    statusBadge.innerHTML = `
        <div class="status-indicator" style="background: ${badgeBg}"></div>
        <span>${statusText}</span>
    `;

    // Update status card
    statusCard.className = `printer-status ${statusClass}`;
    statusCard.innerHTML = `<span>${statusText}</span>`;

    // Update phase info
    if (phaseCard) {
        phaseCard.textContent = statusData.detail ? statusData.detail : `Phase: ${statusData.phase || 'UNKNOWN'}`;
    }

    // Gestion des boutons de contrôle selon phase
    const pauseBtn = document.getElementById('pause-btn');
    const resumeBtn = document.getElementById('resume-btn');
    if (statusData.status === 'Cooling') {
        // Désactiver les contrôles pendant le refroidissement
        pauseBtn.disabled = true;
        resumeBtn.disabled = true;
        pauseBtn.style.opacity = '0.5';
        resumeBtn.style.opacity = '0.5';
        pauseBtn.title = "Contrôle désactivé pendant le refroidissement";
        resumeBtn.title = "Contrôle désactivé pendant le refroidissement";
    } else {
        pauseBtn.disabled = false;
        resumeBtn.disabled = false;
        pauseBtn.style.opacity = '1';
        resumeBtn.style.opacity = '1';
        pauseBtn.title = "";
        resumeBtn.title = "";
    }
}

// Mise à jour de la commande en cours
function updateCurrentJob(jobs) {
    const currentJobDiv = document.getElementById('current-job');
    const currentJob = jobs.find(job => job.statut === 'PROCESSING');

    if (currentJob) {
        const progress = calculateOverallProgress(currentJob);
        currentJobDiv.innerHTML = `
            <h3>${currentJob.nom_client} ${currentJob.reference_externe || ''}</h3>
            <p>ID: ${currentJob.id} - Statut: ${currentJob.statut}</p>
            <div style="margin: 15px 0;">
                <progress max="100" value="${progress}"></progress>
                <p style="text-align: center; margin-top: 8px;">Progression globale: ${progress.toFixed(1)}%</p>
            </div>
        `;
    } else {
        currentJobDiv.innerHTML = `
            <div class="no-job">
                <i class="fas fa-inbox"></i>
                <p>Aucune commande en cours</p>
            </div>
        `;
    }
}

// Calcul de la progression globale d'une commande
function calculateOverallProgress(job) {
    let totalTasks = 0, totalDone = 0;

    job.taches.forEach(task => {
        totalTasks += task.quantite_totale;
        totalDone += task.quantite_faite;
    });

    return totalTasks > 0 ? (totalDone / totalTasks) * 100 : 0;
}

// Mise à jour de la liste d'attente
function updateJobList(jobs) {
    const ul = document.getElementById('job-list');
    const pendingJobs = jobs.filter(job => job.statut === 'PENDING');

    ul.innerHTML = '';
    if (pendingJobs.length === 0) {
        ul.innerHTML = `
            <div class="no-queue">
                <i class="fas fa-check-circle"></i>
                <p>File d'attente vide</p>
            </div>
        `;
        return;
    }

    pendingJobs.forEach(job => {
        const li = document.createElement('li');
        const totalTasks = job.taches.length;
        const totalQuantity = job.taches.reduce((sum, task) => sum + task.quantite_totale, 0);

        li.innerHTML = `
            <i class="fas fa-clock"></i>
            <div style="flex: 1;">
                <strong>${job.nom_client} ${job.reference_externe || ''}</strong><br>
                <small>${totalTasks} tâche(s), ${totalQuantity} exemplaire(s) • ${new Date(job.date_creation).toLocaleString()}</small>
            </div>
            <span style="color: #667eea; font-weight: 500;">En attente</span>
        `;
        ul.appendChild(li);
    });
}

// Gestion du formulaire de création de job
document.getElementById('job-form').addEventListener('submit', async (event) => {
    event.preventDefault();

    const formData = new FormData(event.target);
    const files = formData.getAll('files');

    // Validation des fichiers
    if (files.length === 0) {
        showMessage('Erreur', 'Veuillez sélectionner au moins une image.', 'error');
        return;
    }

    // Récupération des données du formulaire
    const jobData = {
        nom_client: formData.get('nom_client'),
        reference_externe: formData.get('reference_externe') || null,
        taches: [{
            type: formData.get('task_type') || 'BATCH',
            quantite: parseInt(formData.get('quantity')) || 1,
            config: {
                image_path: files[0].name, // Sera remplacé par le chemin serveur
                cut: formData.get('cut') === 'on',
                label_type: formData.get('label_type') || '62',
                rotate: formData.get('rotate') || '0'
            }
        }]
    };

    // Préparer les données pour l'API
    const apiFormData = new FormData();
    apiFormData.append('command_json', JSON.stringify(jobData));

    // Ajouter tous les fichiers
    files.forEach(file => {
        apiFormData.append('files', file);
    });

    // Afficher le loading
    const submitBtn = event.target.querySelector('button[type="submit"]');
    submitBtn.classList.add('loading');
    submitBtn.disabled = true;

    try {
        const response = await fetch('/api/jobs', {
            method: 'POST',
            body: apiFormData
        });

        const result = await response.json();

        if (response.ok) {
            showMessage('Succès', `Commande créée avec succès! ID: ${result.job_id}`, 'success');
            event.target.reset();
            updateFileCount(); // Reset file count display
            updatePreview(); // Reset preview
        } else {
            showMessage('Erreur', result.error || 'Erreur inconnue', 'error');
        }
    } catch (error) {
        showMessage('Erreur', `Erreur réseau: ${error.message}`, 'error');
    } finally {
        submitBtn.classList.remove('loading');
        submitBtn.disabled = false;
    }
});

// Gestion de l'upload de fichiers
document.getElementById('files').addEventListener('change', (event) => {
    updateFileCount();
    updatePreview();

    // Changer le texte du label selon le nombre de fichiers
    const label = document.getElementById('file-label');
    const files = event.target.files;
    if (files.length === 0) {
        label.innerHTML = '<i class="fas fa-upload"></i> Sélectionner l\'image';
    } else if (files.length === 1) {
        label.innerHTML = `<i class="fas fa-check"></i> ${files[0].name}`;
    } else {
        label.innerHTML = `<i class="fas fa-check"></i> ${files.length} fichiers sélectionnés`;
    }
});

// Mise à jour du compteur de fichiers
function updateFileCount() {
    const fileInput = document.getElementById('files');
    const fileCount = document.getElementById('file-count');
    const files = fileInput.files;

    if (files.length === 0) {
        fileCount.textContent = 'Aucun fichier sélectionné';
        fileCount.style.color = '#6c757d';
    } else {
        fileCount.textContent = `${files.length} fichier(s) sélectionné(s)`;
        fileCount.style.color = '#28a745';

        // Afficher les noms des fichiers
        const fileNames = Array.from(files).map(f => f.name).join(', ');
        fileCount.title = fileNames;
    }
}

// Mise à jour de l'aperçu du job
function updatePreview() {
    const previewDiv = document.getElementById('job-preview');
    const form = document.getElementById('job-form');
    const formData = new FormData(form);

    const hasData = formData.get('nom_client') ||
                   formData.get('reference_externe') ||
                   formData.getAll('files').length > 0;

    if (!hasData) {
        previewDiv.innerHTML = `
            <div class="preview-placeholder">
                <i class="fas fa-magic"></i>
                <p>Remplissez le formulaire pour voir l'aperçu</p>
            </div>
        `;
        return;
    }

    const clientName = formData.get('nom_client') || 'Non spécifié';
    const reference = formData.get('reference_externe') || 'Aucune';
    const taskType = formData.get('task_type') || 'BATCH';
    const quantity = parseInt(formData.get('quantity')) || 1;
    const labelType = formData.get('label_type') || '62';
    const rotate = formData.get('rotate') || '0';
    const cut = formData.get('cut') === 'on';
    const files = formData.getAll('files');

    previewDiv.innerHTML = `
        <div class="preview-content">
            <h4><i class="fas fa-eye"></i> Aperçu de la Commande</h4>
            <p><strong>Client:</strong> ${clientName}</p>
            <p><strong>Référence:</strong> ${reference}</p>
            <p><strong>Type de tâche:</strong> ${taskType === 'BATCH' ? 'Batch (même image)' : 'Série (images différentes)'}</p>
            <p><strong>Quantité:</strong> ${quantity} exemplaire(s)</p>
            <p><strong>Type d'étiquette:</strong> ${labelType}mm</p>
            <p><strong>Rotation:</strong> ${rotate}°</p>
            <p><strong>Découpe automatique:</strong> ${cut ? 'Oui' : 'Non'}</p>
            <p><strong>Fichiers:</strong> ${files.length} sélectionné(s)</p>
        </div>
    `;
}

// Écouter les changements du formulaire pour mettre à jour l'aperçu
document.getElementById('job-form').addEventListener('input', updatePreview);
document.getElementById('job-form').addEventListener('change', updatePreview);

// Gestion du reset du formulaire
document.getElementById('job-form').addEventListener('reset', () => {
    setTimeout(() => {
        updateFileCount();
        updatePreview();
        const label = document.getElementById('file-label');
        label.innerHTML = '<i class="fas fa-upload"></i> Sélectionner l\'image';
    }, 10);
});

// Contrôles du worker (pause/resume)
document.getElementById('pause-btn').addEventListener('click', async () => {
    try {
        const response = await fetch('/api/control/pause', { method: 'POST' });
        if (response.ok) {
            showMessage('Succès', 'Worker mis en pause', 'success');
        } else {
            showMessage('Erreur', 'Erreur lors de la mise en pause', 'error');
        }
    } catch (error) {
        showMessage('Erreur', `Erreur réseau: ${error.message}`, 'error');
    }
});

document.getElementById('resume-btn').addEventListener('click', async () => {
    try {
        const response = await fetch('/api/control/resume', { method: 'POST' });
        if (response.ok) {
            showMessage('Succès', 'Worker relancé', 'success');
        } else {
            showMessage('Erreur', 'Erreur lors du redémarrage', 'error');
        }
    } catch (error) {
        showMessage('Erreur', `Erreur réseau: ${error.message}`, 'error');
    }
});

// Gestion de l'overlay de messages
function showMessage(title, text, type = 'success') {
    const overlay = document.getElementById('message-overlay');
    const titleEl = document.getElementById('message-title');
    const textEl = document.getElementById('message-text');
    const iconEl = document.querySelector('.message-icon i');

    titleEl.textContent = title;
    textEl.textContent = text;

    // Changer l'icône selon le type
    iconEl.className = type === 'success' ? 'fas fa-check-circle' :
                      type === 'error' ? 'fas fa-exclamation-triangle' :
                      'fas fa-info-circle';

    // Changer la couleur de l'icône
    iconEl.style.color = type === 'success' ? '#28a745' :
                        type === 'error' ? '#dc3545' :
                        '#17a2b8';

    overlay.style.display = 'flex';
}

document.getElementById('message-close').addEventListener('click', () => {
    document.getElementById('message-overlay').style.display = 'none';
});

// Fermer l'overlay en cliquant à l'extérieur
document.getElementById('message-overlay').addEventListener('click', (e) => {
    if (e.target.id === 'message-overlay') {
        document.getElementById('message-overlay').style.display = 'none';
    }
});

// Initialisation
document.addEventListener('DOMContentLoaded', () => {
    updateFileCount();
    updatePreview();
});
