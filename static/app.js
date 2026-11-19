// BackingTrack Generator – webinterface (vanilla JS).
// API_BASE leeg = zelfde server. Een iOS-app gebruikt dezelfde endpoints.
const API_BASE = "";
const $ = (id) => document.getElementById(id);
const state = { options: null, profile: null, busy: false };

const SOURCE_LABEL = {
  library: "Lokale bibliotheek",
  claude: "Claude-analyse",
  heuristic: "Lokale schatting",
  mood: "Sfeerpreset",
};

function store(key, value) {
  try { value === null ? localStorage.removeItem(key) : localStorage.setItem(key, value); } catch (_) {}
}
function load(key) {
  try { return localStorage.getItem(key); } catch (_) { return null; }
}

async function api(path, body) {
  const res = await fetch(API_BASE + path, body === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const j = await res.json();
      msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch (_) {}
    throw new Error(msg);
  }
  return res.json();
}

function el(tag, attrs = {}, ...children) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k === "text") n.textContent = v;
    else n.setAttribute(k, v);
  }
  for (const c of children) n.append(c);
  return n;
}

function option(value, label) {
  return el("option", { value, text: label });
}

function setStatus(msg, kind = "info", spinning = false) {
  const s = $("status");
  s.innerHTML = "";
  s.className = "text-sm min-h-[1.25rem] " + (kind === "error" ? "text-red-400" : "text-slate-400");
  if (spinning) s.append(el("span", { class: "spin mr-2 align-middle" }));
  s.append(document.createTextNode(msg));
}

function setBusy(b) {
  state.busy = b;
  ["btnGenerate", "btnPreview", "btnAnalyze"].forEach((id) => ($(id).disabled = b));
}

function fmtSize(bytes) {
  if (bytes > 1e6) return (bytes / 1e6).toFixed(1) + " MB";
  return Math.max(1, Math.round(bytes / 1e3)) + " kB";
}
function fmtTime(sec) {
  const m = Math.floor(sec / 60), s = Math.round(sec % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

// ------------------------------------------------------------------ opties
// Referentieveld bij het opstarten altijd leeg (de browser vult anders het laatst getypte nummer weer in)
// Chrome ziet het veld anders als "gebruikersnaam" bij het API-sleutelveld en vult het zelf in.
// Daarom: alleen-lezen tot je erin klikt (Chrome vult geen alleen-lezen velden), en een paar keer leegmaken
// zolang je het veld nog niet hebt aangeraakt.
function clearReferenceOnStart() {
  const ref = $("reference");
  if (!ref.dataset.touched) ref.value = "";
}
(function guardReference() {
  const ref = $("reference");
  const unlock = () => { ref.dataset.touched = "1"; ref.removeAttribute("readonly"); };
  ref.addEventListener("focus", unlock);
  ref.addEventListener("pointerdown", unlock);
  [300, 1000, 2500].forEach((t) => setTimeout(clearReferenceOnStart, t));
  setTimeout(() => ref.removeAttribute("readonly"), 3000);   // daarna altijd gewoon bewerkbaar
})();
window.addEventListener("pageshow", (e) => { if (e.persisted) { clearReferenceOnStart(); if (state.profile) clearProfile(false); } });

async function init() {
  clearReferenceOnStart();
  const opts = await api("/api/options");
  state.options = opts;
  clearReferenceOnStart();   // ook na een late formulier-herstel door de browser

  opts.references.forEach((r) => $("refList").append(el("option", { value: r })));
  opts.moods.forEach((m) => $("mood").append(option(m.value, m.label)));
  $("mood").value = "sad";

  $("genre").append(option("auto", "Automatisch (uit referentie/sfeer)"));
  opts.genres.forEach((g) => $("genre").append(option(g.value, g.label)));

  $("key").append(option("auto", "Automatisch (uit referentie/sfeer)"));
  for (const group of ["Mineur", "Majeur"]) {
    const og = el("optgroup", { label: group });
    opts.keys.filter((k) => k.group === group).forEach((k) => og.append(option(k.value, k.label)));
    $("key").append(og);
  }

  $("progression").append(option("auto", "Automatisch (passend bij referentie/sfeer)"));
  const og = el("optgroup", { label: "Presets" });
  opts.progressions.forEach((p) => og.append(option("preset:" + p.value, p.label)));
  $("progression").append(og);
  $("progression").append(option("custom", "Eigen akkoordenschema…"));

  for (let m = 1; m <= 10; m++) $("durMin").append(option(String(m), `${m} min`));
  $("durMin").value = "4";

  opts.instruments.forEach((i) => {
    const id = "inst_" + i.id;
    $("instruments").append(
      el("label", { class: "chip" }, el("input", { type: "checkbox", id, checked: "" }), el("span", { text: i.label }))
    );
  });

  const savedKey = load("bt_api_key");
  if (savedKey) { $("apiKey").value = savedKey; $("rememberKey").checked = true; }

  applyMoodDefaults();
  bindEvents();
  updateHints();
  checkHealth();
  loadSessions();
  startHeartbeat();
}

function bindEvents() {
  $("bpm").addEventListener("input", updateHints);
  $("durMin").addEventListener("change", updateHints);
  $("durSec").addEventListener("change", updateHints);
  $("fade").addEventListener("change", () => $("fadeBarsWrap").classList.toggle("hidden", !$("fade").checked));
  $("progression").addEventListener("change", updateProgression);
  $("mood").addEventListener("change", () => { if (!state.profile) applyMoodDefaults(); });
  $("btnAnalyze").addEventListener("click", analyze);
  $("reference").addEventListener("keydown", (e) => { if (e.key === "Enter") analyze(); });
  $("reference").addEventListener("input", () => {
    if (state.profile && $("reference").value.trim() !== state.profileRef) clearProfile(false);
  });
  $("btnClearProfile").addEventListener("click", () => clearProfile(true));
  $("btnGenerate").addEventListener("click", generate);
  $("btnPreview").addEventListener("click", preview);
  $("btnRefresh").addEventListener("click", loadSessions);
  $("sessionSearch").addEventListener("input", renderSessions);
  $("btnRestore").addEventListener("click", () => restoreSettings(state.lastResult));
  $("btnReveal").addEventListener("click", revealSession);
  $("btnStop").addEventListener("click", stopServer);
  $("btnChords").addEventListener("click", openChords);
  $("btnSolos").addEventListener("click", () => makeSolos(false));
  $("btnRemoveSolos").addEventListener("click", () => makeSolos(true));
  $("btnAddSolo").addEventListener("click", addSoloRow);
  $("mixWithSolo").addEventListener("click", () => playMix(true));
  $("mixNoSolo").addEventListener("click", () => playMix(false));
  $("btnCloseChords").addEventListener("click", closeChords);
  $("btnPrintChords").addEventListener("click", () => window.print());
  $("chordModal").addEventListener("click", (e) => { if (e.target.id === "chordModal") closeChords(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeChords(); });
  $("rememberKey").addEventListener("change", () => {
    store("bt_api_key", $("rememberKey").checked ? $("apiKey").value.trim() || null : null);
  });
  $("apiKey").addEventListener("change", () => {
    if ($("rememberKey").checked) store("bt_api_key", $("apiKey").value.trim() || null);
  });
}

function applyMoodDefaults() {
  const m = state.options.moods.find((x) => x.value === $("mood").value);
  if (!m) return;
  $("bpm").value = m.bpm;
  updateHints();
}

function updateProgression() {
  const v = $("progression").value;
  $("customProg").classList.toggle("hidden", v !== "custom");
  let hint = "";
  if (v.startsWith("preset:")) {
    const p = state.options.progressions.find((x) => "preset:" + x.value === v);
    hint = p ? `Trappen: ${p.text}` : "";
  } else if (v === "custom") {
    hint = "Romeinse cijfers (i VI III VII) of akkoordnamen (Am F C G). ':2' = twee maten, ':0.5' = halve maat. '12-bar' werkt ook.";
  } else if (state.profile) {
    hint = `Couplet: ${state.profile.verse}  ·  Refrein: ${state.profile.chorus}`;
  }
  $("progHint").textContent = hint;
}

function durationSeconds() {
  return Math.min(600, Math.max(60, parseInt($("durMin").value) * 60 + parseInt($("durSec").value)));
}

function updateHints() {
  const bpm = parseInt($("bpm").value);
  $("bpmVal").textContent = bpm;
  const dur = durationSeconds();
  const bars = Math.max(16, Math.round((dur * bpm) / 240 / 4) * 4);
  const real = (bars * 4 * 60) / bpm;
  $("barsHint").textContent = `≈ ${bars} maten (4/4) · werkelijke lengte ${fmtTime(real)}`;
}

// ------------------------------------------------------------------ analyse
async function analyze() {
  const reference = $("reference").value.trim();
  if (!reference) { setStatus("Vul eerst een referentienummer in.", "error"); return; }
  setBusy(true);
  setStatus("Sfeer analyseren…", "info", true);
  try {
    const res = await api("/api/analyze-reference", {
      reference,
      api_key: $("apiKey").value.trim() || null,
      use_claude: $("useClaude").checked,
    });
    applyProfile(res.profile, reference);
    $("anSource").textContent = `${SOURCE_LABEL[res.source] || res.source} · ${res.message}`;
    setStatus("Instellingen aangepast aan de referentie – je kunt alles nog wijzigen.");
  } catch (e) {
    setStatus("Analyse mislukt: " + e.message, "error");
  } finally {
    setBusy(false);
  }
}

function applyProfile(p, ref) {
  state.profile = p;
  state.profileRef = ref;
  $("analysis").classList.remove("hidden");
  $("anTitle").textContent = p.title || ref;
  $("anDesc").textContent = p.description;
  const chips = $("anChips");
  chips.innerHTML = "";
  const genreLabel = (state.options.genres.find((g) => g.value === p.genre) || {}).label || p.genre;
  const moodLabel = (state.options.moods.find((m) => m.value === p.mood) || {}).label || p.mood;
  [genreLabel, moodLabel, `${p.bpm} BPM`, p.key, `Couplet: ${p.verse}`, `Refrein: ${p.chorus}`].forEach((t) =>
    chips.append(el("span", { class: "px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 text-xs", text: t }))
  );
  $("genre").value = p.genre;
  $("mood").value = p.mood;
  if ([...$("key").options].some((o) => o.value === p.key)) $("key").value = p.key;
  else $("key").value = "auto";
  $("bpm").value = Math.min(180, Math.max(50, p.bpm));
  $("progression").value = "auto";
  updateProgression();
  updateHints();
}

function clearProfile(resetInput) {
  state.profile = null;
  state.profileRef = null;
  $("analysis").classList.add("hidden");
  if (resetInput) $("reference").value = "";
  $("genre").value = "auto";
  $("key").value = "auto";
  applyMoodDefaults();
  updateProgression();
}

// ------------------------------------------------------------------ genereren
function buildRequest() {
  const prog = $("progression").value;
  const instruments = {};
  state.options.instruments.forEach((i) => (instruments[i.id] = $("inst_" + i.id).checked));
  const formats = [];
  if ($("fmtWav").checked) formats.push("wav");
  if ($("fmtAiff").checked) formats.push("aiff");
  const seed = $("seed").value.trim();
  return {
    song_name: $("songName").value.trim() || null,
    reference: $("reference").value.trim() || null,
    profile: state.profile,
    mood: $("mood").value,
    genre: $("genre").value,
    key: $("key").value,
    progression_mode: prog === "auto" ? "auto" : prog === "custom" ? "custom" : "preset",
    progression_preset: prog.startsWith("preset:") ? prog.slice(7) : null,
    progression_custom: prog === "custom" ? $("customProg").value.trim() : null,
    bpm: parseInt($("bpm").value),
    duration_seconds: durationSeconds(),
    intro: $("intro").checked,
    bridge: $("bridge").checked,
    fade_outro: $("fade").checked,
    fade_bars: parseInt($("fadeBars").value),
    instruments,
    formats,
    seed: seed ? parseInt(seed) : null,
    humanize: $("humanize").checked,
  };
}

async function preview() {
  setBusy(true);
  setStatus("Preview renderen (8 maten refrein)…", "info", true);
  try {
    const res = await api("/api/preview", buildRequest());
    if (res.url) {
      $("previewCard").classList.remove("hidden");
      $("previewAudio").src = API_BASE + res.url;
      $("previewAudio").play().catch(() => {});
      setStatus(`Preview klaar (${res.bars} maten, ${fmtTime(res.seconds)}).` + warnText(res.warnings));
    } else {
      setStatus("Geen audio: " + (res.warnings.join(" ") || "renderen niet beschikbaar"), "error");
    }
  } catch (e) {
    setStatus("Preview mislukt: " + e.message, "error");
  } finally {
    setBusy(false);
  }
}

function warnText(w) {
  return w && w.length ? " Let op: " + w.join(" ") : "";
}

async function generate() {
  setBusy(true);
  setStatus("Track genereren en renderen… (kan een halve minuut duren)", "info", true);
  try {
    const res = await api("/api/generate", buildRequest());
    let full = res;
    try { full = { ...res, ...(await api(`/api/sessions/${encodeURIComponent(res.id)}`)) }; } catch (_) {}
    showResult(full);   // volledige sessie: met opgeslagen instellingen (nodig voor solo's en ‘Instellingen overnemen’)
    setStatus(`Klaar: ${res.folder}`);
    loadSessions();
  } catch (e) {
    setStatus("Genereren mislukt: " + e.message, "error");
  } finally {
    setBusy(false);
  }
}

function showResult(r) {
  state.lastResult = r;
  $("result").classList.remove("hidden");
  $("resTitle").textContent = r.title || r.folder;
  const genreLabel = (state.options.genres.find((g) => g.value === r.genre) || {}).label || r.genre;
  $("resMeta").textContent =
    `${genreLabel} · ${r.key} · ${r.bpm} BPM · ${r.bars} maten · ${fmtTime(r.duration_seconds)}` +
    (r.seed != null ? ` · seed ${r.seed}` : r.source === "studio" ? " · gemaakt met de HTML-app" : "");
  $("resZip").href = API_BASE + r.zip_url;
  $("resPath").textContent = r.path;

  const audio = $("mixAudio");
  const playable = (r.files || []).filter((f) => f.kind === "audio" && !/aiff?$/i.test(f.name));
  const firstAudio = playable.find((f) => !/count-in/i.test(f.name)) || playable[0];
  if (state.shownId !== r.id) { audio.pause(); audio.removeAttribute("src"); }
  state.shownId = r.id;
  $("mixSwitch").classList.toggle("hidden", !(r.mix_solo_url && r.mix_url));
  if (r.mix_solo_url && r.mix_url) playMix(true, false);
  else if (r.mix_url) { audio.classList.remove("hidden"); audio.src = API_BASE + r.mix_url; $("playerLabel").textContent = "Volledige mix"; }
  else if (firstAudio) { audio.classList.remove("hidden"); audio.src = API_BASE + firstAudio.url; $("playerLabel").textContent = `Speelt: ${firstAudio.name} (geen mix; klik ▶ bij een bestand om een andere stem te horen)`; }
  else { audio.classList.add("hidden"); audio.removeAttribute("src"); $("playerLabel").textContent = ""; }
  $("btnRestore").classList.toggle("hidden", !r.request);
  $("btnReveal").classList.toggle("hidden", !r.id && !r.folder);

  const w = $("resWarnings");
  w.innerHTML = "";
  (r.warnings || []).forEach((t) =>
    w.append(el("div", { class: "text-xs rounded-lg bg-amber-500/10 text-amber-300 px-3 py-2", text: t }))
  );

  const tl = $("timeline");
  tl.innerHTML = "";
  r.sections.forEach((s) => {
    const block = el("div", {
      class: `sec-${s.name} flex items-center justify-center border-r border-black/30 overflow-hidden`,
      title: `${s.label} – ${s.bars} maten`,
    });
    block.style.flexGrow = s.bars;
    block.style.opacity = 0.55 + s.energy * 0.45;
    const solo = soloAt(r, s);
    block.textContent = (solo ? "🎸" : "") + (s.bars >= 6 ? s.label.replace("Couplet", "C").replace("Refrein", "R") : "");
    if (solo) { block.style.boxShadow = "inset 0 -4px 0 #ec4899"; block.title += ` · Solo ${solo.number}`; }
    tl.append(block);
  });

  const sec = $("sections");
  sec.innerHTML = "";
  r.sections.forEach((s) =>
    sec.append(
      el("div", { class: "flex gap-2 items-baseline" },
        el("span", { class: `sec-${s.name} w-2 h-2 rounded-full flex-none translate-y-[-1px]` }),
        el("span", { class: "w-24 flex-none text-slate-300", text: s.label }),
        el("span", { class: "hidden sm:inline w-20 flex-none text-slate-500 text-xs", text: `maat ${s.start_bar + 1}–${s.start_bar + s.bars}` }),
        el("span", { class: "min-w-0 flex-1 text-slate-400 font-mono text-xs leading-relaxed break-words", text: s.chords.join(" · ") }),
        soloAt(r, s) ? el("span", { class: "flex-none text-[10px] px-1.5 rounded bg-pink-500/20 text-pink-300", text: `🎸 solo ${soloAt(r, s).number}` }) : ""
      )
    )
  );

  const files = $("files");
  files.innerHTML = "";
  (r.files || []).forEach((f) => {
    const icon = f.kind === "midi" ? "🎹" : f.kind === "audio" ? "🔊" : "📄";
    const row = el("div", { class: "flex items-center gap-2" });
    if (f.kind === "audio" && !/aiff?$/i.test(f.name)) {
      const play = el("button", { class: "w-8 h-8 flex-none rounded-lg bg-slate-800 hover:bg-amber-500 hover:text-black", title: "Afspelen", text: "▶" });
      play.addEventListener("click", () => {
        audio.classList.remove("hidden"); audio.src = API_BASE + f.url; audio.play().catch(() => {});
        $("playerLabel").textContent = `Speelt: ${f.name}`;
      });
      row.append(play);
    } else row.append(el("span", { class: "w-8 flex-none" }));
    row.append(el("a", { href: API_BASE + f.url, download: f.name.split("/").pop(),
                class: "flex-1 min-w-0 flex justify-between gap-3 px-3 py-2 rounded-lg bg-slate-800/50 hover:bg-slate-800" },
        el("span", { class: "truncate", text: `${icon} ${f.name}` }),
        el("span", { class: "text-slate-500 text-xs flex-none", text: fmtSize(f.size) })));
    files.append(row);
  });
  renderSoloBox(r);
  if (window.innerWidth < 1024 && !state.keepScroll) $("result").scrollIntoView({ behavior: "smooth" });
  state.keepScroll = false;
}

// ------------------------------------------------------------------ gitaarsolo's
function soloAt(r, s) {
  return (r.solos || []).find((x) => x.start_bar === s.start_bar && x.bars === s.bars);
}

function playMix(withSolo, autoplay = true) {
  const r = state.lastResult, audio = $("mixAudio");
  if (!r) return;
  const url = withSolo ? r.mix_solo_url : r.mix_url;
  if (!url) return;
  const t = audio.src ? audio.currentTime : 0, wasPlaying = !audio.paused;
  audio.classList.remove("hidden");
  audio.src = API_BASE + url;
  audio.addEventListener("loadedmetadata", () => { try { audio.currentTime = t; } catch (_) {} }, { once: true });
  if (autoplay && wasPlaying) audio.play().catch(() => {});
  $("playerLabel").textContent = withSolo ? "Volledige mix met solo's" : "Volledige mix zonder solo (om zelf te spelen)";
  $("mixWithSolo").className = "px-2.5 py-1 " + (withSolo ? "bg-pink-500 text-black" : "bg-slate-800 hover:bg-slate-700");
  $("mixNoSolo").className = "px-2.5 py-1 " + (!withSolo ? "bg-amber-500 text-black" : "bg-slate-800 hover:bg-slate-700");
}

const SOLO_STYLES = [["auto", "Stijl: auto"], ["melodisch", "Melodisch"], ["bluesy", "Bluesy (bends)"], ["virtuoos", "Virtuoos (snel)"]];
const SOLO_TONES = [["auto", "Klank: auto"], ["overdrive", "Overdrive"], ["distortion", "Distortion"], ["clean", "Clean"], ["jazz", "Jazzgitaar"]];
const SOLO_CHORDS = [["verse", "Over couplet"], ["chorus", "Over refrein"], ["bridge", "Over bridge"]];
const SOLO_BARS = [2, 4, 8, 12, 16, 24, 32];

// Basisstructuur = het nummer zonder ingevoegde solo's (daar verwijzen de plaatsen naar)
function baseSections(r) {
  let i = 0;
  return (r.sections || []).filter((s) => !s.solo).map((s) => ({ ...s, base_index: s.base_index ?? i++ }));
}

function renderSoloBox(r) {
  const canSolo = !!r.request;
  $("soloForm").classList.toggle("hidden", !canSolo);
  $("soloUnavailable").classList.toggle("hidden", canSolo);
  $("soloStatus").textContent = "";
  const solos = r.solos || [];
  $("soloInfo").textContent = solos.length ? `${solos.length} solo${solos.length > 1 ? "'s" : ""} in het nummer` : "";
  $("btnRemoveSolos").classList.toggle("hidden", !solos.length);
  $("btnSolos").textContent = solos.length ? "🎸 Solo's opnieuw maken" : "🎸 Solo's maken";
  const req = (r.request && r.request.solos) || [];
  state.soloRows = solos.map((x, k) => ({
    after: x.after, bars: x.bars, chords: x.chords || "verse",
    style: (req[k] && req[k].style) || x.style || "auto", tone: (req[k] && req[k].tone) || x.tone || "auto",
  }));
  renderSoloRows();
}

function defaultSoloRow() {
  const base = baseSections(state.lastResult);
  const preOutro = base.length >= 2 ? base[base.length - 2].base_index : 0;
  const used = new Set(state.soloRows.map((x) => x.after));
  // eerste suggestie: vóór de outro; daarna na een refrein dat nog vrij is
  const chorus = base.filter((s) => s.name === "chorus" && !used.has(s.base_index) && s.base_index < preOutro);
  const after = !used.has(preOutro) ? preOutro : (chorus.length ? chorus[chorus.length - 1].base_index : preOutro);
  const twelve = base.some((s) => s.bars === 12);
  return { after, bars: twelve ? 12 : 8, chords: "verse", style: "auto", tone: "auto" };
}

function addSoloRow() {
  if (state.soloRows.length >= 8) return;
  state.soloRows.push(defaultSoloRow());
  renderSoloRows();
}

function sel(options, value, onChange, cls = "") {
  const s = el("select", { class: "inp " + cls });
  options.forEach(([v, t]) => s.append(option(String(v), t)));
  s.value = String(value);
  s.addEventListener("change", () => onChange(s.value));
  return s;
}

function renderSoloRows() {
  const box = $("soloRows"), r = state.lastResult;
  box.innerHTML = "";
  if (!r || !r.request) return;
  const base = baseSections(r);
  const places = base.slice(0, -1).map((s, k, arr) =>
    [s.base_index, k === arr.length - 1 ? `Vóór de outro (na ${s.label})` : `Na ${s.label}`]);
  if (!state.soloRows.length) {
    box.append(el("p", { class: "text-xs text-slate-500", text: "Nog geen solo's. Klik op ‘＋ Solo toevoegen’." }));
    return;
  }
  // nummering volgt de volgorde in het nummer
  const order = state.soloRows.map((x, k) => [x.after, k]).sort((a, b) => a[0] - b[0] || a[1] - b[1]).map((x) => x[1]);
  order.forEach((k, n) => {
    const row = state.soloRows[k];
    const del = el("button", { class: "w-7 h-7 rounded-lg bg-slate-800 hover:bg-red-500/80 text-slate-300 flex-none", title: "Deze solo weghalen", text: "✕" });
    del.addEventListener("click", () => { state.soloRows.splice(k, 1); renderSoloRows(); });
    box.append(el("div", { class: "solo-row rounded-lg bg-slate-900/60 border border-slate-800 p-2.5" },
      el("div", { class: "flex items-center justify-between gap-2 mb-2" },
        el("span", { class: "text-sm font-semibold text-pink-300", text: `🎸 Gitaarsolo ${n + 1}` }), del),
      el("div", { class: "grid grid-cols-2 sm:grid-cols-3 gap-2" },
        sel(places, row.after, (v) => { row.after = Number(v); renderSoloRows(); }, "col-span-2 sm:col-span-2"),
        sel(SOLO_BARS.map((b) => [b, `${b} maten`]), row.bars, (v) => (row.bars = Number(v))),
        sel(SOLO_STYLES, row.style, (v) => (row.style = v)),
        sel(SOLO_TONES, row.tone, (v) => (row.tone = v)),
        sel(SOLO_CHORDS, row.chords, (v) => (row.chords = v)))));
  });
}

async function makeSolos(removeAll) {
  const r = state.lastResult;
  if (!r || state.busy) return;
  if (removeAll && !confirm("Alle solo's uit dit nummer halen? Het nummer krijgt weer de oorspronkelijke lengte.")) return;
  const solos = removeAll ? [] : state.soloRows;
  if (!removeAll && !solos.length) { $("soloStatus").textContent = "Voeg eerst een solo toe met ‘＋ Solo toevoegen’."; return; }
  setBusy(true);
  ["btnSolos", "btnAddSolo", "btnRemoveSolos"].forEach((id) => ($(id).disabled = true));
  $("soloStatus").innerHTML = "";
  $("soloStatus").append(el("span", { class: "spin mr-2 align-middle" }),
    document.createTextNode(removeAll ? "Nummer zonder solo's opnieuw opbouwen…" : "Nummer met solo's opnieuw opbouwen en renderen…"));
  try {
    const res = await api(`/api/sessions/${encodeURIComponent(r.id)}/solos`, { solos });
    state.keepScroll = true;
    showResult(res);
    loadSessions();
    $("soloStatus").textContent = removeAll ? "Solo's weggehaald."
      : res.mix_solo_url ? `Klaar! Het nummer duurt nu ${fmtTime(res.duration_seconds)}. Klik nog een keer voor nieuwe varianten.`
      : "Solo-MIDI gemaakt (geen audio: FluidSynth/SoundFont niet gevonden).";
  } catch (e) {
    $("soloStatus").textContent = "Solo's maken mislukt: " + e.message;
  } finally {
    setBusy(false);
    ["btnSolos", "btnAddSolo", "btnRemoveSolos"].forEach((id) => ($(id).disabled = false));
  }
}

async function openSession(id) {
  try {
    const data = await api(`/api/sessions/${encodeURIComponent(id)}`);
    showResult(data);
  } catch (e) {
    setStatus("Kon sessie niet openen: " + e.message, "error");
  }
}

function renderSessions() {
  const box = $("sessions"), q = $("sessionSearch").value.trim().toLowerCase();
  const list = (state.sessions || []).filter((s) =>
    !q || [s.id, s.title, s.key, s.genre, s.bpm && `${s.bpm}`].some((x) => x && String(x).toLowerCase().includes(q)));
  box.innerHTML = "";
  $("sessionCount").textContent = state.sessions ? `(${state.sessions.length})` : "";
  if (!list.length) {
    box.append(el("p", { class: "text-slate-500 text-sm", text: state.sessions && state.sessions.length ? "Geen nummers gevonden." : "Nog geen nummers." }));
    return;
  }
  list.forEach((s) => {
    const btn = el("button", { class: "text-left px-3 py-2 rounded-lg bg-slate-800/40 hover:bg-slate-800 w-full" });
    const top = el("div", { class: "flex justify-between gap-3" },
      el("span", { class: "truncate", text: s.title && s.title !== s.id ? s.title : s.id }),
      el("span", { class: "text-slate-500 text-xs flex-none", text: (s.created || "").replace("T", " ").slice(0, 16) }));
    const meta = [s.key, s.bpm ? `${s.bpm} BPM` : "", s.duration_seconds ? fmtTime(s.duration_seconds) : "",
                  s.source === "studio" ? "HTML-app" : ""].filter(Boolean).join(" · ");
    btn.append(top, el("div", { class: "text-xs text-slate-500 truncate", text: meta + (s.title && s.title !== s.id ? `  ·  ${s.id}` : "") }));
    btn.addEventListener("click", () => openSession(s.id));
    box.append(btn);
  });
}

async function loadSessions() {
  const box = $("sessions");
  try {
    state.sessions = await api("/api/sessions");
    renderSessions();
  } catch (e) {
    box.textContent = "Kon sessies niet laden.";
  }
}

async function checkHealth() {
  const b = $("healthBadge");
  try {
    const h = await api("/api/health");
    const audio = h.fluidsynth && h.soundfont;
    b.textContent = audio ? "Audio ✓" : "Alleen MIDI";
    b.className = "text-xs px-2 py-1 rounded-full " + (audio ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-300");
    b.title = audio ? `FluidSynth: ${h.fluidsynth}\nSoundFont: ${h.soundfont}` :
      "FluidSynth of SoundFont ontbreekt – zie INSTALLATIE.md";
  } catch (_) {
    b.textContent = "Server offline";
    b.className = "text-xs px-2 py-1 rounded-full bg-red-500/15 text-red-300";
  }
}

// ------------------------------------------------------------------ nummer opnieuw gebruiken
function restoreSettings(r) {
  const q = r && r.request;
  if (!q) return;
  if (r.profile && q.reference) { $("reference").dataset.touched = "1"; $("reference").removeAttribute("readonly"); $("reference").value = q.reference; applyProfile(r.profile, q.reference); }
  else clearProfile(true);
  $("mood").value = q.mood || $("mood").value;
  $("genre").value = q.genre || "auto";
  $("key").value = [...$("key").options].some((o) => o.value === q.key) ? q.key : "auto";
  const prog = q.progression_mode === "preset" ? "preset:" + q.progression_preset : q.progression_mode === "custom" ? "custom" : "auto";
  $("progression").value = prog;
  $("customProg").value = q.progression_custom || "";
  updateProgression();
  $("bpm").value = q.bpm;
  const secs = q.duration_seconds || 240;
  $("durMin").value = String(Math.min(10, Math.max(1, Math.floor(secs / 60))));
  $("durSec").value = String([0, 15, 30, 45].reduce((a, b) => (Math.abs(b - secs % 60) < Math.abs(a - secs % 60) ? b : a), 0));
  $("songName").value = q.song_name || "";
  $("intro").checked = q.intro !== false;
  $("bridge").checked = !!q.bridge;
  $("fade").checked = !!q.fade_outro;
  $("fadeBarsWrap").classList.toggle("hidden", !q.fade_outro);
  $("fadeBars").value = String(q.fade_bars || 8);
  for (const [k, v] of Object.entries(q.instruments || {})) if ($("inst_" + k)) $("inst_" + k).checked = !!v;
  $("fmtWav").checked = (q.formats || []).includes("wav");
  $("fmtAiff").checked = (q.formats || []).includes("aiff");
  $("seed").value = r.seed ?? "";
  $("humanize").checked = q.humanize !== false;
  updateHints();
  setStatus("Instellingen van dit nummer staan klaar. Met dezelfde seed krijg je hetzelfde nummer, wis de seed voor een variatie.");
  if (window.innerWidth < 1024) window.scrollTo({ top: 0, behavior: "smooth" });
}

async function revealSession() {
  const r = state.lastResult;
  if (!r) return;
  try { await api(`/api/sessions/${encodeURIComponent(r.id || r.folder)}/reveal`, {}); }
  catch (e) { setStatus("Finder openen mislukt: " + e.message, "error"); }
}

// ------------------------------------------------------------------ gitaarakkoorden
const SVGNS = "http://www.w3.org/2000/svg";
function svgEl(tag, attrs, text) {
  const n = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (text !== undefined) n.textContent = text;
  return n;
}
/* Akkoorddiagram: 6 snaren (laag E links), 5 frets, vingernummers, barré, x/o, fretnummer */
function chordDiagram(v) {
  const W = 120, H = 158, L = 24, T = 30, SW = 16, FH = 22, FRETS = 5;
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, class: "chord-dia" });
  const x = (s) => L + s * SW, y = (f) => T + f * FH;
  // nut of fretnummer
  if (v.start_fret === 1) svg.append(svgEl("rect", { x: L - 1, y: T - 4, width: SW * 5 + 2, height: 4, fill: "currentColor" }));
  else svg.append(svgEl("text", { x: L - 8, y: T + FH / 2 + 4, "text-anchor": "end", "font-size": 10, fill: "currentColor" }, `${v.start_fret}fr`));
  for (let f = 0; f <= FRETS; f++)
    svg.append(svgEl("line", { x1: L, x2: L + SW * 5, y1: y(f), y2: y(f), stroke: "currentColor", "stroke-width": 1, opacity: 0.55 }));
  for (let s = 0; s < 6; s++)
    svg.append(svgEl("line", { x1: x(s), x2: x(s), y1: T, y2: y(FRETS), stroke: "currentColor", "stroke-width": 1 + (5 - s) * 0.18, opacity: 0.8 }));
  // x / o boven de hals
  v.frets.forEach((f, s) => {
    if (f < 0) svg.append(svgEl("text", { x: x(s), y: T - 9, "text-anchor": "middle", "font-size": 11, fill: "currentColor" }, "×"));
    else if (f === 0) svg.append(svgEl("circle", { cx: x(s), cy: T - 13, r: 4, fill: "none", stroke: "currentColor", "stroke-width": 1.4 }));
  });
  // barré
  if (v.barre) {
    const fy = y(v.barre.fret - v.start_fret + 0.5);
    svg.append(svgEl("rect", { x: x(v.barre.from) - 7, y: fy - 7, width: x(v.barre.to) - x(v.barre.from) + 14, height: 14, rx: 7, fill: "#f59e0b" }));
    svg.append(svgEl("text", { x: (x(v.barre.from) + x(v.barre.to)) / 2, y: fy + 4, "text-anchor": "middle", "font-size": 10, "font-weight": 700, fill: "#111" }, "1"));
  }
  // vingers
  v.frets.forEach((f, s) => {
    if (f <= 0) return;
    if (v.barre && f === v.barre.fret && v.fingers[s] === 1) return;
    const cy = y(f - v.start_fret + 0.5);
    svg.append(svgEl("circle", { cx: x(s), cy, r: 7, fill: "#f59e0b" }));
    if (v.fingers[s]) svg.append(svgEl("text", { x: x(s), y: cy + 3.5, "text-anchor": "middle", "font-size": 10, "font-weight": 700, fill: "#111" }, String(v.fingers[s])));
  });
  // nootnamen onder de snaren
  v.notes.forEach((n, s) => {
    if (n) svg.append(svgEl("text", { x: x(s), y: H - 6, "text-anchor": "middle", "font-size": 8.5, fill: "currentColor", opacity: 0.75 }, n));
  });
  return svg;
}
function trackChords(r) {
  const out = [];
  for (const s of r.sections || []) for (const c of s.chords || []) if (!out.includes(c)) out.push(c);
  return out;
}
async function openChords() {
  const r = state.lastResult;
  if (!r) return;
  const chords = trackChords(r);
  $("chordTitle").textContent = `${r.title || r.folder} · ${r.key} · ${r.bpm} BPM`;
  const secs = $("chordSections");
  secs.innerHTML = "";
  r.sections.forEach((s) =>
    secs.append(el("div", { class: "flex gap-3" },
      el("span", { class: "w-24 flex-none text-slate-400", text: s.label }),
      el("span", { class: "min-w-0 flex-1 font-mono text-slate-200 leading-relaxed break-words", text: s.chords.join("  ·  ") })))
  );
  const grid = $("chordGrid");
  grid.innerHTML = '<p class="text-slate-400 text-sm">Grepen berekenen…</p>';
  $("chordModal").classList.remove("hidden");
  document.body.style.overflow = "hidden";
  try {
    const res = await api("/api/guitar-chords", { chords, key: r.key });
    grid.innerHTML = "";
    for (const c of res.chords) {
      const row = el("div", { class: "chordrow border-t border-slate-800 pt-4" },
        el("div", { class: "text-lg font-semibold text-amber-300 mb-2", text: c.symbol }));
      const dias = el("div", { class: "grid grid-cols-2 sm:grid-cols-4 gap-3" });
      if (!c.voicings.length) dias.append(el("p", { class: "text-sm text-slate-500", text: c.error || "Geen speelbare greep gevonden." }));
      c.voicings.forEach((v) => {
        const box = el("div", { class: "flex flex-col items-center" });
        box.append(chordDiagram(v));
        box.append(el("div", { class: "text-xs text-slate-400 mt-1", text: `${v.label} · ${v.tab}` }));
        dias.append(box);
      });
      row.append(dias);
      grid.append(row);
    }
  } catch (e) {
    grid.innerHTML = "";
    grid.append(el("p", { class: "text-red-400 text-sm", text: "Kon de akkoorden niet berekenen: " + e.message }));
  }
}
function closeChords() {
  $("chordModal").classList.add("hidden");
  document.body.style.overflow = "";
}

// ------------------------------------------------------------------ levensduur
// De pagina meldt zich elke 15 s bij de server. Sluit je het laatste tabblad, dan stopt de
// server na ~10 s vanzelf (nooit tijdens het genereren).
const CLIENT_ID = Math.random().toString(36).slice(2) + Date.now().toString(36);
let heartbeatTimer = null;
async function heartbeat() {
  try {
    await fetch(`${API_BASE}/api/heartbeat?client=${CLIENT_ID}`, { method: "POST", keepalive: true });
  } catch (_) {
    if (document.visibilityState === "visible") showStopped(false);
  }
}
function startHeartbeat() {
  heartbeat();
  heartbeatTimer = setInterval(heartbeat, 15000);
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") heartbeat(); });
  window.addEventListener("pagehide", () => {
    try { navigator.sendBeacon(`${API_BASE}/api/bye?client=${CLIENT_ID}`); } catch (_) {}
  });
}
function showStopped(byUser) {
  if (heartbeatTimer) clearInterval(heartbeatTimer);
  document.body.innerHTML =
    '<div class="min-h-screen grid place-items-center p-6 text-center">' +
    '<div><div class="text-5xl mb-4">⏻</div><h1 class="text-xl font-semibold mb-2">BackingTrack is gestopt</h1>' +
    `<p class="text-slate-400">${byUser ? "Je kunt dit tabblad sluiten." : "De server draait niet meer."} ` +
    "Opnieuw starten: dubbelklik op het BackingTrack-icoon op je bureaublad.</p></div></div>";
}

// ------------------------------------------------------------------ server stoppen
async function stopServer() {
  if (state.busy) { setStatus("Wacht tot het genereren klaar is.", "error"); return; }
  if (!confirm("BackingTrack stoppen? Je gegenereerde tracks blijven gewoon bewaard.")) return;
  try {
    await api("/api/shutdown", {});
  } catch (e) {
    setStatus("Stoppen mislukt: " + e.message, "error");
    return;
  }
  showStopped(true);
}

init().catch((e) => setStatus("Kan de server niet bereiken: " + e.message, "error"));
