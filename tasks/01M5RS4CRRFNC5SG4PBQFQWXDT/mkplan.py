"""Временная сборка PLAN.md: текст plan_body.txt + таблицы копий (удаляется)."""
import re
from pathlib import Path

DOCS = Path(__file__).resolve().parent
body = (DOCS / "plan_body.txt").read_text(encoding="utf-8")


def table(match):
    text = (DOCS / f"mutation-run-{match.group(1)}.tsv").read_text(encoding="utf-8")
    return "```\n" + text.rstrip("\n") + "\n```"


(DOCS / "PLAN.md").write_text(re.sub(r"@@TABLE (\d+)@@", table, body), encoding="utf-8")
