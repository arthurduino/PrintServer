// Chargement initial et périodique des tâches terminées
loadCompletedJobs();

setInterval(() => {
    loadCompletedJobs();
}, 30000); // Rafraîchissement toutes les 30 secondes

async function loadCompletedJobs() {
    try {
        const response = await fetch('/api/jobs');
        const jobs = await response.json();

        // Debug info
        const debugEl = document.getElementById('debug-info');
        debugEl.innerHTML = `
            Total tâches: ${jobs.length}<br>
            Tâches DONE: ${jobs.filter(j => j.statut === 'DONE').length}<br>
            Tâches PROCESSING: ${jobs.filter(j => j.statut === 'PROCESSING').length}<br>
            Tâches PENDING: ${jobs.filter(j => j.statut === 'PENDING').length}<br>
            Statuts: ${[...new Set(jobs.map(j => j.statut))].join(', ')}
        `;

        const completedJobs = jobs.filter(job => job.statut === 'DONE');

        if (completedJobs.length === 0) {
            document.getElementById('completed-jobs').innerHTML = '<p>Aucune tâche terminée</p>';
            return;
        }

        // Trier par date de création (plus récent en premier)
        completedJobs.sort((a, b) => new Date(b.date_creation) - new Date(a.date_creation));

        const jobsHtml = completedJobs.map(job => {
            const jobDate = new Date(job.date_creation);
            const taskDetails = job.taches.map(task => {
                const isCompleted = task.statut === 'DONE';
                const isErrored = task.statut === 'ERROR';
                const wasProcessing = task.statut === 'IN_PROGRESS';

                let statusClass = 'status-completed';
                let statusText = 'Terminée';
                let statusIcon = '✅';

                if (isErrored) {
                    statusClass = 'status-error';
                    statusText = 'Erreur';
                    statusIcon = '❌';
                } else if (wasProcessing) {
                    statusClass = 'status-interrupted';
                    statusText = 'Interrompue';
                    statusIcon = '⚠️';
                }

                return `
                    <div class="archive-task-item ${isErrored ? 'error-task' : wasProcessing ? 'interrupted-task' : ''}">
                        <div class="task-header">
                            <strong>${statusIcon} Tâche #${task.id}</strong>
                            <span class="task-status ${statusClass}">${statusText}</span>
                        </div>
                        <div class="task-details">
                            <div class="task-progress-info">
                                <span class="progress-text">${task.quantite_faite}/${task.quantite_totale} exemplaires</span>
                                <small>${task.type_tache} - ${job.nom_client}</small>
                            </div>
                            ${task.config && task.config.image_path ?
                                `<div class="task-image-name">📄 ${task.config.image_path}</div>` : ''}
                        </div>
                        ${task.statut === 'ERROR' ?
                            `<div class="error-details">💥 Tâche interrompue en cours d'impression</div>` : ''}
                        ${task.statut === 'IN_PROGRESS' ?
                            `<div class="interrupted-details">⏸️ Tâche interrompue après ${task.quantite_faite} impressions</div>` : ''}
                    </div>
                `;
            }).join('');

            return `
                <div class="archive-job-card">
                    <div class="job-summary">
                        <h4>Commande #${job.id} - ${job.nom_client}</h4>
                        <div class="job-meta">
                            <span class="completion-date">Terminée le ${jobDate.toLocaleString()}</span>
                            <span class="total-stats">${job.taches.length} tâche(s) • ${job.taches.reduce((sum, t) => sum + t.quantite_faite, 0)}/${job.taches.reduce((sum, t) => sum + t.quantite_totale, 0)} exemplaires</span>
                        </div>
                    </div>
                    <div class="job-tasks">
                        ${taskDetails}
                    </div>
                </div>
            `;
        }).join('');

        document.getElementById('completed-jobs').innerHTML = jobsHtml;

    } catch (error) {
        console.error('Erreur chargement archive:', error);
        document.getElementById('completed-jobs').innerHTML = '<p>Erreur de chargement</p>';
    }
}
