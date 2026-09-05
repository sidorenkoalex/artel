"""Приёмочные тесты 01M1P9QAG65GVF69YJEV0V18D9 — AC-5 (SPEC.md).

## Допущение интерфейса — `doctor.check_zone_waits`

SPEC требование 4 называет модули (`orchestrator/catalog.py::cmd_status`,
`orchestrator/doctor.py`), но не имя новой проверки внутри `doctor.py`.
Тест берёт `doctor.check_zone_waits(conn) -> list[doctor.Check]` по
образцу уже существующих точечных проверок (`doctor.check_leases`,
`doctor.check_orphans`, `doctor.check_backup_age`) и зовёт её НАПРЯМУЮ, не
через `doctor.all_checks()`/`doctor.cmd_doctor()` — та тянет живой смоук
CLI, git identity, диск, targets.yaml и сетевые проверки, не относящиеся
к предмету этой задачи (тот же приём, что `tasks/T044/acceptance_tests/
test_lease_readonly_and_doctor.py` уже применил к `doctor.check_leases`,
докстринг её `_sandbox`-заметки).

`catalog.cmd_status` уже единая точка входа (`_lease_holder_suffix`
добавляет держателя lease ДОБАВКОЙ к строке задачи тем же приёмом) —
для неё интерфейс не изобретается, тест зовёт саму команду.

Красен до реализации: `catalog.cmd_status` сегодня печатает только
состояние/бюджет/lease-держателя (`orchestrator/catalog.py::cmd_status`)
— строка заблокированной задачи не назовёт ни зону, ни занявшую задачу;
`doctor.check_zone_waits` не существует (`AttributeError` — ожидаемо, не
брак теста).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import ZoneSandbox, _invoke  # noqa: E402

from orchestrator import catalog, doctor, store  # noqa: E402

CONFLICT_PATH = "orchestrator/foo_zone.py"
OCCUPIER = "T901"


class Ac5StatusAndDoctorShowZoneWaitTest(ZoneSandbox):
    """AC-5: `status` и `doctor` показывают для заблокированной задачи
    ожидание зоны и занявшую её задачу.

    Ловит мутацию: строка `status` заблокированной задачи не отличается
    от обычной `in_dev` (никакой добавки про зону/занявшую задачу), либо
    `doctor.check_zone_waits` возвращает пустой список / статус `ok` для
    реально заблокированной задачи вместо `warn`/`fail` с деталью,
    называющей обе задачи.
    """

    def setUp(self):
        super().setUp()
        self.reset_task()
        self.set_own_zones(CONFLICT_PATH)
        self.seed_task(OCCUPIER, "Занявшая зону", "in_dev", CONFLICT_PATH)

    def test_ac5_status_line_names_zone_wait_and_occupying_task(self):
        out = _invoke(catalog.cmd_status)

        lines = [ln for ln in out.splitlines() if ln.strip().startswith(self.TASK)]
        self.assertTrue(lines, f"status не напечатал строку задачи {self.TASK}: {out!r}")
        line = lines[0].lower()
        self.assertIn(OCCUPIER.lower(), line,
                     f"строка status задачи {self.TASK} не называет занявшую "
                     f"зону задачу {OCCUPIER}: {line!r}")
        self.assertRegex(line, r"зон",
                         f"строка status задачи {self.TASK} не упоминает "
                         f"ожидание зоны: {line!r}")

    def test_ac5_doctor_check_reports_zone_wait_with_both_task_ids(self):
        checks = doctor.check_zone_waits(store.db())

        relevant = [c for c in checks if self.TASK.lower() in c.detail.lower()]
        self.assertTrue(
            relevant,
            f"doctor.check_zone_waits не сообщил ничего про заблокированную "
            f"задачу {self.TASK}: {checks!r}")
        self.assertTrue(
            any(c.status != "ok" for c in relevant),
            f"doctor.check_zone_waits считает заблокированную задачу "
            f"{self.TASK} в порядке (status=ok): {relevant!r}")
        self.assertTrue(
            any(OCCUPIER.lower() in c.detail.lower() for c in relevant),
            f"doctor.check_zone_waits не назвал занявшую зону задачу "
            f"{OCCUPIER}: {relevant!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
