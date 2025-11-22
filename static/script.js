// Mise à jour périodique
async function updateInterface(delay = 1000) {
    setTimeout(async () => {
        try {
            const statusResponse = await fetch('/api/printer/status');
            const jobsResponse = await fetch('/api/jobs');

            if (statusResponse.ok && jobsResponse.ok) {
                const statusData = await statusResponse.json();
                const jobs = await jobsResponse.json();

                updatePrinterStatus(statusData);
                updateJobList(jobs);

                const isPrinting = statusData.status === 'Busy' || jobs.some(job => job.statut === 'PROCESSING');
                updateInterface(isPrinting ? 500 : 1000);
            } else {
                updateInterface(3000);
            }
        } catch (error) {
            updateInterface(3000);
        }
    }, delay);
}

document.addEventListener('DOMContentLoaded', () => {
    updateInterface();
});

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
