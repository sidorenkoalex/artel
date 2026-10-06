"""AC-4 — приложение PLAN к `tests/test_invariants.py` применяется и снимает паузу повтора в `FsmTest` (или в каждом из трёх медленных наследников).

Проверка статическая (решение Оператора 06.10): `tests/test_invariants.py`
с наложенным приложением не исполняется. PLAN.md читается из ссылки
документов помощником пульта (`_pult.artifact_text`), приложения разбирает
тот же `guard.plan_appendices`, что гейт применимости и мерж; применимость —
`_pult.apply_check` к дереву HEAD рабочей копии (либо приложение уже
наложено в HEAD подтяжкой main — тогда обратная проверка, «до» — HEAD с
обратно снятым приложением). Разбор: текст файла после наложения
разбирается `ast`, строки, добавленные приложением, берутся из его хунков;
паузу снимает добавленный вызов внутри класса, в тексте которого есть
`sleep`/`backoff`/`pause`/`time` (подмена сна `patch_pult_sleep`/
`patch_sleep(runner, …)`, своя обёртка песочницы или подмена значения
паузы).

Группа: разовый
Красен до реализации: PLAN.md задачи ещё не написан (его пишет developer после этого шага) — `artifact_text("PLAN.md")` возвращает `None`, приложения к `tests/test_invariants.py` нет.
"""
import ast
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import CODE_ROOT, apply_check, artifact_text  # noqa: E402

if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from scripts import guard  # noqa: E402

INVARIANTS_REL = "tests/test_invariants.py"
BASE_CLASS = "FsmTest"
SLOW_CLASSES = ("MergeOnlyFromMergeGateTest", "AgentRunsOnlyFromRunTest",
                "FreshVerdictGuardsAcceptanceTest")
PAUSE_WORDS = re.compile(r"sleep|backoff|pause|\btime\b", re.IGNORECASE)
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def head_text() -> str:
    res = subprocess.run(["git", "-C", str(CODE_ROOT), "show",
                          f"HEAD:{INVARIANTS_REL}"],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise AssertionError(f"{INVARIANTS_REL} в HEAD не прочитан: {res.stderr}")
    return res.stdout


def apply_in_tmp(diff: str, text: str, reverse: bool) -> str | None:
    """Текст файла после `git apply` (или `-R`) приложения к `text` во
    временном репозитории; `None` — git отказал."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        subprocess.run(["git", "init", "-q", str(repo)], check=True,
                       capture_output=True)
        path = repo / INVARIANTS_REL
        path.parent.mkdir(parents=True)
        path.write_text(text, encoding="utf-8")
        patch = repo / "appendix.diff"
        patch.write_text(diff, encoding="utf-8")
        args = ["git", "-C", str(repo), "apply"] + (["-R"] if reverse else [])
        res = subprocess.run(args + [str(patch)], capture_output=True, text=True)
        if res.returncode != 0:
            return None
        return path.read_text(encoding="utf-8")


def added_lines(diff: str) -> set[int]:
    """Номера строк файла `tests/test_invariants.py` ПОСЛЕ наложения,
    которые приложение добавило (строки `+` его хунков)."""
    added: set[int] = set()
    in_file = False
    line_no = 0
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            in_file = line.endswith(f" b/{INVARIANTS_REL}")
            continue
        if not in_file or line.startswith(("+++", "---")):
            continue
        hunk = HUNK.match(line)
        if hunk:
            line_no = int(hunk.group(1))
            continue
        if line.startswith("+"):
            added.add(line_no)
            line_no += 1
        elif line.startswith(" "):
            line_no += 1
    return added


def pause_calls_added(after: str, added: set[int]) -> dict[str, list[str]]:
    """Класс → добавленные приложением вызовы в его теле, текст которых
    говорит о сне/паузе повтора."""
    found: dict[str, list[str]] = {}
    for node in ast.walk(ast.parse(after)):
        if not isinstance(node, ast.ClassDef):
            continue
        calls = []
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            span = set(range(sub.lineno, (sub.end_lineno or sub.lineno) + 1))
            text = ast.unparse(sub)
            if span & added and PAUSE_WORDS.search(text):
                calls.append(text)
        found[node.name] = calls
    return found


class InvariantsAppendixTest(unittest.TestCase):

    def appendix(self):
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "PLAN.md задачи нет в ссылке документов")
        appendices, errors = guard.plan_appendices(plan)
        self.assertEqual(errors, [], f"приложения PLAN не разобраны: {errors}")
        found = [a for a in appendices if INVARIANTS_REL in a.paths]
        self.assertEqual(len(found), 1,
                         f"приложений к {INVARIANTS_REL} не одно: "
                         f"{[a.paths for a in appendices]}")
        return found[0]

    def test_ac4_appendix_applies_and_removes_retry_pause_in_fsm_tests(self):
        """Приложение к `tests/test_invariants.py` применяется к ветке и добавляет снятие паузы повтора в `FsmTest` либо в каждый из трёх медленных классов.

        Сценарий: из PLAN.md берётся единственное приложение к
        `tests/test_invariants.py`; (а) `git apply --check` к HEAD
        проходит — либо приложение уже наложено в HEAD (обратная
        проверка проходит); (б) в тексте после наложения добавленные
        приложением вызовы о сне/паузе стоят в теле `FsmTest`, а если не
        там — то в теле каждого из `MergeOnlyFromMergeGateTest`,
        `AgentRunsOnlyFromRunTest`, `FreshVerdictGuardsAcceptanceTest`.

        Ловит мутацию: дифф собран руками с числом строк в хедере хунка, не
        совпадающим с телом хунка, — `git apply --check` отказывает; подмена сна добавлена
        только в `MergeOnlyFromMergeGateTest` и `AgentRunsOnlyFromRunTest`,
        а `FreshVerdictGuardsAcceptanceTest` забыт — у него нет
        добавленного вызова; приложение лишь переписывает комментарии —
        добавленных вызовов нет ни в одном классе.
        """
        appendix = self.appendix()
        head = head_text()
        answer = apply_check(appendix.diff)
        if answer == "":
            after = apply_in_tmp(appendix.diff, head, reverse=False)
            self.assertIsNotNone(after, "git apply приложения к HEAD отказал")
        else:
            reverse_answer = apply_check(appendix.diff, reverse=True)
            self.assertEqual(reverse_answer, "",
                             f"приложение к {INVARIANTS_REL} не применяется к "
                             f"HEAD ({answer}) и не наложено в нём "
                             f"({reverse_answer})")
            after = head

        calls = pause_calls_added(after, added_lines(appendix.diff))
        if calls.get(BASE_CLASS):
            return
        missing = [name for name in SLOW_CLASSES if not calls.get(name)]
        self.assertEqual(missing, [],
                         f"приложение не снимает паузу повтора ни в "
                         f"{BASE_CLASS}, ни в классах {missing}; добавленные "
                         f"вызовы о сне по классам: "
                         f"{ {k: v for k, v in calls.items() if v} }")


if __name__ == "__main__":
    unittest.main()
