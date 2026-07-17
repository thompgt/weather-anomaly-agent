"""
Scheduled-report entry point: pull stats + anomalies for a period and have the
agent write a narrative summary, saved via save_report.

Run on a daily/weekly cron: `python -m agent.report --period daily`
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timedelta, timezone

import anthropic

from .tools import ALL_TOOLS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are a weather analysis reporting agent. You will be given a
reporting period. Use the tools to pull anomalies and stat summaries for the
stations in the system (denver-co, miami-fl, seattle-wa) over that period, then
write a concise markdown report: notable anomalies (cite the real numbers you
pulled), overall conditions per station, and anything worth flagging for next
period. Ground every claim in a tool result — do not invent statistics.

When done, call save_report with the period bounds, a short title, and the
markdown body."""


def run_report(period: str) -> None:
    end = datetime.now(timezone.utc)
    start = end - (timedelta(days=1) if period == "daily" else timedelta(days=7))
    prompt = (
        f"Generate a {period} report for the period "
        f"{start.isoformat()} to {end.isoformat()}."
    )
    runner = client.beta.messages.tool_runner(
        model="claude-opus-4-8",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        tools=ALL_TOOLS,
        messages=[{"role": "user", "content": prompt}],
    )
    for message in runner:
        for block in message.content:
            if block.type == "text" and block.text.strip():
                logger.info("agent: %s", block.text.strip())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", choices=["daily", "weekly"], default="daily")
    args = parser.parse_args()
    run_report(args.period)
