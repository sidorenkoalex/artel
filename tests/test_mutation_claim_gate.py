"""Юнит-тесты гейта заявки мутации на `in_dev -> verifying` (SPEC
01M29A0F88P9GKSXFW90F99H2N, требования 2-4, AC-5..AC-9) — тот же класс
приёма, что `tests/test_zones_gate.py` для соседнего гейта зон: fail-closed
на сбое git, пропуск для канарейки/внешнего target, отбор только
`tests/test_*.py`, детали отказа несут файл и имена функций.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, fsm_advance, gitcmd  # noqa: E402
from tests.sandbox import TaskIdSchemaConnTmpRootTest  # noqa: E402


def _task_row(target=config.DEFAULT_TARGET, is_canary=False):
    return {"branch": "task/t001-x", "target": target, "is_canary": is_canary}


class MutationClaimGateGitFailureTest(TaskIdSchemaConnTmpRootTest):

    def test_git_not_answering_diff_base_refuses(self):
        """Ловит мутацию: `if base is None: ... return True` убран/заменён
        на пропуск — неответ git на merge-base молча пропускал бы переход
        (fail-open вместо fail-closed, AC-7)."""
        t = _task_row()
        with mock.patch.object(gitcmd, "diff_base", return_value=None):
            refuses = fsm_advance._run_gates(
                self.conn, self.task_id,
                [lambda: fsm_advance._mutation_claim_gate(
                    self.conn, self.task_id, t, "task/t001-x")])
        self.assertTrue(refuses)
        details = [r["detail"] for r in self.conn.execute(
            "SELECT detail FROM steps WHERE task_id=?", (self.task_id,))]
        self.assertTrue(any("гейт заявки мутации" in d for d in details))

    def test_git_not_answering_diff_names_refuses(self):
        """Ловит мутацию: тот же класс отказа для `diff_names`, не только
        `diff_base` — точечный фикс одной из двух git-точек сбоя не
        закрывает второй (skills/coding-standards.md, «чини класс, не
        экземпляр»)."""
        t = _task_row()
        with mock.patch.object(gitcmd, "diff_base",
                               return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names", return_value=None):
            refusal = fsm_advance._mutation_claim_gate(
                self.conn, self.task_id, t, "task/t001-x")
        self.assertIsNotNone(refusal)
        self.assertIn("гейт заявки мутации", refusal.action)


class MutationClaimGateSkipConditionsTest(unittest.TestCase):

    def test_canary_task_skips_the_gate(self):
        """Ловит мутацию: условие `t["is_canary"]` убрано — канареечная
        задача звала бы `diff_base` вопреки AC-8, хотя её `verifying` не
        читает origin/CI вовсе."""
        t = _task_row(is_canary=True)

        def boom(*args, **kwargs):
            raise AssertionError("гейт заявки мутации не обязан звать "
                                 "diff_base для канареечной задачи")

        with mock.patch.object(gitcmd, "diff_base", boom):
            refusal = fsm_advance._mutation_claim_gate(
                None, "T001", t, "task/t001-x")
        self.assertIsNone(refusal)

    def test_external_target_skips_the_gate(self):
        """Ловит мутацию: условие внешнего target убрано — diff в
        `config.ROOT` не видит код внешнего target, а гейт всё равно
        пытался бы его читать (AC-8)."""
        t = _task_row(target="some-external-target")

        def boom(*args, **kwargs):
            raise AssertionError("гейт заявки мутации не обязан звать "
                                 "diff_base для внешнего target")

        with mock.patch.object(gitcmd, "diff_base", boom):
            refusal = fsm_advance._mutation_claim_gate(
                None, "T001", t, "task/t001-x")
        self.assertIsNone(refusal)


class _MutationClaimGateRowTest(TaskIdSchemaConnTmpRootTest):
    """`TaskIdSchemaConnTmpRootTest` + `self.t` — общий предок двух классов
    ниже (SPEC 01M2DC6SQVSANMECXPDZJDP75D, R8: их `setUp` были байт-в-байт
    одинаковы; `_task_row` — локальная функция этого файла, поэтому общий
    класс живёт здесь, не в tests/sandbox.py)."""

    def setUp(self):
        super().setUp()
        self.t = _task_row()


class MutationClaimGateFileSelectionTest(_MutationClaimGateRowTest):

    def test_non_test_path_is_not_checked(self):
        """Ловит мутацию: фильтр путей ослаблен до «любой .py» — файл вне
        `tests/test_*.py` (например, правка `orchestrator/store.py` в том
        же диффе) не должен проверяться этим гейтом вовсе (AC-5)."""
        with mock.patch.object(gitcmd, "diff_base",
                               return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names",
                               return_value=["orchestrator/store.py"]), \
             mock.patch.object(gitcmd, "show") as show_mock:
            refusal = fsm_advance._mutation_claim_gate(
                self.conn, self.task_id, self.t, "task/t001-x")
        self.assertIsNone(refusal)
        show_mock.assert_not_called()

    def test_nested_test_path_is_not_checked(self):
        """Ловит мутацию: фильтр путей проверяет только префикс/суффикс
        строки (`startswith("tests/test_")`/`endswith(".py")`) без
        проверки глубины — `tests/test_sub/test_nested.py` тоже начинается
        с `tests/test_` и оканчивается на `.py`, но это не файл верхнего
        уровня `tests/test_*.py` из AC-5."""
        with mock.patch.object(gitcmd, "diff_base",
                               return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names",
                               return_value=["tests/test_sub/test_nested.py"]), \
             mock.patch.object(gitcmd, "show") as show_mock:
            refusal = fsm_advance._mutation_claim_gate(
                self.conn, self.task_id, self.t, "task/t001-x")
        self.assertIsNone(refusal)
        show_mock.assert_not_called()

    def test_file_deleted_in_head_is_skipped(self):
        """Ловит мутацию: `head_source is None` (файл удалён в HEAD) не
        обрабатывается отдельно — гейт передал бы `None` в
        `test_functions_without_mutation_claim` как валидный текст и
        либо упал, либо ложно отказал на уже несуществующем файле."""
        def fake_show(branch, path):
            return (None, "файла нет в этой ветке")

        with mock.patch.object(gitcmd, "diff_base",
                               return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names",
                               return_value=["tests/test_gone.py"]), \
             mock.patch.object(gitcmd, "show", fake_show):
            refusal = fsm_advance._mutation_claim_gate(
                self.conn, self.task_id, self.t, "task/t001-x")
        self.assertIsNone(refusal)

    def test_git_not_answering_show_refuses_not_skips(self):
        """Ловит мутацию: `head_reason == "git не ответил"` не отличается
        от легитимного отсутствия пути в HEAD — сбой самого git на
        чтении СУЩЕСТВУЮЩЕГО файла молча пропускал бы проверку заявки
        вместо отказа (R1-F2, REVIEW.md 01M29A0F88P9GKSXFW90F99H2N
        итерации 1)."""
        def fake_show(branch, path):
            return (None, "git не ответил")

        with mock.patch.object(gitcmd, "diff_base",
                               return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names",
                               return_value=["tests/test_a.py"]), \
             mock.patch.object(gitcmd, "show", fake_show):
            refusal = fsm_advance._mutation_claim_gate(
                self.conn, self.task_id, self.t, "task/t001-x")
        self.assertIsNotNone(refusal)
        self.assertIn("гейт заявки мутации", refusal.action)

    def test_undecodable_file_refuses_not_skips(self):
        """Ловит мутацию: причина «не прочитан: …» (`UnicodeDecodeError`
        на нестандартной кодировке файла, `gitcmd.show`) трактуется как
        легитимное удаление — тест без заявки мутации проскочил бы гейт
        именно там, где штатный (декодируемый) файл был бы пойман
        (R1-F2)."""
        def fake_show(branch, path):
            if branch == "deadbeef":
                return (None, "новый файл")
            return (None, "не прочитан: 'utf-8' codec can't decode byte 0xff")

        with mock.patch.object(gitcmd, "diff_base",
                               return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names",
                               return_value=["tests/test_binary.py"]), \
             mock.patch.object(gitcmd, "show", fake_show):
            refusal = fsm_advance._mutation_claim_gate(
                self.conn, self.task_id, self.t, "task/t001-x")
        self.assertIsNotNone(refusal)
        self.assertIn("гейт заявки мутации", refusal.action)
        self.assertIn("tests/test_binary.py", refusal.detail)

    def test_unclassified_show_failure_on_path_present_in_tree_refuses(self):
        """Ловит мутацию: третья причина сбоя `gitcmd.show` (ни «git не
        ответил», ни «не прочитан: …» — например, повреждённый объект или
        недоступный blob) на пути, который РЕАЛЬНО есть в дереве HEAD
        (`gitcmd.ls_tree_files`), трактуется как легитимное удаление и
        молча пропускается — REVIEW.md 01M29A0F88P9GKSXFW90F99H2N
        итерации 3, R1-F2: `ls_tree_files` даёт независимый от текста
        причины ответ «путь есть в дереве», и такой путь обязан
        отказывать, а не пропускаться."""
        def fake_show(branch, path):
            if branch == "deadbeef":
                return (None, "новый файл")
            return (None, "недоступный blob")

        with mock.patch.object(gitcmd, "diff_base",
                               return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names",
                               return_value=["tests/test_broken.py"]), \
             mock.patch.object(gitcmd, "show", fake_show), \
             mock.patch.object(gitcmd, "ls_tree_files",
                               return_value=["tests/test_broken.py"]):
            refusal = fsm_advance._mutation_claim_gate(
                self.conn, self.task_id, self.t, "task/t001-x")
        self.assertIsNotNone(refusal)
        self.assertIn("гейт заявки мутации", refusal.action)
        self.assertIn("tests/test_broken.py", refusal.detail)

    def test_unclassified_show_failure_on_path_absent_from_tree_skips(self):
        """Ловит мутацию: если `path in tree` заменить на безусловный
        отказ (без проверки принадлежности дереву), легитимно удалённый
        файл с непризнанной причиной `gitcmd.show` тоже отказывал бы —
        `ls_tree_files`, вернувший список БЕЗ этого пути, обязан
        подтверждать легитимное удаление так же, как и раньше."""
        def fake_show(branch, path):
            if branch == "deadbeef":
                return (None, "новый файл")
            return (None, "недоступный blob")

        with mock.patch.object(gitcmd, "diff_base",
                               return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names",
                               return_value=["tests/test_gone2.py"]), \
             mock.patch.object(gitcmd, "show", fake_show), \
             mock.patch.object(gitcmd, "ls_tree_files",
                               return_value=["tests/test_other.py"]):
            refusal = fsm_advance._mutation_claim_gate(
                self.conn, self.task_id, self.t, "task/t001-x")
        self.assertIsNone(refusal)


class MutationClaimGateRefusalContentTest(_MutationClaimGateRowTest):

    def test_missing_claim_produces_named_refusal_with_file_and_function(self):
        """Ловит мутацию: имена функций из `guard.
        test_functions_without_mutation_claim` не попадают в `detail` —
        Оператор/разработчик не узнал бы, какой именно тест без заявки
        (AC-6)."""
        head_source = "def test_new():\n    assert True\n"

        def fake_show(branch, path):
            if branch == "deadbeef":
                return (None, "новый файл")
            return (head_source, "")

        with mock.patch.object(gitcmd, "diff_base",
                               return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names",
                               return_value=["tests/test_new_thing.py"]), \
             mock.patch.object(gitcmd, "show", fake_show):
            refusal = fsm_advance._mutation_claim_gate(
                self.conn, self.task_id, self.t, "task/t001-x")
        self.assertIsNotNone(refusal)
        self.assertIn("tests/test_new_thing.py: test_new", refusal.detail)
        self.assertIn("Ловит мутацию", refusal.detail)
        self.assertIn("advance", refusal.hint)

    def test_claim_present_gives_no_refusal(self):
        """Ловит мутацию: гейт отказывает безусловно на новом тесте вне
        зависимости от докстринга — валидная заявка обязана пропускать
        переход."""
        head_source = ('def test_new():\n'
                       '    """Ловит мутацию: пустой список вместо ошибки."""\n'
                       '    assert True\n')

        def fake_show(branch, path):
            if branch == "deadbeef":
                return (None, "новый файл")
            return (head_source, "")

        with mock.patch.object(gitcmd, "diff_base",
                               return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names",
                               return_value=["tests/test_new_thing.py"]), \
             mock.patch.object(gitcmd, "show", fake_show):
            refusal = fsm_advance._mutation_claim_gate(
                self.conn, self.task_id, self.t, "task/t001-x")
        self.assertIsNone(refusal)


if __name__ == "__main__":
    unittest.main()
