"""AC-4 (tasks/T049/SPEC.md): `check_backup_age` перестаёт заводить алерт.

«После изменения `check_backup_age` не заводит алерт (проверка снята
или деградирована до информационной строки), а поведение остальных
проверок `doctor` не меняется.»

Требование 6 SPEC явно допускает ДВА разных исхода — функция снята
совсем, либо осталась, но без вызова `alerts.raise_alert`. Тест не имеет
права зафиксировать один из них как единственно верный (иначе это уже не
тест критерия, а тест конкретной реализации): проверяется только то, что
названо в самом критерии — источник `doctor.backup_age` никогда не
заводит incident-алерт, независимо от того, существует ли ещё функция
`doctor.check_backup_age` как таковая.

Вторая часть критерия — «поведение остальных проверок doctor не
меняется» — уже гарантируется существующим `tests/test_doctor.py`
(каждая проверка doctor протестирована там по отдельности); AC-6 этой
задачи требует, чтобы `tests/` остался зелёным, то есть регрессия любой
другой проверки уже ловится штатным набором без дублирования здесь
(тот же довод, что у tasks/T046/acceptance_tests/test_predlozheniya_
sisteme.py про AC-4 той задачи).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import alerts, catalog, doctor, store  # noqa: E402
from _sandbox import TmpRootTest, capture  # noqa: E402


class BackupAgeNoAlertTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        # `config.BACKUP_MARKER` намеренно НЕ трогается — это именно то
        # состояние («маркера нет»), на котором старая реализация
        # заводила incident (см. `orchestrator/doctor.py` до этой задачи).

    def test_ac4_missing_backup_marker_never_raises_an_incident_alert(self):
        if hasattr(doctor, "check_backup_age"):
            check = doctor.check_backup_age(store.db())
            self.assertNotEqual(
                check.status, "fail",
                "check_backup_age всё ещё заводит провал при отсутствии "
                "маркера бэкапа — требование 6 SPEC снимает/деградирует "
                "именно это")

        incidents = [a for a in alerts.open_alerts(store.db(), "incident")
                    if a["source"] == "doctor.backup_age"]
        self.assertEqual(
            incidents, [],
            "отсутствие .artel/backup-marker подняло incident-алерт "
            "doctor.backup_age — требование 6 SPEC (легализовано "
            "ADR-0005 п.3) снимает эту проверку/алерт")


if __name__ == "__main__":
    unittest.main()
