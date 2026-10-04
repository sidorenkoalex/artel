"""Юнит-тесты гейта неослабления тестов на `in_dev -> verifying` и на
гейте мержа (SPEC 01M3FQ2V77QNK95Z599DM124QN, требования 1-7) — тот же
класс приёма, что `tests/test_mutation_claim_gate.py` для соседнего гейта
заявки мутации: песочница, подмена примитивов чтения `gitcmd` через
`mock.patch.object`, сверка колонки detail в steps.

Настоящий git (удаление/переименование живой веткой) проверяет планка
задачи; здесь предмет — разбор ответов git, область узла, мандат
Оператора, два разных поведения на молчание git (fail-closed на переходе,
fail-open на мерже) и ПОДКЛЮЧЕНИЕ рубежа к обоим маршрутам
(`GateWiringTest`).
"""
import inspect
import subprocess
import sys
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import guard  # noqa: E402

from orchestrator import (config, fsm_advance, fsm_merge_gate,  # noqa: E402
                          gitcmd, review, store)
from orchestrator.advance_gates import test_integrity  # noqa: E402
from tests.sandbox import (SchemaSeededTmpRootTest,  # noqa: E402
                           TaskIdSchemaConnTmpRootTest)

BASE = "basesha"
CODE_BRANCH = "task/t001-x"
ARTIFACT_BRANCH = "artifact/t001"

ALPHA = '''import unittest


class AlphaTest(unittest.TestCase):

    def test_one(self):
        pass

    def test_two(self):
        pass
'''

ALPHA_WITHOUT_SECOND = '''import unittest


class AlphaTest(unittest.TestCase):

    def test_one(self):
        pass
'''

ALPHA_WITH_SKIP = '''import unittest


class AlphaTest(unittest.TestCase):

    @unittest.skip("временно")
    def test_one(self):
        pass

    def test_two(self):
        pass
'''

HELPER_WITHOUT_TESTS = '''def build(size):
    return list(range(size))
'''

# ---------------------------------------------------------------------------
# Фикстуры послабления SPEC 01M3HWXFYWVDHGW011P6BZJFYA: условный пропуск с
# названной причиной на НОВОМ методе и ранний `return` под условием. Живая
# ветка с настоящим git — предмет планки задачи; здесь предмет — ГРАНИЦЫ
# разбора, до которых планка не достаёт (смешанные маркеры на одном методе,
# вложенность `if`, вызов в условии, неконстантная причина, формы раннего
# выхода вне границы требования 5).

CONDITIONAL_SKIPS = '''import os
import unittest

import pytest

READY = os.path.exists("/bin/zsh")


class NewTest(unittest.TestCase):

    def test_call_inside_if(self):
        if not READY:
            self.skipTest("вызов внутри if")
        self.assertTrue(READY)

    @unittest.skipUnless(READY, "второй позиционный аргумент")
    def test_skip_unless_positional_reason(self):
        self.assertTrue(READY)

    @pytest.mark.skipif(not READY, reason="именованный reason")
    def test_skipif_reason_kwarg(self):
        self.assertTrue(READY)
'''

# Один новый метод под ДВУМЯ маркерами: условный с причиной и безусловный.
MIXED_MARKERS = '''import unittest

READY = False


class MixedTest(unittest.TestCase):

    @unittest.skipUnless(READY, "оболочки нет")
    @unittest.skip("чиню отдельной задачей")
    def test_both(self):
        self.assertTrue(READY)
'''

# Два вызова ОДНОГО вида в одном методе: условный и безусловный. Маркер у
# них один текстом, и годность решается по худшему вхождению.
TWO_SKIP_CALLS = '''import unittest

READY = False


class TwoCallsTest(unittest.TestCase):

    def test_two_calls(self):
        if not READY:
            self.skipTest("оболочки нет")
        self.skipTest("и вообще нечего проверять")
'''

NESTED_SKIP_CALL = '''import unittest

READY = False
PLATFORM = "darwin"


class NestedTest(unittest.TestCase):

    def test_nested(self):
        if not READY:
            for _ in range(1):
                if PLATFORM == "darwin":
                    self.skipTest("оболочки нет")
        self.assertTrue(READY)
'''

SKIP_CALL_IN_CONDITION = '''import unittest

READY = False


class ConditionTest(unittest.TestCase):

    def test_in_condition(self):
        if self.skipTest("оболочки нет"):
            pass
        self.assertTrue(READY)
'''

SKIPIF_WITHOUT_CONDITION = '''import unittest

import pytest


class NoConditionTest(unittest.TestCase):

    @pytest.mark.skipif(reason="оболочки нет")
    def test_no_condition(self):
        self.assertTrue(True)
'''

NON_STRING_REASON = '''import unittest

READY = False


class NonStringTest(unittest.TestCase):

    def test_non_string_reason(self):
        if not READY:
            self.skipTest(None)
        self.assertTrue(READY)
'''

# Новый файл без единого маркера и без раннего выхода.
PLAIN_NEW_FILE = '''import unittest


class PlainTest(unittest.TestCase):

    def test_plain(self):
        self.assertTrue(True)
'''

# Тот же ГОЛЫЙ `test_one`, что в `ALPHA`, но в НОВОМ классе: имя метода
# квалифицированное, и `BetaTest::test_one` в базе сравнения не существует.
ALPHA_PLUS_NEW_CLASS = ALPHA + '''

class BetaTest(unittest.TestCase):

    @unittest.skipUnless(False, "оболочки нет")
    def test_one(self):
        pass
'''

EARLY_RETURN = '''import unittest

READY = False


class EarlyTest(unittest.TestCase):

    def test_early(self):
        """Докстринг не считается первым исполняемым оператором."""
        if not READY:
            return
        self.assertTrue(READY)
'''

# Четыре формы раннего выхода, которые SPEC («Не входит») из границы
# требования 5 исключает дословно.
EARLY_RETURN_OUT_OF_SCOPE = '''import unittest

READY = False


class OutOfScopeTest(unittest.TestCase):

    def test_unconditional_return(self):
        return

    def test_return_is_not_the_first_statement(self):
        self.assertTrue(True)
        if not READY:
            return

    def test_branch_has_two_statements(self):
        if not READY:
            self.assertTrue(True)
            return
        self.assertTrue(READY)

    def test_return_with_a_value(self):
        if not READY:
            return None
        self.assertTrue(READY)
'''

ANSWER_SUBJECT = "T001: ANSWER-1 — ответ Оператора"
ROLE_AUTOCOMMIT_SUBJECT = "T001: артефакты шага developer (автокоммит оркестратора)"


def _task_row(target=config.DEFAULT_TARGET, is_canary=False):
    return {"branch": CODE_BRANCH, "target": target, "is_canary": is_canary}


class _GateSandbox(TaskIdSchemaConnTmpRootTest):
    """Дифф ветки задаётся записями `diff_name_status`, содержимое файлов
    — словарём `(ревизия, путь) -> текст`; ANSWER-n.md задачи — вместе с
    сообщением своего последнего коммита (мандат Оператора отличается от
    автокоммита шага роли именно им)."""

    def setUp(self):
        super().setUp()
        self.t = _task_row()
        self.entries = []
        self.sources = {}
        self.answers = {}

    def _show(self, ref, path, repo=None):
        # `repo` — клон проекта задачи (ADR-0021 п.1, этап 2): git задачи
        # получает репозиторий явно; ответ заглушки от него не зависит.
        if (ref, path) in self.sources:
            return self.sources[(ref, path)], ""
        return None, "файла нет в этой ветке"

    def _ls_tree(self, branch, rel_dir, repo=None):
        return sorted(self.answers)

    def _git(self, *args):
        # Единственный прямой вызов git из гейта — подпись последнего
        # коммита ANSWER-n.md (`_answer_commit_is_role_step_autocommit`).
        path = args[-1]
        subject = self.answers.get(path, ("", ""))[1]
        return subprocess.CompletedProcess(args, 0, f"{subject}\n", "")

    def add_answer(self, name, allowed, subject=ANSWER_SUBJECT):
        text = (f"# Ответ Оператора\n\n"
                f"{test_integrity.TEST_WEAKENING_MANDATE_MARKER} {allowed}\n"
                f"Основание: решение Оператора.\n")
        path = f"tasks/{self.task_id}/{name}"
        self.answers[path] = (text, subject)
        self.sources[(ARTIFACT_BRANCH, path)] = text

    def refusal(self):
        with mock.patch.object(gitcmd, "diff_base", return_value=BASE), \
             mock.patch.object(gitcmd, "diff_name_status",
                               return_value=self.entries), \
             mock.patch.object(gitcmd, "show", self._show), \
             mock.patch.object(gitcmd, "ls_tree_files", self._ls_tree), \
             mock.patch.object(gitcmd, "git", self._git):
            return fsm_advance._test_integrity_gate(
                self.conn, self.task_id, self.t, ARTIFACT_BRANCH)

    def journal(self):
        return [(row["action"], row["detail"]) for row in self.conn.execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.task_id,))]


class GitSilenceFailsClosedTest(_GateSandbox):

    def test_silent_diff_base_refuses(self):
        """Ловит мутацию: `base is None` трактуется как «сравнивать не с
        чем» и гейт возвращает `None` — сломанный git открывает рубеж
        целиком, вопреки ADR-0002 (требование 6, fail-closed)."""
        with mock.patch.object(gitcmd, "diff_base", return_value=None):
            refusal = fsm_advance._test_integrity_gate(
                self.conn, self.task_id, self.t, ARTIFACT_BRANCH)
        self.assertIsNotNone(refusal)
        self.assertEqual(test_integrity.TEST_INTEGRITY_REFUSAL_ACTION,
                         refusal.action)
        self.assertIn("git не ответил", refusal.detail)
        self.assertIn("advance", refusal.hint)

    def test_silent_diff_name_status_refuses(self):
        """Ловит мутацию: fail-closed поставлен только на `diff_base`
        (точечный фикс одной из трёх git-точек) — неответ на список
        файлов диффа уходит дальше как «находок нет»."""
        with mock.patch.object(gitcmd, "diff_base", return_value=BASE), \
             mock.patch.object(gitcmd, "diff_name_status", return_value=None):
            refusal = fsm_advance._test_integrity_gate(
                self.conn, self.task_id, self.t, ARTIFACT_BRANCH)
        self.assertIsNotNone(refusal)
        self.assertIn("список файлов диффа", refusal.detail)

    def test_silent_show_of_a_path_named_by_the_diff_refuses(self):
        """Ловит мутацию: `gitcmd.show`, вернувший `None`, читается как
        «пути в этой ветке нет» — сбой чтения файла, который сам же
        `git diff` назвал изменённым, неотличим от удаления, и
        ослабление внутри такого файла проходит рубеж (AC-11)."""
        self.entries = [("M", "tests/test_alpha.py", None)]
        refusal = self.refusal()
        self.assertIsNotNone(refusal)
        self.assertIn("чтение tests/test_alpha.py", refusal.detail)


class SkipConditionsTest(unittest.TestCase):

    def test_canary_task_skips_the_gate(self):
        """Ловит мутацию: условие `t["is_canary"]` не перенесено из
        образца `_mutation_claim_gate` — канарейка упирается в рубеж,
        которому в её маршруте нечего защищать (AC-10)."""
        def boom(*args, **kwargs):
            raise AssertionError("канарейке гейт не звонит diff_base")

        with mock.patch.object(gitcmd, "diff_base", boom):
            self.assertIsNone(fsm_advance._test_integrity_gate(
                None, "T001", _task_row(is_canary=True), ARTIFACT_BRANCH))

    def test_external_target_skips_the_gate(self):
        """Ловит мутацию: условие внешнего target потеряно — гейт считает
        дифф ПУЛЬТА кодом чужого репозитория (AC-10)."""
        def boom(*args, **kwargs):
            raise AssertionError("внешнему target гейт не звонит diff_base")

        with mock.patch.object(gitcmd, "diff_base", boom):
            self.assertIsNone(fsm_advance._test_integrity_gate(
                None, "T001", _task_row(target="sled"), ARTIFACT_BRANCH))


class FindingsTest(_GateSandbox):

    def test_deleted_file_with_test_methods_refuses(self):
        """Ловит мутацию: класс находки «а» собирается пересечением путей
        base и head вместо разности — удаление файла тестов проходит
        молча, как оно проходит соседний гейт заявки мутации (AC-1)."""
        self.entries = [("D", "tests/test_alpha.py", None)]
        self.sources[(BASE, "tests/test_alpha.py")] = ALPHA
        refusal = self.refusal()
        self.assertIsNotNone(refusal)
        self.assertEqual("tests/test_alpha.py: удалён", refusal.detail)

    def test_deleted_file_without_test_methods_is_not_a_finding(self):
        """Ловит мутацию: находка заводится по одному факту «путь под
        `tests/` исчез», без разбора содержимого base — уборка помощника
        или `__init__.py` начинает требовать мандата без предмета
        (требование 5, AC-6)."""
        self.entries = [("D", "tests/helpers.py", None)]
        self.sources[(BASE, "tests/helpers.py")] = HELPER_WITHOUT_TESTS
        self.assertIsNone(self.refusal())

    def test_renamed_file_is_one_finding_naming_both_paths(self):
        """Ловит мутацию: пара удалён/добавлен не сворачивается в одну
        находку — переименование докладывается как потеря тестов, и
        Оператор не отличает его от настоящего удаления (AC-2)."""
        self.entries = [("R100", "tests/test_alpha.py", "tests/test_beta.py")]
        self.sources[(BASE, "tests/test_alpha.py")] = ALPHA
        self.sources[(CODE_BRANCH, "tests/test_beta.py")] = ALPHA
        refusal = self.refusal()
        self.assertIsNotNone(refusal)
        self.assertEqual(
            "tests/test_alpha.py: переименован в tests/test_beta.py",
            refusal.detail)

    def test_rename_compares_old_base_path_against_new_head_path(self):
        """Ловит мутацию: методы у пары переименования сравниваются по
        ОДНОМУ пути (старому в обеих ревизиях либо новому) — исчезнувший
        при переименовании метод теряется, хотя требование 3 называет обе
        находки."""
        self.entries = [("R090", "tests/test_alpha.py", "tests/test_beta.py")]
        self.sources[(BASE, "tests/test_alpha.py")] = ALPHA
        self.sources[(CODE_BRANCH, "tests/test_beta.py")] = ALPHA_WITHOUT_SECOND
        refusal = self.refusal()
        self.assertIn("переименован в tests/test_beta.py", refusal.detail)
        self.assertIn("метод AlphaTest::test_two исчез", refusal.detail)

    def test_vanished_method_is_named_with_its_class(self):
        """Ловит мутацию: ast-сравнение идёт по ДОБАВЛЕННЫМ именам (как у
        гейта заявки мутации) вместо исчезнувших, либо имя класса
        теряется по дороге — Оператор не знает, какой из одноимённых
        методов двух классов пропал (AC-3)."""
        self.entries = [("M", "tests/test_alpha.py", None)]
        self.sources[(BASE, "tests/test_alpha.py")] = ALPHA
        self.sources[(CODE_BRANCH, "tests/test_alpha.py")] = ALPHA_WITHOUT_SECOND
        refusal = self.refusal()
        self.assertEqual("tests/test_alpha.py: метод AlphaTest::test_two исчез",
                         refusal.detail)

    def test_new_skip_marker_refuses_and_names_the_marker(self):
        """Ловит мутацию: распознаются только исчезнувшие методы, а класс
        находки «г» не реализован — `@unittest.skip` гасит тест без
        единого слова рубежа (AC-4)."""
        self.entries = [("M", "tests/test_alpha.py", None)]
        self.sources[(BASE, "tests/test_alpha.py")] = ALPHA
        self.sources[(CODE_BRANCH, "tests/test_alpha.py")] = ALPHA_WITH_SKIP
        refusal = self.refusal()
        self.assertEqual(
            "tests/test_alpha.py: @unittest.skip на AlphaTest::test_one",
            refusal.detail)

    def test_skip_already_present_in_base_gives_no_refusal(self):
        """Ловит мутацию: класс «г» собирается по одному head («в файле
        есть skip») без сверки с base на том же имени — каждая правка
        файла с давним законным пропуском отказывает на ровном месте
        (AC-4, вторая фраза)."""
        self.entries = [("M", "tests/test_alpha.py", None)]
        self.sources[(BASE, "tests/test_alpha.py")] = ALPHA_WITH_SKIP
        self.sources[(CODE_BRANCH, "tests/test_alpha.py")] = ALPHA_WITH_SKIP
        self.assertIsNone(self.refusal())

    def test_nested_path_is_in_scope(self):
        """Ловит мутацию: область узла скопирована у гейта заявки мутации
        (`f.count("/") == 1`) — тест в подкаталоге можно удалить мимо
        рубежа, хотя полный набор (`pytest tests`) его собирает
        (требование 2, AC-5)."""
        self.entries = [("D", "tests/deep/test_nested.py", None)]
        self.sources[(BASE, "tests/deep/test_nested.py")] = ALPHA
        self.assertIsNotNone(self.refusal())

    def test_task_acceptance_tests_are_out_of_scope(self):
        """Ловит мутацию: область расширена до «любой .py с тестовыми
        методами» без исключения планок — штатная пересборка
        `tasks/*/acceptance_tests/` начинает отказывать переходу, а лок
        планки получает второго хозяина (AC-5)."""
        self.entries = [("D", "tasks/T002/acceptance_tests/test_ac1.py", None)]
        self.sources[(BASE, "tasks/T002/acceptance_tests/test_ac1.py")] = ALPHA
        self.assertIsNone(self.refusal())

    def test_non_python_path_under_tests_is_out_of_scope(self):
        """Ловит мутацию: фильтр смотрит только на префикс `tests/` —
        удаление `tests/fixtures/data.json` идёт в `gitcmd.show` и
        разбирается как питон вместо того, чтобы быть пропущенным."""
        self.entries = [("D", "tests/fixtures/data.json", None)]
        self.assertIsNone(self.refusal())


class MandateTest(_GateSandbox):
    """Дифф из трёх находок в трёх файлах — различается только мандат."""

    def setUp(self):
        super().setUp()
        self.entries = [("D", "tests/test_doomed.py", None),
                        ("M", "tests/test_alpha.py", None)]
        self.sources[(BASE, "tests/test_doomed.py")] = ALPHA
        self.sources[(BASE, "tests/test_alpha.py")] = ALPHA
        self.sources[(CODE_BRANCH, "tests/test_alpha.py")] = ALPHA_WITHOUT_SECOND

    def test_path_element_covers_every_finding_of_that_file(self):
        """Ловит мутацию: элемент-путь сверяется на точное равенство с
        ЭЛЕМЕНТОМ находки, а не с её файлом — разрешение на
        `tests/test_doomed.py` перестаёт покрывать его удаление
        (требование 4)."""
        self.add_answer("ANSWER-1.md", "tests/test_doomed.py")
        refusal = self.refusal()
        self.assertIsNotNone(refusal)
        self.assertNotIn("test_doomed", refusal.detail)
        self.assertIn("AlphaTest::test_two", refusal.detail)

    def test_method_element_does_not_cover_the_whole_file(self):
        """Ловит мутацию: элемент с `::` сравнивается как префикс пути —
        разрешение на один метод молча становится разрешением на весь
        файл, включая его удаление (AC-7)."""
        self.add_answer("ANSWER-1.md",
                        "tests/test_alpha.py::AlphaTest::test_two")
        refusal = self.refusal()
        self.assertIsNotNone(refusal)
        self.assertIn("tests/test_doomed.py: удалён", refusal.detail)
        self.assertNotIn("test_two", refusal.detail)

    def test_mandate_covering_everything_passes_the_gate(self):
        """Ловит мутацию: мандат применяется только к своему классу
        находок (скажем, к удалённым файлам) — разрешение Оператора на
        исчезнувший метод не срабатывает вовсе (AC-7)."""
        self.add_answer("ANSWER-1.md",
                        "tests/test_doomed.py, "
                        "tests/test_alpha.py::AlphaTest::test_two")
        self.assertIsNone(self.refusal())

    def test_covered_findings_are_journalled_as_allowed(self):
        """Ловит мутацию: покрытые находки просто отфильтровываются перед
        сборкой detail, без записи в журнал — Оператор видит отказ об
        одной находке и не узнаёт, что вторая прошла по его мандату
        (AC-8)."""
        self.add_answer("ANSWER-1.md", "tests/test_doomed.py")
        self.refusal()
        allowed = [detail for action, detail in self.journal()
                   if action == test_integrity.TEST_INTEGRITY_ALLOWED_ACTION]
        self.assertEqual(
            ["tests/test_doomed.py: удалён — разрешено ANSWER-1"], allowed)

    def test_answer_committed_by_a_role_autocommit_is_not_a_mandate(self):
        """Ловит мутацию: `_answer_commit_is_role_step_autocommit` не
        вызывается (мандат читается по одному тексту файла) — developer
        кладёт ANSWER-n.md в собственный `tasks/<id>/` прямо в шаге
        `in_dev` и сам себе выписывает разрешение (AC-9)."""
        self.add_answer("ANSWER-1.md",
                        "tests/test_doomed.py, "
                        "tests/test_alpha.py::AlphaTest::test_two",
                        subject=ROLE_AUTOCOMMIT_SUBJECT)
        refusal = self.refusal()
        self.assertIsNotNone(refusal)
        self.assertIn("tests/test_doomed.py: удалён", refusal.detail)
        self.assertIn("AlphaTest::test_two", refusal.detail)

    def test_refusal_hint_names_the_mandate_line(self):
        """Ловит мутацию: подсказка отказа не называет строку мандата —
        роль (и Оператор) не знает, каким именно текстом разрешение
        выдаётся, и пишет его своими словами, которые гейт не читает
        (требование 6)."""
        refusal = self.refusal()
        self.assertIn(test_integrity.TEST_WEAKENING_MANDATE_MARKER,
                      refusal.hint)
        self.assertIn("advance", refusal.hint)


class RenameMandateTest(_GateSandbox):
    """Мандат на пару переименования читается по ЛЮБОМУ из двух путей
    (REVIEW итерация 1, R1-F2): Оператор пишет разрешение, глядя на ветку
    и на PR, где файл уже под новым именем."""

    def setUp(self):
        super().setUp()
        self.entries = [("R090", "tests/test_alpha.py", "tests/test_beta.py")]
        self.sources[(BASE, "tests/test_alpha.py")] = ALPHA
        self.sources[(CODE_BRANCH, "tests/test_beta.py")] = ALPHA_WITHOUT_SECOND

    def test_mandate_on_the_new_path_covers_the_rename_and_its_method(self):
        """Ловит мутацию: `mandate_elements` знает только путь из базы
        сравнения — Оператор выписывает разрешение на имя, которое видит в
        ветке (`tests/test_beta.py`), гейт его не засчитывает и отказывает
        второй раз на безупречно выписанном мандате."""
        self.add_answer("ANSWER-1.md",
                        "tests/test_beta.py, "
                        "tests/test_beta.py::AlphaTest::test_two")
        self.assertIsNone(self.refusal())

    def test_mandate_on_the_old_path_still_covers_the_rename(self):
        """Ловит мутацию: признание нового пути сделано ВМЕСТО старого
        (подмена, а не добавление) — разрешение по пути из базы сравнения,
        который отказ называет первым, перестаёт работать."""
        self.add_answer("ANSWER-1.md", "tests/test_alpha.py")
        self.assertIsNone(self.refusal())

    def test_method_element_of_a_rename_does_not_cover_the_rename_itself(self):
        """Ловит мутацию: признание второго пути расширено до совпадения
        по префиксу — разрешение на один метод переименованного файла
        начинает покрывать и само переименование."""
        self.add_answer("ANSWER-1.md",
                        "tests/test_beta.py::AlphaTest::test_two")
        refusal = self.refusal()
        self.assertIsNotNone(refusal)
        self.assertEqual(
            "tests/test_alpha.py: переименован в tests/test_beta.py",
            refusal.detail)


class ConditionalSkipInNewMethodTest(_GateSandbox):
    """Послабление SPEC 01M3HWXFYWVDHGW011P6BZJFYA (требования 1-3, 7):
    маркер пропуска на НОВОМ методе находкой не считается, если он
    одновременно условный и с названной причиной, и уходит в журнал."""

    PATH = "tests/test_new.py"

    def added(self, source):
        """Единственная правка ветки — НОВЫЙ файл тестов `source`."""
        self.entries = [("A", self.PATH, None)]
        self.sources[(CODE_BRANCH, self.PATH)] = source
        return self.refusal()

    def skips(self):
        return [detail for action, detail in self.journal()
                if action == test_integrity.TEST_INTEGRITY_CONDITIONAL_SKIP_ACTION]

    def test_three_conditional_forms_pass_and_go_to_the_journal(self):
        """Ловит мутацию: послабление реализовано для одной формы из трёх
        (разбирается только декоратор, только `reason=`, только второй
        позиционный) либо запись журнала собрана из голого имени метода без
        класса и файла — честный неприменимый тест снова гонят за мандатом,
        а прошедший пропуск теряется для ревьювера."""
        self.assertIsNone(self.added(CONDITIONAL_SKIPS))
        self.assertEqual(
            ["tests/test_new.py::NewTest::test_call_inside_if — "
             "вызов внутри if; "
             "tests/test_new.py::NewTest::test_skip_unless_positional_reason "
             "— второй позиционный аргумент; "
             "tests/test_new.py::NewTest::test_skipif_reason_kwarg — "
             "именованный reason"],
            self.skips())

    def test_excused_marker_texts_are_the_guard_marker_texts(self):
        """Ловит мутацию: текст маркера собран в узле своим разбором
        точечного имени, а не тем, которым его видит
        `guard.test_skip_markers` — послабление сверяется с маркером,
        которого в наборе гейта нет, и молча не срабатывает ни на одной
        форме."""
        markers = guard.test_skip_markers(CONDITIONAL_SKIPS)
        for name, node in guard.qualified_test_methods(CONDITIONAL_SKIPS).items():
            self.assertEqual(markers[name],
                             set(test_integrity._excused_skips(node)), name)

    def test_unconditional_marker_beside_a_conditional_one_stays_a_finding(self):
        """Ловит мутацию: послабление решает судьбу МЕТОДА, а не каждого
        маркера — один условный декоратор с причиной снимает с того же
        метода и `@unittest.skip`, гасящий его на всех машинах навсегда
        (требование 3 называет такой маркер находкой дословно)."""
        refusal = self.added(MIXED_MARKERS)
        self.assertIsNotNone(refusal)
        self.assertEqual("tests/test_new.py: @unittest.skip на "
                         "MixedTest::test_both", refusal.detail)
        self.assertEqual(["tests/test_new.py::MixedTest::test_both — "
                          "оболочки нет"], self.skips())

    def test_one_unconditional_occurrence_rejects_the_whole_marker(self):
        """Ловит мутацию: годность маркера решается по ПЕРВОМУ подходящему
        вхождению — `self.skipTest("…")` вне всякого `if` уходит из находок
        за компанию с условным вызовом того же вида выше, хотя
        `guard.test_skip_markers` сводит оба к одному тексту маркера и
        рубеж обязан закрыться в пользу находки."""
        refusal = self.added(TWO_SKIP_CALLS)
        self.assertIsNotNone(refusal)
        self.assertEqual("tests/test_new.py: self.skipTest( на "
                         "TwoCallsTest::test_two_calls", refusal.detail)
        self.assertEqual([], self.skips())

    def test_skip_call_nested_deeper_than_one_if_is_conditional(self):
        """Ловит мутацию: условность вызова проверяется только на ПЕРВОМ
        уровне тела `if` — пропуск внутри цикла или вложенного `if`
        перестаёт считаться условным, хотя требование 2 называет любую
        глубину вложенности."""
        self.assertIsNone(self.added(NESTED_SKIP_CALL))
        self.assertEqual(["tests/test_new.py::NestedTest::test_nested — "
                          "оболочки нет"], self.skips())

    def test_skip_call_in_the_if_condition_is_not_conditional(self):
        """Ловит мутацию: условным считается любой вызов, лежащий внутри
        узла `ast.If` — вызов в самом УСЛОВИИ исполняется всегда и гасит
        тест на каждой машине, а рубеж о нём молчит."""
        refusal = self.added(SKIP_CALL_IN_CONDITION)
        self.assertIsNotNone(refusal)
        self.assertIn("self.skipTest( на ConditionTest::test_in_condition",
                      refusal.detail)
        self.assertEqual([], self.skips())

    def test_decorator_without_a_condition_argument_stays_a_finding(self):
        """Ловит мутацию: условным считается сам ВИД декоратора
        (`skipif`/`skipIf`/`skipUnless`) без проверки, что условие ему
        передано — `@pytest.mark.skipif(reason="…")` выключает тест
        безусловно и проходит рубеж на одной названной причине."""
        refusal = self.added(SKIPIF_WITHOUT_CONDITION)
        self.assertIsNotNone(refusal)
        self.assertEqual("tests/test_new.py: @pytest.mark.skipif на "
                         "NoConditionTest::test_no_condition", refusal.detail)

    def test_non_string_constant_is_not_a_reason(self):
        """Ловит мутацию: причиной считается любая константа
        (`self.skipTest(None)`, `self.skipTest(0)`) — в журнал требования 7
        уходит «None» вместо объяснения, и ревьювер получает след без
        смысла."""
        refusal = self.added(NON_STRING_REASON)
        self.assertIsNotNone(refusal)
        self.assertIn("self.skipTest( на NonStringTest::test_non_string_reason",
                      refusal.detail)
        self.assertEqual([], self.skips())

    def test_no_journal_record_when_nothing_passed_the_leniency(self):
        """Ловит мутацию: запись «новый тест с условным пропуском» пишется
        безусловно, на каждом заходе узла — журнал задачи забивается
        пустыми записями, и настоящее послабление в них не разглядеть."""
        self.assertIsNone(self.added(PLAIN_NEW_FILE))
        self.assertEqual([], self.skips())

    def test_new_method_of_an_old_class_name_is_compared_qualified(self):
        """Ловит мутацию: имя сверяется с базой ГОЛЫМ (как в
        `guard._collect_test_functions`) — `BetaTest::test_one` нового
        класса считается существующим из-за одноимённого
        `AlphaTest::test_one`, и послабление на него не действует, хотя
        такого теста в базе сравнения не было вовсе."""
        self.entries = [("M", "tests/test_alpha.py", None)]
        self.sources[(BASE, "tests/test_alpha.py")] = ALPHA
        self.sources[(CODE_BRANCH, "tests/test_alpha.py")] = ALPHA_PLUS_NEW_CLASS
        self.assertIsNone(self.refusal())
        self.assertEqual(["tests/test_alpha.py::BetaTest::test_one — "
                          "оболочки нет"], self.skips())


class EarlyReturnFindingTest(_GateSandbox):
    """Ранний `return` под условием — находка того же класса, что пропуск
    без причины (SPEC 01M3HWXFYWVDHGW011P6BZJFYA, требования 5-6)."""

    PATH = "tests/test_new.py"

    def added(self, source):
        self.entries = [("A", self.PATH, None)]
        self.sources[(CODE_BRANCH, self.PATH)] = source
        return self.refusal()

    def test_early_return_after_a_docstring_is_a_finding(self):
        """Ловит мутацию: докстринг метода принят за первый исполняемый
        оператор (либо ранний выход ищется регуляркой по тексту) — обход
        рубежа, который SPEC называет известным и открытым, остаётся
        открытым; текст находки при этом обязан отличаться от текста
        находки о пропуске и называть файл с квалифицированным именем."""
        refusal = self.added(EARLY_RETURN)
        self.assertIsNotNone(refusal)
        self.assertEqual("tests/test_new.py: ранний return под условием в "
                         "EarlyTest::test_early", refusal.detail)

    def test_other_forms_of_early_exit_are_out_of_scope(self):
        """Ловит мутацию: границы требования 5 расширены — безусловный
        `return` первым действием, `return` не первым оператором, `if` с
        телом из двух операторов или `return None` начинают отказывать
        переходу, и рубеж краснеет на коде, который SPEC («Не входит») из
        границы исключает дословно."""
        self.assertIsNone(self.added(EARLY_RETURN_OUT_OF_SCOPE))

    def test_early_return_present_in_base_is_not_a_finding(self):
        """Ловит мутацию: ранний выход собирается по одному head, без
        сверки с тем же именем в базе — правка файла, где ранний `return`
        стоял годами, отказывает переходу за чужой давний код."""
        self.entries = [("M", self.PATH, None)]
        self.sources[(BASE, self.PATH)] = EARLY_RETURN
        self.sources[(CODE_BRANCH, self.PATH)] = EARLY_RETURN.replace(
            "self.assertTrue(READY)", "self.assertTrue(bool(READY))")
        self.assertIsNone(self.refusal())

    def test_early_return_is_covered_by_the_operator_mandate(self):
        """Ловит мутацию: новая находка заведена в обход общего пути
        находок (собственным отказом мимо `uncovered`) — мандат Оператора
        её не покрывает, и законное решение «этот ранний выход остаётся»
        нечем оформить, кроме правки самого гейта."""
        self.add_answer("ANSWER-1.md",
                        f"{self.PATH}::EarlyTest::test_early")
        self.assertIsNone(self.added(EARLY_RETURN))
        allowed = [detail for action, detail in self.journal()
                   if action == test_integrity.TEST_INTEGRITY_ALLOWED_ACTION]
        self.assertEqual(["tests/test_new.py: ранний return под условием в "
                          "EarlyTest::test_early — разрешено ANSWER-1"],
                         allowed)


class GateWiringTest(unittest.TestCase):
    """Рубеж ПОДКЛЮЧЁН к обоим маршрутам — к телу `fsm_advance.in_dev` и к
    телу `fsm_merge_gate._cmd_approve_merge_gate` (требования 6-7, AC-13).

    Читается по исходному тексту обработчиков (`inspect.getsource`), тем
    же приёмом, что планка задачи: каждый гейт `in_dev` зовётся своим
    `if ...: return False`, и порядок вызовов — это и есть порядок строк в
    теле; воспроизводить весь переход целиком (PLAN.md, подтяжка main,
    ёмкость, зоны, лок планки, origin, прогон планки) ради одного факта о
    соседстве дороже и хрупче, чем прочитать само тело.

    Класс заведён по замечанию R1-F1 ревью итерации 1: без него снятие
    ОБЕИХ строк подключения оставляло 183 теста `tests/` зелёными —
    постоянный набор пульта пропускал отключение рубежа молча, а планка
    задачи после мержа регресс не сторожит (`pytest tests` её не
    собирает). Сверка идёт по форме вызова (`имя(conn`), не по имени в
    тексте: имя, оставшееся в комментарии или в блоке импортов,
    подключением не является.
    """

    def test_in_dev_calls_the_gate_between_mutation_claim_and_review_rework(self):
        """Ловит мутацию: строка вызова `_test_integrity_gate_refuses`
        снята из тела `fsm_advance.in_dev` (модуль гейта при этом цел, и
        все его собственные сценарии зелены) — переход `in_dev ->
        verifying` снова пропускает удаление файла тестов молча; либо
        вызов переставлен ПЕРЕД гейтом заявки мутации, отчего на диффе,
        задевающем оба, меняется старшинство отказов, а вместе с ним
        журнал и stdout сценариев, которые
        `tests/test_fsm_advance_gate_smoke.py` сверяет байт-в-байт."""
        source = inspect.getsource(fsm_advance.in_dev)
        claim = source.find("_mutation_claim_gate(conn")
        integrity = source.find("_test_integrity_gate_refuses(conn")
        rework = source.find("_review_rework_gate_refuses(conn")

        self.assertNotEqual(
            -1, integrity,
            "тело in_dev не зовёт _test_integrity_gate_refuses — рубеж "
            "отключён от перехода in_dev -> verifying")
        self.assertNotEqual(-1, claim,
                            "тело in_dev не зовёт _mutation_claim_gate")
        self.assertNotEqual(-1, rework,
                            "тело in_dev не зовёт _review_rework_gate_refuses")
        self.assertLess(claim, integrity,
                        "новый рубеж обязан стоять ПОСЛЕ гейта заявки мутации")
        self.assertLess(integrity, rework,
                        "новый рубеж обязан стоять ДО гейта отработки замечаний")

    def test_merge_gate_calls_the_gate_after_the_protected_path_gate(self):
        """Ловит мутацию: строка вызова `_test_integrity_diff_gate` снята
        из тела `_cmd_approve_merge_gate` (либо поставлена после попытки
        merge) — ветка, дошедшая до гейта мержа другим маршрутом (ручной
        `advance` Оператора, повторный заход после эскалации, подтяжка
        main, добавившая удаление уже после `verifying`), вливается в main
        без сверки тестов, и снятая с Оператора ручная сверка оказывается
        снята впустую (требование 7, AC-12)."""
        source = inspect.getsource(fsm_merge_gate._cmd_approve_merge_gate)
        protected = source.find("_protected_path_diff_gate(conn")
        integrity = source.find("_test_integrity_diff_gate(conn")
        merge = source.find("_perform_carpentry_merge(")

        self.assertNotEqual(
            -1, integrity,
            "тело _cmd_approve_merge_gate не зовёт _test_integrity_diff_gate "
            "— рубеж отключён от маршрута мержа")
        self.assertNotEqual(-1, protected,
                            "тело гейта мержа не зовёт _protected_path_diff_gate")
        self.assertNotEqual(-1, merge,
                            "тело гейта мержа не зовёт _perform_carpentry_merge")
        self.assertLess(
            protected, integrity,
            "рубеж обязан стоять сразу ЗА гейтом защищённых путей")
        self.assertLess(integrity, merge,
                        "рубеж обязан стоять ДО попытки merge")


class MergeGateTest(SchemaSeededTmpRootTest):
    """Тот же узел на гейте мержа: fail-open на молчание git и эскалация
    на находке (требование 7, AC-12)."""

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        store.update_task(self.conn, self.TASK, state="merge_gate")

    def _escalates(self, entries, sources):
        def show(ref, path, repo=None):
            return (sources[(ref, path)], "") if (ref, path) in sources \
                else (None, "файла нет в этой ветке")

        with mock.patch.object(gitcmd, "diff_base", return_value=BASE), \
             mock.patch.object(gitcmd, "diff_name_status",
                               return_value=entries), \
             mock.patch.object(gitcmd, "show", show), \
             mock.patch.object(gitcmd, "ls_tree_files", return_value=[]):
            return test_integrity.merge_gate_escalates(
                self.conn, self.TASK, "merge_gate", CODE_BRANCH,
                ARTIFACT_BRANCH)

    def test_finding_without_mandate_escalates_with_the_same_text(self):
        """Ловит мутацию: `merge_gate_escalates` докладывает находку
        одним возвратом `True`, забыв `store.set_state` (либо эскалирует
        с пустым detail) — задача остаётся в `merge_gate`, а Оператор не
        узнаёт, какой именно файл тестов потерян, хотя ручную сверку с
        него эта задача сняла (требование 7, AC-12).

        Про то, что узел ВООБЩЕ вызван с маршрута мержа, этот сценарий не
        говорит — он зовёт функцию напрямую; подключение ловит
        `GateWiringTest` ниже."""
        escalated = self._escalates(
            [("D", "tests/test_doomed.py", None)],
            {(BASE, "tests/test_doomed.py"): ALPHA})
        self.assertTrue(escalated)
        row = store.get_task(self.conn, self.TASK)
        self.assertEqual("escalated", row["state"])
        details = [r["detail"] for r in self.conn.execute(
            "SELECT detail FROM steps WHERE task_id=?", (self.TASK,))]
        self.assertTrue(any("tests/test_doomed.py: удалён" in (d or "")
                            for d in details), details)

    def test_silent_git_does_not_stop_the_merge_gate(self):
        """Ловит мутацию: fail-closed перенесён на гейт мержа дословно с
        перехода — сломанный git начинает останавливать мерж там, где
        состояние ещё не тронуто, а соседний рубеж защищённых путей ведёт
        себя ровно наоборот (требование 7, AC-12)."""
        with mock.patch.object(gitcmd, "diff_base", return_value=None):
            escalated = test_integrity.merge_gate_escalates(
                self.conn, self.TASK, "merge_gate", CODE_BRANCH,
                ARTIFACT_BRANCH)
        self.assertFalse(escalated)
        self.assertEqual("merge_gate",
                         store.get_task(self.conn, self.TASK)["state"])

    def test_conditional_skip_passes_the_merge_route_and_is_journalled(self):
        """Ловит мутацию: послабление и его журнальная запись вписаны в
        обёртку перехода, а не в общий узел — честный неприменимый тест
        проходит `in_dev -> verifying` и упирается в эскалацию на самом
        дорогом шаге конвейера, а Оператор на мерже не видит перечня
        пропусков, которые рубеж пропустил (требования 7-8)."""
        escalated = self._escalates(
            [("A", "tests/test_new.py", None)],
            {(CODE_BRANCH, "tests/test_new.py"): CONDITIONAL_SKIPS})
        self.assertFalse(escalated)
        self.assertEqual("merge_gate",
                         store.get_task(self.conn, self.TASK)["state"])
        skips = [r["detail"] for r in self.conn.execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=?",
            (self.TASK, test_integrity.TEST_INTEGRITY_CONDITIONAL_SKIP_ACTION))]
        self.assertEqual(1, len(skips), skips)
        self.assertIn("tests/test_new.py::NewTest::test_call_inside_if — "
                      "вызов внутри if", skips[0])


CONTEXT_BASE = '''import unittest


class CloneHomeTest(unittest.TestCase):

    def test_defect_names_home(self):
        defect = check()
        self.assertIn(str(self.pult_home / "role"), defect)


class StackSectionTest(unittest.TestCase):

    def test_section_names_paths(self):
        self.assertIn("ПУТИ", self.body)
'''

# Оба случая «Контекста» SPEC 01M3Y753QNG6TS5C7MTJS1MEV6 синтетически:
# 01M3SK48D7RDQPSEN78894GDA5 (`self.pult_home` -> `self.clone_home`) и
# 01M3V4ZPB6HFDJ36MTDAQG5VNT (`assertIn("ПУТИ", …)` заменён другим `assertIn`).
CONTEXT_HEAD = CONTEXT_BASE.replace("self.pult_home", "self.clone_home") \
    .replace('"ПУТИ", self.body', '"ВЫХОД", self.body')

CONTEXT_PATH = "tests/test_context.py"
CLONE_HOME_LINE = (f"{CONTEXT_PATH}: утверждения изменены в "
                   f"CloneHomeTest::test_defect_names_home: "
                   f'self.assertIn(str(self.pult_home / "role"), defect)')
STACK_SECTION_LINE = (f"{CONTEXT_PATH}: утверждения изменены в "
                      f"StackSectionTest::test_section_names_paths: "
                      f'self.assertIn("ПУТИ", self.body)')


class AssertionObservationTest(_GateSandbox):
    """Наблюдение за изменёнными утверждениями на обоих рубежах и во входе
    ревьювера (SPEC 01M3Y753QNG6TS5C7MTJS1MEV6, требование 5, тесты 10г-ж)."""

    def setUp(self):
        super().setUp()
        store.insert_task(self.conn, self.task_id, "Задача", "in_dev",
                          CODE_BRANCH, config.DEFAULT_TARGET, 25.0)
        self.conn.commit()
        self.entries = [("M", CONTEXT_PATH, None)]
        self.sources[(BASE, CONTEXT_PATH)] = CONTEXT_BASE
        self.sources[(CODE_BRANCH, CONTEXT_PATH)] = CONTEXT_HEAD

    def patched(self):
        stack = ExitStack()
        for name, value in (("diff_base", mock.Mock(return_value=BASE)),
                            ("diff_name_status",
                             mock.Mock(return_value=self.entries)),
                            ("show", self._show),
                            ("ls_tree_files", self._ls_tree),
                            ("git", self._git)):
            stack.enter_context(mock.patch.object(gitcmd, name, value))
        return stack

    def observations(self):
        return [detail for action, detail in self.journal()
                if action == test_integrity.ASSERTION_OBSERVATION_ACTION]

    def test_transition_passes_and_journals_both_context_cases(self):
        """Переход `in_dev -> verifying` выполнен, журнал несёт одну запись
        «изменены утверждения тестов (наблюдение)» с обоими случаями.

        Ловит мутацию: находка об утверждениях не доходит до журнала либо
        блокирует переход."""
        with self.patched():
            refused = fsm_advance._test_integrity_gate_refuses(
                self.conn, self.task_id, self.t, ARTIFACT_BRANCH)
        self.assertFalse(refused)
        self.assertEqual([f"{CLONE_HOME_LINE}; {STACK_SECTION_LINE}"],
                         self.observations())

    def test_mandate_marks_only_covered_findings(self):
        """Мандат `путь::Класс::метод` и мандат на путь помечают находку
        «покрыто мандатом ANSWER-n»; мандат на другой метод — нет.

        Ловит мутацию: находка заведена без имени метода либо под другим
        именем."""
        cases = (
            ("ANSWER-1.md",
             f"{CONTEXT_PATH}::CloneHomeTest::test_defect_names_home",
             [f"{CLONE_HOME_LINE} — покрыто мандатом ANSWER-1",
              STACK_SECTION_LINE]),
            ("ANSWER-2.md", CONTEXT_PATH,
             [f"{CLONE_HOME_LINE} — покрыто мандатом ANSWER-2",
              f"{STACK_SECTION_LINE} — покрыто мандатом ANSWER-2"]),
            ("ANSWER-3.md", f"{CONTEXT_PATH}::CloneHomeTest::test_other",
             [CLONE_HOME_LINE, STACK_SECTION_LINE]),
        )
        for name, allowed, expected in cases:
            with self.subTest(mandate=allowed):
                self.answers.clear()
                self.conn.execute("DELETE FROM steps")
                self.add_answer(name, allowed)
                with self.patched():
                    self.assertIsNone(fsm_advance._test_integrity_gate(
                        self.conn, self.task_id, self.t, ARTIFACT_BRANCH))
                self.assertEqual(["; ".join(expected)], self.observations())

    def test_merge_gate_and_review_package_carry_the_same_findings(self):
        """Гейт мержа пишет ту же запись и мерж не останавливает; раздел
        «Изменённые утверждения тестов» входа ревьювера несёт те же находки.

        Ловит мутацию: наблюдение есть только на одном рубеже либо не
        доходит до ревьювера."""
        store.update_task(self.conn, self.task_id, state="merge_gate")
        with self.patched():
            escalated = test_integrity.merge_gate_escalates(
                self.conn, self.task_id, "merge_gate", CODE_BRANCH,
                ARTIFACT_BRANCH)
            part = review._changed_assertions_part(
                self.conn, self.task_id, CODE_BRANCH, ARTIFACT_BRANCH,
                config.DEFAULT_TARGET, "run")
        self.assertFalse(escalated)
        self.assertEqual("merge_gate",
                         store.get_task(self.conn, self.task_id)["state"])
        self.assertEqual([f"{CLONE_HOME_LINE}; {STACK_SECTION_LINE}"],
                         self.observations())
        self.assertIn(review.CHANGED_ASSERTIONS_SECTION, part)
        self.assertIn(CLONE_HOME_LINE, part)
        self.assertIn(STACK_SECTION_LINE, part)

    def test_vanished_method_and_unparseable_head(self):
        """Исчезнувший метод — одна находка «метод … исчез» без находки об
        утверждениях; неразбираемый head — отказ по исчезнувшим методам,
        без исключения, с записью «наблюдение не выполнено».

        Ловит мутацию: двойная находка либо трейсбек на неразбираемом
        файле."""
        self.sources[(CODE_BRANCH, CONTEXT_PATH)] = \
            CONTEXT_BASE.split("\n\nclass StackSectionTest")[0] + "\n"
        with self.patched():
            refusal = fsm_advance._test_integrity_gate(
                self.conn, self.task_id, self.t, ARTIFACT_BRANCH)
        self.assertEqual(
            f"{CONTEXT_PATH}: метод StackSectionTest::test_section_names_paths "
            f"исчез", refusal.detail)
        self.assertEqual([], self.observations())

        self.conn.execute("DELETE FROM steps")
        self.sources[(CODE_BRANCH, CONTEXT_PATH)] = "class Broken(:\n"
        with self.patched():
            refusal = fsm_advance._test_integrity_gate(
                self.conn, self.task_id, self.t, ARTIFACT_BRANCH)
        self.assertIn("CloneHomeTest::test_defect_names_home исчез",
                      refusal.detail)
        self.assertEqual([], self.observations())
        unobserved = [detail for action, detail in self.journal()
                      if action == test_integrity.ASSERTION_UNOBSERVED_ACTION]
        self.assertEqual(1, len(unobserved), self.journal())
        self.assertIn(f"наблюдение не выполнено: {CONTEXT_PATH}: "
                      f"не разбирается (head)", unobserved[0])

    def test_git_silence_journals_not_performed_on_both_routes(self):
        """Молчание git — запись «наблюдение не выполнено: <причина>»:
        на переходе рядом с прежним fail-closed отказом, на мерже — без
        остановки.

        Ловит мутацию: молчание git на наблюдении проходит молча, как
        «находок нет», либо меняет прежнюю реакцию рубежа на сбой."""
        store.update_task(self.conn, self.task_id, state="merge_gate")
        with mock.patch.object(gitcmd, "diff_base", return_value=None):
            refusal = fsm_advance._test_integrity_gate(
                self.conn, self.task_id, self.t, ARTIFACT_BRANCH)
            escalated = test_integrity.merge_gate_escalates(
                self.conn, self.task_id, "merge_gate", CODE_BRANCH,
                ARTIFACT_BRANCH)
        self.assertIn("git не ответил", refusal.detail)
        self.assertFalse(escalated)
        unobserved = [detail for action, detail in self.journal()
                      if action == test_integrity.ASSERTION_UNOBSERVED_ACTION]
        self.assertEqual(2, len(unobserved), self.journal())
        for detail in unobserved:
            self.assertTrue(detail.startswith(
                "наблюдение не выполнено: гейт неослабления тестов: git не "
                "ответил"), detail)


class DiffNameStatusTest(unittest.TestCase):
    """Разбор ответа `git diff -M --name-status -z`
    (`gitcmd.diff_name_status`, требование 3)."""

    def _parse(self, stdout, returncode=0):
        res = subprocess.CompletedProcess(("git",), returncode, stdout, "")
        with mock.patch.object(gitcmd, "git", return_value=res):
            return gitcmd.diff_name_status("a", "b")

    def test_rename_entry_carries_both_paths(self):
        """Ловит мутацию: у записи `R100` читается один путь — второе
        поле принимается за статус следующей записи, и весь разбор
        съезжает, а переименование выглядит удалением."""
        out = "R100\0tests/test_a.py\0tests/test_b.py\0M\0tests/test_c.py\0"
        self.assertEqual(
            [("R100", "tests/test_a.py", "tests/test_b.py"),
             ("M", "tests/test_c.py", None)], self._parse(out))

    def test_plain_entries_have_no_second_path(self):
        """Ловит мутацию: второй путь подставляется всем записям —
        удаление начинает выглядеть переименованием в следующий файл
        диффа."""
        self.assertEqual([("D", "tests/test_a.py", None)],
                         self._parse("D\0tests/test_a.py\0"))

    def test_git_failure_is_none_not_empty_list(self):
        """Ловит мутацию: ненулевой код возврата отдаётся пустым списком
        — вызывающий гейт читает сбой git как «диффа нет» и открывает
        рубеж (тот же контракт `None`, что у `diff_names` рядом)."""
        self.assertIsNone(self._parse("", returncode=128))


if __name__ == "__main__":
    unittest.main()
