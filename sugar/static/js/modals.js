function showNotification(message, status = 'success') {
    const container = document.body;

    const notification = document.createElement('div');
    const bgColor = status === 'success' ? 'bg-indigo-600' : 'bg-red-500';

    // Base classes for the notification
    notification.className = `fixed top-5 right-5 p-4 rounded-lg text-white shadow-lg z-50 transform transition-all duration-300 ease-in-out flex items-center justify-between`;

    // Start off-screen
    notification.classList.add('translate-x-full');

    // Add color
    notification.classList.add(bgColor);

    const messageSpan = document.createElement('span');
    messageSpan.textContent = message;
    notification.appendChild(messageSpan);

    const closeButton = document.createElement('button');
    closeButton.innerHTML = '&times;'; // '×' character
    closeButton.className = 'ml-4 text-white text-lg font-bold leading-none hover:text-gray-200 focus:outline-none';
    notification.appendChild(closeButton);

    container.appendChild(notification);

    // Function to close the notification
    const closeNotification = () => {
        notification.classList.add('translate-x-full');
        notification.addEventListener('transitionend', () => notification.remove(), { once: true });
    };

    // Animate in
    setTimeout(() => {
        notification.classList.remove('translate-x-full');
    }, 100);

    // Set timeout to animate out and then remove
    const autoCloseTimeout = setTimeout(closeNotification, 5000);

    // Add event listener to close button
    closeButton.addEventListener('click', () => {
        clearTimeout(autoCloseTimeout); // Clear auto-close timeout if manually closed
        closeNotification();
    });
}

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
