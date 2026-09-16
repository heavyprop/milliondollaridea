document.querySelectorAll("[data-copy-target]").forEach((button) => {
    const target = document.getElementById(button.dataset.copyTarget);
    const container = button.closest(".cli-copy-block, .cli-token-result");
    const status = container?.querySelector(".cli-copy-status");
    if (!target || !status) return;
    button.hidden = false;
    const label = button.textContent;
    let reset;
    button.addEventListener("click", async () => {
        clearTimeout(reset);
        button.disabled = true;
        const text = target instanceof HTMLInputElement ? target.value : target.textContent;
        try {
            await navigator.clipboard.writeText(text);
            button.textContent = "Copied";
            status.textContent = "Copied to clipboard.";
        } catch {
            if (target instanceof HTMLInputElement) {
                target.focus();
                target.select();
            } else {
                const range = document.createRange();
                range.selectNodeContents(target);
                const selection = window.getSelection();
                selection.removeAllRanges();
                selection.addRange(range);
            }
            status.textContent = "Text selected. Use your device's copy command.";
        } finally {
            button.disabled = false;
            reset = setTimeout(() => { button.textContent = label; status.textContent = ""; }, 4000);
        }
    });
});
