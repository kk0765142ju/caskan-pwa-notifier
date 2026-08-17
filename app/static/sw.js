// Service Worker for Web Push Notification & PWA
self.addEventListener('push', function(event) {
    if (!event.data) return;

    try {
        const payload = event.data.json();
        const title = payload.title || 'aroma Rilith 通知';
        const options = {
            body: payload.body || '',
            icon: payload.icon || '/static/icon-192.png',
            badge: '/static/icon-192.png',
            data: payload.data || {},
            vibrate: [100, 50, 100],
            actions: [
                { action: 'open', title: '確認する' }
            ]
        };

        event.waitUntil(
            self.registration.showNotification(title, options)
        );
    } catch (e) {
        console.error('Push payload parse error:', e);
    }
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();

    const targetUrl = event.notification.data.url || '/';

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
            for (let i = 0; i < clientList.length; i++) {
                let client = clientList[i];
                if (client.url === targetUrl && 'focus' in client) {
                    return client.focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow(targetUrl);
            }
        })
    );
});
