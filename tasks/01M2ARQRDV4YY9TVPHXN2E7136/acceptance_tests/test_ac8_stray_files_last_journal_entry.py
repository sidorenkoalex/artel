"""AC-8 (tasks/01M2ARQRDV4YY9TVPHXN2E7136/SPEC.md): пока запись журнала
«посторонние файлы в каталоге планки» остаётся ПОСЛЕДНЕЙ записью с момента
входа задачи в текущий визит состояния `tests_writing`, выход
`fsm_advance.tests_writing` отклоняет переход текстом «планка ссылается на
отброшенные файлы: <список>».

Песочница — `tests.sandbox.LightTransitionSandbox`, тем же приёмом, что
`test_ac4_ac5_tests_writing_dry_collect.py` рядом: собственный SPEC/планка
на диске, без копирования патчей песочницы.

Красен до реализации: гейт, читающий последнюю запись журнала визита
`tests_writing` и сверяющий её с «посторонние файлы в каталоге планки», в
`fsm_advance.tests_writing` ещё не добавлен (требование 3 SPEC) — сегодня
трассируемость AC и (будущий) сухой сбор проходят на полностью валидной
планке этого сценария, и переход уходит в `in_dev`, а не остаётся в
`tests_writing` с текстом «планка ссылается на отброшенные файлы».
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import fsm, store  # noqa: E402
from tests.sandbox import LightTransitionSandbox  # noqa: E402

SPEC_ONE_AC = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: планка визита состояния

## Критерии приёмки

AC-1. Единственный критерий, покрытый тестом.
"""

PASSING_TEST = '''"""Зелёный с рождения: фикстура планки-сценария этого файла, не планка
реальной задачи — проверяет только прохождение гейта tests_writing."""
import unittest


class PlankTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)
'''


class Ac8StrayLastEntrySandbox(LightTransitionSandbox):

    def enter_tests_writing(self) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "SPEC.md").write_text(
            SPEC_ONE_AC.format(task=self.TASK), encoding="utf-8")
        self.set_state("tests_writing")

    def write_valid_plank(self) -> None:
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_ac.py").write_text(PASSING_TEST, encoding="utf-8")

    def journal_stray_files(self, names: list[str]) -> None:
        store.journal(
            store.db(), self.TASK, "orchestrator",
            "посторонние файлы в каталоге планки",
            f"в каталоге планки посторонние файлы: {', '.join(names)}")


class StrayFilesBlockTheTransitionTest(Ac8StrayLastEntrySandbox):

    def test_ac8_stray_files_as_the_last_entry_block_the_transition(self):
        """Планка полностью валидна (трассируемость AC пройдена), но
        последняя запись журнала визита `tests_writing` — «посторонние
        файлы в каталоге планки» (checkpoint отбросил файлы этого же шага
        test_author) — переход отклонён, задача остаётся в `tests_writing`,
        текст отказа называет отброшенные файлы поимённо.

        Ловит мутацию: гейт AC-8 не читает журнал вовсе (либо читает, но не
        трактует эту запись как отказ) — переход прошёл бы в `in_dev`
        несмотря на файлы, отброшенные автокоммитом этого же шага."""
        self.enter_tests_writing()
        self.write_valid_plank()
        self.journal_stray_files(["fixtures.json", "helpers/util.py"])

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "tests_writing")
        self.assertIn("планка ссылается на отброшенные файлы", out)
        self.assertIn("fixtures.json", out)
        self.assertIn("helpers/util.py", out)

    def test_ac8_superseded_stray_entry_no_longer_blocks(self):
        """Та же запись «посторонние файлы...», но НЕ последняя — за ней
        следует более поздняя активность визита (например, повторный шаг
        роли после починки) — переход больше не блокируется этой записью
        и идёт штатным путём.

        Ловит мутацию: гейт ищет «была ли КОГДА-ЛИБО хоть одна такая
        запись с начала визита» вместо «остаётся ли она ПОСЛЕДНЕЙ» — тогда
        устаревшая, уже замещённая запись продолжала бы блокировать переход
        бесконечно, даже после того как test_author закрыл вопрос."""
        self.enter_tests_writing()
        self.write_valid_plank()
        self.journal_stray_files(["fixtures.json"])
        store.journal(store.db(), self.TASK, "operator", "заметка Оператора",
                      "файл поправлен, шаг test_author повторён")

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "in_dev")


if __name__ == "__main__":
    unittest.main()
