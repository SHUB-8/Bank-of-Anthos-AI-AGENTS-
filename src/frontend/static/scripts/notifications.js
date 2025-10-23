
document.addEventListener('DOMContentLoaded', () => {
    const notificationBell = document.getElementById('notification-bell');
    const notificationCount = document.getElementById('notification-count');
    const notificationList = document.getElementById('notification-list');

    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
        return '';
    }

    async function fetchNotifications() {
        try {
            const token = getCookie('token');
            const response = await fetch('/orchestrator/notifications', {
                headers: { 'Authorization': token ? `Bearer ${token}` : '' }
            });
            if (response.ok) {
                const data = await response.json();
                updateNotificationUI(data.notifications || []);
            } else {
                console.error('Failed to fetch notifications');
            }
        } catch (error) {
            console.error('Error fetching notifications:', error);
        }
    }

    function updateNotificationUI(notifications) {
        if (!notificationCount || !notificationList) return;
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
                const ts = notification.created_at || notification.timestamp;
                notificationItem.innerHTML = `
                    <div class="notification-item">
                        <div class="notification-message">${notification.message}</div>
                        <div class="notification-timestamp">${ts ? new Date(ts).toLocaleString() : ''}</div>
                    </div>
                `;
                notificationList.appendChild(notificationItem);
            });
        }
    }

    // Expose OTP prompt hook for chatbox
    window.chatboxShowOtp = function(confirmationId) {
        const container = document.getElementById('otp-container');
        if (!container) return;
        container.style.display = 'block';
        container.dataset.confirmationId = confirmationId;
    };

    async function verifyOtp() {
        const token = getCookie('token');
        const container = document.getElementById('otp-container');
        const input = document.getElementById('otp-input');
        const confirmationId = container?.dataset?.confirmationId;
        if (!confirmationId || !input) return;
        const res = await fetch('/orchestrator/verify-otp', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': token ? `Bearer ${token}` : '' },
            body: JSON.stringify({ confirmation_id: confirmationId, otp: input.value.trim() })
        });
        const data = await res.json();
        if (data.status === 'confirmed') {
            alert('Transaction executed.');
            container.style.display = 'none';
            input.value = '';
        } else if (data.status === 'invalid') {
            alert(`Incorrect OTP. Remaining attempts: ${data.remaining_attempts}`);
        } else if (data.status === 'blocked') {
            alert('Blocked after 3 failed attempts.');
            container.style.display = 'none';
            input.value = '';
        } else if (data.status === 'expired') {
            alert('OTP expired. Please initiate again.');
            container.style.display = 'none';
            input.value = '';
        }
    }

    const otpButton = document.getElementById('otp-submit');
    if (otpButton) otpButton.addEventListener('click', verifyOtp);

    // Fetch notifications every 30 seconds
    fetchNotifications();
    setInterval(fetchNotifications, 30000);
});
