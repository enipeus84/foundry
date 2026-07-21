(() => {
  "use strict";

  const openButton = document.querySelector("#nav-open");
  const shell = document.querySelector("#primary-drawer");
  const drawer = shell?.querySelector(".drawer");
  const closeButton = shell?.querySelector("[data-nav-close]");

  if (!openButton || !shell || !drawer || !closeButton) return;

  const focusableSelector = "a[href], button:not([disabled])";

  const setOpen = (open) => {
    shell.hidden = !open;
    openButton.setAttribute("aria-expanded", String(open));
    document.body.classList.toggle("nav-open", open);
    if (open) {
      closeButton.focus();
    } else {
      openButton.focus();
    }
  };

  openButton.addEventListener("click", () => setOpen(true));
  closeButton.addEventListener("click", () => setOpen(false));
  shell.querySelector("[data-nav-dismiss]")?.addEventListener("click", () => setOpen(false));

  document.addEventListener("keydown", (event) => {
    if (shell.hidden) return;
    if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
      return;
    }
    if (event.key !== "Tab") return;

    const focusable = Array.from(drawer.querySelectorAll(focusableSelector));
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });
})();
