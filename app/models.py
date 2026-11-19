"""Pydantic-modellen voor de REST API (ook bruikbaar als contract voor een iOS-client)."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class MusicProfile(BaseModel):
    title: str = ""
    source: Literal["library", "claude", "heuristic", "mood"] = "mood"
    genre: str
    mood: str
    bpm: int = Field(ge=50, le=180)
    key: str
    verse: str
    chorus: str
    bridge: str
    drum_style: str
    bass_style: str
    keys_style: str
    guitar_style: str
    pad_style: str
    velocity: int = Field(85, ge=30, le=127)
    swing: float = Field(0.0, ge=0.0, le=1.0)
    color: int = Field(0, ge=0, le=2)
    programs: dict[str, int] = Field(default_factory=dict)
    description: str = ""


class AnalyzeRequest(BaseModel):
    reference: str = Field(min_length=1, max_length=200)
    api_key: Optional[str] = None
    use_claude: bool = True


class AnalyzeResponse(BaseModel):
    profile: MusicProfile
    source: str
    matched: Optional[str] = None
    confidence: float = 0.0
    message: str = ""


class Instruments(BaseModel):
    drums: bool = True
    bass: bool = True
    keys: bool = True
    guitar: bool = True
    pad: bool = True


class GenerateRequest(BaseModel):
    reference: Optional[str] = None
    profile: Optional[MusicProfile] = None
    mood: str = "sad"
    genre: str = "auto"
    key: str = "auto"
    progression_mode: Literal["auto", "preset", "custom"] = "auto"
    progression_preset: Optional[str] = None
    progression_custom: Optional[str] = None
    bpm: int = Field(90, ge=50, le=180)
    duration_seconds: int = Field(240, ge=60, le=600)
    bridge: bool = True
    fade_outro: bool = True
    fade_bars: int = Field(8, ge=4, le=8)
    instruments: Instruments = Field(default_factory=Instruments)
    formats: list[Literal["wav", "aiff"]] = Field(default_factory=lambda: ["wav"])
    seed: Optional[int] = None
    humanize: bool = True


class SectionInfo(BaseModel):
    name: str
    label: str
    start_bar: int
    bars: int
    energy: float
    chords: list[str]


class FileInfo(BaseModel):
    name: str
    kind: str
    instrument: Optional[str] = None
    size: int
    url: str


class SessionResult(BaseModel):
    id: str
    folder: str
    path: str
    created: str
    title: str
    genre: str
    mood: str
    key: str
    bpm: int
    bars: int
    duration_seconds: float
    requested_seconds: int
    seed: int
    fade_outro: bool
    bridge: bool
    sections: list[SectionInfo]
    files: list[FileInfo]
    mix_url: Optional[str] = None
    zip_url: str
    audio_rendered: bool
    warnings: list[str] = Field(default_factory=list)
    profile: MusicProfile


class PreviewResult(BaseModel):
    url: Optional[str]
    bars: int
    seconds: float
    audio_rendered: bool
    warnings: list[str] = Field(default_factory=list)
