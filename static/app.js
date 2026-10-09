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

    // خطوة مقرّبة (1، 2، 2.5، 5 × قوة 10) بحيث 4 خطوط تغطي أعلى قيمة
    function niceMax(v) {
      var raw = v / 4, mag = Math.pow(10, Math.floor(Math.log10(raw)));
      var steps = [1, 2, 2.5, 5, 10];
      for (var i = 0; i < steps.length; i++) if (steps[i] * mag >= raw) return steps[i] * mag * 4;
      return 40 * mag;
    }
    function shortNum(v) { return v >= 1000 ? +(v / 1000).toFixed(1) + "k" : String(Math.round(v)); }

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
      $("#d-total").textContent = nf.format(o.total) + " ر.س";
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
     المخزون
     ========================================================= */
  var stockTable = $("#stock-table");
  if (stockTable) {
    var sFilter = "";
    var sRows = $$("tbody tr", stockTable);
    var LOW = 10, FULL = 50;

    var paint = function (tr) {
      var q = +tr.dataset.stock;
      var meter = $("[data-meter]", tr);
      var state = q === 0 ? ["danger", "نفد"] : q <= LOW ? ["warn", "منخفض"] : ["ok", "متوفر"];
      meter.className = state[0];
      meter.style.setProperty("--w", Math.min(100, q / FULL * 100) + "%");
      var cell = $("[data-state]", tr);
      cell.innerHTML = "";
      var b = document.createElement("span");
      b.className = "badge " + state[0];
      b.textContent = state[1];
      cell.appendChild(b);
    };
    var stateOf = function (q) { return q === 0 ? "out" : q <= LOW ? "low" : "ok"; };
    var applyStock = function () {
      var n = 0;
      sRows.forEach(function (tr) {
        var ok = matches(tr) && (!sFilter || stateOf(+tr.dataset.stock) === sFilter);
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
})();
