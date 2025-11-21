// Configuration des formats d'étiquettes
const LABEL_CONFIGS = {
    '62': { width: 62, height: 29, name: '62mm' },
    '48': { width: 48, height: 25, name: '48mm' },
    '30': { width: 30, height: 21, name: '30mm' }
};

// Variables globales pour l'aperçu
let currentImage = null;
let currentFile = null;

// Fonction pour mettre à jour les contours de marges et indicateurs de dimensions
function updatePreviewLayout(format, rotation) {
    const previewPaper = document.getElementById('preview-canvas').parentNode;
    const existingMargins = previewPaper.querySelector('.preview-margins');
    if (existingMargins) {
        existingMargins.remove();
    }

    if (format === '--') return;

    const labelConfig = LABEL_CONFIGS[format];
    const isRotated = rotation === 90 || rotation === 270;

    // Dimensions utilisables après marges
    const marginLeftRight = 1; // 1mm de chaque côté sur les bords du rouleau
    const marginTopBottom = 1.5; // 1.5mm de chaque côté au niveau des découpes
    const usableWidth = labelConfig.width - (2 * marginLeftRight);
    const usableHeight = labelConfig.height - (2 * marginTopBottom);

    // Dimensions effectives selon la rotation
    const displayWidth = isRotated ? usableHeight : usableWidth;
    const displayHeight = isRotated ? usableWidth : usableHeight;

    // Créer les éléments de marges
    const marginsContainer = document.createElement('div');
    marginsContainer.className = 'preview-margins';

    // Contour des marges (rectangle en pointillés)
    const marginOutline = document.createElement('div');
    marginOutline.className = 'preview-margin-outline';

    // Calculer les dimensions et position du contour de marges
    // L'image fait 400x200px, on doit centrer le contour autour d'elle
    const canvasWidth = 400;
    const canvasHeight = 200;

    // Facteur d'échelle pour s'adapter au canvas
    const scaleFactor = Math.min(canvasWidth / displayWidth, canvasHeight / displayHeight, 1) * 0.8; // Laisser un peu de marge
    const outlineWidth = displayWidth * scaleFactor;
    const outlineHeight = displayHeight * scaleFactor;

    marginOutline.style.width = `${outlineWidth}px`;
    marginOutline.style.height = `${outlineHeight}px`;
    marginOutline.style.left = `${(canvasWidth - outlineWidth) / 2}px`;
    marginOutline.style.top = `${(canvasHeight - outlineHeight) / 2}px`;

    // Indicateurs de dimensions
    const widthIndicator = document.createElement('div');
    widthIndicator.className = 'dimension-indicator horizontal width';
    widthIndicator.textContent = `${displayWidth}mm`;
    widthIndicator.style.left = `${(canvasWidth - outlineWidth) / 2}px`;
    widthIndicator.style.top = `${(canvasHeight - outlineHeight) / 2 - 20}px`;
    widthIndicator.style.width = `${outlineWidth}px`;

    const heightIndicator = document.createElement('div');
    heightIndicator.className = 'dimension-indicator vertical height';
    heightIndicator.textContent = `${displayHeight}mm`;
    heightIndicator.style.left = `${(canvasWidth + outlineWidth) / 2 + 5}px`;
    heightIndicator.style.top = `${(canvasHeight - outlineHeight) / 2}px`;
    heightIndicator.style.height = `${outlineHeight}px`;

    marginsContainer.appendChild(marginOutline);
    marginsContainer.appendChild(widthIndicator);
    marginsContainer.appendChild(heightIndicator);

    previewPaper.appendChild(marginsContainer);
}

// Fonction pour mettre à jour l'aperçu
function updatePreview() {
    const previewCanvas = document.getElementById('preview-canvas');
    const formatSelect = document.getElementById('label_type');
    const rotateSelect = document.getElementById('rotate');

    // Nettoyer le canvas et ses éléments
    previewCanvas.innerHTML = '';
    const existingMargins = previewCanvas.parentNode.querySelector('.preview-margins');
    if (existingMargins) {
        existingMargins.remove();
    }

    if (!currentImage) {
        previewCanvas.innerHTML = '<div class="preview-placeholder"><span>Sélectionnez une image pour voir l\'aperçu</span></div>';
        updateDimensionInfo('--', '0');
        return;
    }

    // Créer l'élément image
    const img = document.createElement('img');
    img.src = currentImage;
    img.className = 'preview-image';
    previewCanvas.appendChild(img);
    updatePreviewLayout(formatSelect.value, rotateSelect.value);
    updateDimensionInfo(formatSelect.value, rotateSelect.value);
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
        // Dimensions utilisables après marges
        const marginLeftRight = 1; // 1mm de chaque côté sur les bords du rouleau
        const marginTopBottom = 1.5; // 1.5mm de chaque côté au niveau des découpes
        const usableWidth = labelConfig.width - (2 * marginLeftRight);
        const usableHeight = labelConfig.height - (2 * marginTopBottom);

        const isRotated = rotation === 90 || rotation === 270;
        const width = isRotated ? usableHeight : usableWidth;
        const height = isRotated ? usableWidth : usableHeight;
        actualSizeSpan.textContent = `Espace image: ${width} x ${height} mm`;
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
