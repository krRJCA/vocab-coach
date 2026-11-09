"""Forgiving answer checking for typed Korean.

Hangul syllables are split into jamo (ㄱ, ㅏ, ...) before comparing, so a
single wrong vowel (주새요 vs 주세요) counts as a small mistake instead of a
whole wrong character. Spaces and punctuation are ignored.

A near match can still change the facts (만 원 vs 이만 원, 아이스 vs 따뜻한,
돼요 vs 안 돼요), so close answers must also pass three rules:
  1. the same numbers,
  2. the same negation (안, 못, 없다, 않다),
  3. the key words a task requires (optional "keywords" in scenarios.json).
"""

import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher

HANGUL_START = 0xAC00
HANGUL_END = 0xD7A3
CLOSE_THRESHOLD = 0.85

INITIALS = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
VOWELS = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
FINALS = ["", *"ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"]

NATIVE_NUMBERS = {
    "한": 1, "하나": 1, "두": 2, "둘": 2, "세": 3, "셋": 3, "네": 4, "넷": 4, "다섯": 5, "여섯": 6,
    "일곱": 7, "여덟": 8, "아홉": 9, "열": 10, "열한": 11, "열하나": 11, "열두": 12, "열둘": 12,
    "스무": 20, "스물": 20,
}
# Short words that are also ordinary words (네 = yes, 이 = this) only count
# as numbers when a counter follows: 네 잔, 이 번.
COUNTERS = ("잔", "개", "원", "번", "호선", "명", "시", "분", "장", "정거장", "킬로", "층", "호", "그릇")
SINO_DIGITS = dict(zip("일이삼사오육칠팔구", range(1, 10)))
SINO_UNITS = {"십": 10, "백": 100, "천": 1000, "만": 10000}
NEGATION_WORDS = {"안", "못"}
NEGATION_STEMS = ("없", "않")


def normalize(text):
    """Lowercase, NFC, and drop spaces and punctuation."""
    text = unicodedata.normalize("NFC", text).lower()
    return "".join(ch for ch in text if ch.isalnum())


def to_jamo(text):
    """Split each Hangul syllable into its initial, vowel, and final jamo."""
    jamo = []
    for ch in text:
        code = ord(ch)
        if HANGUL_START <= code <= HANGUL_END:
            index = code - HANGUL_START
            jamo.append(INITIALS[index // 588])
            jamo.append(VOWELS[(index % 588) // 28])
            jamo.append(FINALS[index % 28])
        else:
            jamo.append(ch)
    return "".join(jamo)


# Speech recognition writes some words in Latin letters: 아이디 → ID, 큐알 → QR
LATIN_WORDS = {"id": "아이디", "qr": "큐알", "kg": "킬로"}
# Store deals: "원 플러스 원" (read in English) is written "1+1" or "1 플러스 1"
DEALS = re.compile(r"(원|1)\s*(플러스|\+)\s*(원|1)")


def spoken_forms(text):
    """Write numbers by value and Latin words in Hangul, so "2명이요" = "두 명이요".

    Speech recognition writes numbers as digits (4,500원, 2명), while the lesson
    text spells them out (사천오백 원, 두 명). Each number becomes <value>.
    """
    for latin, hangul in LATIN_WORDS.items():
        text = re.sub(rf"(?i)(?<![a-z]){latin}(?![a-z])", hangul, text)
    text = DEALS.sub("원플러스원", text)
    return " ".join(f"<{value}>" if value is not None else word for word, value in number_words(text))


def jamo_ratio(a, b):
    a, b = to_jamo(normalize(a)), to_jamo(normalize(b))
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def similarity(answer, target):
    """Similarity from 0 to 1, compared at the jamo level (numbers compared by value)."""
    return max(jamo_ratio(answer, target), jamo_ratio(spoken_forms(answer), spoken_forms(target)))


# ---------- Fact rules ----------


def sino_value(word):
    """Read a Sino-Korean number word such as 이만 or 오천. None if it isn't one."""
    total, digit = 0, None
    for ch in word:
        if ch in SINO_DIGITS and digit is None:
            digit = SINO_DIGITS[ch]
        elif ch in SINO_UNITS:
            total += (digit or 1) * SINO_UNITS[ch]
            digit = None
        else:
            return None
    return total + (digit or 0)


def number_words(text):
    """[(word, number value or None)] for a sentence; counters are split off: 한잔 → 한, 잔."""
    # "다시 한번" (once again) and "한 번 더" (one more time) are idioms, not counts
    text = re.sub(r"다시\s*한\s*번|한\s*번\s*더", " ", text)
    text = re.sub(r"(?<=\d),(?=\d{3})", "", text)  # 4,500 → 4500
    words = []
    for word in re.findall(r"\w+", text):
        word = word.removesuffix("이요").removesuffix("요")  # 하나요, 이만 원이요
        # Split a counter written without a space: 한잔 → 한 잔, 이만원 → 이만 원
        counter = next((c for c in COUNTERS if word.endswith(c) and word != c), None)
        words += [word[: -len(counter)], counter] if counter else [word]
    result = []
    for word, following in zip(words, [*words[1:], ""]):
        value = None
        if digits := re.match(r"(\d+)([만천백]?)", word):  # 4500, 2만, 6천
            value = int(digits.group(1)) * {"만": 10000, "천": 1000, "백": 100, "": 1}[digits.group(2)]
            rest = word[digits.end():]
            result.append((str(value), value))
            if rest:  # 4500원입니다 → 4500 + 원입니다
                result.append((rest, None))
            continue
        if word:
            value = NATIVE_NUMBERS.get(word, sino_value(word))
            amount_follows = word == "만" and sino_value(following) is not None  # 만 오천
            if value is not None and len(word) == 1 and not following.startswith(COUNTERS) \
                    and not amount_follows:
                value = None
        result.append((word, value))
    # "만 오천", "이만 팔천": one amount written as two words → 15000, 28000
    merged = []
    for word, value in result:
        if (merged and value is not None and value < 10000 and merged[-1][1] is not None
                and merged[-1][1] % 10000 == 0 and merged[-1][0].endswith("만")):
            merged[-1] = (merged[-1][0] + word, merged[-1][1] + value)
        else:
            merged.append((word, value))
    return merged


def numbers(text):
    """All numbers in a sentence, written as digits, native or Sino-Korean words."""
    return sorted(value for _, value in number_words(text) if value is not None)


def is_negative(text):
    words = re.findall(r"\w+", text)
    return any(w in NEGATION_WORDS for w in words) or any(
        stem in w for w in words for stem in NEGATION_STEMS
    )


def has_keywords(answer, keywords):
    """Each keyword group is a list of options; the answer needs one from every group."""
    answer = normalize(answer)
    return all(any(normalize(option) in answer for option in group) for group in keywords)


def fact_problem(answer, target, keywords=()):
    """Why the answer says something different from the target, or "" if it doesn't."""
    if numbers(answer) != numbers(target):
        return "different number"
    if is_negative(answer) != is_negative(target):
        return "negation changes the meaning"
    if keywords and not has_keywords(answer, keywords):
        return "missing a key word for this task"
    return ""


def check(answer, accepted, keywords=()):
    """Compare an answer with every accepted form.

    Returns (result, best_match, score) where result is
    "exact", "close", or "wrong".
    """
    if isinstance(accepted, str):
        accepted = [accepted]
    best_match, best_score = accepted[0], 0.0
    for target in accepted:
        score = similarity(answer, target)
        if score > best_score:
            best_match, best_score = target, score
    if best_score == 1.0:
        return "exact", best_match, best_score
    if best_score >= CLOSE_THRESHOLD and not fact_problem(answer, best_match, keywords):
        return "close", best_match, best_score
    return "wrong", best_match, best_score


def find_in_transcript(answer, accepted, keywords=()):
    """Like check(), but also looks for the phrase inside a longer transcript.

    Speech recognition in a noisy place (music with lyrics, people talking)
    often writes down the background words too: "오늘 밤 춤을 춰 큰 사이즈로
    주세요 사랑해". This tries every run of words about as long as the target
    (75-120% of its letters, so "충전해 주세요" can't stand in for "교통카드
    충전해 주세요") and applies the fact rules to the words around it, so a
    "안" just before the phrase still counts.

    Returns (result, best_match, score, found_inside).
    """
    result, match, score = check(answer, accepted, keywords)
    if result != "wrong":
        return result, match, score, False
    if isinstance(accepted, str):
        accepted = [accepted]
    words = answer.split()
    best = None
    for target in accepted:
        size = len(normalize(target))
        for start in range(len(words)):
            for end in range(start + 1, len(words) + 1):
                length = len(normalize(" ".join(words[start:end])))
                if length > size * 1.2 + 1:
                    break
                if length < size * 0.75:
                    continue
                span_result, _, span_score = check(" ".join(words[start:end]), [target], keywords)
                around = " ".join(words[max(0, start - 1):end + 1])
                if span_result == "wrong" or fact_problem(around, target, keywords):
                    continue
                if best is None or span_score > best[2]:
                    best = (span_result, target, span_score)
    if best:
        return (*best, True)
    return result, match, score, False


def shares_sounds(heard, phrase, share=0.5):
    """True if at least `share` of the phrase's letters occur in what was heard."""
    target = Counter(normalize(phrase))
    if not target:
        return False
    found = sum((Counter(normalize(heard)) & target).values())
    return found / sum(target.values()) >= share


def check_spoken(plain, accepted, keywords=(), hinted=None):
    """Grade a spoken answer, using the lesson-phrase hint only as a careful second try.

    plain: what Whisper heard without a hint. hinted: a function that runs Whisper
    again with the lesson's phrases as a hint (only called if needed).

    The hint helps in noisy places, but with no real speech (a tone, a fan, music
    with no voice) Whisper "hears" a lesson phrase out of nothing. So a phrase found
    only with the hint counts only if the plain transcript already contains at least
    half of its sounds.

    Returns (result, best_match, score, heard, how) where how is "", "inside"
    (found inside a longer transcript) or "hint".
    """
    result, match, score, inside = find_in_transcript(plain, accepted, keywords)
    if result != "wrong" or hinted is None:
        return result, match, score, plain, "inside" if inside else ""
    heard = hinted()
    hint_result, hint_match, hint_score, _ = find_in_transcript(heard, accepted, keywords)
    if hint_result != "wrong" and shares_sounds(plain, hint_match):
        return hint_result, hint_match, hint_score, heard, "hint"
    return result, match, score, plain, ""
