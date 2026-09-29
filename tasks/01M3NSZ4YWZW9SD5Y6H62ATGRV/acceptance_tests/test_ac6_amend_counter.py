"""AC-6: счётчик ADR-0012 общий — успешный вызов `amend-tests` любого
режима даёт ровно одно событие `AMEND_ACTION` журнала задачи, неуспешный
(отказ проверки, сбой между записями) — ни одного; окно и порог прежние,
два успеха в окне поднимают алерт «планка девальвируется».

Группа: разовый
Красен до реализации: правка долгоживущего файла из worktree получает отказ, успешного вызова нет — счётчик не растёт, и алерт не поднимается.

Почему разовый: сценарий строит ветку документов через `artifact_branch`
и адресует `tasks/<id>/acceptance_tests/` — признаки, запрещённые
долгоживущему файлу; долгоживущие тесты — требование 9 SPEC.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import AmendSandbox, failed, long_lived_source, plank_source  # noqa: E402
from orchestrator import alerts, amend, store  # noqa: E402


class AmendCounterTest(AmendSandbox):

    PLANK_COVERS_AC2 = True

    def devaluation_alerts(self) -> list:
        return [a for a in alerts.open_alerts(store.db())
                if a["source"] == amend.DEVALUATION_ALERT_SOURCE]

    def step(self, label: str, action, *, success: bool) -> None:
        before = self.amend_events()
        code, out = action()
        self.assertEqual(not failed(code), success, f"{label}: {out}")
        self.assertEqual(self.amend_events() - before, 1 if success else 0,
                         f"{label}: событий «{amend.AMEND_ACTION}» — не "
                         f"{1 if success else 0}: {out}")

    def test_ac6_one_event_per_success_none_per_failure(self):
        """Подряд: отказ проверки (нет строки группы) — 0 событий; успех
        из worktree — 1 и ещё нет алерта; сбой записи в ветку документов
        после коммита кода — 0; `--from-branch` — 1 и алерт «планка
        девальвируется»; удаление с переносом в планку — 1.

        Ловит мутацию: событие журналируется на каждую изменённую ветку
        (две записи за вызов) либо до последней записи (сбой между
        записями оставляет событие) — счёт на шаге расходится.
        """
        self.write_wt(self.own, long_lived_source(group=None))
        self.step("отказ проверки", self.amend, success=False)
        self.restore_wt()

        self.write_wt(self.own, long_lived_source(tail="# правка 1\n"))
        self.step("успех из worktree", self.amend, success=True)
        self.assertEqual(self.devaluation_alerts(), [],
                         "одна правка в окне — не повод для алерта")

        self.restore_wt()
        self.write_wt(self.own, long_lived_source(tail="# правка 2\n"))
        with self.docs_branch_write_fails():
            self.step("сбой между записями", self.amend, success=False)

        self.step("успех --from-branch", self.amend_from_branch, success=True)
        self.assertTrue(self.devaluation_alerts(),
                        "две правки в окне обязаны поднять алерт")

        self.restore_wt()
        self.materialize_plank()
        (self.wt / self.own).unlink()
        self.write_wt(f"tasks/{self.TASK}/acceptance_tests/test_moved.py",
                      plank_source(("test_ac2_long_fixture",)))
        self.step("успех удаления с переносом", self.amend, success=True)

    def test_ac6_window_and_threshold_unchanged(self):
        """Окно и порог счётчика ADR-0012 — прежние 5 и 1.

        Ловит мутацию: порог поднят (или окно сужено), чтобы правки
        долгоживущих файлов не поднимали алерт.
        """
        self.assertEqual(amend.WINDOW_SIZE, 5)
        self.assertEqual(amend.WINDOW_THRESHOLD, 1)


if __name__ == "__main__":
    unittest.main()
