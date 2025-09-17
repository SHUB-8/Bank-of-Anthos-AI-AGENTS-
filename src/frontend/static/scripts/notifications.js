
document.addEventListener('DOMContentLoaded', () => {
    const notificationBell = document.getElementById('notification-bell');
    const notificationCount = document.getElementById('notification-count');
    const notificationList = document.getElementById('notification-list');

    async function fetchNotifications() {
        try {
            const response = await fetch('/notifications');
            if (response.ok) {
                const notifications = await response.json();
                updateNotificationUI(notifications);
            } else {
                console.error('Failed to fetch notifications');
            }
        } catch (error) {
            console.error('Error fetching notifications:', error);
        }
    }

    function updateNotificationUI(notifications) {
        if (notifications.length > 0) {
            notificationCount.textContent = notifications.length;
            notificationCount.style.display = 'block';
        } else {
            notificationCount.style.display = 'none';
        }

        notificationList.innerHTML = '';
        if (notifications.length === 0) {
            const noNotificationItem = document.createElement('a');
            noNotificationItem.className = 'dropdown-item';
            noNotificationItem.textContent = 'No new notifications';
            notificationList.appendChild(noNotificationItem);
        } else {
            notifications.forEach(notification => {
                const notificationItem = document.createElement('a');
                notificationItem.className = 'dropdown-item';
                notificationItem.href = '#';
                notificationItem.innerHTML = `
                    <div class="notification-item">
                        <div class="notification-message">${notification.message}</div>
                        <div class="notification-timestamp">${new Date(notification.timestamp).toLocaleString()}</div>
                    </div>
                `;
                notificationList.appendChild(notificationItem);
            });
        }
    }

    // Fetch notifications every 30 seconds
    fetchNotifications();
    setInterval(fetchNotifications, 30000);
});
