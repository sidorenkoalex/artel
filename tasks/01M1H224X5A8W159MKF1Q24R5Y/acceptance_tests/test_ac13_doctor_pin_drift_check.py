"""AC-13: `doctor` печатает отдельную информационную проверку: расхождение
между пином `config.ROOT` и текущим HEAD main артели — называет оба sha и
точную команду обновления пина. Статус этой проверки никогда не `fail` и
не блокирует прогон `doctor`.

Допущение интерфейса (SPEC/ANSWER-1 не называют механизм хранения пина —
решение зафиксировано здесь тестом, «лок» test-authoring): Stage0
(требование 4 SPEC) гарантирует, что `merge_gate -> done` НЕ двигает
рабочее дерево/HEAD `config.ROOT` — то есть «пин» и есть ФАКТИЧЕСКИЙ
текущий HEAD `config.ROOT` (отдельного хранилища для значения пина не
заводится, оно и так уже единственный источник истины по построению
Stage0). Проверка ниже поэтому сравнивает `gitcmd.head_sha()` (HEAD
`config.ROOT`, "пин") с HEAD `refs/heads/main` `origin` артели ("текущий
main артели", ANSWER-1 — тот же `self.origin`, что и AC-8/9/12).
Операторская команда обновления пина названа `pin-update` (AC-14, тот же
файл интерфейсных допущений) — дефис-конвенция существующих команд
(`target-init`, `alert-ack`, `acceptance-dry-run`, `orchestrator/artel.py`).

Проверяется на уровне `doctor.all_checks(conn)` (агрегатор `doctor.
cmd_doctor`, `orchestrator/doctor.py`), а не по имени конкретной
подпроверки — устойчиво к тому, как разработчик её назовёт.

Красен до реализации: сегодня ни один Check из `all_checks` не сравнивает
HEAD `config.ROOT` с HEAD main артели вовсе (пина не существует) — тест
ищет Check, чей `detail` называет ОБА sha (по 7-значному префиксу), и не
находит ни одного.
"""
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import doctor, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import ArtelSelfTargetSandbox  # noqa: E402


class DoctorReportsRootPinDriftTest(ArtelSelfTargetSandbox):

    def _find_pin_check(self, root_sha: str, origin_sha: str):
        checks = doctor.all_checks(store.db())
        for c in checks:
            if root_sha[:7] in c.detail and origin_sha[:7] in c.detail:
                return c
        return None

    def test_ac13_drift_is_reported_naming_both_shas_never_as_fail(self):
        """Main артели (`self.origin`) ушёл вперёд ОТДЕЛЬНО от пина
        `config.ROOT` (`advance_origin_main_without_touching_root` —
        песочница AC-8/9/12 этой же задачи) — среди `all_checks` обязан
        найтись Check, чей `detail` называет ОБА sha (пин и текущий main
        артели), со статусом НЕ `fail`.

        Ловит мутацию: отсутствие самой проверки (сегодняшнее состояние)
        — `_find_pin_check` вернёт `None`; либо проверка, которая для
        расхождения пина возвращает `status="fail"` — прямое нарушение
        «статус никогда не fail» AC-13.
        """
        root_sha = self.root_head_sha()
        origin_sha_after = self.advance_origin_main_without_touching_root()

        check = self._find_pin_check(root_sha, origin_sha_after)

        self.assertIsNotNone(
            check, f"ни один Check не назвал оба sha ({root_sha[:7]}, "
            f"{origin_sha_after[:7]}) — проверка расхождения пина не найдена")
        self.assertNotEqual(check.status, "fail",
                           "расхождение пина не должно проваливать doctor")

    def test_ac13_no_drift_is_not_reported_as_a_problem(self):
        """Контроль: пин `config.ROOT` СОВПАДАЕТ с HEAD main артели (ничего
        не продвигали) — проверка расхождения (если её Check вообще
        найден по одному sha, повторённому дважды) не несёт статус
        `fail`; отсутствие проверки в этом случае — не дефект (нечего
        печатать про расхождение, которого нет)."""
        root_sha = self.root_head_sha()

        checks = doctor.all_checks(store.db())

        pin_related = [c for c in checks if root_sha[:7] in c.detail]
        self.assertTrue(all(c.status != "fail" for c in pin_related),
                        "ни одна проверка, упоминающая sha пина, не должна "
                        "проваливать doctor при отсутствии расхождения")


if __name__ == "__main__":
    unittest.main()
