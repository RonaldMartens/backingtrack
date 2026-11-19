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
async function init() {
  const opts = await api("/api/options");
  state.options = opts;

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
    showResult(res);
    setStatus(`Klaar: ${res.folder}`);
    loadSessions();
  } catch (e) {
    setStatus("Genereren mislukt: " + e.message, "error");
  } finally {
    setBusy(false);
  }
}

function showResult(r) {
  $("result").classList.remove("hidden");
  $("resTitle").textContent = r.title || r.folder;
  const genreLabel = (state.options.genres.find((g) => g.value === r.genre) || {}).label || r.genre;
  $("resMeta").textContent =
    `${genreLabel} · ${r.key} · ${r.bpm} BPM · ${r.bars} maten · ${fmtTime(r.duration_seconds)} · seed ${r.seed}`;
  $("resZip").href = API_BASE + r.zip_url;
  $("resPath").textContent = r.path;

  const audio = $("mixAudio");
  if (r.mix_url) { audio.classList.remove("hidden"); audio.src = API_BASE + r.mix_url; }
  else { audio.classList.add("hidden"); audio.removeAttribute("src"); }

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
    block.textContent = s.bars >= 6 ? s.label.replace("Couplet", "C").replace("Refrein", "R") : "";
    tl.append(block);
  });

  const sec = $("sections");
  sec.innerHTML = "";
  r.sections.forEach((s) =>
    sec.append(
      el("div", { class: "flex gap-2 items-baseline" },
        el("span", { class: `sec-${s.name} w-2 h-2 rounded-full flex-none translate-y-[-1px]` }),
        el("span", { class: "w-24 flex-none text-slate-300", text: s.label }),
        el("span", { class: "w-20 flex-none text-slate-500 text-xs", text: `maat ${s.start_bar + 1}–${s.start_bar + s.bars}` }),
        el("span", { class: "text-slate-400 truncate font-mono text-xs", text: s.chords.join(" · ") })
      )
    )
  );

  const files = $("files");
  files.innerHTML = "";
  r.files.forEach((f) => {
    const icon = f.kind === "midi" ? "🎹" : f.kind === "audio" ? "🔊" : "📄";
    files.append(
      el("a", { href: API_BASE + f.url, download: f.name,
                class: "flex justify-between gap-3 px-3 py-2 rounded-lg bg-slate-800/50 hover:bg-slate-800" },
        el("span", { class: "truncate", text: `${icon} ${f.name}` }),
        el("span", { class: "text-slate-500 text-xs flex-none", text: fmtSize(f.size) }))
    );
  });
  if (window.innerWidth < 1024) $("result").scrollIntoView({ behavior: "smooth" });
}

async function openSession(id) {
  try {
    const data = await api(`/api/sessions/${encodeURIComponent(id)}`);
    showResult(data);
  } catch (e) {
    setStatus("Kon sessie niet openen: " + e.message, "error");
  }
}

async function loadSessions() {
  const box = $("sessions");
  try {
    const list = await api("/api/sessions");
    box.innerHTML = "";
    if (!list.length) {
      box.append(el("p", { class: "text-slate-500 text-sm", text: "Nog geen sessies." }));
      return;
    }
    list.slice(0, 15).forEach((s) => {
      const btn = el("button", {
        class: "text-left flex justify-between gap-3 px-3 py-2 rounded-lg bg-slate-800/40 hover:bg-slate-800 w-full",
      },
        el("span", { class: "truncate", text: s.id }),
        el("span", { class: "text-slate-500 text-xs flex-none", text: (s.created || "").replace("T", " ").slice(0, 16) }));
      btn.addEventListener("click", () => openSession(s.id));
      box.append(btn);
    });
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

init().catch((e) => setStatus("Kan de server niet bereiken: " + e.message, "error"));
