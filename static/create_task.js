// Configuration des formats d'étiquettes
const LABEL_CONFIGS = {
    '62': { width: 62, height: 29, name: '62mm' },
    '48': { width: 48, height: 25, name: '48mm' },
    '30': { width: 30, height: 21, name: '30mm' }
};

// Variables globales pour l'aperçu
let currentImage = null;
let currentFile = null;
let originalImageDimensions = null;

// Initialiser l'aperçu au chargement de la page
document.addEventListener('DOMContentLoaded', () => {
    console.log('Page chargée, initialisation de l\'aperçu');
    updatePreview();
});

// Gestionnaire pour le changement de fichier image
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
        return;
    }

    currentFile = file;

    // Lire le fichier en tant que Data URL
    const reader = new FileReader();
    reader.onload = (e) => {
        currentImage = e.target.result;
        console.log('Image chargée, mise à jour de l\'aperçu');
        updatePreview();
    };
    reader.readAsDataURL(file);
});

// Gestionnaire pour le changement de format
document.getElementById('label_type').addEventListener('change', () => {
    if (currentImage) {
        console.log('Format changé, mise à jour de l\'aperçu');
        updatePreview();
    }
});

// Gestionnaire pour le changement de rotation
document.getElementById('rotate').addEventListener('change', () => {
    if (currentImage) {
        console.log('Rotation changée, mise à jour des informations');
        // Seulement mettre à jour les informations, pas l'aperçu visuel
        const formatSelect = document.getElementById('label_type');
        const rotateSelect = document.getElementById('rotate');

        if (originalImageDimensions) {
            const formatValue = parseInt(formatSelect.value);
            const heightMm = formatValue;
            const widthMm = (originalImageDimensions.width / originalImageDimensions.height) * heightMm;
            const currentRotation = parseInt(rotateSelect.value) || 0;
            updateDimensionInfo(widthMm, heightMm, currentRotation);
        }
    }
});

// Fonction principale pour mettre à jour l'aperçu
function updatePreview() {
    const previewCanvas = document.getElementById('preview-canvas');
    const formatSelect = document.getElementById('label_type');
    const rotateSelect = document.getElementById('rotate');

    // Nettoyer le canvas
    previewCanvas.innerHTML = '';

    if (!currentImage) {
        previewCanvas.innerHTML = '<div class="preview-placeholder"><span>Sélectionnez une image pour voir l\'aperçu</span></div>';
        updateDimensionInfo('--', '--', '0');
        return;
    }

    // Créer une image temporaire pour obtenir les dimensions naturelles
    const tempImg = new Image();
    tempImg.onload = function() {
        console.log('Dimensions originales:', tempImg.naturalWidth, 'x', tempImg.naturalHeight);

        // Stocker les dimensions naturelles
        originalImageDimensions = {
            width: tempImg.naturalWidth,
            height: tempImg.naturalHeight
        };

        console.log('Dimensions originales:', tempImg.naturalWidth, 'x', tempImg.naturalHeight);

        // Calculer les dimensions en millimètres - hauteur toujours = format sélectionné
        const formatValue = parseInt(formatSelect.value);
        const heightMm = formatValue; // Hauteur fixe selon le format
        const widthMm = (tempImg.naturalWidth / tempImg.naturalHeight) * heightMm; // Largeur proportionnelle

        console.log('Dimensions calculées:', widthMm.toFixed(1), 'x', heightMm, 'mm');

        // Créer et ajouter l'image à l'aperçu (rotation seulement dans les paramètres, pas visuellement)
        const imgElement = document.createElement('img');
        imgElement.src = currentImage;
        imgElement.className = 'preview-image';
        // Pas de rotation visuelle dans l'aperçu
        imgElement.style.transform = 'rotate(0deg)';

        // Calculer la taille d'affichage pour que l'image tienne dans le canvas
        const canvasWidth = 380;
        const canvasHeight = 280;

        // Dimensions d'affichage (selon proportions naturelles)
        const displayWidthPx = widthMm * (300 / 25.4);  // Convertir mm vers pixels
        const displayHeightPx = heightMm * (300 / 25.4);

        // Calculer l'échelle pour adapter au canvas
        const scaleX = canvasWidth / displayWidthPx;
        const scaleY = canvasHeight / displayHeightPx;
        const scale = Math.min(scaleX, scaleY, 1);

        imgElement.style.width = (displayWidthPx * scale) + 'px';
        imgElement.style.height = (displayHeightPx * scale) + 'px';
        imgElement.style.maxWidth = '100%';
        imgElement.style.maxHeight = '100%';

        previewCanvas.appendChild(imgElement);

        // Mettre à jour les informations de dimension (sans tenir compte de la rotation pour l'affichage)
        const currentRotation = parseInt(rotateSelect.value) || 0;
        updateDimensionInfo(widthMm, heightMm, currentRotation);
    };

    tempImg.src = currentImage;
}

// Fonction pour mettre à jour les informations de dimensions
function updateDimensionInfo(widthMm, heightMm, rotation) {
    const formatSelect = document.getElementById('label_type');
    const rotateSelect = document.getElementById('rotate');

    if (widthMm === '--' || heightMm === '--') {
        document.getElementById('current-format').textContent = 'Format: --mm';
        document.getElementById('rotation-info').textContent = 'Rotation: 0°';
        document.getElementById('actual-size').textContent = 'Taille réelle: -- x -- mm';
        return;
    }

    const labelConfig = LABEL_CONFIGS[formatSelect.value];

    document.getElementById('current-format').textContent = `Format: ${labelConfig.name}`;
    document.getElementById('rotation-info').textContent = `Rotation: ${rotation}°`;

    // Pour l'affichage, tenir compte de la rotation
    const isRotated = parseInt(rotation) === 90 || parseInt(rotation) === 270;
    const displayWidth = isRotated ? parseFloat(heightMm) : parseFloat(widthMm);
    const displayHeight = isRotated ? parseFloat(widthMm) : parseFloat(heightMm);

    document.getElementById('actual-size').textContent = `Taille réelle: ${displayWidth.toFixed(1)} x ${displayHeight.toFixed(1)} mm`;
}

// Fonction pour réinitialiser l'aperçu
function resetPreview() {
    currentImage = null;
    currentFile = null;
    originalImageDimensions = null;
    updatePreview();
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

    // Créer la tâche
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
                rotate: document.getElementById('rotate').value || '0'
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
            resetPreview();
            setTimeout(() => {
                window.location.href = '/';
            }, 2000);
        } else {
            showMessage('Erreur', result.error || 'Erreur inconnue');
        }
    } catch (error) {
        showMessage('Erreur', 'Erreur réseau');
        console.error('Erreur réseau:', error);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Créer la tâche';
    }
});

// Fonction pour afficher les messages
function showMessage(title, message) {
    const overlay = document.getElementById('message-overlay');
    document.getElementById('message-title').textContent = title;
    document.getElementById('message-text').textContent = message;
    overlay.style.display = 'flex';
}

// Gestionnaire pour fermer le message
document.getElementById('message-close').addEventListener('click', () => {
    document.getElementById('message-overlay').style.display = 'none';
});

console.log('Script create_task.js chargé');
