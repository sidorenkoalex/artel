"""Приёмочные тесты AC-6/AC-7 (tasks/01M1NKTF173WV5CPDZ1C3WW69K/SPEC.md):
автокоммит шага не перезаписывает файл, изменившийся в артефактной
ветке ПОСЛЕ старта шага, если сама роль его в этом шаге не трогала —
заводит alert `kind=incident` с сообщением про конфликт артефактов
(AC-6); остальные, реально изменённые ролью файлы коммитятся автокоммитом
как обычно, конфликт по одному файлу их не блокирует (AC-7).

Красен до реализации: `checkpoint._commit_external_step_artifacts`
сегодня сравнивает диск только с ТЕКУЩЕЙ головой артефактной ветки на
момент коммита, не с версией на старте шага, — правка Оператора,
случившаяся между стартом шага и его концом, сегодня молча
перезаписывается устаревшим диском роли (инцидент 04.09 из «Контекста»
SPEC), а не защищается конфликт-гвардом с alert'ом; AC-6 падает на
отсутствии alert'а и на перезаписи, AC-7 (позитивная часть того же
сценария) проверяет, что параллельная правка другого файла не
пострадала бы даже без гварда — сам по себе не ловит регресс гварда, но
фиксирует контракт «конфликт по одному файлу не блокирует перенос
остальных» на будущее.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import alerts, artifact_branch, checkpoint, config, gitcmd, runner, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

TARGET = "ac6conflicttarget"
TASK = "01AC6AC7CONFLICTGUARD"


class ConflictGuardOnAutocommitTest(RealGitSandbox):

    def setUp(self):
        super().setUp()
        store.insert_task(store.db(), TASK, "Конфликт-гвард автокоммита",
                          "in_dev", f"task/{TASK.lower()}-x", TARGET,
                          config.DEFAULT_BUDGET_USD)
        self.commit_artifact({
            f"tasks/{TASK}/SPEC.md": "SPEC v1",
            f"tasks/{TASK}/PLAN.md": "PLAN v1",
        }, "исходное состояние")
        # Старт шага: материализация ГОЛОВЫ артефактной ветки на диск роли
        # (AC-1) — тот же вызов, каким пользуется реальный агентный шаг
        # (`runner.run_agent_once`).
        self.cwd = runner.role_cwd(store.db(), TASK, TARGET)
        self.task_dir = self.cwd / "tasks" / TASK

    def commit_artifact(self, files: dict, message: str) -> None:
        sha = artifact_branch.commit_files(TASK, files, f"{TASK}: {message}")
        self.assertTrue(sha, "фикстура не закоммитила артефактную ветку")

    def artifact_text(self, rel: str):
        branch = artifact_branch.branch_name(TASK)
        text, _ = gitcmd.show(branch, rel)
        return text

    def test_ac6_operator_edit_mid_step_is_not_overwritten_and_raises_incident(self):
        """Оператор правит SPEC.md на гейте ПОСЛЕ старта шага; роль SPEC.md
        в этом шаге не трогает (диск остаётся с версией старта шага) —
        автокоммит обязан сохранить правку Оператора и завести alert.

        Ловит мутацию: конфликт-гвард не реализован (сравнение только с
        ТЕКУЩЕЙ головой ветки) — SPEC v2 Оператора перезаписывается
        обратно устаревшим SPEC v1 с диска роли, alert не заводится.
        """
        self.commit_artifact({f"tasks/{TASK}/SPEC.md": "SPEC v2 (Оператор)"},
                             "правка Оператора на гейте")

        checkpoint.commit_step_artifacts(store.db(), TASK, "developer")

        self.assertEqual(
            self.artifact_text(f"tasks/{TASK}/SPEC.md"), "SPEC v2 (Оператор)",
            "автокоммит не имеет права перезаписать правку Оператора "
            "устаревшим диском роли")
        incidents = [a["message"] for a in alerts.open_alerts(store.db(),
                                                               "incident")]
        self.assertTrue(
            any("конфликт артефактов: правка в ветке новее рабочего "
               "каталога" in m for m in incidents),
            f"alert kind=incident с этим текстом не найден среди: {incidents}")

    def test_ac7_a_file_the_role_actually_changed_still_commits_normally(self):
        """Тот же конфликт по SPEC.md, но роль параллельно меняет СВОЙ файл
        (PLAN.md) на этом же шаге — его собственная правка обязана дойти
        до артефактной ветки, конфликт по другому файлу её не блокирует.

        Ловит мутацию: обнаружение конфликта по одному файлу отменяет
        коммит ВСЕГО шага целиком (например, ранний `return ""` при
        первом найденном конфликте) — PLAN.md роли тоже не долетает до
        ветки.
        """
        self.commit_artifact({f"tasks/{TASK}/SPEC.md": "SPEC v2 (Оператор)"},
                             "правка Оператора на гейте")
        (self.task_dir / "PLAN.md").write_text("PLAN v2 (разработчик)",
                                               encoding="utf-8")

        checkpoint.commit_step_artifacts(store.db(), TASK, "developer")

        self.assertEqual(self.artifact_text(f"tasks/{TASK}/PLAN.md"),
                         "PLAN v2 (разработчик)",
                         "правка роли по НЕконфликтующему файлу обязана "
                         "дойти до ветки несмотря на конфликт по SPEC.md")


if __name__ == "__main__":
    unittest.main()
