"""YouTube transcript extraction utilities."""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

try:
    from youtube_transcript_api import (
        NoTranscriptFound,
        RequestBlocked,
        TranscriptsDisabled,
        VideoUnavailable,
        YouTubeTranscriptApi,
    )
except Exception:
    NoTranscriptFound = Exception
    RequestBlocked = Exception
    TranscriptsDisabled = Exception
    VideoUnavailable = Exception
    YouTubeTranscriptApi = None


def extract_video_id(url: str) -> str:
    """Extract a YouTube video id from common URL formats."""
    cleaned_url = (url or "").strip()
    if not cleaned_url:
        return ""

    if re.fullmatch(r"[A-Za-z0-9_-]{11}", cleaned_url):
        return cleaned_url

    parsed = urlparse(cleaned_url)
    host = parsed.netloc.lower()

    if "youtu.be" in host:
        return parsed.path.strip("/").split("/")[0]

    if "youtube.com" in host:
        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [""])[0]
        if parsed.path.startswith("/shorts/") or parsed.path.startswith("/embed/"):
            parts = parsed.path.strip("/").split("/")
            return parts[1] if len(parts) > 1 else ""

    return ""


def _fetch_primary_transcript(video_id: str):
    """Support both older and newer youtube-transcript-api variants."""
    if hasattr(YouTubeTranscriptApi, "get_transcript"):
        return YouTubeTranscriptApi.get_transcript(video_id)

    api = YouTubeTranscriptApi()
    if hasattr(api, "fetch"):
        return api.fetch(video_id)

    raise RuntimeError("Unsupported youtube-transcript-api version")


def _list_transcripts(video_id: str):
    """Return a transcript list object for fallback transcript selection."""
    if hasattr(YouTubeTranscriptApi, "list_transcripts"):
        return YouTubeTranscriptApi.list_transcripts(video_id)

    api = YouTubeTranscriptApi()
    if hasattr(api, "list"):
        return api.list(video_id)

    raise RuntimeError("Transcript listing is not supported by this youtube-transcript-api version")


def _fetch_from_transcript_object(transcript_obj):
    """Normalize transcript fetch across library versions."""
    if hasattr(transcript_obj, "fetch"):
        return transcript_obj.fetch()
    return transcript_obj


def _normalize_transcript_items(transcript) -> str:
    """Convert transcript entries to a single searchable text blob."""
    parts: list[str] = []

    for item in transcript or []:
        if isinstance(item, dict):
            text = str(item.get("text", "")).strip()
        else:
            text = str(getattr(item, "text", "")).strip()
        if text:
            parts.append(text)

    return " ".join(parts).strip()


def extract_transcript(url: str) -> str:
    """Fetch a YouTube transcript or raise a user-friendly error."""
    if YouTubeTranscriptApi is None:
        raise ValueError(
            "youtube-transcript-api is not installed. Install backend requirements to enable YouTube ingestion."
        )

    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError("Invalid YouTube URL or video id.")

    try:
        transcript = _fetch_primary_transcript(video_id)
    except (NoTranscriptFound, TranscriptsDisabled):
        try:
            transcript_list = _list_transcripts(video_id)
            transcript_obj = None

            if hasattr(transcript_list, "find_generated_transcript"):
                try:
                    transcript_obj = transcript_list.find_generated_transcript(["en", "hi"])
                except Exception:
                    transcript_obj = None

            if transcript_obj is None and hasattr(transcript_list, "find_transcript"):
                transcript_obj = transcript_list.find_transcript(["en", "hi"])

            transcript = _fetch_from_transcript_object(transcript_obj)
        except Exception as exc:
            raise ValueError(
                "This YouTube video does not have accessible captions or transcripts."
            ) from exc
    except VideoUnavailable as exc:
        raise ValueError("This YouTube video is unavailable.") from exc
    except RequestBlocked as exc:
        raise ValueError(
            "YouTube is blocking automatic transcript requests from this server. "
            "Paste the transcript manually in the YouTube upload box and I can still index it."
        ) from exc
    except Exception as exc:
        message = str(exc)
        if "blocking requests from your IP" in message or "RequestBlocked" in message or "IpBlocked" in message:
            raise ValueError(
                "YouTube is blocking automatic transcript requests from this server. "
                "Paste the transcript manually in the YouTube upload box and I can still index it."
            ) from exc
        raise ValueError(
            "Could not fetch this YouTube transcript automatically. "
            "If captions are available, copy the transcript and paste it manually."
        ) from exc

    text = _normalize_transcript_items(transcript)
    if not text:
        raise ValueError("Transcript was fetched but no readable text was found.")

    return text
