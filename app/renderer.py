"""Audio-rendering via FluidSynth + nabewerking (fade, trimmen, mixen, WAV/AIFF/M4A)."""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf

from .config import SAMPLE_RATE


class RenderError(RuntimeError):
    pass


def render_midi(fluidsynth: str, soundfont: Path, midi_path: Path, out_wav: Path, gain: float = 0.5) -> None:
    cmd = [fluidsynth, "-ni", "-g", str(gain), "-r", str(SAMPLE_RATE), "-o", "synth.reverb.active=1",
           "-o", "synth.chorus.active=1", "-F", str(out_wav), str(soundfont), str(midi_path)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        raise RenderError("FluidSynth reageerde niet binnen 15 minuten.")
    if proc.returncode != 0 or not out_wav.exists():
        raise RenderError(f"FluidSynth-fout: {(proc.stderr or proc.stdout).strip()[-400:]}")


def load(path: Path) -> np.ndarray:
    data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    if sr != SAMPLE_RATE:
        raise RenderError(f"Onverwachte samplerate {sr}")
    if data.shape[1] == 1:
        data = np.repeat(data, 2, axis=1)
    return data


def fit_length(audio: np.ndarray, n: int) -> np.ndarray:
    if len(audio) >= n:
        return audio[:n]
    return np.vstack([audio, np.zeros((n - len(audio), audio.shape[1]), dtype=audio.dtype)])


def apply_fade(audio: np.ndarray, fade_start_s: Optional[float], fade_end_s: Optional[float],
               tail_fade_s: float = 0.05) -> np.ndarray:
    out = audio.copy()
    n = len(out)
    if fade_start_s is not None and fade_end_s is not None:
        a = int(fade_start_s * SAMPLE_RATE)
        b = min(n, int(fade_end_s * SAMPLE_RATE))
        if b > a:
            t = np.linspace(0.0, 1.0, b - a, dtype=np.float32)
            out[a:b] *= np.cos(t * np.pi / 2)[:, None]   # gelijk aan de CC11-curve
        out[b:] = 0.0
    k = min(n, int(tail_fade_s * SAMPLE_RATE))
    if k > 0:
        out[n - k:] *= np.linspace(1.0, 0.0, k, dtype=np.float32)[:, None]
    return out


def protect_clip(audio: np.ndarray, ceiling: float = 0.97) -> np.ndarray:
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    return audio * (ceiling / peak) if peak > ceiling else audio


def normalize(audio: np.ndarray, target: float = 0.89) -> np.ndarray:
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    return audio * (target / peak) if peak > 1e-6 else audio


def write(audio: np.ndarray, path: Path, fmt: str, subtype: str = "PCM_24") -> None:
    sf.write(str(path), audio, SAMPLE_RATE, format=fmt, subtype=subtype)


def to_m4a(afconvert: Optional[str], wav_path: Path, m4a_path: Path) -> bool:
    if not afconvert:
        return False
    proc = subprocess.run([afconvert, "-f", "m4af", "-d", "aac", "-b", "256000", str(wav_path), str(m4a_path)],
                          capture_output=True, text=True, timeout=300)
    return proc.returncode == 0 and m4a_path.exists()
