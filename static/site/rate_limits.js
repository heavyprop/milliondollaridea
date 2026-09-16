document.addEventListener("htmx:beforeSwap", function (event) {
    if (event.detail.xhr.status === 429 &&
        event.detail.xhr.getResponseHeader("HX-Retarget") === "#rate-limit-notice") {
        event.detail.shouldSwap = true;
        event.detail.isError = false;
    }
});

document.addEventListener("htmx:afterSwap", function (event) {
    if (event.detail.target.id === "rate-limit-notice") {
        event.detail.target.focus();
    }
});
