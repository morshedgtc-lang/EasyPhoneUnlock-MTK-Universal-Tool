const API = "";
let ADMIN_TOKEN = "";

async function adminLogin() {
  const username = document.getElementById("adminUser").value.trim();
  const password = document.getElementById("adminPass").value;
  const msg = document.getElementById("loginMsg");
  msg.className = "msg";
  msg.textContent = "Signing in...";
  try {
    const res = await fetch(`${API}/api/v1/admin/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json();
    if (res.ok && data.status === "success") {
      ADMIN_TOKEN = data.admin_token;
      sessionStorage.setItem("admin_token", ADMIN_TOKEN);
      showPanel();
    } else {
      msg.className = "msg err";
      msg.textContent = data.detail || "Login failed.";
    }
  } catch (e) {
    msg.className = "msg err";
    msg.textContent = "Cannot reach server.";
  }
}

function logout() {
  ADMIN_TOKEN = "";
  sessionStorage.removeItem("admin_token");
  document.getElementById("panelView").classList.add("hidden");
  document.getElementById("loginView").classList.remove("hidden");
}

function showPanel() {
  document.getElementById("loginView").classList.add("hidden");
  document.getElementById("panelView").classList.remove("hidden");
  refreshAll();
}

function authHeaders() {
  return { "Authorization": `Bearer ${ADMIN_TOKEN}`, "Content-Type": "application/json" };
}

async function refreshAll() {
  await loadUsers();
  await loadLogs();
  await loadConfig();
}

async function loadUsers() {
  const res = await fetch(`${API}/api/v1/admin/users`, { headers: authHeaders() });
  if (!res.ok) return;
  const data = await res.json();
  const tbody = document.querySelector("#usersTable tbody");
  tbody.innerHTML = "";
  let active = 0, credits = 0, hwid = 0;
  data.users.forEach(u => {
    if (u.is_active) active++;
    credits += u.credits || 0;
    if (u.hwid) hwid++;
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${u.id}</td>
      <td>${esc(u.username)}</td>
      <td>${esc(u.email || "")}</td>
      <td class="mono">${u.credits}</td>
      <td class="mono">${u.hwid ? esc(u.hwid) : "<em>unbound</em>"}</td>
      <td class="mono">${esc(u.last_ip || "-")}</td>
      <td><span class="badge ${u.is_active ? "yes" : "no"}">${u.is_active ? "Active" : "Disabled"}</span></td>
      <td>${u.is_admin ? "★" : ""}</td>
      <td>
        ${u.is_active
          ? `<button class="mini" onclick="userAction(${u.id},'disable')">Disable</button>`
          : `<button class="mini" onclick="userAction(${u.id},'activate')">Activate</button>`}
        <button class="mini" onclick="userAction(${u.id},'reset_hwid')">Reset HWID</button>
        <button class="mini" onclick="userAction(${u.id},'delete')">Delete</button>
      </td>`;
    tbody.appendChild(tr);
  });
  document.getElementById("statUsers").textContent = data.users.length;
  document.getElementById("statActive").textContent = active;
  document.getElementById("statCredits").textContent = credits;
  document.getElementById("statHwid").textContent = hwid;
}

async function addCredits() {
  const user_id = parseInt(document.getElementById("creditUserId").value);
  const credits = parseInt(document.getElementById("creditAmount").value);
  const msg = document.getElementById("creditMsg");
  if (!user_id || !credits) { msg.className = "msg err"; msg.textContent = "Enter user ID and credits."; return; }
  const res = await fetch(`${API}/api/v1/admin/credits/add`, {
    method: "POST", headers: authHeaders(), body: JSON.stringify({ user_id, credits })
  });
  const data = await res.json();
  msg.className = res.ok ? "msg" : "msg err";
  msg.textContent = res.ok ? `Added ${credits}. New balance: ${data.new_balance}` : (data.detail || "Failed.");
  if (res.ok) { document.getElementById("creditUserId").value = ""; document.getElementById("creditAmount").value = ""; loadUsers(); }
}

async function userAction(user_id, action) {
  if (action === "delete" && !confirm("Delete this user permanently?")) return;
  const res = await fetch(`${API}/api/v1/admin/users/action`, {
    method: "POST", headers: authHeaders(), body: JSON.stringify({ user_id, action })
  });
  if (res.ok) loadUsers();
}

async function loadConfig() {
  const res = await fetch(`${API}/api/v1/system/status`);
  const data = await res.json();
  const chip = document.getElementById("maintenanceChip");
  chip.textContent = `Maintenance: ${data.maintenance ? "ON" : "OFF"}`;
  chip.className = "chip" + (data.maintenance ? " on" : "");
  document.getElementById("cfgMaintenance").value = data.maintenance ? "1" : "0";
  document.getElementById("cfgVersion").value = data.latest_version || "";
  document.getElementById("cfgAnnounce").value = data.announcement || "";
}

async function saveConfig() {
  const msg = document.getElementById("cfgMsg");
  const pairs = [
    ["maintenance_mode", document.getElementById("cfgMaintenance").value],
    ["latest_version", document.getElementById("cfgVersion").value.trim()],
    ["announcement", document.getElementById("cfgAnnounce").value.trim()],
  ];
  for (const [key, value] of pairs) {
    await fetch(`${API}/api/v1/admin/config`, {
      method: "POST", headers: authHeaders(), body: JSON.stringify({ key, value })
    });
  }
  msg.className = "msg";
  msg.textContent = "Settings saved.";
  loadConfig();
}

async function loadLogs() {
  const res = await fetch(`${API}/api/v1/admin/logs?limit=30`, { headers: authHeaders() });
  if (!res.ok) return;
  const data = await res.json();
  const tbody = document.querySelector("#logsTable tbody");
  tbody.innerHTML = "";
  data.logs.forEach(l => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${l.id}</td><td>${l.user_id}</td>
      <td class="mono">${l.amount > 0 ? "+" : ""}${l.amount}</td>
      <td>${esc(l.operation)}</td><td class="mono">${esc(l.hwid || "-")}</td>
      <td class="mono">${esc(l.ip || "-")}</td>
      <td>${esc((l.timestamp || "").replace("T", " ").slice(0, 19))}</td>`;
    tbody.appendChild(tr);
  });
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Auto-resume session
window.addEventListener("load", () => {
  const saved = sessionStorage.getItem("admin_token");
  if (saved) { ADMIN_TOKEN = saved; showPanel(); }
});
