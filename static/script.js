// Mise à jour périodique des données
setInterval(async () => {
    try {
        // Mise à jour du status de l'imprimante
        const statusResponse = await fetch('/api/printer/status');
        const statusData = await statusResponse.json();

        const statusElement = document.getElementById('printer-status');
        statusElement.textContent = `${statusData.status}${statusData.detail ? ' - ' + statusData.detail : ''}`;

        // Mise à jour de la couleur selon le status
        statusElement.className = '';
        if (statusData.status === 'Ready') {
            statusElement.classList.add('status-ready');
        } else if (statusData.status === 'Cooling') {
            statusElement.classList.add('status-cooling');
        } else {
            statusElement.classList.add('status-error');
        }

        // Gestion des boutons de contrôle selon phase
        const pauseBtn = document.getElementById('pause-btn');
        const resumeBtn = document.getElementById('resume-btn');
        if (statusData.status === 'Cooling') {
            // Désactiver les contrôles pendant le refroidissement
            pauseBtn.disabled = true;
            resumeBtn.disabled = true;
            pauseBtn.title = "Contrôle désactivé pendant le refroidissement";
            resumeBtn.title = "Contrôle désactivé pendant le refroidissement";
        } else {
            pauseBtn.disabled = false;
            resumeBtn.disabled = false;
            pauseBtn.title = "";
            resumeBtn.title = "";
        }

        // Mise à jour des jobs
        const jobsResponse = await fetch('/api/jobs');
        const jobs = await jobsResponse.json();

        updateCurrentJob(jobs);
        updateJobList(jobs);

    } catch (error) {
        console.error('Erreur lors de la mise à jour:', error);
    }
}, 1000);

// Mise à jour de la commande en cours
function updateCurrentJob(jobs) {
    const currentJobDiv = document.getElementById('current-job');
    const currentJob = jobs.find(job => job.statut === 'PROCESSING');

    if (currentJob) {
        const progress = calculateOverallProgress(currentJob);
        currentJobDiv.innerHTML = `
            <h3>${currentJob.nom_client} ${currentJob.reference_externe || ''}</h3>
            <p>ID: ${currentJob.id} - Statut: ${currentJob.statut}</p>
            <progress max="100" value="${progress}"></progress>
            <p>Progression globale: ${progress.toFixed(1)}%</p>
        `;
    } else {
        currentJobDiv.innerHTML = '<p>Aucune commande en cours de traitement</p>';
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
        ul.innerHTML = '<li>Aucun job en attente</li>';
        return;
    }

    pendingJobs.forEach(job => {
        const li = document.createElement('li');
        const totalTasks = job.taches.length;
        const totalQuantity = job.taches.reduce((sum, task) => sum + task.quantite_totale, 0);

        li.innerHTML = `
            ${job.nom_client} ${job.reference_externe || ''}
            (${totalTasks} tâches, ${totalQuantity} exemplaires)
            - Créé le ${new Date(job.date_creation).toLocaleString()}
        `;
        ul.appendChild(li);
    });
}

// Gestion du formulaire d'upload (job de test)
document.getElementById('upload-form').addEventListener('submit', async (event) => {
    event.preventDefault();

    const formData = new FormData(event.target);
    const files = formData.getAll('files');

    if (files.length === 0) {
        alert('Veuillez sélectionner au moins une image.');
        return;
    }

    // Job de test simplifié : Batch de 10 copies pour la première image
    const testJob = {
        nom_client: "Test Batch 10",
        reference_externe: "#TEST",
        taches: [{
            type: "BATCH",
            quantite: 1,
            config: {
                image_path: files[0].name,  // Le nom du fichier uploadé
                cut: true,
                label_type: "62",
                rotate: "0"
            }
        }]
    };

    formData.set('command_json', JSON.stringify(testJob));

    try {
        const response = await fetch('/api/jobs', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();
        if (response.ok) {
            alert(`Job créé avec succès! ID: ${result.job_id}`);
            event.target.reset();
        } else {
            alert(`Erreur: ${result.error || 'Erreur inconnue'}`);
        }
    } catch (error) {
        alert(`Erreur réseau: ${error.message}`);
    }
});

// Contrôles du worker (pause/resume)
document.getElementById('pause-btn').addEventListener('click', async () => {
    await fetch('/api/control/pause', { method: 'POST' });
    alert('Worker mis en pause');
});

document.getElementById('resume-btn').addEventListener('click', async () => {
    await fetch('/api/control/resume', { method: 'POST' });
    alert('Worker relancé');
});
