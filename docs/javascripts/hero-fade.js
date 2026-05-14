/* Squidfunk-style scroll fade for the homepage hero.
   Hero scrolls normally; the layer is position: fixed (anchored to viewport)
   and fades via opacity tied to scroll progress through the hero. The header
   + tabs strip background also fades from transparent to solid teal as the
   user scrolls past the hero. Reattaches on instant-nav. */
(function () {
  let cleanup = null;

  function init() {
    if (cleanup) cleanup();
    cleanup = null;

    const hero = document.querySelector(".cora-hero");
    if (!hero) return;
    const layer = hero.querySelector(".cora-hero__layer");
    if (!layer) return;

    const root = document.documentElement;
    const reducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    const abortController = new AbortController();
    let ticking = false;

    function update() {
      const rect = hero.getBoundingClientRect();
      const scrolled = Math.max(0, -rect.top);

      if (reducedMotion) {
        const past = rect.bottom <= 0;
        layer.style.opacity = past ? "0" : "1";
        layer.style.visibility = past ? "hidden" : "visible";
        root.style.setProperty("--cora-header-overlay", past ? "1" : "0");
      } else {
        // Layer fade: sqrt curve, completes within first 20% of hero scroll.
        const linear = Math.min(1, scrolled / (rect.height * 0.2));
        const progress = Math.sqrt(linear);
        layer.style.opacity = String(1 - progress);
        layer.style.visibility = progress >= 1 ? "hidden" : "visible";

        // Header overlay: linear, fully solid by 50% of hero scroll.
        const headerProgress = Math.min(1, scrolled / (rect.height * 0.5));
        root.style.setProperty(
          "--cora-header-overlay",
          String(headerProgress),
        );
      }
      ticking = false;
    }

    function onScroll() {
      if (!ticking) {
        requestAnimationFrame(update);
        ticking = true;
      }
    }

    window.addEventListener("scroll", onScroll, {
      passive: true,
      signal: abortController.signal,
    });
    window.addEventListener("resize", onScroll, {
      passive: true,
      signal: abortController.signal,
    });
    update();

    cleanup = () => {
      abortController.abort();
      root.style.removeProperty("--cora-header-overlay");
    };
  }

  if (typeof document$ !== "undefined") {
    document$.subscribe(init);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
