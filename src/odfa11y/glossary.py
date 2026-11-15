# SPDX-License-Identifier: MPL-2.0
"""Core definitions of domain terms that are not enum values."""

TERMS = {
    "source": "The original document whose bytes bind the reviewed plan.",
    "candidate": "The in-memory or saved document produced by applying reviewed decisions.",
    "plan": "A source-bound set of human questions, answers and fidelity requirements.",
    "decision": "A registered kind, its reviewed target when needed, and a validated answer.",
    "answer": "The explicit human instruction accepted by a decision kind.",
    "target": "A canonical logical path paired with the fingerprint of reviewed content.",
    "fingerprint": "A short content identity that detects a target changing after review.",
    "finding": "An observed document condition reported under an authoritative rule.",
    "rule": "A registered condition with a stable identifier, severity and meaning.",
    "fact": "A typed measurement supplied by the check that owns it.",
    "evidence bundle": "The declared artifacts of a run with their integrity manifest.",
    "manifest (evidence)": "The bundle version and hashes of its declared files.",
    "batch file": "A file listing independent document identifiers, sources and plans.",
    "profile": "The selected level of assurance and acceptance strictness for a run.",
    "fidelity": "Preservation of the source properties required by the reviewed policy.",
    "publication": "Making a completed artifact available at the chosen destination.",
    "refusal": "A policy or source condition that prevents the requested action safely.",
    "remedy": "A typed next action supplied by the producer of an expected failure.",
}
