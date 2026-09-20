"""AC-8 (tasks/01M2XJKKPHM5XDAE42838AMBQH/SPEC.md): `python3
scripts/guard.py --all` — режим CI «Валидация артефактов» по всему
`tasks/` — остаётся зелёным на дереве, где есть исторические планки,
читающие артефакты с диска: новая проверка не вызывается ни из
`check()`, ни из `main()`.

Зелёный с рождения: сегодня проверки нет вовсе, и `--all` зелен. Тест
не «подтверждает приезд», а держит требование 4 SPEC после
реализации: он падает ровно в том случае, ради которого написан —
когда новую проверку подключили к общему прогону guard, и исторические
планки, которые SPEC запрещает переписывать, покрасили бы CI на main.
Предусловие «такие планки в дереве есть» проверяется здесь же, чтобы
тест не стал вырожденно зелёным на дереве без них.
"""
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

TASK_ID = "01M2XJKKPHM5XDAE42838AMBQH"

ARTIFACT_NAMES = ("PLAN.md", "SPEC.md", "REVIEW.md", "TZ.md",
                  "QUESTIONS.md", "TEST_REPORT.md", "ANSWER-")
# Признаки выражения доступа к файловой системе из требования 1 SPEC:
# `Path(…)` и операции `/` с ним (в тексте строки — ` / "…"`), `open(`,
# `.read_text(`, `os.path.join`, `os.path.exists`.
FS_ACCESS_MARKERS = ("Path(", "open(", ".read_text(", ".joinpath(",
                     "os.path.join", "os.path.exists", " / ")

_QUOTED_ARTIFACT = re.compile(
    "|".join(f'"[^"]*{re.escape(name)}[^"]*"' for name in ARTIFACT_NAMES))


def historical_disk_reading_planks() -> list[str]:
    """Файлы исторических планок (все задачи, кроме этой), где имя
    артефакта стоит строковым литералом на одной строке с признаком
    доступа к файловой системе — то есть ровно те, на которых новая
    проверка обязана была бы ругаться, попади она в `--all`."""
    found = []
    tasks_root = REPO_ROOT / "tasks"
    for path in sorted(tasks_root.glob("*/acceptance_tests/**/*.py")):
        # Каталог задачи — ПЕРВЫЙ сегмент относительно `tasks/`, не
        # «id встречается где-нибудь в пути»: рабочая копия шага сама
        # лежит в `.artel/worktrees/<id>/`, и наивная проверка по
        # `path.parts` отсеяла бы вообще все планки дерева.
        if path.relative_to(tasks_root).parts[0] == TASK_ID:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line in text.splitlines():
            if _QUOTED_ARTIFACT.search(line) and any(
                    marker in line for marker in FS_ACCESS_MARKERS):
                found.append(str(path.relative_to(REPO_ROOT)))
                break
    return found


class GuardAllStaysGreenTest(unittest.TestCase):

    def test_ac8_guard_all_is_green_on_historical_planks(self):
        """В дереве есть исторические планки, читающие артефакты задачи с
        диска, и `scripts/guard.py --all` по всему `tasks/` при этом
        завершается нулевым кодом возврата.

        Ловит мутацию: новая проверка добавлена в общий список
        `check()`/`main()` (самый естественный для guard приём — рядом с
        `scan_redness_markers`/`scan_indented_ac_markers`) — прогон
        `--all` найдёт нарушения в исторических планках, вернёт
        ненулевой код, и CI «Валидация артефактов» покраснеет на main,
        хотя SPEC прямо запрещает и переписывание истории, и такой
        вызов.
        """
        planks = historical_disk_reading_planks()
        self.assertTrue(
            planks,
            "в дереве не нашлось ни одной исторической планки с чтением "
            "артефакта с диска — предусловие AC-8 не воспроизводится")

        result = subprocess.run(
            [sys.executable, "scripts/guard.py", "--all"],
            cwd=REPO_ROOT, capture_output=True, text=True)

        self.assertEqual(
            0, result.returncode,
            f"guard --all покраснел (исторические планки с чтением с "
            f"диска: {planks[:5]}…):\n{result.stdout}\n{result.stderr}")


# AC-10: ci — критерий буквально про существующий набор `tests/`
# («Прогон python3 -m pytest tests/ зелёный; в частности
# tests/test_guard_*.py, tests/test_acceptance_collect.py,
# tests/test_fsm_advance_tests_writing_dry_collect.py»): его исполняет
# зелёный CI кодовой ветки задачи и прогон полного набора автогейтом
# приёмки (orchestrator/fsm_autogate.py: `acceptance.run_full_suite`), а
# не отдельный ассерт планки — skills/test-authoring.md прямо запрещает
# роли гонять полный `tests/` внутри шага, и таймаут раннера планки (120
# с на тест) для него не рассчитан.


if __name__ == "__main__":
    unittest.main()
