"""Счёт вызовов git до и после правки в PLAN задачи (AC-11).

Группа: разовый

Красен до реализации: PLAN.md задачи ещё не написан разработчиком — `artifact_text("PLAN.md")` возвращает `None`.

Источник — PLAN.md из ссылки документов задачи (`_pult.artifact_text`).
Тест проверяет наличие раздела со счётом, не верность чисел: сами числа
снимаются шпионом во временной копии и сверяются ревью.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import artifact_text  # noqa: E402

PROBE = "Ac5ProofMismatchTest"
COMMANDS = ("git remote", "git push", "git ls-remote")


def sections(text: str) -> list:
    """Разделы markdown: заголовок `#…` со всем текстом до следующего."""
    parts = re.split(r"(?m)^(?=#{1,6} )", text)
    return [p for p in parts if p.strip()]


def test_ac11_plan_has_git_call_counts_before_and_after():
    """В PLAN есть раздел со счётом вызовов на тесте `Ac5ProofMismatchTest`.

    Один раздел PLAN.md называет тест замера (`Ac5ProofMismatchTest` либо
    его наследника словом «наследник»), все три команды `git remote`,
    `git push`, `git ls-remote`, слова «до» и «после» и несёт не меньше
    шести чисел (три команды × до/после).

    Ловит мутацию: PLAN без счёта вызовов или со счётом только «после» /
    без `ls-remote` — ни один раздел не несёт всех признаков.
    """
    plan = artifact_text("PLAN.md")
    assert plan is not None, "PLAN.md нет в ссылке документов задачи"

    def complete(section: str) -> bool:
        low = section.lower()
        return ((PROBE in section or "наследник" in low)
                and all(cmd in section for cmd in COMMANDS)
                and re.search(r"(?<!\w)до(?!\w)", low) is not None
                and "после" in low
                and len(re.findall(r"(?<![\w.])\d+(?![\w.])", section)) >= 6)

    assert any(complete(s) for s in sections(plan)), (
        "ни один раздел PLAN.md не несёт счёта вызовов git remote / git push / "
        f"git ls-remote до и после правки на {PROBE}")
