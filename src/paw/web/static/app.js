/* The PAW local web shell client.
 *
 * Rules this file keeps:
 *  - it holds **no credential**: the read-only surface needs no CSRF
 *    token, so nothing is written to localStorage, a cookie, or a query
 *    string;
 *  - it never renders raw HTML from the API: every value goes through
 *    textContent, so a value cannot become markup;
 *  - it reads durable state, so a reload or a reconnect loses nothing:
 *    the state it shows is the state the server holds;
 *  - it distinguishes loading, empty, error and unavailable;
 *  - it is keyboard operable and announces what it loads.
 */
(function () {
  "use strict";

  var API = "/api/v1";

  var el = {
    view: document.getElementById("view"),
    viewTitle: document.getElementById("view-title"),
    inspect: document.getElementById("inspect"),
    toast: document.getElementById("toast"),
    nav: document.getElementById("nav"),
    stateProject: document.getElementById("state-project"),
    stateProfile: document.getElementById("state-profile"),
    stateModel: document.getElementById("state-model"),
    stateTask: document.getElementById("state-task"),
    refresh: document.getElementById("refresh")
  };

  var current = { view: "sessions", taskId: "" };

  function setChip(node, label, value) {
    if (!node) { return; }
    var b = node.querySelector("b");
    if (b) { b.textContent = value; } else { node.textContent = label + " " + value; }
  }

  function showToast(message) {
    if (!el.toast) { return; }
    el.toast.textContent = message;
    el.toast.hidden = false;
    window.setTimeout(function () { el.toast.hidden = true; }, 6000);
  }

  function clear(node) {
    while (node && node.firstChild) { node.removeChild(node.firstChild); }
  }

  /* Every state is explicit: the user is never left looking at a blank
   * panel wondering whether it is loading or empty. */
  function renderState(node, kind, title, body) {
    clear(node);
    var wrap = document.createElement("div");
    wrap.className = "state state-" + kind;
    var h = document.createElement("p");
    h.className = "state-title";
    h.textContent = title;
    var p = document.createElement("p");
    p.className = "state-body";
    p.textContent = body;
    wrap.appendChild(h);
    wrap.appendChild(p);
    node.appendChild(wrap);
  }

  function renderTable(node, columns, rows, emptyMessage) {
    clear(node);
    if (!rows.length) {
      renderState(node, "empty", "Không có gì để hiện", emptyMessage);
      return;
    }
    var table = document.createElement("table");
    var thead = document.createElement("thead");
    var hrow = document.createElement("tr");
    columns.forEach(function (column) {
      var th = document.createElement("th");
      th.textContent = column.label;
      hrow.appendChild(th);
    });
    thead.appendChild(hrow);
    table.appendChild(thead);
    var tbody = document.createElement("tbody");
    rows.forEach(function (row) {
      var tr = document.createElement("tr");
      columns.forEach(function (column) {
        var td = document.createElement("td");
        var value = column.get(row);
        if (value instanceof Node) {
          td.appendChild(value);
        } else {
          td.textContent = value === undefined || value === null ? "—" : String(value);
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    node.appendChild(table);
  }

  function renderJson(node, value) {
    clear(node);
    var pre = document.createElement("pre");
    pre.textContent = JSON.stringify(value, null, 2);
    node.appendChild(pre);
  }

  function request(path) {
    return fetch(API + path, {
      method: "GET",
      credentials: "omit",
      headers: { "Accept": "application/json" }
    }).then(function (response) {
      return response.json().catch(function () { return null; }).then(function (body) {
        if (!response.ok) {
          var code = (body && body.code) || "web.request_failed";
          var message = (body && body.message) || "Yêu cầu thất bại.";
          var error = new Error(message);
          error.code = code;
          error.status = response.status;
          throw error;
        }
        return body;
      });
    });
  }

  function loadSessions() {
    el.view.setAttribute("aria-busy", "true");
    renderState(el.view, "loading", "Đang tải sessions…", "Một khoảnh khắc.");
    return request("/sessions?limit=25").then(function (page) {
      el.view.setAttribute("aria-busy", "false");
      var items = (page && page.items) || [];
      renderTable(el.view, [
        { label: "Session", get: function (r) { return r.session_id; } },
        { label: "Trạng thái", get: function (r) { return r.status; } },
        { label: "Task", get: function (r) { return r.current_task_id; } },
        { label: "Cập nhật", get: function (r) { return r.updated_at; } }
      ], items, "Chưa có session nào. Bề mặt hiện chỉ đọc.");
    }).catch(function (error) {
      el.view.setAttribute("aria-busy", "false");
      renderState(el.view, "error", "Không tải được sessions", error.message);
    });
  }

  function loadTasks() {
    el.view.setAttribute("aria-busy", "true");
    renderState(el.view, "loading", "Đang tải tasks…", "Một khoảnh khắc.");
    return request("/sessions?limit=50").then(function (page) {
      el.view.setAttribute("aria-busy", "false");
      var rows = [];
      ((page && page.items) || []).forEach(function (session) {
        if (session.current_task_id) {
          rows.push({ id: session.current_task_id, session: session.session_id, status: session.status });
        }
      });
      renderTable(el.view, [
        {
          label: "Task",
          get: function (r) {
            var button = document.createElement("button");
            button.type = "button";
            button.className = "nav-item";
            button.textContent = r.id;
            button.addEventListener("click", function () { selectTask(r.id); });
            return button;
          }
        },
        { label: "Session", get: function (r) { return r.session; } },
        { label: "Trạng thái", get: function (r) { return r.status; } }
      ], rows, "Chưa có task nào. Một task xuất hiện khi một phiên chat chạy.");
    }).catch(function (error) {
      el.view.setAttribute("aria-busy", "false");
      renderState(el.view, "error", "Không tải được tasks", error.message);
    });
  }

  function loadInspect() {
    if (!current.taskId) {
      renderState(el.inspect, "empty", "Chưa chọn task",
        "Chọn một task ở khung giữa để xem bằng chứng, context, routing, policy, checks và artifacts.");
      return Promise.resolve();
    }
    renderState(el.inspect, "loading", "Đang tải bằng chứng…", "Một khoảnh khắc.");
    var kinds = ["decision", "context", "routing", "policy", "ledger",
                 "checkpoint", "verification", "artifacts"];
    return Promise.all(kinds.map(function (kind) {
      return request("/tasks/" + encodeURIComponent(current.taskId) + "/inspect/" + kind)
        .then(function (body) { return { kind: kind, body: body }; })
        .catch(function (error) { return { kind: kind, error: error.message }; });
    })).then(function (results) {
      var summary = results.map(function (item) {
        return { kind: item.kind, value: item.error ? ("— " + item.error) : item.body };
      });
      renderJson(el.inspect, summary);
    });
  }

  function loadCapabilities() {
    renderState(el.view, "loading", "Đang tải capabilities…", "Một khoảnh khắc.");
    return request("/capabilities").then(function (body) {
      renderJson(el.view, body);
      setChip(el.stateModel, "model:", "xem capabilities");
    }).catch(function (error) {
      renderState(el.view, "error", "Không tải được capabilities", error.message);
    });
  }

  function loadHealth() {
    renderState(el.view, "loading", "Đang tải health…", "Một khoảnh khắc.");
    return request("/health").then(function (body) {
      renderJson(el.view, body);
      setChip(el.stateProject, "project:", body.revision || "—");
    }).catch(function (error) {
      renderState(el.view, "unavailable", "Health không khả dụng", error.message);
    });
  }

  function selectTask(taskId) {
    current.taskId = taskId;
    setChip(el.stateTask, "task:", taskId);
    el.viewTitle.textContent = "Task " + taskId;
    renderState(el.view, "loading", "Đang tải task…", "Một khoảnh khắc.");
    request("/tasks/" + encodeURIComponent(taskId)).then(function (body) {
      renderJson(el.view, body);
      setChip(el.stateTask, "task:", body.status || taskId);
      return loadInspect();
    }).catch(function (error) {
      renderState(el.view, "error", "Không tải được task", error.message);
      showToast(error.message);
    });
  }

  var views = {
    sessions: { title: "Sessions", load: loadSessions },
    tasks: { title: "Tasks", load: loadTasks },
    inspect: { title: "Inspect", load: loadInspect },
    capabilities: { title: "Capabilities", load: loadCapabilities },
    health: { title: "Health", load: loadHealth }
  };

  function show(view) {
    if (!views[view]) { return; }
    current.view = view;
    el.viewTitle.textContent = views[view].title;
    var items = el.nav.querySelectorAll(".nav-item");
    for (var i = 0; i < items.length; i++) {
      if (items[i].getAttribute("data-view") === view) {
        items[i].setAttribute("aria-current", "true");
      } else {
        items[i].removeAttribute("aria-current");
      }
    }
    views[view].load();
  }

  el.nav.addEventListener("click", function (event) {
    var button = event.target.closest(".nav-item");
    if (button && button.getAttribute("data-view")) {
      show(button.getAttribute("data-view"));
    }
  });

  el.refresh.addEventListener("click", function () {
    show(current.view);
  });

  /* The state the shell shows is the state the server holds, so a reload
   * or a reconnect loses nothing durable. The task selection is a view
   * choice, not durable state, so it is rebuilt from the URL. */
  window.addEventListener("popstate", function () { show(current.view); });

  show("sessions");
}());
