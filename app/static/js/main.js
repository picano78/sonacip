// Main JavaScript for SONACIP

document.addEventListener('DOMContentLoaded', function() {
    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    // Confirm delete actions
    const deleteButtons = document.querySelectorAll('[data-confirm-delete]');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            if (!confirm('Sei sicuro di voler eliminare questo elemento?')) {
                e.preventDefault();
            }
        });
    });

    // AJAX like button functionality
    const likeButtons = document.querySelectorAll('.like-button');
    likeButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            const postId = this.dataset.postId;
            const url = `/social/post/${postId}/like`;
            
            fetch(url, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCsrfToken()
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const icon = this.querySelector('i');
                    const count = this.querySelector('.like-count');
                    
                    if (data.liked) {
                        icon.classList.remove('bi-heart');
                        icon.classList.add('bi-heart-fill');
                    } else {
                        icon.classList.remove('bi-heart-fill');
                        icon.classList.add('bi-heart');
                    }
                    
                    if (count) {
                        count.textContent = data.likes_count;
                    }
                }
            })
            .catch(error => console.error('Error:', error));
        });
    });

    // Get CSRF token from meta tag or form
    function getCsrfToken() {
        const token = document.querySelector('meta[name="csrf-token"]');
        if (token) {
            return token.content;
        }
        
        const input = document.querySelector('input[name="csrf_token"]');
        if (input) {
            return input.value;
        }
        
        return '';
    }

    // Image preview for file uploads
    const imageInputs = document.querySelectorAll('input[type="file"][accept*="image"]');
    imageInputs.forEach(input => {
        input.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    // Create or update preview
                    let preview = input.parentElement.querySelector('.image-preview');
                    if (!preview) {
                        preview = document.createElement('img');
                        preview.className = 'image-preview img-thumbnail mt-2';
                        preview.style.maxWidth = '200px';
                        input.parentElement.appendChild(preview);
                    }
                    preview.src = e.target.result;
                };
                reader.readAsDataURL(file);
            }
        });
    });

    // Character counter for textareas
    const textareas = document.querySelectorAll('textarea[data-max-length]');
    textareas.forEach(textarea => {
        const maxLength = parseInt(textarea.dataset.maxLength);
        const counter = document.createElement('small');
        counter.className = 'text-muted';
        textarea.parentElement.appendChild(counter);
        
        function updateCounter() {
            const remaining = maxLength - textarea.value.length;
            counter.textContent = `${remaining} caratteri rimanenti`;
            
            if (remaining < 0) {
                counter.classList.add('text-danger');
            } else {
                counter.classList.remove('text-danger');
            }
        }
        
        textarea.addEventListener('input', updateCounter);
        updateCounter();
    });

    // Notification polling (optional - check for new notifications)
    if (document.querySelector('.notification-icon')) {
        setInterval(updateNotificationCount, 60000); // Every minute
    }

    function updateNotificationCount() {
        fetch('/notifications/unread-count', {
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        })
        .then(response => response.json())
        .then(data => {
            const badge = document.querySelector('.notification-badge');
            if (badge) {
                if (data.count > 0) {
                    badge.textContent = data.count;
                    badge.style.display = 'inline';
                } else {
                    badge.style.display = 'none';
                }
            }
        })
        .catch(error => console.error('Error:', error));
    }

    // Form validation enhancement
    const forms = document.querySelectorAll('.needs-validation');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!form.checkValidity()) {
                e.preventDefault();
                e.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });

    // Back to top button
    const backToTopButton = document.createElement('button');
    backToTopButton.innerHTML = '<i class="bi bi-arrow-up"></i>';
    backToTopButton.className = 'btn btn-primary position-fixed bottom-0 end-0 m-3 rounded-circle';
    backToTopButton.style.display = 'none';
    backToTopButton.style.width = '50px';
    backToTopButton.style.height = '50px';
    backToTopButton.style.zIndex = '1000';
    document.body.appendChild(backToTopButton);

    window.addEventListener('scroll', () => {
        if (window.scrollY > 300) {
            backToTopButton.style.display = 'block';
        } else {
            backToTopButton.style.display = 'none';
        }
    });

    backToTopButton.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    // Privacy banner modal handling (configurable by super admin)
    const privacyModalEl = document.getElementById('privacyModal');
    if (privacyModalEl) {
        const currentVersion = privacyModalEl.dataset.privacyVersion || 'v1';
        const storedVersion = localStorage.getItem('sonacipPrivacyVersion');
        const privacyModal = new bootstrap.Modal(privacyModalEl);
        const acceptBtn = document.getElementById('acceptPrivacyBtn');

        if (storedVersion !== currentVersion) {
            privacyModal.show();
        }

        if (acceptBtn) {
            acceptBtn.addEventListener('click', () => {
                localStorage.setItem('sonacipPrivacyVersion', currentVersion);
                privacyModal.hide();
            });
        }
    }
});
