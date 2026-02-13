// Main JavaScript for SONACIP

document.addEventListener('DOMContentLoaded', function() {
    // PWA install prompt handling (Android + iOS)
    let deferredPrompt = null;
    const installButtons = [
        document.getElementById('installAppBtnTop'),
        document.getElementById('installAppBtn'),
        document.getElementById('installAppBtnGuest')
    ].filter(Boolean);
    const installBanner = document.getElementById('pwaInstallBanner');
    const installBannerAction = document.getElementById('pwaInstallAction');
    const installBannerClose = document.getElementById('pwaInstallClose');
    const installDesc = document.getElementById('pwaInstallDesc');
    const installIosHint = document.getElementById('pwaInstallIosHint');
    const isIos = /iphone|ipad|ipod/i.test(navigator.userAgent);
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone;

    function showInstallUI(mode) {
        if (isStandalone) return;
        installButtons.forEach(btn => btn.classList.remove('d-none'));
        if (installBanner) {
            installBanner.style.display = 'flex';
        }
        if (installIosHint) {
            installIosHint.classList.toggle('d-none', mode !== 'ios');
        }
        if (installDesc) {
            installDesc.textContent = mode === 'ios'
                ? 'Aggiungi SONACIP alla schermata home per usarla come app.'
                : 'Aggiungi SONACIP alla schermata home per un accesso rapido.';
        }
        if (installBannerAction) {
            installBannerAction.textContent = mode === 'ios' ? 'Come fare' : 'Installa';
        }
    }

    function hideInstallUI() {
        if (installBanner) {
            installBanner.style.display = 'none';
        }
    }

    function promptInstall() {
        if (deferredPrompt) {
            deferredPrompt.prompt();
            deferredPrompt.userChoice.then(() => {
                deferredPrompt = null;
                hideInstallUI();
            });
            return;
        }
        if (isIos && !isStandalone) {
            showInstallUI('ios');
        }
    }

    window.addEventListener('beforeinstallprompt', (event) => {
        event.preventDefault();
        deferredPrompt = event;
        showInstallUI('prompt');
    });

    installButtons.forEach(btn => {
        btn.addEventListener('click', promptInstall);
    });

    if (installBannerAction) {
        installBannerAction.addEventListener('click', promptInstall);
    }

    if (installBannerClose) {
        installBannerClose.addEventListener('click', hideInstallUI);
    }

    if (isIos && !isStandalone) {
        showInstallUI('ios');
    }

    // Auto-hide alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    const confirmButtons = document.querySelectorAll('[data-confirm-delete], [data-confirm]');
    confirmButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            const msg = this.dataset.confirm || 'Sei sicuro di voler eliminare questo elemento? Questa azione non può essere annullata.';
            if (!confirm(msg)) {
                e.preventDefault();
                e.stopImmediatePropagation();
            }
        });
    });

    document.querySelectorAll('form[data-confirm-submit]').forEach(form => {
        form.addEventListener('submit', function(e) {
            const msg = this.dataset.confirmSubmit || 'Sei sicuro di voler procedere?';
            if (!confirm(msg)) {
                e.preventDefault();
            }
        });
    });

    document.querySelectorAll('[data-tooltip-text]').forEach(el => {
        const tip = document.createElement('div');
        tip.className = 'sonacip-tooltip';
        tip.textContent = el.dataset.tooltipText;
        tip.style.cssText = 'position:absolute;background:#1a1a2e;color:white;padding:6px 12px;border-radius:8px;font-size:0.8rem;white-space:nowrap;z-index:9999;pointer-events:none;opacity:0;transition:opacity 0.2s;';
        document.body.appendChild(tip);
        el.addEventListener('mouseenter', function(ev) {
            const r = this.getBoundingClientRect();
            tip.style.left = r.left + r.width / 2 - tip.offsetWidth / 2 + 'px';
            tip.style.top = r.top - tip.offsetHeight - 8 + window.scrollY + 'px';
            tip.style.opacity = '1';
        });
        el.addEventListener('mouseleave', function() { tip.style.opacity = '0'; });
    });

    document.querySelectorAll('form').forEach(form => {
        const submitBtn = form.querySelector('[type="submit"]');
        if (!submitBtn) return;
        form.addEventListener('submit', function() {
            if (form.checkValidity()) {
                submitBtn.disabled = true;
                const origText = submitBtn.innerHTML;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Invio in corso...';
                setTimeout(() => { submitBtn.disabled = false; submitBtn.innerHTML = origText; }, 8000);
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

    // Notification & message polling for authenticated users
    let _lastNotifCount = -1;
    let _lastMsgCount = -1;

    if (document.querySelector('body[data-user-id]')) {
        updateNotificationCount();
        updateMessageCount();
        setInterval(updateNotificationCount, 30000);
        setInterval(updateMessageCount, 30000);
    }

    if (!document.getElementById('sonacip-pulse-style')) {
        const pulseStyle = document.createElement('style');
        pulseStyle.id = 'sonacip-pulse-style';
        pulseStyle.textContent = '@keyframes badgePulse{0%{transform:scale(1)}50%{transform:scale(1.35)}100%{transform:scale(1)}}.badge-pulse{animation:badgePulse 0.45s ease-in-out 2;}';
        document.head.appendChild(pulseStyle);
    }

    function updateNotificationCount() {
        fetch('/notifications/unread-count', {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(response => response.json())
        .then(data => {
            const count = data.count || 0;
            const isNew = _lastNotifCount >= 0 && count > _lastNotifCount;
            _lastNotifCount = count;

            document.querySelectorAll('.bi-bell-fill').forEach(icon => {
                const link = icon.closest('.sidebar-link') || icon.closest('a');
                if (!link) return;
                let badge = link.querySelector('.sidebar-badge, .notification-badge');
                if (count > 0) {
                    if (!badge) {
                        badge = document.createElement('span');
                        badge.className = 'sidebar-badge';
                        link.appendChild(badge);
                    }
                    badge.textContent = count;
                    badge.style.display = 'inline';
                    if (isNew) {
                        badge.classList.remove('badge-pulse');
                        void badge.offsetWidth;
                        badge.classList.add('badge-pulse');
                    }
                } else if (badge) {
                    badge.style.display = 'none';
                }
            });

            const legacyBadge = document.querySelector('.notification-badge');
            if (legacyBadge) {
                if (count > 0) {
                    legacyBadge.textContent = count;
                    legacyBadge.style.display = 'inline';
                } else {
                    legacyBadge.style.display = 'none';
                }
            }
        })
        .catch(error => console.error('Error:', error));
    }

    function updateMessageCount() {
        fetch('/messages/unread-count', {
            headers: { 'X-Requested-With': 'XMLHttpRequest' }
        })
        .then(response => response.json())
        .then(data => {
            const count = data.count || 0;
            const isNew = _lastMsgCount >= 0 && count > _lastMsgCount;
            _lastMsgCount = count;

            document.querySelectorAll('.bi-envelope, .bi-envelope-fill').forEach(icon => {
                const link = icon.closest('.sidebar-link') || icon.closest('a');
                if (!link) return;
                let badge = link.querySelector('.sidebar-badge, .message-badge');
                if (count > 0) {
                    if (!badge) {
                        badge = document.createElement('span');
                        badge.className = 'sidebar-badge';
                        link.appendChild(badge);
                    }
                    badge.textContent = count;
                    badge.style.display = 'inline';
                    if (isNew) {
                        badge.classList.remove('badge-pulse');
                        void badge.offsetWidth;
                        badge.classList.add('badge-pulse');
                    }
                } else if (badge) {
                    badge.style.display = 'none';
                }
            });
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

    // Privacy cookie bar handling (GDPR-style bottom bar)
    const privacyCookieBar = document.getElementById('privacyCookieBar');
    if (privacyCookieBar) {
        const currentVersion = privacyCookieBar.dataset.privacyVersion || 'v1';
        const storedVersion = localStorage.getItem('sonacipPrivacyVersion');
        const acceptBtn = document.getElementById('acceptPrivacyBtn');
        const rejectBtn = document.getElementById('rejectPrivacyBtn');

        if (storedVersion !== currentVersion) {
            privacyCookieBar.style.display = 'block';
            privacyCookieBar.style.animation = 'slideUpBar 0.4s ease-out';
        }

        const hideBar = () => {
            privacyCookieBar.style.animation = 'slideDownBar 0.3s ease-in forwards';
            setTimeout(() => { privacyCookieBar.style.display = 'none'; }, 300);
        };

        if (acceptBtn) {
            acceptBtn.addEventListener('click', () => {
                localStorage.setItem('sonacipPrivacyVersion', currentVersion);
                hideBar();
            });
        }
        if (rejectBtn) {
            rejectBtn.addEventListener('click', () => {
                localStorage.setItem('sonacipPrivacyVersion', currentVersion + '_rejected');
                hideBar();
            });
        }
    }

    // Ads tracking (impressions) - only after privacy accepted (version stored)
    try {
        const barEl = document.getElementById('privacyCookieBar');
        const privacyVersion = barEl ? (barEl.dataset.privacyVersion || 'v1') : (localStorage.getItem('sonacipPrivacyVersion') || 'v1');
        const accepted = localStorage.getItem('sonacipPrivacyVersion') === privacyVersion;
        if (accepted) {
            const nodes = document.querySelectorAll('[data-ad-impression-url]');
            nodes.forEach(n => {
                const url = n.getAttribute('data-ad-impression-url');
                if (!url) return;
                fetch(url, { method: 'GET', credentials: 'same-origin' }).catch(() => {});
            });
        }
    } catch (e) {}

    // Page loading indicator
    const pageLoader = document.getElementById('pageLoader');
    if (pageLoader) {
        document.addEventListener('click', function(e) {
            const link = e.target.closest('a[href]');
            if (link && !link.target && !link.href.startsWith('javascript:') && !link.href.startsWith('#') && !link.dataset.bsToggle && !link.closest('.ac-dropdown')) {
                pageLoader.style.display = 'block';
            }
        });
        document.querySelectorAll('form').forEach(form => {
            form.addEventListener('submit', () => { pageLoader.style.display = 'block'; });
        });
        window.addEventListener('pageshow', () => { pageLoader.style.display = 'none'; });
    }

    // Theme toggle (light/dark)
    const themeToggles = document.querySelectorAll('[data-theme-toggle]');
    const rootBody = document.body;
    const savedTheme = localStorage.getItem('sonacipTheme');
    if (savedTheme) {
        rootBody.setAttribute('data-theme', savedTheme);
    }
    
    const applyTheme = (mode) => {
        rootBody.setAttribute('data-theme', mode);
        localStorage.setItem('sonacipTheme', mode);
        themeToggles.forEach(btn => {
            btn.innerHTML = mode === 'dark' ? '<i class="bi bi-sun"></i>' : '<i class="bi bi-moon"></i>';
        });
    };
    
    if (themeToggles.length > 0) {
        applyTheme(rootBody.getAttribute('data-theme') || 'light');
        themeToggles.forEach(btn => {
            btn.addEventListener('click', () => {
                const next = rootBody.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
                applyTheme(next);
            });
        });
    }

    // Sidebar toggle for mobile
    const sidebar = document.getElementById('mainSidebar');
    const sidebarToggle = document.getElementById('sidebarToggle');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    
    if (sidebar && sidebarToggle && sidebarOverlay) {
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
            sidebarOverlay.classList.toggle('active');
        });
        
        sidebarOverlay.addEventListener('click', () => {
            sidebar.classList.remove('open');
            sidebarOverlay.classList.remove('active');
        });
        
        sidebar.querySelectorAll('.sidebar-link').forEach(link => {
            link.addEventListener('click', () => {
                if (window.innerWidth < 768) {
                    sidebar.classList.remove('open');
                    sidebarOverlay.classList.remove('active');
                }
            });
        });

        let touchStartX = 0;
        let touchStartY = 0;
        let touchStartTime = 0;
        const SWIPE_THRESHOLD = 50;
        const SWIPE_MAX_Y = 80;
        const EDGE_ZONE = 30;

        document.addEventListener('touchstart', function(e) {
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
            touchStartTime = Date.now();
        }, { passive: true });

        document.addEventListener('touchend', function(e) {
            if (window.innerWidth >= 768) return;
            const dx = e.changedTouches[0].clientX - touchStartX;
            const dy = Math.abs(e.changedTouches[0].clientY - touchStartY);
            const dt = Date.now() - touchStartTime;
            if (dy > SWIPE_MAX_Y || dt > 400) return;

            if (dx > SWIPE_THRESHOLD && touchStartX < EDGE_ZONE && !sidebar.classList.contains('open')) {
                sidebar.classList.add('open');
                sidebarOverlay.classList.add('active');
            }
            if (dx < -SWIPE_THRESHOLD && sidebar.classList.contains('open')) {
                sidebar.classList.remove('open');
                sidebarOverlay.classList.remove('active');
            }
        }, { passive: true });
    }

    // Sidebar collapse toggle for desktop (double-click on brand)
    const sidebarBrand = document.querySelector('.sidebar-brand');
    if (sidebarBrand && sidebar) {
        sidebarBrand.addEventListener('dblclick', () => {
            if (window.innerWidth >= 768) {
                sidebar.classList.toggle('collapsed');
                document.body.classList.toggle('sidebar-collapsed');
                localStorage.setItem('sidebarCollapsed', sidebar.classList.contains('collapsed'));
            }
        });
        
        // Restore collapsed state
        if (localStorage.getItem('sidebarCollapsed') === 'true' && window.innerWidth >= 992) {
            sidebar.classList.add('collapsed');
            document.body.classList.add('sidebar-collapsed');
        }
    }

    // Search Autocomplete
    function initSearchAutocomplete() {
        const searchInputs = document.querySelectorAll('[data-autocomplete], input[name="q"], input[name="query"], #searchConversations');
        searchInputs.forEach(input => {
            if (input.dataset.acInit) return;
            input.dataset.acInit = '1';
            input.setAttribute('autocomplete', 'off');

            const scope = input.dataset.autocompleteScope || 'all';
            const navigateOnSelect = input.dataset.autocompleteNavigate !== 'false';
            let dropdown = null;
            let debounceTimer = null;
            let selectedIdx = -1;
            let results = [];

            function createDropdown() {
                if (dropdown) return dropdown;
                dropdown = document.createElement('div');
                dropdown.className = 'ac-dropdown';
                dropdown.style.cssText = 'position:absolute;z-index:9999;background:white;border-radius:12px;box-shadow:0 4px 24px rgba(0,0,0,0.15);max-height:360px;overflow-y:auto;display:none;min-width:280px;border:1px solid #e4e6ea;';
                const wrapper = input.closest('.position-relative') || input.parentElement;
                wrapper.style.position = 'relative';
                wrapper.appendChild(dropdown);
                return dropdown;
            }

            function renderResults(items) {
                results = items;
                selectedIdx = -1;
                const dd = createDropdown();
                if (!items.length) { dd.style.display = 'none'; return; }

                const typeLabels = {user:'Utente', listing:'Annuncio', event:'Evento', society:'Societ\u00e0'};
                const typeColors = {user:'#1877f2', listing:'#43a047', event:'#fb8c00', society:'#7c4dff'};

                // Clear previous content
                dd.innerHTML = '';
                
                // Create items using DOM methods to prevent XSS
                items.forEach((item, i) => {
                    const link = document.createElement('a');
                    link.href = item.url || '#';
                    link.className = 'ac-item';
                    link.dataset.idx = i;
                    link.style.cssText = 'display:flex;align-items:center;gap:12px;padding:10px 14px;text-decoration:none;color:inherit;cursor:pointer;transition:background 0.15s;border-bottom:1px solid #f0f2f5;';
                    
                    // Avatar
                    if (item.avatar) {
                        const img = document.createElement('img');
                        img.src = item.avatar;
                        img.style.cssText = 'width:36px;height:36px;border-radius:50%;object-fit:cover;';
                        link.appendChild(img);
                    } else {
                        const avatarDiv = document.createElement('div');
                        avatarDiv.style.cssText = 'width:36px;height:36px;border-radius:50%;background:'+(typeColors[item.type]||'#e4e6ea')+';display:flex;align-items:center;justify-content:center;color:white;';
                        const icon = document.createElement('i');
                        icon.className = 'bi ' + (item.icon || 'bi-person');
                        avatarDiv.appendChild(icon);
                        link.appendChild(avatarDiv);
                    }
                    
                    // Text content
                    const textDiv = document.createElement('div');
                    textDiv.style.cssText = 'flex:1;min-width:0;';
                    
                    const titleDiv = document.createElement('div');
                    titleDiv.style.cssText = 'font-weight:600;font-size:0.9rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;';
                    titleDiv.textContent = item.text || '';
                    textDiv.appendChild(titleDiv);
                    
                    const subDiv = document.createElement('div');
                    subDiv.style.cssText = 'font-size:0.78rem;color:#65676b;';
                    subDiv.textContent = item.sub || '';
                    textDiv.appendChild(subDiv);
                    
                    link.appendChild(textDiv);
                    
                    // Type label
                    const typeSpan = document.createElement('span');
                    typeSpan.style.cssText = 'font-size:0.7rem;padding:2px 8px;border-radius:10px;background:'+(typeColors[item.type]||'#e4e6ea')+'20;color:'+(typeColors[item.type]||'#65676b')+';font-weight:600;';
                    typeSpan.textContent = typeLabels[item.type] || item.type || '';
                    link.appendChild(typeSpan);
                    
                    dd.appendChild(link);
                });
                
                dd.style.display = 'block';

                dd.querySelectorAll('.ac-item').forEach(a => {
                    a.addEventListener('mouseenter', function() {
                        dd.querySelectorAll('.ac-item').forEach(x => x.style.background = '');
                        this.style.background = '#f0f2f5';
                        selectedIdx = parseInt(this.dataset.idx);
                    });
                    a.addEventListener('mouseleave', function() { this.style.background = ''; });
                    if (!navigateOnSelect) {
                        a.addEventListener('click', function(ev) {
                            ev.preventDefault();
                            input.value = results[parseInt(this.dataset.idx)].text;
                            dd.style.display = 'none';
                            const form = input.closest('form');
                            if (form) form.submit();
                        });
                    }
                });
            }

            function fetchSuggestions(q) {
                fetch('/api/search-suggestions?q=' + encodeURIComponent(q) + '&scope=' + scope)
                    .then(r => r.json())
                    .then(items => renderResults(items))
                    .catch(() => {});
            }

            input.addEventListener('input', function() {
                const val = this.value.trim();
                clearTimeout(debounceTimer);
                if (val.length < 2) {
                    if (dropdown) dropdown.style.display = 'none';
                    return;
                }
                debounceTimer = setTimeout(() => fetchSuggestions(val), 250);
            });

            input.addEventListener('keydown', function(e) {
                if (!dropdown || dropdown.style.display === 'none') return;
                const items = dropdown.querySelectorAll('.ac-item');
                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    selectedIdx = Math.min(selectedIdx + 1, items.length - 1);
                    items.forEach((x, i) => x.style.background = i === selectedIdx ? '#f0f2f5' : '');
                    items[selectedIdx]?.scrollIntoView({block:'nearest'});
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    selectedIdx = Math.max(selectedIdx - 1, 0);
                    items.forEach((x, i) => x.style.background = i === selectedIdx ? '#f0f2f5' : '');
                    items[selectedIdx]?.scrollIntoView({block:'nearest'});
                } else if (e.key === 'Enter' && selectedIdx >= 0 && selectedIdx < results.length) {
                    e.preventDefault();
                    if (navigateOnSelect) {
                        window.location.href = results[selectedIdx].url;
                    } else {
                        input.value = results[selectedIdx].text;
                        dropdown.style.display = 'none';
                        const form = input.closest('form');
                        if (form) form.submit();
                    }
                } else if (e.key === 'Escape') {
                    dropdown.style.display = 'none';
                }
            });

            input.addEventListener('focus', function() {
                if (this.value.trim().length >= 2 && results.length) {
                    createDropdown().style.display = 'block';
                }
            });

            document.addEventListener('click', function(e) {
                if (dropdown && !dropdown.contains(e.target) && e.target !== input) {
                    dropdown.style.display = 'none';
                }
            });
        });
    }
    initSearchAutocomplete();

    // Calendar grid: clickable cells for creating events
    const calendarCells = document.querySelectorAll('.calendar-cell-clickable');
    const calendarCreateUrl = document.querySelector('[data-calendar-create-url]');
    const baseCreateUrl = calendarCreateUrl ? calendarCreateUrl.dataset.calendarCreateUrl : '/scheduler/calendar/new';
    
    calendarCells.forEach(cell => {
        const handleCellClick = (e) => {
            // Don't trigger if clicking on an existing event link
            if (e.target.closest('a')) return;
            
            const date = cell.dataset.date;
            const hour = cell.dataset.hour;
            if (date) {
                let url = baseCreateUrl + '?date=' + date;
                if (hour) {
                    url += '&hour=' + hour;
                }
                window.location.href = url;
            }
        };
        
        cell.addEventListener('click', handleCellClick);
        
        // Keyboard accessibility
        cell.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                handleCellClick(e);
            }
        });
    });

    // --- Real-time Notification & Message Polling ---
    var userId = document.body.dataset.userId;
    if (userId) {
        var lastNotifCount = -1;
        var lastMsgCount = -1;

        function updateBadges() {
            fetch('/notifications/unread-count', { credentials: 'same-origin' })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    var count = data.count || 0;
                    document.querySelectorAll('.sidebar-link[href*="notifications"] .sidebar-badge, .notif-badge-live').forEach(function(b) {
                        if (count > 0) {
                            b.textContent = count > 99 ? '99+' : count;
                            b.style.display = '';
                        } else {
                            b.style.display = 'none';
                        }
                    });
                    if (lastNotifCount >= 0 && count > lastNotifCount) {
                        showNotifToast(count - lastNotifCount);
                    }
                    lastNotifCount = count;
                }).catch(function() {});

            fetch('/messages/unread-count', { credentials: 'same-origin' })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    var count = data.count || 0;
                    document.querySelectorAll('.sidebar-link[href*="messages"] .sidebar-badge, .msg-badge-live').forEach(function(b) {
                        if (count > 0) {
                            b.textContent = count > 99 ? '99+' : count;
                            b.style.display = '';
                        } else {
                            b.style.display = 'none';
                        }
                    });
                    lastMsgCount = count;
                }).catch(function() {});
        }

        setInterval(updateBadges, 30000);
        setTimeout(updateBadges, 3000);
    }

    // --- Notification Toast ---
    function showNotifToast(newCount) {
        var existing = document.getElementById('sonacipNotifToast');
        if (existing) existing.remove();

        var toast = document.createElement('div');
        toast.id = 'sonacipNotifToast';
        toast.style.cssText = 'position:fixed;top:20px;right:20px;z-index:10000;background:linear-gradient(135deg,#1877f2,#42a5f5);color:#fff;padding:14px 22px;border-radius:14px;box-shadow:0 8px 32px rgba(24,119,242,0.35);font-size:0.95rem;font-weight:500;display:flex;align-items:center;gap:10px;cursor:pointer;animation:slideInRight 0.4s ease;max-width:360px;';
        
        // Secure: Use textContent for user-controlled data
        var icon = document.createElement('i');
        icon.className = 'bi bi-bell-fill';
        icon.style.fontSize = '1.2rem';
        
        var textSpan = document.createElement('span');
        textSpan.textContent = newCount === 1 ? 'Hai una nuova notifica' : 'Hai ' + newCount + ' nuove notifiche';
        
        toast.appendChild(icon);
        toast.appendChild(textSpan);
        
        toast.onclick = function() {
            window.location.href = '/notifications/';
        };
        document.body.appendChild(toast);

        setTimeout(function() {
            toast.style.animation = 'slideOutRight 0.4s ease forwards';
            setTimeout(function() { toast.remove(); }, 400);
        }, 5000);
    }

    // Inject toast animation CSS once
    if (!document.getElementById('notifToastCSS')) {
        var s = document.createElement('style');
        s.id = 'notifToastCSS';
        s.textContent = '@keyframes slideInRight{from{transform:translateX(120%);opacity:0}to{transform:translateX(0);opacity:1}}@keyframes slideOutRight{from{transform:translateX(0);opacity:1}to{transform:translateX(120%);opacity:0}}';
        document.head.appendChild(s);
    }

    // Lazy loading for images - Performance optimization
    if ('loading' in HTMLImageElement.prototype) {
        // Browser supports native lazy loading
        const images = document.querySelectorAll('img:not([loading])');
        images.forEach(img => {
            img.loading = 'lazy';
        });
    } else {
        // Fallback to Intersection Observer for older browsers
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    if (img.dataset.src) {
                        img.src = img.dataset.src;
                        img.removeAttribute('data-src');
                    }
                    observer.unobserve(img);
                }
            });
        }, {
            rootMargin: '50px 0px',
            threshold: 0.01
        });

        document.querySelectorAll('img[data-src]').forEach(img => {
            imageObserver.observe(img);
        });
    }

    // Form validation feedback improvements
    const forms = document.querySelectorAll('form.needs-validation');
    forms.forEach(form => {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
                
                // Show error message for first invalid field
                const firstInvalid = form.querySelector(':invalid');
                if (firstInvalid) {
                    firstInvalid.focus();
                    // Add visual feedback
                    firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }
            form.classList.add('was-validated');
        }, false);
    });

    // Enhanced error messages with better UX
    const errorContainers = document.querySelectorAll('.error-message, .alert-danger');
    errorContainers.forEach(container => {
        if (container.textContent.trim()) {
            container.style.animation = 'shake 0.5s';
        }
    });

    // Add shake animation CSS if not present
    if (!document.getElementById('errorAnimCSS')) {
        const style = document.createElement('style');
        style.id = 'errorAnimCSS';
        style.textContent = `
            @keyframes shake {
                0%, 100% { transform: translateX(0); }
                10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); }
                20%, 40%, 60%, 80% { transform: translateX(5px); }
            }
        `;
        document.head.appendChild(style);
    }

    // Performance monitoring - send to analytics if available
    if (window.performance && window.performance.timing) {
        window.addEventListener('load', function() {
            setTimeout(function() {
                const perfData = window.performance.timing;
                const pageLoadTime = perfData.loadEventEnd - perfData.navigationStart;
                const connectTime = perfData.responseEnd - perfData.requestStart;
                const renderTime = perfData.domComplete - perfData.domLoading;
                
                // Check if in development mode via data attribute on body
                const isDev = document.body.dataset.devMode === 'true' || 
                              window.location.hostname === 'localhost' || 
                              window.location.hostname === '127.0.0.1';
                
                // Only log in development mode
                if (isDev) {
                    console.log('Performance Metrics:', {
                        pageLoadTime: pageLoadTime + 'ms',
                        connectTime: connectTime + 'ms',
                        renderTime: renderTime + 'ms'
                    });
                    
                    if (pageLoadTime > 3000) {
                        console.warn('Slow page load detected:', pageLoadTime + 'ms');
                    }
                }
                
                // Send to analytics endpoint if available (production)
                if (typeof analytics !== 'undefined' && pageLoadTime > 0) {
                    try {
                        // Send performance metrics to backend analytics
                        fetch('/analytics/performance', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({
                                pageLoadTime: pageLoadTime,
                                connectTime: connectTime,
                                renderTime: renderTime,
                                url: window.location.pathname
                            })
                        }).catch(function() {
                            // Silently fail - analytics should never break the app
                        });
                    } catch (e) {
                        // Silently fail
                    }
                }
            }, 0);
        });
    }
});
