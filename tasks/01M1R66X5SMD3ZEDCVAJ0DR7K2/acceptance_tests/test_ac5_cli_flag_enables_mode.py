"""Приёмочные тесты 01M1R66X5SMD3ZEDCVAJ0DR7K2 — AC-5 (`guard.py --all` с
новым флагом включает режим артефактной ветки для ВСЕГО набора файлов
запуска; без флага — поведение как до задачи).

Флаг зафиксирован этой планкой как `--artifact-branch`
(`_sandbox.ARTIFACT_BRANCH_FLAG`, обоснование — докстринг `_sandbox.py`).

Красен до реализации: `--artifact-branch` сегодня не распознан —
`main()` трактует его как путь к файлу, которого нет («--artifact-branch:
файл не найден»), а НЕ как включение режима; прогон одного и того же
черновика с флагом и без даёт СЕГОДНЯ ОДИНАКОВЫЙ exit-код 1 (по разным
причинам), тогда как тест ниже требует РАЗНЫЕ коды (0 с флагом, 1 без) —
`assertNotEqual`/`assertEqual(code_on, 0, ...)` красны именно на этом
расхождении.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import run_main, spec_zones_text  # noqa: E402


class FlagTogglesTheWholeRunTest(unittest.TestCase):
    """Один и тот же набор файлов (единственный черновик с нарушением) —
    флаг включает режим для ВСЕГО прогона `--all`, меняя итог с отказа на
    успех."""

    def test_ac5_same_fixture_flips_exit_code_depending_on_the_flag(self):
        """Черновик SPEC без `zones`: без флага — реальное нарушение
        (exit 1, как сегодня); с флагом — то же нарушение переведено в
        предупреждение (exit 0). Один и тот же входной набор файлов,
        единственная переменная — присутствие флага.

        Ловит мутацию: разработчик подключает флаг, но не пробрасывает
        его в цикл по файлам `--all` (например читает флаг, но забывает
        передать соответствующий параметр в проверку каждого файла) —
        тогда прогон с флагом продолжил бы отказывать (exit 1), как и без
        него, и `assertEqual(code_on, 0, ...)` покраснеет.
        """
        files = {"tasks/T1/SPEC.md": spec_zones_text(status="draft", zones=None)}

        code_off, out_off = run_main(files, artifact_branch=False)
        code_on, out_on = run_main(files, artifact_branch=True)

        self.assertEqual(code_off, 1, out_off)
        self.assertEqual(code_on, 0, out_on)

    def test_ac5_flag_applies_to_every_file_of_the_all_run_not_just_the_first(self):
        """Два черновика с нарушением в ОДНОМ прогоне `--all
        --artifact-branch` — оба переведены в предупреждение, не только
        первый по алфавиту.

        Ловит мутацию: разработчик применяет режим только к ПЕРВОМУ
        обработанному файлу (например читает флаг один раз и сбрасывает
        локальную переменную после первой итерации цикла) — тогда второй
        файл (`tasks/T2/...`) остался бы нарушением, exit-код — 1 вместо
        ожидаемого 0.
        """
        files = {
            "tasks/T1/SPEC.md": spec_zones_text(status="draft", zones=None),
            "tasks/T2/SPEC.md": spec_zones_text(status="draft", zones=None),
        }

        code, out = run_main(files, artifact_branch=True)

        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
