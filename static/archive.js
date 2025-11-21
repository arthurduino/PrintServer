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
            const totalQuantity = job.taches.reduce((sum, task) => sum + task.quantite_totale, 0);
            const completedDate = new Date(job.date_creation);

            return `
                <div class="completed-item">
                    <div class="completed-header">
                        <strong>Tâche ${job.id}</strong>
                        <span class="status-completed">Terminée</span>
                    </div>
                    <div class="completed-details">
                        <span>${totalQuantity} exemplaire(s)</span>
                        <small>Terminée le ${completedDate.toLocaleString()}</small>
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
