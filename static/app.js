/* Growmatic — تفاعلات اللوحة. بدون مكتبات خارجية. */
(function () {
  "use strict";

  var root = document.documentElement;
  var $ = function (sel, el) { return (el || document).querySelector(sel); };
  var $$ = function (sel, el) { return Array.prototype.slice.call((el || document).querySelectorAll(sel)); };
  var nf = new Intl.NumberFormat("en-US");
  var df = new Intl.DateTimeFormat("ar-u-ca-gregory-nu-latn", { day: "numeric", month: "short" });
  var dfLong = new Intl.DateTimeFormat("ar-u-ca-gregory-nu-latn", { weekday: "long", day: "numeric", month: "long" });
  var parseDate = function (iso) { var p = iso.split("-"); return new Date(+p[0], +p[1] - 1, +p[2]); };

  function store(key, value) {
    try {
      if (value === undefined) return localStorage.getItem(key);
      localStorage.setItem(key, value);
    } catch (e) { return null; }
  }

  function isDark() {
    if (root.dataset.theme) return root.dataset.theme === "dark";
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }
  function cssVar(name) { return getComputedStyle(root).getPropertyValue(name).trim(); }

  /* ---------- تنبيه منبثق ---------- */
  function toast(msg) {
    var stack = $("#toasts");
    if (!stack) return;
    var t = document.createElement("div");
    t.className = "toast";
    t.textContent = msg;
    stack.appendChild(t);
    setTimeout(function () { t.classList.add("out"); }, 2600);
    setTimeout(function () { t.remove(); }, 3000);
  }

  /* ---------- الوضع الليلي ---------- */
  var themeBtn = $("#theme-btn");
  if (themeBtn) {
    themeBtn.addEventListener("click", function () {
      var next = isDark() ? "light" : "dark";
      root.dataset.theme = next;
      store("theme", next);
      document.dispatchEvent(new CustomEvent("themechange"));
    });
  }

  /* ---------- قائمة الجوال ---------- */
  var sidebar = $("#sidebar"), scrim = $("#scrim"), menuBtn = $("#menu-btn");
  function setMenu(open) {
    if (!sidebar) return;
    sidebar.classList.toggle("open", open);
    scrim.classList.toggle("show", open);
  }
  if (menuBtn) menuBtn.addEventListener("click", function () { setMenu(!sidebar.classList.contains("open")); });
  if (scrim) scrim.addEventListener("click", function () { setMenu(false); });

  // خطوة مقرّبة (1، 2، 2.5، 5 × قوة 10) بحيث 4 خطوط تغطي أعلى قيمة
  function niceMax(v) {
    if (!v) return 4;
    var raw = v / 4, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    var steps = [1, 2, 2.5, 5, 10];
    for (var i = 0; i < steps.length; i++) if (steps[i] * mag >= raw) return steps[i] * mag * 4;
    return 40 * mag;
  }
  function shortNum(v) { return v >= 1000 ? +(v / 1000).toFixed(1) + "k" : String(Math.round(v)); }

  /* ---------- تحية حسب الوقت ---------- */
  var greet = $("#greeting");
  if (greet) {
    var h = new Date().getHours();
    greet.textContent = h < 12 ? "صباح الخير" : h < 18 ? "مساء النور" : "مساء الخير";
  }

  /* ---------- عدّاد متحرك ---------- */
  function countTo(el, target) {
    var from = +(el.dataset.current || 0);
    el.dataset.current = target;
    var start = null, dur = 700;
    function frame(ts) {
      if (start === null) start = ts;
      var p = Math.min(1, (ts - start) / dur);
      var eased = 1 - Math.pow(1 - p, 3);
      el.textContent = nf.format(Math.round(from + (target - from) * eased));
      if (p < 1) requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }

  /* ---------- تحريك الأشرطة عند التحميل ---------- */
  root.classList.add("is-loading");
  requestAnimationFrame(function () { requestAnimationFrame(function () { root.classList.remove("is-loading"); }); });

  /* ---------- مجموعة أزرار اختيار واحد ---------- */
  function radioGroup(container, attr, onChange) {
    if (!container) return;
    container.addEventListener("click", function (e) {
      var btn = e.target.closest("button");
      if (!btn || !container.contains(btn)) return;
      $$("button", container).forEach(function (b) {
        var on = b === btn;
        b.classList.toggle("active", on);
        if (b.hasAttribute("role")) b.setAttribute("aria-checked", on ? "true" : "false");
        if (b.hasAttribute("aria-pressed")) b.setAttribute("aria-pressed", on ? "true" : "false");
      });
      onChange(btn.getAttribute(attr));
    });
  }

  /* ---------- البحث العام ---------- */
  var searchWrap = $("#search-wrap"), searchInput = $("#search");
  var searchHandlers = [];
  if ($("[data-search]") && searchWrap) {
    searchWrap.hidden = false;
    searchInput.addEventListener("input", function () {
      searchHandlers.forEach(function (fn) { fn(); });
    });
  }
  function query() { return searchInput ? searchInput.value.trim().toLowerCase() : ""; }
  function matches(el) {
    var q = query();
    return !q || (el.dataset.search || "").toLowerCase().indexOf(q) !== -1;
  }

  /* =========================================================
     الصفحة الرئيسية
     ========================================================= */
  var dashEl = $("#dash-data");
  if (dashEl) initDashboard(JSON.parse(dashEl.textContent));

  function initDashboard(data) {
    var days = 30;
    var chartEl = $("#sales-chart");
    var tableEl = $("#sales-table");
    var tableBtn = $("#table-toggle");

    function seriesColor(s) {
      if (data.stores.length === 1) return cssVar("--primary");
      return isDark() ? s.color.dark : s.color.light;
    }

    function windowRows(n, offset) {
      var end = data.daily.length - (offset || 0);
      return data.daily.slice(Math.max(0, end - n), end);
    }

    function totals(rows) {
      var rev = 0, ord = 0;
      rows.forEach(function (r) {
        data.stores.forEach(function (s) { rev += r[s.key]; ord += r[s.key + "_orders"]; });
      });
      return { revenue: rev, orders: ord, aov: ord ? Math.round(rev / ord) : 0 };
    }

    function render() {
      var rows = windowRows(days);
      var prevRows = data.daily.length >= days * 2 ? windowRows(days, days) : null;
      var cur = totals(rows), prev = prevRows ? totals(prevRows) : null;

      $("#range-label").textContent = df.format(parseDate(rows[0].date)) + " – " + df.format(parseDate(rows[rows.length - 1].date));

      ["revenue", "orders", "aov"].forEach(function (k) {
        var card = $('[data-kpi="' + k + '"]');
        countTo($("[data-value]", card), cur[k]);
        var d = $("[data-delta]", card);
        if (prev && prev[k]) {
          var pct = (cur[k] - prev[k]) / prev[k] * 100;
          d.className = "delta " + (pct >= 0 ? "up" : "down");
          d.textContent = (pct >= 0 ? "▲ " : "▼ ") + Math.abs(pct).toFixed(1) + "%";
          d.hidden = false;
        } else {
          d.hidden = true;
        }
        drawSpark($("[data-spark]", card), rows.map(function (r) {
          var rev = 0, ord = 0;
          data.stores.forEach(function (s) { rev += r[s.key]; ord += r[s.key + "_orders"]; });
          return k === "revenue" ? rev : k === "orders" ? ord : (ord ? rev / ord : 0);
        }));
      });

      drawChart(rows);
      drawTable(rows);
      renderFinance(rows);
    }

    function renderFinance(rows) {
      var sum = function (suffix) {
        var t = 0;
        rows.forEach(function (r) { data.stores.forEach(function (s) { t += r[s.key + suffix]; }); });
        return t;
      };
      var rev = sum(""), vat = sum("_vat"), profit = sum("_profit");
      var vals = {
        vat: vat,
        ship: sum("_ship_rev") - sum("_ship_cost"),
        profit: profit,
        margin: rev - vat ? profit / (rev - vat) * 100 : 0
      };
      $$("[data-fin]").forEach(function (el) {
        var k = el.dataset.fin;
        if (k === "margin") el.textContent = vals.margin.toFixed(1) + "%";
        else countTo(el, Math.round(vals[k]));
        el.classList.toggle("neg", vals[k] < 0);
      });
    }

    function drawSpark(svg, values) {
      var w = 120, h = 36, max = Math.max.apply(null, values), min = Math.min.apply(null, values);
      var span = max - min || 1;
      var pts = values.map(function (v, i) {
        return [i / (values.length - 1) * w, h - 4 - (v - min) / span * (h - 10)];
      });
      var line = pts.map(function (p, i) { return (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1); }).join(" ");
      var color = cssVar("--primary");
      var id = "sg" + Math.random().toString(36).slice(2, 7);
      svg.innerHTML =
        '<defs><linearGradient id="' + id + '" x1="0" y1="0" x2="0" y2="1">' +
        '<stop offset="0" stop-color="' + color + '" stop-opacity=".22"/><stop offset="1" stop-color="' + color + '" stop-opacity="0"/></linearGradient></defs>' +
        '<path d="' + line + " L" + w + " " + h + " L0 " + h + ' Z" fill="url(#' + id + ')"/>' +
        '<path d="' + line + '" fill="none" stroke="' + color + '" stroke-width="1.6" vector-effect="non-scaling-stroke"/>';
    }

    function drawChart(rows) {
      var W = chartEl.clientWidth || 600, H = chartEl.clientHeight || 300;
      var pad = { t: 16, r: 54, b: 30, l: 44 };
      var iw = W - pad.l - pad.r, ih = H - pad.t - pad.b;
      var all = [];
      rows.forEach(function (r) { data.stores.forEach(function (s) { all.push(r[s.key]); }); });
      var yMax = niceMax(Math.max.apply(null, all) * 1.08);
      var x = function (i) { return pad.l + (rows.length === 1 ? iw / 2 : i / (rows.length - 1) * iw); };
      var y = function (v) { return pad.t + ih - v / yMax * ih; };
      var single = data.stores.length === 1;

      var svg = '<svg viewBox="0 0 ' + W + " " + H + '" direction="ltr" role="img" aria-label="رسم المبيعات اليومية">';
      for (var g = 0; g <= 4; g++) {
        var gv = yMax / 4 * g, gy = y(gv);
        svg += '<line class="grid-line" x1="' + pad.l + '" x2="' + (W - pad.r + 6) + '" y1="' + gy + '" y2="' + gy + '"/>';
        svg += '<text class="axis-label" x="' + (pad.l - 8) + '" y="' + (gy + 4) + '" text-anchor="end">' + shortNum(gv) + "</text>";
      }
      var ticks = Math.min(W < 520 ? 4 : 6, rows.length);
      for (var t = 0; t < ticks; t++) {
        var idx = Math.round(t / (ticks - 1) * (rows.length - 1));
        svg += '<text class="axis-label" x="' + x(idx) + '" y="' + (H - 8) + '" text-anchor="middle">' + df.format(parseDate(rows[idx].date)) + "</text>";
      }

      data.stores.forEach(function (s, si) {
        var color = seriesColor(s);
        var path = rows.map(function (r, i) { return (i ? "L" : "M") + x(i).toFixed(1) + " " + y(r[s.key]).toFixed(1); }).join(" ");
        if (single) {
          svg += '<defs><linearGradient id="area-g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="' + color + '" stop-opacity=".28"/><stop offset="1" stop-color="' + color + '" stop-opacity="0"/></linearGradient></defs>';
          svg += '<path d="' + path + " L" + x(rows.length - 1) + " " + y(0) + " L" + x(0) + " " + y(0) + ' Z" fill="url(#area-g)"/>';
        }
        svg += '<path class="series-line" d="' + path + '" stroke="' + color + '"/>';
        if (!single) {
          // تسمية مباشرة عند نهاية الخط
          var last = rows[rows.length - 1][s.key];
          svg += '<text class="axis-label" x="' + (x(rows.length - 1) + 8) + '" y="' + (y(last) + 4 + (si ? 6 : -6)) + '" style="fill: var(--ink-2); font-weight: 600">' + s.name + "</text>";
        }
      });
      svg += '<line class="crosshair" id="xh" y1="' + pad.t + '" y2="' + (pad.t + ih) + '" visibility="hidden"/>';
      data.stores.forEach(function (s, si) {
        svg += '<circle class="hover-dot" id="hd' + si + '" r="5" fill="' + seriesColor(s) + '" visibility="hidden"/>';
      });
      svg += '<rect id="hit" x="' + pad.l + '" y="' + pad.t + '" width="' + iw + '" height="' + ih + '" fill="transparent" tabindex="0" aria-label="مرّر لعرض قيمة كل يوم"/>';
      svg += "</svg>";
      chartEl.innerHTML = svg;

      // وسيلة الإيضاح للمقارنة بين متجرين
      var legend = $("#chart-legend");
      legend.innerHTML = "";
      if (!single) {
        data.stores.forEach(function (s) {
          var item = document.createElement("span");
          var key = document.createElement("i");
          key.style.background = seriesColor(s);
          item.appendChild(key);
          item.appendChild(document.createTextNode(s.name));
          legend.appendChild(item);
        });
      }

      // التلميح والخط العمودي
      var tip = document.createElement("div");
      tip.className = "chart-tip";
      tip.style.opacity = 0;
      chartEl.appendChild(tip);
      var hit = $("#hit", chartEl), xh = $("#xh", chartEl);
      var svgEl = $("svg", chartEl);

      function show(i) {
        var r = rows[i], px = x(i);
        xh.setAttribute("x1", px); xh.setAttribute("x2", px); xh.setAttribute("visibility", "visible");
        tip.innerHTML = "";
        var dEl = document.createElement("div");
        dEl.className = "tip-date";
        dEl.textContent = dfLong.format(parseDate(r.date));
        tip.appendChild(dEl);
        var topY = H;
        data.stores.forEach(function (s, si) {
          var dot = $("#hd" + si, chartEl);
          dot.setAttribute("cx", px); dot.setAttribute("cy", y(r[s.key])); dot.setAttribute("visibility", "visible");
          topY = Math.min(topY, y(r[s.key]));
          var row = document.createElement("div");
          row.className = "tip-row";
          var val = document.createElement("strong");
          val.textContent = nf.format(r[s.key]) + " ر.س";
          var keyWrap = document.createElement("span");
          keyWrap.className = "tip-key";
          var k = document.createElement("i");
          k.style.background = seriesColor(s);
          keyWrap.appendChild(k);
          keyWrap.appendChild(document.createTextNode(s.name + " · " + r[s.key + "_orders"] + " طلب"));
          row.appendChild(val);
          row.appendChild(keyWrap);
          tip.appendChild(row);
        });
        var scale = chartEl.clientWidth / W;
        var left = Math.min(Math.max(px * scale, 90), chartEl.clientWidth - 90);
        tip.style.left = left + "px";
        tip.style.top = Math.max(topY * scale - 14, 40) + "px";
        tip.style.opacity = 1;
      }
      function hide() {
        tip.style.opacity = 0;
        xh.setAttribute("visibility", "hidden");
        data.stores.forEach(function (s, si) { $("#hd" + si, chartEl).setAttribute("visibility", "hidden"); });
      }
      var focusIdx = rows.length - 1;
      hit.addEventListener("pointermove", function (e) {
        var rect = svgEl.getBoundingClientRect();
        var sx = (e.clientX - rect.left) / rect.width * W;
        var i = Math.round((sx - pad.l) / iw * (rows.length - 1));
        focusIdx = Math.max(0, Math.min(rows.length - 1, i));
        show(focusIdx);
      });
      hit.addEventListener("pointerleave", hide);
      hit.addEventListener("focus", function () { show(focusIdx); });
      hit.addEventListener("blur", hide);
      hit.addEventListener("keydown", function (e) {
        if (e.key === "ArrowLeft") focusIdx = Math.max(0, focusIdx - 1);
        else if (e.key === "ArrowRight") focusIdx = Math.min(rows.length - 1, focusIdx + 1);
        else return;
        e.preventDefault();
        show(focusIdx);
      });
    }

    function drawTable(rows) {
      var table = document.createElement("table");
      var thead = table.createTHead().insertRow();
      ["التاريخ"].concat(data.stores.map(function (s) { return s.name; })).forEach(function (h) {
        var th = document.createElement("th"); th.textContent = h; thead.appendChild(th);
      });
      var body = table.createTBody();
      rows.slice().reverse().forEach(function (r) {
        var tr = body.insertRow();
        tr.insertCell().textContent = df.format(parseDate(r.date));
        data.stores.forEach(function (s) { tr.insertCell().textContent = nf.format(r[s.key]) + " ر.س"; });
      });
      tableEl.innerHTML = "";
      tableEl.appendChild(table);
    }

    tableBtn.addEventListener("click", function () {
      var showTable = tableEl.hidden;
      tableEl.hidden = !showTable;
      chartEl.hidden = showTable;
      tableBtn.textContent = showTable ? "عرض كرسم" : "عرض كجدول";
      tableBtn.setAttribute("aria-pressed", showTable ? "true" : "false");
      if (!showTable) drawChart(windowRows(days));
    });

    radioGroup($("#range"), "data-days", function (v) { days = +v; render(); });

    var resizeTimer;
    window.addEventListener("resize", function () {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () { if (!chartEl.hidden) drawChart(windowRows(days)); }, 120);
    });
    document.addEventListener("themechange", render);
    render();
  }

  /* =========================================================
     التقارير
     ========================================================= */
  var trendEl = $("#trend-data");
  if (trendEl) initReports(JSON.parse(trendEl.textContent));

  function initReports(data) {
    var chartEl = $("#trend-chart"), tableEl = $("#trend-table"), toggle = $("#trend-table-toggle");
    var single = data.stores.length === 1;
    var color = function (s) { return single ? cssVar("--primary") : (isDark() ? s.color.dark : s.color.light); };

    var periodSel = $("#period-select");
    // نسخة العرض الثابتة: كل فترة صفحة جاهزة في مسار خاص بيها
    var isStatic = document.body.dataset.static === "1";
    var kindNow = ($("#report-form [name=kind]") || {}).value;
    var periodUrl = function (key) {
      if (isStatic) return "/" + document.body.dataset.store + "/reports/" + kindNow + "/" + key + "/";
      var url = new URL(window.location.href);
      url.searchParams.set("period", key);
      return url.toString();
    };
    if (periodSel) periodSel.addEventListener("change", function () {
      if (isStatic) window.location.href = periodUrl(periodSel.value);
      else $("#report-form").submit();
    });
    var printBtn = $("#print-btn");
    if (printBtn) printBtn.addEventListener("click", function () { window.print(); });

    function draw() {
      var rows = data.trend;
      var W = chartEl.clientWidth || 600, H = chartEl.clientHeight || 300;
      var pad = { t: 16, r: 12, b: 34, l: 48 };
      var iw = W - pad.l - pad.r, ih = H - pad.t - pad.b;
      var max = 0;
      rows.forEach(function (r) { data.stores.forEach(function (s) { max = Math.max(max, r[s.key]); }); });
      var yMax = niceMax(max * 1.05);
      var y = function (v) { return pad.t + ih - v / yMax * ih; };
      var band = iw / rows.length;
      var gap = 2, groupW = Math.min(band * 0.62, 26 * data.stores.length + gap);
      var barW = (groupW - gap * (data.stores.length - 1)) / data.stores.length;

      var svg = '<svg viewBox="0 0 ' + W + " " + H + '" direction="ltr" role="img" aria-label="المبيعات حسب الفترة">';
      for (var g = 0; g <= 4; g++) {
        var gv = yMax / 4 * g, gy = y(gv);
        svg += '<line class="grid-line" x1="' + pad.l + '" x2="' + (W - pad.r) + '" y1="' + gy + '" y2="' + gy + '"/>';
        svg += '<text class="axis-label" x="' + (pad.l - 8) + '" y="' + (gy + 4) + '" text-anchor="end">' + shortNum(gv) + "</text>";
      }
      var every = Math.max(1, Math.ceil(70 / band));  // كل تاريخ محتاج حوالي 70px
      var curIdx = rows.findIndex(function (r) { return r.key === data.current; });
      rows.forEach(function (r, i) {
        var cx = pad.l + band * i + band / 2;
        var x0 = cx - groupW / 2;
        var isCur = r.key === data.current;
        data.stores.forEach(function (s, si) {
          var v = r[s.key], top = y(v), h = Math.max(0, y(0) - top);
          var bx = x0 + si * (barW + gap), rad = Math.min(4, barW / 2, h);
          // مستطيل بحواف علوية مدوّرة 4px ومثبّت على خط الصفر
          var d = "M" + bx + " " + y(0) + " V" + (top + rad) + " Q" + bx + " " + top + " " + (bx + rad) + " " + top +
                  " H" + (bx + barW - rad) + " Q" + (bx + barW) + " " + top + " " + (bx + barW) + " " + (top + rad) + " V" + y(0) + " Z";
          svg += '<path class="bar-rect' + (isCur ? "" : " dim") + '" d="' + d + '" fill="' + color(s) + '"/>';
        });
        // تاريخ الفترة المختارة دايماً ظاهر، والتواريخ اللي جنبه بتستخبى عشان ما تتداخلش
        if (isCur || (i % every === 0 && Math.abs(i - curIdx) >= every)) {
          svg += '<text class="axis-label' + (isCur ? " x-current" : "") + '" x="' + cx + '" y="' + (H - 12) + '" text-anchor="middle">' + r.label + "</text>";
        }
        svg += '<rect class="bar-hit" data-i="' + i + '" x="' + (pad.l + band * i) + '" y="' + pad.t + '" width="' + band + '" height="' + ih + '" fill="transparent" tabindex="0"/>';
      });
      svg += "</svg>";
      chartEl.innerHTML = svg;

      var legend = $("#trend-legend");
      legend.innerHTML = "";
      if (!single) {
        data.stores.forEach(function (s) {
          var item = document.createElement("span"), key = document.createElement("i");
          key.style.background = color(s);
          item.appendChild(key);
          item.appendChild(document.createTextNode(s.name));
          legend.appendChild(item);
        });
      }

      var tip = document.createElement("div");
      tip.className = "chart-tip";
      tip.style.opacity = 0;
      chartEl.appendChild(tip);
      var svgEl = $("svg", chartEl), scale = function () { return chartEl.clientWidth / W; };

      function show(i) {
        var r = rows[i];
        tip.innerHTML = "";
        var head = document.createElement("div");
        head.className = "tip-date";
        head.textContent = r.full + (r.partial ? " (غير مكتملة)" : "");
        tip.appendChild(head);
        var top = H;
        data.stores.forEach(function (s) {
          top = Math.min(top, y(r[s.key]));
          var row = document.createElement("div"); row.className = "tip-row";
          var val = document.createElement("strong"); val.textContent = nf.format(r[s.key]) + " ر.س";
          var k = document.createElement("span"); k.className = "tip-key";
          var line = document.createElement("i"); line.style.background = color(s);
          k.appendChild(line);
          k.appendChild(document.createTextNode(s.name + " · " + nf.format(r[s.key + "_orders"]) + " طلب · ربح " + nf.format(r[s.key + "_profit"])));
          row.appendChild(val); row.appendChild(k); tip.appendChild(row);
        });
        var hint = document.createElement("div");
        hint.className = "tip-date";
        hint.style.margin = "6px 0 0";
        hint.textContent = "اضغط لفتح تقرير الفترة";
        tip.appendChild(hint);
        var cx = (pad.l + band * i + band / 2) * scale();
        tip.style.left = Math.min(Math.max(cx, 120), chartEl.clientWidth - 120) + "px";
        tip.style.top = Math.max(top * scale() - 12, 60) + "px";
        tip.style.opacity = 1;
      }
      $$(".bar-hit", svgEl).forEach(function (hit) {
        var i = +hit.dataset.i;
        hit.addEventListener("pointerenter", function () { show(i); });
        hit.addEventListener("focus", function () { show(i); });
        hit.addEventListener("pointerleave", function () { tip.style.opacity = 0; });
        hit.addEventListener("blur", function () { tip.style.opacity = 0; });
        var go = function () {
          window.location.href = periodUrl(rows[i].key);
        };
        hit.addEventListener("click", go);
        hit.addEventListener("keydown", function (e) { if (e.key === "Enter") go(); });
      });
    }

    function drawTable() {
      var table = document.createElement("table");
      var head = table.createTHead().insertRow();
      ["الفترة"].concat(data.stores.map(function (s) { return s.name; }), ["الطلبات"]).forEach(function (h) {
        var th = document.createElement("th"); th.textContent = h; head.appendChild(th);
      });
      var body = table.createTBody();
      data.trend.slice().reverse().forEach(function (r) {
        var tr = body.insertRow();
        tr.insertCell().textContent = r.full;
        var orders = 0;
        data.stores.forEach(function (s) { tr.insertCell().textContent = nf.format(r[s.key]) + " ر.س"; orders += r[s.key + "_orders"]; });
        tr.insertCell().textContent = nf.format(orders);
      });
      tableEl.innerHTML = "";
      tableEl.appendChild(table);
    }

    toggle.addEventListener("click", function () {
      var showTable = tableEl.hidden;
      tableEl.hidden = !showTable;
      chartEl.hidden = showTable;
      toggle.textContent = showTable ? "عرض كرسم" : "عرض كجدول";
      toggle.setAttribute("aria-pressed", showTable ? "true" : "false");
      if (!showTable) draw();
    });

    var t;
    window.addEventListener("resize", function () { clearTimeout(t); t = setTimeout(function () { if (!chartEl.hidden) draw(); }, 120); });
    document.addEventListener("themechange", draw);
    window.addEventListener("beforeprint", draw);
    draw();
    drawTable();
  }

  /* =========================================================
     الطلبات
     ========================================================= */
  var ordersData = $("#orders-data");
  if (ordersData) initOrders(JSON.parse(ordersData.textContent));

  function initOrders(data) {
    var byId = {};
    data.orders.forEach(function (o) { byId[o.id] = o; });
    var statusFilter = "";
    var rows = $$("#orders-table tbody tr");

    $$("[data-date]").forEach(function (td) { td.textContent = df.format(parseDate(td.dataset.date)); });

    function apply() {
      var n = 0;
      rows.forEach(function (tr) {
        var ok = (!statusFilter || tr.dataset.status === statusFilter) && matches(tr);
        tr.hidden = !ok;
        if (ok) n++;
      });
      $("#visible-count").textContent = n;
      $("#orders-empty").hidden = n > 0;
    }
    radioGroup($("#status-filter"), "data-status", function (v) { statusFilter = v; apply(); });
    searchHandlers.push(apply);

    var drawer = $("#drawer"), dScrim = $("#drawer-scrim"), current = null, lastFocus = null;
    var FLOW = ["جديد", "قيد التجهيز", "تم الشحن", "تم التسليم"];

    function open(id) {
      var o = byId[id];
      if (!o) return;
      current = o;
      lastFocus = document.activeElement;
      $("#drawer-title").textContent = "#" + o.id;
      $("#d-customer").textContent = o.customer;
      $("#d-city").textContent = o.city;
      $("#d-store").textContent = data.stores[o.store];
      $("#d-payment").textContent = o.payment;
      var money = function (v) { return nf.format(Math.round(v * 100) / 100) + " ر.س"; };
      $("#d-subtotal").textContent = money(o.subtotal);
      $("#d-discount").textContent = o.discount ? "−" + money(o.discount) : "—";
      $("#d-shipping").textContent = o.shipping ? money(o.shipping) : "مجاني";
      $("#d-vat").textContent = money(o.vat);
      $("#d-total").textContent = money(o.total);
      var lines = $("#d-lines");
      lines.innerHTML = "";
      o.lines.forEach(function (l) {
        var li = document.createElement("li");
        var a = document.createElement("span"); a.textContent = l.name + " × " + l.qty;
        var b = document.createElement("strong"); b.textContent = nf.format(l.qty * l.price) + " ر.س";
        li.appendChild(a); li.appendChild(b); lines.appendChild(li);
      });
      renderTimeline(o.status);
      $("#d-status").value = o.status;
      dScrim.hidden = false;
      requestAnimationFrame(function () { dScrim.classList.add("show"); drawer.classList.add("open"); });
      drawer.setAttribute("aria-hidden", "false");
      $("#drawer-close").focus();
    }
    function renderTimeline(status) {
      var tl = $("#d-timeline");
      tl.innerHTML = "";
      var reached = FLOW.indexOf(status);
      FLOW.forEach(function (s, i) {
        var li = document.createElement("li");
        li.textContent = s;
        if (status !== "ملغي" && i <= reached) li.className = "done";
        tl.appendChild(li);
      });
      if (status === "ملغي") {
        var c = document.createElement("li"); c.className = "cancel"; c.textContent = "ملغي"; tl.appendChild(c);
      }
    }
    function close() {
      drawer.classList.remove("open");
      dScrim.classList.remove("show");
      drawer.setAttribute("aria-hidden", "true");
      setTimeout(function () { dScrim.hidden = true; }, 250);
      if (lastFocus) lastFocus.focus();
    }

    rows.forEach(function (tr) {
      tr.addEventListener("click", function () { open(tr.dataset.id); });
      tr.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(tr.dataset.id); } });
    });
    $("#drawer-close").addEventListener("click", close);
    dScrim.addEventListener("click", close);
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && drawer.classList.contains("open")) close(); });

    $("#d-save").addEventListener("click", function () {
      if (!current) return;
      var s = $("#d-status").value;
      current.status = s;
      var tr = $('#orders-table tr[data-id="' + current.id + '"]');
      tr.dataset.status = s;
      var badge = $(".badge", tr);
      badge.className = "badge " + data.statuses[s][0];
      badge.textContent = s;
      renderTimeline(s);
      apply();
      toast("تم تحديث حالة الطلب #" + current.id + " (تجريبي)");
    });
  }

  /* =========================================================
     المنتجات
     ========================================================= */
  var productsEl = $("#products");
  if (productsEl) {
    var pFilter = "";
    var cards = $$(".product", productsEl);
    var applyProducts = function () {
      var n = 0;
      cards.forEach(function (c) {
        var ok = matches(c) && (!pFilter || (pFilter === "out" ? c.dataset.out === "out" : c.dataset.status === pFilter));
        c.hidden = !ok;
        if (ok) n++;
      });
      $("#visible-count").textContent = n;
      $("#products-empty").hidden = n > 0;
    };
    radioGroup($("#product-filter"), "data-filter", function (v) { pFilter = v; applyProducts(); });
    searchHandlers.push(applyProducts);

    var setView = function (v) {
      productsEl.classList.toggle("as-list", v === "list");
      store("productView", v);
    };
    radioGroup($("#view-toggle"), "data-view", setView);
    if (store("productView") === "list") {
      var listBtn = $('#view-toggle [data-view="list"]');
      if (listBtn) listBtn.click();
    }
  }

  /* =========================================================
     المخزون: خطة إعادة الطلب
     ========================================================= */
  var stockTable = $("#stock-table");
  if (stockTable) {
    var sFilter = "";
    var sRows = $$("tbody tr", stockTable);
    var lead = +stockTable.dataset.lead, safety = +stockTable.dataset.safety;
    var STATE = {
      out: ["danger", "نافد"], reorder: ["danger", "اطلب الآن"], soon: ["warn", "اطلب قريباً"],
      ok: ["ok", "متوفر"], over: ["info", "مخزون راكد"]
    };
    var stateOf = function (q, v) {
      var cover = v ? q / v : Infinity;
      if (q === 0 && v) return "out";
      if (q <= v * (lead + safety)) return "reorder";
      if (cover <= lead + safety + 7) return "soon";
      if (cover > 90) return "over";
      return "ok";
    };
    var paint = function (tr) {
      var q = +tr.dataset.stock, v = +tr.dataset.velocity;
      var cover = v ? q / v : Infinity;
      var st = stateOf(q, v);
      tr.dataset.state = st;
      var meter = $("[data-meter]", tr);
      meter.className = STATE[st][0];
      meter.style.setProperty("--w", (cover === Infinity ? 100 : Math.min(100, cover / 60 * 100)) + "%");
      $("[data-cover]", tr).textContent = cover === Infinity ? "—" : Math.round(cover) + " يوم";
      var dateCell = $("[data-date]", tr);
      if (cover === Infinity || q === 0) dateCell.textContent = q === 0 ? "نافد الآن" : "—";
      else {
        var d = new Date(); d.setDate(d.getDate() + Math.floor(cover));
        dateCell.textContent = df.format(d);
      }
      var cell = $("[data-state-cell]", tr);
      cell.innerHTML = "";
      var b = document.createElement("span");
      b.className = "badge " + STATE[st][0];
      b.textContent = STATE[st][1];
      cell.appendChild(b);
    };
    var applyStock = function () {
      var n = 0;
      sRows.forEach(function (tr) {
        var ok = matches(tr) && (!sFilter || tr.dataset.state === sFilter);
        tr.hidden = !ok;
        if (ok) n++;
      });
      $("#stock-empty").hidden = n > 0;
    };

    var toastTimer;
    sRows.forEach(function (tr) {
      paint(tr);
      $$("[data-step]", tr).forEach(function (btn) {
        btn.addEventListener("click", function () {
          var q = Math.max(0, +tr.dataset.stock + +btn.dataset.step);
          tr.dataset.stock = q;
          var out = $("[data-qty]", tr);
          out.textContent = q;
          out.classList.remove("bump");
          void out.offsetWidth;
          out.classList.add("bump");
          paint(tr);
          clearTimeout(toastTimer);
          toastTimer = setTimeout(function () { toast("تم تعديل الكمية (تجريبي، لن تُحفظ في سلة)"); }, 700);
        });
      });
    });
    radioGroup($("#stock-filter"), "data-filter", function (v) { sFilter = v; applyStock(); });
    searchHandlers.push(applyStock);
  }

  /* =========================================================
     جرس التنبيهات
     ========================================================= */
  var bellBtn = $("#bell-btn"), bellPanel = $("#bell-panel");
  if (bellBtn) {
    var setBell = function (open) {
      bellPanel.hidden = !open;
      bellBtn.setAttribute("aria-expanded", open ? "true" : "false");
    };
    bellBtn.addEventListener("click", function (e) { e.stopPropagation(); setBell(bellPanel.hidden); });
    document.addEventListener("click", function (e) { if (!bellPanel.hidden && !bellPanel.contains(e.target)) setBell(false); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") setBell(false); });
  }

  /* =========================================================
     الرؤى: فلترة حسب الأهمية
     ========================================================= */
  var insightList = $("#insights");
  if (insightList) {
    var iFilter = "";
    var cardsI = $$(".insight", insightList);
    var applyI = function () {
      cardsI.forEach(function (c) { c.hidden = !(matches(c) && (!iFilter || c.dataset.severity === iFilter)); });
    };
    radioGroup($("#insight-filter"), "data-filter", function (v) { iFilter = v; applyI(); });
    searchHandlers.push(applyI);
  }

  /* =========================================================
     محاكي القرارات
     ========================================================= */
  var simEl = $("#sim-data");
  if (simEl) initSimulator(JSON.parse(simEl.textContent));

  function initSimulator(d) {
    var stores = Object.keys(d.free_over).filter(function (s) { return $("#lv-free-" + s); });
    var r = d.vat;
    var base = {
      price: 0, disc: 1, ads: 0, elastic: d.elasticity,
      free: Object.assign({}, d.free_over), fee: Object.assign({}, d.fee)
    };
    var adMarginRate = 0;  // ربح لكل ريال مبيعات قبل الإعلانات

    // كل طلب: [المتجر، المنتجات بعد الخصم، الخصم، الشحن، تكلفة البضاعة، تكلفة الشحن، نسبة رسوم الدفع]
    function run(sc) {
      var orders = 0, gross = 0, profit = 0, shipNet = 0;
      var vol = Math.max(0, 1 + sc.elastic * sc.price / 100);
      d.orders.forEach(function (o) {
        var store = o[0], merch = o[1], disc = o[2], cogs = o[4], shipCost = o[5], feeRate = o[6];
        var subtotal = merch + disc;
        var newDisc = disc * sc.disc;
        var newMerch = (subtotal - newDisc) * (1 + sc.price / 100);
        // الكوبونات: تقليل الخصم بيقلل طلباتها شوية، وزيادته بتزوّدها شوية
        var w = vol;
        if (disc > 0) w *= sc.disc < 1 ? 1 - 0.35 * (1 - sc.disc) : 1 + 0.2 * (sc.disc - 1);
        var ship = newMerch >= sc.free[store] ? 0 : sc.fee[store];
        var g = newMerch + ship;
        var net = g / (1 + r);
        var p = net - cogs - shipCost - g * feeRate;
        orders += w; gross += g * w; profit += p * w;
        shipNet += (ship / (1 + r) - shipCost) * w;
      });
      if (!adMarginRate) adMarginRate = profit / gross;
      // الإعلانات: المبيعات الإضافية بعائد متناقص
      var spend = d.ad_spend * (1 + sc.ads / 100);
      var roas = d.ad_spend ? d.ad_revenue / d.ad_spend : 0;
      var extraRev = d.ad_spend * sc.ads / 100 * roas * (sc.ads > 0 ? d.ad_marginal : 1);
      var aov = gross / orders;
      orders += aov ? extraRev / aov : 0;
      gross += extraRev;
      profit += extraRev * adMarginRate;
      var scale = 30 / d.window;
      return { orders: orders * scale, gross: gross * scale, ship: shipNet * scale, ads: spend * scale, profit: (profit - spend) * scale };
    }

    function read() {
      var sc = {
        price: +$("#lv-price").value, disc: +$("#lv-disc").value / 100, ads: +$("#lv-ads").value,
        elastic: +$("#lv-elastic").value, free: {}, fee: {}
      };
      stores.forEach(function (s) { sc.free[s] = +$("#lv-free-" + s).value; sc.fee[s] = +$("#lv-fee-" + s).value; });
      Object.keys(base.free).forEach(function (s) { if (!(s in sc.free)) { sc.free[s] = base.free[s]; sc.fee[s] = base.fee[s]; } });
      return sc;
    }
    var fmt = function (v) { return (v < 0 ? "−" : "") + nf.format(Math.abs(Math.round(v))); };
    function setDelta(el, cur, b, invert) {
      var diff = cur - b;
      if (Math.abs(diff) < 0.5) { el.className = "small muted"; el.textContent = "بدون تغيير"; return; }
      var good = (diff > 0) !== !!invert;
      el.className = "delta " + (good ? "up" : "down");
      el.textContent = (diff > 0 ? "+" : "−") + nf.format(Math.abs(Math.round(diff)));
    }

    var baseline;
    function update() {
      var sc = read();
      $("#out-price").textContent = (sc.price > 0 ? "+" : "") + sc.price + "%";
      $("#out-disc").textContent = Math.round(sc.disc * 100) + "%";
      $("#out-ads").textContent = (sc.ads > 0 ? "+" : "") + sc.ads + "%";
      $("#out-elastic").textContent = sc.elastic.toFixed(1);
      stores.forEach(function (s) {
        $("#out-free-" + s).textContent = sc.free[s] ? sc.free[s] + " ر.س" : "دايماً مجاني";
        $("#out-fee-" + s).textContent = sc.fee[s] + " ر.س";
      });
      var bsc = JSON.parse(JSON.stringify(base)); bsc.elastic = sc.elastic;
      baseline = run(bsc);
      var res = run(sc);

      $("#r-profit").textContent = fmt(res.profit);
      $("#r-profit").classList.toggle("neg", res.profit < 0);
      var pd = res.profit - baseline.profit;
      var pde = $("#r-profit-delta");
      if (Math.abs(pd) < 1) { pde.className = "delta"; pde.textContent = ""; }
      else {
        pde.className = "delta " + (pd > 0 ? "up" : "down");
        pde.textContent = (pd > 0 ? "▲ +" : "▼ −") + nf.format(Math.abs(Math.round(pd))) + " ر.س";
      }
      $("#r-profit-base").textContent = "الوضع الحالي: " + fmt(baseline.profit) + " ر.س شهرياً";
      [["orders", false], ["gross", false], ["ship", false], ["ads", true]].forEach(function (k) {
        $("#r-" + k[0]).textContent = fmt(res[k[0]]);
        $("#r-" + k[0]).classList.toggle("neg", res[k[0]] < -0.5);
        setDelta($("#r-" + k[0] + "-d"), res[k[0]], baseline[k[0]], k[1]);
      });

      // أثر كل قرار لوحده
      var levers = [
        ["الأسعار", function (x) { x.price = sc.price; }],
        ["الخصومات", function (x) { x.disc = sc.disc; }],
        ["الشحن", function (x) { x.free = sc.free; x.fee = sc.fee; }],
        ["الإعلانات", function (x) { x.ads = sc.ads; }]
      ];
      var contrib = levers.map(function (l) {
        var x = JSON.parse(JSON.stringify(bsc)); l[1](x);
        return { name: l[0], v: run(x).profit - baseline.profit };
      });
      var maxAbs = Math.max.apply(null, contrib.map(function (c) { return Math.abs(c.v); }).concat([1]));
      var list = $("#r-contrib");
      list.innerHTML = "";
      contrib.forEach(function (c) {
        var li = document.createElement("li");
        var name = document.createElement("span"); name.className = "contrib-name"; name.textContent = c.name;
        var track = document.createElement("div"); track.className = "contrib-track";
        var bar = document.createElement("span");
        bar.className = "contrib-bar " + (c.v >= 0 ? "pos" : "neg-bar");
        bar.style.setProperty("--w", (Math.abs(c.v) / maxAbs * 50) + "%");
        track.appendChild(bar);
        var val = document.createElement("strong"); val.className = "num contrib-val " + (c.v < -0.5 ? "neg" : "");
        val.textContent = Math.abs(c.v) < 0.5 ? "0" : (c.v > 0 ? "+" : "−") + nf.format(Math.abs(Math.round(c.v)));
        li.appendChild(name); li.appendChild(track); li.appendChild(val);
        list.appendChild(li);
      });
    }

    $$(".sim-controls input[type=range]").forEach(function (inp) { inp.addEventListener("input", update); });

    var setVal = function (id, v) { var el = $(id); if (el) el.value = v; };
    function reset() {
      setVal("#lv-price", 0); setVal("#lv-disc", 100); setVal("#lv-ads", 0);
      stores.forEach(function (s) { setVal("#lv-free-" + s, base.free[s]); setVal("#lv-fee-" + s, base.fee[s]); });
    }
    $("#sim-presets").addEventListener("click", function (e) {
      var b = e.target.closest("[data-preset]");
      if (!b) return;
      reset();
      var p = b.dataset.preset;
      if (p === "price5") setVal("#lv-price", 5);
      if (p === "ship") stores.forEach(function (s) { setVal("#lv-free-" + s, base.free[s] + 50); });
      if (p === "nodisc") setVal("#lv-disc", 50);
      if (p === "ads") setVal("#lv-ads", 30);
      update();
    });
    update();
  }
})();
