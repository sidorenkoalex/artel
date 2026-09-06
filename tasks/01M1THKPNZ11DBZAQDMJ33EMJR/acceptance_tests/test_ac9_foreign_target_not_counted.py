"""Приёмочный тест AC-9 — tasks/01M1THKPNZ11DBZAQDMJ33EMJR/SPEC.md.

AC-9. Отказы задачи внешнего target (не self) не учитываются счётчиком
стоп-крана self.

Заведение задачи внешнего target — тем же `catalog.cmd_new(...,
target=...)`, что и для self (см. `_sandbox.py`, докстринг): `target` не
сверяется с реестром на заведении, а дальнейший путь `run` для НЕ-self
target деградирует тихо там, где ему нечем ответить без настоящего git
(`artifact_branch.materialize_task_dir`), не падает — проверено прогоном
песочницы при подготовке файла (задача внешнего target доходит до
`escalated` тем же путём, что и self).

Красен до реализации: ДА — счётчика стоп-крана волны нет вовсе, но
дополнительно (в отличие от «зелёных с рождения» тестов этого пакета)
здесь красный ИМЕННО по причине, которую критерий называет: если бы
реализация появилась, но без фильтра по `target`, три задачи внешнего
target подняли бы алерт — тест обязан отличать «алерта нет, потому что
функции ещё нет» от «алерта нет, потому что она отфильтровала чужой
target» лишь после появления кода; до появления кода оба неотличимы
изнутри теста, что и оговорено в `_sandbox.py`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import WaveBreakerSandbox  # noqa: E402

CLASS_1B_TEXT = "API Error: Connection refused (ConnectionRefused)"
FOREIGN_TARGET = "внешний-проект"


class Ac9ForeignTargetNotCountedTest(WaveBreakerSandbox):

    def test_ac9_three_foreign_target_failures_do_not_raise_self_alert(self):
        """Три разные задачи ВНЕШНЕГО target, отказавшие тем же классом
        1б, в пределах того же окна — не учитываются счётчиком
        стоп-крана self: алерт не появляется, хотя число задач (3) и
        класс совпадают с AC-2.

        Ловит мутацию: подсчёт задач ведётся по всему журналу `steps`
        без фильтра `target=config.DEFAULT_TARGET` (или без фильтра
        вовсе) — тогда три задачи внешнего target подняли бы алерт
        стоп-крана self ровно как в AC-2.
        """
        for title in ("Чужая первая", "Чужая вторая", "Чужая третья"):
            task = self.new_task(title, target=FOREIGN_TARGET)
            row = self.task_row(task)
            self.assertEqual(row["target"], FOREIGN_TARGET,
                             "задача действительно заведена НЕ на self")
            self.fail_class(task, CLASS_1B_TEXT)
            self.assertEqual(self.task_row(task)["state"], "escalated",
                             "сценарий отказа реально прогнан до конца")

        found = self.wave_breaker_alerts()

        self.assertEqual(
            found, [],
            f"отказы задач внешнего target не должны учитываться "
            f"счётчиком стоп-крана self; найдено: "
            f"{[r['message'] for r in found]}")


if __name__ == "__main__":
    unittest.main()
