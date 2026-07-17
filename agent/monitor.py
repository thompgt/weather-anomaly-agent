"""
Monitor-loop entry point: poll `anomalies` for status='new', have the agent
investigate each one (classify severity/false-positive using real tool calls,
not guesses), record its note, and send an alert for anything it confirms.

Run once (`python -m agent.monitor`) on a cron/scheduler, or repeatedly during
development with the `/loop` skill to iterate on the prompt quickly.
"""

from __future__ import annotations

import logging

import anthropic

from . import db
from .tools import ALL_TOOLS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = anthropic.Anthropic()

SYSTEM_PROMPT = """You are a weather anomaly investigation agent. You will be given
one detected anomaly (already flagged by a statistical detection engine — you do
not need to re-derive whether it's numerically unusual, that part is done).

Your job:
1. Use the tools to look at the surrounding time series, compare to climatology,
   and pull related anomalies for context.
2. Decide whether this looks like a real, alert-worthy weather event, or likely
   noise/a false positive (e.g. a sensor glitch, a single-point spike with no
   surrounding support).
3. Call update_anomaly with status "confirmed" or "dismissed" and a concise
   agent_note explaining your reasoning, citing the actual numbers you observed.
4. If confirmed and severity is "medium" or "high", call send_alert with a short,
   specific message (station, variable, magnitude, time) grounded in your tool
   results. Do not alert on "low" severity or dismissed anomalies.

Be concise. Do not speculate about numbers you have not queried."""


def investigate_anomaly(anomaly: dict) -> None:
    prompt = f"Investigate this anomaly and take action: {anomaly}"
    runner = client.beta.messages.tool_runner(
        model="claude-opus-4-8",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=ALL_TOOLS,
        messages=[{"role": "user", "content": prompt}],
    )
    for message in runner:
        for block in message.content:
            if block.type == "text" and block.text.strip():
                logger.info("agent: %s", block.text.strip())


def run_monitor_pass() -> int:
    new_anomalies = db.get_anomalies(status="new")
    for anomaly in new_anomalies:
        logger.info("investigating anomaly %s", anomaly["id"])
        investigate_anomaly(anomaly)
    return len(new_anomalies)


if __name__ == "__main__":
    count = run_monitor_pass()
    logger.info("processed %d new anomalies", count)
