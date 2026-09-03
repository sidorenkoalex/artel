"""AC-4: `doctor.check_orphans` сканирует на сироты обе директории артели:
исторический `tasks/` пульта (без изменений) и новый
`.artel/projects/artel/tasks/` — задача или ветка без строки БД в любой из
них заводит существующий incident-алерт тем же порядком, что и сегодня для
внешних target.

Красен до реализации: `orchestrator/doctor.py::check_orphans` строит
список каталогов для сканирования как `scan = [(config.DEFAULT_TARGET,
config.TASKS)] + [(name, config.PROJECTS/name/"tasks") for name in
targets.load() if name != config.DEFAULT_TARGET]` (строки ~553-557) —
фильтр `if name != config.DEFAULT_TARGET` НАРОЧНО исключает 'artel' из
второго списка, даже когда 'artel' объявлена в targets.yaml (что она уже
объявлена — AC-1). Тест ниже кладёт осиротевший каталог именно в
`.artel/projects/artel/tasks/` (не в `tasks/` пульта) и падает потому, что
сегодня этот каталог просто не входит в `scan` вовсе — ни один incident не
заводится.
"""
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import alerts, catalog, config, doctor, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402

ARTEL_TARGETS_YAML = """targets:
  artel:
    forge: github
    url: https://example.invalid/artel
    base: main
    token_slot: artel-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


class OrphanScanCoversArtelProjectsDirTest(TmpRootTest):
    """`.artel/projects/artel/tasks/<id>` без строки БД — такой же сирота,
    как `tasks/<id>` пульта."""

    def setUp(self):
        super().setUp()
        config.TARGETS.write_text(ARTEL_TARGETS_YAML, encoding="utf-8")
        capture(catalog.cmd_init)

    def test_ac4_orphan_dir_under_artel_projects_tasks_raises_an_incident(self):
        """Каталог `.artel/projects/artel/tasks/T777` без строки БД (новая
        топология артельных задач требования 3 SPEC) — `check_orphans`
        обязана завести `doctor.orphans.dir` incident на него, тем же
        порядком, что и для сироты в `tasks/` пульта.

        Ловит мутацию: фильтр `if name != config.DEFAULT_TARGET` в
        построении `scan` внутри `check_orphans` — тогда каталог просто
        не сканируется, `orphans-dirs` останется "ok", incident не
        заведётся.
        """
        orphan_dir = config.PROJECTS / config.DEFAULT_TARGET / "tasks" / "T777"
        orphan_dir.mkdir(parents=True)

        checks = doctor.check_orphans(store.db())

        by_name = {c.name: c for c in checks}
        self.assertEqual(by_name["orphans-dirs"].status, "fail")
        incidents = [a for a in alerts.open_alerts(store.db(), "incident")
                    if a["source"] == "doctor.orphans.dir"]
        self.assertEqual(len(incidents), 1)
        self.assertIn("T777", incidents[0]["message"])

    def test_ac4_both_pult_tasks_and_artel_projects_orphans_caught_together(self):
        """Одновременная сирота в ИСТОРИЧЕСКОМ `tasks/` пульта (T555) и в
        НОВОМ `.artel/projects/artel/tasks/` (T777) — обе замечены одним
        прогоном `check_orphans`, ни одна не перекрывает другую и не
        сканируется дважды (по одному incident на каждую).

        Ловит мутацию: реализация, которая просто ЗАМЕНЯЕТ старую запись
        `(config.DEFAULT_TARGET, config.TASKS)` на новую вместо ДОБАВЛЕНИЯ
        второй `(config.DEFAULT_TARGET, config.PROJECTS/'artel'/'tasks')`
        — тогда историческая сирота `tasks/T555` перестала бы замечаться
        (регрессия «без изменений» требования 3), и итоговых incidents
        было бы 1, а не 2.
        """
        (config.TASKS / "T555").mkdir(parents=True)
        (config.PROJECTS / config.DEFAULT_TARGET / "tasks" / "T777").mkdir(
            parents=True)

        checks = doctor.check_orphans(store.db())

        by_name = {c.name: c for c in checks}
        self.assertEqual(by_name["orphans-dirs"].status, "fail")
        incidents = [a for a in alerts.open_alerts(store.db(), "incident")
                    if a["source"] == "doctor.orphans.dir"]
        self.assertEqual(len(incidents), 2)
        messages = " ".join(a["message"] for a in incidents)
        self.assertIn("T555", messages)
        self.assertIn("T777", messages)

    def test_ac4_known_task_id_in_artel_projects_tasks_is_not_an_orphan(self):
        """Контроль: каталог `.artel/projects/artel/tasks/<id>`, для
        которого В БД ЕСТЬ строка задачи — не сирота, `orphans-dirs`
        остаётся "ok", incident не заводится (симметрично тому, как уже
        сегодня работает `tasks/<id>` пульта с известным id)."""
        store.insert_task(store.db(), "01KNOWNARTELTASK00000001",
                          "Известная задача артели", "in_dev",
                          "task/01knownarteltask00000001",
                          config.DEFAULT_TARGET, 25.0)
        (config.PROJECTS / config.DEFAULT_TARGET / "tasks" /
         "01KNOWNARTELTASK00000001").mkdir(parents=True)

        checks = doctor.check_orphans(store.db())

        by_name = {c.name: c for c in checks}
        self.assertEqual(by_name["orphans-dirs"].status, "ok")
        self.assertEqual(alerts.open_alerts(store.db(), "incident"), [])


if __name__ == "__main__":
    unittest.main()
