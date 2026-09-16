// Progressive enhancement: code remains readable/selectable without JavaScript.
document.querySelectorAll("[data-code-block]").forEach((block) => {
    const button = block.querySelector(".code-copy");
    const status = block.querySelector(".code-copy-status");
    const code = block.querySelector("code");
    if (!navigator.clipboard?.writeText || !button || !status || !code) return;

    button.hidden = false;
    let resetTimer;
    button.addEventListener("click", async () => {
        clearTimeout(resetTimer);
        button.disabled = true;
        status.textContent = "";
        status.removeAttribute("data-error");
        try {
            await navigator.clipboard.writeText(code.textContent);
            status.textContent = "Copied";
        } catch {
            status.textContent = "Select the code to copy it manually.";
            status.dataset.error = "true";
        } finally {
            button.disabled = false;
            resetTimer = setTimeout(() => { status.textContent = ""; }, 5000);
        }
    });
});
