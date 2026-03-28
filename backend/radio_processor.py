"""
Radio processing pipeline:
  OpenF1 audio URL → Faster-Whisper transcription → keyword extraction → VADER sentiment
"""

import asyncio
import httpx
import tempfile
import os
from typing import Optional
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Lazy-load Whisper model (loaded once on first use)
_whisper_model = None
_vader = SentimentIntensityAnalyzer()

# Cache of already-processed URLs so we never re-transcribe
_processed_urls: set[str] = set()

PIT_KEYWORDS = {"pit", "box", "pitting"}
TIRE_KEYWORDS = {"tire", "tyre", "soft", "medium", "hard", "intermediate", "deg", "graining"}
SC_KEYWORDS = {"safety car", "vsc", "virtual"}
ISSUE_KEYWORDS = {"damage", "brake", "engine", "vibration", "hydraulic", "water", "smoke", "fire"}


def _get_whisper():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
    return _whisper_model


def transcribe_audio(audio_bytes: bytes) -> str:
    model = _get_whisper()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name
    try:
        segments, _ = model.transcribe(tmp_path, beam_size=1)
        return " ".join(s.text.strip() for s in segments)
    finally:
        os.unlink(tmp_path)


def extract_keywords(text: str) -> list[str]:
    lower = text.lower()
    found = []
    for kw in PIT_KEYWORDS:
        if kw in lower:
            found.append("PIT")
            break
    for kw in TIRE_KEYWORDS:
        if kw in lower:
            found.append("TIRE")
            break
    for kw in SC_KEYWORDS:
        if kw in lower:
            found.append("SC")
            break
    for kw in ISSUE_KEYWORDS:
        if kw in lower:
            found.append("ISSUE")
            break
    return found


def sentiment_score(text: str) -> float:
    return _vader.polarity_scores(text)["compound"]


def has_pit_keyword(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in PIT_KEYWORDS)


async def process_clip(clip: dict) -> Optional[dict]:
    """
    Downloads and processes a single radio clip.
    Returns None if already processed or download fails.
    """
    url = clip.get("recording_url")
    if not url or url in _processed_urls:
        return None

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            audio_bytes = resp.content
    except Exception as e:
        print(f"[Radio] Failed to download {url}: {e}")
        return None

    try:
        transcript = await asyncio.to_thread(transcribe_audio, audio_bytes)
    except Exception as e:
        print(f"[Radio] Transcription failed for {url}: {e}")
        return None

    _processed_urls.add(url)

    return {
        "driver_number": clip["driver_number"],
        "transcript": transcript,
        "keywords": extract_keywords(transcript),
        "sentiment": sentiment_score(transcript),
        "pit_keyword": has_pit_keyword(transcript),
        "date": clip.get("date"),
    }


async def process_clips(clips: list[dict]) -> list[dict]:
    """Process a batch of clips concurrently."""
    results = await asyncio.gather(*[process_clip(c) for c in clips])
    return [r for r in results if r is not None]
