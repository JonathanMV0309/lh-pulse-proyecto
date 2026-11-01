document.addEventListener('DOMContentLoaded', function () {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('archivoInput');
    const fileInfo = document.getElementById('fileInfo');
    const fileName = document.getElementById('fileName');
    const fileSize = document.getElementById('fileSize');
    const clearFileBtn = document.getElementById('clearFileBtn');
    const submitBtn = document.getElementById('submitBtn');
    const importForm = document.getElementById('importForm');
    const btnText = document.getElementById('btnText');
    const btnSpinner = document.getElementById('btnSpinner');

    const allowedExtensions = ['.xlsx', '.xls'];

    function isValidFile(file) {
        if (!file) return false;
        const name = file.name.toLowerCase();
        return allowedExtensions.some(ext => name.endsWith(ext));
    }

    function showFileInfo(file) {
        fileName.textContent = file.name;
        fileSize.textContent = formatBytes(file.size);
        fileInfo.classList.remove('d-none');
        submitBtn.disabled = false;
    }

    function hideFileInfo() {
        fileInfo.classList.add('d-none');
        fileName.textContent = '';
        fileSize.textContent = '';
        submitBtn.disabled = true;
    }

    function resetInput() {
        fileInput.value = '';
        hideFileInfo();
        dropZone.classList.remove('drag-over');
    }

    function formatBytes(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function handleFile(file) {
        if (!file) return;
        if (!isValidFile(file)) {
            alert('Selecciona un archivo Excel válido (.xlsx o .xls).');
            resetInput();
            return;
        }
        showFileInfo(file);
    }

    // ==================== Eventos de selección ====================
    fileInput.addEventListener('change', function () {
        if (this.files && this.files.length > 0) {
            handleFile(this.files[0]);
        } else {
            resetInput();
        }
    });

    // Click en dropZone abre selector
    dropZone.addEventListener('click', function () {
        fileInput.click();
    });

    // Soporte teclado (accesibilidad)
    dropZone.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            fileInput.click();
        }
    });

    // Drag & Drop
    dropZone.addEventListener('dragover', function (e) {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', function (e) {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', function (e) {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            const file = e.dataTransfer.files[0];
            // Asignar al input para que se envíe (solución compatible)
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);
            fileInput.files = dataTransfer.files;
            handleFile(file);
        }
    });

    // Limpiar selección
    clearFileBtn.addEventListener('click', function () {
        resetInput();
    });

    // ==================== Prevención de doble envío ====================
    importForm.addEventListener('submit', function (e) {
        const file = fileInput.files[0];
        if (!file || !isValidFile(file)) {
            e.preventDefault();
            alert('Debe seleccionar un archivo Excel válido (.xlsx o .xls).');
            return false;
        }

        // Desactivar botón y mostrar spinner
        submitBtn.disabled = true;
        btnText.innerHTML = 'Importando...';
        btnText.classList.remove('d-none');
        btnSpinner.classList.remove('d-none');

        // No bloqueamos el envío; la recarga mostrará los mensajes flash
    });
});