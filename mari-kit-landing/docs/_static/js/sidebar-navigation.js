/* Keep the independently scrolling docs menu in place across page loads.
 * Per-tab storage contains navigation geometry only. Storage denial is harmless.
 */
(() => {
  "use strict";
  const script = document.currentScript;
  const root = script ? new URL("../../", script.src).pathname : "/";
  const storageKey = `mari-kit:sidebar:v1:${root}`;

  function initialize() {
    const sidebar = document.querySelector(".sidebar-scroll");
    if (!sidebar) return;
    const links = [...sidebar.querySelectorAll(".sidebar-tree a.reference")];
    let saved = null;
    try {
      const value = JSON.parse(sessionStorage.getItem(storageKey));
      if (value && Number.isFinite(value.top) && value.top >= 0) saved = value;
    } catch (_) { /* private browsing or unavailable storage */ }

    let interacted = false;
    let pending = false;
    const bounds = () => sidebar.getBoundingClientRect();
    function save() {
      pending = false;
      const top = bounds().top;
      const anchor = links.find(link => link.getBoundingClientRect().bottom > top);
      try {
        sessionStorage.setItem(storageKey, JSON.stringify({
          top: sidebar.scrollTop,
          anchor: anchor ? new URL(anchor.href).pathname : null,
          offset: anchor ? anchor.getBoundingClientRect().top - top : 0,
        }));
      } catch (_) { /* scrolling still works without persistence */ }
    }

    function restore() {
      if (interacted) return;
      if (saved) {
        const anchor = links.find(link => new URL(link.href).pathname === saved.anchor);
        // An anchor also survives font wrapping and additions earlier in the menu.
        sidebar.scrollTop = anchor && Number.isFinite(saved.offset)
          ? sidebar.scrollTop + anchor.getBoundingClientRect().top - bounds().top - saved.offset
          : saved.top;
      } else {
        // A fresh deep link should reveal its active entry, moving only the menu.
        const active = sidebar.querySelector(".current-page > a.reference");
        if (active) {
          const box = active.getBoundingClientRect();
          const viewport = bounds();
          if (box.top < viewport.top || box.bottom > viewport.bottom) {
            sidebar.scrollTop += box.top - viewport.top - sidebar.clientHeight / 2;
          }
        }
      }
    }

    for (const event of ["pointerdown", "touchstart", "wheel", "keydown"]) {
      document.addEventListener(event, () => { interacted = true; }, {passive: true, once: true});
    }
    sidebar.addEventListener("scroll", () => {
      if (!pending) {
        pending = true;
        requestAnimationFrame(save);
      }
    }, {passive: true});
    sidebar.addEventListener("click", save, {capture: true});
    window.addEventListener("pagehide", save);
    // BFCache already holds the correct DOM and scroll position.
    window.addEventListener("pageshow", event => {
      if (!event.persisted) restore();
    });
    restore();
    requestAnimationFrame(restore);
    if (document.fonts) document.fonts.ready.then(() => requestAnimationFrame(restore));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize, {once: true});
  } else {
    initialize();
  }
})();
