"""Тесты свежести вердикта ревью (см. tasks/T004/SPEC.md).

Сценарии гоняются на временной БД: config.DB и config.TASKS подменяются
на tmpdir, команды FSM вызываются напрямую.

НЕОСЛАБЛЯЕМЫЕ ТЕСТЫ (ADR-0002, принцип целостности): кодируют инварианты
«вердикт ревьювера учитывается FSM ровно один раз» и «лимит итераций
ревью не съедается повторно» (README «Инварианты» 3, docs/design.md §4).
Ослабить, заскипать или удалить их может только Оператор отдельным ADR;
перечень «инвариант → тест → откуда» — docs/invariants.md.
"""
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (artifacts, catalog, config, fsm,  # noqa: E402
                          gitcmd, review, runner, store)
from tests.sandbox import (SpyRun, capture, capture_new_task_id,  # noqa: E402
                           disk_backed_ls_tree_files, disk_backed_show,
                           fake_git)

REPO_ROOT = Path(__file__).resolve().parent.parent


# Заготовки валидны по guard: с T017 он вызывается на каждом переходе
# `advance` и артефакт без обязательных секций задачу не двигает.
REVIEW_MD = """---
task: {task}
type: review
author_role: reviewer
status: {status}
iteration: {iteration}
schema_version: 1
---

# REVIEW: проверка

## Соответствие SPEC

## Замечания

## Вердикт

## Проверено исполнением
`python3 -m unittest discover -s tests` — зелёный.
"""

PLAN_READY_MD = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: проверка

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""


class FreshVerdictIterationTest(unittest.TestCase):
    def test_next_iteration_is_fresh(self):
        self.assertEqual(artifacts.fresh_verdict_iteration({"iteration": "2"}, 1), 2)

    def test_first_verdict_is_fresh(self):
        self.assertEqual(artifacts.fresh_verdict_iteration({"iteration": "1"}, 0), 1)

    def test_already_counted_iteration_is_stale(self):
        self.assertIsNone(artifacts.fresh_verdict_iteration({"iteration": "1"}, 1))

    def test_older_iteration_is_stale(self):
        self.assertIsNone(artifacts.fresh_verdict_iteration({"iteration": "1"}, 2))

    def test_missing_iteration_is_stale(self):
        self.assertIsNone(artifacts.fresh_verdict_iteration({}, 0))

    def test_unparsable_iteration_is_stale(self):
        self.assertIsNone(artifacts.fresh_verdict_iteration({"iteration": "две"}, 0))

    def test_iteration_with_trailing_spaces(self):
        self.assertEqual(artifacts.fresh_verdict_iteration({"iteration": " 3 "}, 2), 3)


class ReviewFreshnessScenarioTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        # `ROOT` тоже уводится (SPEC T049: холодный старт сканирует его для
        # посева счётчика — непропатченный ROOT читал бы реальное дерево
        # пульта); `templates/`/`skills/` копируются рядом — `cmd_new`
        # читает `templates/SPEC.md`, `cmd_run` читает промпт роли из
        # `skills/*.md`, оба уже из песочницы.
        shutil.copytree(REPO_ROOT / "templates", root / "templates")
        shutil.copytree(REPO_ROOT / "skills", root / "skills")

        for attr, value in (("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs"),
                            ("ROOT", root),
                            ("PROJECTS", root / ".artel" / "projects"),
                            ("TARGETS", root / "targets.yaml"),
                            # Курируемый слой ролей (T019): каталог заводит
                            # запуск шага — пусть заводит в песочнице, а не
                            # в .artel/ репозитория.
                            ("ROLE_HOME", root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             root / ".artel" / "home" / ".claude"),
                            ("BACKUP_MARKER", root / ".artel" / "backup-marker"),
                            # `cmd_new` (SPEC T048) сам заводит ветку и
                            # worktree через `gitcmd`.
                            ("WORKTREES", root / ".artel" / "worktrees")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        # Ревью-пакет (T011) собирается настоящим git. В песочнице его нет —
        # подменяем сам вызов: тестам этого модуля важен номер итерации в
        # промпте, а не содержимое diff (оно проверяется отдельно,
        # test_review_package.py).
        git_patcher = mock.patch.object(gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        # A7 (generic-путь заведения, AC-5): `cmd_new` коммитит артефакты
        # плотницки, минуя `gitcmd.git` (фейк выше) — без этого патча
        # `cmd_new` падает `sys.exit` («git не ответил»).
        spy_patcher = mock.patch.object(gitcmd.subprocess, "run", SpyRun())
        spy_patcher.start()
        self.addCleanup(spy_patcher.stop)
        # `artifact_source.resolve` теперь ВСЕГДА `foreign=True` — FSM
        # читает REVIEW.md/PLAN.md через `gitcmd.show`/`ls_tree_files`;
        # эта песочница без настоящего git ведёт диск `config.TASKS` как
        # единственный источник истины (тем же приёмом, что и
        # `write_review`/`write_plan_ready` ниже).
        show_patcher = mock.patch.object(gitcmd, "show", disk_backed_show)
        show_patcher.start()
        self.addCleanup(show_patcher.stop)
        ls_patcher = mock.patch.object(gitcmd, "ls_tree_files",
                                       disk_backed_ls_tree_files)
        ls_patcher.start()
        self.addCleanup(ls_patcher.stop)
        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)
        pf_patcher = mock.patch(
            "orchestrator.doctor.preflight_checks",
            lambda role, target: [])
        pf_patcher.start()
        self.addCleanup(pf_patcher.stop)

        self.capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(
            catalog.cmd_new, "Проверка вердикта")
        # REVIEW.md/PLAN.md здесь кладутся на диск НАПРЯМУЮ (не через
        # `cmd_new`, требование 4 — он пишет в worktree, не в
        # `config.TASKS`); песочница не на «чужой ветке» в смысле
        # `gitcmd.on_foreign_branch` (фейк `gitcmd.git` держит
        # `current_branch()` пустым), так что fsm читает их отсюда же.
        self.tdir = config.TASKS / self.TASK
        self.tdir.mkdir(parents=True, exist_ok=True)
        self.set_state("review")
        self.write_plan_ready()

    # ------------------------------------------------------------ утилиты

    capture = staticmethod(capture)

    def task_row(self) -> sqlite3.Row:
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def write_review(self, status: str, iteration: int) -> None:
        (self.tdir / "REVIEW.md").write_text(
            REVIEW_MD.format(task=self.TASK, status=status, iteration=iteration),
            encoding="utf-8")

    def write_plan_ready(self) -> None:
        (self.tdir / "PLAN.md").write_text(
            PLAN_READY_MD.format(task=self.TASK), encoding="utf-8")

    def journal_actions(self) -> list[tuple[str, str]]:
        return [(r["action"], r["detail"]) for r in store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]

    def back_to_review_after_verifying_reject(self) -> None:
        """review(approved #1) → verifying → reject → in_dev → review.

        SPEC T079 вставила `verifying` между `review` и `acceptance`
        (requirement 4): свежий approved-вердикт больше не ведёт
        напрямую в `acceptance`, и `reject` (requirement 8, AC-10) с
        T079 применим и к `verifying`, не только к `acceptance` —
        реализует ту же проверку «возврат требует нового вердикта» без
        необходимости зеленить CI веткой ради захода в `acceptance`.
        """
        self.write_review("approved", 1)
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.task_row()["state"], "verifying")
        self.capture(fsm.cmd_reject, self.TASK, "критерий 2 не выполнен")
        self.assertEqual(self.task_row()["state"], "in_dev")
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.task_row()["state"], "review")

    # ----------------------------------------------------------- сценарии

    def test_stale_approved_does_not_pass_after_verifying_reject(self):
        self.back_to_review_after_verifying_reject()

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.task_row()["state"], "review")
        self.assertIn("уже учтён", out)
        self.assertIn("iteration: 2", out)

    def test_stale_verdict_is_journaled(self):
        self.back_to_review_after_verifying_reject()

        self.capture(fsm.cmd_advance, self.TASK)

        rejected = [d for a, d in self.journal_actions() if a == "переход отклонён"]
        self.assertEqual(len(rejected), 1)
        self.assertIn("уже учтён", rejected[0])

    def test_fresh_verdict_passes_to_verifying(self):
        self.back_to_review_after_verifying_reject()
        self.capture(fsm.cmd_advance, self.TASK)  # старый вердикт не провозит

        self.write_review("approved", 2)
        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.task_row()["state"], "verifying")

    def test_changes_requested_counted_once(self):
        self.write_review("changes_requested", 1)
        self.capture(fsm.cmd_advance, self.TASK)
        self.assertEqual(self.task_row()["state"], "in_dev")
        self.assertEqual(self.task_row()["review_iters"], 1)

        self.capture(fsm.cmd_advance, self.TASK)  # in_dev -> review, PLAN ready
        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.task_row()["state"], "review")
        self.assertIn("уже учтён", out)
        # лимит итераций тот же вердикт второй раз не съедает
        self.assertEqual(self.task_row()["review_iters"], 1)

    def test_first_verdict_passes_to_verifying(self):
        """SPEC T079, требование 4: review->acceptance напрямую больше
        нет — свежий approved ведёт в verifying (ждёт зелёного CI)."""
        self.write_review("approved", 1)

        self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.task_row()["state"], "verifying")
        self.assertEqual(self.task_row()["reviewed_iter"], 1)

    def test_draft_review_still_waits_for_verdict(self):
        self.write_review("draft", 1)

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.task_row()["state"], "review")
        self.assertIn("жду вердикта", out)

    def test_reviewer_prompt_asks_for_next_iteration(self):
        self.back_to_review_after_verifying_reject()

        with mock.patch("orchestrator.runner.spawn_agent") as popen_mock:
            proc = mock.MagicMock(**{"wait.return_value": 0})
            proc.stdout.__iter__.return_value = iter([])
            popen_mock.return_value = proc
            self.capture(runner.cmd_run, self.TASK)

        # Промпт с T017 уходит агенту файлом на stdin, а не аргументом argv.
        prompt = Path(popen_mock.call_args.kwargs["stdin"].name).read_text(
            encoding="utf-8")
        self.assertIn("iteration: 2", prompt)


class MigrationTest(unittest.TestCase):
    def test_old_db_gets_reviewed_iter_column(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db_path = Path(tmp.name) / ".artel" / "state.db"
        db_path.parent.mkdir()

        old = sqlite3.connect(db_path)
        old.executescript(
            """
            CREATE TABLE tasks (
              id TEXT PRIMARY KEY, title TEXT, state TEXT, branch TEXT,
              review_iters INTEGER DEFAULT 0, accept_rejects INTEGER DEFAULT 0,
              budget_usd REAL, spent_usd REAL DEFAULT 0,
              created_at TEXT, updated_at TEXT
            );
            INSERT INTO tasks (id, state) VALUES ('T001', 'review');
            """
        )
        old.commit()
        old.close()

        with mock.patch.object(config, "DB", db_path):
            row = store.db().execute("SELECT * FROM tasks WHERE id='T001'").fetchone()

        self.assertEqual(row["reviewed_iter"], 0)


if __name__ == "__main__":
    unittest.main()
