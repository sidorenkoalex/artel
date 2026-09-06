"""Приёмочные тесты SPEC 01M1REVMB50SND1KJ3CYQMV2ST: `detail` эскалации
«конфликт подтяжки main» называет конфликтные файлы и несёт хвост
`stdout`/`stderr` `git merge`, а не только `stderr` (который git не
использует для «CONFLICT (content): …» и «Automatic merge failed» —
они идут в `stdout`).

Красен до реализации: `_pull_main_or_escalate` (`orchestrator/fsm.py`)
на строке записи `detail` конфликта подтяжки сейчас читает только
`merge.stderr.strip()[:500]` — ни список конфликтующих файлов
(`_conflicting_files`, уже вызванный чуть выше для решения об
авторазрешении карты), ни `merge.stdout` в `detail` не попадают; тесты
этого файла проверяют формат, которого в коде задачи ещё нет —
падение здесь означает отсутствие кода задачи, не дефект теста.
Прогон 05.09 подтвердил ровно этот разрез: 5 из 8 тестов файла красные
по этой причине (`test_ac1_single_non_map_conflict_...`,
`test_ac1_stdout_tail_truncated_...`, `test_ac2_map_plus_other_file_
lists_both_names_...`, `test_ac3_all_diagnostics_empty_...`,
`test_ac5_map_only_conflict_regen_failure_...`). Три теста зелёные уже
сегодня по другой, законной причине — не путать с ложной зеленью:
`test_ac1_nonempty_stderr_also_kept` кроет часть требования 1, которая
не менялась (непустой `stderr` код и до задачи копирует в `detail`
целиком) — это регрессионный барьер на будущее, не проверка новой
функциональности; `test_ac2_map_plus_other_file_does_not_autoresolve`
и `test_ac5_map_only_conflict_still_autoresolves_without_escalation`
кроют условие вызова `_auto_resolve_map_conflict` (T067, требование 3
этого SPEC прямо запрещает его менять) — оно уже реализовано и не
трогается этой задачей.

Лёгкая FSM-песочница без реального git — тот же приём, что и
`tests/test_branch_freshness_gate.py` (T051) и `tests/test_fsm_map_
conflict_autoresolve.py` (T067): `gitcmd.in_repo` замокан заглушкой,
управляющей содержимым `stdout`/`stderr` `git merge` и списком
конфликтующих файлов независимо друг от друга — то, чего пере-
используемые заглушки тех файлов не позволяют (там `stdout`/`stderr`
конфликта фиксированы одним литералом).
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from orchestrator import (acceptance, catalog, config, fsm, gitcmd,  # noqa: E402
                          store, workspace)
from tests.sandbox import (SpyRun, capture, capture_new_task_id,  # noqa: E402
                           disk_backed_ls_tree_files, disk_backed_show,
                           fake_git)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

MAP_REL = "docs/codebase-map.md"

PLAN_READY = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: детализация конфликта подтяжки

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""


class PullConflictDetailTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        shutil.copytree(REPO_ROOT / "templates", root / "templates")

        for attr, value in (("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs"),
                            ("ROOT", root),
                            ("PROJECTS", root / ".artel" / "projects"),
                            ("TARGETS", root / "targets.yaml"),
                            ("ROLE_HOME", root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             root / ".artel" / "home" / ".claude"),
                            ("BACKUP_MARKER", root / ".artel" / "backup-marker"),
                            ("WORKTREES", root / ".artel" / "worktrees")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        patcher = mock.patch.object(gitcmd, "git", fake_git)
        patcher.start()
        self.addCleanup(patcher.stop)
        # см. tests/test_branch_freshness_gate.py — fake_git отвечает на
        # "rev-parse FETCH_HEAD" пустой строкой; замена _origin_main_sha
        # заглушкой с truthy-значением держит путь исполнения ДО merge
        # (без неё _pull_main_or_escalate деградирует на "fresh" раньше,
        # чем дойдёт до сценария конфликта, который проверяет этот файл).
        origin_sha_patcher = mock.patch.object(
            fsm, "_origin_main_sha", return_value="deadbeefcafefeed")
        origin_sha_patcher.start()
        self.addCleanup(origin_sha_patcher.stop)
        spy_patcher = mock.patch.object(gitcmd.subprocess, "run", SpyRun())
        spy_patcher.start()
        self.addCleanup(spy_patcher.stop)
        show_patcher = mock.patch.object(gitcmd, "show", disk_backed_show)
        show_patcher.start()
        self.addCleanup(show_patcher.stop)
        ls_patcher = mock.patch.object(gitcmd, "ls_tree_files",
                                       disk_backed_ls_tree_files)
        ls_patcher.start()
        self.addCleanup(ls_patcher.stop)

        self.wt_path = root / "wt"
        wt_patcher = mock.patch.object(
            workspace, "ensure", lambda task_id, branch: (self.wt_path, None))
        wt_patcher.start()
        self.addCleanup(wt_patcher.stop)

        self.capture = staticmethod(capture)
        self.capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(
            catalog.cmd_new, "Детализация конфликта подтяжки")
        self.tdir = config.TASKS / self.TASK
        self.branch = self.task_row()["branch"]

    # ------------------------------------------------------------ утилиты

    def task_row(self):
        return store.db().execute("SELECT * FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()

    def state(self) -> str:
        return self.task_row()["state"]

    def set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def journal_rows(self) -> list:
        return store.task_steps(store.db(), self.TASK)

    def escalation_detail(self) -> str:
        """`detail` самой последней записи журнала со `state -> escalated`
        — там и только там пишется формат, проверяемый этим файлом (не
        весь журнал шага, где есть и посторонние записи фиксации)."""
        rows = [r for r in self.journal_rows() if r["action"] == "state -> escalated"]
        self.assertTrue(rows, "нет записи 'state -> escalated' в журнале")
        return rows[-1]["detail"] or ""

    def write_plan_ready(self) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "PLAN.md").write_text(
            PLAN_READY.format(task=self.TASK), encoding="utf-8")

    def advance_from_in_dev(self) -> str:
        self.write_plan_ready()
        self.set_state("in_dev")
        return self.capture(fsm.cmd_advance, self.TASK)

    @staticmethod
    def _ok(repo, *args) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(("git", "-C", str(repo), *args), 0, "", "")

    def _fixation_response(self, repo, *args) -> subprocess.CompletedProcess | None:
        """Ответ на вызовы фиксации (`fixation.read`/`fix`, A7) — не предмет
        этого файла; см. `tests/test_branch_freshness_gate.py` (тот же
        приём) для мотивации каждой ветки."""
        if args == ("rev-parse", "HEAD"):
            return self._ok(repo, *args)
        if args[:2] == ("status", "--porcelain"):
            return self._ok(repo, *args)
        if args[:1] == ("init",):
            return self._ok(repo, *args)
        if args[:2] == ("diff", "--cached"):
            return self._ok(repo, *args)
        if args[:1] == ("add",):
            return self._ok(repo, *args)
        return None

    def make_conflict_side_effect(self, *, conflict_files,
                                  merge_stdout="", merge_stderr=""):
        """Заглушка `gitcmd.in_repo`: `merge` конфликтует с заданными
        `stdout`/`stderr`, `diff --name-only --diff-filter=U` называет
        `conflict_files`, `merge --abort` всегда успешен. `stdout`/
        `stderr` конфликта управляются НЕЗАВИСИМО от списка файлов —
        то, чего фиксированные заглушки других тестовых файлов не дают,
        а формат AC-1..AC-3 требует именно такой независимости."""
        self.merge_calls: list = []
        self.abort_calls: list = []

        def side_effect(repo, *args):
            fixation_response = self._fixation_response(repo, *args)
            if fixation_response is not None:
                return fixation_response
            if args[:1] == ("merge",) and "--abort" in args:
                self.abort_calls.append((repo, args))
                return self._ok(repo, *args)
            if args[:1] == ("merge",):
                self.merge_calls.append((repo, args))
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 1, merge_stdout, merge_stderr)
            if args[:2] == ("diff", "--name-only"):
                text = ("\n".join(conflict_files) +
                       ("\n" if conflict_files else ""))
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0, text, "")
            if args[:1] in (("checkout",), ("commit",), ("reset",)):
                # `reset -q -- tasks/<id>` — очистка worktree перед merge
                # (задача 01M1RA0R9AH9RBAHD4A2Z5SEWQ, смержена 06.09 после
                # лока этой планки); в песочнике — безобидный no-op, как
                # checkout/commit. Правка Оператора (amend-tests, 06.09).
                return self._ok(repo, *args)
            raise AssertionError(f"неожиданный gitcmd.in_repo вызов: {args}")

        return side_effect

    def run_conflict_scenario(self, *, conflict_files, merge_stdout="",
                              merge_stderr="", regen_ok: bool = True) -> str:
        """Проводит ветку через `in_dev -> review` с замоканным конфликтом
        подтяжки; возвращает вывод `cmd_advance`. `regen_ok` управляет
        успехом регенерации карты для AC-5 (провал авторазрешения)."""
        side_effect = self.make_conflict_side_effect(
            conflict_files=conflict_files, merge_stdout=merge_stdout,
            merge_stderr=merge_stderr)
        regen_result = (subprocess.CompletedProcess(
            ["python3", "scripts/codebase_map.py"], 0, "", "")
            if regen_ok else subprocess.CompletedProcess(
            ["python3", "scripts/codebase_map.py"], 1, "", "regen boom"))
        with mock.patch.object(gitcmd, "commits_behind", return_value=5), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(fsm.subprocess, "run", return_value=regen_result), \
             mock.patch.object(acceptance, "run") as acc_run:
            out = self.advance_from_in_dev()
        self._acc_run = acc_run
        return out

    # --------------------------------------------------------------- AC-1

    def test_ac1_single_non_map_conflict_names_file_and_stdout_conflict_line(self):
        """Конфликт по одному файлу кода (не карта) — `detail` эскалации
        называет и файл, и строку `CONFLICT` из `stdout` `git merge`
        (git пишет её именно туда, не в `stderr` — «Контекст» SPEC).

        Ловит мутацию: `detail` по-прежнему собирается только из
        `merge.stderr` (как до задачи) — `stderr` здесь пуст, значит имя
        файла и строка `CONFLICT` в `detail` не появятся, и оба
        `assertIn` ниже упадут.
        """
        merge_stdout = ("Auto-merging module.py\n"
                        "CONFLICT (content): Merge conflict in module.py\n"
                        "Automatic merge failed; fix conflicts and then "
                        "commit the result.\n")
        out = self.run_conflict_scenario(conflict_files=["module.py"],
                                         merge_stdout=merge_stdout)

        self.assertEqual(self.state(), "escalated")
        detail = self.escalation_detail()
        self.assertIn("конфликтные файлы: module.py", detail,
                      f"detail не называет конфликтный файл: {detail!r}")
        self.assertIn("CONFLICT (content): Merge conflict in module.py",
                      detail, f"detail не несёт строку CONFLICT из stdout: "
                      f"{detail!r}")
        self.assertEqual(len(self.abort_calls), 1,
                         "неразрешаемый конфликт обязан откатываться")
        self._acc_run.assert_not_called()

    def test_ac1_stdout_tail_truncated_to_500_chars_like_stderr(self):
        """Хвост `stdout` `git merge` обрезается до 500 символов — тем же
        приёмом, что уже применяется к `stderr` (SPEC, требование 1).

        Ловит мутацию: обрезка `stdout` убрана или заменена на другой
        лимит — маркер `TAIL_END_MARKER`, поставленный за пределами
        500-го символа, просочится в `detail`, и `assertNotIn` упадёт.
        """
        marker = "TAIL_END_MARKER"
        merge_stdout = ("CONFLICT (content): Merge conflict in module.py\n"
                        + ("Z" * 600) + marker)
        out = self.run_conflict_scenario(conflict_files=["module.py"],
                                         merge_stdout=merge_stdout)

        detail = self.escalation_detail()
        self.assertNotIn(marker, detail,
                         f"stdout не обрезан до 500 символов: {detail!r}")
        self.assertIn("CONFLICT (content): Merge conflict in module.py",
                      detail)

    def test_ac1_nonempty_stderr_also_kept(self):
        """Требование 1: `stderr`, если он не пуст, тоже несётся в
        `detail` (обрезанным до 500 символов) наряду со списком файлов и
        хвостом `stdout` — не заменяется им.

        Ловит мутацию: обработка `stderr` выброшена вовсе при переходе
        на список файлов/`stdout` — маркер `STDERR_MARKER` не попадёт в
        `detail`, `assertIn` упадёт.
        """
        merge_stdout = "CONFLICT (content): Merge conflict in module.py\n"
        merge_stderr = "STDERR_MARKER: warning: something\n"
        self.run_conflict_scenario(conflict_files=["module.py"],
                                   merge_stdout=merge_stdout,
                                   merge_stderr=merge_stderr)

        detail = self.escalation_detail()
        self.assertIn("STDERR_MARKER", detail,
                     f"непустой stderr обязан остаться в detail: {detail!r}")

    # --------------------------------------------------------------- AC-2

    def test_ac2_map_plus_other_file_lists_both_names_joined_by_comma(self):
        """Конфликт по двум файлам — `docs/codebase-map.md` и ещё один —
        не сводится к авторазрешению (список конфликтов не равен ровно
        `[MAP_REL]`): `_auto_resolve_map_conflict` не завершает merge,
        `merge --abort` выполняется, `detail` называет ОБА файла через
        `, ` в строке «конфликтные файлы: …» (SPEC, требование 1, AC-2).

        Ловит мутацию: список конфликтов усечён до одного файла (первого
        найденного) вместо полного списка — второе имя пропадёт из
        `detail`, `assertIn` по нему упадёт.
        """
        merge_stdout = ("CONFLICT (content): Merge conflict in "
                        f"{MAP_REL}\nCONFLICT (content): Merge conflict "
                        "in other.py\n")
        out = self.run_conflict_scenario(
            conflict_files=[MAP_REL, "other.py"], merge_stdout=merge_stdout)

        self.assertEqual(self.state(), "escalated",
                         "конфликт по нескольким файлам, включая карту, "
                         "обязан эскалировать (карта не разрешается сама, "
                         "когда конфликтует не одна)")
        detail = self.escalation_detail()
        self.assertIn(f"конфликтные файлы: {MAP_REL}, other.py", detail,
                      f"detail не называет оба файла через ', ': {detail!r}")
        self.assertEqual(len(self.abort_calls), 1)
        self._acc_run.assert_not_called()

    def test_ac2_map_plus_other_file_does_not_autoresolve(self):
        """Требование 3/AC-2: авторазрешение карты не вызывается (или
        вызывается и не завершает merge), когда конфликтующих файлов
        больше одного — регенератор карты не должен звониться вовсе.

        Ловит мутацию: условие авторазрешения ослаблено до «карта СРЕДИ
        конфликтов» вместо «карта — ЕДИНСТВЕННЫЙ конфликт» — регенератор
        позовётся, `assert_not_called` упадёт.
        """
        side_effect = self.make_conflict_side_effect(
            conflict_files=[MAP_REL, "other.py"],
            merge_stdout="CONFLICT (content): Merge conflict in other.py\n")
        with mock.patch.object(gitcmd, "commits_behind", return_value=2), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(fsm.subprocess, "run") as regen, \
             mock.patch.object(acceptance, "run") as acc_run:
            self.advance_from_in_dev()

        regen.assert_not_called()
        self.assertEqual(self.state(), "escalated")
        acc_run.assert_not_called()

    # --------------------------------------------------------------- AC-3

    def test_ac3_all_diagnostics_empty_has_no_dangling_separators(self):
        """`git merge` вернул ненулевой код с пустыми `stdout`/`stderr`, а
        `git diff --name-only --diff-filter=U` тоже пуст — `detail` не
        содержит пустых хвостов: ни строки «конфликтные файлы:» без
        имени за ней, ни висящих разделителей («; »/«, ») без текста
        после (SPEC, AC-3) — формат деградирует так же аккуратно, как
        вырожденный случай «git не ответил осмысленно» в остальном коде
        подтяжки, а не оставляет мусор от наивной склейки пустых частей.

        Ловит мутацию: `detail` склеивается из частей (список файлов/
        stdout-хвост/stderr-хвост) без фильтрации пустых значений перед
        `join` — на пустых входах это оставляет висящий `": "`/`"; "` в
        конце строки или литерал «конфликтные файлы:» без имени; оба
        случая ловят проверки ниже.
        """
        out = self.run_conflict_scenario(conflict_files=[], merge_stdout="",
                                         merge_stderr="")

        self.assertEqual(self.state(), "escalated")
        detail = self.escalation_detail()
        stripped = detail.rstrip()
        self.assertFalse(stripped.endswith(":"),
                         f"detail заканчивается голым ':': {detail!r}")
        self.assertFalse(stripped.endswith(";"),
                         f"detail заканчивается голым ';': {detail!r}")
        self.assertFalse(stripped.endswith(","),
                         f"detail заканчивается голой ',': {detail!r}")
        self.assertNotIn("; ;", detail, f"висящий разделитель: {detail!r}")
        self.assertNotIn(": ;", detail, f"висящий разделитель: {detail!r}")
        self.assertNotIn(", ,", detail, f"висящий разделитель: {detail!r}")
        self.assertNotIn("конфликтные файлы:", detail,
                         f"пустой список конфликтов не имеет права "
                         f"порождать строку 'конфликтные файлы:' без "
                         f"имён: {detail!r}")

    # --------------------------------------------------------------- AC-5

    def test_ac5_map_only_conflict_still_autoresolves_without_escalation(self):
        """Единственный конфликтующий файл — ровно `docs/codebase-map.md`
        — поведение `_auto_resolve_map_conflict` не меняется этой
        задачей: успешное авторазрешение по-прежнему завершает merge без
        эскалации (SPEC, AC-5) — список конфликтов, который теперь читает
        и код детализации, не должен помешать существующему пути успеха.

        Ловит мутацию: авторазрешение сломано попыткой задачи прочитать
        список конфликтов ДО решения об авторазрешении (например, повторный
        `git diff` после уже начатого `checkout --theirs`, который вернёт
        иной список) — переход в `review` не состоится, `assertEqual`
        по состоянию упадёт.
        """
        side_effect = self.make_conflict_side_effect(
            conflict_files=[MAP_REL],
            merge_stdout=f"CONFLICT (content): Merge conflict in {MAP_REL}\n")
        with mock.patch.object(gitcmd, "commits_behind", return_value=3), \
             mock.patch.object(gitcmd, "in_repo", side_effect=side_effect), \
             mock.patch.object(fsm.subprocess, "run",
                               return_value=subprocess.CompletedProcess(
                                   ["python3", "scripts/codebase_map.py"],
                                   0, "", "")) as regen, \
             mock.patch.object(acceptance, "run",
                               return_value=(True, "ok")) as acc_run:
            out = self.advance_from_in_dev()

        self.assertEqual(self.state(), "review",
                         "конфликт только по карте по-прежнему "
                         "разрешается сам, без эскалации")
        regen.assert_called_once()
        acc_run.assert_called_once_with(self.wt_path / "tasks" / self.TASK)

    def test_ac5_map_only_conflict_regen_failure_escalates_with_conflict_list(self):
        """Единственный конфликтующий файл — карта, но регенерация не
        удалась: `merge --abort` выполняется, эскалация несёт список
        конфликтов на МОМЕНТ неудачи (здесь — ровно `[MAP_REL]`) по тем
        же правилам AC-1/AC-2 (SPEC, AC-5) — провал авторазрешения не
        имеет права вернуться к старому формату «только stderr».

        Ловит мутацию: провал авторазрешения возвращается к записи
        `detail` из одного `merge.stderr` (путь до задачи) вместо нового
        формата со списком файлов — `assertIn` по имени карты в `detail`
        упадёт.
        """
        out = self.run_conflict_scenario(
            conflict_files=[MAP_REL],
            merge_stdout=f"CONFLICT (content): Merge conflict in {MAP_REL}\n",
            regen_ok=False)

        self.assertEqual(self.state(), "escalated",
                         "провал регенерации при авторазрешении обязан "
                         "эскалировать")
        detail = self.escalation_detail()
        self.assertIn(f"конфликтные файлы: {MAP_REL}", detail,
                      f"detail не называет карту при провале авторазрешения: "
                      f"{detail!r}")
        self.assertEqual(len(self.abort_calls), 1,
                         "провал авторазрешения обязан откатывать merge")
        self._acc_run.assert_not_called()


# AC-4: skip — покрыт существующими файлами `tests/test_branch_freshness_
# gate.py` (T051/T052/T053) и `tests/test_fsm_map_conflict_autoresolve.py`
# (T067), которые CI гоняет на каждом коммите независимо от этой задачи;
# требование 3/AC-5 этого SPEC прямо запрещает менять их утверждения, а
# новый тест здесь дублировал бы их проверки без добавленного покрытия —
# критерий проверяется тем, что те файлы остаются зелёными после
# изменения кода, не отдельным тестом этого файла.


if __name__ == "__main__":
    unittest.main()
