"""AC-16 (tasks/01M1PNBSHR2PMFECMP7C204MF1/SPEC.md): «Существующие тесты
T041 (tests/test_timeout_checkpoint.py), T074 (tests/test_pause_now.py),
T044 (tests/test_lease.py), T062 (tests/test_release.py) остаются
зелёными без ослабления.»

Регрессионная планка: реальный `python -m unittest` по четырём файлам,
названным в самом критерии буквально по номерам задач — не импорт (успех
импорта не гарантирует, что тесты внутри пройдут) и не мок, а настоящий
прогон. «Без ослабления» (правка самих файлов теста под изменившееся
поведение вместо починки кода) этот тест по построению засечь не может —
это предмет ревью диффа разработчика, не исполняемое здесь свойство;
наблюдаемая часть критерия — код возврата прогона.

Зелёный с рождения: до реализации требований этой задачи (группа
процессов, group-kill, сторож зависших прогонов) все четыре файла уже
проходят — они покрывают существующее поведение runner/pause/lease/
release, не затронутое ДО того, как разработчик тронет эти модули;
прогнано локально перед фиксацией этого файла: `python3 -m unittest
tests.test_timeout_checkpoint tests.test_pause_now tests.test_lease
tests.test_release` — 73/73 ok. Задача этого теста — заметить, если
реализация требований 1-3 SPEC заденет эти модули и что-то в них
сломает, не подтвердить факт их сегодняшней зелёности заново.
"""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import REPO_ROOT  # noqa: E402

EXISTING_TEST_MODULES = (
    "tests.test_timeout_checkpoint",  # T041
    "tests.test_pause_now",           # T074
    "tests.test_lease",               # T044
    "tests.test_release",             # T062
)


class ExistingRegressionSuiteStaysGreenTest(unittest.TestCase):

    def test_ac16_t041_t074_t044_t062_pass_after_the_change(self):
        """Прогоняет T041/T074/T044/T062 как есть — критерий требует их
        зелёности после реализации, не факта существования файлов или их
        импортируемости.

        Ловит мутацию: любая правка `orchestrator/runner.py`, `pause.py`,
        `lease.py`, `release.py` ради группы процессов/group-kill
        (требования 1-2 SPEC), которая по пути ломает уже существующее
        поведение (например, `os.killpg` без перехвата
        `ProcessLookupError` на уже мёртвом pgid — там, где сегодняшний
        тест держит pid стабом без реальной группы, — или смена сигнатуры
        функции, которую эти тесты мокают/зовут напрямую) — код возврата
        подпроцесса станет ненулевым, `assertEqual` ниже покраснеет.
        """
        result = subprocess.run(
            [sys.executable, "-m", "unittest", *EXISTING_TEST_MODULES],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=180)

        self.assertEqual(
            result.returncode, 0,
            "существующий набор T041/T074/T044/T062 не проходит целиком "
            "после изменений:\n" + result.stderr[-4000:])


if __name__ == "__main__":
    unittest.main()
