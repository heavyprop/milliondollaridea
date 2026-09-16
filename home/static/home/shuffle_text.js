(() => {
    const text = document.querySelector("[data-shuffle-text]");
    if (!text) return;

    const characters = "untrainable34964#$&@#&$";
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let timer;
    let position = 0;

    function shuffle() {
        const letters = Array.from(text.textContent);
        const choices = Array.from(characters).filter(character => character !== letters[position]);
        letters[position] = choices[Math.floor(Math.random() * choices.length)];
        text.textContent = letters.join("");
        position = (position + 1) % 5;
    }

    function updateAnimation() {
        window.clearInterval(timer);
        if (!reducedMotion.matches && !document.hidden) {
            shuffle();
            timer = window.setInterval(shuffle, 140);
        }
    }

    reducedMotion.addEventListener("change", updateAnimation);
    document.addEventListener("visibilitychange", updateAnimation);
    updateAnimation();
})();
