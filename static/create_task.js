// Configuration des formats d'étiquettes
const LABEL_CONFIGS = {
    '62': { width: 62, height: 29, name: '62mm' },
    '48': { width: 48, height: 25, name: '48mm' },
    '30': { width: 30, height: 21, name: '30mm' }
};

// Variables globales pour l'aperçu
let currentImage = null;
let currentFile = null;

// Fonction pour mettre à jour l'aperçu
function updatePreview() {
    const previewCanvas = document.getElementById('preview-canvas');
    const formatSelect = document.getElementById('label_type');
    const rotateSelect = document.getElementById('rotate');

    // Nettoyer le canvas
    previewCanvas.innerHTML = '';

    if (!currentImage) {
        previewCanvas.innerHTML = '<div class="preview-placeholder"><span>Sélectionnez une image pour voir l\'aperçu</span></div>';
        updateDimensionInfo('--', '0');
        return;
    }

    // Créer l'élément image
    const img = document.createElement('img');
    img.src = currentImage;
    img.className = 'preview-image';

    // Appliquer la rotation
    const rotation = parseInt(rotateSelect.value) || 0;
    img.style.transform = `rotate(${rotation}deg)`;

    // Calculer les dimensions affichées
    const labelConfig = LABEL_CONFIGS[formatSelect.value];
    const dpi = 300; // Supposons 300 DPI
    const pixelsPerMm = dpi / 25.4; // Conversion mm vers pixels
    const displayWidth = labelConfig.width * pixelsPerMm;
    const displayHeight = labelConfig.height * pixelsPerMm;

    // Pour les rotations de 90° et 270°, échanger largeur/hauteur
    const isRotated = rotation === 90 || rotation === 270;
    const actualDisplayWidth = isRotated ? displayHeight : displayWidth;
    const actualDisplayHeight = isRotated ? displayWidth : displayHeight;

    // Mettre à l'échelle pour l'aperçu (adapter l'image au canvas)
    const canvasWidth = 380; // Largeur disponible dans le canvas (moins les marges)
    const canvasHeight = 280; // Hauteur disponible dans le canvas (moins les marges)

    const scaleX = canvasWidth / actualDisplayWidth;
    const scaleY = canvasHeight / actualDisplayHeight;
    const scaleFactor = Math.min(scaleX, scaleY, 1); // Ne pas agrandir l'image

    img.style.width = `${actualDisplayWidth * scaleFactor}px`;
    img.style.height = `${actualDisplayHeight * scaleFactor}px`;
    img.style.maxWidth = '100%';
    img.style.maxHeight = '100%';

    previewCanvas.appendChild(img);
    updateDimensionInfo(formatSelect.value, rotation);
}

// Fonction pour mettre à jour les informations de dimension
function updateDimensionInfo(format, rotation) {
    const currentFormatSpan = document.getElementById('current-format');
    const rotationInfoSpan = document.getElementById('rotation-info');
    const actualSizeSpan = document.getElementById('actual-size');

    if (format === '--') {
        currentFormatSpan.textContent = 'Format: --mm';
        rotationInfoSpan.textContent = 'Rotation: 0°';
        actualSizeSpan.textContent = 'Taille réelle: -- x -- mm';
        return;
    }

    const labelConfig = LABEL_CONFIGS[format];
    currentFormatSpan.textContent = `Format: ${labelConfig.name}`;
    rotationInfoSpan.textContent = `Rotation: ${rotation}°`;

    if (labelConfig) {
        const isRotated = rotation === 90 || rotation === 270;
        const width = isRotated ? labelConfig.height : labelConfig.width;
        const height = isRotated ? labelConfig.width : labelConfig.height;
        actualSizeSpan.textContent = `Taille réelle: ${width} x ${height} mm`;
    }
}

// Gestionnaire pour le changement de fichier
document.getElementById('files').addEventListener('change', async (event) => {
    const file = event.target.files[0];
    if (!file) {
        currentImage = null;
        currentFile = null;
        updatePreview();
        return;
    }

    if (!file.type.startsWith('image/')) {
        showMessage('Erreur', 'Veuillez sélectionner un fichier image valide');
        event.target.value = '';
        return;
    }

    currentFile = file;

    // Lire le fichier en tant que Data URL
    const reader = new FileReader();
    reader.onload = (e) => {
        currentImage = e.target.result;
        updatePreview();
    };
    reader.readAsDataURL(file);
});

// Gestionnaires pour les changements de paramètres
document.getElementById('label_type').addEventListener('change', updatePreview);
document.getElementById('rotate').addEventListener('change', updatePreview);

// Fonction pour réinitialiser l'aperçu
function resetPreview() {
    currentImage = null;
    currentFile = null;
    updatePreview();
}

// Initialiser l'aperçu au chargement
document.addEventListener('DOMContentLoaded', () => {
    updatePreview();
});

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
            resetPreview(); // Réinitialiser l'aperçu
            // Rediriger vers la page d'accueil après un délai
            setTimeout(() => {
                window.location.href = '/';
            }, 2000);
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
