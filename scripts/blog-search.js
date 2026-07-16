/**
 * Client-side search + tag filtering for the blog hub.
 *
 * The hub ships every post as real HTML (good for crawlers and no-JS readers).
 * This script progressively enhances that list: it reads the `data-search` and
 * `data-tags` attributes baked onto each `.post-card` at build time and shows or
 * hides cards in place — no fetch, no index file, nothing to keep in sync.
 *
 * State lives in the URL (`?q=` and `?tag=`) so searches and tag filters are
 * shareable and survive a refresh or a back-button press.
 */
(function () {
  var root = document.querySelector("[data-blog-filters]");
  var grid = document.querySelector("[data-post-grid]");
  if (!root || !grid) return;

  var input = root.querySelector("[data-blog-search]");
  var tagWrap = root.querySelector(".tag-filter");
  var countEl = root.querySelector("[data-result-count]");
  var moreBtn = root.querySelector("[data-tag-more]");
  var emptyEl = document.querySelector("[data-blog-empty]");
  var resetBtn = document.querySelector("[data-blog-reset]");

  var cards = Array.prototype.slice.call(grid.querySelectorAll("[data-post]"));
  var allChip = tagWrap.querySelector("[data-tag-all]");
  var tagChips = Array.prototype.slice
    .call(tagWrap.querySelectorAll("[data-tag]"))
    .filter(function (b) {
      return b.getAttribute("data-tag") !== "";
    });

  // Precompute each card's searchable text and its tag set (lowercased) once.
  var index = cards.map(function (card) {
    var tags = (card.getAttribute("data-tags") || "")
      .split("|")
      .map(function (t) {
        return t.trim().toLowerCase();
      })
      .filter(Boolean);
    return {
      el: card,
      search: (card.getAttribute("data-search") || "").toLowerCase(),
      tags: tags,
    };
  });

  var query = "";
  var activeTags = []; // lowercased; empty means "All"

  function debounce(fn, wait) {
    var t;
    return function () {
      clearTimeout(t);
      t = setTimeout(fn, wait);
    };
  }

  function syncUrl() {
    var params = new URLSearchParams(window.location.search);
    if (query) params.set("q", query);
    else params.delete("q");
    if (activeTags.length) params.set("tag", activeTags.join(","));
    else params.delete("tag");
    var qs = params.toString();
    var next = window.location.pathname + (qs ? "?" + qs : "");
    window.history.replaceState(null, "", next);
  }

  function apply() {
    var q = query.trim().toLowerCase();
    // Multi-word search: every whitespace-separated term must appear somewhere.
    var terms = q ? q.split(/\s+/) : [];
    var visible = 0;

    for (var i = 0; i < index.length; i++) {
      var item = index[i];
      var matchesText = true;
      for (var t = 0; t < terms.length; t++) {
        if (item.search.indexOf(terms[t]) === -1) {
          matchesText = false;
          break;
        }
      }
      // Tag filter uses OR semantics: a card matches if it carries any active tag.
      var matchesTags = true;
      if (activeTags.length) {
        matchesTags = false;
        for (var a = 0; a < activeTags.length; a++) {
          if (item.tags.indexOf(activeTags[a]) !== -1) {
            matchesTags = true;
            break;
          }
        }
      }
      var show = matchesText && matchesTags;
      item.el.hidden = !show;
      if (show) visible++;
    }

    if (emptyEl) emptyEl.hidden = visible !== 0;
    if (countEl) {
      if (!query && !activeTags.length) {
        countEl.textContent = index.length + " articles";
      } else {
        countEl.textContent =
          visible + (visible === 1 ? " article" : " articles") + " found";
      }
    }
  }

  function updateChipState() {
    allChip.classList.toggle("is-active", activeTags.length === 0);
    tagChips.forEach(function (chip) {
      var tag = chip.getAttribute("data-tag").toLowerCase();
      chip.classList.toggle("is-active", activeTags.indexOf(tag) !== -1);
    });
  }

  function setTag(tag, additive) {
    var lower = tag.toLowerCase();
    if (!tag) {
      activeTags = [];
    } else {
      var idx = activeTags.indexOf(lower);
      if (idx !== -1) {
        activeTags.splice(idx, 1);
      } else if (additive) {
        activeTags.push(lower);
      } else {
        activeTags = [lower];
      }
    }
    updateChipState();
    apply();
    syncUrl();
  }

  // --- Wire up events ------------------------------------------------------
  if (input) {
    input.addEventListener(
      "input",
      debounce(function () {
        query = input.value;
        apply();
        syncUrl();
      }, 120),
    );
    // Escape clears the search box quickly.
    input.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && input.value) {
        input.value = "";
        query = "";
        apply();
        syncUrl();
      }
    });
  }

  allChip.addEventListener("click", function () {
    setTag("", false);
  });

  tagChips.forEach(function (chip) {
    chip.addEventListener("click", function (e) {
      // Ctrl/Cmd-click (or shift) adds to the current selection; a plain click
      // narrows to just that tag, or toggles it off if it's the only one active.
      var additive = e.metaKey || e.ctrlKey || e.shiftKey;
      setTag(chip.getAttribute("data-tag"), additive);
    });
  });

  if (moreBtn) {
    moreBtn.addEventListener("click", function () {
      var expanded = moreBtn.getAttribute("aria-expanded") === "true";
      tagWrap.querySelectorAll(".tag-chip.is-overflow").forEach(function (chip) {
        chip.hidden = expanded;
      });
      moreBtn.setAttribute("aria-expanded", String(!expanded));
      moreBtn.textContent = expanded
        ? moreBtn.getAttribute("data-more-label") || moreBtn.textContent
        : "Show less";
    });
    moreBtn.setAttribute("data-more-label", moreBtn.textContent);
  }

  if (resetBtn) {
    resetBtn.addEventListener("click", function () {
      query = "";
      if (input) input.value = "";
      activeTags = [];
      updateChipState();
      apply();
      syncUrl();
    });
  }

  // --- Hydrate from URL (shareable searches) -------------------------------
  var params = new URLSearchParams(window.location.search);
  var initialQuery = params.get("q");
  var initialTag = params.get("tag");
  if (initialQuery) {
    query = initialQuery;
    if (input) input.value = initialQuery;
  }
  if (initialTag) {
    activeTags = initialTag
      .split(",")
      .map(function (t) {
        return t.trim().toLowerCase();
      })
      .filter(Boolean);
    // Reveal overflow chips if a filtered-in tag lives in the collapsed group.
    if (moreBtn) {
      var overflowActive = tagChips.some(function (chip) {
        return (
          chip.classList.contains("is-overflow") &&
          activeTags.indexOf(chip.getAttribute("data-tag").toLowerCase()) !== -1
        );
      });
      if (overflowActive) moreBtn.click();
    }
  }

  updateChipState();
  apply();
})();
