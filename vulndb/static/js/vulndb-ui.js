/* VULNDB UI helpers — no CDN */
(function () {
  function qs(sel, root) { return (root || document).querySelector(sel); }
  function qsa(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

  // Collapsible filter panel
  qsa("[data-collapse]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var panel = btn.closest(".filter-panel");
      if (!panel) return;
      panel.classList.toggle("is-collapsed");
      var open = !panel.classList.contains("is-collapsed");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    });
  });

  // Settings / generic tab panes via data-tabs
  qsa("[data-tabs]").forEach(function (nav) {
    var scope = nav.getAttribute("data-tabs");
    qsa("a, button", nav).forEach(function (link) {
      link.addEventListener("click", function (e) {
        e.preventDefault();
        var id = link.getAttribute("data-tab") || (link.getAttribute("href") || "").replace("#", "");
        if (!id) return;
        qsa("a, button", nav).forEach(function (x) { x.classList.remove("is-active"); });
        link.classList.add("is-active");
        qsa('[data-tab-pane="' + scope + '"]').forEach(function (pane) {
          pane.classList.toggle("is-active", pane.id === id || pane.getAttribute("data-pane-id") === id);
        });
        if (history.replaceState) history.replaceState(null, "", "#" + id);
      });
    });
    var hash = (location.hash || "").replace("#", "");
    if (hash) {
      var target = qs('[data-tab="' + hash + '"], [href="#' + hash + '"]', nav);
      if (target) target.click();
    }
  });

  // CVSS / content tabs inside a panel
  qsa("[data-local-tabs]").forEach(function (bar) {
    qsa(".tab", bar).forEach(function (tab) {
      tab.addEventListener("click", function () {
        var name = tab.getAttribute("data-tab");
        qsa(".tab", bar).forEach(function (t) { t.classList.toggle("is-active", t === tab); });
        var root = bar.parentElement;
        qsa("[data-pane]", root).forEach(function (pane) {
          pane.classList.toggle("is-active", pane.getAttribute("data-pane") === name);
        });
      });
    });
  });

  // Modal open/close
  qsa("[data-modal-open]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var id = btn.getAttribute("data-modal-open");
      var m = qs("#" + id);
      if (m) m.classList.add("is-open");
    });
  });
  qsa("[data-modal-close]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var m = btn.closest(".modal-backdrop");
      if (m) m.classList.remove("is-open");
    });
  });
  qsa(".modal-backdrop").forEach(function (m) {
    m.addEventListener("click", function (e) {
      if (e.target === m) m.classList.remove("is-open");
    });
  });

  // Local ID preview in setup
  var prefix = qs("#org-prefix");
  var preview = qs("#id-preview");
  if (prefix && preview) {
    var render = function () {
      var p = (prefix.value || "ACME").toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 16) || "ACME";
      prefix.value = p;
      var y = new Date().getFullYear();
      preview.textContent = p + "-" + y + "-0001";
    };
    prefix.addEventListener("input", render);
    render();
  }
})();
