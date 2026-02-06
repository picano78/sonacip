(function() {
  'use strict';

  function isPushSupported() {
    return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  }

  function urlBase64ToUint8Array(base64String) {
    var padding = '='.repeat((4 - base64String.length % 4) % 4);
    var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    var rawData = window.atob(base64);
    var outputArray = new Uint8Array(rawData.length);
    for (var i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }

  function getVapidKey() {
    return fetch('/notifications/push/vapid-key', {
      credentials: 'same-origin'
    }).then(function(resp) {
      return resp.json();
    }).then(function(data) {
      return data.publicKey || '';
    });
  }

  function subscribeToPush() {
    if (!isPushSupported()) return Promise.resolve(null);

    return Notification.requestPermission().then(function(permission) {
      if (permission !== 'granted') return null;

      return getVapidKey().then(function(vapidKey) {
        if (!vapidKey) return null;

        return navigator.serviceWorker.ready.then(function(registration) {
          return registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(vapidKey)
          });
        }).then(function(subscription) {
          var subJson = subscription.toJSON();
          return fetch('/notifications/push/subscribe', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              endpoint: subJson.endpoint,
              keys: {
                p256dh: subJson.keys.p256dh,
                auth: subJson.keys.auth
              }
            })
          }).then(function() {
            return subscription;
          });
        });
      });
    }).catch(function(err) {
      console.warn('Push subscription failed:', err);
      return null;
    });
  }

  function unsubscribeFromPush() {
    if (!isPushSupported()) return Promise.resolve(false);

    return navigator.serviceWorker.ready.then(function(registration) {
      return registration.pushManager.getSubscription();
    }).then(function(subscription) {
      if (!subscription) return false;

      var endpoint = subscription.endpoint;
      return subscription.unsubscribe().then(function() {
        return fetch('/notifications/push/unsubscribe', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ endpoint: endpoint })
        });
      }).then(function() {
        return true;
      });
    }).catch(function(err) {
      console.warn('Push unsubscribe failed:', err);
      return false;
    });
  }

  function autoSubscribe() {
    var body = document.body;
    var userId = body.getAttribute('data-user-id');
    if (!userId) return;
    if (!isPushSupported()) return;

    if (Notification.permission === 'denied') return;

    navigator.serviceWorker.ready.then(function(registration) {
      return registration.pushManager.getSubscription();
    }).then(function(subscription) {
      if (!subscription) {
        subscribeToPush();
      }
    }).catch(function() {});
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', autoSubscribe);
  } else {
    autoSubscribe();
  }

  window.SonacipPush = {
    isSupported: isPushSupported,
    subscribe: subscribeToPush,
    unsubscribe: unsubscribeFromPush
  };
})();
