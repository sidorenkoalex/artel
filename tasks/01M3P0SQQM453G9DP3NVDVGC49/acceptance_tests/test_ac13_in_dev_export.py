"""AC-13: переход `in_dev -> verifying` сравнивает прогоны долгоживущих
файлов в рабочей копии и в изолированной выгрузке с теми же исходами, что
выход из `tests_writing`; отказ называет `amend-tests` Оператора.

Песочница — `_sandbox.ExportSandbox`; фикстурный файл
`_sandbox.EXPORT_FIXTURE` залочен на выходе из `tests_writing` без флагов
(зелёный в обоих прогонах), флаги каталога управления ставятся после лока
— байты файла и перечень сумм не меняются.

Группа: разовый
Красен до реализации: `in_dev -> verifying` гоняет долгоживущие файлы только в рабочей копии — окольный метод, сбой сбора вне рабочей копии и пропуск через помощника уводят задачу в `verifying`; честный файл на `tests/sandbox.py` нынешний guard не пускает дальше `tests_writing`. Методы «красный в обоих прогонах» и «чистый файл проходит» зелёные с рождения: отказ нынешнего прогона рабочей копии не несёт подсказки выгрузки, чистый файл нынешний `in_dev` пропускает.

Валидация стабом (временная реализация прогона в выгрузке и встраивания
рядом со сверкой перечня; откачена): все методы файла зелёные.

Почему разовый: сценарий строит ветку документов через `artifact_branch`
и зовёт git через `subprocess` — признаки, которые нынешний (до этой
задачи) guard запрещает долгоживущему файлу; долгоживущие тесты
требований 9-12 пишет разработчик (требование 15 SPEC).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (EXPORT_HINT, EXPORT_METHOD, ExportSandbox,  # noqa: E402
                      honest_fixture)


class InDevExportTest(ExportSandbox):

    def setUp(self):
        super().setUp()
        self.lock_with_own(self.export_fixture())

    def refused_with(self, *flags: str) -> str:
        self.disarm()
        self.arm(*flags)
        text = self.advance_in_dev()
        self.assertEqual(self.state(), "in_dev",
                         f"{flags}: переход обязан быть отклонён: {text}")
        self.assertIn(self.own_name(), text, f"{flags}: отказ не называет файл")
        self.assertIn("amend-tests", text, f"{flags}: отказ не называет amend-tests")
        return text

    def test_ac13_green_in_copy_red_in_export_refused(self):
        """Окольный метод (зелёный в рабочей копии, красный в выгрузке) —
        переход отклонён; отказ называет файл, метод, подсказку выгрузки и
        `amend-tests`.

        Ловит мутацию: сравнение «рабочая копия / выгрузка» встроено только
        в выход из `tests_writing`, а в обработчик `in_dev` — нет: задача
        уходит в `verifying`.
        """
        text = self.refused_with("roundabout")
        self.assertIn(EXPORT_METHOD, text)
        self.assertIn(EXPORT_HINT, text)

    def test_ac13_collect_error_in_export_refused(self):
        """Модуль падает при сборе только в выгрузке — переход отклонён с
        именем файла и `amend-tests`.

        Ловит мутацию: ошибка сбора выгрузки на `in_dev` засчитана проходом
        (разбор отчёта только по методам).
        """
        self.refused_with("collect")

    def test_ac13_skip_through_helper_refused(self):
        """Метод пропущен через помощника в рабочей копии — переход
        отклонён по отчёту с именем файла, метода и `amend-tests`
        (нынешний прогон рабочей копии пропуск принимает зелёным).

        Ловит мутацию: пропуск проверяется только в прогоне выгрузки, а не
        «в любом из двух» — пропуск рабочей копии проходит в `verifying`.
        """
        text = self.refused_with("skip")
        self.assertIn(EXPORT_METHOD, text)

    def test_ac13_red_in_both_is_not_an_export_refusal(self):
        """Метод красный в обоих прогонах — отказ даёт обычный прогон
        приёмки рабочей копии, но не сравнение выгрузки: подсказки выгрузки
        в тексте нет.

        Ловит мутацию: `in_dev` отказывает по любому не зелёному исходу
        выгрузки без сравнения с рабочей копией — текст несёт подсказку
        «тест привязан к настоящему репозиторию».
        """
        self.disarm()
        self.arm("red")
        text = self.advance_in_dev()
        self.assertEqual(self.state(), "in_dev", text)
        self.assertNotIn(EXPORT_HINT, text)

    def test_ac13_clean_file_passes(self):
        """Без флагов фикстурный файл зелёный в обоих прогонах — переход
        проходит в `verifying`.

        Ловит мутацию: выгрузка строится без `tests/` задачи (или прогон
        без `extra`-файлов) и отказывает «метод не найден» — чистая задача
        не проходит `in_dev`.
        """
        self.disarm()
        text = self.advance_in_dev()
        self.assertEqual(self.state(), "verifying", text)


class InDevHonestFileTest(ExportSandbox):

    COPY_CODE = True

    def test_ac13_honest_sandbox_file_passes(self):
        """Честный долгоживущий файл на `tests/sandbox.py` проходит и выход
        из `tests_writing`, и `in_dev -> verifying`.

        Ловит мутацию: выгрузка на `in_dev` архивирует голову ветки без
        `orchestrator/`/`tests/sandbox.py` (только файлы перечня) — честный
        файл падает на импорте, переход отклонён.
        """
        self.lock_with_own(honest_fixture())
        text = self.advance_in_dev()
        self.assertEqual(self.state(), "verifying", text)


if __name__ == "__main__":
    unittest.main()
