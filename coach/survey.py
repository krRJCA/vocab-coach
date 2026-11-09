"""Feedback survey for classmates who try the app.

Usability: the System Usability Scale (SUS; Brooke, 1996), the standard 10-question
usability survey. Each answer is 1 (strongly disagree) to 5 (strongly agree); odd
questions are positive, even ones negative. Score = 2.5 x (sum of (answer - 1) for odd
+ (5 - answer) for even), from 0 to 100. 68 is the average across thousands of studies
(Sauro, 2011); above 80 is in the top 10%.

Learning: three questions on whether the app helps in real life, plus two open questions.
Answers are anonymous and saved in data/feedback.json.
"""

import json
from datetime import date
from pathlib import Path

FEEDBACK_PATH = Path(__file__).resolve().parents[1] / "data" / "feedback.json"

SUS_QUESTIONS = [
    "I think that I would like to use this app frequently.",
    "I found the app unnecessarily complex.",
    "I thought the app was easy to use.",
    "I think that I would need the support of a technical person to be able to use this app.",
    "I found the various functions in this app were well integrated.",
    "I thought there was too much inconsistency in this app.",
    "I would imagine that most people would learn to use this app very quickly.",
    "I found the app very cumbersome to use.",
    "I felt very confident using the app.",
    "I needed to learn a lot of things before I could get going with this app.",
]
LEARNING_QUESTIONS = [
    "The scenarios are situations I really face (or will face) in Busan.",
    "After a lesson, I feel more confident using these phrases in real life.",
    "Speaking practice (Speak, Time attack) helped me more than typing alone.",
]
SCALE = {1: "Strongly disagree", 2: "Disagree", 3: "Neutral", 4: "Agree", 5: "Strongly agree"}
LEVELS = ["Beginner", "Intermediate", "Advanced", "Native speaker"]


def sus_score(answers):
    """SUS score (0-100) from ten answers of 1-5."""
    total = sum((a - 1) if i % 2 == 0 else (5 - a) for i, a in enumerate(answers))
    return total * 2.5


def sus_grade(score):
    """Adjective rating (Bangor, Kortum & Miller, 2009)."""
    if score >= 80.3:
        return "excellent"
    if score >= 68:
        return "good (above average)"
    if score >= 51:
        return "OK (below average)"
    return "poor"


def load():
    try:
        return json.loads(FEEDBACK_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def add(level, sus, learning, useful, improve):
    responses = load()
    responses.append({
        "date": date.today().isoformat(), "level": level, "sus": sus, "learning": learning,
        "sus_score": sus_score(sus), "most_useful": useful.strip(), "improve": improve.strip(),
    })
    FEEDBACK_PATH.write_text(json.dumps(responses, ensure_ascii=False, indent=1), encoding="utf-8")
    return responses[-1]


def summary(responses):
    """Average SUS and average of each learning question."""
    if not responses:
        return None
    count = len(responses)
    return {
        "count": count,
        "sus": sum(r["sus_score"] for r in responses) / count,
        "learning": [sum(r["learning"][i] for r in responses) / count for i in range(len(LEARNING_QUESTIONS))],
    }
