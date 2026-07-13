// Mobile top-nav toggle
(function () {
  var toggle = document.getElementById('nav-toggle');
  if (toggle) {
    toggle.addEventListener('click', function () {
      var nav = document.getElementById('topnav');
      var open = nav.classList.toggle('open');
      toggle.setAttribute('aria-expanded', open);
    });
  }
})();

// Talk filters: conference / seminar / most-recent-per-topic.
// Untyped talks count as both conference and seminar (the old site hid them
// once any filter changed; that was a bug).
(function () {
  var tbody = document.querySelector('#talks-table tbody');
  if (!tbody) return;
  var boxes = {
    conf: document.getElementById('opt-show-conf'),
    sem: document.getElementById('opt-show-sem'),
    one: document.getElementById('opt-show-one')
  };

  function apply() {
    var confs = boxes.conf.checked;
    var sems = boxes.sem.checked;
    var latest = boxes.one.checked;
    var seen = {};
    Array.prototype.forEach.call(tbody.children, function (tr) {
      var type = tr.getAttribute('data-type');
      var topics = (tr.getAttribute('data-topic') || '').split(' ').filter(Boolean);
      var isSem = (type === 'sem' || type === 'coll');
      var isConf = (type === 'conf');
      var typeOk = isConf ? confs : (isSem ? sems : (confs || sems));
      // A talk covering several topics stays visible as long as it is the
      // most recent visible talk for at least one of them.
      var allSeen = topics.length > 0 && topics.every(function (t) { return seen[t]; });
      var show = typeOk && !(latest && allSeen);
      if (show && latest) topics.forEach(function (t) { seen[t] = true; });
      tr.style.display = show ? '' : 'none';
    });
  }

  Object.keys(boxes).forEach(function (k) {
    boxes[k].addEventListener('change', apply);
  });
})();

// BibTeX badges copy the entry to the clipboard instead of downloading the
// .bib file (which would just need to be merged by hand).  The href stays as
// a fallback for browsers without the clipboard API.
(function () {
  if (!(navigator.clipboard && window.fetch)) return;
  Array.prototype.forEach.call(document.querySelectorAll('a.bib-copy'), function (a) {
    a.addEventListener('click', function (ev) {
      ev.preventDefault();
      if (a.classList.contains('copied')) return;
      fetch(a.getAttribute('href'))
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
        .then(function (text) { return navigator.clipboard.writeText(text); })
        .then(function () {
          var label = a.textContent;
          a.classList.add('copied');
          a.textContent = 'Copied!';
          setTimeout(function () {
            a.classList.remove('copied');
            a.textContent = label;
          }, 1500);
        })
        .catch(function () { window.location = a.href; });
    });
  });
})();
