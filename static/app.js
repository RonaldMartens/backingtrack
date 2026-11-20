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
  $("btnDelete").addEventListener("click", deleteSession);
  $("btnStop").addEventListener("click", stopServer);
  $("btnChords").addEventListener("click", openChords);
  $("btnSoloGuide").addEventListener("click", openSoloGuide);
  $("btnCloseSolo").addEventListener("click", closeSoloGuide);
  $("btnPrintSolo").addEventListener("click", () => printWin("soloModal"));
  $("btnSolos").addEventListener("click", () => makeSolos(false));
  $("btnRemoveSolos").addEventListener("click", () => makeSolos(true));
  $("btnAddSolo").addEventListener("click", addSoloRow);
  $("mixWithSolo").addEventListener("click", () => playMix(true));
  $("mixNoSolo").addEventListener("click", () => playMix(false));
  $("btnCloseChords").addEventListener("click", closeChords);
  $("btnPrintChords").addEventListener("click", () => printWin("chordModal"));
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    const top = topWindow();
    if (top === "chordModal") closeChords(); else if (top === "soloModal") closeSoloGuide();
  });
  initFloatWin("chordModal", { width: 900, offset: 0 });
  initFloatWin("soloModal", { width: 1120, offset: 40 });
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
  const prevId = state.lastResult && state.lastResult.id;
  state.lastResult = r;
  if (r.id !== prevId) refreshOpenWindows();
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
  const solos = (r.solos || []).filter((x) => x.after != null);   // oude (over een deel gelegde) solo's negeren
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

async function deleteSession() {
  const r = state.lastResult;
  if (!r || state.busy) return;
  const name = r.title && r.title !== r.id ? `“${r.title}” (${r.id})` : `“${r.id}”`;
  if (!confirm(`Nummer ${name} verwijderen?\n\nDe hele map met alle audio-, MIDI- en tekstbestanden gaat naar de Prullenmand.`)) return;
  try {
    const res = await fetch(`${API_BASE}/api/sessions/${encodeURIComponent(r.id)}`, { method: "DELETE" });
    if (!res.ok) { let m = res.statusText; try { m = (await res.json()).detail || m; } catch (_) {} throw new Error(m); }
    const out = await res.json();
    const audio = $("mixAudio"); audio.pause(); audio.removeAttribute("src");
    state.lastResult = null; state.shownId = null;
    closeChords(); closeSoloGuide();
    $("result").classList.add("hidden");
    setStatus(out.trash ? `Verwijderd: ${r.id} staat in de Prullenmand (terug te zetten zolang je die niet leegt).`
                        : `Verwijderd: ${r.id} is definitief gewist.`);
    loadSessions();
  } catch (e) {
    setStatus("Verwijderen mislukt: " + e.message, "error");
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
    const btn = el("button", { class: "text-left px-3 py-2 rounded-lg bg-slate-800/40 hover:bg-slate-800 w-full min-w-0" });
    const top = el("div", { class: "flex justify-between gap-3 min-w-0" },
      el("span", { class: "truncate min-w-0", text: s.title && s.title !== s.id ? s.title : s.id }),
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
  showWin("chordModal");
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
  hideWin("chordModal");
}

// ------------------------------------------------------------------ zwevende vensters
// Akkoorden en soloschema zijn vrij verplaatsbare, vergrootbare vensters (op de telefoon schermvullend).
// De pagina eronder blijft gewoon bruikbaar; positie en grootte worden per venster onthouden.

let winZ = 50;
const isPhone = () => window.matchMedia("(max-width: 639px)").matches;
const winBody = (id) => $(id).querySelector(".win-body");

function loadWinPos(id) {
  try { return JSON.parse(localStorage.getItem("bt_win_" + id) || "null"); } catch (_) { return null; }
}
function saveWinPos(id) {
  if (isPhone()) return;
  const w = $(id);
  if (w.classList.contains("hidden")) return;
  try {
    localStorage.setItem("bt_win_" + id, JSON.stringify({
      left: w.offsetLeft, top: w.offsetTop, width: w.offsetWidth, height: w.offsetHeight }));
  } catch (_) {}
}

// Houd het venster (in ieder geval de titelbalk) binnen beeld.
function clampWin(w) {
  const vw = window.innerWidth, vh = window.innerHeight;
  const width = Math.min(w.offsetWidth, vw - 16), height = Math.min(w.offsetHeight, vh - 16);
  if (w.offsetWidth > width) w.style.width = width + "px";
  if (w.offsetHeight > height) w.style.height = height + "px";
  const left = Math.max(8 - width + 120, Math.min(w.offsetLeft, vw - 120));
  const top = Math.max(8, Math.min(w.offsetTop, vh - 60));
  w.style.left = left + "px"; w.style.top = top + "px";
}

function placeWin(id) {
  const w = $(id), o = w._floatOpts;
  const saved = loadWinPos(id);
  const vw = window.innerWidth, vh = window.innerHeight;
  if (saved) {
    Object.assign(w.style, { left: saved.left + "px", top: saved.top + "px",
                             width: saved.width + "px", height: saved.height + "px" });
  } else {
    const width = Math.min(o.width, vw - 40), height = Math.min(Math.round(vh * 0.82), vh - 40);
    Object.assign(w.style, {
      left: Math.max(20, Math.round((vw - width) / 2) + o.offset) + "px",
      top: Math.max(20, Math.round((vh - height) / 2) + o.offset / 2) + "px",
      width: width + "px", height: height + "px" });
  }
  clampWin(w);
}

function bringToFront(id) { $(id).style.zIndex = ++winZ; }

function topWindow() {
  let best = null, z = -1;
  for (const id of ["chordModal", "soloModal"]) {
    const w = $(id);
    if (!w.classList.contains("hidden") && Number(w.style.zIndex || 50) > z) { z = Number(w.style.zIndex || 50); best = id; }
  }
  return best;
}

function showWin(id) {
  const w = $(id);
  const wasHidden = w.classList.contains("hidden");
  w.classList.remove("hidden");
  if (wasHidden) { placeWin(id); winBody(id).scrollTop = 0; }
  bringToFront(id);
  if (isPhone()) document.body.style.overflow = "hidden";
}

function hideWin(id) {
  const w = $(id);
  if (w.classList.contains("hidden")) return;
  saveWinPos(id);
  w.classList.add("hidden");
  if (!topWindow()) document.body.style.overflow = "";
}

function printWin(id) {
  $(id).classList.add("print-me");
  document.body.classList.add("print-one");
  const done = () => {
    $(id).classList.remove("print-me");
    document.body.classList.remove("print-one");
    window.removeEventListener("afterprint", done);
  };
  window.addEventListener("afterprint", done);
  window.print();
  setTimeout(done, 1000);   // Safari stuurt niet altijd 'afterprint'
}

function initFloatWin(id, opts) {
  const w = $(id), head = w.querySelector(".win-head");
  w._floatOpts = opts;
  w.addEventListener("pointerdown", () => bringToFront(id));
  head.addEventListener("pointerdown", (e) => {
    if (isPhone() || e.button !== 0 || e.target.closest("button, a, select, input")) return;
    e.preventDefault();
    const sx = e.clientX, sy = e.clientY, ox = w.offsetLeft, oy = w.offsetTop;
    head.setPointerCapture(e.pointerId);
    w.classList.add("dragging");
    const move = (ev) => {
      w.style.left = ox + ev.clientX - sx + "px";
      w.style.top = oy + ev.clientY - sy + "px";
      clampWin(w);
    };
    const up = () => {
      head.removeEventListener("pointermove", move);
      head.removeEventListener("pointerup", up);
      head.removeEventListener("pointercancel", up);
      w.classList.remove("dragging");
      saveWinPos(id);
    };
    head.addEventListener("pointermove", move);
    head.addEventListener("pointerup", up);
    head.addEventListener("pointercancel", up);
  });
  // Dubbelklik op de titelbalk: terug naar de standaardplek en -grootte.
  head.addEventListener("dblclick", (e) => {
    if (isPhone() || e.target.closest("button")) return;
    try { localStorage.removeItem("bt_win_" + id); } catch (_) {}
    placeWin(id);
  });
  // Grootte via de hoek rechtsonder (CSS resize) onthouden.
  if (window.ResizeObserver) {
    let t = null;
    new ResizeObserver(() => { clearTimeout(t); t = setTimeout(() => saveWinPos(id), 300); }).observe(w);
  }
  window.addEventListener("resize", () => { if (!w.classList.contains("hidden") && !isPhone()) clampWin(w); });
}

// Ander nummer geopend terwijl een venster openstaat: venster bijwerken naar het nieuwe nummer.
function refreshOpenWindows() {
  if (!$("chordModal").classList.contains("hidden")) openChords();
  if (!$("soloModal").classList.contains("hidden")) openSoloGuide();
}

// ------------------------------------------------------------------ soloschema
const sg = { data: null, scale: null, box: null, chord: null, labels: "degrees" };
const SG_STRING_NAMES = ["E", "A", "D", "G", "B", "e"];

/* Fretboard: hoge e boven (zoals tab), frets 0..max. Toont de ladder; optioneel een positie en akkoordtonen. */
function fretboard(opts) {
  const { data, scale, box, chord, labels, from = 0, to = data.max_fret, mini = false } = opts;
  const FW = mini ? 26 : 46, SS = mini ? 15 : 22, L = mini ? 22 : 40, T = mini ? 10 : 18;
  const nF = to - from + 1;
  const W = L + nF * FW + 10, H = T + SS * 5 + (mini ? 16 : 30);
  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, class: "fretboard", width: "100%" });
  if (!mini) svg.style.minWidth = "760px";
  const xF = (f) => L + (f - from) * FW;                // rechterrand van fret f
  const xN = (f) => (f === 0 ? L - (mini ? 10 : 18) : xF(f) - FW / 2);
  const yS = (s) => T + (5 - s) * SS;                   // s=0 laag E onderaan
  // fretdraden
  for (let f = from; f <= to; f++) {
    const x = f === 0 ? L : xF(f);
    svg.append(svgEl("line", { x1: x, x2: x, y1: yS(5), y2: yS(0), stroke: "currentColor", "stroke-width": f === 0 ? 4 : 1, opacity: f === 0 ? 0.9 : 0.4 }));
  }
  if (from > 0) svg.append(svgEl("line", { x1: L, x2: L, y1: yS(5), y2: yS(0), stroke: "currentColor", "stroke-width": 1, opacity: 0.4 }));
  // inlays
  [3, 5, 7, 9, 12, 15, 17].filter((f) => f >= Math.max(1, from) && f <= to).forEach((f) => {
    const cx = xF(f) - FW / 2, cy = (yS(0) + yS(5)) / 2;
    if (f === 12) [-SS, SS].forEach((d) => svg.append(svgEl("circle", { cx, cy: cy + d, r: mini ? 2.5 : 4, fill: "currentColor", opacity: 0.18 })));
    else svg.append(svgEl("circle", { cx, cy, r: mini ? 2.5 : 4, fill: "currentColor", opacity: 0.18 }));
  });
  // snaren
  for (let s = 0; s < 6; s++) {
    svg.append(svgEl("line", { x1: from === 0 ? L : L, x2: xF(to), y1: yS(s), y2: yS(s), stroke: "currentColor", "stroke-width": 0.8 + (5 - s) * 0.25, opacity: 0.75 }));
    if (!mini) svg.append(svgEl("text", { x: 6, y: yS(s) + 4, "font-size": 11, fill: "currentColor", opacity: 0.6 }, SG_STRING_NAMES[s]));
  }
  // fretnummers
  for (let f = Math.max(from, 1); f <= to; f++)
    if (!mini || [3, 5, 7, 9, 12, 15].includes(f) || f === from)
      svg.append(svgEl("text", { x: xF(f) - FW / 2, y: H - (mini ? 3 : 8), "text-anchor": "middle", "font-size": mini ? 8 : 10, fill: "currentColor", opacity: 0.55 }, String(f)));
  // noten
  const pcs = new Set(scale.pcs);
  const blue = new Set(scale.id === "blues" ? [(data.root_pc + 6) % 12] : scale.id === "major_blues" ? [(data.root_pc + 3) % 12] : []);
  const inBox = box ? new Set(box.notes.map(([s, f]) => `${s}:${f}`)) : null;
  const chordPcs = chord ? new Map(chord.tones.map((t) => [t.pc, t.role])) : null;
  const R = mini ? 5.5 : 9;
  for (let s = 0; s < 6; s++) {
    for (let f = from; f <= to; f++) {
      const pc = (data.open[s] + f) % 12;
      const isScale = pcs.has(pc), isChord = chordPcs && chordPcs.has(pc);
      if (!isScale && !isChord) continue;
      const boxOk = !inBox || inBox.has(`${s}:${f}`) || (isChord && f >= box.from && f <= box.to);
      if (!boxOk && !mini) {
        svg.append(svgEl("circle", { cx: xN(f), cy: yS(s), r: R * 0.45, fill: "currentColor", opacity: 0.18 }));
        continue;
      }
      if (!boxOk) continue;
      const root = pc === data.root_pc;
      let fill = root ? "#f59e0b" : blue.has(pc) ? "#3b82f6" : "#475569";
      let opacity = 1;
      if (chordPcs && !isChord) opacity = 0.28;
      if (chordPcs && isChord && !isScale) fill = "#9d174d";
      const g = svgEl("g", { opacity });
      g.append(svgEl("circle", { cx: xN(f), cy: yS(s), r: R, fill }));
      if (isChord) g.append(svgEl("circle", { cx: xN(f), cy: yS(s), r: R + (mini ? 1.5 : 2.5), fill: "none", stroke: "#ec4899", "stroke-width": mini ? 1.5 : 2.5 }));
      if (!mini) {
        const lab = labels === "notes" || !scale.degrees[pc] ? data.pc_names[pc] : scale.degrees[pc];
        g.append(svgEl("text", { x: xN(f), y: yS(s) + 3.6, "text-anchor": "middle", "font-size": lab.length > 2 ? 8 : 10, "font-weight": 700, fill: root ? "#111" : "#fff" }, lab));
      }
      svg.append(g);
    }
  }
  return svg;
}

async function openSoloGuide() {
  const r = state.lastResult;
  if (!r) return;
  $("sgTitle").textContent = `${r.title || r.folder} · ${r.key} · ${r.bpm} BPM`;
  $("sgBody").innerHTML = '<p class="text-slate-400 text-sm">Soloschema berekenen…</p>';
  showWin("soloModal");
  try {
    sg.data = await api("/api/solo-guide", {
      key: r.key, genre: r.genre || "",
      sections: (r.sections || []).map((s) => ({ label: s.label, name: s.name, chords: s.chords || [] })),
    });
    sg.scale = sg.data.scales[0].id; sg.box = null; sg.chord = null;
    renderSoloGuide();
  } catch (e) {
    $("sgBody").innerHTML = "";
    $("sgBody").append(el("p", { class: "text-red-400 text-sm", text: "Kon het soloschema niet maken: " + e.message }));
  }
}

function closeSoloGuide() {
  hideWin("soloModal");
}

function sgButton(text, on, onClick, cls = "scale-chip") {
  const b = el("button", { class: `${cls} ${on ? "on" : ""}`, text });
  b.addEventListener("click", onClick);
  return b;
}

function renderSoloGuide() {
  const d = sg.data, body = $("sgBody");
  const scale = d.scales.find((x) => x.id === sg.scale) || d.scales[0];
  const box = sg.box != null ? scale.boxes.find((b) => b.number === sg.box) : null;
  body.innerHTML = "";

  // 1. toonladders
  const chips = el("div", { class: "flex flex-wrap gap-2 noprint" });
  d.scales.forEach((sc, i) => chips.append(sgButton(`${i === 0 ? "★ " : ""}${sc.name}`, sc.id === scale.id, () => {
    sg.scale = sc.id; sg.box = null; renderSoloGuide();
  })));
  body.append(el("h3", { class: "text-xs uppercase tracking-wider text-slate-500 mb-2", text: "Toonladders voor dit nummer" }), chips);
  body.append(el("div", { class: "mt-3 rounded-lg bg-slate-800/40 px-3 py-2 text-sm" },
    el("div", { class: "font-semibold text-amber-300", text: `${scale.name}: ${scale.note_names.join(" – ")}` }),
    el("div", { class: "text-slate-300 text-xs mt-0.5", text: scale.why })));

  // 2. hele hals
  const tools = el("div", { class: "flex flex-wrap items-center gap-2 mt-4 noprint" });
  tools.append(el("span", { class: "text-xs text-slate-500 mr-1", text: "Positie:" }));
  tools.append(sgButton("Hele hals", sg.box == null, () => { sg.box = null; renderSoloGuide(); }));
  scale.boxes.forEach((b) => tools.append(sgButton(`${b.number}${b.root_on_low_e ? " ★" : ""} (fret ${b.from}–${b.to})`, sg.box === b.number, () => { sg.box = b.number; renderSoloGuide(); })));
  tools.append(el("span", { class: "flex-1" }));
  tools.append(sgButton("Graden", sg.labels === "degrees", () => { sg.labels = "degrees"; renderSoloGuide(); }));
  tools.append(sgButton("Nootnamen", sg.labels === "notes", () => { sg.labels = "notes"; renderSoloGuide(); }));
  body.append(tools);
  const wrap = el("div", { class: "fb-wrap overflow-x-auto mt-2 rounded-lg bg-slate-900/50 p-2" });
  wrap.append(fretboard({ data: d, scale, box, chord: sg.chord, labels: sg.labels }));
  body.append(wrap);
  const legend = el("div", { class: "flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-400 mt-2" });
  const dot = (c, ring) => { const x = el("span", { class: "inline-block w-3 h-3 rounded-full align-middle mr-1" }); x.style.background = c; if (ring) x.style.boxShadow = "0 0 0 2px #ec4899"; return x; };
  legend.append(el("span", {}, dot("#f59e0b"), "grondtoon"), el("span", {}, dot("#475569"), "ladder-toon"));
  if (scale.id === "blues" || scale.id === "major_blues") legend.append(el("span", {}, dot("#3b82f6"), "blue note (doorgangsnoot)"));
  legend.append(el("span", {}, dot("#475569", true), "doelnoot van het gekozen akkoord"));
  if (sg.chord) legend.append(el("span", {}, dot("#9d174d", true), "doelnoot buiten de ladder (kleurtoon)"));
  if (sg.chord) {
    const clear = el("button", { class: "text-pink-300 hover:text-white", text: `✕ akkoord ${sg.chord.symbol} loslaten` });
    clear.addEventListener("click", () => { sg.chord = null; renderSoloGuide(); });
    legend.append(clear);
  }
  body.append(legend);

  // 3. posities (mini-diagrammen, klikbaar en voor afdrukken)
  body.append(el("h3", { class: "text-xs uppercase tracking-wider text-slate-500 mt-5 mb-2", text: `De ${scale.boxes.length} posities van ${scale.name}` }));
  const grid = el("div", { class: "grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3" });
  scale.boxes.forEach((b) => {
    const card = el("button", { class: `chordrow text-left rounded-lg p-2 border ${sg.box === b.number ? "border-amber-500 bg-amber-500/10" : "border-slate-800 bg-slate-900/40 hover:border-slate-600"}` });
    card.append(el("div", { class: "text-xs text-slate-300 mb-1", text: `Positie ${b.number}${b.root_on_low_e ? " ★" : ""} · fret ${b.from}–${b.to}` }));
    card.append(fretboard({ data: d, scale, box: b, chord: null, labels: sg.labels, from: Math.max(0, b.from - (b.from > 0 ? 1 : 0)), to: b.to + 1, mini: true }));
    card.addEventListener("click", () => { sg.box = b.number; renderSoloGuide(); winBody("soloModal").scrollTo({ top: 0, behavior: "smooth" }); });
    grid.append(card);
  });
  body.append(grid);
  body.append(el("p", { class: "text-xs text-slate-500 mt-2", text: "★ = positie met de grondtoon op de lage E-snaar (vaak de makkelijkste start). Schuif van positie naar positie om over de hele hals te soleren." }));

  // 4. per deel: wat past + doelnoten per akkoord
  body.append(el("h3", { class: "text-xs uppercase tracking-wider text-slate-500 mt-5 mb-2", text: "Per deel van het nummer · klik een akkoord voor de doelnoten" }));
  const names = Object.fromEntries(d.scales.map((x) => [x.id, x.name]));
  const list = el("div", { class: "grid gap-2" });
  d.sections.forEach((sec) => {
    const row = el("div", { class: "chordrow rounded-lg bg-slate-800/30 px-3 py-2" });
    const head = el("div", { class: "flex flex-wrap items-baseline gap-2" },
      el("span", { class: `sec-${sec.name} w-2 h-2 rounded-full flex-none` }),
      el("span", { class: "font-semibold text-slate-200 w-28 flex-none", text: sec.label }));
    const fit = el("span", { class: "text-xs flex-1 min-w-0" });
    if (sec.fits.length) {
      fit.append(el("span", { class: "text-slate-500", text: "Past: " }));
      sec.fits.forEach((id, i) => {
        const b = el("button", { class: "text-emerald-300 hover:text-white underline-offset-2 hover:underline", text: names[id] });
        b.addEventListener("click", () => { sg.scale = id; sg.box = null; renderSoloGuide(); });
        fit.append(b);
        if (i < sec.fits.length - 1) fit.append(document.createTextNode(" · "));
      });
    } else {
      fit.append(el("span", { class: "text-pink-300", text: "Geen ladder past over het hele deel: wissel per akkoord (zie hieronder) of mik op de doelnoten." }));
    }
    head.append(fit);
    row.append(head);
    const chordsRow = el("div", { class: "flex flex-wrap gap-2 mt-2" });
    sec.chords.forEach((c) => {
      const on = sg.chord && sg.chord.symbol === c.symbol;
      const b = el("button", { class: `text-left rounded-lg px-2.5 py-1.5 border text-xs ${on ? "border-pink-500 bg-pink-500/10" : "border-slate-700 hover:border-slate-500"}` });
      b.append(el("div", { class: "font-mono font-semibold text-amber-300 text-sm", text: c.symbol }));
      if (c.tones.length) b.append(el("div", { class: "text-slate-300", text: c.tones.map((t) => t.name).join(" · ") }));
      const extra = [];
      if (c.outside.length) extra.push(`kleurtoon: ${c.outside.join(", ")} (niet in de ★-ladder)`);
      if (c.fits && c.fits.length && !sec.fits.length) extra.push(`speel: ${names[c.fits[0]]}`);
      if (extra.length) b.append(el("div", { class: "text-slate-500", text: extra.join(" · ") }));
      b.addEventListener("click", () => {
        sg.chord = on ? null : c;
        if (!on && c.fits && c.fits.length && !c.fits.includes(sg.scale)) sg.scale = c.fits[0];
        renderSoloGuide();
        winBody("soloModal").scrollTo({ top: 0, behavior: "smooth" });
      });
      chordsRow.append(b);
    });
    row.append(chordsRow);
    list.append(row);
  });
  body.append(list);
  body.append(el("p", { class: "text-xs text-slate-500 mt-3", text:
    "Tip: speel vrij in de ★-toonladder en land op de sterke tellen (vooral bij een akkoordwissel) op een doelnoot van het akkoord dat op dat moment klinkt: grondtoon, terts of kwint. De terts maakt het verschil tussen ‘zomaar toonladder’ en ‘melodie’." }));
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
