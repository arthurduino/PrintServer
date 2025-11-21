// Configuration des formats d'étiquettes
const LABEL_CONFIGS = {
    '62': { width: 62, height: 29, name: '62mm' },
    '48': { width: 48, height: 25, name: '48mm' },
    '30': { width: 30, height: 21, name: '30mm' }
};

// Variables globales pour l'aperçu
let currentImage = null;
let currentFile = null;
let originalImageDimensions = null; // Stocke les dimensions originales de l'image

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

    // Créer l'élément image temporaire pour obtenir les dimensions naturelles
    const tempImg = new Image();
    tempImg.onload = () => {
        // Stocker les dimensions naturelles
        originalImageDimensions = {
            width: tempImg.naturalWidth,
            height: tempImg.naturalHeight
        };

        // Maintenant créer l'image affichée
        const img = document.createElement('img');
        img.src = currentImage;
        img.className = 'preview-image';

        // Déterminer si l'image originale est en paysage ou portrait
        const originalWidth = originalImageDimensions.width;
        const originalHeight = originalImageDimensions.height;
        const isLandscape = originalWidth >= originalHeight;

        // Sélectionner automatiquement la rotation selon l'orientation
        const autoRotation = isLandscape ? 0 : 90;
        rotateSelect.value = autoRotation.toString();
        img.style.transform = `rotate(${autoRotation}deg)`;

        // Toujours hauteur = 62mm (format sélectionné), largeur proportionnelle
        const labelConfig = LABEL_CONFIGS[formatSelect.value];
        const heightMm = labelConfig.width; // Hauteur toujours = format sélectionné
        const widthMm = (originalWidth / originalHeight) * heightMm; // Largeur proportionnelle

        // Calculer les dimensions selon la rotation automatique
        let displayWidthMm, displayHeightMm;
        if (isLandscape) {
            // Paysage avec rotation 0° : largeur naturelle, hauteur fixe
            displayWidthMm = widthMm;
            displayHeightMm = heightMm;
        } else {
            // Portrait avec rotation 90° : tourner donc hauteur devient largeur, etc.
            displayWidthMm = heightMm; // Après rotation 90°, l'ancienne hauteur devient largeur
            displayHeightMm = widthMm; // L'ancienne largeur proportionnelle devient hauteur
        }

        // Convertir en pixels pour l'affichage
        const dpi = 300;
        const pixelsPerMm = dpi / 25.4;
        const displayWidthPx = displayWidthMm * pixelsPerMm;
        const displayHeightPx = displayHeightMm * pixelsPerMm;

        // Pour les rotations de 90° et 270°, échanger largeur/hauteur
        const isRotated = autoRotation === 90 || autoRotation === 270;
        const actualDisplayWidthPx = isRotated ? displayHeightPx : displayWidthPx;
        const actualDisplayHeightPx = isRotated ? displayWidthPx : displayHeightPx;

        // Mettre à l'échelle pour l'aperçu (adapter l'image au canvas)
        const canvasWidth = 380;
        const canvasHeight = 280;

        const scaleX = canvasWidth / actualDisplayWidthPx;
        const scaleY = canvasHeight / actualDisplayHeightPx;
        const scaleFactor = Math.min(scaleX, scaleY, 1);

        img.style.width = `${actualDisplayWidthPx * scaleFactor}px`;
        img.style.height = `${actualDisplayHeightPx * scaleFactor}px`;
        img.style.maxWidth = '100%';
        img.style.maxHeight = '100%';

        previewCanvas.appendChild(img);
        updateDimensionInfo(displayWidthMm, displayHeightMm, autoRotation);
    };
    tempImg.src = currentImage;
}

// Fonction pour mettre à jour les informations de dimension
function updateDimensionInfo(displayWidthMm, displayHeightMm, rotation) {
    const currentFormatSpan = document.getElementById('current-format');
    const rotationInfoSpan = document.getElementById('rotation-info');
    const actualSizeSpan = document.getElementById('actual-size');

    if (displayWidthMm === '--') {
        currentFormatSpan.textContent = 'Format: --mm';
        rotationInfoSpan.textContent = 'Rotation: 0°';
        actualSizeSpan.textContent = 'Taille réelle: -- x -- mm';
        return;
    }

    // Trouver le format actuel sélectionné
    const formatSelect = document.getElementById('label_type');
    const labelConfig = LABEL_CONFIGS[formatSelect.value];

    currentFormatSpan.textContent = `Format: ${labelConfig.name}`;
    rotationInfoSpan.textContent = `Rotation: ${rotation}°`;

    // Pour les rotations de 90° et 270°, échanger largeur/hauteur dans l'affichage
    const isRotated = rotation === 90 || rotation === 270;
    const actualWidthDisplay = isRotated ? displayHeightMm : displayWidthMm;
    const actualHeightDisplay = isRotated ? displayWidthMm : displayHeightMm;

    actualSizeSpan.textContent = `Taille réelle: ${actualWidthDisplay.toFixed(1)} x ${actualHeightDisplay.toFixed(1)} mm`;
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
    originalImageDimensions = null;
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
