"""Строка `canary_runs` прогона несёт роли эскалаций, вычисленные пультом из `steps` клона.

Прогон `canary._run_one_task` идёт целиком, подменён только процесс клона:
`_ephemeral_clone` отдаёт временный каталог со входом
`CANARY_DRIVE_ENTRY`, `_drive_in_clone` — код выхода 0 и путь файла
результата, который разбирает настоящий `_read_drive_result`. Подмена
закрытых имён `canary` в долгоживущем файле `tests/` запрещена, поэтому
эти проверки — в разовой группе; свойства `escalation_roles` и критерия
чистоты держит долгоживущий файл задачи в `tests/`. Сюда же — неизменность
порогов допуска ADR-0019 п.5 этой задачей (факт задачи).

Группа: разовый
Красен до реализации: пульт не вычисляет роли из `steps` и не пишет колонку `escalation_roles` — её нет в `canary_runs`, чтение падает `sqlite3.OperationalError`.
"""

import contextlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import canary, config, fsm, models

MARKER = fsm.ARTIFACT_ESCALATION_ROLE_STEP_MARKER
FIXATION = "sha зафиксирован"
HEAD = "f" * 40

# Набор полей `metrics` результата клона кода до задачи —
# `canary._DRIVE_METRIC_FIELDS` на main (коммит 891b3a48).
MAIN_METRIC_FIELDS = (
    "steps", "cost_usd", "review_iterations", "escalations", "dev_retries",
    "outcome", "kill_note", "test_author_visited", "ceiling_exhausted",
    "ceiling_raise",
)


def step(action: str, detail=None, actor: str = "fsm") -> dict:
    return {"ts": "2026-10-14T00:00:00Z", "actor": actor, "action": action,
            "detail": detail}


def role_step() -> list:
    return [step("agent run started", "попытка", "runner"),
            step("agent run finished", "ok", "runner")]


def enter(state: str, detail: str = "") -> list:
    return [step(f"state -> {state}", detail), step(FIXATION, "a" * 40)]


def ac1_steps() -> list:
    """Журнал AC-1: ловушку видят analyst, затем аудитор SPEC."""
    return [step("created", "Учебная задача", "catalog"),
            step("набор моделей задачи", "c-codex-all", "catalog"),
            *role_step(),
            step("state -> escalated", "analyst: батч вопросов"),
            step(FIXATION, "a" * 40), step(MARKER, "analyst"),
            *enter("spec_writing"), *role_step(),
            *enter("spec_audit"), *role_step(),
            step("state -> escalated", "spec_auditor: escalate"),
            step(FIXATION, "b" * 40), step(MARKER, "spec_auditor"),
            *enter("spec_writing"), *role_step(),
            *enter("spec_audit"), *role_step(),
            *enter("tests_writing"), *role_step(),
            *enter("in_dev"), *role_step(),
            *enter("review"), *role_step(),
            *enter("acceptance"), *enter("merge_gate")]


def ac11a_steps() -> list:
    """Журнал AC-11 (а): ловушка analyst, затем бюджетная эскалация из spec_audit."""
    return [step("created", "Учебная задача", "catalog"), *role_step(),
            step("state -> escalated", "analyst: ловушка"),
            step(FIXATION, "1" * 40), step(MARKER, "analyst"),
            *enter("spec_writing"), *role_step(),
            *enter("spec_audit"), *role_step(),
            step("state -> escalated", "бюджет исчерпан: $1.00 из $1.00"),
            step(FIXATION, "2" * 40),
            *enter("spec_audit"), *role_step(),
            *enter("tests_writing"), *role_step(),
            *enter("in_dev"), *role_step(),
            *enter("review"), *role_step(),
            *enter("acceptance"), *enter("merge_gate")]


def metrics_for(steps: list) -> dict:
    """Метрики ровно с полями кода до задачи, посчитанные по `steps`."""
    metrics = {
        "steps": sum(1 for s in steps if s["action"].startswith("state -> ")),
        "cost_usd": 1.5, "review_iterations": 0,
        "escalations": [s["detail"] or "" for s in steps
                        if s["action"] == "state -> escalated"],
        "dev_retries": 0, "outcome": "killed", "kill_note": "штатно",
        "test_author_visited": True, "ceiling_exhausted": False,
        "ceiling_raise": None,
    }
    assert tuple(metrics) == MAIN_METRIC_FIELDS
    return metrics


class RunOneTaskRowTest(unittest.TestCase):
    """Связка «результат процесса клона — разбор — запись `canary_runs`»."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.dest = self.tmp / "clone"
        entry = self.dest / canary.CANARY_DRIVE_ENTRY
        entry.parent.mkdir(parents=True)
        entry.write_text("# вход ведения\n", encoding="utf-8")
        self.template = self.tmp / "canary-status-sort.md"
        self.template.write_text("# Учебная задача\n", encoding="utf-8")
        self.result_path = self.tmp / "canary-drive-result.json"

    def write_result(self, steps: list) -> dict:
        data = {"task_id": "01CLONETASK", "head": HEAD, "escalated": True,
                "metrics": metrics_for(steps), "steps": steps}
        self.result_path.write_text(json.dumps(data, ensure_ascii=False),
                                    encoding="utf-8")
        return data

    def run_and_read_row(self) -> tuple:
        dest = self.dest

        @contextlib.contextmanager
        def fake_clone(*_args, **_kwargs):
            yield dest

        db = self.tmp / "state.db"
        with mock.patch.object(config, "DB", db), \
                mock.patch.object(canary, "_ephemeral_clone", fake_clone), \
                mock.patch.object(canary, "_drive_in_clone",
                                  return_value=(0, "лог клона\n",
                                                self.result_path)), \
                mock.patch("builtins.print"):
            canary._run_one_task(self.template, "20261014T000000Z", 2.0,
                                 target_sha=HEAD, sha_label="проверяемый")
        conn = sqlite3.connect(str(db))
        self.addCleanup(conn.close)
        return conn.execute(
            "SELECT escalation_roles, escalations, verdict FROM canary_runs"
        ).fetchone()

    def test_ac1_run_row_carries_analyst_and_spec_auditor(self):
        """Прогон с журналом AC-1 пишет `escalation_roles = analyst,spec_auditor`, `escalations = 2`.

        Ловит мутацию: пульт не передаёт `steps` в запись строки (или
        вычисляет роли только из `metrics`, где ролей нет) — колонка
        остаётся `NULL`; либо маркер ищется соседней записью и строка несёт
        `unknown,unknown`.
        """
        self.write_result(ac1_steps())
        roles, escalations, verdict = self.run_and_read_row()
        self.assertEqual((roles, escalations), ("analyst,spec_auditor", 2))
        self.assertEqual(verdict, "green")

    def test_ac4_result_without_new_metrics_field_is_accepted_and_row_has_roles(self):
        """Результат клона с полями `metrics` кода до задачи принимается, роли — из `steps`.

        Разбор результата `_read_drive_result` не отказывает такому файлу,
        а строка прогона с журналом AC-11 (а) несёт `analyst,unknown`.

        Ловит мутацию: в `_DRIVE_METRIC_FIELDS` добавлено обязательное поле
        ролей — результат клона старого кода отклоняется («записал
        результат без полей: metrics.…»), прогон становится `drive_failed`
        без ролей.
        """
        data = self.write_result(ac11a_steps())
        self.assertEqual(set(data["metrics"]), set(MAIN_METRIC_FIELDS))
        result, problem = canary._read_drive_result(self.result_path)
        self.assertIsNone(problem)
        self.assertIsNotNone(result)
        roles, escalations, verdict = self.run_and_read_row()
        self.assertEqual((roles, escalations), ("analyst,unknown", 2))
        self.assertEqual(verdict, "green")


class AdmissionThresholdsTest(unittest.TestCase):

    def test_ac10_admission_thresholds_unchanged(self):
        """Пороги допуска ADR-0019 п.5 задачей не тронуты: три чистых, два шаблона, средний класс.

        Ловит мутацию: правка критерия заодно снижает
        `ADMIT_MIN_CLEAN_RUNS`/`ADMIT_MIN_TEMPLATES` или переименовывает
        класс «средний», условие которого держит допуск.
        """
        self.assertEqual(models.ADMIT_MIN_CLEAN_RUNS, 3)
        self.assertEqual(models.ADMIT_MIN_TEMPLATES, 2)
        self.assertEqual(models.TEMPLATE_MEDIUM, "средний")


if __name__ == "__main__":
    unittest.main()
