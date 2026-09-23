"""Hand-authored 30-day curriculum fixture for examples/coach/answers.json."""

from __future__ import annotations

import json
from pathlib import Path

from afterthought.coach.interview import Profile, answers_from_file
from afterthought.coach.plan import build_request

ROOT = Path(__file__).resolve().parents[1]
ANSWERS = ROOT / "examples" / "coach" / "answers.json"
OUT = ROOT / "examples" / "chatgpt-export" / "fixtures"
MODEL = "hand-authored fixture"

S = {
    "redact": "redact before sharing",
    "summ": "summarise a document",
    "verify": "verify a claim against the source",
    "extract": "structured extraction",
    "draft": "draft then edit",
    "compare": "compare two versions",
    "prompt": "write a reusable prompt",
    "review": "review model output critically",
}
ITEMS = [
    (
        1,
        "Take one old, non-confidential precedent agreement and strip every party name, date and figure by hand. Save it as your practice document.",
        S["redact"],
        "You cannot practise on client material, so make a safe copy first.",
    ),
    (
        2,
        "Ask the assistant for a one-paragraph summary of the practice document. Then read the summary against the document and mark every sentence true or false.",
        S["summ"],
        "Your first summary invented a clause; this time you check it.",
    ),
    (
        3,
        "Ask for the summary again but tell the model to quote the clause number for every statement. Check each quote exists.",
        S["verify"],
        "Forcing citations makes invented clauses easy to catch.",
    ),
    (
        4,
        "Ask the assistant to list every defined term in the practice document as a two-column table: term, clause where defined.",
        S["extract"],
        "Tables are easier to check than prose.",
    ),
    (
        5,
        "Write down, in one paragraph, the three things you always look for in a supply agreement redline. Save it as your standard position note.",
        S["prompt"],
        "The model needs your standard position in writing before it can compare against it.",
    ),
    (
        6,
        "Give the model your standard position note and the practice document. Ask which of the three points the document meets and which clause proves it.",
        S["verify"],
        "A first small version of the deviation review.",
    ),
    (
        7,
        "Ask the assistant to draft a three-sentence client email explaining one clause in plain language. Edit it until you would send it.",
        S["draft"],
        "Drafting to edit rather than from scratch is the habit you want.",
    ),
    (
        8,
        "Make a second copy of the practice document and change five clauses by hand. Ask the model to list the differences between the two copies.",
        S["compare"],
        "This is the redline comparison, on material you control.",
    ),
    (
        9,
        "Check the model's difference list against your five changes. Note what it missed and what it invented.",
        S["review"],
        "Knowing the failure modes is what makes the tool usable.",
    ),
    (
        10,
        "Ask for the difference list again as a table: clause, our wording, their wording, significance (high, medium, low). Check the significance column.",
        S["extract"],
        "The deviation table is the artefact you want at the end.",
    ),
    (
        11,
        "Write a reusable prompt that produces the deviation table from any two documents. Save it in your notes.",
        S["prompt"],
        "A saved prompt turns a good result into a repeatable one.",
    ),
    (
        12,
        "Ask the model to explain one clause of the practice document to a non-lawyer in five sentences. Check every sentence against the clause.",
        S["summ"],
        "Plain-language explanation is most of an advice note.",
    ),
    (
        13,
        "Redact a real, closed matter's agreement using find and replace for names, dates and figures. Check it twice before it leaves your machine.",
        S["redact"],
        "A real document, made safe, gives realistic practice.",
    ),
    (
        14,
        "Run your saved deviation prompt on the redacted real agreement against your standard position note. Check every row.",
        S["verify"],
        "First real run of the workflow, on safe material.",
    ),
    (
        15,
        "Ask the assistant to draft a short advice note from the checked deviation table. Edit it to your standard.",
        S["draft"],
        "Table in, note out: the second half of your goal.",
    ),
    (
        16,
        "Time yourself: redact, run the deviation prompt, check, draft the note. Write down how long each step took.",
        S["review"],
        "You cannot improve the hour without measuring it.",
    ),
    (
        17,
        "Ask the model to list the questions it would need answered before it could assess a clause it flagged. Answer them yourself.",
        S["review"],
        "Good questions from the model show where it is guessing.",
    ),
    (
        18,
        "Ask for a fee estimate structure for a redline review as an Excel-ready table: task, hours, rate. Adjust the hours to reality.",
        S["extract"],
        "Estimates are structured extraction too.",
    ),
    (
        19,
        "Take a scanned PDF from a closed matter, redact it, and ask the assistant to transcribe one page. Compare against the scan.",
        S["verify"],
        "Scans are where transcription errors hide.",
    ),
    (
        20,
        "Ask the model to translate one redacted clause from Chinese to English and back. Note what changed in meaning.",
        S["review"],
        "Round-trip translation exposes drift.",
    ),
    (
        21,
        "Give the model two versions of your own standard position note and ask which is clearer and why. Pick one.",
        S["compare"],
        "Your own writing benefits from the same comparison.",
    ),
    (
        22,
        "Write a prompt that drafts an advice note from a deviation table in your house style. Include two example paragraphs of your real writing (redacted).",
        S["prompt"],
        "Examples of your voice beat descriptions of it.",
    ),
    (
        23,
        "Run the full workflow on a second redacted closed matter. Time it again and compare with day 16.",
        S["review"],
        "Second measurement shows whether the saved prompts help.",
    ),
    (
        24,
        "Ask the assistant to find every clause in the redacted agreement that references another clause, and check the references resolve.",
        S["verify"],
        "Cross-reference checking is tedious for people and cheap for models.",
    ),
    (
        25,
        "Draft a one-page internal note on how you now review redlines with AI, including what you never paste in. Edit until a colleague could follow it.",
        S["draft"],
        "Writing the process down protects confidentiality and spreads the skill.",
    ),
    (
        26,
        "Ask the model to critique your internal note as a sceptical senior partner would. Address two of its points.",
        S["review"],
        "Adversarial review is one of the best uses of the tool.",
    ),
    (
        27,
        "Build a checklist of the model's failure modes you have seen this month: invented clauses, missed changes, wrong significance. Keep it next to your prompts.",
        S["review"],
        "A failure checklist is your quality control.",
    ),
    (
        28,
        "Run the deviation prompt with the checklist appended, telling the model to flag anything it is unsure about. See whether the flags are useful.",
        S["prompt"],
        "Asking for uncertainty gets you fewer confident errors.",
    ),
    (
        29,
        "On a redacted matter, produce the deviation table and advice note end to end, checking each row against the source before drafting.",
        S["verify"],
        "Dress rehearsal for the real thing.",
    ),
    (
        30,
        "Write a short review: what the workflow now takes in minutes, which steps still need your judgement, and what you will try next month.",
        S["draft"],
        "Reflection turns 30 days of tasks into a habit.",
    ),
]


def main() -> None:
    profile = Profile(name="Siyu", answers=answers_from_file(ANSWERS))
    req = build_request(profile, 30)
    p = OUT / req.task / f"{req.key}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    items = [{"day": d, "task": t, "skill": s, "why": w} for d, t, s, w in ITEMS]
    p.write_text(
        json.dumps(
            {"task": req.task, "key": req.key, "model": MODEL, "response": {"items": items}},
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )
    print("wrote", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
