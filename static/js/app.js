(() => {
  const $ = (id) => document.getElementById(id);
  let socket = null, seat = null, state = null;
  const show = (id) => ["login", "lobby", "game"].forEach((s) => ($(s).hidden = s !== id));
  const msg = (t) => ($("msg").textContent = t || "");

  async function api(path, body) {
    const r = await fetch(path, { method: body ? "POST" : "GET", credentials: "same-origin",
      headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || "Request failed");
    return d;
  }
  const send = (ev, data) => new Promise((res) => socket.emit(ev, data || {}, res));
  async function act(ev, data) {
    const r = await send(ev, data);
    if (!r || !r.ok) { msg(r ? r.error : "No response"); return null; }
    msg(""); return r;
  }

  function connect() {
    socket = io({ transports: ["websocket", "polling"] });
    socket.on("state", onState);
    socket.on("connect_error", () => msg("Connection failed"));
    socket.on("disconnect", () => { msg("Disconnected"); $("grid").replaceChildren(); show("lobby"); });
  }

  const mySymbol = () => Object.keys(state.players).find((s) => state.players[s].seat === seat);
  function onState(s) { state = s; show("game"); render(); }

  function render() {
    const me = mySymbol(), opp = me === "X" ? "O" : "X";
    const grid = $("grid");
    if (!grid.children.length) {
      for (let i = 0; i < 9; i++) {
        const b = document.createElement("button");
        b.addEventListener("click", () => act("move", { index: i }));
        grid.appendChild(b);
      }
    }
    [...grid.children].forEach((b, i) => {
      b.textContent = state.board[i];
      b.disabled = state.status !== "playing" || state.turn !== me || !!state.board[i];
      b.classList.toggle("win", !!state.line && state.line.includes(i));
    });
    const you = state.players[me], them = state.players[opp];
    const mine = state.scores[String(seat)] || 0;
    const theirs = them ? state.scores[String(them.seat)] || 0 : 0;
    $("scores").textContent = `${you.name} (${me}) ${mine} - ${theirs} ${them ? them.name : "…"} · draws ${state.draws}`;
    let t = "";
    if (state.status === "waiting") t = `Waiting for opponent. Room code: ${state.code}`;
    else if (state.status === "playing") t = state.turn === me ? "Your turn" : "Opponent's turn";
    else {
      t = !state.winner ? "Draw!" : state.winner === me ? "You win!" : "You lose";
      if (state.result === "forfeit") t += " (forfeit)";
      if (state.opponent_left) t += " — opponent left";
    }
    $("status").textContent = t;
    const rm = $("rematch");
    rm.hidden = !(state.status === "finished" && !state.opponent_left);
    const voted = state.rematch.includes(seat);
    rm.disabled = voted;
    rm.textContent = voted ? "Waiting for opponent…" : state.rematch.length ? "Accept rematch" : "Rematch";
  }

  function fillTable(id, rows) {
    const body = $(id).querySelector("tbody");
    body.replaceChildren();
    rows.forEach((cells) => {
      const tr = document.createElement("tr");
      cells.forEach((c) => { const td = document.createElement("td"); td.textContent = c; tr.appendChild(td); });
      body.appendChild(tr);
    });
  }
  async function tab(name) {
    try {
      $("lb").hidden = name !== "board"; $("hist").hidden = name !== "hist";
      if (name === "board") fillTable("lb", (await api("/api/leaderboard")).map((r, i) => [i + 1, r.name, r.wins, r.losses, r.draws, r.points]));
      else fillTable("hist", (await api("/api/history")).map((r) => [r.opponent, r.outcome + (r.result === "forfeit" ? " (forfeit)" : ""), r.played_at]));
    } catch (e) { msg(e.message); }
  }
  const setSeat = (r) => { if (r) seat = r.seat; };

  $("loginBtn").addEventListener("click", async () => {
    try { await api("/api/guest", { name: $("name").value }); msg(""); start(); } catch (e) { msg(e.message); }
  });
  $("quick").addEventListener("click", async () => setSeat(await act("quick_match")));
  $("create").addEventListener("click", async () => setSeat(await act("create_room")));
  $("join").addEventListener("click", async () => setSeat(await act("join", { code: $("code").value })));
  $("rematch").addEventListener("click", () => act("rematch"));
  $("leave").addEventListener("click", async () => { await act("leave_room"); $("grid").replaceChildren(); show("lobby"); });
  document.querySelectorAll("nav button").forEach((b) => b.addEventListener("click", () => tab(b.dataset.tab)));

  async function start() {
    try {
      const me = await api("/api/me");
      $("who").textContent = me.name;
      if (!socket) connect();
      show("lobby");
    } catch { show("login"); }
  }
  start();
})();
