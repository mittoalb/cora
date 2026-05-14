/* Wrap Material's palette toggle in document.startViewTransition so the
   light <-> dark swap cross-fades instead of flashing. Material's palette
   uses hidden radios <input id="__palette_0/1"> with <label for="...">
   buttons; clicking a label fires the radio change which Material observes
   to flip data-md-color-scheme. We intercept the label click, halt it,
   then re-fire the radio click inside a view transition. */
(function () {
  if (typeof document === "undefined") return;
  if (typeof document.startViewTransition !== "function") return;

  document.addEventListener(
    "click",
    (event) => {
      const label = event.target.closest('label[for^="__palette_"]');
      if (!label) return;
      if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

      const input = document.getElementById(label.htmlFor);
      if (!input || input.checked) return;

      event.preventDefault();
      event.stopPropagation();

      document.startViewTransition(async () => {
        input.click();
        // Yield one frame so Material's RxJS handler applies the swap
        // before the browser snapshots the "new" state.
        await new Promise((resolve) => requestAnimationFrame(resolve));
      });
    },
    true,
  );
})();
