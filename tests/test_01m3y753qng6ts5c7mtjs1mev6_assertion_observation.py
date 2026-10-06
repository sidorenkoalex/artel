"""Наблюдение гейта неослабления тестов за утверждениями метода, сохранившего
имя: что считается утверждением и его нормальной формой, какие правки дают
находку, форма находки, мандат, запись журнала на гейте мержа и раздел
ревью-пакета (AC-1..AC-5, AC-7, AC-8, AC-9 на гейте мержа, AC-10).

Группа: долгоживущий

Красен до реализации: гейт неослабления тела сохранившего имя метода не
сравнивает — журнал не получает записи «изменены утверждения тестов
(наблюдение)», ревью-пакет не несёт раздела «Изменённые утверждения
тестов», запись «наблюдение не выполнено» не пишется. Тесты «не находка»
(AC-2, перенос в помощника AC-3) красны той же причиной: каждый из них
держит рядом контрольную правку, которая обязана стать находкой, и без
записи журнала падает на ней. Два теста AC-5 о неразбираемой стороне
(`test_ac5_unparsable_*`) зелёные с рождения: прежние находки файла и
отсутствие исключения — сегодняшнее поведение, тесты держат его против
сравнения утверждений без отказоустойчивого разбора.

Песочница — `tests.sandbox.ConnRealGitSandbox`: настоящий git-репозиторий,
база — коммит на main, голова — ветка задачи от неё, мандат Оператора —
`ANSWER-1.md` на артефактной ветке, закоммиченный не автокоммитом шага
роли. Наблюдение читается только через публичные входы:
`test_integrity.merge_gate_escalates` (гейт мержа) и
`review.review_package` (вход ревьювера); предмет сверки — журнал `steps`
и текст пакета. Ожидаемые значения, атрибуты и имена локальных переменных
фикстур берутся случайными при каждом запуске; зерно печатается и входит
в текст провала.
"""
import random
import unittest

from orchestrator import config, review, store
from orchestrator.advance_gates import test_integrity
from tests.sandbox import ConnRealGitSandbox

TASK = "T001"
BRANCH = "task/t001-nablyudenie"
ARTIFACT = "artifact/t001"
STATE = "review"
OBSERVATION_ACTION = "изменены утверждения тестов (наблюдение)"
NOT_PERFORMED = "наблюдение не выполнено"
REVIEW_SECTION = "Изменённые утверждения тестов"
CHANGED = "утверждения изменены в "
ANSWER_SUBJECT = f"{TASK}: ANSWER-1 — ответ Оператора"


def seeded(test) -> random.Random:
    """Генератор входов фикстуры с напечатанным зерном (`test.seed`)."""
    test.seed = random.randrange(1 << 30)
    print(f"зерно: {test.seed}")
    return random.Random(test.seed)


def identifiers(rng: random.Random, count: int) -> list:
    """`count` различных имён переменных, не совпадающих с именами фикстур."""
    names: set = set()
    while len(names) < count:
        names.add("v_" + "".join(rng.choice("abcdefghijklmnopqrstuvwxyz")
                                 for _ in range(6)))
    return sorted(names)


class ObservationSandbox(ConnRealGitSandbox):
    """Задача `TASK` в состоянии `STATE`; `commit_diff` кладёт базу на main
    и голову на ветку задачи; `merge_gate` — публичный вход гейта мержа."""

    seed = None

    def setUp(self):
        super().setUp()
        store.insert_task(self.conn, TASK, "Песочница наблюдения", STATE,
                          BRANCH, config.DEFAULT_TARGET, 10.0)
        self.conn.commit()

    def write(self, path: str, text) -> None:
        target = self.root / path
        if text is None:
            target.unlink()
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def commit_diff(self, base: dict, head: dict) -> None:
        """База — коммит на main; голова — коммит ветки задачи поверх неё
        (`None` в `head` — файл удалён)."""
        for path, text in base.items():
            self.write(path, text)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "база")
        self.checkout(BRANCH, create=True)
        for path, text in head.items():
            self.write(path, text)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "голова")
        self.checkout(config.MAIN_BRANCH)

    def add_mandate(self, elements: str) -> None:
        """`ANSWER-1.md` с мандатом ослабления на артефактной ветке —
        коммитом с подписью ответа Оператора, не автокоммита роли."""
        self.checkout(ARTIFACT, create=True)
        self.write("/".join(("tasks", TASK, "ANSWER-1.md")),
                   f"# Ответ Оператора\n\n"
                   f"{test_integrity.TEST_WEAKENING_MANDATE_MARKER} {elements}\n"
                   f"Основание: решение Оператора.\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", ANSWER_SUBJECT)
        self.checkout(config.MAIN_BRANCH)

    def merge_gate(self, branch: str = BRANCH) -> bool:
        return test_integrity.merge_gate_escalates(self.conn, TASK, STATE,
                                                   branch, ARTIFACT)

    def journal(self) -> list:
        return [(row["action"], row["detail"] or "")
                for row in self.conn.execute(
                    "SELECT action, detail FROM steps WHERE task_id=? "
                    "ORDER BY id", (TASK,))]

    def observations(self) -> list:
        return [detail for action, detail in self.journal()
                if action == OBSERVATION_ACTION]

    def observation(self) -> str:
        """Detail единственной записи наблюдения рубежа."""
        found = self.observations()
        self.assertEqual(1, len(found), self.why(
            f"ожидалась одна запись «{OBSERVATION_ACTION}», журнал: "
            f"{self.journal()}"))
        return found[0]

    def state(self) -> str:
        return self.conn.execute("SELECT state FROM tasks WHERE id=?",
                                 (TASK,)).fetchone()["state"]

    def why(self, text: str) -> str:
        return f"{text} (зерно: {self.seed})" if self.seed is not None else text


# ---------------------------------------------------------------------------
# AC-1: правки, которые находка.

def ac1_sources(rng: random.Random) -> tuple:
    expected = rng.randrange(1, 1000)
    other = expected + rng.randrange(1, 50)
    suffix = rng.choice(("role", "home", "clone", "pool", "bin"))
    base = f'''import unittest


class AlphaTest(unittest.TestCase):

    def test_removed(self):
        body = render()
        self.assertIn("ПУТИ", body)
        self.assertEqual(len(body), 3)

    def test_equal_to_true(self):
        self.assertEqual(flag(), 1)

    def test_equal_to_in(self):
        self.assertEqual(word(), "abc")

    def test_regex_to_raises(self):
        with self.assertRaisesRegex(ValueError, "плохо"):
            parse("x")

    def test_assert_to_if(self):
        value = compute()
        assert value == 1

    def test_expected_value(self):
        self.assertEqual(compute(), {expected})

    def test_attribute(self):
        defect = check()
        self.assertIn(str(self.pult_home / "{suffix}"), defect)

    def test_shortened(self):
        self.assertIn("ПУТИ К ФАЙЛАМ", render())

    def test_tightened(self):
        self.assertIn("abc", word())

    def test_multiset(self):
        self.assertTrue(ready())
        self.assertTrue(ready())
        self.assertFalse(broken())
'''
    head = f'''import unittest


class AlphaTest(unittest.TestCase):

    def test_removed(self):
        body = render()
        self.assertEqual(len(body), 3)

    def test_equal_to_true(self):
        self.assertTrue(flag())

    def test_equal_to_in(self):
        self.assertIn("abc", word())

    def test_regex_to_raises(self):
        with self.assertRaises(ValueError):
            parse("x")

    def test_assert_to_if(self):
        value = compute()
        if value == 1:
            pass

    def test_expected_value(self):
        self.assertEqual(compute(), {other})

    def test_attribute(self):
        defect = check()
        self.assertIn(str(self.clone_home / "{suffix}"), defect)

    def test_shortened(self):
        self.assertIn("ПУТИ", render())

    def test_tightened(self):
        self.assertEqual("abc", word())

    def test_multiset(self):
        self.assertTrue(ready())
        self.assertFalse(broken())
        self.assertFalse(broken())
'''
    return base, head


AC1_METHODS = ("test_removed", "test_equal_to_true", "test_equal_to_in",
               "test_regex_to_raises", "test_assert_to_if",
               "test_expected_value", "test_attribute", "test_shortened",
               "test_tightened", "test_multiset")


class ChangedAssertionIsFindingTest(ObservationSandbox):

    def test_ac1_removed_kind_argument_tightened_and_multiset_are_findings(self):
        """Каждая из десяти правок утверждения сохранившего имя метода — находка.

        В одном файле `tests/test_alpha.py` десять методов, каждый с одной
        правкой: удалён `assertIn`; `assertEqual` -> `assertTrue`;
        `assertEqual` -> `assertIn`; `assertRaisesRegex` -> `assertRaises`;
        `assert` -> `if`; другое ожидаемое значение (случайное);
        `self.pult_home` -> `self.clone_home`; укороченная подстрока;
        `assertIn` -> `assertEqual`; одно из двух одинаковых
        `assertTrue(ready())` заменено вторым `assertFalse(broken())` —
        число утверждений прежнее, мультимножество другое. Запись
        наблюдения гейта мержа называет каждый из десяти методов.

        Ловит мутацию: сравниваются только множества нормальных форм или
        только число утверждений — `test_multiset` (и смена аргумента при
        прежнем числе) находкой не станет; аргументы не входят в ключ —
        `test_expected_value`/`test_attribute`/`test_shortened` выпадут;
        сравнение утверждений выключено — записи нет вовсе.
        """
        base, head = ac1_sources(seeded(self))
        self.commit_diff({"tests/test_alpha.py": base},
                         {"tests/test_alpha.py": head})
        self.merge_gate()
        detail = self.observation()
        self.assertIn("tests/test_alpha.py", detail, self.why(detail))
        for name in AC1_METHODS:
            self.assertIn(f"{CHANGED}AlphaTest::{name}:", detail,
                          self.why(f"нет находки на {name}: {detail}"))


# ---------------------------------------------------------------------------
# AC-2: правки, которые НЕ находка (и две контрольные — находка).

def ac2_sources(rng: random.Random) -> tuple:
    names = identifiers(rng, 14)
    rng.shuffle(names)
    old, new = names[:7], names[7:]

    def text(names, messages, root, is_head, refused, limit):
        a, b, c, d, e, p, _ = names
        first, second = messages
        added = ("        self.assertEqual(size(), 3)\n" if is_head else "")
        reordered = ("        self.assertEqual(size(), 3)\n"
                     "        self.assertTrue(ready())\n" if is_head else
                     "        self.assertTrue(ready())\n"
                     "        self.assertEqual(size(), 3)\n")
        formatting = ("        # комментарий к сверке размера\n"
                      "        self.assertEqual(\n"
                      "            size(),\n"
                      "            3,\n"
                      "        )\n" if is_head else
                      "        self.assertEqual(size(), 3)\n")
        return f'''import unittest

from orchestrator import ci_rerun, fsm
from orchestrator.config import LIMIT_A, LIMIT_B


def test_param({p}):
    assert {p}.exists()


class BetaTest(unittest.TestCase):

    def test_added(self):
        self.assertTrue(ready())
{added}
    def test_reordered(self):
{reordered}
    def test_locals(self):
        {a} = render()
        self.assertIn("x", {a})
        for {b} in items():
            self.assertTrue({b})
        with opened() as {c}:
            self.assertEqual({c}.read(), "y")
        try:
            run()
        except ValueError as {d}:
            self.assertIn("z", str({d}))
        self.assertTrue(all({e} > 0 for {e} in items()))

    def test_messages(self):
        self.assertEqual(size(), 3, msg="{first}")
        self.assertIn("x", render(), "{first}")
        self.assertTrue(ready(), "{second}")
        assert size() == 3, "{second}"

    def test_import_root(self):
        self.assertTrue({root}._x(1))

    def test_formatting(self):
{formatting}
    def test_unknown_method_control(self):
        self.assert_refused(run(), "{refused}")

    def test_bare_import_control(self):
        self.assertEqual(size(), {limit})
'''

    base = text(old, ("первое сообщение", "второе сообщение"), "fsm", False,
                "старая причина", "LIMIT_A")
    head = text(new, ("иное сообщение", "совсем иное"), "ci_rerun", True,
                "новая причина", "LIMIT_B")
    return base, head


AC2_SILENT = ("test_param", "BetaTest::test_added", "BetaTest::test_reordered",
              "BetaTest::test_locals", "BetaTest::test_messages",
              "BetaTest::test_import_root", "BetaTest::test_formatting")
AC2_CONTROLS = ("BetaTest::test_unknown_method_control",
                "BetaTest::test_bare_import_control")


class NeutralEditIsNotFindingTest(ObservationSandbox):

    def test_ac2_added_reordered_locals_messages_import_root_are_not_findings(self):
        """Добавление, перестановка, локальные имена, сообщения, корень импорта и форматирование — не находка.

        `tests/test_beta.py`: в head добавлено утверждение; два
        утверждения переставлены; случайно переименованы параметр
        тестовой функции модуля, цель присваивания, переменная цикла,
        `with … as`, `except … as`, переменная генератора; сменены
        `msg=`, позиционное сообщение `assertIn`/`assertTrue` и часть
        `assert` после запятой; `fsm._x(1)` -> `ci_rerun._x(1)` (оба —
        импортированные модули); утверждение разнесено по строкам с
        комментарием. Ни один из этих методов в записи наблюдения не
        назван. Две контрольные правки в том же файле — находка: у
        неизвестного таблице `self.assert_refused` сменён второй
        позиционный аргумент (сравниваются все аргументы); голое
        импортированное имя `LIMIT_A` -> `LIMIT_B` (меткой «импорт» не
        заменяется).

        Ловит мутацию: локальные имена, сообщение или корень импорта
        входят в ключ сравнения — соответствующий метод появится в
        записи; позиционный аргумент сверх обязательных отбрасывается и у
        неизвестных имён либо голое импортированное имя заменяется меткой
        — контрольный метод выпадет из записи; сравнение выключено целиком
        — записи нет, контроль красен.
        """
        base, head = ac2_sources(seeded(self))
        self.commit_diff({"tests/test_beta.py": base},
                         {"tests/test_beta.py": head})
        self.merge_gate()
        detail = self.observation()
        for name in AC2_CONTROLS:
            self.assertIn(f"{CHANGED}{name}:", detail,
                          self.why(f"контроль {name} не стал находкой: {detail}"))
        for name in AC2_SILENT:
            self.assertNotIn(f"{CHANGED}{name}:", detail,
                             self.why(f"{name} стал находкой: {detail}"))


# ---------------------------------------------------------------------------
# AC-3: что считается утверждением, глубина и помощники первого уровня.

AC3_BASE = '''import unittest
from unittest import mock

import pytest


def check_value(value):
    assert value > 0


class GammaTest(unittest.TestCase):

    def _check(self, value):
        self.assertEqual(value, 1)

    def _expect_one(self, value):
        self.assertEqual(value, 1)

    def test_fail(self):
        if broken():
            self.fail("сломано")
        keep()

    def test_mock_assert(self):
        handle = mock.Mock()
        run(handle)
        handle.assert_called_once_with(1)

    def test_own_assert(self):
        self.assert_refused(run())
        keep()

    def test_pytest_raises(self):
        with pytest.raises(ValueError):
            parse("x")

    def test_pytest_warns(self):
        with pytest.warns(UserWarning):
            warn()

    def test_plain_assert(self):
        keep()
        assert ready()

    def test_in_branch(self):
        if ready():
            keep()
        else:
            self.assertFalse(flag())

    def test_in_loop(self):
        for item in items():
            self.assertGreater(item, 0)

    def test_in_with(self):
        with opened() as handle:
            self.assertEqual(handle.read(), "y")

    def test_in_subtest(self):
        for item in items():
            with self.subTest(item=item):
                self.assertIn(item, allowed())

    def test_in_nested_function(self):
        def inner():
            self.assertTrue(ready())
        inner()

    def test_helper_removed(self):
        self._check(compute())

    def test_module_helper_removed(self):
        check_value(compute())

    def test_moved_into_helper(self):
        result = compute()
        self.assertEqual(result, 1)

    def test_moved_out_of_helper(self):
        result = compute()
        self._expect_one(result)
'''

AC3_HEAD = '''import unittest
from unittest import mock

import pytest


def check_value(value):
    use(value)


class GammaTest(unittest.TestCase):

    def _check(self, value):
        use(value)

    def _expect_one(self, value):
        self.assertEqual(value, 1)

    def test_fail(self):
        if broken():
            pass
        keep()

    def test_mock_assert(self):
        handle = mock.Mock()
        run(handle)

    def test_own_assert(self):
        run()
        keep()

    def test_pytest_raises(self):
        parse("x")

    def test_pytest_warns(self):
        warn()

    def test_plain_assert(self):
        keep()
        ready()

    def test_in_branch(self):
        if ready():
            keep()
        else:
            flag()

    def test_in_loop(self):
        for item in items():
            use(item)

    def test_in_with(self):
        with opened() as handle:
            handle.read()

    def test_in_subtest(self):
        for item in items():
            with self.subTest(item=item):
                use(item)

    def test_in_nested_function(self):
        def inner():
            ready()
        inner()

    def test_helper_removed(self):
        self._check(compute())

    def test_module_helper_removed(self):
        check_value(compute())

    def test_moved_into_helper(self):
        result = compute()
        self._expect_one(result)

    def test_moved_out_of_helper(self):
        result = compute()
        self.assertEqual(result, 1)
'''

AC3_FOUND = ("test_fail", "test_mock_assert", "test_own_assert",
             "test_pytest_raises", "test_pytest_warns", "test_plain_assert",
             "test_in_branch", "test_in_loop", "test_in_with",
             "test_in_subtest", "test_in_nested_function",
             "test_helper_removed", "test_module_helper_removed")
AC3_SILENT = ("test_moved_into_helper", "test_moved_out_of_helper")


class AssertionKindsAndHelpersTest(ObservationSandbox):

    def test_ac3_assertion_kinds_any_depth_and_first_level_helpers(self):
        """Виды утверждений, любая глубина тела и помощники первого уровня.

        `tests/test_gamma.py`: из методов удалены по одному `self.fail`,
        `mock.assert_called_once_with`, собственный `self.assert_refused`,
        `pytest.raises`, `pytest.warns`, оператор `assert`; утверждение в
        ветке `else`, в цикле, в `with`, в `subTest`, во вложенной
        функции; утверждение из помощника `self._check` и из функции
        модуля `check_value` (их зовут методы, сами методы не тронуты) —
        каждый такой метод назван в записи наблюдения. Перенос
        `assertEqual(result, 1)` в `self._expect_one(result)` и обратно —
        не находка.

        Ловит мутацию: вспомогательные функции не разворачиваются — оба
        помощника выпадут из находок, а перенос в помощника станет
        находкой; обход тела только верхнего уровня — утверждения в
        ветке, цикле, `with`, `subTest` и вложенной функции выпадут;
        `fail`/`pytest.raises`/`pytest.warns`/собственный `assert_*` не
        опознаются утверждением — соответствующий метод выпадет.
        """
        self.commit_diff({"tests/test_gamma.py": AC3_BASE},
                         {"tests/test_gamma.py": AC3_HEAD})
        self.merge_gate()
        detail = self.observation()
        for name in AC3_FOUND:
            self.assertIn(f"{CHANGED}GammaTest::{name}:", detail,
                          f"нет находки на {name}: {detail}")
        for name in AC3_SILENT:
            self.assertNotIn(f"{CHANGED}GammaTest::{name}:", detail,
                             f"перенос через помощника стал находкой: {detail}")


# ---------------------------------------------------------------------------
# AC-4: одна находка на метод, до трёх утверждений, не длиннее 120 знаков.

FIVE_VALUES = (11, 22, 33, 44, 55)
LONG_LITERAL = "ДЛИННАЯ-ПОДСТРОКА-" * 12


def delta_source(body: str) -> str:
    return ('import unittest\n\n\nclass DeltaTest(unittest.TestCase):\n\n'
            '    def test_method(self):\n' + body + '        keep()\n')


class FindingFormTest(ObservationSandbox):

    def test_ac4_two_removed_assertions_give_one_finding_with_base_text(self):
        """Два удалённых утверждения одного метода — одна находка с исходным текстом base.

        Ловит мутацию: находка заводится на каждое утверждение, а не на
        метод — строка «утверждения изменены в DeltaTest::test_method»
        встретится дважды; в текст кладётся нормальная форма (`ast.dump`)
        вместо исходного текста — исходного `self.assertIn("ПУТИ", body)`
        в записи не будет.
        """
        base = delta_source('        body = render()\n'
                            '        self.assertIn("ПУТИ", body)\n'
                            '        self.assertTrue(ready())\n')
        head = delta_source('        body = render()\n')
        self.commit_diff({"tests/test_delta.py": base},
                         {"tests/test_delta.py": head})
        self.merge_gate()
        detail = self.observation()
        self.assertEqual(1, detail.count(f"{CHANGED}DeltaTest::test_method"),
                         detail)
        self.assertIn(f"tests/test_delta.py: {CHANGED}DeltaTest::test_method: ",
                      detail)
        self.assertIn('self.assertIn("ПУТИ", body)', detail)

    def test_ac4_at_most_three_assertions_then_tail(self):
        """Пять удалённых утверждений — в тексте ровно три из них и хвост «и ещё 2».

        Ловит мутацию: перечень не урезается до трёх — в записи все пять
        текстов и нет хвоста; хвост считает не остаток, а общее число
        («и ещё 5»).
        """
        base = delta_source("".join(
            f"        self.assertEqual(size(), {v})\n" for v in FIVE_VALUES))
        head = delta_source("")
        self.commit_diff({"tests/test_delta.py": base},
                         {"tests/test_delta.py": head})
        self.merge_gate()
        detail = self.observation()
        shown = [v for v in FIVE_VALUES
                 if f"self.assertEqual(size(), {v})" in detail]
        self.assertEqual(3, len(shown), detail)
        self.assertIn("и ещё 2", detail)

    def test_ac4_long_assertion_is_cut_to_120_chars(self):
        """Удалённое утверждение длиннее 120 знаков в тексте находки урезано до 120.

        Ловит мутацию: текст утверждения кладётся целиком без урезания —
        полный литерал окажется в записи и хвост после «DeltaTest::
        test_method: » длиннее 120 знаков.
        """
        assertion = f'self.assertIn("{LONG_LITERAL}", render())'
        self.assertGreater(len(assertion), 120)
        base = delta_source(f"        {assertion}\n")
        head = delta_source("")
        self.commit_diff({"tests/test_delta.py": base},
                         {"tests/test_delta.py": head})
        self.merge_gate()
        detail = self.observation()
        marker = f"{CHANGED}DeltaTest::test_method: "
        self.assertIn(marker, detail)
        shown = detail.split(marker, 1)[1].strip()
        self.assertNotIn(LONG_LITERAL, detail)
        self.assertTrue(shown, detail)
        self.assertLessEqual(len(shown), 120, shown)
        self.assertTrue(assertion.startswith(shown[:40]), shown)


# ---------------------------------------------------------------------------
# AC-5: исчезнувший метод, удалённый файл, неразбираемая сторона.

ALPHA_TWO = '''import unittest


class AlphaTest(unittest.TestCase):

    def test_one(self):
        self.assertEqual(compute(), 1)

    def test_two(self):
        self.assertIn("ПУТИ", render())
'''

ALPHA_ONE_CHANGED = '''import unittest


class AlphaTest(unittest.TestCase):

    def test_one(self):
        self.assertEqual(compute(), 2)
'''

ALPHA_TWO_CHANGED = ALPHA_TWO.replace("compute(), 1", "compute(), 2")

EPSILON = '''import unittest


class EpsilonTest(unittest.TestCase):

    def test_gone(self):
        self.assertTrue(ready())
'''

BROKEN = "import unittest\n\n\nclass Broken(unittest.TestCase:\n    def test_x(self)\n"


class VanishedDeletedUnparsableTest(ObservationSandbox):

    def all_details(self) -> str:
        return "\n".join(detail for _action, detail in self.journal())

    def test_ac5_vanished_method_has_single_finding(self):
        """Исчезнувший метод — одна находка «метод … исчез», без находки об утверждениях.

        Мандат на `AlphaTest::test_two` снимает находку об исчезновении;
        соседний `test_one` со сменой ожидаемого значения — контроль, что
        наблюдение выполнено, а его смена вне раздела SPEC «Меняемое
        поведение» эскалирует мерж (SPEC 01M45FJD46BX45VHC36S4VS9QN,
        требование 7).

        Ловит мутацию: метод, которого нет в head, сравнивается как
        «все утверждения удалены» — во всём журнале `AlphaTest::test_two`
        встретится дважды (исчез + утверждения изменены).
        """
        self.commit_diff({"tests/test_alpha.py": ALPHA_TWO},
                         {"tests/test_alpha.py": ALPHA_ONE_CHANGED})
        self.add_mandate("tests/test_alpha.py::AlphaTest::test_two")
        self.assertTrue(self.merge_gate())
        detail = self.observation()
        self.assertIn(f"{CHANGED}AlphaTest::test_one:", detail)
        everything = self.all_details()
        self.assertIn("метод AlphaTest::test_two исчез", everything)
        self.assertEqual(1, everything.count("AlphaTest::test_two"), everything)

    def test_ac5_deleted_file_has_no_assertion_finding(self):
        """Удалённый файл не даёт находки об утверждениях.

        Ловит мутацию: у удалённого файла head считается пустым и
        сравнение утверждений идёт — запись наблюдения назовёт
        `EpsilonTest::test_gone`.
        """
        self.commit_diff({"tests/test_alpha.py": ALPHA_TWO,
                          "tests/test_epsilon.py": EPSILON},
                         {"tests/test_alpha.py": ALPHA_TWO_CHANGED,
                          "tests/test_epsilon.py": None})
        self.add_mandate("tests/test_epsilon.py")
        self.assertTrue(self.merge_gate())
        detail = self.observation()
        self.assertIn(f"{CHANGED}AlphaTest::test_one:", detail)
        self.assertNotIn("EpsilonTest", detail)
        self.assertNotIn("tests/test_epsilon.py: утверждения", detail)

    def test_ac5_unparsable_head_keeps_other_findings_without_exception(self):
        """Неразбираемый head: исключения нет, находки об исчезнувших методах — как до задачи.

        Ловит мутацию: сравнение утверждений разбирает head без
        отказоустойчивого приёма — `SyntaxError` вылетает из гейта; либо
        неразбираемость гасит и прежние находки файла — мерж не
        эскалирует.
        """
        self.commit_diff({"tests/test_alpha.py": ALPHA_TWO},
                         {"tests/test_alpha.py": BROKEN})
        self.assertTrue(self.merge_gate())
        self.assertEqual("escalated", self.state())
        everything = self.all_details()
        self.assertIn("метод AlphaTest::test_one исчез", everything)
        self.assertNotIn(CHANGED, everything)

    def test_ac5_unparsable_base_compares_nothing_without_exception(self):
        """Неразбираемый base: исключения нет, находок об утверждениях нет, мерж не остановлен.

        Ловит мутацию: base без отказоустойчивого приёма — `SyntaxError`
        из гейта; либо неразбираемый base читается как «утверждений нет»
        и голова сверяется с пустым — находка там, где сравнивать нечего
        (мерж при этом всё равно не должен эскалировать).
        """
        self.commit_diff({"tests/test_alpha.py": BROKEN},
                         {"tests/test_alpha.py": ALPHA_TWO})
        self.assertFalse(self.merge_gate())
        self.assertEqual(STATE, self.state())
        self.assertNotIn(CHANGED, self.all_details())


# ---------------------------------------------------------------------------
# AC-7: отметка мандата.

ALPHA_BOTH_CHANGED = ALPHA_TWO.replace("compute(), 1", "compute(), 2") \
    .replace('"ПУТИ"', '"ПУТ"')


class MandateMarkTest(ObservationSandbox):

    def setUp(self):
        super().setUp()
        self.commit_diff({"tests/test_alpha.py": ALPHA_TWO},
                         {"tests/test_alpha.py": ALPHA_BOTH_CHANGED})

    def test_ac7_method_mandate_marks_only_named_method(self):
        """Мандат `путь::Класс::метод` помечает находку этого метода и только её.

        Изменены оба метода; мандат назван на `test_one` — отметка
        «покрыто мандатом ANSWER-1» в записи ровно одна.

        Ловит мутацию: находка об утверждениях заведена без имени метода
        (пустое `name`) — мандат с `::` её не покроет и отметки не будет;
        отметка ставится всем находкам файла по мандату на один метод —
        отметок две.
        """
        self.add_mandate("tests/test_alpha.py::AlphaTest::test_one")
        self.assertTrue(self.merge_gate())
        detail = self.observation()
        self.assertEqual(1, detail.count("покрыто мандатом ANSWER-1"), detail)

    def test_ac7_path_mandate_marks_findings_of_the_file(self):
        """Мандат на путь файла помечает его находки об утверждениях.

        Ловит мутацию: отметка сверяется только с элементами `::` — мандат
        на путь находку не помечает, отметки нет.
        """
        self.add_mandate("tests/test_alpha.py")
        self.assertFalse(self.merge_gate())
        detail = self.observation()
        self.assertIn("покрыто мандатом ANSWER-1", detail)

    def test_ac7_other_method_mandate_does_not_mark(self):
        """Мандат на другой метод того же файла находку не помечает.

        Изменён только `test_one`; мандат назван на `test_two`.

        Ловит мутацию: находка заведена под именем файла или класса, а не
        метода, либо мандат сверяется по префиксу пути — мандат на
        соседний метод её пометит.
        """
        self.git("branch", "-D", BRANCH)
        self.checkout(BRANCH, create=True)
        self.write("tests/test_alpha.py", ALPHA_TWO_CHANGED)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "голова: изменён только test_one")
        self.checkout(config.MAIN_BRANCH)
        self.add_mandate("tests/test_alpha.py::AlphaTest::test_two")
        self.assertTrue(self.merge_gate())
        detail = self.observation()
        self.assertIn(f"{CHANGED}AlphaTest::test_one:", detail)
        self.assertNotIn("покрыто мандатом", detail)


# ---------------------------------------------------------------------------
# AC-8, AC-9 (гейт мержа), AC-10.

CONTEXT_BASE = '''import unittest


class CloneHomeTest(unittest.TestCase):

    def test_defect_names_home(self):
        defect = check()
        self.assertIn(str(self.pult_home / "role"), defect)


class StackSectionTest(unittest.TestCase):

    def test_section_names_paths(self):
        self.assertIn("ПУТИ", self.body)
'''

CONTEXT_HEAD = CONTEXT_BASE.replace("self.pult_home", "self.clone_home") \
    .replace('"ПУТИ", self.body', '"ВЫХОД", self.body')


class MergeGateObservationTest(ObservationSandbox):

    def test_ac8_merge_gate_journals_and_does_not_escalate(self):
        """Гейт мержа на диффе двух случаев «Контекста» пишет запись наблюдения и эскалирует мерж.

        Оба случая — смена утверждений вне раздела SPEC «Меняемое
        поведение»: с SPEC 01M45FJD46BX45VHC36S4VS9QN (требование 7) она
        эскалирует гейт мержа, а запись наблюдения остаётся прежней
        (требование 8).

        Ловит мутацию: находки об утверждениях не влиты в узел отказа —
        гейт мержа вернёт `False` и задача останется в `merge_gate`;
        наблюдение подключено только к переходу — записи на мерже нет.
        """
        self.commit_diff({"tests/test_context.py": CONTEXT_BASE},
                         {"tests/test_context.py": CONTEXT_HEAD})
        self.assertTrue(self.merge_gate())
        self.assertEqual("escalated", self.state())
        detail = self.observation()
        self.assertIn(f"tests/test_context.py: {CHANGED}"
                      f"CloneHomeTest::test_defect_names_home: ", detail)
        self.assertIn(f"tests/test_context.py: {CHANGED}"
                      f"StackSectionTest::test_section_names_paths: ", detail)

    def test_ac9_merge_gate_git_silence_journals_not_performed(self):
        """Молчание git на гейте мержа — запись «наблюдение не выполнено», мерж не остановлен.

        Ветки, которую гейт читает, нет: git не называет базу сравнения.

        Ловит мутацию: молчание git на наблюдении трактуется как «находок
        нет» молча — записи «наблюдение не выполнено» нет; либо оно
        эскалирует мерж — гейт вернёт `True`.
        """
        self.commit_diff({"tests/test_context.py": CONTEXT_BASE},
                         {"tests/test_context.py": CONTEXT_HEAD})
        self.assertFalse(self.merge_gate("task/t001-net-takoy-vetki"))
        self.assertEqual(STATE, self.state())
        hits = [f"{a} {d}" for a, d in self.journal()
                if NOT_PERFORMED in a or NOT_PERFORMED in d]
        self.assertTrue(hits, self.journal())

    def test_ac9_merge_gate_unparsable_file_journals_not_performed(self):
        """Неразбираемый файл на гейте мержа — запись «наблюдение не выполнено: …», мерж не остановлен.

        Ловит мутацию: неразбираемая сторона молча пропускается без
        записи — Оператор не узнает, что наблюдение по файлу не
        выполнено; либо неразбираемость эскалирует мерж.
        """
        self.commit_diff({"tests/test_alpha.py": BROKEN},
                         {"tests/test_alpha.py": ALPHA_TWO})
        self.assertFalse(self.merge_gate())
        self.assertEqual(STATE, self.state())
        hits = [f"{a} {d}" for a, d in self.journal()
                if NOT_PERFORMED in a or NOT_PERFORMED in d]
        self.assertTrue(hits, self.journal())

    def test_ac10_review_package_carries_changed_assertions_section(self):
        """Ревью-пакет при находках несёт раздел «Изменённые утверждения тестов» с теми же находками.

        Ловит мутацию: находки об утверждениях пишутся только в журнал и
        не попадают во вход ревьювера — раздела в тексте пакета нет; либо
        раздел есть, но без находки (пустой перечень).
        """
        self.commit_diff({"tests/test_context.py": CONTEXT_BASE},
                         {"tests/test_context.py": CONTEXT_HEAD})
        text = review.review_package(self.conn, TASK, "Песочница наблюдения",
                                     BRANCH)["text"]
        self.assertIn(REVIEW_SECTION, text)
        section = text[text.index(REVIEW_SECTION):]
        self.assertIn(f"{CHANGED}CloneHomeTest::test_defect_names_home", section)
        self.assertIn(f"{CHANGED}StackSectionTest::test_section_names_paths",
                      section)


if __name__ == "__main__":
    unittest.main()
