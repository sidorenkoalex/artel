"""Юнит-тесты условия «а» `fsm_autogate._autogate_conditions` — чтение
планки `acceptance_tests/` и её AC-пометок через источник артефактов
задачи, не с диска рабочей копии (SPEC 01M1NBWWPJMHKJMYXRDCM0W0C5).

Приёмочные тесты задачи (`tasks/01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/`,
`AutogateBranchSandbox`) уже покрывают сценарий целиком через настоящий
git. Эти тесты дополняют их на уровне юнита самой функции — чистые моки
`artifact_source.resolve`/`gitcmd.*`, без реального репозитория — для
углов, которые приёмочные тесты не бьют напрямую: разбор ВСЕХ `*.py`
каталога (не только `test_*.py`, расхождение с дисковым
`guard.scan_acceptance_tests`, прецедент `fsm._tests_writing_ac_state`),
вырожденный ответ `gitcmd.ls_tree_files` (`None` — git не ответил) и
точный текст пометки источника (ветка+sha).
"""
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, artifact_source, budget, ci, fixation,
                          fsm_autogate, gates, gitcmd, store, workspace)
from scripts import guard

BRANCH = "artifact/T001"
SHA = "a" * 40
CODE_BRANCH = "task/t001-x"


class _AutogateConditionsUnitTest(unittest.TestCase):
    """Условия б/в/г/д заглушены на «выполнено» — тем же приёмом, что
    `AutogateBranchSandbox.conditions` приёмочных тестов задачи; предмет
    этих тестов — только условие «а»."""

    TASK = "T001"

    def call(self, *, ls_tree_files=None, show_map=None, acc_tdir=None,
             iteration=1, verifying_status=(ci.VERIFYING_GREEN, "зелёный")):
        acc_tdir = acc_tdir if acc_tdir is not None else Path("/no/such/dir")
        show_map = show_map or {}
        t = {"branch": CODE_BRANCH, "spent_usd": 0.0, "budget_usd": 5.0}

        def fake_show(branch, rel):
            self.assertEqual(branch, BRANCH)
            return (show_map[rel], "") if rel in show_map else (None, "нет файла")

        def fake_verifying_status(branch):
            self.assertEqual(branch, CODE_BRANCH,
                             "ci-критерий обязан спрашивать статус КОДОВОЙ "
                             "ветки задачи, не артефактной")
            return verifying_status

        with mock.patch.object(artifact_source, "resolve",
                               return_value=(BRANCH, True)), \
             mock.patch.object(gitcmd, "branch_head_sha", return_value=SHA), \
             mock.patch.object(gitcmd, "ls_tree_files",
                               return_value=ls_tree_files), \
             mock.patch.object(gitcmd, "show", side_effect=fake_show), \
             mock.patch.object(workspace, "on_task_branch",
                               return_value=True), \
             mock.patch.object(workspace, "path",
                               return_value=Path("/wt")), \
             mock.patch.object(acceptance, "run_full_suite",
                               return_value=(True, "")), \
             mock.patch.object(budget, "budget_block", return_value=None), \
             mock.patch.object(ci, "verifying_status",
                               side_effect=fake_verifying_status):
            return fsm_autogate._autogate_conditions(object(), self.TASK, t,
                                                      acc_tdir, iteration)


class AllPyFilesScannedTest(_AutogateConditionsUnitTest):

    def test_manual_marker_in_non_test_prefixed_file_is_seen(self):
        """`guard.scan_ac_content` (ветко-корректное чтение) разбирает
        ВСЕ `*.py` каталога, не только `test_*.py` — тот же приём, что
        `fsm._tests_writing_ac_state` (SPEC T031), сознательно
        расходящийся с дисковым `guard.scan_acceptance_tests`.

        Ловит мутацию: фильтр на `Path(p).name.startswith("test_")`
        перед сбором `sources` пропустил бы этот файл — manual-маркер
        остался бы невидим, условие «а» прошло бы автогейтом вместо
        отказа.
        """
        rel = f"tasks/{self.TASK}/acceptance_tests/helper.py"
        content = (
            '"""Не test_*, обычный помощник планки."""\n'
            "# AC-3: manual — маркер юнит-теста в файле без префикса test_.\n"
        )

        ok, reason = self.call(ls_tree_files=[rel], show_map={rel: content})

        self.assertEqual(reason, "автогейт: критерии manual — AC-3 "
                         f"(источник планки: ветка {BRANCH}, sha {SHA})")


class MissingLsTreeAnswerTest(_AutogateConditionsUnitTest):

    def test_git_not_answering_ls_tree_is_treated_as_empty_planka(self):
        """`gitcmd.ls_tree_files` возвращает `None` (git не ответил на
        сам запрос дерева, не «каталога нет») — условие «а» отказывает
        тем же fail-closed приёмом, что и для действительно пустого
        каталога, не проходит автогейтом молча.

        Ловит мутацию: код, различающий `None` и `[]` через `is None`
        без общего `or []`/эквивалента, уронил бы саму функцию
        `TypeError` на последующей итерации по `None`, а не вернул бы
        причину отказа.
        """
        ok, reason = self.call(ls_tree_files=None)

        self.assertEqual(
            reason,
            "автогейт: каталог приёмочных тестов пуст или отсутствует "
            f"(источник планки: ветка {BRANCH}, sha {SHA})")


class NonPyFilesIgnoredTest(_AutogateConditionsUnitTest):

    def test_directory_with_only_non_py_files_is_treated_as_empty(self):
        """Каталог в дереве ветки существует, но несёт только не-`.py`
        файл — тот же отказ, что и для полностью отсутствующего
        каталога (фильтр на `.py`, не голое «список путей непуст»).

        Ловит мутацию: код, убравший фильтр `p.endswith(".py")` перед
        `py_paths` (голая проверка «список путей из дерева непуст»),
        принял бы README.md за непустую планку — `sources` остался бы
        пуст (`gitcmd.show` для него не замокан), markers пуст, и
        условие «а» прошло бы автогейтом вместо ожидаемого отказа
        «каталог приёмочных тестов пуст или отсутствует».
        """
        rel = f"tasks/{self.TASK}/acceptance_tests/README.md"

        ok, reason = self.call(ls_tree_files=[rel], show_map={})

        self.assertIn("автогейт: каталог приёмочных тестов пуст или "
                      "отсутствует", reason)


class SourceNoteOnPassTest(_AutogateConditionsUnitTest):

    def test_ok_list_names_branch_and_sha_on_clean_planka(self):
        """Условие «а» пройдено (чистая планка) — перечень `ok` несёт
        точную пометку источника (ветка + полный sha), которую
        `_maybe_autogate_acceptance` кладёт в `detail` перехода
        `acceptance -> merge_gate` (SPEC AC-6).

        Ловит мутацию: код, забывший `ok.append(source_note)` на пути
        пройденного условия «а» (называть источник — не только на
        отказе, но и на успехе, того требует SPEC AC-6), — тест уронил
        бы `assertIn`; тесты на путях отказа (`reason`) такой пропуск
        не поймали бы, поэтому нужен отдельный тест именно ветки успеха.
        """
        rel = f"tasks/{self.TASK}/acceptance_tests/test_marker.py"
        content = (
            '"""Чистая планка юнит-теста."""\n'
            "import unittest\n\n\n"
            "class MarkerTest(unittest.TestCase):\n"
            "    def test_ac1_marker(self):\n"
            "        self.assertTrue(True)\n"
        )

        ok, reason = self.call(ls_tree_files=[rel], show_map={rel: content})

        self.assertIsNone(reason)
        self.assertIn(f"источник планки: ветка {BRANCH}, sha {SHA}", ok)


class DiskAccTdirIgnoredForConditionATest(_AutogateConditionsUnitTest):

    def test_disk_scan_helper_is_never_called(self):
        """Условие «а» не читает диск рабочей копии вовсе — старое ядро
        `guard.scan_acceptance_tests` (принимает `Path`, читает диск) не
        имеет права быть вызванным реализацией.

        Ловит мутацию: частичный откат правки (например, оставленный по
        ошибке вызов дискового пути как запасного варианта) — мок
        роняет тест немедленно вместо того, чтобы молча совпасть по
        результату, как совпал бы AC-1 приёмочный тест только по
        отсутствию manual-маркера.
        """
        rel = f"tasks/{self.TASK}/acceptance_tests/test_marker.py"
        content = (
            '"""Чистая планка юнит-теста."""\n'
            "import unittest\n\n\n"
            "class MarkerTest(unittest.TestCase):\n"
            "    def test_ac1_marker(self):\n"
            "        self.assertTrue(True)\n"
        )

        with mock.patch.object(
                guard, "scan_acceptance_tests",
                side_effect=AssertionError(
                    "condition A must not touch the disk-based scan")):
            ok, reason = self.call(ls_tree_files=[rel], show_map={rel: content})

        self.assertIsNone(reason)


def _ci_marker_planka(task: str, n: int, reason: str) -> tuple[str, str]:
    rel = f"tasks/{task}/acceptance_tests/test_marker.py"
    content = (f'"""Планка с единственной пометкой ci."""\n'
              f"# AC-{n}: ci — {reason}\n")
    return rel, content


class CiMarkerConditionTest(_AutogateConditionsUnitTest):
    """Пометка `ci` (01M1SHJTT0V516BWHYXWS50F3G, требования 2, 3): не
    смешивается с manual/skip (AC-3), исполняется по зелёному CI ГОЛОВЫ
    КОДОВОЙ ветки задачи `t["branch"]`, не артефактной ветки планки
    (AC-4, AC-5)."""

    def test_green_ci_satisfies_the_ci_marker(self):
        """Ловит мутацию: код, не добавляющий `ok`-запись на зелёном CI
        (или добавляющий её, но не пропускающий дальше к условиям б/в/г/д),
        уронил бы либо непустой `reason`, либо отсутствие строки про
        ci-критерии в перечне выполненных условий."""
        rel, content = _ci_marker_planka(self.TASK, 1, "CI ветки зелёный")

        ok, reason = self.call(
            ls_tree_files=[rel], show_map={rel: content},
            verifying_status=(ci.VERIFYING_GREEN, "CI коммита abc12345 "
                              "зелёный (2 проверок)"))

        self.assertIsNone(reason)
        self.assertTrue(any("критерии ci подтверждены" in line and "AC-1" in line
                            for line in ok))

    def test_red_ci_blocks_the_ci_marker(self):
        """AC-5: CI красный — критерий `ci` не засчитан, автогейт
        отказывает с причиной, называющей критерий и статус CI."""
        rel, content = _ci_marker_planka(self.TASK, 1, "CI ветки зелёный")

        ok, reason = self.call(
            ls_tree_files=[rel], show_map={rel: content},
            verifying_status=(ci.VERIFYING_RED, "CI коммита abc12345 не "
                              "зелёный: python=failure"))

        self.assertIsNotNone(reason)
        self.assertIn("AC-1", reason)
        self.assertIn("python=failure", reason)

    def test_missing_ci_data_blocks_the_ci_marker(self):
        """AC-5: данных CI нет вовсе (`VERIFYING_NONE`) — тот же fail-
        closed отказ, что и для явно красного CI, не автопроход."""
        rel, content = _ci_marker_planka(self.TASK, 1, "CI ветки зелёный")

        ok, reason = self.call(
            ls_tree_files=[rel], show_map={rel: content},
            verifying_status=(ci.VERIFYING_NONE, "проверок нет вовсе"))

        self.assertIsNotNone(reason)
        self.assertIn("AC-1", reason)

    def test_ci_marker_is_not_reported_as_manual_or_skip(self):
        """AC-3: присутствие пометки `ci` само по себе не отправляет
        задачу на ручной гейт — отказ (когда он есть) обязан звучать про
        статус CI, а не «критерии manual»/«критерии skip»."""
        rel, content = _ci_marker_planka(self.TASK, 1, "CI ветки зелёный")

        ok, reason = self.call(
            ls_tree_files=[rel], show_map={rel: content},
            verifying_status=(ci.VERIFYING_NONE, "проверок нет вовсе"))

        self.assertIsNotNone(reason)
        self.assertNotIn("критерии manual", reason)
        self.assertNotIn("критерии skip", reason)

    def test_ci_marker_queries_the_code_branch_not_the_artifact_branch(self):
        """Требование 2: sha головы КОДОВОЙ ветки (`t["branch"]`), не
        артефактной ветки планки (`BRANCH`, откуда читается сама
        пометка) — `fake_verifying_status` в `call()` уже требует это
        через `assertEqual`, здесь фиксируется явным тестом, чтобы
        регресс не потерялся при рефакторинге."""
        rel, content = _ci_marker_planka(self.TASK, 1, "CI ветки зелёный")

        ok, reason = self.call(ls_tree_files=[rel], show_map={rel: content})

        self.assertIsNone(reason)


class PullMergeCommitsTest(unittest.TestCase):
    """Юнит-тесты `fsm_autogate._acceptance_pull_merge_commits`
    (01M2B6K76EAFDF5X1B3Z9XK30Q, требование 3/AC-3) — угол, который
    приёмочные тесты задачи (реальный git, всегда отвечающий) не бьют:
    git не ответил на сам запрос."""

    def test_git_not_answering_gives_empty_list(self):
        """Ловит мутацию: код, не проверяющий `res is None`/`returncode`
        перед `res.stdout.splitlines()`, уронил бы `AttributeError` на
        `None` вместо пустого списка — тот же вырожденный случай, что и
        у прочих примитивов `gitcmd`."""
        with mock.patch.object(gitcmd, "git", return_value=None):
            self.assertEqual(
                fsm_autogate._acceptance_pull_merge_commits(CODE_BRANCH), [])

    def test_full_sha_lines_are_returned(self):
        """Ловит мутацию: формат `%h` (сокращённый sha) вместо `%H` —
        тест сверяет ДЛИНУ строки (40 знаков полного sha), сокращённый
        вариант её не даст."""
        res = mock.Mock(returncode=0, stdout=f"{SHA}\n")

        with mock.patch.object(gitcmd, "git", return_value=res) as git_mock:
            merges = fsm_autogate._acceptance_pull_merge_commits(CODE_BRANCH)

        git_mock.assert_called_once_with("log", "--merges", "--format=%H",
                                         CODE_BRANCH)
        self.assertEqual(merges, [SHA])


class ManualCriteriaExcludesCiTest(_AutogateConditionsUnitTest):
    """Юнит-тест `fsm_autogate._acceptance_manual_criteria`
    (01M2B6K76EAFDF5X1B3Z9XK30Q, требование 3/AC-3) — угол, который
    приёмочные тесты задачи не заводят (там нет пометки `ci`)."""

    def test_ci_marker_is_excluded_manual_and_skip_are_kept(self):
        """Ловит мутацию: фильтр `kind in ("manual", "skip", "escalate")`,
        ослабленный до «любой kind» (или потерянный вовсе), протащил бы
        AC-1 (`ci`) в список — критерий `ci` не остаётся человеку, его
        уже проверяет автогейт (условие «а»), не предмет группы «б»."""
        rel = f"tasks/{self.TASK}/acceptance_tests/test_marker.py"
        content = ('"""Планка со смесью пометок."""\n'
                  "# AC-1: ci — CI ветки зелёный.\n"
                  "# AC-2: skip — обоснование причины skip.\n")

        with mock.patch.object(gitcmd, "ls_tree_files", return_value=[rel]), \
             mock.patch.object(gitcmd, "show", return_value=(content, "")):
            items = fsm_autogate._acceptance_manual_criteria(self.TASK, BRANCH)

        self.assertEqual(len(items), 1, items)
        self.assertIn("AC-2", items[0])
        self.assertNotIn("AC-1", " ".join(items))


class AcceptanceChecklistDetailMergesOmittedTest(unittest.TestCase):
    """Юнит-тест `fsm_autogate._acceptance_checklist_detail`
    (01M2B6K76EAFDF5X1B3Z9XK30Q, требование 3/AC-3) — манускрит-критерий
    есть, но подтяжек main не было вовсе: строка «родители подтяжек» не
    имеет права появиться (требование 3: «если такие были»)."""

    TASK = "T001"

    def test_no_merges_means_no_parents_line(self):
        """Ловит мутацию: код, печатающий строку «родители подтяжек:»
        даже с пустым списком (`if merges:` ослаблен до безусловного
        добавления) — `assertNotIn` ниже поймает пустую строку после
        двоеточия."""
        t = {"branch": CODE_BRANCH, "spent_usd": 0.0, "budget_usd": 5.0}
        rel = f"tasks/{self.TASK}/acceptance_tests/test_marker.py"
        content = ('"""Планка с manual-критерием."""\n'
                  "# AC-3: manual — проверка руками.\n")

        with mock.patch.object(artifact_source, "resolve",
                               return_value=(BRANCH, True)), \
             mock.patch.object(gitcmd, "branch_head_sha", return_value=SHA), \
             mock.patch.object(gitcmd, "ls_tree_files", return_value=[rel]), \
             mock.patch.object(gitcmd, "show", return_value=(content, "")), \
             mock.patch.object(gitcmd, "git",
                               return_value=mock.Mock(returncode=0, stdout="")):
            detail = fsm_autogate._acceptance_checklist_detail(
                object(), self.TASK, t, 1)

        self.assertIn("остаётся человеку", detail)
        self.assertNotIn("родители подтяжек", detail)


class MaybeAutogateChecklistJournalTest(unittest.TestCase):
    """Юнит-тесты AC-1 (01M2B6K76EAFDF5X1B3Z9XK30Q): `_maybe_autogate_
    acceptance` журналирует «приёмка: что проверит approve» РОВНО один
    раз, независимо от исхода `_autogate_conditions` — тот же приём
    развязки, что уже применяют юнит-тесты `_autogate_conditions` выше
    (условия б/в/г/д заглушены; здесь заглушён весь автогейт разом, так
    как предмет теста — количество журнальных записей, не их содержание).
    """

    TASK = "T001"

    def _run(self, *, autogate_reason):
        t = {"branch": CODE_BRANCH, "spent_usd": 0.0, "budget_usd": 5.0}
        journal_calls = []

        def fake_journal(conn, task_id, actor, action, detail=""):
            journal_calls.append((actor, action, detail))

        with mock.patch.object(artifact_source, "resolve",
                               return_value=(BRANCH, True)), \
             mock.patch.object(gitcmd, "branch_head_sha", return_value=SHA), \
             mock.patch.object(gitcmd, "ls_tree_files", return_value=None), \
             mock.patch.object(fsm_autogate, "_autogate_conditions",
                               return_value=(["ok"], autogate_reason)), \
             mock.patch.object(gates, "policy", return_value=gates.AUTO), \
             mock.patch.object(store, "journal", side_effect=fake_journal), \
             mock.patch.object(store, "set_state") as set_state_mock, \
             mock.patch.object(store, "task_target", return_value="artel"), \
             mock.patch.object(fixation, "approve_sha_hint", return_value=""):
            fsm_autogate._maybe_autogate_acceptance(
                object(), self.TASK, t, Path("/no/such/dir"), 1)

        checklist_calls = [c for c in journal_calls
                           if c[1] == fsm_autogate.ACCEPTANCE_CHECKLIST_ACTION]
        return checklist_calls, set_state_mock

    def test_checklist_logged_once_when_autogate_refuses(self):
        """Ловит мутацию: запись, дублируемая на каждый вызов (или
        случайно журналируемая ещё раз внутри ветки отказа) — `len`
        отличился бы от 1."""
        calls, set_state_mock = self._run(
            autogate_reason="автогейт: критерии manual — AC-1")

        self.assertEqual(len(calls), 1, calls)
        set_state_mock.assert_not_called()

    def test_checklist_logged_once_when_autogate_passes(self):
        """Ловит мутацию: печать/журнал чек-листа, поставленные ПОСЛЕ
        решения автогейта и обусловленные его исходом (например, только
        в ветке отказа) — на пути «все условия выполнены» запись
        пропала бы, `len` был бы 0."""
        calls, set_state_mock = self._run(autogate_reason=None)

        self.assertEqual(len(calls), 1, calls)
        set_state_mock.assert_called_once()

    def test_no_checklist_when_gate_policy_is_manual(self):
        """SPEC T066 AC-5 (не должна ослабнуть этой задачей): политика
        гейта не `auto` — функция не журналирует и не печатает ничего,
        включая новую запись чек-листа.

        Ловит мутацию: чек-лист, вынесенный ДО отсечки `gates.policy`,
        — `store.journal` был бы вызван даже на политике `manual`."""
        t = {"branch": CODE_BRANCH, "spent_usd": 0.0, "budget_usd": 5.0}

        with mock.patch.object(gates, "policy", return_value=gates.MANUAL), \
             mock.patch.object(store, "journal") as journal_mock:
            fsm_autogate._maybe_autogate_acceptance(
                object(), self.TASK, t, Path("/no/such/dir"), 1)

        journal_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
