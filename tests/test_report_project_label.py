"""Метка проекта в HTML `report`: задача с `tasks.target` NULL и метка
алерта панели (SPEC 01M57PMBHWK5EGQ8HPA5TQX72H, требования 1-2; ANSWER-2,
пп. 1-2).

Связка: строки задач, журнала и алертов в БД песочницы —
`report.cmd_report` (файл `.artel/report.html`).
"""
import os
import re
from unittest import mock

from orchestrator import config, report, store
from tests.sandbox import TaskSeededTmpRootTest, capture, declare_target

EXTERNAL = "sled"
DECLARED_ONLY = "zubr"
ODD_TARGET = "odd-target"


def _strip(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


class _ReportBase(TaskSeededTmpRootTest):

    def setUp(self):
        super().setUp()
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "",
                                           "CODEX_SANDBOX": "",
                                           "CODEX_SANDBOX_NETWORK_DISABLED": ""})
        env.start()
        self.addCleanup(env.stop)
        self.conn = store.db()

    def render(self) -> str:
        capture(report.cmd_report)
        return (config.ROOT / ".artel" / "report.html").read_text(encoding="utf-8")


class NullTargetTaskRowsTest(_ReportBase):
    """T001 — `target` NULL в гейте acceptance, T002 — `target` NULL в done,
    T003 — внешнего проекта в acceptance: у каждой — запуск test_author."""

    def setUp(self):
        super().setUp()
        store.update_task(self.conn, self.TASK, state="acceptance", target=None)
        store.insert_task(self.conn, "T002", "Закрытая", "done", "task/t002",
                          config.DEFAULT_TARGET, 25.0)
        store.update_task(self.conn, "T002", target=None)
        store.insert_task(self.conn, "T003", "Внешняя", "acceptance",
                          "task/t003", EXTERNAL, 25.0)
        for task_id in ("T001", "T002", "T003"):
            store.journal(self.conn, task_id, report.TEST_AUTHOR_ROLE,
                          report.STEP_STARTED_ACTION, "старт шага")

    def test_null_target_task_has_no_label_in_any_row(self):
        """Задача с `target` NULL во всех строках задач — без метки, как
        задача артели: ни `[None]`, ни `[artel]`, ни метки за id.

        Сценарий: NULL-задача стоит и в очереди гейтов (T001), и в закрытых
        (T002); строки плиток, очереди, закрытых, разреза задач, трения и
        шагов test_author — текст без тегов.
        Ловит мутацию: проект строки берётся как `row["target"]` без замены
        NULL на артель — у задачи появляется `[None]`; либо метка ставится
        каждой задаче — `[artel]`.
        """
        text = _strip(self.render())
        for task_id in ("T001", "T002"):
            with self.subTest(task=task_id):
                self.assertNotRegex(text, rf"{task_id}\s*\[")
        self.assertNotIn("[None]", text)
        self.assertNotIn(f"[{config.DEFAULT_TARGET}]", text)
        self.assertRegex(text, rf"T003\s*\[{EXTERNAL}\]")


class AlertPanelLabelTest(_ReportBase):
    """Алерты панели: проект `targets.yaml` без задач в выборке, значение,
    не названное ни проектом, ни id задачи, id задачи, NULL и артель."""

    def setUp(self):
        super().setUp()
        declare_target(DECLARED_ONLY)
        for target, mark in ((DECLARED_ONLY, "m-declared"),
                             (ODD_TARGET, "m-odd"),
                             (self.TASK, "m-task"),
                             (None, "m-null"),
                             (config.DEFAULT_TARGET, "m-artel")):
            store.insert_alert(self.conn, target, "incident", "test", mark)

    def alert_rows(self) -> dict:
        html = self.render()
        items = re.findall(r'<li class="alert-item">(.*?)</li>', html)
        rows = {}
        for item in items:
            text = _strip(item).strip()
            mark = re.search(r"m-\w+", text).group(0)
            rows[mark] = text
        return rows

    def test_alert_label_from_declared_projects_and_raw_value(self):
        """Проект `targets.yaml` и неизвестное значение `target` — в
        скобках как есть; id задачи, NULL и артель — без метки.

        Ловит мутацию: метка ставится лишь проекту задач выборки (проект
        `targets.yaml` без задач и неизвестное значение теряют скобки);
        либо id задачи, NULL или артель получают метку.
        """
        rows = self.alert_rows()
        self.assertTrue(rows["m-declared"].startswith(f"[{DECLARED_ONLY}]"),
                        rows)
        self.assertTrue(rows["m-odd"].startswith(f"[{ODD_TARGET}]"), rows)
        for mark in ("m-task", "m-null", "m-artel"):
            with self.subTest(mark=mark):
                self.assertNotIn("[", rows[mark], rows)
