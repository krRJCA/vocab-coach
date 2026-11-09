"""Pre-test and post-test: does a lesson actually teach its phrases?

Before a lesson the learner takes a pre-test: every phrase of the scenario, from
its English meaning, with no hints and no feedback until the end. After studying
they take the post-test on the same phrases. The difference is the learning gain,
the standard way to measure whether teaching worked. Tests don't change the
review schedule; they only measure.

Checkpoints (one per level, see data/levels.json) use the same runner on a mix
of phrases from every scenario in the level; passing (80%) completes the level.

Results are saved in data/tests.json:
    {scenario_id: {"pre": result, "post": [result, ...]},
     checkpoint_id: {"checkpoint": [result, ...]}}
    result = {"date", "correct", "total", "answers": [{"chunk", "answer", "result"}]}
"""

import json
import random
from datetime import date
from pathlib import Path

TESTS_PATH = Path(__file__).resolve().parents[1] / "data" / "tests.json"
COUNTS_AS_KNOWN = ("exact", "close")  # same rule as recall: the exact phrase, spelled close enough


def load(path=TESTS_PATH):
    """Test results from `path` (each signed-in user has their own file)."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save(tests, path=TESTS_PATH):
    Path(path).write_text(json.dumps(tests, ensure_ascii=False, indent=1), encoding="utf-8")


def test_items(scenario, kind):
    """The scenario's phrases in a fixed shuffled order (different for pre and post)."""
    ids = [chunk["id"] for chunk in scenario["chunks"]]
    random.Random(f"{scenario['id']}-{kind}").shuffle(ids)
    return ids


def record(tests, scenario_id, kind, answers):
    """Save a finished test. answers: [{"chunk", "answer", "result"}]."""
    result = {
        "date": date.today().isoformat(),
        "correct": sum(a["result"] in COUNTS_AS_KNOWN for a in answers),
        "total": len(answers),
        "answers": answers,
    }
    entry = tests.setdefault(scenario_id, {})
    if kind == "pre":
        entry["pre"] = result
    else:
        entry.setdefault(kind, []).append(result)  # "post" or "checkpoint"
    return result


def checkpoint_items(checkpoint, scenarios):
    """A fixed mix of phrases: `test_per_scenario` from each scenario of the level, interleaved."""
    per = checkpoint.get("test_per_scenario", 2)
    picked = []
    for scenario in scenarios:
        ids = [chunk["id"] for chunk in scenario["chunks"]]
        random.Random(f"{checkpoint['id']}-{scenario['id']}").shuffle(ids)
        picked += ids[:per]
    random.Random(checkpoint["id"]).shuffle(picked)
    return picked


def checkpoint_status(tests, checkpoint):
    """(best score, latest score, passed) for a checkpoint, scores as fractions or None."""
    results = (tests.get(checkpoint["id"]) or {}).get("checkpoint") or []
    scores = [r["correct"] / r["total"] for r in results if r["total"]]
    if not scores:
        return None, None, False
    return max(scores), scores[-1], max(scores) >= checkpoint.get("pass", 0.8)


def summary(tests, scenario_id):
    """(pre score, latest post score, gain) as fractions, or None where missing."""
    entry = tests.get(scenario_id) or {}
    pre = entry.get("pre")
    post = (entry.get("post") or [None])[-1]
    score = lambda r: r["correct"] / r["total"] if r and r["total"] else None  # noqa: E731
    pre_score, post_score = score(pre), score(post)
    gain = post_score - pre_score if pre_score is not None and post_score is not None else None
    return pre_score, post_score, gain
