document.addEventListener('DOMContentLoaded', function () {
    // --- Training Logic ---
    const trainButton = document.getElementById('train-all-btn');
    const confirmTrainBtn = document.getElementById('confirm-train-btn');

    if (confirmTrainBtn && trainButton) {
        const trainingUrl = trainButton.dataset.trainingUrl;
        const csrfToken = trainButton.dataset.csrfToken;

        confirmTrainBtn.addEventListener('click', function () {
            const originalContent = trainButton.innerHTML;
            trainButton.disabled = true;
            trainButton.innerHTML = `<svg class="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>`;

            fetch(trainingUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({})
            })
                .then(response => {
                    if (response.status === 409) {
                        return response.json().then(err => {
                            throw new Error(err.error || 'A training task is already in progress.');
                        });
                    }
                    if (!response.ok) {
                        return response.json().then(err => {
                            throw new Error(err.error || 'Unknown server error.');
                        });
                    }
                    return response.json();
                })
                .then(data => {
                    alert('Model training has started in the background. The "Last trained" date will update upon completion, and you can reload the page to see new results.');
                    setTimeout(() => {
                        location.reload();
                    }, 5000);
                })
                .catch(error => {
                    console.error('Error starting training:', error.message);
                    alert('Failed to start training: ' + error.message);
                    trainButton.disabled = false;
                    trainButton.innerHTML = originalContent;
                });
        });
    }

    // --- Delete Logic ---
    const deleteConfirmationModal = document.getElementById('delete-confirmation-modal');
    const confirmDeleteBtn = document.getElementById('confirm-delete-btn');
    const deleteFilenameSpan = document.getElementById('delete-filename');
    let fileIdToDelete = null;

    document.querySelectorAll('.delete-file-btn').forEach(button => {
        button.addEventListener('click', function () {
            fileIdToDelete = this.dataset.fileid;
            if (deleteFilenameSpan) {
                deleteFilenameSpan.textContent = this.dataset.filename;
            }
        });
    });

    if (confirmDeleteBtn) {
        confirmDeleteBtn.addEventListener('click', function () {
            if (fileIdToDelete) {
                const csrfToken = this.dataset.csrfToken;
                const form = document.createElement('form');
                form.method = 'POST';
                form.action = `/delete/${fileIdToDelete}/`;
                form.innerHTML = `<input type="hidden" name="csrfmiddlewaretoken" value="${csrfToken}">`;
                document.body.appendChild(form);
                form.submit();
            }
            if (deleteConfirmationModal) {
                deleteConfirmationModal.classList.add('hidden');
            }
        });
    }

    // --- Custom File Input Logic for Upload Modal ---
    const excelFileUploadUI = document.getElementById('excel-file-upload'); // The visible but hidden file input for UI interaction
    const excelFileUploadForm = document.getElementById('excel-file-upload-for-form'); // The file input actually inside the form
    const fileNameDisplay = document.getElementById('file-name-display');
    const submitUploadBtn = document.getElementById('submit-upload-btn');
    const hiddenUploadForm = document.getElementById('hidden-upload-form');

    if (excelFileUploadUI && fileNameDisplay && submitUploadBtn && excelFileUploadForm) {
        excelFileUploadUI.addEventListener('change', function () {
            if (this.files && this.files.length > 0) {
                fileNameDisplay.textContent = this.files[0].name;
                submitUploadBtn.disabled = false; // Enable submit button

                // Crucial: Transfer the selected file(s) to the form's input
                // This creates a new DataTransfer object and assigns its files to the form's input
                const dataTransfer = new DataTransfer();
                for (let i = 0; i < this.files.length; i++) {
                    dataTransfer.items.add(this.files[i]);
                }
                excelFileUploadForm.files = dataTransfer.files;

            } else {
                fileNameDisplay.textContent = 'No file chosen';
                submitUploadBtn.disabled = true; // Disable submit button
                excelFileUploadForm.files = new DataTransfer().files; // Clear files from the form's input
            }
        });
    }

    // Add event listener to the UI upload button to submit the hidden form
    submitUploadBtn.addEventListener('click', function () {
        if (!this.disabled) { // Only submit if the button is enabled
            hiddenUploadForm.submit();
        }
    });
});
