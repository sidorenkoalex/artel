"""AC-8 (SPEC.md, требование 3) — `doctor` предупреждает, если открытый
пул в `~/.artel-canary` по содержимому отличается от запечатанного в
`canary/pool.sealed` (незапечатанные правки).

Красен до реализации: `doctor` сегодня не знает о пуле вовсе — ни
проверки такого рода в `orchestrator/doctor.py::all_checks`, ни
`pool-seal`, создающего `pool.sealed`, с которым было бы что сравнивать
(см. `test_pool_seal.py`). `test_ac8_...` падает на первом
`assertNotIn("WARN", ...)` уже неверно (доктор в принципе не печатает
такую строку) — событие «нет WARN до правки» технически совпадает с
ожиданием ДО расхождения, поэтому красноту несёт вторая половина теста:
`assertIn` после правки пула не находит `WARN` о пуле, так как проверки
нет вовсе.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import PoolDoctorSandbox  # noqa: E402


def _pool_warning_lines(doctor_output: str) -> list:
    return [ln for ln in doctor_output.splitlines()
           if "WARN" in ln and ("пул" in ln.lower() or "canary" in ln.lower())]


class PoolDoctorWarningTest(PoolDoctorSandbox):

    def test_ac8_doctor_warns_only_when_open_pool_diverges_from_sealed(self):
        """Два прогона `doctor` на одном и том же (иначе не относящемся
        к пулу) пульте: (1) сразу после `pool-seal`, открытый пул и
        `pool.sealed` совпадают — ни одной строки-предупреждения о
        расхождении пула быть не должно; (2) правим один файл открытого
        пула, не запечатывая правку, — `doctor` обязан напечатать
        предупреждение об этом расхождении.

        Ловит мутацию: разработчик реализует сравнение, но не подключает
        его к выводу `doctor` (тихая проверка без предупреждения) — обе
        половины теста тогда одинаково пусты, и второй `assertTrue`
        (правка обязана дать хотя бы одну строку) падает; проверка,
        которая предупреждает ВСЕГДА (даже без расхождения) — ловит
        первый `assertEqual([], ...)`.
        """
        self.write_pool_templates({
            "a.md": "тело А\n", "b.md": "тело Б\n"})
        self.seal()

        clean_output = self.run_doctor()
        clean_warnings = _pool_warning_lines(clean_output)
        self.assertEqual(
            clean_warnings, [],
            f"doctor предупреждает о расхождении пула сразу после "
            f"pool-seal, когда открытый пул и sealed совпадают: "
            f"{clean_warnings}")

        (self.pool_dir / "a.md").write_text(
            "тело А, правка без pool-seal\n", encoding="utf-8")

        dirty_output = self.run_doctor()
        dirty_warnings = _pool_warning_lines(dirty_output)
        self.assertTrue(
            dirty_warnings,
            f"doctor не предупредил о незапечатанной правке открытого "
            f"пула (AC-8): полный вывод:\n{dirty_output}")


if __name__ == "__main__":
    unittest.main()
