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
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (config, fsm_advance, fsm_merge_gate,  # noqa: E402
                          gitcmd, store)
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

    def _show(self, ref, path):
        if (ref, path) in self.sources:
            return self.sources[(ref, path)], ""
        return None, "файла нет в этой ветке"

    def _ls_tree(self, branch, rel_dir):
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
        def show(ref, path):
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
