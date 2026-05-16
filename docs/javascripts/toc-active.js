/* Right-rail TOC: highlight the section currently in view.
   Mirrors Tailwind's on-this-page pattern: a 2px teal accent + weight
   bump on the active link as the reader scrolls. CSS owns the visuals
   (see extra.css .cora-toc-active); this file owns the bookkeeping.
   Re-binds on Material's document$ stream so navigation.instant page
   swaps reattach cleanly. */
(function () {
  const ACTIVE = "cora-toc-active";
  let cleanup = null;

  function init() {
    if (cleanup) cleanup();
    cleanup = null;

    /* Material renders TOC links as absolute URLs (page URL + #anchor),
       not bare "#anchor". Match by the URL hash so it works regardless,
       and target the right rail via its aria-label so we don't depend on
       Material's internal class scheme. */
    const links = Array.from(
      document.querySelectorAll(
        'nav[aria-label="Table of contents"] a[href*="#"]',
      ),
    );
    if (!links.length) return;

    const linksByHeading = new Map();
    const headings = [];
    for (const link of links) {
      let url;
      try {
        url = new URL(link.href, document.baseURI);
      } catch (_) {
        continue;
      }
      const id = url.hash ? decodeURIComponent(url.hash.slice(1)) : "";
      if (!id) continue;
      const h = document.getElementById(id);
      if (!h) continue;
      if (!linksByHeading.has(h)) {
        linksByHeading.set(h, []);
        headings.push(h);
      }
      linksByHeading.get(h).push(link);
    }
    if (!headings.length) return;

    let activeLinks = [];
    let ticking = false;

    function update() {
      ticking = false;
      const activationY = window.innerHeight * 0.25;
      let current = null;
      for (const h of headings) {
        if (h.getBoundingClientRect().top <= activationY) {
          current = h;
        } else {
          break;
        }
      }
      /* If we've reached the bottom of the page, force the last heading
         active. Otherwise short final sections never cross the activation
         line and the rail looks stuck on the previous one. */
      const scrollBottom = window.scrollY + window.innerHeight;
      const docHeight = document.documentElement.scrollHeight;
      if (scrollBottom >= docHeight - 4) {
        current = headings[headings.length - 1];
      }
      const next = current ? linksByHeading.get(current) : [];
      if (next === activeLinks) return;
      for (const link of activeLinks) link.classList.remove(ACTIVE);
      for (const link of next) link.classList.add(ACTIVE);
      activeLinks = next;
    }

    function onScroll() {
      if (!ticking) {
        requestAnimationFrame(update);
        ticking = true;
      }
    }

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    update();

    cleanup = () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      for (const link of activeLinks) link.classList.remove(ACTIVE);
      activeLinks = [];
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
