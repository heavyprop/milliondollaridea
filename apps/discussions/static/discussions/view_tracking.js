function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);

    if (parts.length === 2) {
        return parts.pop().split(";").shift();
    }

    return "";
}

function sendViewSeconds(viewUrl, seconds) {
    if (!viewUrl || seconds <= 0) {
        return;
    }

    const data = new FormData();
    data.append("seconds", seconds);

    fetch(viewUrl, {
        method: "POST",
        body: data,
        headers: {
            "X-CSRFToken": getCookie("csrftoken"),
        },
        keepalive: true,
    });
}

function setupViewTracking() {
    const thread = document.querySelector("[data-view-url]");

    if (!thread) {
        return;
    }

    const viewUrl = thread.dataset.viewUrl;
    let lastSentAt = Date.now();

    function sendDelta() {
        const now = Date.now();
        const seconds = Math.floor((now - lastSentAt) / 1000);

        if (seconds < 1) {
            return;
        }

        lastSentAt = now;
        sendViewSeconds(viewUrl, seconds);
    }

    setInterval(sendDelta, 10000);
    window.addEventListener("pagehide", sendDelta);
}

document.addEventListener("DOMContentLoaded", setupViewTracking);
