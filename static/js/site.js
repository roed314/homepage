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
      var topic = tr.getAttribute('data-topic');
      var isSem = (type === 'sem' || type === 'coll');
      var isConf = (type === 'conf');
      var typeOk = isConf ? confs : (isSem ? sems : (confs || sems));
      var show = typeOk && !(latest && topic && seen[topic]);
      if (show && latest && topic) seen[topic] = true;
      tr.style.display = show ? '' : 'none';
    });
  }

  Object.keys(boxes).forEach(function (k) {
    boxes[k].addEventListener('change', apply);
  });
})();
