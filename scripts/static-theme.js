(function () {
  var KEY = "portfolio-theme";

  function getSystemTheme() {
    return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  }

  function getStoredTheme() {
    var stored = localStorage.getItem(KEY);
    return stored === "light" || stored === "dark" ? stored : null;
  }

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;

    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) {
      meta.setAttribute("content", theme === "light" ? "#faf9fc" : "#0c0b0f");
    }

    document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
      var isDark = theme === "dark";
      btn.setAttribute("aria-label", isDark ? "Switch to light mode" : "Switch to dark mode");
      btn.setAttribute("title", isDark ? "Light mode" : "Dark mode");
    });
  }

  function currentTheme() {
    return document.documentElement.dataset.theme === "light" ? "light" : "dark";
  }

  window.portfolioTheme = {
    init: function () {
      applyTheme(getStoredTheme() || getSystemTheme());
    },
    toggle: function () {
      var next = currentTheme() === "dark" ? "light" : "dark";
      localStorage.setItem(KEY, next);
      applyTheme(next);
    },
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      window.portfolioTheme.init();
    });
  } else {
    window.portfolioTheme.init();
  }
})();
