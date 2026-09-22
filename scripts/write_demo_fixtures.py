"""Write the hand-authored extraction fixtures for the demo export.

The fixture key depends on the conversation id and message hashes, so this
script computes it rather than hard-coding file names. The content below was
written by a person reading the demo conversations; every message_id is a
real id from the export except one, which is deliberately wrong to show the
UNVERIFIED path.
"""

from __future__ import annotations

import json
from pathlib import Path

from afterthought.compile.extract import build_request
from afterthought.ingest import load
from afterthought.ingest.base import group_conversations
from afterthought.redact import redact

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / "examples" / "chatgpt-export" / "conversations.json"
OUT = ROOT / "examples" / "chatgpt-export" / "fixtures"
MODEL = "hand-authored fixture"

RESPONSES = {
    "conv-lantern-01": {
        "summary": "The user started Lantern, a home energy dashboard fed by an Octopus Home Mini, chose PostgreSQL with TimescaleDB over InfluxDB for storage and Grafana over a custom UI, and left downsampling as an open question.",
        "entities": [
            {
                "name": "Lantern",
                "kind": "project",
                "aliases": [],
                "facts": [
                    {
                        "text": "Lantern is a side project: a home energy dashboard.",
                        "message_id": "conv-lantern-01-m01",
                    },
                    {
                        "text": "Lantern reads an Octopus Home Mini smart meter every 30 seconds and shows usage, cost and a forecast for the day.",
                        "message_id": "conv-lantern-01-m01",
                    },
                    {
                        "text": "Readings must be stored for at least two years.",
                        "message_id": "conv-lantern-01-m01",
                    },
                    {
                        "text": "At 30-second resolution Lantern will store roughly 1 million readings a year.",
                        "message_id": "conv-lantern-01-m02",
                    },
                    {
                        "text": "Storage will be PostgreSQL with the TimescaleDB extension.",
                        "message_id": "conv-lantern-01-m03",
                    },
                    {
                        "text": "Lantern runs on a Raspberry Pi 4.",
                        "message_id": "conv-lantern-01-m03",
                    },
                    {
                        "text": "The dashboard will use Grafana rather than a custom UI for now.",
                        "message_id": "conv-lantern-01-m05",
                    },
                ],
            },
            {
                "name": "Octopus Home Mini",
                "kind": "tool",
                "aliases": ["Home Mini"],
                "facts": [
                    {
                        "text": "Provides smart meter readings every 30 seconds through the Octopus API.",
                        "message_id": "conv-lantern-01-m01",
                    },
                    {
                        "text": "Octopus has changed the Home Mini API before.",
                        "message_id": "conv-lantern-01-m04",
                    },
                    {
                        "text": "The Home Mini provides 30-second data at no charge.",
                        "message_id": "conv-lantern-01-m07",
                    },
                ],
            },
            {
                "name": "PostgreSQL",
                "kind": "tool",
                "aliases": ["Postgres"],
                "facts": [
                    {
                        "text": "Chosen as Lantern's storage together with the TimescaleDB extension.",
                        "message_id": "conv-lantern-01-m03",
                    },
                    {
                        "text": "Easier to join readings against tariff tables than InfluxDB because it is relational.",
                        "message_id": "conv-lantern-01-m02",
                    },
                ],
            },
            {
                "name": "TimescaleDB",
                "kind": "tool",
                "aliases": ["Timescale"],
                "facts": [
                    {
                        "text": "Adds automatic time partitioning, continuous aggregates and compression to PostgreSQL.",
                        "message_id": "conv-lantern-01-m02",
                    },
                    {
                        "text": "Compression can shrink two years of readings to a few hundred megabytes.",
                        "message_id": "conv-lantern-01-m02",
                    },
                    {
                        "text": "Compression jobs can spike memory on a Raspberry Pi 4, so shared_buffers should be set conservatively.",
                        "message_id": "conv-lantern-01-m04",
                    },
                ],
            },
            {
                "name": "InfluxDB",
                "kind": "tool",
                "aliases": [],
                "facts": [
                    {
                        "text": "Considered for Lantern storage: very fast ingest, but a second query language and a weaker story for joining with relational data.",
                        "message_id": "conv-lantern-01-m02",
                    },
                ],
            },
            {
                "name": "Grafana",
                "kind": "tool",
                "aliases": [],
                "facts": [
                    {
                        "text": "Suggested by Priya for the Lantern dashboard instead of a custom UI.",
                        "message_id": "conv-lantern-01-m03",
                    },
                    {
                        "text": "Talks to Postgres natively and provides time-range pickers, alerting and annotations.",
                        "message_id": "conv-lantern-01-m04",
                    },
                ],
            },
            {
                "name": "Priya",
                "kind": "person",
                "aliases": [],
                "facts": [
                    {
                        "text": "Runs the data team at the user's day job.",
                        "message_id": "conv-lantern-01-m03",
                    },
                    {
                        "text": "Suggested Grafana for the Lantern dashboard.",
                        "message_id": "conv-lantern-01-m03",
                    },
                ],
            },
            {
                "name": "Raspberry Pi 4",
                "kind": "tool",
                "aliases": ["Pi 4", "Pi"],
                "facts": [
                    {
                        "text": "Hosts Lantern; a 4 GB model runs Postgres fine.",
                        "message_id": "conv-lantern-01-m04",
                    },
                ],
            },
        ],
        "decisions": [
            {
                "question": "Which storage should Lantern use for two years of 30-second meter readings?",
                "options": ["PostgreSQL with TimescaleDB", "InfluxDB"],
                "chosen": "PostgreSQL with TimescaleDB",
                "reasoning": "Familiar SQL, easy joins with tariff tables, automatic time partitioning, continuous aggregates and compression.",
                "assumptions": [
                    "The Octopus Home Mini keeps providing 30-second data for free",
                    "A Raspberry Pi 4 can run Postgres comfortably",
                ],
                "decider": None,
                "message_id": "conv-lantern-01-m03",
            },
            {
                "question": "Should the Lantern dashboard use Grafana or a custom UI?",
                "options": ["Grafana", "Custom UI"],
                "chosen": "Grafana",
                "reasoning": "Native Postgres support, time-range pickers, alerting and annotations for free; a custom UI can come later if the dashboard outgrows it.",
                "assumptions": [],
                "decider": None,
                "message_id": "conv-lantern-01-m05",
            },
        ],
        "questions": [
            {
                "text": "How to downsample two years of 30-second data for graphs without losing the peaks?",
                "message_id": "conv-lantern-01-m05",
            },
        ],
    },
    "conv-lantern-02": {
        "summary": "The user learned how to downsample Lantern's 30-second readings without losing peaks and settled on 5-minute and 1-hour continuous aggregates that store mean, max and min.",
        "entities": [
            {
                "name": "Lantern",
                "kind": "project",
                "aliases": [],
                "facts": [
                    {
                        "text": "Lantern will keep 5-minute and 1-hour continuous aggregates storing mean, max and min per bucket.",
                        "message_id": "conv-lantern-02-m03",
                    },
                    {
                        "text": "Raw readings will be compressed after seven days.",
                        "message_id": "conv-lantern-02-m04",
                    },
                    {
                        "text": "Tariff changes will be marked on graphs as Grafana annotations.",
                        "message_id": "conv-lantern-02-m03",
                    },
                ],
            },
            {
                "name": "Time-series downsampling",
                "kind": "concept",
                "aliases": ["downsampling"],
                "facts": [
                    {
                        "text": "Averaging 30-second readings into 5-minute buckets hides short spikes such as a kettle.",
                        "message_id": "conv-lantern-02-m01",
                    },
                    {
                        "text": "Keeping mean, max and min per bucket preserves peaks when graphing: draw the mean as a line and the max as a faint band.",
                        "message_id": "conv-lantern-02-m02",
                    },
                    {
                        "text": "LTTB (largest triangle three buckets) picks visually important points instead of averaging.",
                        "message_id": "conv-lantern-02-m02",
                    },
                ],
            },
            {
                "name": "TimescaleDB",
                "kind": "tool",
                "aliases": ["Timescale"],
                "facts": [
                    {
                        "text": "Continuous aggregates maintain bucketed statistics automatically as new readings arrive.",
                        "message_id": "conv-lantern-02-m02",
                    },
                    {
                        "text": "The Timescale toolkit extension ships an lttb() function.",
                        "message_id": "conv-lantern-02-m02",
                    },
                ],
            },
            {
                "name": "Grafana",
                "kind": "tool",
                "aliases": [],
                "facts": [
                    {
                        "text": "Has a plugin for LTTB downsampling.",
                        "message_id": "conv-lantern-02-m02",
                    },
                    {
                        "text": "Annotations can mark events such as deploys or tariff changes on graphs.",
                        "message_id": "conv-lantern-02-m03",
                    },
                ],
            },
            {
                "name": "Priya",
                "kind": "person",
                "aliases": [],
                "facts": [
                    {
                        "text": "Her data team uses Grafana annotations to mark deploys.",
                        "message_id": "conv-lantern-02-m03",
                    },
                ],
            },
        ],
        "decisions": [
            {
                "question": "How should Lantern downsample readings for graphs?",
                "options": [
                    "Mean only per bucket",
                    "Mean, max and min per bucket in continuous aggregates",
                    "LTTB",
                ],
                "chosen": "Mean, max and min per bucket in 5-minute and 1-hour continuous aggregates",
                "reasoning": "Peaks stay visible as a band above the mean and Timescale maintains the buckets automatically.",
                "assumptions": [],
                "decider": None,
                "message_id": "conv-lantern-02-m03",
            },
        ],
        "questions": [],
    },
    "conv-lantern-03": {
        "summary": "After losing readings during two broadband outages, the user decided to move Postgres and Grafana to a small VPS and keep the collector on the Raspberry Pi with a local retry buffer.",
        "entities": [
            {
                "name": "Lantern",
                "kind": "project",
                "aliases": [],
                "facts": [
                    {
                        "text": "Home broadband dropped twice in one week and readings were lost.",
                        "message_id": "conv-lantern-03-m01",
                    },
                    {
                        "text": "Postgres and Grafana will move to a small VPS; the collector stays on the Raspberry Pi with a local retry buffer.",
                        "message_id": "conv-lantern-03-m03",
                    },
                    {
                        "text": "The hosting decision will be revisited in June if the VPS bill or SD card wear becomes a problem.",
                        "message_id": "conv-lantern-03-m03",
                    },
                ],
            },
            {
                "name": "Raspberry Pi 4",
                "kind": "tool",
                "aliases": ["Pi"],
                "facts": [
                    {
                        "text": "Will run only the Lantern collector after the move to a VPS.",
                        "message_id": "conv-lantern-03-m03",
                    },
                    {
                        "text": "A day of 30-second readings is about 3,000 rows and will not wear an SD card, but Postgres write-ahead logs would have.",
                        "message_id": "conv-lantern-03-m04",
                    },
                ],
            },
            {
                "name": "VPS",
                "kind": "tool",
                "aliases": ["virtual private server"],
                "facts": [
                    {
                        "text": "Will host Lantern's Postgres and Grafana.",
                        "message_id": "conv-lantern-03-m03",
                    },
                    {
                        "text": "Assumed to cost under 5 pounds a month.",
                        "message_id": "conv-lantern-03-m03",
                    },
                ],
            },
            {
                "name": "PostgreSQL",
                "kind": "tool",
                "aliases": ["Postgres"],
                "facts": [
                    {
                        "text": "Moving Postgres off the Pi removes the SD card write-ahead log wear risk.",
                        "message_id": "conv-lantern-03-m04",
                    },
                ],
            },
            {
                "name": "Grafana",
                "kind": "tool",
                "aliases": [],
                "facts": [
                    {
                        "text": "Will move to the VPS with Postgres so the dashboard stays up during home broadband outages.",
                        "message_id": "conv-lantern-03-m03",
                    },
                ],
            },
        ],
        "decisions": [
            {
                "question": "Where should Lantern's database and dashboard run: the home Raspberry Pi or a VPS?",
                "options": [
                    "Stay on the Pi with a local buffer",
                    "Postgres and Grafana on a VPS, collector on the Pi",
                    "Everything on the VPS polling the Octopus cloud API",
                ],
                "chosen": "Postgres and Grafana on a VPS, collector stays on the Pi with a local retry buffer",
                "reasoning": "The outages were broadband rather than power, so splitting the collector from the database keeps the dashboard available for the least change.",
                "assumptions": [
                    "A small VPS costs under 5 pounds a month",
                    "The Pi collector can buffer a day of readings on its SD card",
                ],
                "decider": None,
                "message_id": "conv-lantern-03-m03",
            },
        ],
        "questions": [],
    },
}


def main() -> None:
    msgs = [m.model_copy(update={"text": redact(m.text)[0]}) for m in load(EXPORT)]
    for conv in group_conversations(msgs):
        req = build_request(conv, [m.span for m in conv.messages])
        path = OUT / req.task / f"{req.key}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"task": req.task, "key": req.key, "model": MODEL, "response": RESPONSES[conv.id]}
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("wrote", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
