"""Юнит-тесты сверки свежести ветки на входе в гейт (SPEC T051, требования
1, 3-7, 10) — orchestrator/fsm.py::_pull_main_or_escalate и её подключение
в обеих точках (`in_dev -> review` через `cmd_advance`, `acceptance ->
merge_gate` через `cmd_approve`).

Полный прогон РЕАЛЬНОГО git (merge, конфликт, `git merge --abort`, счёт
коммитов) — приёмочные тесты `tasks/T051/acceptance_tests/`
(`_sandbox.py::RealGitFreshnessTest`); здесь — ветвление самой логики
через мок трёх точек механизма (`gitcmd.commits_behind`, `gitcmd.in_repo`,
`orchestrator.acceptance.run`), тем же приёмом лёгкой FSM-песочницы без
реального git, что и `tests/test_advance_guard.py`.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (acceptance, catalog, config, fsm, gitcmd,  # noqa: E402
                          store, workspace)
from tests.sandbox import (LightTransitionSandbox, SpyRun,  # noqa: E402
                           capture, disk_backed_ls_tree_files,
                           disk_backed_show, fake_git)

REPO_ROOT = Path(__file__).resolve().parent.parent

PLAN_READY = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: сверка свежести

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""


class BranchFreshnessGateTest(LightTransitionSandbox):

    # ------------------------------------------------------------ утилиты

    def journal_details(self) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]

    def approve_from_acceptance(self) -> str:
        self.set_state("acceptance")
        return self.capture(fsm.cmd_approve, self.TASK)

    @staticmethod
    def _ok(repo, *args) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(("git", "-C", str(repo), *args), 0, "", "")

    def _fixation_response(self, repo, *args) -> subprocess.CompletedProcess | None:
        """Ответ на вызовы `fixation.read`/`fix` (A7: self/артель фиксируется
        тем же кодом, что и любой target, — `confirm_fixation`/`record_
        fixation` зовут `gitcmd.in_repo` на КАЖДОМ approve/advance, до и
        независимо от предмета этого файла, подтяжки свежести) — `None`,
        если `args` не про фиксацию (вызывающий код решает дальше сам).
        Эти вызовы НЕ считаются `merge_calls`/`abort_calls` — те про
        предмет теста, не про фиксацию."""
        if args == ("rev-parse", "HEAD"):
            # Пустой sha (не фейковый непустой) — `confirm_fixation`
            # деградирует «сверять не с чем» (тот же вырожденный случай,
            # что и до A7: этот файл — не про фиксацию, approve без `sha`
            # обязан продолжать работать).
            return subprocess.CompletedProcess(
                ("git", "-C", str(repo), *args), 0, "", "")
        if args[:2] == ("status", "--porcelain"):
            return subprocess.CompletedProcess(
                ("git", "-C", str(repo), *args), 0, "", "")
        if args[:1] == ("init",):
            return self._ok(repo, *args)
        if args[:2] == ("diff", "--cached"):
            return subprocess.CompletedProcess(
                ("git", "-C", str(repo), *args), 0, "", "")  # нечего коммитить
        if args[:1] == ("add",):
            return self._ok(repo, *args)
        if args[:1] in (("checkout",), ("reset",)):
            # Очистка worktree перед merge (SPEC 01M1RA0R9AH9RBAHD4A2Z5SEWQ,
            # требования 1-2): отбрасывание карты (`checkout --`) и
            # исключение `tasks/<id>/` из WIP-чекпоинта (`reset -q --`) —
            # безобидный no-op здесь, как и `add`/`diff --cached` выше;
            # песочница этого файла — не о самой очистке, «чисто, нечего
            # коммитить» безусловно.
            return self._ok(repo, *args)
        return None

    def _conflict_then_abort_ok(self, repo, *args) -> subprocess.CompletedProcess:
        fixation_response = self._fixation_response(repo, *args)
        if fixation_response is not None:
            return fixation_response
        if args[:1] == ("merge",) and "--abort" in args:
            self.abort_calls.append((repo, args))
            return self._ok(repo, *args)
        if args[:1] == ("merge",):
            self.merge_calls.append((repo, args))
            return subprocess.CompletedProcess(
                ("git", "-C", str(repo), *args), 1, "",
                "CONFLICT (content): Merge conflict in shared.txt")
        if args[:2] == ("diff", "--name-only"):
            # Конфликт не сводится к «только карта» (SPEC T067,
            # требование 4) — список конфликтующих файлов называет
            # посторонний файл, авторазрешение не применимо, прежний
            # abort+escalate.
            return subprocess.CompletedProcess(
                ("git", "-C", str(repo), *args), 0, "shared.txt\n", "")
        raise AssertionError(f"неожиданный gitcmd.in_repo вызов: {args}")

    def _recording_ok(self, repo, *args) -> subprocess.CompletedProcess:
        fixation_response = self._fixation_response(repo, *args)
        if fixation_response is not None:
            return fixation_response
        self.merge_calls.append((repo, args))
        return self._ok(repo, *args)

    def setup_recording(self) -> None:
        self.merge_calls: list = []
        self.abort_calls: list = []

    # ----------------------------------------------------- ветка не отстала

    def test_advance_skips_pull_when_branch_not_behind(self):
        self.setup_recording()
        with mock.patch.object(gitcmd, "commits_behind", return_value=0), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._recording_ok), \
             mock.patch.object(acceptance, "run",
                               return_value=(True, "ok")) as acc_run:
            self.advance_from_in_dev()

        self.assertEqual(self.state(), "verifying",
                         "переход обязан пройти как и до T051 (требование 7); "
                         "ADR-0015 — цель перехода in_dev теперь verifying, "
                         "не review")
        self.assertEqual(self.merge_calls, [], "не отставшая ветка — merge не звонится")
        # ADR-0015: прогон приёмки теперь часть ЭТОГО ЖЕ перехода
        # `in_dev -> verifying` (был отдельным гейтом `review -> verifying`
        # до этой задачи) — звонится независимо от того, отставала ли ветка.
        acc_run.assert_called_once()

    def test_approve_skips_pull_when_branch_not_behind(self):
        self.setup_recording()
        with mock.patch.object(gitcmd, "commits_behind", return_value=None), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._recording_ok), \
             mock.patch.object(acceptance, "run") as acc_run:
            self.approve_from_acceptance()

        self.assertEqual(self.state(), "merge_gate",
                         "None (git не ответил) — тот же вырожденный случай, "
                         "что и 0 коммитов (требование 9)")
        self.assertEqual(self.merge_calls, [])
        acc_run.assert_not_called()

    # ------------------------------------------------- успешная подтяжка

    def test_advance_pulls_main_and_advances_when_acceptance_green(self):
        """Подтяжка использует зафетченный с origin sha как источник merge
        (не литерал `config.MAIN_BRANCH`, не литерал `"FETCH_HEAD"`) и идёт
        в worktree ЗАДАЧИ, не в рабочей копии пульта; после зелёной приёмки
        переход в `review` состоится.

        Ловит мутацию: `base` merge возвращён к литералу `config.
        MAIN_BRANCH` или к `"FETCH_HEAD"` вместо зафетченного sha — AC-2/
        R1-F1 тихо перестанут выполняться, а `assertNotIn`/`assertIn` по
        аргументам merge здесь это поймают.

        Ловит мутацию (SPEC 01M1RNZ6V7TTTTYAHBMF8JBQQS, REVIEW.md
        итерация 1, R1-F2): возврат материализации планки к временному
        каталогу (регрессия №14) или к `cwd=config.ROOT` — `plank_root`/
        `cwd` ниже перестали бы совпадать с `self.wt_path`, и `assertEqual`
        по ним это поймает.
        """
        self.setup_recording()
        self.write_acceptance_plank()
        with mock.patch.object(gitcmd, "commits_behind", return_value=3), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._recording_ok), \
             mock.patch.object(acceptance, "run",
                               return_value=(True, "ok")) as acc_run:
            self.advance_from_in_dev()

        self.assertEqual(self.state(), "verifying",
                         "переход обязан состояться после успешной подтяжки "
                         "(ADR-0015 — цель перехода in_dev теперь verifying)")
        self.assertEqual(len(self.merge_calls), 1)
        repo, args = self.merge_calls[0]
        self.assertEqual(repo, self.wt_path, "merge — в worktree ЗАДАЧИ, "
                         "не в рабочей копии пульта (ADR-0006 п.2)")
        self.assertEqual(args[0], "merge")
        self.assertIn("--no-ff", args, "подтяжка не rebase (требование 3)")
        # SPEC 01M1NBWPKNBXP9ZXXQDJM7AXPJ, AC-2: источник merge — sha,
        # зафетченный с origin (здесь замокан `fsm._origin_main_sha` ->
        # "deadbeefcafefeed", REVIEW.md R1-F1 итерация 1: литерал
        # "FETCH_HEAD" больше не подставляется НИКОГДА, даже когда
        # `_origin_main_sha` вырождена — см.
        # `test_advance_treats_origin_fetch_failure_as_fresh`), НЕ
        # локальный `config.MAIN_BRANCH` буквальным аргументом merge.
        self.assertNotIn(config.MAIN_BRANCH, args,
                         "AC-2: config.MAIN_BRANCH (локальный пин) не "
                         "имеет права быть источником merge")
        self.assertIn("deadbeefcafefeed", args)
        self.assertNotIn("FETCH_HEAD", args,
                         "R1-F1: литерал FETCH_HEAD не подставляется — не "
                         "честный no-op ни в config.ROOT (чужой предыдущий "
                         "фетч), ни в приватном FETCH_HEAD worktree'а")
        self.assertNotIn(self.branch, args,
                         "ветка задачи не упоминается в аргументах merge")
        # ADR-0015: с этой задачи `in_dev` зовёт `acceptance.run` дважды —
        # раз внутри `pull.evaluate` (рубеж «прогон планки после
        # подтяжки», SPEC 01M1RNZ6V7TTTTYAHBMF8JBQQS, этот тест изначально
        # про НЕГО) и второй раз своим отдельным рубежом
        # `_acceptance_run_refuses` (SPEC T023, требование 6, переехавшим
        # из `review()`) — оба легитимны и стояли в системе ДО этой задачи
        # (просто на двух разных вызовах `advance`, не в одном); первый
        # вызов в списке — от `pull.evaluate`, его и проверяет этот тест
        # (тот же приём, что `tests/test_fsm_map_conflict_autoresolve.py`).
        self.assertEqual(acc_run.call_count, 2)
        plank_root = acc_run.call_args_list[0][0][0]
        self.assertEqual(
            plank_root, self.wt_path / "tasks" / self.TASK,
            "SPEC 01M1RNZ6V7TTTTYAHBMF8JBQQS AC-1: планка обязана "
            "материализоваться в рабочий каталог кода задачи (worktree "
            "self-target), не во временный каталог")
        self.assertEqual(
            acc_run.call_args_list[0].kwargs.get("cwd"), self.wt_path,
            "SPEC 01M1RNZ6V7TTTTYAHBMF8JBQQS AC-2: cwd прогона обязан "
            "быть равен рабочему каталогу кода задачи, не config.ROOT")

    def test_approve_pulls_main_and_advances_when_acceptance_green(self):
        """SPEC 01M1RNZ6V7TTTTYAHBMF8JBQQS, AC-1/AC-2: approve из
        `acceptance` гоняет планку, материализованную из артефактной ветки
        НА МЕСТЕ в рабочий каталог кода задачи (`acceptance.
        materialize_from_branch(..., wt_path)`, не во временный каталог) —
        и при зелёном прогоне доходит до `merge_gate`.

        Ловит мутацию: возврат к временному каталогу (регрессия №14) —
        `plank_root`, переданный в `acceptance.run`, не совпал бы с путём
        внутри `self.wt_path`, и `assertEqual` ниже это поймает.
        """
        self.setup_recording()
        self.write_acceptance_plank()
        with mock.patch.object(gitcmd, "commits_behind", return_value=1), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._recording_ok), \
             mock.patch.object(acceptance, "run",
                               return_value=(True, "ok")) as acc_run:
            self.approve_from_acceptance()

        self.assertEqual(self.state(), "merge_gate")
        self.assertEqual(len(self.merge_calls), 1)
        acc_run.assert_called_once()
        plank_root = acc_run.call_args[0][0]
        self.assertEqual(
            plank_root, self.wt_path / "tasks" / self.TASK,
            "SPEC 01M1RNZ6V7TTTTYAHBMF8JBQQS AC-1: планка материализуется "
            "в рабочий каталог кода задачи, не во временный каталог")
        self.assertEqual(
            acc_run.call_args.kwargs.get("cwd"), self.wt_path,
            "SPEC 01M1RNZ6V7TTTTYAHBMF8JBQQS AC-2: cwd прогона обязан "
            "быть равен рабочему каталогу кода задачи, не config.ROOT")

    # --------------------------- AC-4 (эквивалент лёгкой песочницы) ---

    def test_freshness_check_never_defaults_base_to_local_pin(self):
        """SPEC 01M1NBWPKNBXP9ZXXQDJM7AXPJ, AC-4 — эквивалент в стиле
        этого файла (лёгкая песочница без реального git не может честно
        развести «ветка отстаёт от origin, но совпадает с локальным
        пином» — тот сценарий кроют приёмочные тесты задачи,
        `_sandbox.py::OriginDivergedSandbox::test_ac4_*`): узел сверки
        обязан звать `gitcmd.commits_behind` с явным `base`, полученным
        из fetch, а не оставлять параметр пустым — иначе `commits_behind`
        сама подставила бы `config.MAIN_BRANCH` (локальный пин), ровно
        дефект инцидента 04.09 из «Контекста» SPEC.

        Ловит мутацию: `base` не передаётся в `commits_behind` явно
        (аргумент опущен/`None`) — вызов молча упадёт на дефолт `config.
        MAIN_BRANCH` внутри `commits_behind`, а `spying_commits_behind`
        здесь это поймает пустым/`None` `base`.
        """
        self.setup_recording()
        behind_calls = []

        def spying_commits_behind(branch, base=None, repo=None):
            behind_calls.append((branch, base))
            return 3

        with mock.patch.object(gitcmd, "commits_behind",
                               side_effect=spying_commits_behind), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._recording_ok), \
             mock.patch.object(acceptance, "run", return_value=(True, "ok")):
            self.advance_from_in_dev()

        self.assertEqual(len(behind_calls), 1)
        _, base = behind_calls[0]
        self.assertTrue(
            base, "AC-4: base обязан быть передан явно из origin-fetch, "
            "не оставлен пустым/None (иначе commits_behind сама "
            "подставит config.MAIN_BRANCH — локальный пин)")
        self.assertNotEqual(
            base, config.MAIN_BRANCH,
            "AC-4: base не имеет права совпасть с локальным config.MAIN_BRANCH")

    # ------------------------------- R1-F1 (REVIEW.md итерация 1, major)

    def test_advance_treats_origin_fetch_failure_as_fresh(self):
        """REVIEW.md 01M1NBWPKNBXP9ZXXQDJM7AXPJ итерация 1, замечание
        R1-F1 (major): `_origin_main_sha` вырождена (git fetch/rev-parse
        не ответили, либо конфигурация target'а неисправна) — переход
        обязан деградировать на "fresh" немедленно, НЕ подставляя литерал
        "FETCH_HEAD" ни в `commits_behind`, ни в `merge`. Прежде такая
        подстановка сравнивала/мержила ветку задачи против постороннего
        состояния `config.ROOT`/приватного `FETCH_HEAD` worktree'а — не
        «ничего не делала», как заявляла деградация.

        Ловит мутацию: убранный ранний `if not base: return "fresh"` —
        вызов дойдёт до `commits_behind`/`merge` с литералом `"FETCH_HEAD"`
        вместо честного no-op, и моки `behind`/`self.merge_calls` здесь
        это поймают непустым вызовом.
        """
        self.setup_recording()
        with mock.patch.object(fsm, "_origin_main_sha", return_value=None), \
             mock.patch.object(gitcmd, "commits_behind") as behind, \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._recording_ok), \
             mock.patch.object(acceptance, "run",
                               return_value=(True, "ok")) as acc_run:
            self.advance_from_in_dev()

        self.assertEqual(self.state(), "verifying",
                         "вырожденная _origin_main_sha — тот же исход, что "
                         "и «ветка не отстала» (требование 7); ADR-0015 — "
                         "цель перехода in_dev теперь verifying, не review")
        behind.assert_not_called()
        self.assertEqual(self.merge_calls, [],
                         "R1-F1: merge не имеет права звонить против "
                         "постороннего FETCH_HEAD")
        # ADR-0015: прогон приёмки теперь часть ЭТОГО ЖЕ перехода
        # `in_dev -> verifying` — звонится независимо от исхода сверки
        # свежести, вырожденной или нет.
        acc_run.assert_called_once()

    # --------------------------------------------------- конфликт подтяжки

    def test_advance_escalates_on_pull_conflict_and_aborts(self):
        self.setup_recording()
        self.write_plan_ready()
        self.set_state("in_dev")
        with mock.patch.object(gitcmd, "commits_behind", return_value=5), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._conflict_then_abort_ok), \
             mock.patch.object(acceptance, "run") as acc_run:
            out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "escalated",
                         "конфликт подтяжки обязан эскалировать (требование 5)")
        combined = out + "\n".join(self.journal_details())
        self.assertIn("конфликт", combined.lower())
        self.assertEqual(len(self.merge_calls), 1)
        self.assertEqual(len(self.abort_calls), 1,
                         "конфликт обязан откатываться git merge --abort")
        acc_run.assert_not_called()

    def test_approve_escalates_on_pull_conflict_and_aborts(self):
        self.setup_recording()
        self.set_state("acceptance")
        with mock.patch.object(gitcmd, "commits_behind", return_value=2), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._conflict_then_abort_ok), \
             mock.patch.object(acceptance, "run") as acc_run:
            out = self.capture(fsm.cmd_approve, self.TASK)

        self.assertEqual(self.state(), "escalated")
        combined = out + "\n".join(self.journal_details())
        self.assertIn("конфликт", combined.lower())
        self.assertEqual(len(self.abort_calls), 1)
        acc_run.assert_not_called()

    # --------------------------------------- красные приёмочные после пула

    def test_advance_escalates_on_red_acceptance_after_pull_keeps_merge(self):
        """SPEC 01M1R9YEK08XEQWBFX0929WFVJ, AC-4: планка, реально
        материализованная из артефактной ветки и реально красная после
        подтяжки main, обязана эскалировать (требование 6, T051), а не
        схлопнуться в новый именованный отказ AC-3 — тот остаётся только
        для планки, которая не найдена в источнике.

        Ловит мутацию: подмена ветки «планка найдена и красная» на
        новую ветку AC-3 «планка не найдена» — состояние осталось бы
        `in_dev`/предыдущим вместо `escalated`, и `MARKER-RED` пропал бы
        из журнала.
        """
        self.setup_recording()
        self.write_plan_ready()
        self.write_acceptance_plank()
        self.set_state("in_dev")
        with mock.patch.object(gitcmd, "commits_behind", return_value=4), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._recording_ok), \
             mock.patch.object(acceptance, "run",
                               return_value=(False, "MARKER-RED")):
            out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "escalated",
                         "красные приёмочные после подтяжки эскалируют "
                         "(требование 6)")
        combined = out + "\n".join(self.journal_details())
        self.assertIn("MARKER-RED", combined)
        self.assertEqual(len(self.merge_calls), 1,
                         "слияние остаётся — откат не выполняется")
        self.assertEqual(self.abort_calls, [])

    def test_approve_escalates_on_red_acceptance_after_pull_keeps_merge(self):
        """SPEC 01M1R9YEK08XEQWBFX0929WFVJ, AC-4: тот же сценарий, что и
        `test_advance_escalates_on_red_acceptance_after_pull_keeps_merge`,
        со стороны `approve` из `acceptance` — красная планка эскалирует,
        слияние сохраняется (не откатывается).

        Ловит мутацию: подмена ветки «планка найдена и красная» на
        новую ветку AC-3 «планка не найдена» — состояние осталось бы
        `acceptance` вместо `escalated`, и `MARKER-RED` пропал бы из
        журнала.
        """
        self.setup_recording()
        self.write_acceptance_plank()
        self.set_state("acceptance")
        with mock.patch.object(gitcmd, "commits_behind", return_value=7), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._recording_ok), \
             mock.patch.object(acceptance, "run",
                               return_value=(False, "MARKER-RED")):
            out = self.capture(fsm.cmd_approve, self.TASK)

        self.assertEqual(self.state(), "escalated")
        combined = out + "\n".join(self.journal_details())
        self.assertIn("MARKER-RED", combined)
        self.assertEqual(len(self.merge_calls), 1)
        self.assertEqual(self.abort_calls, [])

    # --------- отказ AC-3 на сбое чтения SPEC.md (REVIEW.md R1-F1, ит. 4)

    def test_approve_refuses_when_spec_read_fails_after_missing_plank(self):
        """REVIEW.md 01M1R9YEK08XEQWBFX0929WFVJ итерация 4, замечание
        major: R1-F1 (сбой чтения SPEC.md отказывает именованно, не
        молчаливый "pulled") был исправлен по коду за три итерации, но
        ни разу не закреплён тестом — единственной защитой от регресса
        оставалась ручная эмпирическая проверка ревьювера на каждой
        итерации. Планка не найдена в артефактной ветке
        (`acceptance_tests/` отсутствует) легитимна ТОЛЬКО когда SPEC.md
        реально прочитан и не несёт AC-разметки/несёт `skip_tests`; здесь
        чтение самого SPEC.md проваливается (git не ответил) — узел
        обязан отказать именованно (AC-3), не подставлять дефолт
        `meta={}` (`guard.requires_ac_markup({}) == False`), который дал
        бы молчаливый "pulled".

        Ловит мутацию: возврат `_read_branch_text_or_refuse` к прямому
        `gitcmd.show(...) or {}` — состояние осталось бы `merge_gate`
        вместо `acceptance`, а именованный отказ пропал бы из журнала.
        """
        self.setup_recording()

        def fake_show(branch, rel):
            if rel.endswith("SPEC.md"):
                return None, "git не ответил"
            return disk_backed_show(branch, rel)

        with mock.patch.object(gitcmd, "commits_behind", return_value=6), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._recording_ok), \
             mock.patch.object(gitcmd, "show", side_effect=fake_show), \
             mock.patch.object(acceptance, "run") as acc_run:
            out = self.approve_from_acceptance()

        self.assertEqual(self.state(), "acceptance",
                         "сбой чтения SPEC.md обязан отказать переход, "
                         "не менять состояние")
        combined = out + "\n".join(self.journal_details())
        self.assertIn("не прочитан", combined,
                      "R1-F1: отказ обязан быть именованным в журнале, "
                      "не молчаливым проходом")
        self.assertEqual(len(self.merge_calls), 1,
                         "слияние подтяжки уже состоялось до сверки планки")
        acc_run.assert_not_called()

    # ------------------------------------------------ worktree недоступен

    def test_advance_escalates_when_worktree_not_available(self):
        with mock.patch.object(gitcmd, "commits_behind", return_value=9), \
             mock.patch.object(workspace, "ensure",
                               return_value=(self.wt_path, "worktree add упал")):
            self.write_plan_ready()
            self.set_state("in_dev")
            out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "escalated")
        combined = out + "\n".join(self.journal_details())
        self.assertIn("worktree", combined)


# --------------------------------------------------------------------- AC-10


class TargetSourcedRemoteTest(unittest.TestCase):
    """SPEC 01M1NBWPKNBXP9ZXXQDJM7AXPJ, требование 5/AC-10 (ANSWER-1,
    добавлено после лока приёмочной планки — юнит-тест здесь, не в
    `tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/acceptance_tests/`).

    Источник сверки/подтяжки — конфигурация target'а задачи
    (`targets.yaml`/`store.task_target`), не хардкод `origin` пульта:
    задача с не-self target'ом фетчит `url` её записи, не литерал
    `"origin"`. Self-target уже покрыт `BranchFreshnessGateTest` выше
    (там `config.TARGETS` намеренно не заводится — AC-9); здесь отдельная
    песочница ИМЕННО потому, что этот сценарий обязан завести файл.
    """

    TARGETS_YAML = """targets:
  acme:
    forge: github
    url: http://127.0.0.1:9/acme-target.git
    base: trunk
    token_slot: artel-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

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
        config.TARGETS.write_text(self.TARGETS_YAML, encoding="utf-8")

        self.calls: list = []

        def spying_git(*args):
            self.calls.append(args)
            return fake_git(*args)

        patcher = mock.patch.object(gitcmd, "git", spying_git)
        patcher.start()
        self.addCleanup(patcher.stop)
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

        self.capture = capture
        self.capture(catalog.cmd_init)
        self.TASK = catalog.cmd_new("Внешний target", target="acme")
        self.tdir = config.TASKS / self.TASK
        self.branch = store.db().execute(
            "SELECT branch FROM tasks WHERE id=?",
            (self.TASK,)).fetchone()["branch"]

    def test_pull_freshness_fetches_inside_the_target_clone_not_the_pult(self):
        """Ветка не отстала (`commits_behind` -> 0) — сверке этого
        достаточно, чтобы проявить свой источник: fetch обязан случиться
        ДО самого сравнения (AC-1 для self-target, тот же порядок здесь),
        внутри клона контекста target'а (`config.PROJECTS/acme/workspace`,
        `-C`), не в `config.ROOT`; ветка фетча — её `base` (`trunk`), не
        `config.MAIN_BRANCH` (`main`).

        Переведено на клон контекста target'а задачей SPEC
        01M1R5B33CC7E6BZK085XV3ZCX (AC-4, требование 3): remote внешнего
        target на git-уровне — литеральное имя `"origin"` (клон несёт
        свой git remote `origin` по тому же соглашению, что и
        `config.ROOT` пульта, `orchestrator/repo_context.py` докстринг),
        не голый `url` записи — тот недостижим без настоящего remote
        (эта же логика раньше уходила в `config.ROOT` литералом
        `"fetch", "-q", url, base` без `-C`, что и покрывал прежний
        вариант этого теста до AC-4).

        Ловит мутацию: fetch по-прежнему уходит в `config.ROOT`
        (`c[0] == "fetch"` без `-C`, литералом `entry["url"]` вторым
        аргументом) — `fetch_calls` здесь останется пустым, и
        `assertTrue` это поймает.
        """
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "PLAN.md").write_text(
            PLAN_READY.format(task=self.TASK), encoding="utf-8")
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?",
                     ("in_dev", self.TASK))
        conn.commit()

        with mock.patch.object(gitcmd, "commits_behind", return_value=0):
            self.capture(fsm.cmd_advance, self.TASK)

        fetch_calls = [c for c in self.calls
                       if len(c) > 2 and c[0] == "-C" and c[2] == "fetch"]
        self.assertTrue(fetch_calls, "SPEC 01M1R5B33CC7E6BZK085XV3ZCX AC-4: "
                        "сверка обязана фетчить в клоне контекста target'а")
        remote_args = fetch_calls[0]
        self.assertIn(str(config.PROJECTS / "acme" / "workspace"),
                     remote_args,
                     "AC-4: fetch идёт в клон контекста target'а "
                     "(config.PROJECTS/<target>/workspace), не в "
                     "config.ROOT пульта")
        self.assertIn("origin", remote_args,
                     "AC-4: remote — локальное имя origin клона target'а "
                     "(git-уровень), не голый url targets.yaml")
        self.assertIn("trunk", remote_args,
                     "AC-4: ветка фетча — base записи target'а, не "
                     "config.MAIN_BRANCH")
        self.assertNotIn(config.MAIN_BRANCH, remote_args,
                         "AC-4: config.MAIN_BRANCH — имя ветки self-"
                         "target'а, не этого target'а")


if __name__ == "__main__":
    unittest.main()
