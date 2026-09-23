/* Heizplan-Karte für Home Assistant – ohne Build-Schritt, reines Web Component. */

const DAYS = [["mon", "Mo"], ["tue", "Di"], ["wed", "Mi"], ["thu", "Do"], ["fri", "Fr"], ["sat", "Sa"], ["sun", "So"]];
const WEEKDAY_BY_JS = ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"];
const MODE_LABEL = { comfort: "Warm", eco: "Nacht" };
const DEFAULT_PRESETS = [18, 23, 25];

const pad = (n) => String(n).padStart(2, "0");
const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const toMin = (hhmm) => {
  const [h, m] = hhmm.split(":").map(Number);
  return h * 60 + m;
};
// "00:00" oder "24:00" als Ende bedeutet Mitternacht (Tagesende).
const endMin = (hhmm) => (hhmm === "00:00" || hhmm === "24:00" ? 1440 : toMin(hhmm));
const localIso = (d) =>
  `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
const todayKey = () => DAYS[(new Date().getDay() + 6) % 7][0];

function fmtTemp(t) {
  if (t === null || t === undefined || Number.isNaN(Number(t))) return "–";
  return `${Number(t).toLocaleString("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} °C`;
}

function fmtWhen(iso) {
  const d = new Date(iso);
  const diff = Math.round((startOfDay(d) - startOfDay(new Date())) / 86400000);
  const time = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  if (diff === 0) return time;
  if (diff === 1) return `morgen ${time}`;
  return `${WEEKDAY_BY_JS[d.getDay()]} ${pad(d.getDate())}.${pad(d.getMonth() + 1)}. ${time}`;
}

function barHtml(blocks, overlays = [], nowMin = null) {
  const seg = (s, e, cls) =>
    `<div class="seg ${cls}" style="left:${(s / 14.4).toFixed(3)}%;width:${((e - s) / 14.4).toFixed(3)}%"></div>`;
  return `<div class="bar">${blocks.map(([s, e]) => seg(s, e, "comfort")).join("")}${overlays
    .map(([s, e, mode]) => seg(s, e, `exc ${mode}`))
    .join("")}${nowMin !== null ? `<div class="now-marker" style="left:${(nowMin / 14.4).toFixed(3)}%"></div>` : ""}</div>`;
}

const TICKS = `<div class="ticks"><span>0</span><span>6</span><span>12</span><span>18</span><span>24</span></div>`;

const STYLE = `
  :host { --hp-warm: #e8743b; --hp-cold: #4a90c9; }
  .card { padding: 16px; display: flex; flex-direction: column; gap: 16px; }
  .title { font-size: 1.4em; font-weight: 500; }
  h3 { margin: 0; font-size: 1.05em; font-weight: 500; }
  .muted { color: var(--secondary-text-color); font-size: 0.9em; }
  .error { background: var(--error-color, #db4437); color: #fff; padding: 8px 12px; border-radius: 8px; }
  .rooms { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; }
  .room { border: 1px solid var(--divider-color); border-radius: 12px; padding: 12px; display: flex; flex-direction: column; gap: 6px; }
  .room.disabled .schedule { opacity: 0.5; }
  .row { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; }
  .name { font-size: 1.15em; font-weight: 500; }
  .target { font-size: 1.8em; font-weight: 500; }
  .target.comfort { color: var(--hp-warm); }
  .target.eco { color: var(--hp-cold); }
  .target.override { color: var(--primary-color); }
  .badge { font-size: 0.8em; padding: 2px 8px; border-radius: 10px; color: #fff; vertical-align: middle; }
  .badge.comfort { background: var(--hp-warm); }
  .badge.eco { background: var(--hp-cold); }
  .badge.override { background: var(--primary-color); }
  .presets { display: flex; gap: 6px; }
  .presets button { min-height: 40px; min-width: 52px; font-size: 1.05em; }
  .current { color: var(--secondary-text-color); }
  .info { font-size: 0.9em; color: var(--secondary-text-color); }
  .info.alert { color: var(--warning-color, #e0a000); }
  .bar { position: relative; height: 14px; border-radius: 7px; background: color-mix(in srgb, var(--hp-cold) 25%, transparent); overflow: hidden; margin-top: 4px; }
  .seg { position: absolute; top: 0; bottom: 0; }
  .seg.comfort { background: var(--hp-warm); }
  .seg.exc { background-image: repeating-linear-gradient(45deg, rgba(255,255,255,.45) 0 3px, transparent 3px 7px); }
  .seg.exc.comfort { background-color: var(--hp-warm); }
  .seg.exc.eco { background-color: var(--hp-cold); }
  .now-marker { position: absolute; top: -2px; bottom: -2px; width: 2px; background: var(--primary-text-color); }
  .ticks { display: flex; justify-content: space-between; font-size: 0.7em; color: var(--secondary-text-color); }
  .actions { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
  .actions.right { justify-content: flex-end; }
  button { font: inherit; min-height: 36px; padding: 4px 12px; border-radius: 18px; border: 1px solid var(--divider-color);
    background: var(--card-background-color); color: var(--primary-text-color); cursor: pointer; }
  button.primary { background: var(--primary-color); color: var(--text-primary-color, #fff); border-color: var(--primary-color); }
  button.icon { min-width: 36px; padding: 4px; border-radius: 50%; }
  button.on { background: var(--primary-color); color: var(--text-primary-color, #fff); border-color: var(--primary-color); }
  button.on.comfort { background: var(--hp-warm); border-color: var(--hp-warm); }
  button.on.eco { background: var(--hp-cold); border-color: var(--hp-cold); }
  .switch { display: flex; align-items: center; gap: 6px; font-size: 0.9em; cursor: pointer; }
  .switch input { width: 18px; height: 18px; }
  .section { display: flex; flex-direction: column; gap: 8px; }
  .section-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
  ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
  .exc-item { display: flex; align-items: center; gap: 10px; padding: 8px 10px; border: 1px solid var(--divider-color); border-radius: 10px; }
  .exc-item.active { border-color: var(--primary-color); }
  .exc-text { flex: 1; min-width: 0; }
  .dot { width: 10px; height: 10px; border-radius: 50%; flex: none; display: inline-block; }
  .dot.comfort { background: var(--hp-warm); }
  .dot.eco { background: var(--hp-cold); }
  .form { display: flex; flex-direction: column; gap: 10px; padding: 12px; border-radius: 12px; background: var(--secondary-background-color); }
  .field { display: flex; flex-direction: column; gap: 4px; }
  .field > label { font-size: 0.85em; color: var(--secondary-text-color); }
  .grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; }
  input[type=text], input[type=time], input[type=datetime-local] { font: inherit; padding: 8px; border-radius: 8px;
    border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); }
  .chips { display: flex; flex-wrap: wrap; gap: 8px; }
  .chip { display: flex; align-items: center; gap: 6px; padding: 6px 10px; border-radius: 16px; border: 1px solid var(--divider-color); background: var(--card-background-color); }
  .seg-btns { display: flex; gap: 6px; flex-wrap: wrap; }
  .temps { display: flex; flex-wrap: wrap; gap: 12px 24px; }
  .temp-ctl { display: flex; align-items: center; gap: 8px; }
  .temp-ctl .lbl { min-width: 48px; }
  .temp-ctl .val { min-width: 64px; text-align: center; font-weight: 500; }
  .overview { display: flex; flex-direction: column; gap: 4px; }
  .ov-row { display: grid; grid-template-columns: 28px 1fr; align-items: center; gap: 8px; cursor: pointer; padding: 2px 4px; border-radius: 6px; }
  .ov-row.sel { background: var(--secondary-background-color); font-weight: 500; }
  .ov-row .bar { margin: 0; }
  .ov-ticks { margin-left: 40px; }
  .day-chips { display: flex; gap: 4px; flex-wrap: wrap; }
  .day-chips button { min-width: 42px; padding: 4px 8px; }
  .blocks { display: flex; flex-direction: column; gap: 8px; }
  .block { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
`;

class HeizplanCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._data = null;
    this._error = null;
    this._ui = { editRoom: null, week: null, day: "mon", excForm: null };
    this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
    this.shadowRoot.addEventListener("change", (ev) => this._onChange(ev));
    this.shadowRoot.addEventListener("input", (ev) => this._onInput(ev));
    this.shadowRoot.addEventListener("focusout", () => {
      if (this._pending) setTimeout(() => this._render(true), 0);
    });
  }

  static getStubConfig() {
    return {};
  }

  setConfig(config) {
    this._config = { ...(config || {}) };
    this._render();
  }

  getCardSize() {
    return 8;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._unsub && this.isConnected) this._subscribe();
    const sig = this._currentTempSignature();
    if (sig !== this._sig) {
      this._sig = sig;
      this._render(true);
    }
  }

  connectedCallback() {
    if (this._hass && !this._unsub) this._subscribe();
  }

  disconnectedCallback() {
    if (this._unsub) {
      this._unsub.then((unsub) => unsub()).catch(() => {});
      this._unsub = null;
    }
  }

  _subscribe() {
    if (this._retryAt && Date.now() < this._retryAt) return;
    this._unsub = this._hass.connection.subscribeMessage(
      (data) => {
        this._data = data;
        this._render(true);
      },
      { type: "heizplan/subscribe" },
    );
    this._unsub.catch((err) => {
      this._unsub = null;
      this._retryAt = Date.now() + 30000;
      this._error = `Heizplan nicht erreichbar: ${err?.message || err}`;
      this._render();
    });
  }

  _rooms() {
    if (!this._data) return [];
    const wanted = this._config.rooms;
    return wanted ? this._data.rooms.filter((r) => wanted.includes(r.id)) : this._data.rooms;
  }

  _currentTempSignature() {
    if (!this._data || !this._hass) return "";
    return this._data.rooms.map((r) => this._hass.states[r.climate]?.attributes?.current_temperature).join("|");
  }

  async _call(type, payload = {}) {
    try {
      await this._hass.callWS({ type, ...payload });
      this._error = null;
      return true;
    } catch (err) {
      this._error = err?.message || String(err);
      this._render();
      return false;
    }
  }

  // ------------------------------------------------------------------ Rendern

  _render(soft = false) {
    const root = this.shadowRoot;
    const active = root.activeElement;
    // Nicht neu zeichnen, während jemand tippt – sonst springt der Fokus weg.
    if (soft && active && ["INPUT", "SELECT", "TEXTAREA"].includes(active.tagName) && active.type !== "checkbox") {
      this._pending = true;
      return;
    }
    this._pending = false;

    let body;
    if (!this._data) {
      body = this._error ? "" : `<div class="muted">Lade Heizplan…</div>`;
    } else if (this._ui.editRoom) {
      body = this._renderEditor();
    } else {
      body = `<div class="rooms">${this._rooms().map((r) => this._renderRoom(r)).join("")}</div>
        ${this._renderExceptions()}
        ${this._renderSettings()}`;
    }
    const title = this._config.title ?? "Heizung";
    root.innerHTML = `<style>${STYLE}</style>
      <ha-card><div class="card">
        ${title ? `<div class="title">${esc(title)}</div>` : ""}
        ${this._error ? `<div class="error">${esc(this._error)}</div>` : ""}
        ${body}
      </div></ha-card>`;
  }

  _renderRoom(r) {
    const current = this._hass?.states?.[r.climate]?.attributes?.current_temperature;
    const thermostatTarget = this._hass?.states?.[r.climate]?.attributes?.temperature;
    const manuallyAdjusted =
      r.enabled && thermostatTarget != null && Math.round(thermostatTarget * 2) !== Math.round(r.temperature * 2);
    const now = new Date();
    const nowMin = now.getHours() * 60 + now.getMinutes();
    const blocks = (r.week[todayKey()] || []).map((b) => [toMin(b.from), endMin(b.to)]);
    const dayStart = startOfDay(now);
    const dayEnd = new Date(dayStart.getTime() + 86400000);
    const overlays = this._data.exceptions
      .filter((e) => e.rooms.includes(r.id))
      .map((e) => {
        const s = new Date(e.start);
        const en = new Date(e.end);
        if (en <= dayStart || s >= dayEnd) return null;
        return [Math.max(0, (s - dayStart) / 60000), Math.min(1440, (en - dayStart) / 60000), e.mode];
      })
      .filter(Boolean);

    let info;
    if (!r.enabled)
      info =
        r.source === "override"
          ? `Manuell auf ${fmtTemp(r.temperature)} · Plan pausiert`
          : "Plan pausiert – Thermostat wird nicht gesteuert";
    else if (r.source === "override")
      info = `Manuell eingestellt${r.next_change ? ` · bis ${fmtWhen(r.next_change)}` : ""}`;
    else if (r.source === "exception")
      info = `Ausnahme${r.exception?.note ? `: ${esc(r.exception.note)}` : ""} · bis ${fmtWhen(r.exception.end)}`;
    else info = "Nach Wochenplan";
    const next =
      r.enabled && r.next_change
        ? `Ab ${fmtWhen(r.next_change)}: ${MODE_LABEL[r.next_mode]} (${fmtTemp(r.next_temperature)})`
        : "";
    const sensorHint =
      r.last_sensor_reset && Date.now() - new Date(r.last_sensor_reset) < 86400000
        ? `<div class="info alert">⚠ Thermostat war auf internen Sensor gesprungen – um ${fmtWhen(r.last_sensor_reset)} korrigiert</div>`
        : "";
    const badgeClass = r.source === "override" ? "override" : r.mode;
    const badgeLabel = r.source === "override" ? "Manuell" : MODE_LABEL[r.mode];
    const presets = this._config.presets ?? DEFAULT_PRESETS;

    return `<div class="room ${r.enabled ? "" : "disabled"}">
      <div class="row">
        <div class="name">${esc(r.name)}</div>
        <label class="switch"><input type="checkbox" data-action="enabled" data-room="${esc(r.id)}" ${r.enabled ? "checked" : ""}>Plan aktiv</label>
      </div>
      <div class="row">
        ${
          r.enabled || r.source !== "plan"
            ? `<div><span class="target ${badgeClass}">${fmtTemp(r.temperature)}</span> <span class="badge ${badgeClass}">${badgeLabel}</span></div>`
            : `<div class="muted">Thermostat in Handsteuerung</div>`
        }
        <div class="current">Raum ${fmtTemp(current)} · Thermostat ${fmtTemp(thermostatTarget)}</div>
      </div>
      <div class="info">${info}</div>
      ${next ? `<div class="info">${next}</div>` : ""}
      ${manuallyAdjusted ? `<div class="info alert">✋ Am Thermostat auf ${fmtTemp(thermostatTarget)} verstellt – gilt bis zum nächsten Wechsel</div>` : ""}
      ${sensorHint}
      <div class="schedule">${barHtml(blocks, overlays, nowMin)}${TICKS}</div>
      <div class="presets">${presets
        .map(
          (t) =>
            `<button class="${r.source === "override" && r.temperature === t ? "on" : ""}" data-action="set-override" data-room="${esc(r.id)}" data-temp="${t}">${t}°</button>`,
        )
        .join("")}</div>
      <div class="actions">
        ${
          r.source === "override" || r.source === "exception"
            ? `<button data-action="back-to-plan" data-room="${esc(r.id)}">${r.enabled ? "Zurück zum Plan" : "Manuelle Temperatur aufheben"}</button>`
            : ""
        }
        ${
          r.enabled
            ? `<button data-action="boost" data-room="${esc(r.id)}">2 Std. warm</button>
               <button data-action="eco-today" data-room="${esc(r.id)}">Heute kühl lassen</button>`
            : ""
        }
        <button data-action="edit-week" data-room="${esc(r.id)}">Plan bearbeiten</button>
      </div>
    </div>`;
  }

  _renderExceptions() {
    const names = Object.fromEntries(this._data.rooms.map((r) => [r.id, r.name]));
    const visible = new Set(this._rooms().map((r) => r.id));
    const now = new Date();
    const items = this._data.exceptions
      .filter((e) => e.rooms.some((id) => visible.has(id)))
      .map((e) => {
        const active = new Date(e.start) <= now;
        return `<li class="exc-item ${active ? "active" : ""}">
          <span class="dot ${e.mode}"></span>
          <div class="exc-text">
            <div><b>${MODE_LABEL[e.mode]}</b> · ${e.rooms.map((id) => esc(names[id] ?? id)).join(", ")}${e.note ? ` · ${esc(e.note)}` : ""}</div>
            <div class="muted">${active ? "läuft · " : ""}${fmtWhen(e.start)} – ${fmtWhen(e.end)}</div>
          </div>
          <button class="icon" data-action="del-exc" data-exc="${esc(e.id)}" title="Löschen">✕</button>
        </li>`;
      })
      .join("");
    const form = this._ui.excForm;
    return `<div class="section">
      <div class="section-head"><h3>Ausnahmen</h3>${form ? "" : `<button data-action="new-exc">+ Ausnahme</button>`}</div>
      ${form ? this._renderExcForm() : ""}
      ${items ? `<ul>${items}</ul>` : form ? "" : `<div class="muted">Keine Ausnahmen geplant.</div>`}
    </div>`;
  }

  _renderExcForm() {
    const f = this._ui.excForm;
    const s = this._data.settings;
    return `<div class="form">
      <div class="field"><label>Räume</label><div class="chips">
        ${this._rooms()
          .map(
            (r) =>
              `<label class="chip"><input type="checkbox" data-action="exc-room" data-room="${esc(r.id)}" ${f.rooms.includes(r.id) ? "checked" : ""}>${esc(r.name)}</label>`,
          )
          .join("")}
      </div></div>
      <div class="field"><label>Temperatur</label><div class="seg-btns">
        <button class="${f.mode === "comfort" ? "on comfort" : ""}" data-action="exc-mode" data-mode="comfort">Warm (${fmtTemp(s.comfort_temp)})</button>
        <button class="${f.mode === "eco" ? "on eco" : ""}" data-action="exc-mode" data-mode="eco">Nacht (${fmtTemp(s.eco_temp)})</button>
      </div></div>
      <div class="grid2">
        <div class="field"><label>Von</label><input type="datetime-local" data-field="start" value="${esc(f.start)}"></div>
        <div class="field"><label>Bis</label><input type="datetime-local" data-field="end" value="${esc(f.end)}"></div>
      </div>
      <div class="field"><label>Notiz (optional)</label><input type="text" data-field="note" value="${esc(f.note)}" placeholder="z. B. Homeoffice, Urlaub, Besuch"></div>
      <div class="actions right">
        <button data-action="cancel-exc">Abbrechen</button>
        <button class="primary" data-action="save-exc">Speichern</button>
      </div>
    </div>`;
  }

  _renderSettings() {
    const s = this._data.settings;
    const control = (key, label, mode) => `<div class="temp-ctl">
      <span class="dot ${mode}"></span><span class="lbl">${label}</span>
      <button class="icon" data-action="temp" data-key="${key}" data-step="-0.5" title="kälter">−</button>
      <span class="val">${fmtTemp(s[key])}</span>
      <button class="icon" data-action="temp" data-key="${key}" data-step="0.5" title="wärmer">+</button>
    </div>`;
    return `<div class="section">
      <div class="section-head"><h3>Temperaturen für alle Räume</h3></div>
      <div class="temps">${control("comfort_temp", "Warm", "comfort")}${control("eco_temp", "Nacht", "eco")}</div>
    </div>`;
  }

  _renderEditor() {
    const room = this._data.rooms.find((r) => r.id === this._ui.editRoom);
    if (!room) {
      this._ui.editRoom = null;
      return "";
    }
    const week = this._ui.week;
    const day = this._ui.day;
    const s = this._data.settings;
    const overview = DAYS.map(
      ([key, label]) => `<div class="ov-row ${key === day ? "sel" : ""}" data-action="day" data-day="${key}">
        <span>${label}</span>${barHtml(week[key].map((b) => [toMin(b.from), endMin(b.to)]))}
      </div>`,
    ).join("");
    const blocks = week[day]
      .map(
        (b, i) => `<div class="block">
          <input type="time" data-bfield="from" data-idx="${i}" value="${esc(b.from)}">
          <span>bis</span>
          <input type="time" data-bfield="to" data-idx="${i}" value="${esc(b.to === "24:00" ? "00:00" : b.to)}">
          <button class="icon" data-action="del-block" data-idx="${i}" title="Zeitraum löschen">✕</button>
        </div>`,
      )
      .join("");
    const dayLabel = DAYS.find(([k]) => k === day)[1];
    return `<div class="section">
      <div class="section-head"><h3>Wochenplan ${esc(room.name)}</h3></div>
      <div class="muted">Orange = Warm (${fmtTemp(s.comfort_temp)}), sonst Nacht (${fmtTemp(s.eco_temp)}). Tippe auf einen Tag, um ihn zu bearbeiten.</div>
      <div class="overview">${overview}<div class="ov-ticks">${TICKS}</div></div>
      <div class="day-chips">${DAYS.map(
        ([key, label]) => `<button class="${key === day ? "on" : ""}" data-action="day" data-day="${key}">${label}</button>`,
      ).join("")}</div>
      <div class="field"><label>Warm-Zeiträume am ${dayLabel}</label>
        <div class="blocks">${blocks || `<div class="muted">Keine – ganzer Tag Nacht-Temperatur.</div>`}</div>
      </div>
      <div class="actions">
        <button data-action="add-block">+ Zeitraum</button>
        <button data-action="copy" data-target="weekdays">${dayLabel} auf Mo–Fr kopieren</button>
        <button data-action="copy" data-target="all">${dayLabel} auf alle Tage kopieren</button>
      </div>
      <div class="actions right">
        <button data-action="cancel-edit">Abbrechen</button>
        <button class="primary" data-action="save-week">Speichern</button>
      </div>
    </div>`;
  }

  // ----------------------------------------------------------------- Aktionen

  async _addException(rooms, start, end, mode, note) {
    return this._call("heizplan/add_exception", { rooms, start: localIso(start), end: localIso(end), mode, note });
  }

  async _onClick(ev) {
    const el = ev.target.closest("[data-action]");
    if (!el || el.tagName === "INPUT" || el.tagName === "LABEL") return;
    const roomId = el.dataset.room;
    const ui = this._ui;

    switch (el.dataset.action) {
      case "boost": {
        const now = new Date();
        await this._addException([roomId], now, new Date(now.getTime() + 2 * 3600000), "comfort", "2 Std. warm");
        break;
      }
      case "eco-today": {
        const now = new Date();
        await this._addException([roomId], now, new Date(startOfDay(now).getTime() + 86400000), "eco", "Heute kühl");
        break;
      }
      case "back-to-plan": {
        const room = this._data.rooms.find((r) => r.id === roomId);
        if (room?.source === "override") {
          await this._call("heizplan/clear_override", { room_id: roomId });
        } else if (room?.exception) {
          await this._call("heizplan/delete_exception", { exception_id: room.exception.id, room_id: roomId });
        }
        break;
      }
      case "set-override": {
        await this._call("heizplan/set_override", { room_id: roomId, temperature: Number(el.dataset.temp) });
        break;
      }
      case "edit-week": {
        const room = this._data.rooms.find((r) => r.id === roomId);
        ui.editRoom = roomId;
        ui.week = JSON.parse(JSON.stringify(room.week));
        for (const [key] of DAYS) ui.week[key] = ui.week[key] || [];
        ui.day = todayKey();
        this._error = null;
        this._render();
        break;
      }
      case "day":
        ui.day = el.dataset.day;
        this._render();
        break;
      case "add-block": {
        const blocks = ui.week[ui.day];
        const last = blocks[blocks.length - 1];
        let from = 18 * 60;
        if (last && endMin(last.to) <= 22 * 60) from = endMin(last.to) + 60;
        else if (last) from = 12 * 60;
        const fmt = (m) => `${pad(Math.floor(m / 60))}:${pad(m % 60)}`;
        blocks.push({ from: fmt(from), to: fmt(Math.min(from + 120, 23 * 60 + 59)) });
        this._render();
        break;
      }
      case "del-block":
        ui.week[ui.day].splice(Number(el.dataset.idx), 1);
        this._render();
        break;
      case "copy": {
        const source = ui.week[ui.day];
        const targets = el.dataset.target === "weekdays" ? DAYS.slice(0, 5) : DAYS;
        for (const [key] of targets) {
          if (key !== ui.day) ui.week[key] = source.map((b) => ({ ...b }));
        }
        this._render();
        break;
      }
      case "cancel-edit":
        ui.editRoom = null;
        ui.week = null;
        this._error = null;
        this._render();
        break;
      case "save-week": {
        const week = {};
        for (const [key] of DAYS) {
          week[key] = ui.week[key].map((b) => ({ from: b.from, to: b.to === "00:00" ? "24:00" : b.to }));
        }
        if (await this._call("heizplan/set_week", { room_id: ui.editRoom, week })) {
          ui.editRoom = null;
          ui.week = null;
          this._render();
        }
        break;
      }
      case "new-exc": {
        const start = new Date();
        start.setSeconds(0, 0);
        ui.excForm = {
          rooms: this._rooms().map((r) => r.id),
          mode: "eco",
          start: localIso(start),
          end: localIso(new Date(start.getTime() + 24 * 3600000)),
          note: "",
        };
        this._render();
        break;
      }
      case "exc-mode":
        ui.excForm.mode = el.dataset.mode;
        this._render();
        break;
      case "cancel-exc":
        ui.excForm = null;
        this._error = null;
        this._render();
        break;
      case "save-exc": {
        const f = ui.excForm;
        if (!f.rooms.length) {
          this._error = "Bitte mindestens einen Raum wählen.";
          this._render();
          break;
        }
        if (await this._call("heizplan/add_exception", { rooms: f.rooms, start: f.start, end: f.end, mode: f.mode, note: f.note })) {
          ui.excForm = null;
          this._render();
        }
        break;
      }
      case "del-exc":
        if (confirm("Diese Ausnahme löschen?")) {
          await this._call("heizplan/delete_exception", { exception_id: el.dataset.exc });
        }
        break;
      case "temp": {
        const key = el.dataset.key;
        await this._call("heizplan/set_settings", { [key]: this._data.settings[key] + Number(el.dataset.step) });
        break;
      }
    }
  }

  _onChange(ev) {
    const el = ev.target;
    if (el.dataset.action === "enabled") {
      this._call("heizplan/set_enabled", { room_id: el.dataset.room, enabled: el.checked });
      return;
    }
    if (el.dataset.action === "exc-room" && this._ui.excForm) {
      const f = this._ui.excForm;
      f.rooms = el.checked ? [...new Set([...f.rooms, el.dataset.room])] : f.rooms.filter((id) => id !== el.dataset.room);
      return;
    }
    this._onInput(ev);
    if (el.dataset.bfield) this._render(); // Wochenübersicht aktualisieren
  }

  _onInput(ev) {
    const el = ev.target;
    if (el.dataset.bfield && this._ui.week) {
      const block = this._ui.week[this._ui.day][Number(el.dataset.idx)];
      if (block && el.value) block[el.dataset.bfield] = el.value;
    } else if (el.dataset.field && this._ui.excForm) {
      this._ui.excForm[el.dataset.field] = el.value;
    }
  }
}

if (!customElements.get("heizplan-card")) {
  customElements.define("heizplan-card", HeizplanCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "heizplan-card",
    name: "Heizplan",
    description: "Wochenpläne, Ausnahmen und Temperaturen für die Heizung",
  });

  // HA lädt zusätzliche Frontend-Module parallel zum Dashboard. Dabei kann
  // Lovelace bereits eine dauerhafte Fehlerkarte erzeugen, bevor dieses Element
  // registriert ist. Die Fehlerkarte kann tief in HAs Shadow DOM liegen; daher
  // alle offenen Shadow Roots durchsuchen und nur bei genau diesem Ladefehler
  // einmal neu laden. Beim zweiten Aufbau liegt das Modul bereits im Cache.
  setTimeout(() => {
    const hasLoadError = (root) => {
      for (const el of root.querySelectorAll("*")) {
        if (el.tagName === "HUI-ERROR-CARD") {
          const message = `${el.error || ""} ${el._error || ""} ${el.shadowRoot?.textContent || ""}`;
          if (/heizplan-card/i.test(message)) return true;
        }
        if (el.shadowRoot && hasLoadError(el.shadowRoot)) return true;
      }
      return false;
    };
    const reloadKey = "heizplan-card-load-retry-0.3.9";
    if (hasLoadError(document) && !sessionStorage.getItem(reloadKey)) {
      sessionStorage.setItem(reloadKey, "1");
      location.reload();
    }
  }, 2500);
}
