"""Backward-compatible YouTube helpers.

The active ingestion route uses services.youtube_ingestion directly. Keep these
aliases so older imports still get the hardened implementation.
"""

from services.youtube_ingestion import extract_transcript, extract_video_id as get_video_id
