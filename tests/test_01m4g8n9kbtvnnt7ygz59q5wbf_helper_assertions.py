"""Гейт неослабления тестов видит утверждения в унаследованных помощниках и в
функциях `tests/sandbox.py` (AC-1..AC-5).

Группа: долгоживущий

Красен до реализации: сбор утверждений берёт помощников только среди методов
своего класса и функций своего модуля — удаление утверждения в помощнике
базового класса из другого модуля или в функции `tests/sandbox.py` гейт мержа
не видит (AC-1, AC-2: эскалации нет), перенос утверждения в унаследованный
помощник читается потерей утверждения и храповиком (AC-3: эскалация есть),
метод, проверяющий только через унаследованный помощник, утверждений не
имеет, и снятый вызов помощника находкой не становится (AC-4). Тест AC-5
зелёный с рождения: он держит находки прежних сценариев (помощник своего
класса, функция своего модуля, утверждение самого метода) против
реализации, которая сломает их, расширяя поиск помощников. Тест мандата
AC-2 до реализации тоже зелёный — находки, которую мандат снимает, ещё
нет; его пара без мандата (соседний тест AC-2) красна. Планка проверена
временным стабом реализации (сбор с контекстом файлов `tests/` обеих
сторон, сравнение вызывающих файлов вне диффа): все шесть тестов зелёные,
стаб удалён.

Песочница — `tests.sandbox.ConnRealGitSandbox`: настоящий git-репозиторий,
база — коммит на main, голова — ветка задачи от неё; файлы, которых нет в
голове сценария, в ветке не меняются. Мандат Оператора — `ANSWER-1.md` на
артефактной ветке коммитом ответа Оператора. Наблюдаемое — только через
публичный вход гейта мержа `test_integrity.merge_gate_escalates`: его
возврат, состояние задачи и журнал `steps` (деталь эскалации — текст
находок без мандата). Имена помощников, классов, методов, модулей и
ожидаемые значения берутся случайными при каждом запуске; зерно печатается
и входит в текст провала.
"""
import random
import unittest

from orchestrator import config, store
from orchestrator.advance_gates import test_integrity
from tests.sandbox import ConnRealGitSandbox

TASK = "T001"
BRANCH = "task/t001-pomoshchniki"
ARTIFACT = "artifact/t001"
STATE = "review"
SANDBOX_PATH = "tests/sandbox.py"
ESCALATED_ACTION = "state -> escalated"
OBSERVATION_ACTION = "изменены утверждения тестов (наблюдение)"
CHANGED = "утверждения изменены в "
RATCHET = "храповик"
ANSWER_SUBJECT = f"{TASK}: ANSWER-1 — ответ Оператора"
LETTERS = "abcdefghijklmnopqrstuvwxyz"


def word(rng: random.Random, used: set) -> str:
    """Новое случайное слово из шести строчных латинских букв."""
    while True:
        found = "".join(rng.choice(LETTERS) for _ in range(6))
        if found not in used:
            used.add(found)
            return found


class HelperSandbox(ConnRealGitSandbox):
    """Задача `TASK` в состоянии `STATE`; `commit_diff` кладёт базу на main и
    голову на ветку задачи; `merge_gate` — публичный вход гейта мержа."""

    seed = None

    def setUp(self):
        super().setUp()
        store.insert_task(self.conn, TASK, "Песочница помощников", STATE,
                          BRANCH, config.DEFAULT_TARGET, 10.0)
        self.conn.commit()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used: set = set()

    def name(self, prefix: str) -> str:
        return f"{prefix}{word(self.rng, self.used)}"

    def klass(self, prefix: str) -> str:
        return f"{prefix}{word(self.rng, self.used).capitalize()}Test"

    def write(self, path: str, text) -> None:
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def commit_diff(self, base: dict, head: dict) -> None:
        """База — коммит на main; голова — коммит ветки задачи поверх неё.
        Файл, которого нет в `head`, в ветке не меняется."""
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

    def merge_gate(self) -> bool:
        return test_integrity.merge_gate_escalates(self.conn, TASK, STATE,
                                                   BRANCH, ARTIFACT)

    def journal(self) -> list:
        return [(row["action"], row["detail"] or "")
                for row in self.conn.execute(
                    "SELECT action, detail FROM steps WHERE task_id=? "
                    "ORDER BY id", (TASK,))]

    def escalation(self) -> str:
        """Деталь эскалации гейта мержа — текст находок без мандата."""
        found = [detail for action, detail in self.journal()
                 if action == ESCALATED_ACTION]
        self.assertEqual(1, len(found), self.why(
            f"ожидалась одна эскалация, журнал: {self.journal()}"))
        return found[0]

    def everything(self) -> str:
        return "\n".join(detail for _action, detail in self.journal())

    def state(self) -> str:
        return self.conn.execute("SELECT state FROM tasks WHERE id=?",
                                 (TASK,)).fetchone()["state"]

    def why(self, text: str) -> str:
        return f"{text} (зерно: {self.seed})"


def base_module(base: str, helper: str, body: str) -> str:
    """Модуль `tests/` с базовым классом и одним помощником."""
    return (f"import unittest\n\n\n"
            f"class {base}(unittest.TestCase):\n\n"
            f"    def {helper}(self, value):\n"
            f"{body}")


# ---------------------------------------------------------------------------
# AC-1: помощник базового класса из другого модуля `tests/`.

class InheritedHelperWeakenedTest(HelperSandbox):

    def test_ac1_removed_assertion_in_base_class_helper_is_finding_at_caller(self):
        """Удалено утверждение помощника базового класса из другого модуля `tests/`.

        Модуль `tests/<модуль>.py` держит класс `<Base>` с помощником
        `<helper>(self, value)`: в базе — `assertEqual(value, k)` и
        `assertTrue(value)`, в голове `assertEqual` удалён. Файл теста
        `tests/test_<x>.py` в ветке не меняется: класс `<Caller>(<Base>)`,
        метод `test_<m1>` зовёт `self.<helper>(…)`, соседний `test_<m2>`
        помощника не зовёт. Гейт мержа эскалирует; текст находок называет
        `<Caller>::test_<m1>`, имя помощника и путь его модуля; метод
        `test_<m2>` в журнале не назван.

        Ловит мутацию: помощник ищется только среди методов своего класса
        (базовые классы не обходятся) — эскалации нет, гейт возвращает
        `False`; базовые классы обходятся только в своём файле — то же;
        сравниваются лишь файлы диффа, а вызывающий файл не изменён — то
        же; находка не называет помощника или его файл — в детали
        эскалации нет `<helper>` либо `tests/<модуль>.py`; находка
        ставится всем наследникам `<Base>`, а не вызывающим — в журнале
        появится `test_<m2>`.
        """
        mod, base, helper = self.name("helpers_"), self.klass("Base"), \
            self.name("check_")
        caller, m1, m2 = self.klass("Caller"), self.name("test_"), \
            self.name("test_")
        expected = self.rng.randrange(1, 1000)
        mod_path = f"tests/{mod}.py"
        caller_path = f"tests/test_{word(self.rng, self.used)}.py"
        caller_source = (f"import unittest\n\nfrom tests.{mod} import {base}\n\n\n"
                         f"class {caller}({base}):\n\n"
                         f"    def {m1}(self):\n"
                         f"        result = compute()\n"
                         f"        self.{helper}(result)\n\n"
                         f"    def {m2}(self):\n"
                         f"        self.assertTrue(ready())\n")
        before = base_module(base, helper,
                             f"        self.assertEqual(value, {expected})\n"
                             f"        self.assertTrue(value)\n")
        after = base_module(base, helper, "        self.assertTrue(value)\n")
        self.commit_diff({mod_path: before, caller_path: caller_source},
                         {mod_path: after})

        self.assertTrue(self.merge_gate(), self.why(
            f"удаление утверждения в {mod_path}::{base}.{helper} не "
            f"эскалировало мерж, журнал: {self.journal()}"))
        detail = self.escalation()
        for needle in (f"{caller}::{m1}", helper, mod_path):
            self.assertIn(needle, detail, self.why(
                f"находка не называет {needle!r}: {detail}"))
        self.assertNotIn(f"{caller}::{m2}", self.everything(), self.why(
            f"находка у метода, не зовущего помощника: {self.everything()}"))


# ---------------------------------------------------------------------------
# AC-2: функция `tests/sandbox.py` и мандат на её путь.

class SandboxFunctionWeakenedTest(HelperSandbox):

    def setUp(self):
        super().setUp()
        self.fn, self.other = self.name("assert_"), self.name("expect_")
        expected = self.rng.randrange(1, 1000)
        sandbox = (f'"""Помощники песочницы."""\n\n\n'
                   f"def {self.fn}(test, value):\n"
                   f"    test.assertEqual(value, {expected})\n"
                   f"    test.assertIsNotNone(value)\n\n\n"
                   f"def {self.other}(test, value):\n"
                   f"    test.assertTrue(value)\n")
        weakened = sandbox.replace(
            f"    test.assertEqual(value, {expected})\n", "")
        self.callers = []
        files = {SANDBOX_PATH: sandbox}
        for _ in range(2):
            klass, method = self.klass("Caller"), self.name("test_")
            files[f"tests/test_{word(self.rng, self.used)}.py"] = (
                f"import unittest\n\n"
                f"from tests.sandbox import {self.fn}, {self.other}\n\n\n"
                f"class {klass}(unittest.TestCase):\n\n"
                f"    def {method}(self):\n"
                f"        {self.fn}(self, compute())\n")
            self.callers.append(f"{klass}::{method}")
        self.control_class, self.control = self.klass("Other"), \
            self.name("test_")
        files[f"tests/test_{word(self.rng, self.used)}.py"] = (
            f"import unittest\n\n"
            f"from tests.sandbox import {self.fn}, {self.other}\n\n\n"
            f"class {self.control_class}(unittest.TestCase):\n\n"
            f"    def {self.control}(self):\n"
            f"        {self.other}(self, compute())\n")
        self.commit_diff(files, {SANDBOX_PATH: weakened})

    def test_ac2_removed_assertion_in_sandbox_function_is_finding_at_callers(self):
        """Удалено утверждение функции `tests/sandbox.py` — находка у каждого вызывающего.

        `tests/sandbox.py` в ветке теряет `assertEqual` функции `<fn>`; два
        файла тестов, не менявшиеся в ветке, зовут `<fn>(self, …)` по
        импорту `from tests.sandbox import …`, третий зовёт только соседнюю
        функцию `<other>` с нетронутым утверждением. Гейт мержа эскалирует;
        текст находок называет обоих вызывающих, `<fn>` и
        `tests/sandbox.py`; метод, зовущий `<other>`, не назван.

        Ловит мутацию: функции `tests/sandbox.py` в сбор не входят —
        эскалации нет; находка заводится только у первого найденного
        вызывающего — второй не назван; находка ставится всем методам
        файлов, импортирующих из `tests/sandbox.py`, — назван метод,
        зовущий `<other>`; находка не называет помощника или его файл.
        """
        self.assertTrue(self.merge_gate(), self.why(
            f"удаление утверждения в {SANDBOX_PATH}::{self.fn} не "
            f"эскалировало мерж, журнал: {self.journal()}"))
        detail = self.escalation()
        for needle in (*self.callers, self.fn, SANDBOX_PATH):
            self.assertIn(needle, detail, self.why(
                f"находка не называет {needle!r}: {detail}"))
        self.assertNotIn(f"{self.control_class}::{self.control}",
                         self.everything(), self.why(
                             f"находка у метода, не зовущего {self.fn}: "
                             f"{self.everything()}"))

    def test_ac2_mandate_on_sandbox_path_lifts_finding(self):
        """Мандат ANSWER на путь `tests/sandbox.py` снимает находку у вызывающих.

        Тот же дифф, что в соседнем тесте (без мандата он эскалирует с
        находками у обоих вызывающих); `ANSWER-1.md` на артефактной ветке
        несёт строку мандата `tests/sandbox.py`. Ни одна эскалация гейта
        мержа не называет ни вызывающих методов, ни `<fn>`.

        Ловит мутацию: покрытие мандатом сверяется только с путём файла
        вызывающего метода (как у находок своего файла) — находка у
        вызывающих остаётся непокрытой, мерж эскалирует с их именами.
        """
        self.add_mandate(SANDBOX_PATH)
        self.merge_gate()
        for action, detail in self.journal():
            if action != ESCALATED_ACTION:
                continue
            for needle in (*self.callers, self.fn):
                self.assertNotIn(needle, detail, self.why(
                    f"мандат на {SANDBOX_PATH} не снял находку: {detail}"))


# ---------------------------------------------------------------------------
# AC-3: перенос утверждения из метода в унаследованный помощник.

class MovedIntoInheritedHelperTest(HelperSandbox):

    def test_ac3_move_into_inherited_helper_is_neither_finding_nor_ratchet(self):
        """Перенос утверждения из метода в помощник базового класса — без находки и храповика.

        Два варианта в одном диффе: базовый класс в другом модуле `tests/`
        (в голове у него появляется помощник с `assertEqual(value, k)`,
        метод вместо своего `assertEqual(result, k)` зовёт его) и базовый
        класс в том же файле (появляется помощник с `assertIn(value, …)`,
        метод вместо своего `assertIn(item, …)` зовёт его). Гейт мержа не
        эскалирует, задача остаётся в своём состоянии, журнал не называет
        ни одного из методов и не несёт находки храповика.

        Ловит мутацию: помощник базового класса не разворачивается в одной
        из сторон — перенос читается удалением утверждения, мерж
        эскалирует с именем метода; базовые классы обходятся только в
        чужом модуле или только в своём файле — эскалирует один из двух
        вариантов; храповик считает утверждения без унаследованных
        помощников — убыль «утверждения 2 → 0» эскалирует мерж.
        """
        mod, base, helper, spare = self.name("helpers_"), self.klass("Base"), \
            self.name("expect_"), self.name("spare_")
        local_base, local_helper, local_spare = self.klass("Local"), \
            self.name("expect_"), self.name("spare_")
        c1, c2 = self.klass("Caller"), self.klass("Caller")
        m1, m2 = self.name("test_"), self.name("test_")
        k = self.rng.randrange(1, 1000)
        a, b = self.rng.sample(range(1000, 2000), 2)
        mod_path = f"tests/{mod}.py"
        spare_body = f"    def {spare}(self, value):\n        use(value)\n"
        mod_before = (f"import unittest\n\n\n"
                      f"class {base}(unittest.TestCase):\n\n{spare_body}")
        mod_after = mod_before + (f"\n    def {helper}(self, value):\n"
                                  f"        self.assertEqual(value, {k})\n")

        def caller_file(local_extra: str, body1: str, body2: str) -> str:
            return (f"import unittest\n\nfrom tests.{mod} import {base}\n\n\n"
                    f"class {local_base}(unittest.TestCase):\n\n"
                    f"    def {local_spare}(self, value):\n"
                    f"        use(value)\n"
                    f"{local_extra}\n\n"
                    f"class {c1}({base}):\n\n"
                    f"    def {m1}(self):\n"
                    f"        result = compute()\n"
                    f"{body1}\n\n"
                    f"class {c2}({local_base}):\n\n"
                    f"    def {m2}(self):\n"
                    f"        item = pick()\n"
                    f"{body2}")

        caller_before = caller_file(
            "",
            f"        self.assertEqual(result, {k})\n",
            f"        self.assertIn(item, ({a}, {b}))\n")
        caller_after = caller_file(
            f"\n    def {local_helper}(self, value):\n"
            f"        self.assertIn(value, ({a}, {b}))\n",
            f"        self.{helper}(result)\n",
            f"        self.{local_helper}(item)\n")
        caller_path = f"tests/test_{word(self.rng, self.used)}.py"
        self.commit_diff({mod_path: mod_before, caller_path: caller_before},
                         {mod_path: mod_after, caller_path: caller_after})

        self.assertFalse(self.merge_gate(), self.why(
            f"перенос в унаследованный помощник эскалировал мерж, журнал: "
            f"{self.journal()}"))
        self.assertEqual(STATE, self.state(), self.why("состояние задачи"))
        everything = self.everything()
        for needle in (f"{c1}::{m1}", f"{c2}::{m2}", RATCHET):
            self.assertNotIn(needle, everything, self.why(
                f"перенос дал находку ({needle!r}): {everything}"))


# ---------------------------------------------------------------------------
# AC-4: метод, проверяющий только через унаследованный помощник.

class OnlyInheritedHelperTest(HelperSandbox):

    def test_ac4_method_checking_via_inherited_helper_has_assertions(self):
        """Метод без своих утверждений, зовущий помощника базового класса, утверждения имеет.

        Список утверждений метода гейт отдаёт наружу только через
        сравнение базы и головы, поэтому непустота читается так: в базе
        `<Caller>::test_<m>` проверяет единственным вызовом
        `self.<helper>(…)` помощника базового класса из другого модуля
        `tests/` (сам помощник в ветке не меняется), в голове вызов
        помощника снят. Пустой список базы сравнивать не с чем — находки
        не было бы; гейт мержа эскалирует, и деталь называет метод.

        Ловит мутацию: базовые классы обходятся только у стороны головы
        (или сбор не идёт по `from tests.<модуль> import <Base>`) — список
        базы пуст, снятие вызова находкой не становится, гейт возвращает
        `False`.
        """
        mod, base, helper = self.name("helpers_"), self.klass("Base"), \
            self.name("check_")
        caller, method = self.klass("Caller"), self.name("test_")
        expected = self.rng.randrange(1, 1000)
        mod_path = f"tests/{mod}.py"
        caller_path = f"tests/test_{word(self.rng, self.used)}.py"

        def caller_file(body: str) -> str:
            return (f"import unittest\n\nfrom tests.{mod} import {base}\n\n\n"
                    f"class {caller}({base}):\n\n"
                    f"    def {method}(self):\n"
                    f"{body}")

        self.commit_diff(
            {mod_path: base_module(base, helper,
                                   f"        self.assertEqual(value, "
                                   f"{expected})\n"),
             caller_path: caller_file(f"        self.{helper}(compute())\n")},
            {caller_path: caller_file("        use(compute())\n")})

        self.assertTrue(self.merge_gate(), self.why(
            f"снятый вызов унаследованного помощника не стал находкой — "
            f"список утверждений метода пуст, журнал: {self.journal()}"))
        self.assertIn(f"{caller}::{method}", self.escalation(), self.why(
            "эскалация не называет метод"))


# ---------------------------------------------------------------------------
# AC-5: прежние сценарии — помощник своего класса, функция своего модуля,
# утверждение самого метода.

class FormerScenariosTest(HelperSandbox):

    def test_ac5_own_class_module_and_own_assertion_findings_unchanged(self):
        """Находки и наблюдения прежних сценариев не меняются.

        Один файл `tests/test_<x>.py`, класс `<Caller>(<Base>)`, `<Base>` —
        в другом модуле `tests/` и в ветке не меняется; у него помощник
        `<own>` с `assertEqual(value, k)`. В голове: свой помощник класса
        `<own>` (перекрывает одноимённый базовый) теряет `assertEqual`;
        функция модуля `<fn>` теряет `assert value > 0`; метод
        `test_own_assert` теряет свой `assertTrue(ready())`; метод
        `test_moved` переносит `assertEqual(result, k)` в свой помощник
        `<own2>`; `test_untouched` не меняется. Запись наблюдения несёт
        прежние строки «<файл>: утверждения изменены в <Caller>::<метод>:
        <текст утверждения базы>» для трёх ослабленных методов и не
        называет перенесённый и нетронутый; мерж эскалирует.

        Ловит мутацию: поиск помощника идёт сначала по базовым классам —
        для `self.<own>` берётся нетронутый базовый `<own>`, находка у
        метода своего помощника пропадает; функции своего модуля выпадают
        из сбора при подключении функций `tests/sandbox.py` — пропадает
        находка `test_module_fn`; утверждения помощника кладутся вместо
        утверждений метода, а не вместе с ними — пропадает находка
        `test_own_assert` либо перенос в свой помощник становится
        находкой; текст находки меняет прежнюю форму для помощника своего
        класса — строки с текстом утверждения базы нет.
        """
        mod, base = self.name("helpers_"), self.klass("Base")
        own, own2, fn = self.name("check_"), self.name("check_"), \
            self.name("verify_")
        caller = self.klass("Caller")
        k = self.rng.randrange(1, 1000)
        mod_path = f"tests/{mod}.py"
        path = f"tests/test_{word(self.rng, self.used)}.py"

        def source(fn_body, own_body, own_assert, moved) -> str:
            return (f"import unittest\n\nfrom tests.{mod} import {base}\n\n\n"
                    f"def {fn}(value):\n{fn_body}\n\n"
                    f"class {caller}({base}):\n\n"
                    f"    def {own}(self, value):\n{own_body}\n"
                    f"    def {own2}(self, value):\n"
                    f"        self.assertEqual(value, {k})\n\n"
                    f"    def test_own_helper(self):\n"
                    f"        self.{own}(compute())\n\n"
                    f"    def test_module_fn(self):\n"
                    f"        {fn}(compute())\n\n"
                    f"    def test_own_assert(self):\n{own_assert}\n"
                    f"    def test_moved(self):\n"
                    f"        result = compute()\n{moved}\n"
                    f"    def test_untouched(self):\n"
                    f"        self.assertIn(1, items())\n")

        before = source("    assert value > 0\n",
                        f"        self.assertEqual(value, {k})\n",
                        "        self.assertTrue(ready())\n",
                        f"        self.assertEqual(result, {k})\n")
        after = source("    use(value)\n",
                       "        use(value)\n",
                       "        ready()\n",
                       f"        self.{own2}(result)\n")
        self.commit_diff(
            {mod_path: base_module(base, own,
                                   f"        self.assertEqual(value, {k})\n"),
             path: before},
            {path: after})

        self.assertTrue(self.merge_gate(), self.why(
            f"прежние ослабления не эскалировали мерж: {self.journal()}"))
        observed = "; ".join(detail for action, detail in self.journal()
                             if action == OBSERVATION_ACTION)
        for method, text in (("test_own_helper",
                              f"self.assertEqual(value, {k})"),
                             ("test_module_fn", "assert value > 0"),
                             ("test_own_assert", "self.assertTrue(ready())")):
            line = f"{path}: {CHANGED}{caller}::{method}: {text}"
            self.assertIn(line, observed, self.why(
                f"нет прежней строки наблюдения {line!r}: {observed}"))
        everything = self.everything()
        for method in ("test_moved", "test_untouched"):
            self.assertNotIn(f"{caller}::{method}", everything, self.why(
                f"находка у {method}: {everything}"))


if __name__ == "__main__":
    unittest.main()
