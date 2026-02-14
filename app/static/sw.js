const CACHE_NAME = 'sonacip-v3';
const STATIC_CACHE = 'sonacip-static-v3';
const ASSETS_TO_CACHE = [
  '/',
  '/static/css/style.css',
  '/static/js/main.js',
  '/static/icons/icon-192x192.png',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css'
];

const OFFLINE_PAGE = `<!DOCTYPE html><html lang="it"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0,viewport-fit=cover"><title>SONACIP - Offline</title><style>*{margin:0;padding:0;box-sizing:border-box}body{min-height:100vh;display:flex;align-items:center;justify-content:center;font-family:Inter,system-ui,-apple-system,sans-serif;background:linear-gradient(135deg,#1877f2 0%,#0d5bbd 100%);color:#fff;padding:24px;text-align:center}.container{max-width:400px}.icon{font-size:4rem;margin-bottom:1.5rem;opacity:.9}h1{font-size:1.5rem;margin-bottom:.75rem;font-weight:700}p{font-size:1rem;opacity:.85;margin-bottom:2rem;line-height:1.6}button{background:#fff;color:#1877f2;border:none;padding:14px 32px;border-radius:12px;font-size:1rem;font-weight:600;cursor:pointer;min-height:44px;transition:transform .2s}button:active{transform:scale(.95)}</style></head><body><div class="container"><div class="icon">📡</div><h1>Sei offline</h1><p>Non è possibile raggiungere SONACIP in questo momento. Controlla la tua connessione internet e riprova.</p><button onclick="location.reload()">Riprova</button></div></body></html>`;

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS_TO_CACHE);
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME && cacheName !== STATIC_CACHE) {
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);

  if (url.pathname.startsWith('/static/') || url.hostname.includes('cdn.jsdelivr.net')) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        if (cached) return cached;
        return fetch(event.request).then((response) => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(STATIC_CACHE).then((cache) => {
              cache.put(event.request, clone);
            });
          }
          return response;
        });
      })
    );
    return;
  }

  if (event.request.headers.get('accept') && event.request.headers.get('accept').includes('text/html')) {
    event.respondWith(
      fetch(event.request).then((response) => {
        if (response && response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, clone);
          });
        }
        return response;
      }).catch(() => {
        return caches.match(event.request).then((cached) => {
          if (cached) return cached;
          return new Response(OFFLINE_PAGE, {
            headers: { 'Content-Type': 'text/html; charset=utf-8' }
          });
        });
      })
    );
    return;
  }

  event.respondWith(
    fetch(event.request).then((response) => {
      return response;
    }).catch(() => {
      return caches.match(event.request);
    })
  );
});

self.addEventListener('push', (event) => {
  let data = { title: 'Sonacip', body: 'Nuova notifica', url: '/', icon: '/static/icons/icon-192x192.png' };

  if (event.data) {
    try {
      data = Object.assign(data, event.data.json());
    } catch (e) {
      data.body = event.data.text();
    }
  }

  const notificationOptions = {
    body: data.body,
    icon: data.icon,
    badge: '/static/icons/icon-192x192.png',
    data: { url: data.url },
    vibrate: [200, 100, 200],
    requireInteraction: false,
    silent: false
  };

  // Add sound to notification (browsers will use default notification sound)
  if (data.sound !== false) {
    notificationOptions.silent = false;
  }

  event.waitUntil(
    self.registration.showNotification(data.title, notificationOptions).then(() => {
      // Update app badge count
      return updateBadgeCount();
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  const urlToOpen = (event.notification.data && event.notification.data.url) ? event.notification.data.url : '/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url.includes(urlToOpen) && 'focus' in client) {
          return client.focus();
        }
      }
      return clients.openWindow(urlToOpen);
    }).then(() => {
      // Update badge count when notification is clicked
      return updateBadgeCount();
    })
  );
});

// Function to update app badge count
async function updateBadgeCount() {
  try {
    // Try to get unread count from the API
    const response = await fetch('/notifications/unread-count', {
      credentials: 'same-origin'
    });
    
    if (response.ok) {
      const data = await response.json();
      const count = data.count || 0;
      
      // Update badge using Badge API if available
      if ('setAppBadge' in navigator) {
        if (count > 0) {
          await navigator.setAppBadge(count);
        } else {
          await navigator.clearAppBadge();
        }
      }
    }
  } catch (error) {
    console.log('Could not update badge:', error);
  }
}
