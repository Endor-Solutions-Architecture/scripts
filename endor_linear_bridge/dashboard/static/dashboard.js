/* Deliveries trace drawer: swaps content when a log row is clicked.
   Read-only — renders data embedded in the page, makes no requests. */

(function () {
  var dataElement = document.getElementById("delivery-data");
  if (!dataElement) return;
  var drawerData = JSON.parse(dataElement.textContent);

  function text(id, value) {
    document.getElementById(id).textContent = value;
  }

  function render(delivery) {
    text("drawer-target", delivery.target);
    text("drawer-sub", delivery.subtitle);
    text("drawer-uuid", delivery.notification_uuid);
    text("drawer-linear", delivery.linear);
    text("drawer-parent", delivery.parent);
    text(
      "drawer-findings",
      delivery.findings_stored === null ? "—" : String(delivery.findings_stored)
    );

    var steps = document.getElementById("drawer-steps");
    steps.textContent = "";
    delivery.steps.forEach(function (step) {
      var row = document.createElement("div");
      row.className = "trace-step";

      var icon = document.createElement("span");
      icon.className =
        "material-symbols-rounded " + (step.ok ? "ok-icon" : "fail-icon");
      icon.textContent = step.ok ? "check" : "close";

      var label = document.createElement("span");
      label.className = "trace-label";
      label.textContent = step.step;

      var detail = document.createElement("span");
      detail.className = "trace-detail";
      detail.textContent = step.detail || "";

      row.append(icon, label, detail);
      steps.appendChild(row);
    });

    var severity = document.getElementById("drawer-severity");
    severity.textContent = "";
    var any = false;
    delivery.severity.forEach(function (row) {
      if (!row.count) return;
      any = true;
      var line = document.createElement("div");
      line.className = "severity-row";

      var label = document.createElement("span");
      label.className = "severity-label " + row.css;
      label.textContent = row.label;

      var track = document.createElement("div");
      track.className = "severity-track slim";
      var fill = document.createElement("div");
      fill.className = "severity-fill " + row.css;
      fill.style.width = row.pct + "%";
      track.appendChild(fill);

      var count = document.createElement("span");
      count.className = "severity-count";
      count.textContent = String(row.count);

      line.append(label, track, count);
      severity.appendChild(line);
    });

    var box = document.getElementById("drawer-severity-box");
    box.style.display = any ? "" : "none";
    if (delivery.priority !== null) {
      var names = { 1: "Urgent", 2: "High", 3: "Medium", 4: "Low" };
      text(
        "drawer-priority",
        "Issue priority " + delivery.priority + " · " + names[delivery.priority] +
          " — from max severity across the stored union, not this payload alone."
      );
    } else {
      text("drawer-priority", "");
    }
  }

  var rows = document.querySelectorAll("[data-delivery-id]");
  rows.forEach(function (row) {
    row.addEventListener("click", function () {
      rows.forEach(function (other) { other.classList.remove("selected"); });
      row.classList.add("selected");
      var delivery = drawerData[row.dataset.deliveryId];
      if (delivery) render(delivery);
    });
  });

  // The drawer is always populated: default to the newest delivery.
  var first = document.querySelector("[data-delivery-id]");
  if (first) {
    var newest = drawerData[first.dataset.deliveryId];
    if (newest) render(newest);
  }
})();
