"""AC-13: `tests/test_auto_cycle.py` и существующие тесты lease/liveness
остаются зелёными без ослабления их проверок.

Единственный критерий этой задачи, который не про НОВОЕ поведение, а про
СОХРАНЕНИЕ старого — регрессия, а не свойство, которое можно закодировать
одним новым assert'ом над внутренним состоянием. Проверяется буквально:
реальным прогоном названного файла (AC-13 называет его явно) и файлов,
относящихся к lease/liveness (`test_lease.py` — предмет самого lease;
`test_doctor.py` — единственный файл, реально импортирующий
`orchestrator.liveness`, см. докстринг ниже), тем же интерпретатором,
которым CI/Оператор прогоняют весь набор.

Зелёный с рождения (SPEC ещё не реализован, но правку `test_auto_cycle.
py`/`test_lease.py`/`test_doctor.py` эта задача, по требованию 5 ТЗ и
самой формулировке AC-13, обязана не допускать вовсе): на СЕГОДНЯШНЕМ
дереве (до реализации SPEC) все три файла уже зелёные — сам факт
проверен прогоном при написании этого теста. Красным он станет, только
если реализация детача/`stop` ОСЛАБИТ или сломает существующее поведение
`run`/`auto`/lease/`doctor`, которое эти файлы фиксируют (например,
поменяет сигнатуру, которую они мокают, или сломает синхронное
поведение `--attach`, от которого эти тесты неявно зависят, вызывая
`cmd_run`/`cmd_auto` напрямую).
"""
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# `tests/test_auto_cycle.py` — названа в AC-13 буквально. `test_lease.py`
# — единственный файл целиком про lease (SPEC T044). `test_doctor.py` —
# единственный файл, кроме самого `orchestrator/liveness.py`, реально
# импортирующий и гоняющий `orchestrator.liveness`/`check_leases` (см.
# `grep -rl "liveness" tests/*.py` при написании теста — два результата,
# `tests/sandbox.py` — не тестовый файл, а песочница, и `tests/
# test_doctor.py`).
TARGET_FILES = (
    "tests/test_auto_cycle.py",
    "tests/test_lease.py",
    "tests/test_doctor.py",
)


class Ac13ExistingSuiteStaysGreenTest(unittest.TestCase):

    def test_ac13_named_suite_files_pass_unmodified(self):
        """Прогоняет `python3 -m unittest <module>...` для файлов из
        `TARGET_FILES` НАСТОЯЩИМ интерпретатором против дерева репозитория
        (не песочницы этой задачи) и требует кода возврата 0.

        Ловит мутацию: правка `orchestrator/auto.py`/`orchestrator/
        runner.py`/`orchestrator/lease.py` ради отвязки ломает СИГНАТУРУ
        или поведение, на которое полагаются эти файлы (например, мокинг
        `runner.spawn_agent` в `tests/test_auto_cycle.py` перестаёт
        перехватывать реальный запуск агента, потому что шаг теперь
        стартует из другого места) — тест покраснеет ненулевым кодом
        возврата, с полным выводом упавших тестов в тексте отказа.
        """
        modules = [f.replace("/", ".").removesuffix(".py")
                  for f in TARGET_FILES]
        res = subprocess.run(
            [sys.executable, "-m", "unittest", *modules],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=300)
        self.assertEqual(
            res.returncode, 0,
            f"{', '.join(TARGET_FILES)} — не все тесты зелёные "
            f"(код {res.returncode}):\n{res.stdout}\n{res.stderr}")


if __name__ == "__main__":
    unittest.main()
