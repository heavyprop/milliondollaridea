// this is a listener for detecting if the what is pasted into a text box contains code
// if so, using text.includes then add backticks

function looksLikeCode(text) {
    return (
        text.includes("\n") &&
        (
            text.includes("def ") ||
            text.includes("class ") ||
            text.includes("function ") ||
            text.includes("const ") ||
            text.includes("let ") ||
            text.includes("var ") ||
            text.includes("import ") ||
            text.includes("{") ||
            text.includes("}") ||
            text.includes(";")
        )
    );
}

function wrapPastedCode(event) {
    const textarea = event.currentTarget;
    const pastedText = event.clipboardData.getData("text");

    if (!looksLikeCode(pastedText)) {
        return;
    }

    event.preventDefault();

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const before = textarea.value.slice(0, start);
    const after = textarea.value.slice(end);
    const wrappedCode = "```\n" + pastedText + "\n```";

    textarea.value = before + wrappedCode + after;
    textarea.selectionStart = textarea.selectionEnd = before.length + wrappedCode.length;
}

function setupCodePasteListener() {
    document.querySelectorAll("[data-code-paste]").forEach(function(textarea) {
        textarea.addEventListener("paste", wrapPastedCode);
    });
}

document.addEventListener("DOMContentLoaded", setupCodePasteListener);
