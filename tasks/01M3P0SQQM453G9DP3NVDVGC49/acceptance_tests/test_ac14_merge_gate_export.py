"""AC-14: гейт мержа после подтяжки `main` гоняет долгоживущие файлы в
изолированной выгрузке — падение, ошибка (метода и сбора) или пропуск
останавливает тело гейта без merge с именем файла и метода; все зелёные —
тело идёт дальше (до ожидания CI); задача без долгоживущих файлов
выгрузку не строит ни на одном из трёх переходов.

Песочница — `_sandbox.ExportSandbox`; фикстурный файл
`_sandbox.EXPORT_FIXTURE` залочен без флагов, флаги ставятся после лока.
«Выгрузку не строит» наблюдается по процессам: `subprocess.Popen`
подменён подклассом, записывающим argv (`_sandbox.SpyPopen`), выгрузка
строится `git archive` (требование 9) — контроль с долгоживущим файлом
показывает, что шпион этот вызов видит.

Группа: разовый
Красен до реализации: гейт мержа не гоняет долгоживущие файлы вовсе — падение, ошибка setUp, сбой сбора и пропуск в выгрузке доходят до ожидания CI; `git archive` не зовёт ни один переход, и контроль «с файлом выгрузка строится» падает. Сценарии «все зелёные — дальше» и «без файлов — нет выгрузки» зелёные с рождения.

Валидация стабом (временная реализация прогона в выгрузке через
`git archive` и встраивания в три перехода; откачена): все методы файла
зелёные, шпион видит `git archive` в контрольных сценариях.

Почему разовый: сценарий строит ветку документов через `artifact_branch`
и зовёт git через `subprocess` — признаки, которые нынешний (до этой
задачи) guard запрещает долгоживущему файлу; долгоживущие тесты
требований 9-12 пишет разработчик (требование 15 SPEC).
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (EXPORT_METHOD, ExportSandbox, SpyPopen,  # noqa: E402
                      archive_calls)


class MergeGateExportTest(ExportSandbox):

    def setUp(self):
        super().setUp()
        self.lock_with_own(self.export_fixture())

    def stopped_with(self, flag: str, method: bool = True) -> None:
        self.disarm()
        self.arm(flag)
        outcome, text = self.merge_gate_body()
        self.assertEqual(outcome, ("stopped",),
                         f"{flag}: гейт обязан остановиться: {text}")
        self.assertIn(self.own_name(), text, f"{flag}: остановка не называет файл")
        if method:
            self.assertIn(EXPORT_METHOD, text,
                          f"{flag}: остановка не называет метод")

    def test_ac14_failure_in_export_stops_merge_gate(self):
        """Метод падает в выгрузке — тело гейта `("stopped",)` с именем
        файла и метода.

        Ловит мутацию: прогон в выгрузке не встроен в гейт мержа рядом со
        сверкой лока и перечня — тело доходит до ожидания CI.
        """
        self.stopped_with("red")

    def test_ac14_method_error_in_export_stops_merge_gate(self):
        """`setUp` метода падает исключением только в выгрузке (исход
        «ошибка») — остановка с именем файла и метода.

        Ловит мутацию: отказ только по исходу «падение», исход «ошибка»
        засчитан проходом.
        """
        self.stopped_with("error")

    def test_ac14_collect_error_in_export_stops_merge_gate(self):
        """Модуль падает при сборе в выгрузке — остановка с именем файла.

        Ловит мутацию: ошибка сбора (ни одного метода в отчёте) засчитана
        проходом.
        """
        self.stopped_with("collect", method=False)

    def test_ac14_skip_in_export_stops_merge_gate(self):
        """Метод пропущен через помощника — остановка с именем файла и
        метода.

        Ловит мутацию: гейт мержа проверяет только код возврата pytest
        (пропуск даёт 0) — тело доходит до ожидания CI.
        """
        self.stopped_with("skip")

    def test_ac14_all_green_goes_on(self):
        """Без флагов все методы зелёные — тело гейта доходит до ожидания
        CI.

        Ловит мутацию: гейт останавливается при любом непустом перечне
        (или на зелёном отчёте из-за неверного разбора) — `("stopped",)`.
        """
        self.disarm()
        outcome, text = self.merge_gate_body()
        self.assertEqual(outcome[0] if outcome else None, "wait", text)

    def test_ac14_export_built_with_long_lived_files(self):
        """Контроль шпиона: с долгоживущим файлом тело гейта мержа зовёт
        `git archive`.

        Ловит мутацию: выгрузка на гейте мержа не строится (прогон в
        рабочей копии вместо выгрузки) — шпион не видит `git archive`.
        """
        self.disarm()
        SpyPopen.calls = []
        with mock.patch.object(subprocess, "Popen", SpyPopen):
            self.merge_gate_body()
        self.assertTrue(archive_calls(SpyPopen.calls),
                        "с долгоживущим файлом выгрузка обязана строиться")


class NoLongLivedFilesTest(ExportSandbox):

    def spied(self, call) -> tuple[list, str]:
        SpyPopen.calls = []
        with mock.patch.object(subprocess, "Popen", SpyPopen):
            text = call()
        return archive_calls(SpyPopen.calls), str(text)

    def test_ac14_no_long_lived_files_no_export_on_three_transitions(self):
        """Задача без долгоживущих файлов: выход из `tests_writing`,
        `in_dev -> verifying` и тело гейта мержа проходят, ни один не зовёт
        `git archive`.

        Ловит мутацию: выгрузка строится безусловно (пустой перечень файлов
        не проверен) — шпион видит `git archive` на одном из переходов.
        """
        calls, text = self.spied(self.exit_tests_writing)
        self.assertEqual(self.state(), "in_dev", text)
        self.assertEqual(calls, [], "tests_writing: выгрузка без файлов")
        calls, text = self.spied(self.advance_in_dev)
        self.assertEqual(self.state(), "verifying", text)
        self.assertEqual(calls, [], "in_dev: выгрузка без файлов")
        calls, text = self.spied(self.merge_gate_body)
        self.assertEqual(calls, [], "гейт мержа: выгрузка без файлов")

    def test_ac14_control_export_built_on_tests_writing_with_file(self):
        """Контроль шпиона: с долгоживущим файлом выход из `tests_writing`
        зовёт `git archive`.

        Ловит мутацию: на выходе из `tests_writing` выгрузка не строится —
        шпион не видит `git archive`, и отрицательный сценарий выше ничего
        не доказывает.
        """
        self.wt_commit({self.own: self.export_fixture()})
        calls, text = self.spied(self.exit_tests_writing)
        self.assertEqual(self.state(), "in_dev", text)
        self.assertTrue(calls, "с долгоживущим файлом выгрузка обязана строиться")


if __name__ == "__main__":
    unittest.main()
