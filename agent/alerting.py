"""Slack webhook alert delivery (MVP alert channel)."""

from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

load_dotenv()

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")


def send_alert(channel: str, message: str) -> str:
    """Send an alert. `channel` is currently ignored (single Slack webhook); kept
    in the tool signature so a future multi-channel router is a non-breaking change."""
    if not SLACK_WEBHOOK_URL:
        return "No SLACK_WEBHOOK_URL configured; alert not sent. Message was: " + message
    resp = requests.post(SLACK_WEBHOOK_URL, json={"text": message}, timeout=10)
    resp.raise_for_status()
    return "Alert sent."
