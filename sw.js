self.addEventListener('push', function(event) {
    if (!event.data) return;
    
    const payload = event.data.json();
    const title = payload.title || 'aroma Rilith';
    const options = {
        body: payload.body || '新しい通知があります',
        icon: '/icon-192.png',
        badge: '/icon-192.png',
        data: payload.url || '/'
    };
    
    event.waitUntil(
        self.registration.showNotification(title, options)
    );
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    event.waitUntil(
        clients.openWindow(event.notification.data)
    );
});
