(() => {
    const button = document.getElementById("blocked-users-toggle");
    const list = document.getElementById("blocked-users-list");
    if (!button || !list) return;

    button.addEventListener("click", () => {
        const expanded = button.getAttribute("aria-expanded") === "true";
        button.setAttribute("aria-expanded", String(!expanded));
        list.hidden = expanded;
    });
})();
