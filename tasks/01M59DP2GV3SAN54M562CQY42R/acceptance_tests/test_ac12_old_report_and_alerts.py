"""AC-12: прежние блоки `report` и прежние оповещения не меняются.

Группа: разовый
Зелёный с рождения: до реализации задача ещё не тронула четыре файла тестов отчёта, а `auto_stop` поднимает оповещение внимания прежним текстом — тест держит, что правка задачи этого не изменит.

Неизменность тестов отчёта — факт ЭТОЙ задачи (дифф ветки от базы через
`changed_paths()` помощника пульта); прохождение их утверждений держит
полный прогон `tests/` пультом. Текст оповещения внимания цикла `auto` —
`auto.auto_stop(..., alert=True)` в песочнице `tests/sandbox.py`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, changed_paths  # noqa: E402

sys.path.insert(0, str(CODE_ROOT))
from orchestrator import auto, store  # noqa: E402
from tests.sandbox import TaskSeededTmpRootTest  # noqa: E402

REPORT_TESTS = (
    "tests/test_report.py",
    "tests/test_report_project_label.py",
    "tests/test_01m57pmbhwk5egq8hpa5tqx72h_report.py",
    "tests/test_01m4rzayh3swjw4wfbw4qw15fp_command_report.py",
)


class OldReportAndAlertsTest(TaskSeededTmpRootTest):

    def test_ac12_report_tests_untouched_and_attention_alert_text_kept(self):
        """Четыре файла тестов отчёта не в диффе задачи; оповещение внимания `auto` — прежним текстом.

        Сценарий: (1) пути диффа задачи (`changed_paths()`) не содержат ни
        одного из четырёх файлов тестов отчёта, названных критерием;
        (2) остановка цикла `auto.auto_stop` с `alert=True` заводит ровно
        одно открытое оповещение `kind=attention`, `source=auto`, target —
        id задачи, текст «[<id>] auto остановлен: <состояние>: <причина>».

        Зелёный с рождения: держит неизменность тестов отчёта и текста
        оповещения внимания. Краснеет, если разработчик правит утверждения
        тестов отчёта под новый блок или подменяет оповещение внимания
        оповещением `rounds`/меняет его текст.
        """
        changed = set(changed_paths())
        for path in REPORT_TESTS:
            with self.subTest(path=path):
                self.assertNotIn(path, changed, f"задача правит {path}")

        conn = store.db()
        reason = "лимит 30 шагов за вызов исчерпан"
        auto.auto_stop(conn, self.TASK, "in_dev", reason, "artel.py log", alert=True)
        found = [row for row in store.open_alerts(conn, "attention")
                 if row["target"] == self.TASK]
        self.assertEqual(len(found), 1, [dict(r) for r in found])
        self.assertEqual(found[0]["source"], "auto")
        self.assertEqual(found[0]["message"],
                         f"[{self.TASK}] auto остановлен: in_dev: {reason}")


if __name__ == "__main__":
    unittest.main()
