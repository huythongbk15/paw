/* The PAW local web shell client.
 *
 * Rules this file keeps:
 *  - it holds the CSRF token **in memory only**: it is fetched over the
 *    same origin, never written to localStorage, a cookie, or a URL;
 *  - it never renders raw HTML from the API: every value goes through
 *    textContent, so a value cannot become markup;
 *  - a send is **idempotent**: the request key is minted once for a
 *    composed message and reused if the request is retried, so a repeat
 *    resolves to the same durable operation rather than a second attempt;
 *  - it reads durable state, so a reload or a reconnect loses nothing;
 *  - it distinguishes loading, empty, error and unavailable.
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
    refresh: document.getElementById("refresh"),
    composer: document.getElementById("composer"),
    composerInput: document.getElementById("composer-input"),
    composerSend: document.getElementById("composer-send"),
    composerHint: document.getElementById("composer-hint")
  };

  var current = { view: "chat", taskId: "", sessionId: "" };
  /* The token lives here and nowhere else. */
  var csrfToken = "";
  /* The key for the message being composed, so a retry is the same turn. */
  var pendingKey = "";

  function setChip(node, label, value) {
    if (!node) { return; }
    var b = node.querySelector("b");
    if (b) { b.textContent = value; } else { node.textContent = label + " " + value; }
  }

  function showToast(message) {
    if (!el.toast) { return; }
    el.toast.textContent = message;
    el.toast.hidden = false;
    window.setTimeout(function () { el.toast.hidden = true; }, 8000);
  }

  function clear(node) {
    while (node && node.firstChild) { node.removeChild(node.firstChild); }
  }

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

  function request(path, options) {
    var opts = options || {};
    var init = {
      method: opts.method || "GET",
      credentials: "omit",
      headers: { "Accept": "application/json" }
    };
    if (opts.body !== undefined) {
      init.headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(opts.body);
    }
    if (opts.method && opts.method !== "GET") {
      if (!csrfToken) {
        return Promise.reject(new Error("Chưa có token cục bộ; tải lại trang."));
      }
      init.headers["X-CSRF-Token"] = csrfToken;
    }
    return fetch(API + path, init).then(function (response) {
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

  /* The token, fetched over the same origin and kept in memory. */
  function loadToken() {
    return request("/csrf-token").then(function (body) {
      csrfToken = (body && body.csrf_token) || "";
      return csrfToken;
    });
  }

  function loadSession() {
    return request("/session").then(function (body) {
      current.sessionId = (body && body.session_id) || "";
      setChip(el.stateProfile, "profile:", (body && body.status) || "—");
      return body;
    }).catch(function () {
      current.sessionId = "";
      return null;
    });
  }

  function newKey() {
    if (window.crypto && window.crypto.randomUUID) {
      return window.crypto.randomUUID();
    }
    return "k-" + Date.now() + "-" + Math.floor(Math.random() * 1e9);
  }

  function renderChat(messages) {
    clear(el.view);
    if (!messages.length) {
      renderState(el.view, "empty", "Chưa có tin nhắn",
        "Gửi một yêu cầu để PAW bắt đầu. Một lần gửi là một lần phê duyệt.");
      return;
    }
    messages.forEach(function (message) {
      var block = document.createElement("div");
      block.className = "msg msg-" + (message.role || "user");
      var who = document.createElement("p");
      who.className = "msg-role";
      who.textContent = message.role === "assistant" ? "PAW" : "Bạn";
      var body = document.createElement("p");
      body.className = "msg-body";
      body.textContent = message.content || "";
      block.appendChild(who);
      block.appendChild(body);
      el.view.appendChild(block);
    });
  }

  function loadChat() {
    if (!current.sessionId) {
      renderState(el.view, "unavailable", "Chưa có phiên",
        "Bề mặt này chưa có phiên để nói chuyện.");
      return Promise.resolve();
    }
    return request("/sessions/" + encodeURIComponent(current.sessionId) + "/messages?limit=50")
      .then(function (page) {
        renderChat((page && page.items) || []);
      }).catch(function (error) {
        renderState(el.view, "error", "Không tải được tin nhắn", error.message);
      });
  }

  function sendMessage(text) {
    if (!current.sessionId) {
      showToast("Chưa có phiên để gửi.");
      return Promise.resolve();
    }
    if (!pendingKey) { pendingKey = newKey(); }
    el.composerSend.disabled = true;
    el.composerHint.textContent = "Đang gửi…";
    return request("/sessions/" + encodeURIComponent(current.sessionId) + "/messages", {
      method: "POST",
      body: { text: text, request_key: pendingKey }
    }).then(function (reply) {
      pendingKey = "";
      el.composerInput.value = "";
      setChip(el.stateTask, "task:", reply.task_id || "—");
      if (reply.waiting_for_approval) {
        el.composerHint.textContent = "Đang chờ bạn phê duyệt.";
        showToast("PAW cần bạn phê duyệt tác động này.");
      } else {
        el.composerHint.textContent = "Một lần gửi = một phiếu duyệt.";
      }
      return loadChat();
    }).catch(function (error) {
      el.composerHint.textContent = "Một lần gửi = một phiếu duyệt.";
      showToast(error.message);
    }).then(function () {
      el.composerSend.disabled = false;
      el.composerInput.focus();
    });
  }

  /* The approval card: what PAW is asking a human to allow. It is the
   * one mutating affordance the read-only surface did not have, and it
   * is deliberately explicit - the person sees the operation, the
   * capabilities and the proposed change before deciding. */
  function renderApproval(approval) {
    clear(el.view);
    var card = document.createElement("div");
    card.className = "approval";

    var title = document.createElement("p");
    title.className = "approval-title";
    title.textContent = "PAW cần bạn cho phép một tác động.";
    card.appendChild(title);

    var what = document.createElement("dl");
    what.className = "approval-what";
    [
      ["Tác động", approval.operation || approval.operation_id],
      ["Năng lực", (approval.capabilities || []).join(", ")],
      ["Đường dẫn", approval.path],
      ["Lý do", approval.policy_reason]
    ].forEach(function (pair) {
      var dt = document.createElement("dt");
      dt.textContent = pair[0];
      var dd = document.createElement("dd");
      dd.textContent = pair[1] || "—";
      what.appendChild(dt);
      what.appendChild(dd);
    });
    card.appendChild(what);

    if (approval.change_preview) {
      var pre = document.createElement("pre");
      pre.className = "approval-preview";
      pre.textContent = approval.change_preview;
      card.appendChild(pre);
    }

    var row = document.createElement("div");
    row.className = "approval-row";
    var approve = document.createElement("button");
    approve.type = "button";
    approve.className = "btn btn-primary";
    approve.textContent = "Cho phép";
    approve.addEventListener("click", function () { decide(approval.approval_id, "approve"); });
    var deny = document.createElement("button");
    deny.type = "button";
    deny.className = "btn";
    deny.textContent = "Từ chối";
    deny.addEventListener("click", function () { decide(approval.approval_id, "deny"); });
    row.appendChild(approve);
    row.appendChild(deny);
    card.appendChild(row);

    el.view.appendChild(card);
  }

  function decide(approvalId, decision) {
    request("/sessions/" + encodeURIComponent(current.sessionId) + "/approvals", {
      method: "POST",
      body: {
        approval_id: approvalId,
        decision: decision,
        request_key: newKey()
      }
    }).then(function (reply) {
      showToast(decision === "approve"
        ? "Đã cho phép. PAW tiếp tục tác động."
        : "Đã từ chối tác động này.");
      return loadChat();
    }).then(function () {
      return loadPendingApproval();
    }).catch(function (error) {
      showToast(error.message);
    });
  }

  function loadPendingApproval() {
    if (!current.sessionId) { return Promise.resolve(); }
    return request("/sessions/" + encodeURIComponent(current.sessionId) + "/approval")
      .then(function (approval) {
        if (approval && approval.approval_id) {
          renderApproval(approval);
        } else {
          return loadChat();
        }
      })
      .catch(function (error) {
        // No pending approval is the normal case, not an error.
        if (error && error.code === "web.no_pending_approval") {
          return loadChat();
        }
        return loadChat();
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
      ], items, "Chưa có session nào.");
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
      ], rows, "Chưa có task nào.");
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
      renderJson(el.inspect, results.map(function (item) {
        return { kind: item.kind, value: item.error ? ("— " + item.error) : item.body };
      }));
    });
  }

  function loadCapabilities() {
    renderState(el.view, "loading", "Đang tải capabilities…", "Một khoảnh khắc.");
    return request("/capabilities").then(function (body) {
      renderJson(el.view, body);
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
    chat: { title: "Chat", load: loadPendingApproval },
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

  el.composer.addEventListener("submit", function (event) {
    event.preventDefault();
    var text = el.composerInput.value.trim();
    if (!text) { return; }
    sendMessage(text);
  });

  el.composerInput.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      el.composer.requestSubmit ? el.composer.requestSubmit()
        : el.composer.dispatchEvent(new Event("submit", { cancelable: true }));
    }
  });

  /* The token and the session come first: without them the surface is
   * read-only, and the composer says so. */
  loadToken()
    .then(loadSession)
    .then(function () { show("chat"); })
    .catch(function (error) {
      renderState(el.view, "unavailable", "Bề mặt chưa sẵn sàng", error.message);
      if (el.composerSend) { el.composerSend.disabled = true; }
    });
}());
