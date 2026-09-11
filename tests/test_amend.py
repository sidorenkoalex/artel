"""Юнит-тесты orchestrator/amend.py (tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/SPEC.md).

Приёмочные тесты (tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/acceptance_tests/)
кроют AC-1..AC-12 сквозным путём через настоящий git; здесь — чистые
хелперы в изоляции: разбор `git status --porcelain` (модификация,
untracked, переименование), извлечение итоговой строки прогона (сводка
pytest — `N passed`/`M failed, N passed`), окно из НЕСКОЛЬКИХ залоченных
задач program-wide
(сценарий, которого приёмочные тесты сознательно не покрывают — там
окно всегда из одной задачи, см. докстринг
`acceptance_tests/test_ac9_threshold_alert.py`) и счёт событий строго по
task_id окна, а также разбор argv `--reason` (`artel._reason_arg`).

`AmendThenReviewGateTest` (ANSWER-3, вопрос 2) — регресс-тест реальным
git: до этой правки production `amend-tests` сдвигал `tests_locked_sha`
на HEAD worktree'а КОДОВОЙ ветки, а гейт `in_dev -> review` сверяет лок
с АРТЕФАКТНОЙ веткой пульта (`orchestrator/fsm_advance.py::in_dev`,
`lock_ref = branch`) — асимметрия ломала переход сразу же после
успешной правки планки (tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/PLAN.md,
«Эскалация», вопрос 2). Фикстура — тот же рецепт, что `tests/
test_acceptance_tests_flow.py::LockTest` (SPEC.md/PLAN.md/acceptance_tests
пишутся прямо на артефактную ветку, `artifact_branch.commit_files`),
переиспользующая её шаблоны `SPEC_V2`/`PLAN_MD`/`AC_TEST_BOTH_COVERED`
(тот же приём, что `tests/test_answer.py` уже переиспользует `RealPultGitTest`
из `tests/test_git_fixation.py`).
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (amend, artel, artifact_branch, catalog, config,  # noqa: E402
                          fsm, github_adapter, gitcmd, store, workspace)
from tests.sandbox import RealGitSandbox, TmpRootTest, capture  # noqa: E402
from tests.sandbox import capture_new_task_id  # noqa: E402
from tests.test_acceptance_tests_flow import (  # noqa: E402
    AC_TEST_BOTH_COVERED, PLAN_MD, SPEC_V2)


class RunSummaryTest(unittest.TestCase):

    def test_extracts_ran_line_and_ok(self):
        """Из типичного хвоста pytest-прогона извлекается только итоговая
        строка сводки («N passed in Xs»), без предшествующих строк
        session-заголовка и прогресс-точек.

        Ловит мутацию: регулярка `_RUN_SUMMARY` теряет якорь на «passed»/
        «failed» и вместо итоговой строки в журнал (AC-11) уходит весь
        хвост целиком."""
        tail = ("============================= test session starts "
               "==============================\n"
               "collected 2 items\n\n"
               "test_ac.py ..                                                       "
               "[100%]\n\n"
               "============================== 2 passed in 0.01s "
               "===============================\n")
        self.assertEqual(amend._run_summary(tail), "2 passed in 0.01s")

    def test_extracts_ran_line_and_failed_with_count(self):
        """Итоговая строка проваленного прогона несёт число упавших и
        прошедших тестов (`M failed, N passed in Xs`), но не тащит
        traceback конкретного теста.

        Ловит мутацию: регулярка захватывает весь блок FAILURES (не только
        итоговую строку) — журнал AC-11 раздувается диагностикой вместо
        краткого итога."""
        tail = ("=================================== FAILURES "
               "===================================\n"
               "____________________________ test_ac1_first _____________________________\n"
               "AssertionError: намеренно красный тест без маркера\n\n"
               "========================= 1 failed, 0 passed in 0.00s "
               "=========================\n")
        summary = amend._run_summary(tail)
        self.assertIn("1 failed, 0 passed in 0.00s", summary)
        self.assertNotIn("AssertionError", summary,
                         "итоговая строка не обязана тащить весь traceback")

    def test_missing_ran_line_falls_back_to_full_tail(self):
        """Хвост, не похожий на вывод unittest (регулярка не нашла совпадения),
        возвращается как есть, без потери диагностики.

        Ловит мутацию: убранный fallback (`if match else tail.strip()`)
        превращает несовпадение в `None`/исключение вместо всего хвоста."""
        tail = "что-то совсем не похожее на вывод unittest"
        self.assertEqual(amend._run_summary(tail), tail)


class WorktreeChangedPathsTest(unittest.TestCase):

    def _paths(self, output: str, returncode: int = 0):
        fake = lambda *args: subprocess.CompletedProcess(
            list(args), returncode, output, "")
        with mock.patch.object(gitcmd, "git", fake):
            return amend._worktree_changed_paths(Path("/irrelevant"))

    def test_parses_modified_and_untracked_paths(self):
        """И модифицированный (` M`), и untracked (`??`) путь строки
        `git status --porcelain` попадают в список изменённых путей.

        Ловит мутацию: сдвинутый срез `line[3:]` (например `line[2:]`) режет
        первый символ имени файла — AC-3 сравнивал бы с префиксом усечённый
        путь и ошибочно считал бы правку «за пределами» каталога."""
        output = (" M tasks/T001/acceptance_tests/test_ac.py\n"
                 "?? tasks/T001/PLAN.md\n")
        self.assertEqual(
            sorted(self._paths(output)),
            ["tasks/T001/PLAN.md", "tasks/T001/acceptance_tests/test_ac.py"])

    def test_rename_keeps_only_the_new_side(self):
        """Для строки переименования (`R  старый -> новый`) в список попадает
        только новая сторона — старого пути на диске уже нет.

        Ловит мутацию: убранный `.split(" -> ", 1)[1]` оставляет в списке
        старый (уже не существующий) путь либо всю строку `"старый -> новый"`
        одним элементом."""
        output = ("R  tasks/T001/acceptance_tests/old.py -> "
                 "tasks/T001/acceptance_tests/new.py\n")
        self.assertEqual(self._paths(output),
                         ["tasks/T001/acceptance_tests/new.py"])

    def test_blank_lines_are_ignored(self):
        """Пустая строка на конце вывода `git status --porcelain` не
        превращается в фиктивный «изменённый путь».

        Ловит мутацию: убранная проверка `if not line.strip(): continue`
        добавляет в список путь из трёх символов среза пустой строки."""
        output = " M tasks/T001/acceptance_tests/test_ac.py\n\n"
        self.assertEqual(self._paths(output),
                         ["tasks/T001/acceptance_tests/test_ac.py"])

    def test_git_not_responding_returns_none(self):
        """Ненулевой код возврата git — сигнал «git не ответил», функция
        возвращает `None`, а не пустой/частичный список путей.

        Ловит мутацию: убранная проверка `res.returncode != 0` маскирует
        сбой git под «изменений нет» — команда молча продолжила бы с
        `outside=[]` вместо именованного отказа."""
        self.assertIsNone(self._paths("", returncode=128))


class BranchTestsSnapshotTest(unittest.TestCase):
    """`amend._branch_tests_snapshot` (SPEC 01M287TPG0HAVXS8CHBCY679WN,
    требование 3): чтение дерева `acceptance_tests/` на ПРОИЗВОЛЬНОЙ
    git-ревизии (`gitcmd.ls_tree_files`/`gitcmd.show` принимают и sha, и
    имя ветки одинаково) — здесь в изоляции от настоящего git, песочница
    `RealGitSandbox` для чистых веток отказа не нужна."""

    def _snapshot(self, ls_tree_output: str, ls_returncode: int,
                  show_text_by_rel: dict):
        def fake_git(*args):
            if args[0] == "ls-tree":
                return subprocess.CompletedProcess(
                    list(args), ls_returncode, ls_tree_output, "")
            if args[0] == "show":
                rel = args[1].split(":", 1)[1]
                if rel in show_text_by_rel:
                    return subprocess.CompletedProcess(
                        list(args), 0, show_text_by_rel[rel], "")
                return subprocess.CompletedProcess(list(args), 1, "", "not found")
            raise AssertionError(f"неожиданный вызов git: {args}")

        with mock.patch.object(gitcmd, "git", fake_git):
            return amend._branch_tests_snapshot(
                "deadbeef", "tasks/T001/acceptance_tests")

    def test_reads_all_files_at_the_given_revision(self):
        rel = "tasks/T001/acceptance_tests/test_ac.py"
        snapshot = self._snapshot(rel + "\n", 0, {rel: "содержимое\n"})
        self.assertEqual(snapshot, {rel: "содержимое\n"})

    def test_ls_tree_failure_returns_none(self):
        """Ловит мутацию: проверка `paths is None` убрана — сбой
        `ls-tree` (ненулевой код) читался бы как «файлов нет» вместо
        именованного `None` (ложное «нет расхождения» в AC-8)."""
        self.assertIsNone(self._snapshot("", 128, {}))

    def test_show_failure_for_any_file_returns_none(self):
        """Ловит мутацию: файл, не прочитанный `show` (не в дереве этой
        ревизии, git не ответил), тихо пропускается вместо `None` —
        снимок получился бы неполным, сверка AC-7/AC-8 сравнивала бы
        частичные данные как полные."""
        rel = "tasks/T001/acceptance_tests/test_ac.py"
        self.assertIsNone(self._snapshot(rel + "\n", 0, {}))


class TestsSnapshotAndMaterializeTest(RealGitSandbox):
    """`_materialize_tests_if_missing`/`_tests_snapshot`/
    `_artifact_tests_snapshot` (ANSWER-3, вопрос 2) в изоляции: приёмочные
    тесты кроют их только сквозным путём через FSM, здесь — сами хелперы
    отдельно от отказов/лока/журнала."""

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new, "снимок и материализация")
        self.conn = store.db()
        wt_path, error = workspace.ensure(self.TASK, self.row()["branch"])
        self.assertIsNone(error, f"worktree не создан: {error}")
        self.wt_path = wt_path
        self.tdir = wt_path / "tasks" / self.TASK
        self.rel_tests_dir = f"tasks/{self.TASK}/acceptance_tests"
        # `--exclude-standard` (ANSWER-3: __pycache__/*.pyc не в коммит)
        # читает .gitignore из рабочего дерева worktree — не коммичен,
        # git всё равно его учитывает при статусе/ls-files.
        (self.wt_path / ".gitignore").write_text("__pycache__/\n*.pyc\n",
                                                  encoding="utf-8")

    def row(self):
        return store.db().execute("SELECT * FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()

    def test_materialize_fills_missing_directory_from_artifact_branch(self):
        """Если `acceptance_tests/` ещё нет на диске worktree, материализация
        заполняет её текущим содержимым артефактной ветки.

        Ловит мутацию: перепутанный срез префикса при построении `dest`
        (например обрезка `tasks/{id}/` вместо полного пути) кладёт файл не
        туда либо роняет исключение вместо записи содержимого на диск."""
        artifact_branch.commit_files(
            self.TASK,
            {f"tasks/{self.TASK}/acceptance_tests/test_ac.py": "содержимое\n"},
            f"{self.TASK}: acceptance_tests")

        amend._materialize_tests_if_missing(self.TASK, self.tdir)

        self.assertEqual(
            (self.tdir / "acceptance_tests" / "test_ac.py").read_text(
                encoding="utf-8"),
            "содержимое\n")

    def test_materialize_skips_already_present_directory(self):
        """Каталог `acceptance_tests/` уже есть на диске (Оператор уже
        положил туда правку) — материализация его не трогает вовсе.

        Ловит мутацию: убранный ранний `if tests_dir.is_dir(): return`
        заставляет материализацию перезаписать уже внесённую правку Оператора
        содержимым артефактной ветки — правка тихо теряется."""
        (self.tdir / "acceptance_tests").mkdir(parents=True)
        (self.tdir / "acceptance_tests" / "test_ac.py").write_text(
            "правка Оператора\n", encoding="utf-8")

        amend._materialize_tests_if_missing(self.TASK, self.tdir)

        self.assertEqual(
            (self.tdir / "acceptance_tests" / "test_ac.py").read_text(
                encoding="utf-8"),
            "правка Оператора\n",
            "уже существующий каталог не должен перетираться материализацией")

    def test_tests_snapshot_excludes_gitignored_pycache(self):
        """`__pycache__`/`*.pyc`, неизбежный побочный продукт обязательного
        прогона AC-10, не попадает в снимок для коммита в артефактную ветку.

        Ловит мутацию: убранный `--exclude-standard` (или замена его на
        сырой обход каталога) протаскивает `__pycache__` в снимок — коммит
        правки нёс бы байт-кодовый мусор."""
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True)
        (tests_dir / "test_ac.py").write_text("...\n", encoding="utf-8")
        pycache = tests_dir / "__pycache__"
        pycache.mkdir()
        (pycache / "test_ac.cpython-312.pyc").write_bytes(b"\x00\x01")

        snapshot = amend._tests_snapshot(self.wt_path, self.rel_tests_dir)

        self.assertIn(f"{self.rel_tests_dir}/test_ac.py", snapshot)
        self.assertFalse(
            any("__pycache__" in rel for rel in snapshot),
            f"__pycache__ не должен попасть в снимок для коммита: "
            f"{sorted(snapshot)}")

    def test_tests_snapshot_includes_modified_tracked_file(self):
        """Файл `acceptance_tests/`, уже трекнутый КОДОВОЙ веткой задачи
        (сценарий этой самой задачи, заведённой до A7 — `git ls-files
        tasks/<id>/acceptance_tests/` не пуст), и правда изменённый
        Оператором на диске worktree, попадает в снимок с НОВЫМ содержимым.

        Ловит мутацию: `--cached` убран из `ls-files` (регресс к REVIEW.md
        iteration 2/3, R2-F1) — снимок видит только untracked-файлы, правка
        уже трекнутого файла становится невидимой: AC-2 никогда не находит
        разницу с непустым baseline, а `tests_locked_sha` сдвигается на
        коммит, побайтно идентичный родителю — правка Оператора теряется
        молча."""
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True)
        tracked = tests_dir / "test_ac.py"
        tracked.write_text("исходное содержимое\n", encoding="utf-8")
        self.git_wt("add", "--", self.rel_tests_dir)
        self.git_wt("commit", "-q", "-m", "трекнутая планка (сценарий до A7)")
        tracked.write_text("правка Оператора\n", encoding="utf-8")

        snapshot = amend._tests_snapshot(self.wt_path, self.rel_tests_dir)

        self.assertEqual(
            snapshot.get(f"{self.rel_tests_dir}/test_ac.py"),
            "правка Оператора\n".encode("utf-8"),
            f"снимок обязан видеть правку уже трекнутого файла: {snapshot}")

    def git_wt(self, *args: str) -> str:
        res = subprocess.run(["git", "-C", str(self.wt_path), *args],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0,
                         f"git -C {self.wt_path} {' '.join(args)}: {res.stderr}")
        return res.stdout

    def test_artifact_snapshot_matches_disk_snapshot_after_bare_materialize(self):
        """Диск сразу после «голой» материализации (без правки Оператора)
        побайтно совпадает со снимком артефактной ветки — сверка AC-2 не
        должна путать материализацию с реальной правкой.

        Ловит мутацию: потерянный слэш в префиксе `_artifact_tests_snapshot`
        (`f"{rel_tests_dir}"` вместо `f"{rel_tests_dir}/"`) либо портит набор
        ключей baseline, либо случайно подхватывает посторонний файл с тем
        же префиксом имени — снимки расходятся без единой правки Оператора,
        и AC-2 ложно решает, что фиксировать нечего."""
        artifact_branch.commit_files(
            self.TASK,
            {f"tasks/{self.TASK}/acceptance_tests/test_ac.py": "исходное\n"},
            f"{self.TASK}: acceptance_tests")

        amend._materialize_tests_if_missing(self.TASK, self.tdir)

        disk = amend._tests_snapshot(self.wt_path, self.rel_tests_dir)
        baseline = amend._artifact_tests_snapshot(self.TASK, self.rel_tests_dir)
        self.assertEqual(
            disk, baseline,
            "материализация без правки Оператора не должна читаться как "
            "изменение (AC-2)")


class LockedWindowTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        self.conn = store.db()

    def _make_task(self, task_id: str, created_at: str, *, locked: bool,
                   target: str = config.DEFAULT_TARGET) -> None:
        store.insert_task(self.conn, task_id, task_id, "in_dev",
                          f"task/{task_id.lower()}", target,
                          config.DEFAULT_BUDGET_USD)
        self.conn.execute("UPDATE tasks SET created_at=? WHERE id=?",
                          (created_at, task_id))
        if locked:
            store.update_task(self.conn, task_id, tests_locked_sha=f"sha-{task_id}")
        self.conn.commit()

    def test_unlocked_tasks_are_excluded(self):
        """Задача, ещё не дошедшая до фиксации лока (`tests_locked_sha`
        пуст), не попадает в окно вовсе — даже если program-wide она моложе.

        Ловит мутацию: убранный фильтр `if t["tests_locked_sha"]` включает
        незалоченную задачу в окно — порог AC-9 считался бы по задачам,
        которые ещё не проходили `tests_writing -> in_dev`."""
        self._make_task("T001", "2026-09-01 10:00:00Z", locked=True)
        self._make_task("T002", "2026-09-01 11:00:00Z", locked=False)

        self.assertEqual(amend._locked_window_task_ids(self.conn), ["T001"])

    def test_window_keeps_last_five_by_creation_order_program_wide(self):
        """Из 7 залоченных задач разных target окно берёт ровно последние 5
        по порядку заведения (`created_at`), не различая target.

        Ловит мутацию: фильтрация по `config.DEFAULT_TARGET` вместо
        program-wide теряет задачи `other-target` — окно AC-9 считалось бы
        по одному target, а не по всему пульту, как требует SPEC."""
        ids = [f"P{i:03d}" for i in range(1, 8)]  # 7 залоченных задач
        for i, task_id in enumerate(ids):
            target = config.DEFAULT_TARGET if i % 2 == 0 else "other-target"
            self._make_task(task_id, f"2026-09-01 10:{i:02d}:00Z",
                            locked=True, target=target)

        window = amend._locked_window_task_ids(self.conn)

        self.assertEqual(window, ids[-5:],
                         "окно обязано взять последние 5 по порядку "
                         "заведения независимо от target")

    def test_fewer_than_five_locked_tasks_returns_all_of_them(self):
        """Меньше 5 залоченных задач всего — окно составляют все они, без
        падения и без набора несуществующих «пустых» мест.

        Ловит мутацию: срез `locked[-limit:]`, заменённый на срез с
        фиксированной длиной без учёта фактического размера списка, роняет
        `IndexError` либо молча теряет часть задач при недоборе до 5."""
        self._make_task("T001", "2026-09-01 10:00:00Z", locked=True)
        self._make_task("T002", "2026-09-01 11:00:00Z", locked=True)

        self.assertEqual(amend._locked_window_task_ids(self.conn),
                         ["T001", "T002"])


class AmendEventsInWindowTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        self.conn = store.db()
        for task_id in ("T001", "T002"):
            store.insert_task(self.conn, task_id, task_id, "in_dev",
                              f"task/{task_id.lower()}",
                              config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)

    def test_counts_only_amend_events_of_tasks_in_window(self):
        """Считаются только события журнала с действием `AMEND_ACTION`
        («правка планки») — прочие события того же task_id (например
        фиксация sha со стороны FSM) в счёт не идут; повторная правка той
        же задачи — вторая единица счёта (SPEC требование 4).

        Ловит мутацию: убранный фильтр `AMEND_ACTION in s["action"]` считает
        ЛЮБОЕ событие журнала задачи из окна — порог AC-9 срабатывал бы от
        обычных шагов конвейера, не только от правок планки."""
        store.journal(self.conn, "T001", "operator", amend.AMEND_ACTION, "x")
        store.journal(self.conn, "T001", "operator", amend.AMEND_ACTION, "y")
        store.journal(self.conn, "T002", "operator", amend.AMEND_ACTION, "z")
        store.journal(self.conn, "T002", "fsm", "sha зафиксирован",
                      "не должно попасть в счёт")

        self.assertEqual(amend._amend_events_in_window(self.conn, ["T001"]), 2)
        self.assertEqual(
            amend._amend_events_in_window(self.conn, ["T001", "T002"]), 3)

    def test_task_outside_window_is_not_counted(self):
        """Событие «правка планки» задачи, чей `task_id` НЕ входит в
        переданное окно, не учитывается в счёте вовсе.

        Ловит мутацию: счётчик, игнорирующий `window_ids` и суммирующий
        события ВСЕХ задач БД, завышал бы порог AC-9 старыми правками
        задач, давно выпавших из скользящего окна последних 5."""
        store.journal(self.conn, "T002", "operator", amend.AMEND_ACTION, "z")

        self.assertEqual(amend._amend_events_in_window(self.conn, ["T001"]), 0)

    def test_empty_window_counts_zero(self):
        """Пустое окно (например задач, дошедших до лока, ещё нет вовсе) —
        счёт правок равен 0, без исключения на пустом списке.

        Ловит мутацию: цикл `for task_id in window_ids`, заменённый на
        обращение к `window_ids[0]` без проверки длины, роняет `IndexError`
        вместо честного нуля."""
        self.assertEqual(amend._amend_events_in_window(self.conn, []), 0)


# Правка Оператора: содержательно другой текст, по-прежнему покрывает
# AC-1/AC-2 (тот же довод, что AC_TEST_AMENDED_V1 в
# tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/acceptance_tests/_sandbox.py).
AC_TEST_AMENDED = '''"""Красен до реализации: фикстура покрывает оба критерия
SPEC_V2 песочницы (правка Оператора: добавлена вторая проверка AC-1)."""
import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)

    def test_ac1_first_criterion_again(self):
        self.assertEqual(1 + 1, 2)


# AC-2: manual — Оператор проверяет глазами на приёмке
'''


class AmendThenReviewGateTest(RealGitSandbox):
    """ANSWER-3, вопрос 2 — см. докстринг модуля."""

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new,
                                           "amend -> review, гейт лока")
        self.conn = store.db()
        self.branch = artifact_branch.branch_name(self.TASK)
        self.code_branch = self.row()["branch"]
        wt_path, error = workspace.ensure(self.TASK, self.code_branch)
        self.assertIsNone(error, f"worktree не создан: {error}")
        self.wt_path = wt_path
        self.tdir = wt_path / "tasks" / self.TASK
        # Код фичи (self-target, тот же приём, что LockTest.setUp, AC-5):
        # гейт ёмкости diff снимка (`_capacity_gate_refuses`) для self
        # сверяет именно кодовую ветку в config.ROOT.
        (self.wt_path / "feature.txt").write_text("код фичи\n", encoding="utf-8")
        self.git_wt("add", "feature.txt")
        self.git_wt("commit", "-q", "-m", f"{self.TASK}: код фичи")

    def row(self):
        return store.db().execute("SELECT * FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()

    def state(self) -> str:
        return self.row()["state"]

    def git_wt(self, *args: str) -> str:
        res = subprocess.run(["git", "-C", str(self.wt_path), *args],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0,
                         f"git -C {self.wt_path} {' '.join(args)}: {res.stderr}")
        return res.stdout

    def artifact_commit(self, files: dict, message: str) -> None:
        sha = artifact_branch.commit_files(self.TASK, files,
                                           f"{self.TASK}: {message}")
        self.assertTrue(sha, f"коммит {message!r} на артефактную ветку не удался")

    def enter_in_dev(self) -> None:
        self.artifact_commit(
            {f"tasks/{self.TASK}/SPEC.md": SPEC_V2.format(task=self.TASK, extra="")},
            "SPEC")
        capture(fsm.cmd_advance, self.TASK)  # spec_writing -> spec_gate
        sha = gitcmd.head_sha(config.PROJECTS / config.DEFAULT_TARGET)
        capture(fsm.cmd_approve, self.TASK, sha)  # -> tests_writing
        self.assertEqual(self.state(), "tests_writing")

        self.artifact_commit(
            {f"tasks/{self.TASK}/acceptance_tests/test_ac.py": AC_TEST_BOTH_COVERED},
            "acceptance_tests")
        capture(fsm.cmd_advance, self.TASK)  # tests_writing -> in_dev
        self.assertEqual(self.state(), "in_dev")

    def test_amend_then_advance_passes_lock_gate(self):
        """Успешный `amend-tests`, сразу за ним `advance` — переход
        `in_dev -> review` обязан пройти: лок (`tests_locked_sha`) после
        правки указывает на ту же артефактную ветку, с которой гейт его
        сверяет, а не на HEAD (не относящегося к делу) worktree'а
        кодовой ветки.

        Ловит мутацию: `_cmd_amend_tests` сдвигает `tests_locked_sha` на
        `gitcmd.head_sha(wt_path)` (HEAD worktree'а кодовой ветки) вместо
        sha коммита на артефактную ветку — гейт `in_dev` сравнивает лок с
        АРТЕФАКТНОЙ веткой и всегда видит «расхождение» (два физически
        разных дерева), переход отклоняется бесконечно."""
        self.enter_in_dev()
        (self.tdir / "acceptance_tests").mkdir(parents=True, exist_ok=True)
        (self.tdir / "acceptance_tests" / "test_ac.py").write_text(
            AC_TEST_AMENDED, encoding="utf-8")
        self.artifact_commit(
            {f"tasks/{self.TASK}/PLAN.md": PLAN_MD.format(task=self.TASK)}, "PLAN")

        out = capture(amend.cmd_amend_tests, self.TASK,
                      "исправлена опечатка (регресс ANSWER-3, вопрос 2)")
        self.assertEqual(self.state(), "in_dev", f"amend-tests отказал: {out}")

        # ADR-0015: сверка головы на origin переехала на `in_dev ->
        # verifying` — эта песочница не заводит настоящий push к origin,
        # предмет теста — лок acceptance_tests/ после amend-tests, не
        # origin-push (у него свои тесты, `tests/test_github_adapter.py`).
        with mock.patch.object(github_adapter, "ensure_head_in_origin",
                              return_value=(True, "")):
            capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(
            self.state(), "verifying",
            "гейт in_dev -> verifying обязан пройти сразу после успешной "
            "правки планки (ADR-0015 — цель перехода in_dev теперь "
            "verifying, не review)")


AC_TEST_EXTRA_UNCHANGED = '''"""Зелёный с рождения: файл-контроль amend --from-branch, остаётся
побайтно неизменным между локом и последующей правкой — не должен
попасть в список отличающихся файлов журнала (SPEC
01M287TPG0HAVXS8CHBCY679WN, требование 3)."""
import unittest


class UnchangedTest(unittest.TestCase):
    def test_noop(self):
        self.assertTrue(True)
'''


class AmendFromBranchDivergenceDetailTest(RealGitSandbox):
    """`amend.cmd_amend_tests(..., from_branch=True)` (SPEC
    01M287TPG0HAVXS8CHBCY679WN, требование 3) — деталь, которую
    приёмочные тесты этой же задачи (`tasks/01M287TPG0HAVXS8CHBCY679WN/
    acceptance_tests/test_ac7_ac8_ac9_amend_from_branch.py`) не кроют:
    правка ЗАТРАГИВАЕТ несколько файлов сразу (не один произвольный), а
    файл каталога, оставшийся ПОБАЙТНО неизменным, в список отличий не
    попадает."""

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(
            catalog.cmd_new, "amend --from-branch, несколько файлов")
        self.conn = store.db()
        self.branch = artifact_branch.branch_name(self.TASK)
        self._enter_in_dev()

    def row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def artifact_commit(self, files: dict, message: str) -> str:
        sha = artifact_branch.commit_files(
            self.TASK, files, f"{self.TASK}: {message}")
        self.assertTrue(sha, f"коммит {message!r} не удался")
        return sha

    def _enter_in_dev(self) -> None:
        self.artifact_commit(
            {f"tasks/{self.TASK}/SPEC.md": SPEC_V2.format(task=self.TASK, extra="")},
            "SPEC")
        capture(fsm.cmd_advance, self.TASK)  # spec_writing -> spec_gate
        sha = gitcmd.head_sha(config.PROJECTS / config.DEFAULT_TARGET)
        capture(fsm.cmd_approve, self.TASK, sha)  # -> tests_writing

        self.artifact_commit(
            {f"tasks/{self.TASK}/acceptance_tests/test_ac.py": AC_TEST_BOTH_COVERED,
             f"tasks/{self.TASK}/acceptance_tests/test_extra.py":
                 AC_TEST_EXTRA_UNCHANGED},
            "acceptance_tests")
        capture(fsm.cmd_advance, self.TASK)  # tests_writing -> in_dev

    def journal_texts(self) -> list:
        return [f"{s['action']} {s['detail']}"
               for s in store.task_steps(self.conn, self.TASK)]

    def test_lists_every_differing_file_and_excludes_the_unchanged_one(self):
        new_sha = self.artifact_commit(
            {f"tasks/{self.TASK}/acceptance_tests/test_ac.py": AC_TEST_AMENDED,
             f"tasks/{self.TASK}/acceptance_tests/test_second.py": AC_TEST_AMENDED,
             f"tasks/{self.TASK}/acceptance_tests/test_extra.py":
                 AC_TEST_EXTRA_UNCHANGED},
            "правка планки: два файла сразу, третий побайтно тот же")

        amend.cmd_amend_tests(self.TASK, "два файла сразу", from_branch=True)

        self.assertEqual(self.row()["tests_locked_sha"], new_sha)
        texts = self.journal_texts()
        matched = [t for t in texts if amend.AMEND_ACTION in t]
        self.assertTrue(matched, f"нет записи «{amend.AMEND_ACTION}»: {texts}")
        detail = matched[-1]
        self.assertIn("test_ac.py", detail)
        self.assertIn("test_second.py", detail)
        self.assertNotIn("test_extra.py", detail,
                         "неизменённый файл не должен попасть в список отличий")


class ReasonArgTest(unittest.TestCase):

    def test_flag_absent_returns_none(self):
        """Argv без `--reason` вовсе — разбор возвращает `None`, отличимый
        от пустой строки (AC-5 обязана различать «флага нет» и «флаг пуст»).

        Ловит мутацию: разбор, возвращающий `""` вместо `None` при
        отсутствующем флаге, стирает различие, которое `_cmd_amend_tests`
        всё равно сводит к одному отказу — но ломает любой ДРУГОЙ вызывающий
        код, полагающийся на `None` как признак «флаг не передан»."""
        self.assertIsNone(artel._reason_arg(["T001"]))

    def test_flag_with_value_returns_it(self):
        """`--reason <значение>` — разбор возвращает ровно переданное
        значение, без искажений.

        Ловит мутацию: индексация следующего элемента со сдвигом (например
        `argv[i+2]` вместо `argv[i+1]`) возвращает не то значение либо
        падает `IndexError` на однословном основании."""
        self.assertEqual(
            artel._reason_arg(["T001", "--reason", "опечатка"]), "опечатка")

    def test_flag_with_empty_string_value_returns_empty_string(self):
        """`--reason ""` (флаг присутствует, значение — пустая строка) —
        разбор возвращает именно пустую строку, не `None`.

        Ловит мутацию: проверка `if value:` вместо `if value is not None`
        на месте разбора схлопывает пустую строку с «флага нет» — AC-5
        неотличим бы от AC-4/иного отказа по логам, хотя причина разная."""
        self.assertEqual(artel._reason_arg(["T001", "--reason", ""]), "")

    def test_dangling_flag_without_value_exits(self):
        """`--reason` последним элементом argv, без значения после него —
        именованный `SystemExit`, а не падение с трассировкой.

        Ловит мутацию: убранная проверка границы списка (`i + 1 <
        len(argv)`) роняет необработанный `IndexError` вместо понятного
        сообщения об ошибке использования команды."""
        with self.assertRaises(SystemExit) as ctx:
            artel._reason_arg(["T001", "--reason"])
        self.assertIn("--reason", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
