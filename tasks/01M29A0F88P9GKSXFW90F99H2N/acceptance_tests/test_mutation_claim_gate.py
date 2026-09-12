"""Приёмочные тесты AC-5..AC-9 (задача 01M29A0F88P9GKSXFW90F99H2N):
`orchestrator/fsm_advance.py::_mutation_claim_gate` — восьмой рубеж
перехода `in_dev -> verifying`, сверяющий дифф ветки с заявкой «Ловит
мутацию: …» в новых/изменённых тестах `tests/test_*.py` через
`scripts.guard.test_functions_without_mutation_claim`.

Красен до реализации: `fsm_advance._mutation_claim_gate` ещё не
существует (SPEC 01M29A0F88P9GKSXFW90F99H2N, требование 2) — каждый
тест, вызывающий его напрямую, падает `AttributeError`; тест порядка
вызова (`test_ac5_gate_wired_between_zones_and_review_rework_gates`)
падает `AssertionError` на `assertIn`, потому что имя гейта ещё не
встречается в исходнике `in_dev`.
"""
import inspect
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from orchestrator import brief, config, fsm_advance, gitcmd, store  # noqa: E402
from scripts import guard  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class GateWiredInInDevOrderTest(unittest.TestCase):

    def test_ac5_gate_wired_between_zones_and_review_rework_gates(self):
        """В исходнике `in_dev()` вызов `_mutation_claim_gate` стоит
        СТРОГО между вызовом `_zones_gate_refuses` и вызовом
        `_review_rework_gate_refuses` — требование 2 фиксирует именно
        эту позицию, не факт вызова гейта где-то вообще.

        Ловит мутацию: гейт переставлен ДО `_zones_gate_refuses` либо
        ПОСЛЕ `_review_rework_gate_refuses` (или вызов вовсе убран из
        `in_dev`) — порядок рубежей входа в `verifying` изменится
        незаметно для остальных тестов, которые бьют по гейту напрямую,
        минуя `in_dev`.
        """
        source = inspect.getsource(fsm_advance.in_dev)
        self.assertIn("_mutation_claim_gate", source,
                     "гейт не вызывается в in_dev() вовсе")
        zones_idx = source.index("_zones_gate_refuses(")
        rework_idx = source.index("_review_rework_gate_refuses(")
        claim_idx = source.index("_mutation_claim_gate(")
        self.assertGreater(claim_idx, zones_idx)
        self.assertLess(claim_idx, rework_idx)


class MutationClaimGateSandbox(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.task_id = "T001"
        self.branch = "task/t001-x"
        self.t = {"branch": self.branch, "is_canary": False,
                 "target": config.DEFAULT_TARGET}


def _show_returning(table, default=(None, "нет файла")):
    def show(ref, rel):
        return table.get((ref, rel), default)
    return show


class MutationClaimGateFilePathFilterTest(MutationClaimGateSandbox):

    def test_ac5_only_tests_test_star_paths_are_inspected(self):
        """Дифф несёт файлы вне `tests/test_*.py` (`orchestrator/
        store.py`, `docs/backlog.md`) — гейт обязан их игнорировать
        целиком, ни разу не читая их содержимое через `git show`.

        Ловит мутацию: фильтр путей `tests/test_*.py` убран/ослаблен
        (например, заменён на «любой путь под tests/» без суффикса
        `test_*.py`, или снят вовсе) — гейт полез бы читать содержимое
        путей, которые требование 2 явно исключает из проверки, и упал
        бы на подставленном `AssertionError`.
        """
        with mock.patch.object(gitcmd, "diff_base", return_value="deadbeef"), \
             mock.patch.object(
                 gitcmd, "diff_names",
                 return_value=["orchestrator/store.py", "docs/backlog.md"]), \
             mock.patch.object(
                 gitcmd, "show",
                 side_effect=AssertionError(
                     "гейт заявки мутации прочитал путь вне tests/test_*.py")):
            refusal = fsm_advance._mutation_claim_gate(
                self.conn, self.task_id, self.t, self.branch)
        self.assertIsNone(refusal)

    def test_ac5_file_deleted_in_head_is_skipped(self):
        """Файл `tests/test_gone.py` есть в списке диффа, но в HEAD его
        уже нет (`git show <branch>:<path>` не находит файл) — гейт
        обязан молча пропустить его, не вызывая разбор AST вовсе.

        Ловит мутацию: проверка «файла нет в HEAD — пропустить» убрана
        — гейт передал бы `None` как `head_source` в функцию требования
        1, и (в зависимости от реализации) либо упал бы, либо ложно
        трактовал удалённый файл как «файл добавлен» и разобрал бы
        несуществующий текст.
        """
        table = {(self.branch, "tests/test_gone.py"): (None, "нет файла")}
        with mock.patch.object(gitcmd, "diff_base", return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names",
                              return_value=["tests/test_gone.py"]), \
             mock.patch.object(gitcmd, "show", side_effect=_show_returning(table)), \
             mock.patch.object(
                 guard, "test_functions_without_mutation_claim",
                 side_effect=AssertionError(
                     "удалённый в HEAD файл не должен доходить до разбора AST")):
            refusal = fsm_advance._mutation_claim_gate(
                self.conn, self.task_id, self.t, self.branch)
        self.assertIsNone(refusal)


class MutationClaimGateRefusalContentTest(MutationClaimGateSandbox):

    def test_ac6_refusal_names_action_files_functions_rule_and_hint(self):
        """Один файл диффа, две новые функции без заявки — `GateRefusal`
        несёт именованный `action`, `detail` с путём и обеими функциями
        и текстом правила, `hint` с командой `advance <id>`.

        Ловит мутацию: `action`/`hint` захардкожены под другой гейт
        (скопированы с `_zones_gate` без правки текста), либо `detail`
        собирает только ПЕРВУЮ найденную функцию файла вместо всех —
        Оператор не увидит вторую незаявленную функцию `test_other` в
        отказе.
        """
        head_source = (
            "def test_new():\n"
            "    return 1\n"
            "\n"
            "\n"
            "def test_other():\n"
            "    return 2\n"
        )
        table = {(self.branch, "tests/test_a.py"): (head_source, "")}
        with mock.patch.object(gitcmd, "diff_base", return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names",
                              return_value=["tests/test_a.py"]), \
             mock.patch.object(gitcmd, "show", side_effect=_show_returning(table)):
            refusal = fsm_advance._mutation_claim_gate(
                self.conn, self.task_id, self.t, self.branch)

        self.assertIsNotNone(refusal)
        self.assertEqual(refusal.action, "переход отклонён: гейт заявки мутации")
        self.assertIn("tests/test_a.py", refusal.detail)
        self.assertIn("test_new", refusal.detail)
        self.assertIn("test_other", refusal.detail)
        self.assertIn("Ловит мутацию:", refusal.detail)
        self.assertIn("skills/test-authoring.md", refusal.detail)
        self.assertIn(f"advance {self.task_id}", refusal.hint)

    def test_ac6_file_with_only_claimed_functions_does_not_refuse(self):
        """Новая функция файла несёт полноценную заявку в докстринге —
        гейт обязан пропустить переход (`None`), не отказывать зря.

        Ловит мутацию: гейт отказывает на самом ФАКТЕ изменения файла
        `tests/test_*.py`, не на отсутствии заявки — любой тронутый
        тестовый файл отказывал бы переход, даже когда все заявки на
        месте, и разработчик не смог бы сдать шаг никогда.
        """
        head_source = (
            'def test_ok():\n'
            '    """Ловит мутацию: сравнение заменили на <=, тест '
            'покраснеет."""\n'
            "    return 1\n"
        )
        table = {(self.branch, "tests/test_a.py"): (head_source, "")}
        with mock.patch.object(gitcmd, "diff_base", return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names",
                              return_value=["tests/test_a.py"]), \
             mock.patch.object(gitcmd, "show", side_effect=_show_returning(table)):
            refusal = fsm_advance._mutation_claim_gate(
                self.conn, self.task_id, self.t, self.branch)
        self.assertIsNone(refusal)


class MutationClaimGateGitFailureTest(MutationClaimGateSandbox):

    def test_ac7_git_not_answering_diff_base_refuses(self):
        """`gitcmd.diff_base` не ответил (`None`) — база сравнения не
        определена, гейт обязан отказать именованной причиной, не
        пропустить переход молча (fail-closed, тот же принцип, что и
        гейт зон).

        Ловит мутацию: проверка `base is None` убрана — гейт передал бы
        `None` дальше как базу diff'а вместо явного отказа (fail-open).
        """
        with mock.patch.object(gitcmd, "diff_base", return_value=None), \
             mock.patch.object(
                 gitcmd, "diff_names",
                 side_effect=AssertionError(
                     "без базы сравнения список файлов диффа не нужен")):
            refusal = fsm_advance._mutation_claim_gate(
                self.conn, self.task_id, self.t, self.branch)
        self.assertIsNotNone(refusal)
        self.assertTrue(refusal.action.startswith("переход отклонён"))

    def test_ac7_git_not_answering_diff_names_refuses(self):
        """`gitcmd.diff_names` не ответил (`None`) — список файлов диффа
        не получен, гейт обязан отказать именованной причиной.

        Ловит мутацию: проверка `files is None` убрана/заменена на
        `return None` (пропуск) — сбой git молча пропустил бы переход
        вместо явного отказа (тот же класс регрессии, что
        `ZonesGateGitFailureTest` уже закрывает для гейта зон).
        """
        with mock.patch.object(gitcmd, "diff_base", return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names", return_value=None):
            refusal = fsm_advance._mutation_claim_gate(
                self.conn, self.task_id, self.t, self.branch)
        self.assertIsNotNone(refusal)
        self.assertTrue(refusal.action.startswith("переход отклонён"))


class MutationClaimGateSkipConditionsTest(MutationClaimGateSandbox):

    def test_ac8_canary_task_skips_gate_without_touching_git(self):
        """Канареечная задача (`t["is_canary"]` истинно) — гейт
        возвращает `None` БЕЗ ПРОВЕРКИ, ни разу не обращаясь к
        `gitcmd.diff_base` (тем же условием, что и `_origin_push_gate`).

        Ловит мутацию: условие `t["is_canary"]` убрано/инвертировано —
        канареечная задача, чей `verifying` не ждёт CI и не ходит на
        origin, неожиданно упёрлась бы в дифф-гейт, для которого не
        предусмотрен обход её специфики (заглушка origin и т.п.).
        """
        t = dict(self.t, is_canary=True)
        with mock.patch.object(
                gitcmd, "diff_base",
                side_effect=AssertionError(
                    "канареечная задача не должна звать diff_base")):
            refusal = fsm_advance._mutation_claim_gate(
                self.conn, self.task_id, t, self.branch)
        self.assertIsNone(refusal)

    def test_ac8_external_target_skips_gate_without_touching_git(self):
        """Задача с внешним target (`t["target"] != config.
        DEFAULT_TARGET`) — гейт возвращает `None` без проверки, не
        обращаясь к `gitcmd.diff_base`: `git diff` в `config.ROOT` не
        видит код внешнего target'а.

        Ловит мутацию: условие внешнего target убрано — гейт полез бы
        сравнивать дифф `config.ROOT` для задачи, чей код лежит в
        совсем другом репозитории, и либо отказал бы ложно, либо
        сравнил бы не с тем деревом.
        """
        t = dict(self.t, target="some-external-target")
        with mock.patch.object(
                gitcmd, "diff_base",
                side_effect=AssertionError(
                    "внешний target не должен звать diff_base")):
            refusal = fsm_advance._mutation_claim_gate(
                self.conn, self.task_id, t, self.branch)
        self.assertIsNone(refusal)


class MutationClaimGateAdvanceHistoryTest(MutationClaimGateSandbox):

    def setUp(self):
        super().setUp()
        store.insert_task(self.conn, self.task_id, "Тест гейта заявки",
                          "in_dev", self.branch, config.DEFAULT_TARGET, 10.0)
        store.journal(self.conn, self.task_id, "fsm", "state -> in_dev",
                      "вход в in_dev")

    def test_ac9_refusal_detail_reaches_advance_refusal_history(self):
        """Отказ гейта, прогнанный через тот же каркас `_run_gates`,
        которым `in_dev()` оборачивает остальные гейты этого перехода
        (`_zones_gate_refuses`/`_origin_push_gate` и т.п.), доходит до
        `brief.advance_refusal_history` — разработчик увидит имя файла
        и имя незаявленной функции в штатном блоке «ОТКАЗ ADVANCE
        (история)» без единой правки `runner.py`/`brief.py`.

        Ловит мутацию: `GateRefusal.action` гейта не начинается с
        префикса «переход отклонён» (например, использован другой
        текст-маркер) — `store.refusal_history` не опознает запись как
        отказ advance, и `advance_refusal_history` вернётся пустой
        строкой, будто отказа не было вовсе.
        """
        head_source = (
            "def test_new():\n"
            "    return 1\n"
        )
        table = {(self.branch, "tests/test_a.py"): (head_source, "")}
        with mock.patch.object(gitcmd, "diff_base", return_value="deadbeef"), \
             mock.patch.object(gitcmd, "diff_names",
                              return_value=["tests/test_a.py"]), \
             mock.patch.object(gitcmd, "show", side_effect=_show_returning(table)):
            refuses = fsm_advance._run_gates(
                self.conn, self.task_id,
                [lambda: fsm_advance._mutation_claim_gate(
                    self.conn, self.task_id, self.t, self.branch)])

        self.assertTrue(refuses)
        text = brief.advance_refusal_history(self.conn, self.task_id,
                                             "developer", "in_dev")
        self.assertIn("tests/test_a.py", text)
        self.assertIn("test_new", text)


if __name__ == "__main__":
    unittest.main()
