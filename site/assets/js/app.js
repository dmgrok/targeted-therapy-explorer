/* Targeted Therapy Explorer — client-only helpers.
   No cookies, no browser storage, no network, no analytics. */
(function () {
  "use strict";

  function snapshotDate() {
    var el = document.getElementById("snapshot-date");
    if (!el) return null;
    var iso = el.getAttribute("datetime") || el.textContent || "";
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
    if (!m) return null;
    return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  }

  function showStaleBanner() {
    var start = snapshotDate();
    var banner = document.getElementById("stale-banner");
    if (!start || !banner) return;
    var now = new Date();
    var utc = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
    var days = Math.floor((utc - start.getTime()) / 86400000);
    if (days > 8) {
      banner.hidden = false;
      banner.classList.add("is-visible");
    }
  }

  function countriesOf(el) {
    return (el.getAttribute("data-countries") || "")
      .split(/\s+/)
      .filter(Boolean);
  }

  function applyCountryFilter() {
    var select = document.getElementById("country-filter");
    if (!select) return;
    var value = select.value || "all";
    var trials = document.querySelectorAll(".trial");
    var shown = 0;
    for (var i = 0; i < trials.length; i++) {
      var match = value === "all" || countriesOf(trials[i]).indexOf(value) !== -1;
      trials[i].classList.toggle("is-hidden", !match);
      if (match) shown += 1;
    }
    var empty = document.getElementById("trial-empty");
    if (empty) empty.style.display = shown === 0 ? "block" : "none";
    var count = document.getElementById("filter-count");
    if (count) {
      if (value === "all") {
        count.textContent = shown + " recruiting trials.";
      } else {
        count.textContent = shown + " recruiting trials with a site in " + value + ".";
      }
    }
    if (history.replaceState) {
      var url = new URL(window.location.href);
      if (value === "all") url.searchParams.delete("country");
      else url.searchParams.set("country", value);
      history.replaceState({}, "", url);
    }
  }

  function initFilter() {
    var select = document.getElementById("country-filter");
    if (!select) return;
    var params = new URLSearchParams(window.location.search);
    var preset = params.get("country");
    if (preset) {
      for (var i = 0; i < select.options.length; i++) {
        if (select.options[i].value === preset) {
          select.value = preset;
          break;
        }
      }
    }
    select.addEventListener("change", applyCountryFilter);
    applyCountryFilter();
  }

  showStaleBanner();
  initFilter();
})();
