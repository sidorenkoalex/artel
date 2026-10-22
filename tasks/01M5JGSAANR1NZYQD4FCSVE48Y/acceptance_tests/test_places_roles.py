"""Места шагов ролей и команд в контексте задачи: чекпоинт, засчитывание долгоживущего файла test_author, `amend-tests`, предпроверка, подтяжка main, матрица мандата, команда `knowledge` — профиль компонента задачи (AC-22), отказ `for_task` трёх вариантов зон (AC-24) и исход строки таблицы (AC-9).

Группа: разовый
Красен до реализации: места берут `decide(target)` либо `for_task` без зон — у учебной записи из двух компонентов это отказ «… исполняется после G1б»: у задачи на `frontend` свой долгоживущий файл `frontend` не коммитится чекпоинтом и не признаётся своим, засчитывание даёт запись отказа, `amend-tests`/предпроверка/подтяжка отказывают, матрица не засчитывает путь области `frontend`; у задачи с отказом `for_task` тексты исходов не несут текстов AC-3.

Предмет — места таблицы «Места задачи и исход при отказе `for_task`» по
файлу и строке SPEC: часть — публичные входы (`checkpoint.
commit_success_checkpoint`, `checkpoint.restore_out_of_bounds_deletions`,
`preflight.cmd_preflight`, `mandate.matrix_refusals`,
`knowledge_cards.cmd_knowledge`), часть — закрытые функции мест
(`runner._missing_required_artifact`, `amend._profile_or_exit`/
`_task_profile`/`_group_line_errors`, `pull._materialize_and_run_plank`):
сквозной шаг роли и подтяжка требуют агента и форджа. Файл разовый: после
мержа прямой вызов места теряет смысл «места таблицы».

Стенд — `tests.sandbox.RealGitSandbox` с bare `origin`: `targets.yaml`
песочницы с учебным проектом `_training` (`backend`/`frontend`), клон
проекта с `origin`, рабочая копия задачи заводится пультом
(`workspace.ensure`). Подменены только внешние источники подтяжки
(ссылка документов, выкладка и прогон планки).

Провалидировано временным стабом реализации (удалён, не закоммичен):
`for_task` по зонам задачи и места файла на `for_task` — все методы файла
зелёные.
"""
import contextlib
import io
import random
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _training import (NOT_SET, NOT_TOUCHED, REFUSAL_VARIANTS,  # noqa: E402
                       ZONES, check_variant_text, outcome_text, patch_all,
                       training_entry, ulid)

from orchestrator import (acceptance, amend, artifact_branch,  # noqa: E402
                          artifact_source,
                          catalog, checkpoint, config, knowledge_cards,
                          preflight, pull, runner, store, workspace)
from orchestrator.advance_gates import mandate  # noqa: E402
from tests.sandbox import RealGitSandbox, capture, make_project_repo  # noqa: E402

ARTIFACT = "refs/artifacts/T"
NOT_COVERED = "свойство остаётся и не покрыто"
HEADERS = ("Что меняется",
           "Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка)",
           "Остаётся ли свойство после изменения",
           "Чем покрыто после (тест файл:строка) или «не покрыто»",
           "Решение")


def matrix(element: str, covered: str) -> str:
    row = (f"`{element}`", "тест компонента", "остаётся", covered, "ок")
    return ("## Матрица неослабления\n\n"
            "| " + " | ".join(HEADERS) + " |\n"
            + "|" + "---|" * len(HEADERS) + "\n"
            + "| " + " | ".join(row) + " |\n")


class RolesSandbox(RealGitSandbox):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.add_synced_origin()
        self.project = "uch" + "".join(self.rng.choice("abcdefghkmnp")
                                       for _ in range(5))
        text = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(text.rstrip("\n") + "\n"
                                  + training_entry(self.project), encoding="utf-8")
        self.clone = make_project_repo(self.project)
        capture(catalog.cmd_init)

    def note(self, text: str = "") -> str:
        return f"зерно: {self.seed}; {text}"

    def commit_base(self, files: dict) -> None:
        for rel, body in files.items():
            path = self.clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        self.git("-C", str(self.clone), "add", "-A")
        self.git("-C", str(self.clone), "commit", "-q", "-m", "база")
        self.git("-C", str(self.clone), "push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    def task(self, variant: str, state: str = "in_dev", task_id=None):
        task_id = task_id or ulid(self.rng)
        branch = f"task/{task_id.lower()}-uch"
        store.insert_task(self.conn, task_id, f"Задача {variant}", state,
                          branch, self.project, 25.0)
        if ZONES[variant] is not None:
            store.update_task(self.conn, task_id, zones=ZONES[variant])
        wt, error = workspace.ensure(task_id, branch, self.project)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        return task_id, Path(wt)

    def write(self, wt: Path, files: dict) -> None:
        for rel, body in files.items():
            path = wt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")

    def head_files(self, wt: Path) -> set:
        return set(self.git("-C", str(wt), "ls-tree", "-r", "--name-only",
                            "HEAD").split())

    def journal(self, task_id: str, action: str) -> list:
        return [r["detail"] or "" for r in store.task_steps(self.conn, task_id)
                if r["action"] == action]

    def journal_text(self, task_id: str) -> str:
        return "\n".join(f"{r['action']}: {r['detail'] or ''}"
                         for r in store.task_steps(self.conn, task_id))

    @staticmethod
    def own_frontend(task_id: str) -> str:
        return f"frontend/src/ui/btn.{task_id.lower()}.test.jsx"

    @staticmethod
    def own_backend(task_id: str) -> str:
        return f"backend/tests/test_{task_id.lower()}_x.py"

    # --- места -----------------------------------------------------------

    def run_test_author_checkpoint(self, variant: str):
        task_id, wt = self.task(variant, "tests_writing")
        own, foreign = self.own_frontend(task_id), self.own_backend(task_id)
        self.write(wt, {own: "// свой\n", foreign: "# чужой\n"})
        with contextlib.redirect_stdout(io.StringIO()):
            checkpoint.commit_success_checkpoint(self.conn, task_id, "test_author")
        return task_id, wt, own, foreign

    def restore(self, variant: str):
        task_id = ulid(self.rng)
        own = self.own_frontend(task_id)
        self.commit_base({own: "// свой\n"})
        task_id, wt = self.task(variant, "in_dev", task_id)
        (wt / own).unlink()
        with contextlib.redirect_stdout(io.StringIO()):
            restored = checkpoint.restore_out_of_bounds_deletions(
                self.conn, task_id, "developer", wt)
        return task_id, wt, own, restored

    def developer_checkpoint(self, variant: str):
        task_id, wt = self.task(variant, "in_dev")
        own = self.own_frontend(task_id)
        self.write(wt, {own: "// свой\n", "frontend/src/App.jsx": "export const A = 2;\n"})
        with contextlib.redirect_stdout(io.StringIO()):
            checkpoint.commit_success_checkpoint(self.conn, task_id, "developer")
        return task_id, wt, own

    def missing_artifact(self, variant: str):
        task_id, wt = self.task(variant, "tests_writing")
        docs = self.root / "docs" / task_id
        docs.mkdir(parents=True, exist_ok=True)
        value, text = outcome_text(runner._missing_required_artifact,
                                   "test_author", wt, task_id, docs_dir=docs,
                                   conn=self.conn)
        return task_id, value, text

    def pull_plank(self, variant: str):
        task_id, wt = self.task(variant, "in_dev")
        seen = []
        tdir = self.root / "plank" / task_id
        (tdir / "acceptance_tests").mkdir(parents=True, exist_ok=True)
        (tdir / "acceptance_tests" / "a.test.jsx").write_text("// тест\n",
                                                             encoding="utf-8")

        def run(tests_dir, **kwargs):
            seen.append(kwargs)
            return True, ""
        row = store.get_task(self.conn, task_id)
        with patch_all(
                mock.patch.object(artifact_source, "resolve",
                                  return_value=(ARTIFACT, False)),
                mock.patch.object(acceptance, "materialize_from_branch",
                                  return_value=tdir),
                mock.patch.object(acceptance, "plank_present", return_value=True),
                mock.patch.object(acceptance, "run", run)):
            value, text = outcome_text(
                pull._materialize_and_run_plank, self.conn, task_id, row,
                row["branch"], config.MAIN_BRANCH, wt, "in_dev", "basesha",
                lambda *a: None)
        return task_id, value, text, seen

    def preflight(self, variant: str):
        task_id, _wt = self.task(variant, "tests_writing")
        _value, text = outcome_text(preflight.cmd_preflight, task_id)
        return task_id, text


# ===================================================================== AC-22

class Ac22RolePlacesTest(RolesSandbox):

    def test_ac22_test_author_checkpoint_commits_frontend_file(self):
        """Чекпоинт test_author задачи на `frontend` коммитит свой файл по шаблону `frontend`, файл по правилу `backend` — нет.

        Ловит мутацию: `for_task` без зон — запись «долгоживущие тесты не
        закоммичены пультом», ничего не закоммичено; отбор по `backend`.
        """
        task_id, wt, own, foreign = self.run_test_author_checkpoint("frontend")
        head = self.head_files(wt)
        self.assertIn(own, head, self.note(self.journal_text(task_id)))
        self.assertNotIn(foreign, head, self.note())
        self.assertEqual(self.journal(task_id, checkpoint.TEST_AUTHOR_NOT_COMMITTED_ACTION),
                         [], self.note())

    def test_ac22_restore_keeps_own_frontend_deletion(self):
        """Удаление своего долгоживущего файла `frontend` разработчиком задачи на `frontend` не восстанавливается.

        Ловит мутацию: права удаления по `for_task` без зон — своих файлов
        нет, удаление восстановлено из HEAD.
        """
        task_id, wt, own, restored = self.restore("frontend")
        self.assertFalse((wt / own).exists(), self.note(self.journal_text(task_id)))
        self.assertNotIn(own, restored, self.note(str(restored)))

    def test_ac22_developer_checkpoint_own_long_lived(self):
        """Чекпоинт developer задачи на `frontend` признаёт свой долгоживущий файл вне зон своим: он в HEAD, записи о посторонних с ним нет.

        Ловит мутацию: `_own_long_lived` по `for_task` без зон — файл
        посторонний, не закоммичен.
        """
        task_id, wt, own = self.developer_checkpoint("frontend")
        self.assertIn(own, self.head_files(wt), self.note(self.journal_text(task_id)))
        stray = "\n".join(self.journal(task_id, checkpoint.STRAY_WORKTREE_FILES_ACTION))
        self.assertNotIn(own, stray, self.note(stray))

    def test_ac22_missing_artifact_names_frontend_hint(self):
        """Засчитывание test_author задачи на `frontend` без файлов называет долгоживущий файл по шаблону `frontend`.

        Ловит мутацию: `_missing_required_artifact` на `decide(target)` —
        запись «долгоживущий файл не засчитан» и подсказка без
        долгоживущего файла.
        """
        task_id, value, text = self.missing_artifact("frontend")
        self.assertIsInstance(value, str, self.note(text))
        self.assertIn(f".{task_id.lower()}.test.jsx", value, self.note(value))
        self.assertIn("frontend/src/", value, self.note(value))
        self.assertEqual(self.journal(task_id, runner.LONG_LIVED_NOT_COUNTED_ACTION),
                         [], self.note())

    def test_ac22_amend_places_take_frontend(self):
        """`amend-tests` задачи на `frontend`: профиль команды, профиль узлов долгоживущих и проверка строк группы — по `frontend`, без отказа.

        Ловит мутацию: `_task_profile`/`_group_line_errors` на
        `decide(target)` — `None` и отказ; `_profile_or_exit` — выход
        «amend-tests: отказ».
        """
        task_id, _wt = self.task("frontend", "in_dev")
        value, text = outcome_text(amend._profile_or_exit, self.conn, task_id)
        self.assertEqual(getattr(value, "component", None), "frontend", self.note(text))
        self.assertEqual(getattr(amend._task_profile(task_id), "component", None),
                         "frontend", self.note())
        store.update_task(self.conn, task_id, tests_locked_sha="locksha")
        row = store.get_task(self.conn, task_id)
        with mock.patch.object(artifact_branch, "ls_tree", return_value=[]):
            errors = amend._group_line_errors(
                row, f"{config.TASKS.name}/{task_id}/acceptance_tests", [])
        self.assertEqual(errors, [], self.note(str(errors)))

    def test_ac22_preflight_profile_passes(self):
        """Предпроверка задачи на `frontend`: проверка профиля пройдена, долгоживущие и строки группы не пропущены как «профиль не разрешён».

        Ловит мутацию: предпроверка на `decide(target)` — «профиль тестов:
        отказ» с причиной записи.
        """
        _task_id, text = self.preflight("frontend")
        self.assertIn(f"{preflight.CHECK_PROFILE}: пройдена", text, self.note(text))
        self.assertNotIn(preflight.PROFILE_UNRESOLVED, text, self.note(text))

    def test_ac22_pull_runs_plank_by_frontend(self):
        """Подтяжка main задачи на `frontend` гонит планку каналом профиля `frontend`.

        Ловит мутацию: `_task_own_profile` на `profile_of(target)` —
        `ComponentsPending`, подтяжка падает без прогона.
        """
        _task_id, _value, text, seen = self.pull_plank("frontend")
        self.assertEqual(len(seen), 1, self.note(text))
        self.assertEqual(getattr(seen[0].get("command"), "component", None),
                         "frontend", self.note(repr(seen)))

    def test_ac22_matrix_covered_by_frontend_path(self):
        """Матрица мандата на `answer` задачи на `frontend` засчитывает покрытием путь файла области `frontend`.

        Ловит мутацию: `matrix_refusals` с отказом `for_task` откатывается на
        правило `tests/…` — «свойство остаётся и не покрыто».
        """
        task_id, _wt = self.task("frontend", "in_dev")
        element = "frontend/src/ui/old.test.jsx"
        got = mandate.matrix_refusals(matrix(element, "frontend/src/ui/new.test.jsx:1"),
                                      [element], conn=self.conn, task_id=task_id)
        self.assertFalse([r for r in got if NOT_COVERED in r], self.note(str(got)))

    def test_ac22_knowledge_command_output_unchanged(self):
        """Команда `knowledge` задачи на `frontend` выдаёт тот же вывод, что у задачи того же проекта с отказом `for_task` (профиль команда не читает).

        Зелёный с рождения: команда `knowledge` читает карточки проекта по
        записи, не профиль тестов — держит, что перевод мест на `for_task`
        её вывод не меняет.
        """
        outs = []
        for variant in ("frontend", "outside"):
            task_id, _wt = self.task(variant, "in_dev")
            _value, text = outcome_text(knowledge_cards.cmd_knowledge,
                                        [task_id, "::x"])
            outs.append(text.replace(task_id, "<id>"))
        self.assertEqual(outs[0], outs[1], self.note(outs[0]))


# ===================================================================== AC-24

class Ac24RoleRefusalsTest(RolesSandbox):

    def test_ac24_test_author_checkpoint(self):
        """Чекпоинт test_author задачи с отказом `for_task`: запись «долгоживущие тесты не закоммичены пультом» с текстом AC-3, worktree не тронут.

        Ловит мутацию: `for_task` без зон — причина «… после G1б».
        """
        for variant in REFUSAL_VARIANTS:
            with self.subTest(variant=variant):
                task_id, wt, own, _foreign = self.run_test_author_checkpoint(variant)
                detail = "\n".join(self.journal(
                    task_id, checkpoint.TEST_AUTHOR_NOT_COMMITTED_ACTION))
                check_variant_text(self, detail, variant, self.note("чекпоинт"))
                self.assertTrue((wt / own).exists(), self.note("worktree тронут"))

    def test_ac24_restore_deletions(self):
        """Удаление долгоживущего файла у задачи с отказом `for_task` восстанавливается из HEAD, запись восстановления несёт текст AC-3.

        Варианты с заданными зонами: у задачи без зон права удаления
        developer зонами не ограничены (прежнее правило), удаление вне
        разрешённых путей к ней неприменимо.

        Ловит мутацию: запись восстановления без причины `for_task`.
        """
        for variant in ("both", "outside"):
            with self.subTest(variant=variant):
                task_id, wt, own, restored = self.restore(variant)
                self.assertTrue((wt / own).exists(), self.note("не восстановлен"))
                self.assertIn(own, restored, self.note(str(restored)))
                detail = "\n".join(self.journal(task_id,
                                                checkpoint.RESTORED_DELETIONS_ACTION))
                check_variant_text(self, detail, variant, self.note("восстановление"))

    def test_ac24_developer_checkpoint_stray(self):
        """Чекпоинт developer задачи с отказом `for_task` и файлом вне зон: запись «посторонние файлы в worktree» с текстом AC-3.

        Варианты с заданными зонами (у варианта «зоны не заданы» файлов
        «вне зон» без зон нет — условие строки таблицы к нему не
        применимо).

        Ловит мутацию: запись о посторонних без причины `for_task`.
        """
        for variant in ("both", "outside"):
            with self.subTest(variant=variant):
                task_id, wt, own = self.developer_checkpoint(variant)
                self.assertNotIn(own, self.head_files(wt), self.note())
                detail = "\n".join(self.journal(
                    task_id, checkpoint.STRAY_WORKTREE_FILES_ACTION))
                check_variant_text(self, detail, variant, self.note("посторонние"))

    def test_ac24_missing_artifact(self):
        """Засчитывание test_author задачи с отказом `for_task`: запись «долгоживущий файл не засчитан» с текстом AC-3.

        Ловит мутацию: `decide(target)` — причина «… после G1б».
        """
        for variant in REFUSAL_VARIANTS:
            with self.subTest(variant=variant):
                task_id, _value, _text = self.missing_artifact(variant)
                detail = "\n".join(self.journal(task_id,
                                                runner.LONG_LIVED_NOT_COUNTED_ACTION))
                check_variant_text(self, detail, variant, self.note("засчитывание"))

    def test_ac24_amend(self):
        """`amend-tests` задачи с отказом `for_task` отказывает текстом AC-3; проверка строк группы — тем же текстом.

        Ловит мутацию: `_group_line_errors` на `decide(target)` — «… после
        G1б».
        """
        for variant in REFUSAL_VARIANTS:
            with self.subTest(variant=variant):
                task_id, _wt = self.task(variant, "in_dev")
                value, text = outcome_text(amend._profile_or_exit, self.conn, task_id)
                self.assertIsInstance(value, SystemExit, self.note(text))
                check_variant_text(self, text, variant, self.note("amend-tests"))
                row = store.get_task(self.conn, task_id)
                errors = amend._group_line_errors(
                    row, f"{config.TASKS.name}/{task_id}/acceptance_tests", [])
                check_variant_text(self, "\n".join(errors), variant,
                                   self.note("строки группы"))

    def test_ac24_preflight(self):
        """Предпроверка задачи с отказом `for_task`: «профиль тестов: отказ» с текстом AC-3.

        Ловит мутацию: `decide(target)` — причина «… после G1б».
        """
        for variant in REFUSAL_VARIANTS:
            with self.subTest(variant=variant):
                _task_id, text = self.preflight(variant)
                self.assertIn(f"{preflight.CHECK_PROFILE}: отказ", text, self.note(text))
                check_variant_text(self, text, variant, self.note("предпроверка"))

    def test_ac24_pull(self):
        """Подтяжка main задачи с отказом `for_task` отказывает текстом AC-3 без прогона планки.

        Ловит мутацию: `ComponentsPending` с причиной `profile_of` («…
        после G1б»); прогон прежним раннером пульта.
        """
        for variant in REFUSAL_VARIANTS:
            with self.subTest(variant=variant):
                task_id, _value, text, seen = self.pull_plank(variant)
                self.assertEqual(seen, [], self.note("прогон при отказе"))
                check_variant_text(self, f"{text}\n{self.journal_text(task_id)}",
                                   variant, self.note("подтяжка"))

    def test_ac24_matrix(self):
        """Матрица мандата задачи с отказом `for_task` — отказ команды с текстом AC-3, не откат на правило `tests/…`.

        Ловит мутацию: `matrix_refusals` при отказе профиля засчитывает
        `tests/…` — отказов нет.
        """
        for variant in REFUSAL_VARIANTS:
            with self.subTest(variant=variant):
                task_id, _wt = self.task(variant, "in_dev")
                element = "tests/test_old.py"
                got = mandate.matrix_refusals(matrix(element, "tests/test_new.py:1"),
                                              [element], conn=self.conn,
                                              task_id=task_id)
                check_variant_text(self, "\n".join(got), variant, self.note("матрица"))


# ===================================================================== AC-9

class Ac9RoleOutcomesTest(RolesSandbox):

    def test_ac9_role_places_journal_reason(self):
        """Чекпоинт и засчитывание test_author у задачи с зонами вне компонентов пишут запись журнала с причиной; `amend-tests`, предпроверка, подтяжка — отказ; эскалации нет.

        Ловит мутацию: место молча пропускает (нет записи, нет отказа) —
        чекпоинт коммитит, подтяжка гонит планку прежним раннером.
        """
        task_id, wt, own, _foreign = self.run_test_author_checkpoint("outside")
        self.assertTrue(self.journal(task_id, checkpoint.TEST_AUTHOR_NOT_COMMITTED_ACTION))
        self.assertNotIn(own, self.head_files(wt))
        task_id, _value, _text = self.missing_artifact("outside")
        self.assertTrue(self.journal(task_id, runner.LONG_LIVED_NOT_COUNTED_ACTION))
        task_id, _wt = self.task("outside", "in_dev")
        value, _text = outcome_text(amend._profile_or_exit, self.conn, task_id)
        self.assertIsInstance(value, SystemExit)
        _task_id, text = self.preflight("outside")
        self.assertIn(NOT_TOUCHED, text, self.note(text))
        task_id, _value, text, seen = self.pull_plank("outside")
        self.assertEqual(seen, [], self.note(text))
        rows = self.conn.execute(
            "SELECT id FROM tasks WHERE target=? AND state='escalated'",
            (self.project,)).fetchall()
        self.assertEqual(rows, [], self.note("эскалация места"))
        self.assertTrue(NOT_SET)


if __name__ == "__main__":
    unittest.main()
