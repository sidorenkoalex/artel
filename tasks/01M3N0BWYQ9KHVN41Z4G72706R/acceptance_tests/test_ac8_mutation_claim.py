"""AC-8 — «Ловит мутацию: …» у каждого тестового метода долгоживущего
файла на выходе из `tests_writing`; «Зелёный с рождения: …» её не заменяет;
разовый файл на этом переходе заявки не требует.

Группа: разовый
Красен до реализации: заявку мутации выход из `tests_writing` сейчас не проверяет — долгоживущий файл с методом без неё уходит в `in_dev`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402

METHOD = "test_ac1_fixture_criterion"


class MutationClaimTest(_sandbox.GroupPlankSandbox):

    def test_ac8_long_lived_method_without_claim_refuses(self):
        """Долгоживущий файл, чей метод `test_ac1_fixture_criterion` не
        несёт «Ловит мутацию» в докстринге, — отказ перехода; запись
        отказа называет и файл, и метод.

        Ловит мутацию: проверку заявки подключили к выходу из
        `tests_writing`, но передают в `guard.
        test_functions_without_mutation_claim` одинаковые base и head
        (как для неизменённого файла `tests/`) — функция не видит «новых»
        методов, переход уходит в `in_dev`.
        """
        self.assert_refused_naming(
            {"test_claimless.py": _sandbox.plank_source(claim=None)},
            "test_claimless.py", METHOD, why="метод без «Ловит мутацию»")

    def test_ac8_green_since_birth_does_not_replace_claim(self):
        """Метод долгоживущего файла, чей докстринг несёт только
        «Зелёный с рождения: …», — тоже отказ с файлом и методом.

        Ловит мутацию: разработчик принял «Зелёный с рождения» как
        законную замену заявки (так, как её принимает планка по
        skills/test-authoring.md) — переход уходит в `in_dev`.
        """
        self.assert_refused_naming(
            {"test_green.py": _sandbox.plank_source(claim=_sandbox.GREEN_ONLY)},
            "test_green.py", METHOD, why="только «Зелёный с рождения»")

    def test_ac8_once_file_without_claim_passes(self):
        """Разовый файл, чей метод не несёт «Ловит мутацию», — переход
        проходит в `in_dev`; тот же файл с группой «долгоживущий» —
        отклонён (контроль).

        Ловит мутацию: проверку заявки применили ко всем `test_*.py`
        планки без учёта группы — разовый файл отклоняется, задача
        остаётся в `tests_writing`.
        """
        self.assert_refused_naming(
            {"test_ac.py": _sandbox.plank_source(
                group=_sandbox.GROUP_LONG, claim=None)},
            "test_ac.py", METHOD, why="контроль: долгоживущий без заявки")
        self.assert_passes(
            {"test_ac.py": _sandbox.plank_source(
                group=_sandbox.GROUP_ONCE, claim=None)},
            why="разовый файл без «Ловит мутацию»")


if __name__ == "__main__":
    unittest.main()
