document.addEventListener('DOMContentLoaded', () => {
    // Function to show a modal
    const showModal = (modal) => {
        if (modal) {
            modal.classList.remove('hidden');
        }
    };

    // Function to hide a modal
    const hideModal = (modal) => {
        if (modal) {
            modal.classList.add('hidden');
        }
    };

    // Add event listeners to all modal open triggers
    document.querySelectorAll('[data-modal-show]').forEach(trigger => {
        trigger.addEventListener('click', () => {
            const modal = document.getElementById(trigger.dataset.modalShow);
            showModal(modal);
        });
    });

    // Add event listeners to all modal hide triggers
    document.querySelectorAll('[data-modal-hide]').forEach(trigger => {
        trigger.addEventListener('click', () => {
            const modal = document.getElementById(trigger.dataset.modalHide);
            hideModal(modal);
        });
    });

    // Add event listeners for clicks on modal overlays to close them
    document.querySelectorAll('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (event) => {
            // Make sure the click is on the overlay itself, not on a child element (the modal content)
            if (event.target === overlay) {
                const modal = overlay.closest('[role="dialog"]');
                hideModal(modal);
            }
        });
    });
});
