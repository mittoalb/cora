/* Editorial reveal-on-scroll for docs pages.
   Tags every direct child of .md-typeset from the first <h2> onwards with
   .cora-reveal, then upgrades each to .cora-revealed as it enters the
   viewport via IntersectionObserver. Skips the home page (hero owns that
   animation) and respects prefers-reduced-motion. Hash jumps reveal the
   target and everything above it instantly so #anchor links land cleanly. */
(function () {
  const REVEAL = "cora-reveal";
  const REVEALED = "cora-revealed";
  let observer = null;

  function init() {
    if (observer) {
      observer.disconnect();
      observer = null;
    }

    if (document.querySelector(".cora-hero")) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const article = document.querySelector(".md-content .md-typeset");
    if (!article) return;

    const firstH2 = article.querySelector(":scope > h2");
    if (!firstH2) return;

    const targets = [];
    for (let node = firstH2; node; node = node.nextElementSibling) {
      targets.push(node);
    }
    targets.forEach((el) => el.classList.add(REVEAL));

    observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add(REVEALED);
            observer.unobserve(entry.target);
          }
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.05 },
    );
    targets.forEach((el) => observer.observe(el));

    if (location.hash) {
      let anchor = null;
      try {
        anchor = article.querySelector(location.hash);
      } catch (_) {
        // Invalid CSS selector in hash (for example starts with digit); ignore.
      }
      if (anchor) {
        let cursor = anchor.closest(".md-typeset > *") || anchor;
        while (cursor && cursor.parentElement === article) {
          cursor.classList.add(REVEALED);
          if (observer) observer.unobserve(cursor);
          cursor = cursor.previousElementSibling;
        }
      }
    }
  }

  if (typeof document$ !== "undefined") {
    document$.subscribe(init);
  } else if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
