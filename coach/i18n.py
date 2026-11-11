"""English / Japanese for the learner-facing app.

T("English text {n}", n=3) shows the text in the chosen language. The English text itself is
the key, so a missing translation simply falls back to English. Lesson content (data/
scenarios.json) gets its Japanese from data/scenarios_ja.json, read with L(obj, "en").

The language comes from ?lang=ja in the address (so a link can open in Japanese), else the
sidebar switch, else the browser's language on the first visit. Korean, romanization and audio
are never translated. The team-only areas (Model lab, survey results) stay in English.
"""

import json
from pathlib import Path

import streamlit as st

LANGUAGES = {"en": "English", "ja": "日本語"}
CONTENT_JA = json.loads((Path(__file__).resolve().parents[1] / "data" / "scenarios_ja.json").read_text(encoding="utf-8"))


def lang():
    state = st.session_state
    if "lang" not in state:
        asked = st.query_params.get("lang")
        if asked in LANGUAGES:
            state.lang = asked
        else:
            locale = (getattr(st.context, "locale", None) or "").lower()
            state.lang = "ja" if locale.startswith("ja") else "en"
    return state.lang


def T(text, **values):
    if lang() == "ja":
        text = JA.get(text, text)
    return text.format(**values) if values else text


def L(obj, key):
    """A content field in the chosen language: L(chunk, "en"), L(turn, "task_en"), L(chunk, "note")."""
    if lang() == "ja":
        ja_key = "ja" if key == "en" else key[:-3] + "_ja" if key.endswith("_en") else key + "_ja"
        if obj.get(ja_key):
            return obj[ja_key]
    return obj[key]


def add_japanese(scenarios, levels):
    """Attach the Japanese fields from data/scenarios_ja.json to the lesson content."""
    ja = CONTENT_JA
    for scenario in scenarios:
        info = ja["scenarios"].get(scenario["id"], {})
        scenario["title_ja"], scenario["situation_ja"] = info.get("title"), info.get("situation")
        scenario["level_ja"] = info.get("level")
        for number, line in enumerate(scenario["dialogue"], 1):
            line["ja"] = ja["lines"].get(f"{scenario['id']}_d{number}")
        for chunk in scenario["chunks"]:
            info = ja["chunks"].get(chunk["id"], {})
            chunk["ja"], chunk["note_ja"] = info.get("en"), info.get("note")
            chunk["common_mistake_ja"] = info.get("mistake")
            chunk["register_ja"] = ja["registers"].get(chunk["register"])
        add_turns(scenario["roleplay"])
    for level in levels:
        info = ja["levels"].get(level["id"], {})
        level["title_ja"], level["level_ja"] = info.get("title"), info.get("level")
        level["description_ja"] = info.get("description")
        if checkpoint := level.get("checkpoint"):
            info = ja["levels"].get(checkpoint["id"], {})
            checkpoint["title_ja"], checkpoint["situation_ja"] = info.get("title"), info.get("situation")
            add_turns(checkpoint["roleplay"])
        for item in level.get("planned", []):
            item["title_ja"] = ja["planned"].get(item["title_en"])


def add_turns(turns):
    for turn in turns:
        info = CONTENT_JA["roleplay"].get(turn["id"], {})
        turn["prompt_ja"], turn["task_ja"] = info.get("prompt"), info.get("task")


JA = {
    # ---- loading, answering, feedback
    "Loading your progress…": "学習の記録を読み込んでいます…",
    "Loading the AI model (first time only)…": "AIモデルを読み込んでいます（初回のみ）…",
    "Loading {model} (first time only)…": "{model}を読み込んでいます（初回のみ）…",
    "{label}: tap the mic and say it in Korean": "{label}：マイクをタップして韓国語で言ってください",
    "Listening…": "聞き取り中…",
    "Listening again more closely…": "もう一度よく聞いています…",
    "I couldn't hear anything. Try recording again, a little louder.":
        "何も聞こえませんでした。もう少し大きな声で、もう一度録音してください。",
    "Check": "チェック",
    "Found your phrase among background sounds.": "周りの音の中から、あなたのフレーズを見つけました。",
    "AI meaning similarity {score}": "AIによる意味の類似度 {score}",
    "AI meaning similarity {score}: {reason}": "AIによる意味の類似度 {score}：{reason}",
    "different meaning": "意味が違います",
    "different number": "数字が違います",
    "negation changes the meaning": "否定で意味が変わっています",
    "missing a key word for this task": "この課題の大事な単語が抜けています",
    "정확해요! Exactly right: **{match}**": "정확해요! 完璧です：**{match}**",
    "Almost! Check the spelling: **{match}**": "おしい！つづりを確認しましょう：**{match}**",
    "Right meaning! The phrase we're practicing is: **{match}**": "意味は合っています！練習中のフレーズは：**{match}**",
    "자연스러워요! Different words, same meaning. Model answer: **{match}**":
        "자연스러워요! 言い方は違っても意味は同じです。模範解答：**{match}**",
    "Not quite. A natural answer: **{match}**": "ちょっと違います。自然な答え：**{match}**",
    "✅ Also correct: ": "✅ これも正解：",
    "🎙️ {model} heard: {answer}": "🎙️ {model}の聞き取り：{answer}",
    "You wrote: {answer}": "あなたの答え：{answer}",
    # ---- recall
    "How do you say it in Korean?": "韓国語で何と言いますか？",
    "Hint: *{romanization}*": "ヒント：*{romanization}*",
    "Your answer": "あなたの答え",
    "Show hint": "ヒントを見る",
    "🔊 Listen and repeat:": "🔊 聞いて、まねして言ってみましょう：",
    "🎙️ Your recording:": "🎙️ あなたの録音：",
    "It will come back tomorrow so you can practice this exact phrase.":
        "このフレーズそのものを練習できるよう、明日もう一度出題します。",
    "You used the hint, so this phrase will come back tomorrow.": "ヒントを使ったので、このフレーズは明日もう一度出題します。",
    "Practice again": "もう一度練習する",
    "Next →": "次へ →",
    # ---- home and cards
    "{n} phrases": "{n}フレーズ",
    "{n}-turn role-play": "{n}ターンのロールプレイ",
    "Start anyway →": "このまま始める →",
    "Start lesson →": "レッスンを始める →",
    "✅ Passed": "✅ 合格",
    "Best so far: {best}": "これまでの最高：{best}",
    "Open anytime: also works as a placement test": "いつでも受けられます。レベル確認テストとしても使えます",
    "Checkpoint {n}": "チェックポイント{n}",
    "{n}-phrase mixed test": "{n}フレーズの総合テスト",
    "{n}-turn story": "{n}ターンのストーリー",
    "pass: {pct}": "合格ライン：{pct}",
    "Take the checkpoint →": "チェックポイントに挑戦 →",
    "🚧 coming soon": "🚧 準備中",
    "Level {n}": "レベル{n}",
    "{level} · TOPIK {topik} level": "{level} · TOPIK {topik}級レベル",
    "✅ complete": "✅ 修了",
    "{done} / {total} lessons finished (post-test taken).": "{done} / {total} レッスン修了（事後テスト受験済み）。",
    "🔒 Recommended after Checkpoint {n}. You can still open any lesson.":
        "🔒 チェックポイント{n}のあとがおすすめです。どのレッスンも開けます。",
    "REAL KOREAN FOR BUSAN": "釜山ですぐ使える韓国語",
    "Learn the Korean you actually need in Busan: whole phrases inside real situations, practiced until "
    "you can say them without help.":
        "釜山で本当に必要な韓国語を、実際の場面の中でフレーズごと学び、何も見ずに言えるようになるまで練習します。",
    "🎬 {n} scenarios in {levels} levels": "🎬 {levels}レベル・{n}シーン",
    "💬 {n} phrases": "💬 {n}フレーズ",
    "🔊 Natural Korean voices": "🔊 自然な韓国語の音声",
    "🎙️ Speak or type": "🎙️ 話しても、打ってもOK",
    "How a lesson works": "レッスンの流れ",
    "Situation": "場面",
    "Notice": "気づく",
    "Recall": "思い出す",
    "Role-play": "ロールプレイ",
    "Listen to a real dialogue.": "実際の会話を聞きます。",
    "Study the key phrases and common mistakes.": "大切なフレーズとよくある間違いを学びます。",
    "Type or say each phrase from memory.": "各フレーズを記憶から打つか、声に出して言います。",
    "Use the phrases in a new conversation.": "新しい会話でフレーズを使います。",
    "⌨️ How to type Korean": "⌨️ 韓国語の入力方法",
    "- **Mac:** System Settings → Keyboard → Text Input → Edit → **+** → Korean → 2-Set Korean\n"
    "- **Windows:** Settings → Time & Language → Language → Add a language → Korean\n"
    "- **Phone:** add the Korean keyboard in your keyboard settings\n\n"
    "Romanization is only a hint. Typing real Hangul is part of the practice.":
        "- **Mac：** システム設定 → キーボード → 入力ソース → 編集 → **＋** → 韓国語 → 2ボル式\n"
        "- **Windows：** 設定 → 時刻と言語 → 言語 → 言語を追加 → 韓国語\n"
        "- **スマホ：** キーボード設定で韓国語キーボードを追加\n\n"
        "ローマ字はあくまでヒントです。本物のハングルを打つことも練習のうちです。",
    "🔬 Why this works": "🔬 なぜ効果があるのか",
    "- **Retrieval practice:** recalling a phrase builds memory far better than rereading it.\n"
    "- **Spaced repetition:** each phrase comes back after 1, 2, 4, 7, then 15 days.\n"
    "- **Chunks, not single words:** fluent speakers store whole phrases.\n"
    "- **Task-based learning:** role-plays use the phrases for a real goal.\n"
    "- **Interleaving:** daily review mixes phrases from different scenarios.":
        "- **想起練習：** 読み返すより、思い出すほうがずっと記憶に残ります。\n"
        "- **間隔反復：** 各フレーズは1日、2日、4日、7日、15日後に再び出題されます。\n"
        "- **単語ではなくかたまりで：** 流暢な話者はフレーズごと覚えています。\n"
        "- **タスク型学習：** ロールプレイで実際の目的のためにフレーズを使います。\n"
        "- **交互練習：** 毎日の復習では、いろいろなシーンのフレーズを混ぜて出題します。",
    # ---- moving around
    "🏁 Checkpoint {n}": "🏁 チェックポイント{n}",
    "Level {n} · Lesson {i} of {total}": "レベル{n} · レッスン {i}/{total}",
    "Level {n} · Checkpoint": "レベル{n} · チェックポイント",
    "← All lessons": "← レッスン一覧",
    "Previous in the course": "コースの前のレッスン",
    "Next in the course": "コースの次のレッスン",
    "🎉 That's the last lesson for now. More are coming soon!": "🎉 今あるレッスンはここまでです。今後追加予定です！",
    "Finished this lesson?": "このレッスンは終わりましたか？",
    "Next: {label}": "次：{label}",
    "Continue →": "続ける →",
    "🔀 Jump to another lesson": "🔀 ほかのレッスンへ移動",
    "Level": "レベル",
    "Lesson": "レッスン",
    # ---- lesson
    "1 · Situation": "1 · 場面",
    "2 · Notice": "2 · 気づく",
    "3 · Recall": "3 · 思い出す",
    "4 · Role-play": "4 · ロールプレイ",
    "📝 Test": "📝 テスト",
    "Show romanization": "ローマ字を表示",
    "Show English": "日本語訳を表示",
    "English": "日本語訳",
    "Type or say each phrase in Korean. Every answer goes into your review schedule.":
        "各フレーズを韓国語で打つか、声に出して言いましょう。答えはすべて復習スケジュールに入ります。",
    "All phrases are in your review queue. Try the role-play next!": "すべてのフレーズが復習リストに入りました。次はロールプレイに挑戦しましょう！",
    # ---- role-play
    "🗣️ Practice": "🗣️ 練習",
    "⏱️ Time attack": "⏱️ タイムアタック",
    "Mode": "モード",
    "Time attack: the recorder starts by itself after their line, and you have a few seconds to answer, "
    "like a real conversation.":
        "タイムアタック：相手のセリフのあと自動で録音が始まり、本物の会話のように数秒以内に答えます。",
    "Their line plays, then **you have a few seconds to answer**, no pausing. Recording starts and stops "
    "by itself. Read the task first!":
        "相手のセリフが流れたら、**数秒以内に答えましょう**。一時停止はできません。録音は自動で始まり、"
        "自動で止まります。まず課題を読んでおきましょう！",
    "A new conversation. Listen to what they say, then reply in Korean to complete the task.":
        "新しい会話です。相手の言うことを聞いて、韓国語で答えて課題をクリアしましょう。",
    "🎧 Listening practice: hide their words until you ask": "🎧 リスニング練習：相手のセリフを隠す",
    "▶ Start the conversation": "▶ 会話を始める",
    "⏰ No answer in time": "⏰ 時間内に答えがありませんでした",
    "🔊 Listen…": "🔊 聞いてください…",
    "Listen…": "聞いてください…",
    "Show their words": "セリフを見る",
    "🎯 <b>Your task:</b> {task}": "🎯 <b>課題：</b>{task}",
    "Your reply": "あなたの返事",
    "Conversation complete: {passed} / {total} replies understood.": "会話終了：{total}回中{passed}回、伝わりました。",
    " Average start: {seconds} s.": " 話し始めるまでの平均：{seconds}秒。",
    "Try again": "もう一度",
    "Show the whole conversation": "会話全体を見る",
    "Perfect conversation! 완벽해요!": "完璧な会話です！완벽해요!",
    "Great conversation!": "すばらしい会話です！",
    "Good start. Try it again!": "いいスタートです。もう一度挑戦しましょう！",
    "{passed} of {total} replies understood": "{total}回中{passed}回伝わりました",
    "average start {seconds} s": "話し始めるまで平均{seconds}秒",
    "{n} at natural pace": "自然なペース{n}回",
    "You": "あなた",
    "🔇 (nothing heard)": "🔇（聞き取れず）",
    "⏰ (no answer)": "⏰（無回答）",
    "right": "正解",
    "almost": "おしい",
    "missed": "不正解",
    "a natural answer": "自然な答え",
    "time to start speaking": "話し始めるまでの時間",
    "🎙️ Listen to your answers": "🎙️ 自分の答えを聞く",
    "🔇 No words recognized": "🔇 言葉を聞き取れませんでした",
    "A natural answer": "自然な答え",
    "Exactly right": "完璧です",
    "Almost: check the spelling": "おしい：つづりを確認",
    "Right meaning, different words": "言い方は違っても意味は正解",
    "Not quite": "ちょっと違います",
    "⚡ Started answering after {seconds} s: natural conversation pace": "⚡ {seconds}秒で話し始めました：自然な会話のペースです",
    "🕐 Started answering after {seconds} s: a little slow, keep practicing":
        "🕐 {seconds}秒で話し始めました：少しゆっくりです。練習を続けましょう",
    "🐢 Started answering after {seconds} s: try to answer sooner": "🐢 {seconds}秒で話し始めました：もう少し早く答えてみましょう",
    "⏰ Time's up: no answer heard": "⏰ 時間切れ：答えが聞こえませんでした",
    "No words recognized": "言葉を聞き取れませんでした",
    # time-attack recorder (assets/time_attack.js)
    "{seconds} s to answer": "{seconds}秒以内に答える",
    "Answer sent. Checking…": "送信しました。確認中…",
    "Microphone blocked. Allow it in the browser and try again.": "マイクがブロックされています。ブラウザで許可して、もう一度試してください。",
    "Your turn: speak now!": "あなたの番です。今、話して！",
    "Got it. Checking…": "受け取りました。確認中…",
    "Time's up!": "時間切れ！",
    "Press start. Their line plays, then you have to answer in time.": "スタートを押してください。相手のセリフのあと、時間内に答えましょう。",
    # conversation player (assets/conversation_player.html)
    "Play the whole conversation": "会話を通して再生",
    "Play conversation": "会話を再生",
    "Pause": "一時停止",
    "Repeat this line": "この行をくり返す",
    "Playback speed": "再生速度",
    # ---- tests
    "Pre-test": "事前テスト",
    "Post-test": "事後テスト",
    "Checkpoint test": "チェックポイントテスト",
    "Gain": "伸び",
    "I don't know yet →": "まだわからない →",
    "Stop the test": "テストをやめる",
    "Answers from your last test": "前回のテストの答え",
    "Answers from your last attempt": "前回の挑戦の答え",
    "Also correct: {also}": "これも正解：{also}",
    "You: {answer}": "あなた：{answer}",
    "(no answer)": "（無回答）",
    "{title} finished: {correct} / {total} phrases known.": "{title}終了：{total}フレーズ中{correct}個わかりました。",
    "Measure what this lesson teaches you. Take the **pre-test before** you start (it's fine to know nothing "
    "yet!) and the **post-test after** studying. Each test asks every phrase from its English meaning, with no "
    "hints. You see the answers at the end. Tests don't change your review schedule.":
        "このレッスンで何を身につけたかを測りましょう。始める**前に事前テスト**（まだ何も知らなくて大丈夫！）、"
        "学んだ**あとに事後テスト**を受けます。どちらも各フレーズを意味から答える形式で、ヒントはありません。"
        "答えは最後に表示されます。テストは復習スケジュールには影響しません。",
    "📝 Start the pre-test": "📝 事前テストを始める",
    "📝 Take the post-test": "📝 事後テストを受ける",
    "📝 Take the post-test again": "📝 事後テストをもう一度受ける",
    "Pre-test done. Study the lesson (Situation → Role-play), then take the post-test.":
        "事前テスト完了。レッスン（場面 → ロールプレイ）を学んでから、事後テストを受けましょう。",
    # ---- checkpoint
    "Level {n} · {title}": "レベル{n} · {title}",
    ". ": "。",
    "📝 Mixed test ({n} phrases)": "📝 総合テスト（{n}フレーズ）",
    "🗣️ Story role-play ({n} turns)": "🗣️ ストーリー・ロールプレイ（{n}ターン）",
    "🎉 {correct} / {total} ({pct}): Level {n} complete!": "🎉 {correct} / {total}（{pct}）：レベル{n}修了！",
    " Level {n} is unlocked.": " レベル{n}が解放されました。",
    "Not yet: {correct} / {total} ({pct}). You need {need}. Review: {names}, then try again.":
        "あと少し：{correct} / {total}（{pct}）。合格には{need}が必要です。{names}を復習して、もう一度挑戦しましょう。",
    "{n} phrases, {per} from each Level {level} lesson, mixed together. No hints and no feedback until the "
    "end, just like a lesson test. Score {pct} or more to complete the level. You can take it anytime, even "
    "before the lessons, to see if you can skip ahead.":
        "レベル{level}の各レッスンから{per}フレーズずつ、計{n}フレーズを混ぜて出題します。レッスンのテストと同じく、"
        "最後までヒントも採点結果も出ません。{pct}以上でレベル修了です。レッスンの前でもいつでも受けられるので、"
        "先に進めるか確かめられます。",
    "Best score": "最高点",
    "Last attempt": "前回",
    "Status": "状態",
    "Not yet": "まだ",
    "📝 Start the checkpoint test": "📝 チェックポイントテストを始める",
    "One turn from each part of the level, in a row, like a real day out. Practice it here; the story isn't "
    "scored for passing.":
        "レベルの各パートから1ターンずつ、本物のお出かけのように続けて話します。ここで練習しましょう。"
        "ストーリーは合格判定には入りません。",
    # ---- review
    "🔁 Review": "🔁 復習",
    "Nothing to review yet. Start a lesson first!": "まだ復習するものはありません。まずレッスンを始めましょう！",
    "Go to lessons": "レッスンへ",
    "Nothing due today. Come back tomorrow! 🎉": "今日の復習はありません。また明日！🎉",
    "{n} phrases due, mixed from all scenarios.": "今日の復習：{n}フレーズ（全シーンから混ぜて出題）。",
    "Review finished for today. 수고했어요!": "今日の復習は終わりです。수고했어요！",
    "Refresh due phrases": "復習フレーズを更新",
    # ---- progress
    "📈 Progress": "📈 学習の記録",
    "Learning gains": "学習の伸び",
    "Scenario": "シーン",
    "🏁 Checkpoint {n} (Level {n})": "🏁 チェックポイント{n}（レベル{n}）",
    "best {pct}": "最高 {pct}",
    "✅ passed": "✅ 合格",
    "not yet": "まだ",
    "Take a lesson's 📝 Test before and after studying to see what it taught you.":
        "学習の前後にレッスンの📝テストを受けると、何を身につけたかがわかります。",
    "No progress yet. Finish a lesson to see your stats.": "まだ記録がありません。レッスンを終えると統計が表示されます。",
    "Phrases learned": "学んだフレーズ",
    "Due today": "今日の復習",
    "Mastered (box 5)": "習得済み（ボックス5）",
    "Recall accuracy": "正答率",
    "Recall accuracy over time": "正答率の推移",
    "Practice on two or more days to see a trend. Each point is one day's share of correct answers in "
    "Recall and Review.":
        "2日以上練習すると推移が表示されます。各点は、その日の「思い出す」と「復習」での正解の割合です。",
    "Accuracy (%)": "正答率（%）",
    "% correct": "正解率（%）",
    "{days} days, {answers} answers. Spaced repetition brings back harder phrases more often, so a flat line "
    "can still mean progress.":
        "{days}日間、{answers}回答。間隔反復では難しいフレーズほど多く出題されるので、横ばいでも上達している場合があります。",
    "Phrases per box": "ボックスごとのフレーズ数",
    "Box 1 comes back tomorrow; box 5 waits 15 days.": "ボックス1は明日、ボックス5は15日後に出題されます。",
    "Phrases": "フレーズ",
    "Box {box} ({days}d)": "ボックス{box}（{days}日）",
    "Accuracy by scenario": "シーン別の正答率",
    "Answers": "回答数",
    "Accuracy": "正答率",
    "All phrases": "すべてのフレーズ",
    "Phrase": "フレーズ",
    "Box": "ボックス",
    "Next review": "次の復習",
    "Reset progress": "記録をリセット",
    "Delete all progress": "すべての記録を削除",
    # ---- team password, feedback
    "🔒 This part is for the project team.": "🔒 ここはプロジェクトチーム専用です。",
    "🔒 Team: see {what}": "🔒 チーム用：{what}",
    "the survey results": "アンケート結果を見る",
    "the Model lab": "Model labを開く",
    "That's not the password.": "パスワードが違います。",
    "Password": "パスワード",
    "Unlock": "解除",
    "💬 Feedback": "💬 フィードバック",
    "Thank you! Your answers were saved. 감사합니다! 🙏": "ありがとうございます！回答を保存しました。감사합니다! 🙏",
    "Tried a lesson or two? Please tell us what you think. It takes about 2 minutes, it's anonymous, and it "
    "helps us improve the app.":
        "レッスンを試してみましたか？ぜひ感想を教えてください。約2分・匿名で、アプリの改善に役立てます。",
    "Your Korean level": "あなたの韓国語レベル",
    "Beginner": "初級",
    "Intermediate": "中級",
    "Advanced": "上級",
    "Native speaker": "ネイティブ",
    "**Using the app** (1 = strongly disagree, 5 = strongly agree)": "**アプリの使いやすさ**（1 = まったくそう思わない、5 = とてもそう思う）",
    "**Learning**": "**学習について**",
    "I think that I would like to use this app frequently.": "このアプリを頻繁に使いたいと思う。",
    "I found the app unnecessarily complex.": "このアプリは不必要に複雑だと感じた。",
    "I thought the app was easy to use.": "このアプリは使いやすいと思った。",
    "I think that I would need the support of a technical person to be able to use this app.":
        "このアプリを使うには、技術に詳しい人のサポートが必要だと思う。",
    "I found the various functions in this app were well integrated.": "このアプリのさまざまな機能はうまくまとまっていると感じた。",
    "I thought there was too much inconsistency in this app.": "このアプリには一貫性のないところが多すぎると思った。",
    "I would imagine that most people would learn to use this app very quickly.": "ほとんどの人はこのアプリの使い方をすぐに覚えられると思う。",
    "I found the app very cumbersome to use.": "このアプリはとても使いにくいと感じた。",
    "I felt very confident using the app.": "自信を持ってこのアプリを使えた。",
    "I needed to learn a lot of things before I could get going with this app.":
        "このアプリを使い始める前に、多くのことを覚える必要があった。",
    "The scenarios are situations I really face (or will face) in Busan.": "シーンは、釜山で実際に出会う（これから出会う）場面だ。",
    "After a lesson, I feel more confident using these phrases in real life.": "レッスンのあと、実生活でこれらのフレーズを使う自信がついた。",
    "Speaking practice (Speak, Time attack) helped me more than typing alone.":
        "話す練習（話す、タイムアタック）は、打つだけの練習より役に立った。",
    "What was most useful?": "いちばん役に立ったことは？",
    "What should we improve or add?": "改善・追加してほしいことは？",
    "Send feedback": "送信する",
    "Please answer every 1-5 question (the open questions are optional).": "1〜5の質問にはすべて答えてください（自由記述は任意です）。",
    # ---- layout, sidebar
    "Home": "ホーム",
    "Review": "復習",
    "Progress": "記録",
    "Feedback": "フィードバック",
    "Checkpoint": "チェックポイント",
    "💾 Your progress is saved only in this browser, on this device": "💾 学習の記録はこのブラウザ（この端末）にだけ保存されます",
    "Your progress is stored in this browser's local storage. It stays when you refresh or come back later, "
    "but not on another device or browser, and clearing browser data deletes it.":
        "学習の記録はこのブラウザのローカルストレージに保存されます。再読み込みしても、あとで戻ってきても残りますが、"
        "ほかの端末やブラウザには引き継がれず、ブラウザのデータを消すと削除されます。",
    "💾 Progress resets when the app restarts": "💾 アプリが再起動すると記録はリセットされます",
    "Your progress is kept only on this server and is erased whenever the app restarts (after updates or "
    "long inactivity).":
        "学習の記録はこのサーバーにだけ保存され、アプリが再起動すると（更新後や長時間使われなかったとき）消えます。",
    "💾 Progress is saved on this computer": "💾 学習の記録はこのコンピューターに保存されます",
    "🚧 Class prototype, still being checked": "🚧 授業のプロトタイプ（確認中）",
    "The Korean content and voices are still being checked, so expect rough edges.":
        "韓国語の内容と音声はまだ確認中のため、粗い部分があるかもしれません。",
    "🇯🇵 Japanese is AI-translated, still being checked": "🇯🇵 日本語訳はAIによるもので、確認中です",
    "Korean for life in Busan": "釜山生活の韓国語",
    "🚧 Under construction": "🚧 制作中",
    "to review": "復習",
    "learned": "学習済み",
    "mastered": "習得",
    "Phrases your review schedule brings back today. Each correct answer pushes a phrase further away (1, 2, "
    "4, 7, then 15 days); a wrong one brings it back tomorrow. Click to review.":
        "今日の復習スケジュールに入っているフレーズです。正解するたびに次の出題が先になり（1、2、4、7、15日）、"
        "間違えると明日また出題されます。クリックして復習しましょう。",
    "Phrases you have practiced at least once": "1回以上練習したフレーズ",
    "Phrases in the last box: you got them right 4 times in a row, spread over weeks":
        "最後のボックスにあるフレーズ：数週間かけて4回連続で正解しました",
    "Practice settings": "練習の設定",
    "Answer by": "答え方",
    "🎙️ Speak": "🎙️ 話す",
    "⌨️ Type": "⌨️ 打つ",
    "Speak uses the microphone and a speech-recognition model, chosen below.": "「話す」はマイクと音声認識モデルを使います。",
    "Speech model": "音声認識モデル",
    "Compare them side by side on the 🔬 Model lab page.": "🔬 Model labで並べて比べられます。",
    "About this model": "このモデルについて",
    "🤖 AI meaning check": "🤖 AI意味チェック",
    "Accept answers with different words but the same meaning (Hugging Face model {model}).":
        "言い方が違っても意味が同じ答えを正解にします（Hugging Faceのモデル {model}）。",
    "Signed in as **{name}**": "**{name}** でログイン中",
    "Sign out": "ログアウト",
    "Made at BUFS for international students in Busan": "釜山外大で、釜山の留学生のために制作",
    "AI project prototype · v0.1": "AIプロジェクト試作版 · v0.1",
    "🌐 Language": "🌐 言語",
    # ---- icon steps (short labels; the full sentence is behind ⓘ)
    "More": "詳しく",
    "See the meaning": "意味を見る",
    "Say it in Korean": "韓国語で言う",
    "It comes back to review": "あとで復習に出る",
    "Read the task": "課題を読む",
    "Listen": "聞く",
    "Answer within seconds": "数秒以内に答える",
    "Reply in Korean": "韓国語で返事",
    "Complete the task": "課題をクリア",
    "Study": "学ぶ",
    "See your gain": "伸びを見る",
    "Mixed": "ランダム出題",
    "No hints": "ヒントなし",
    "{pct} to pass": "{pct}で合格",
    "One turn per lesson": "各レッスンから1ターン",
    "Practice, not scored": "練習（採点なし）",
    # ---- noisy surroundings
    "🔊 **Noisy surroundings detected.** The AI may mishear some words. A quieter spot, or holding the microphone "
    "closer, will help.":
        "🔊 **周りがうるさいようです。** AIが一部の言葉を聞き間違えるかもしれません。静かな場所に移るか、"
        "マイクを口に近づけると改善します。",
    "🔊 **Very noisy surroundings.** The background is almost as loud as your voice, so the AI will probably "
    "mishear you. Try a quieter spot, hold the microphone closer, or switch to ⌨️ Type in the sidebar.":
        "🔊 **周りがとてもうるさいです。** 周りの音があなたの声とほぼ同じ大きさなので、AIが聞き間違える可能性が"
        "高いです。静かな場所に移るか、マイクを近づけるか、サイドバーで「⌨️ 打つ」に切り替えてください。",
    "Hide until the noise changes": "周りの音が変わるまで非表示",
    "🔊 Noisy surroundings": "🔊 周りがうるさいようです",
    "⌨️ Switch to typing": "⌨️ 打つに切り替える",
    "Keep speaking": "このまま話す",
    "Noisy surroundings: the AI may mishear you.": "周りがうるさいため、AIが聞き間違えるかもしれません。",
    "I couldn't hear your words over the background noise. Try a quieter spot, or hold the microphone closer.":
        "周りの音で、あなたの言葉が聞き取れませんでした。静かな場所に移るか、マイクを口に近づけてください。",
    "🔊 It was noisy where you recorded, so the AI may have misheard you.": "🔊 録音した場所がうるさかったので、AIが聞き間違えたかもしれません。",
    # onboarding tour
    "👋 Welcome to Vocab Coach": "👋 Vocab Coachへようこそ",
    "Learn the Korean you need in Busan, one real situation at a time. Here's a 1-minute tour of how it works.":
        "釜山で本当に使う韓国語を、実際の場面ごとに学びます。使い方を1分でご案内します。",
    "Real situations, not word lists": "単語リストではなく、実際の場面",
    "Each lesson is a place you'll really go: a café, the metro, a pharmacy. You learn the <b>whole phrases</b> people use there.":
        "各レッスンは、カフェ、地下鉄、薬局など、実際に行く場所です。そこで使われる<b>フレーズ丸ごと</b>を学びます。",
    "Every lesson, step by step": "レッスンの流れ",
    "<b>1 Situation:</b> listen to a real conversation. <b>2 Notice:</b> study the phrases. "
    "<b>3 Recall:</b> say them from memory. <b>4 Role-play:</b> use them in a new conversation. "
    "A short 📝 test before and after shows what you learned.":
        "<b>1 場面：</b>実際の会話を聞く。<b>2 気づく：</b>フレーズを学ぶ。<b>3 思い出す：</b>何も見ずに言う。"
        "<b>4 ロールプレイ：</b>新しい会話で使う。学習の前後の短い📝テストで、どれだけ身についたかが分かります。",
    "Start here": "ここから始めましょう",
    "Lessons go from easy to harder. Begin with {lesson}, then work along Level 1.":
        "レッスンはやさしい順に並んでいます。{lesson}から始めて、レベル1を順に進みましょう。",
    "🏁 The checkpoint": "🏁 チェックポイント",
    "After Level 1, a mixed test checks you're ready for Level 2. Already know some Korean? Try it first: it works as a placement test.":
        "レベル1の後は、まとめテストでレベル2に進む準備ができたか確認します。韓国語を少し知っている人は、"
        "先に受けてみてください。レベル分けテストとしても使えます。",
    "Come back every day": "毎日少しずつ",
    "<b>🔁 Review</b> brings phrases back just before you'd forget them. <b>📈 Progress</b> shows how far you've come.":
        "<b>🔁 復習</b>は、忘れかけたころにフレーズをもう一度出します。<b>📈 記録</b>で、どこまで進んだかが分かります。",
    "Your phrases at a glance": "フレーズの状況がひと目で",
    "How many phrases are due for review today, how many you've learned, and how many you've mastered.":
        "今日復習するフレーズの数、学んだ数、マスターした数が表示されます。",
    "Speak or type": "話す、または打つ",
    "Answer with your <b>🎙️ voice</b> (allow the microphone) or <b>⌨️ type</b>. Speaking works best somewhere quiet.":
        "<b>🎙️ 声</b>（マイクを許可してください）か<b>⌨️ キーボード</b>で答えます。話すときは静かな場所がおすすめです。",
    "English or 日本語": "English または 日本語",
    "Switch the app's language here anytime. The Korean stays the same.":
        "アプリの言語はここでいつでも切り替えられます。韓国語はそのままです。",
    "You're ready! 🎉": "準備完了！🎉",
    "Your progress is saved in this browser. You can replay this tour anytime from the sidebar.":
        "学習記録はこのブラウザに保存されます。このツアーはサイドバーからいつでも見直せます。",
    "Next →": "次へ →",
    "← Back": "← 戻る",
    "Skip tour": "ツアーをスキップ",
    "Close": "閉じる",
    "Start {lesson} →": "{lesson}を始める →",
    "Step {n} of {total}": "{n} / {total}",
    "🧭 Take the tour": "🧭 使い方ツアー",
    "📖 Inside a lesson": "📖 レッスンの中身",
    "Every lesson has the same five parts. Let's look at each one.": "どのレッスンも同じ5つのパートでできています。順番に見てみましょう。",
    "The situation": "場面",
    "Where you are and what happens. Everything in this lesson is for this one real situation.":
        "どこにいて、何が起きるか。このレッスンの内容はすべて、この実際の場面のためのものです。",
    "Listen to the whole conversation. Tap any line to hear it again, slow it down, "
    "or hide the romanization and English when you're ready.":
        "会話全体を聞きます。どの行もタップすればもう一度聞けて、速度を落とすこともできます。"
        "慣れたらローマ字と訳を隠しましょう。",
    "The key phrases, one card each: the sound, the meaning, how polite it is, and a common mistake to avoid.":
        "大事なフレーズを1枚ずつのカードで。音声、意味、丁寧さ、よくある間違いが分かります。",
    "See the meaning, then <b>say or type the Korean</b> from memory. Getting it right moves it into your review schedule.":
        "意味を見て、何も見ずに<b>韓国語を話すか打ちます</b>。正解すると復習スケジュールに入ります。",
    "A new conversation in the same place. <b>🗣️ Practice</b> at your own pace, or try <b>⏱️ Time attack</b>: "
    "answer in a few seconds, like a real chat.":
        "同じ場所での新しい会話です。<b>🗣️ 練習</b>で自分のペースで、または<b>⏱️ タイムアタック</b>で"
        "本当の会話のように数秒で答えましょう。",
    "Take it before you study and again after. The 📈 Progress page shows how much you learned.":
        "学習の前と後に受けます。📈 記録ページで、どれだけ身についたかが分かります。",
    "Moving on": "次へ進む",
    "Go to the previous or next lesson here, or back to all lessons.": "ここから前後のレッスンや、レッスン一覧に移動できます。",
    "Your turn! 🎧": "さあ、始めましょう！🎧",
    "Start with <b>1 · Situation</b> and listen to the conversation.": "まず<b>1 · 場面</b>で会話を聞いてみましょう。",
    "Let's go →": "始める →",
    "Switch to light mode": "ライトモードに切り替え",
    "Switch to dark mode": "ダークモードに切り替え",
    # short versions for phones
    "🚧 Prototype": "🚧 試作版",
    "🇯🇵 AI-translated": "🇯🇵 AI翻訳",
    "💾 Saved in this browser": "💾 このブラウザに保存",
    "💾 Resets on restart": "💾 再起動でリセット",
    "💾 Saved on this computer": "💾 このPCに保存",
    "Real Korean for real situations in Busan.": "釜山の場面で使う、本物の韓国語。",
}
