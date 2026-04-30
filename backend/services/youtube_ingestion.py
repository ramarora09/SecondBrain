"""YouTube transcript extraction utilities."""

from __future__ import annotations

import os
import re
from urllib.parse import parse_qs, urlparse

try:
    from requests import ConnectionError as RequestsConnectionError
    from requests import Timeout as RequestsTimeout
    from requests.exceptions import ProxyError as RequestsProxyError
    from youtube_transcript_api import (
        NoTranscriptFound,
        RequestBlocked,
        TranscriptsDisabled,
        VideoUnavailable,
        YouTubeTranscriptApi,
    )
    from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig
except Exception:
    RequestsConnectionError = Exception
    RequestsProxyError = Exception
    RequestsTimeout = Exception
    NoTranscriptFound = Exception
    RequestBlocked = Exception
    TranscriptsDisabled = Exception
    VideoUnavailable = Exception
    YouTubeTranscriptApi = None
    GenericProxyConfig = None
    WebshareProxyConfig = None


DEFAULT_LANGUAGES = ("en", "hi", "en-US", "en-GB")


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


def _preferred_languages() -> list[str]:
    """Read transcript language preference from env, preserving a useful default."""
    configured = os.getenv("YOUTUBE_TRANSCRIPT_LANGUAGES", "")
    languages = [lang.strip() for lang in configured.split(",") if lang.strip()]
    return languages or list(DEFAULT_LANGUAGES)


def _proxy_config():
    """Build an optional transcript API proxy config for production hosts."""
    if GenericProxyConfig is None or WebshareProxyConfig is None:
        return None

    webshare_user = os.getenv("WEBSHARE_PROXY_USERNAME", "").strip()
    webshare_password = os.getenv("WEBSHARE_PROXY_PASSWORD", "").strip()
    if webshare_user and webshare_password:
        locations = [
            item.strip()
            for item in os.getenv("WEBSHARE_PROXY_LOCATIONS", "").split(",")
            if item.strip()
        ]
        retries = int(os.getenv("WEBSHARE_RETRIES_WHEN_BLOCKED", "10"))
        return WebshareProxyConfig(
            proxy_username=webshare_user,
            proxy_password=webshare_password,
            filter_ip_locations=locations or None,
            retries_when_blocked=retries,
        )

    proxy_url = os.getenv("YOUTUBE_PROXY_URL", "").strip()
    if proxy_url:
        return GenericProxyConfig(http_url=proxy_url, https_url=proxy_url)

    return None


def _transcript_api():
    if YouTubeTranscriptApi is None:
        raise RuntimeError("youtube-transcript-api is not installed")
    return YouTubeTranscriptApi(proxy_config=_proxy_config())


def _fetch_primary_transcript(video_id: str):
    """Support both older and newer youtube-transcript-api variants."""
    languages = _preferred_languages()
    if hasattr(YouTubeTranscriptApi, "get_transcript"):
        return YouTubeTranscriptApi.get_transcript(video_id, languages=languages)

    api = _transcript_api()
    if hasattr(api, "fetch"):
        return api.fetch(video_id, languages=languages)

    raise RuntimeError("Unsupported youtube-transcript-api version")


def _list_transcripts(video_id: str):
    """Return a transcript list object for fallback transcript selection."""
    if hasattr(YouTubeTranscriptApi, "list_transcripts"):
        return YouTubeTranscriptApi.list_transcripts(video_id)

    api = _transcript_api()
    if hasattr(api, "list"):
        return api.list(video_id)

    raise RuntimeError("Transcript listing is not supported by this youtube-transcript-api version")


def _fetch_from_transcript_object(transcript_obj):
    """Normalize transcript fetch across library versions."""
    if hasattr(transcript_obj, "fetch"):
        return transcript_obj.fetch()
    return transcript_obj


def _choose_transcript(transcript_list):
    """Choose the best manual/generated transcript across configured languages."""
    languages = _preferred_languages()

    for finder in ("find_manually_created_transcript", "find_generated_transcript", "find_transcript"):
        if hasattr(transcript_list, finder):
            try:
                return getattr(transcript_list, finder)(languages)
            except Exception:
                pass

    try:
        available = list(transcript_list)
    except Exception:
        available = []

    if available:
        return available[0]

    return None


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
            transcript_obj = _choose_transcript(transcript_list)
            if transcript_obj is None:
                raise ValueError("No transcript matched the configured languages.")
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
            "Configure a YouTube transcript proxy on the backend or paste the transcript manually."
        ) from exc
    except (RequestsConnectionError, RequestsProxyError, RequestsTimeout) as exc:
        raise ValueError(
            "The backend could not reach YouTube to fetch captions. "
            "Check server network/proxy settings or paste the transcript manually."
        ) from exc
    except Exception as exc:
        message = str(exc)
        if "blocking requests from your IP" in message or "RequestBlocked" in message or "IpBlocked" in message:
            raise ValueError(
                "YouTube is blocking automatic transcript requests from this server. "
                "Configure a YouTube transcript proxy on the backend or paste the transcript manually."
            ) from exc
        raise ValueError(
            "Could not fetch this YouTube transcript automatically. "
            "If captions are available, copy the transcript and paste it manually."
        ) from exc

    text = _normalize_transcript_items(transcript)
    if not text:
        raise ValueError("Transcript was fetched but no readable text was found.")

    return text
