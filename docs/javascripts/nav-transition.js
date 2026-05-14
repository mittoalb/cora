/* Smooth content transition for Material's instant navigation.
   Each time document$ emits (after a tab/link swap), replay a short
   fade-in on .md-main__inner so the new page eases in instead of
   snapping. Respects prefers-reduced-motion. */
(function () {
  const DURATION_MS = 220;

  function play() {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const target = document.querySelector(".md-main__inner");
    if (!target || typeof target.animate !== "function") return;
    target.animate(
      [
        { opacity: 0, transform: "translateY(4px)" },
        { opacity: 1, transform: "none" },
      ],
      { duration: DURATION_MS, easing: "ease-out", fill: "backwards" },
    );
  }

  if (typeof document$ !== "undefined") {
    document$.subscribe(play);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", play);
  } else {
    play();
  }
})();
