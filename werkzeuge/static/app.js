// Haus-Wiki: Zoom im Plan, Hervorheben per #BMK, Filter in Listen. Ohne externe Bibliotheken.
(function () {
  var plan = document.getElementById("plan");
  if (plan) {
    var svg = plan.querySelector("svg");
    var stufe = 0;
    var setze = function () { svg.style.width = (100 * Math.pow(1.5, stufe)) + "%"; };
    document.querySelectorAll("[data-zoom]").forEach(function (b) {
      b.addEventListener("click", function () {
        var z = parseInt(b.getAttribute("data-zoom"), 10);
        stufe = z === 0 ? 0 : Math.max(0, Math.min(5, stufe + z));
        setze();
      });
    });
    var ziel = decodeURIComponent(location.hash.slice(1));
    if (ziel) {
      var treffer = plan.querySelectorAll('.hs[data-bmk="' + ziel.replace(/"/g, "") + '"]');
      if (treffer.length) {
        if (window.innerWidth < 900) { stufe = 2; setze(); }
        treffer.forEach(function (a) { a.classList.add("aktiv"); });
        treffer[0].scrollIntoView({ block: "center", inline: "center" });
      }
    }
  }
  var filter = document.getElementById("filter");
  var liste = document.getElementById("elementliste");
  if (filter && liste) {
    var anwenden = function () {
      var q = filter.value.trim().toLowerCase();
      liste.querySelectorAll("tbody tr").forEach(function (tr) {
        tr.style.display = !q || tr.textContent.toLowerCase().indexOf(q) >= 0 ? "" : "none";
      });
    };
    var p = new URLSearchParams(location.search).get("q");
    if (p) filter.value = p;
    filter.addEventListener("input", anwenden);
    anwenden();
  }
})();
