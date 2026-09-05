"""Приёмочные тесты 01M1R66X5SMD3ZEDCVAJ0DR7K2 — AC-6 (в режиме
артефактной ветки нарушение у «сданного» артефакта — exit-код 1;
нарушение только у черновиков — exit-код 0, напечатанное как
предупреждение).

Красен до реализации: см. докстринг `test_ac5_cli_flag_enables_mode.py`
— `--artifact-branch` сегодня не распознан, любой прогон с флагом
сегодня возвращает 1 по причине «файл не найден» для самого флага,
независимо от содержимого фикстур; `test_ac6_only_draft_violations_exit_zero`
красен именно на этом (ожидает 0, получает 1), `test_ac6_a_single_sdan_violation_exits_one`
проходит по коду СЛУЧАЙНО (тоже 1), но с ДРУГИМ текстом вывода — этот
файл его не проверяет текстом, только полагается на первый тест как
дискриминатор; оба вместе локализуют дефект.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import run_main, spec_zones_text  # noqa: E402


class OnlyDraftViolationsExitZeroTest(unittest.TestCase):
    def test_ac6_only_draft_violations_exit_zero(self):
        """Единственный файл — черновик с нарушением, режим включён:
        прогон завершается успешно (exit 0), несмотря на найденное
        нарушение.

        Ловит мутацию: разработчик правильно печатает предупреждение, но
        забывает исключить его вклад в итоговый список ошибок,
        определяющий код возврата (`if all_errors: return 1` без разбора
        на «сданные» и «черновики») — тогда любое найденное нарушение,
        даже черновичное, вернуло бы 1.
        """
        files = {"tasks/T1/SPEC.md": spec_zones_text(status="draft", zones=None)}

        code, out = run_main(files, artifact_branch=True)

        self.assertEqual(code, 0, out)


class ASingleSdanViolationExitsOneTest(unittest.TestCase):
    def test_ac6_a_single_sdan_violation_exits_one_even_among_clean_drafts(self):
        """Черновик БЕЗ нарушений (валиден) + сданный С нарушением —
        режим включён: прогон отказывает (exit 1) из-за сданного файла,
        несмотря на то, что черновик рядом чист.

        Ловит мутацию: разработчик учитывает в итоговом коде возврата
        только ПЕРВЫЙ по алфавиту/порядку обхода файл, а не весь набор
        (например `return 0 if not errors_of(files[0]) else 1`) — приходя
        первым по `rglob`, чистый черновик `SPEC.md` в `tasks/T1/`
        замаскировал бы нарушение соседнего `tasks/T2/`.
        """
        files = {
            "tasks/T1/SPEC.md": spec_zones_text(status="draft", zones="tests/"),
            "tasks/T2/SPEC.md": spec_zones_text(status="ready", zones=None),
        }

        code, out = run_main(files, artifact_branch=True)

        self.assertEqual(code, 1, out)


if __name__ == "__main__":
    unittest.main()
