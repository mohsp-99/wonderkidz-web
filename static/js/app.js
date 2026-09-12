/* WonderKidz — shared client behaviour (adapted from the mockup shared.js). Server-driven bits use htmx. */
(function () {
  'use strict';
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };

  function initBurger() {
    var b = $('[data-burger]'), m = $('[data-mobnav]');
    if (!b || !m) return;
    b.addEventListener('click', function () { m.classList.toggle('is-open'); });
  }

  function initCity() {
    var pill = $('[data-city]'), panel = $('#city-panel');
    if (!pill || !panel) return;
    pill.addEventListener('click', function (e) { e.stopPropagation(); panel.hidden = !panel.hidden; });
    document.addEventListener('click', function (e) { if (!panel.hidden && !panel.contains(e.target)) panel.hidden = true; });
  }

  function initTabs() {
    $$('[data-tabgroup]').forEach(function (group) {
      var btns = $$('[data-tab]', group);
      function activate(btn, push) {
        btns.forEach(function (b) { b.classList.remove('is-on'); });
        btn.classList.add('is-on');
        var scope = group.dataset.tabscope ? $(group.dataset.tabscope) : document;
        $$('.tabpane', scope).forEach(function (p) {
          if (p.id === btn.dataset.tab) p.classList.add('is-on'); else p.classList.remove('is-on');
        });
        if (push && history.replaceState) history.replaceState(null, '', '#' + btn.dataset.tab);
      }
      btns.forEach(function (btn) { btn.addEventListener('click', function () { activate(btn, true); }); });
      var hash = location.hash.replace('#', '');
      var initial = btns.filter(function (b) { return b.dataset.tab === hash; })[0];
      if (initial) activate(initial, false);
    });
  }

  function initDrawer() {
    var panel = $('[data-filters]');
    if (!panel) return;
    var scrim = document.createElement('div');
    scrim.className = 'scrim';
    document.body.appendChild(scrim);
    function open() { panel.classList.add('is-open'); scrim.classList.add('is-open'); }
    function close() { panel.classList.remove('is-open'); scrim.classList.remove('is-open'); }
    $$('[data-openfilters]').forEach(function (b) { b.addEventListener('click', open); });
    $$('[data-closefilters]').forEach(function (b) { b.addEventListener('click', close); });
    scrim.addEventListener('click', close);
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
  }

  function initGallery() {
    var main = $('[data-galmain]');
    if (!main) return;
    $$('[data-gal]').forEach(function (t) {
      t.addEventListener('click', function () {
        $$('[data-gal]').forEach(function (x) { x.classList.remove('is-on'); });
        t.classList.add('is-on');
        var img = $('img', main);
        if (img) img.src = t.dataset.gal;
        var c = $('.ph-count', main);
        if (c) c.textContent = t.dataset.galidx;
      });
    });
  }

  function initOtp() {
    var boxes = $$('.otp-inputs input');
    if (!boxes.length) return;
    var hidden = $('#otp-code');
    var submit = $('#otp-submit');
    var FA = '۰۱۲۳۴۵۶۷۸۹';
    function sync() {
      var v = boxes.map(function (b) { return b.value; }).join('');
      v = v.replace(/[۰-۹]/g, function (d) { return String(FA.indexOf(d)); });
      if (hidden) hidden.value = v;
      var done = boxes.every(function (b) { return b.value; });
      if (submit) submit.disabled = !done;
      if (done && submit && submit.form && !submit.form.dataset.autoSubmitted) {
        submit.form.dataset.autoSubmitted = '1';
        submit.form.requestSubmit ? submit.form.requestSubmit() : submit.form.submit();
      }
    }
    boxes.forEach(function (inp, i) {
      inp.addEventListener('input', function () {
        var v = inp.value.replace(/[^0-9۰-۹]/g, '');
        if (v.length > 1) { // pasted full code
          v.split('').forEach(function (ch, j) { if (boxes[i + j]) boxes[i + j].value = ch; });
          var last = boxes[Math.min(boxes.length - 1, i + v.length - 1)];
          last.focus();
        } else {
          inp.value = v;
          if (v && boxes[i + 1]) boxes[i + 1].focus();
        }
        sync();
      });
      inp.addEventListener('keydown', function (e) {
        if (e.key === 'Backspace' && !inp.value && boxes[i - 1]) boxes[i - 1].focus();
      });
    });
    boxes[0].focus();
    var timerEl = $('#otp-timer'), resend = $('#otp-resend');
    if (timerEl) {
      var left = parseInt(timerEl.dataset.seconds || '120', 10);
      var tick = function () {
        var m = Math.floor(left / 60), s = left % 60;
        timerEl.querySelector('b').textContent = toFa(m + ':' + (s < 10 ? '0' + s : s));
        if (left-- <= 0) { clearInterval(t); timerEl.hidden = true; if (resend) resend.hidden = false; }
      };
      tick();
      var t = setInterval(tick, 1000);
    }
  }

  function initPhoneMask() {
    $$('[data-phone-input]').forEach(function (inp) {
      inp.addEventListener('input', function () {
        inp.value = inp.value.replace(/[۰-۹]/g, function (d) { return String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)); }).replace(/[^\d+]/g, '');
      });
    });
    $$('[data-numeric]').forEach(function (inp) {
      inp.addEventListener('input', function () {
        var v = inp.value.replace(/[۰-۹]/g, function (d) { return String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)); }).replace(/[^\d]/g, '');
        inp.value = v ? toFa(Number(v).toLocaleString('en-US')).replace(/,/g, '٬') : '';
      });
    });
  }

  function initCopy() {
    document.addEventListener('click', function (e) {
      var b = e.target.closest('[data-copy]');
      if (!b) return;
      navigator.clipboard && navigator.clipboard.writeText(b.dataset.copy).then(function () {
        var old = b.textContent; b.textContent = 'کپی شد ✓'; setTimeout(function () { b.textContent = old; }, 1500);
      });
    });
  }

  var FA = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
  function toFa(s) { return String(s).replace(/[0-9]/g, function (d) { return FA[+d]; }); }
  window.wkToFa = toFa;

  function initChatScroll() {
    var box = $('.ct-msgs');
    if (box) box.scrollTop = box.scrollHeight;
    document.body.addEventListener('htmx:afterSwap', function (e) {
      var b = e.target.classList && e.target.classList.contains('ct-msgs') ? e.target : $('.ct-msgs', e.target);
      if (b) b.scrollTop = b.scrollHeight;
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    initBurger(); initCity(); initTabs(); initDrawer(); initGallery(); initOtp(); initPhoneMask(); initCopy(); initChatScroll();
    if ('serviceWorker' in navigator && location.protocol === 'https:') navigator.serviceWorker.register('/sw.js').catch(function () {});
  });
})();
