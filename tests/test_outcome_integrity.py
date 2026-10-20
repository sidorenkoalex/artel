"""Юнит-тесты помощников гейта неослабления по исходам
`orchestrator/advance_gates/outcome_integrity.py` (SPEC
01M5CJVB5B5V55PQQVR2QRHWZN, требования 3-5) на уровне записей
`CaseResult`: набор `PASS_TO_PASS`, краснота на ветке, сравнение отчётов,
рост пропусков и покрытие мандатом. Сквозные сценарии перехода — в
долгоживущем `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py`.
"""
import unittest

from orchestrator import project_profile
from orchestrator.advance_gates import outcome_integrity as gate
from orchestrator.reporters.outcome import CaseResult

PATH = "frontend/src/a.test.jsx"


def vitest(name: str, outcome: str = "passed", **fields) -> CaseResult:
    return CaseResult(project_profile.test_id("web", PATH, name), outcome,
                      mode=fields.pop("mode", "run"), **fields)


def junit(name: str, outcome: str = "passed") -> CaseResult:
    return CaseResult(project_profile.test_id("py", "tests/test_a.py", name),
                      outcome)


class RecordLevelTest(unittest.TestCase):

    def test_retried_pass_on_base_not_in_pass_to_pass(self):
        """`passed` с повтором на базе (`pult-vitest`) — вне `PASS_TO_PASS`; без повтора — в нём.

        Ловит мутацию: `in_pass_to_pass` без сверки `retries == 0` — тест с
        повтором на базе попадает в набор.
        """
        self.assertFalse(gate.in_pass_to_pass(vitest("x", retries=1)))
        self.assertTrue(gate.in_pass_to_pass(vitest("x")))
        self.assertTrue(gate.in_pass_to_pass(junit("x")))
        self.assertFalse(gate.in_pass_to_pass(junit("x", "skipped")))

    def test_red_on_branch_kinds(self):
        """Красный на ветке — `failed`, `error`, `passed` с повтором; `skipped` и чистый `passed` — нет.

        Ловит мутацию: `passed` с повтором не считается красным либо
        `skipped` считается красным.
        """
        for case, red in ((vitest("x", "failed"), True),
                          (junit("x", "error"), True),
                          (vitest("x", retries=2), True),
                          (vitest("x", "skipped", mode="skip"), False),
                          (junit("x", "skipped"), False),
                          (junit("x"), False)):
            with self.subTest(case=case):
                self.assertEqual(gate.red_on_branch(case), red)

    def test_compare_vitest_findings_and_non_findings(self):
        """Сравнение `pult-vitest`: исчез, стал пропуском, появились `todo`/`fails`, новые пропуск/`todo`/`fails` — находки; неизменные `todo`/`fails` и новый зелёный — нет; по одной на идентификатор.

        Ловит мутацию: `todo`/`fails` — находка без сверки с базой; «стал
        пропуском» только у `passed`; новый идентификатор не проверяется;
        у `to_todo` две находки.
        """
        base = [vitest("gone"), vitest("s_fail", "failed"),
                vitest("to_todo"), vitest("to_fails"),
                vitest("keep_todo", "skipped", mode="todo"),
                vitest("keep_fails", fails=True), vitest("quiet")]
        head = [vitest("s_fail", "skipped", mode="skip"),
                vitest("to_todo", "skipped", mode="todo"),
                vitest("to_fails", fails=True),
                vitest("keep_todo", "skipped", mode="todo"),
                vitest("keep_fails", fails=True), vitest("quiet"),
                vitest("new_skip", "skipped", mode="skip"),
                vitest("new_todo", "skipped", mode="todo"),
                vitest("new_fails", fails=True), vitest("new_pass")]
        found = {f.id.rsplit("::", 1)[1]: f.kind for f in gate.compare(base, head)}
        self.assertEqual(found, {
            "gone": gate.GONE, "s_fail": gate.BECAME_SKIPPED,
            "to_todo": gate.TODO_APPEARED, "to_fails": gate.FAILS_APPEARED,
            "new_skip": gate.NEW_SKIPPED, "new_todo": gate.NEW_TODO,
            "new_fails": gate.NEW_FAILS})
        self.assertEqual(gate.compare(base, head)[0].kind, gate.GONE)

    def test_compare_junit_became_skipped_from_each_outcome(self):
        """`junit-xml`: `passed`/`failed`/`error` базы, ставшие `skipped`, — «стал пропуском»; пропуск на обеих сторонах — нет.

        Ловит мутацию: «стал пропуском» только у `passed` базы; пропуск,
        бывший пропуском и на базе, даёт находку.
        """
        base = [junit("p"), junit("f", "failed"), junit("e", "error"),
                junit("s", "skipped")]
        head = [junit(n, "skipped") for n in ("p", "f", "e", "s")]
        kinds = {f.id.rsplit("::", 1)[1]: f.kind for f in gate.compare(base, head)}
        self.assertEqual(kinds, {n: gate.BECAME_SKIPPED for n in ("p", "f", "e")})

    def test_skip_growth_line(self):
        """Рост числа пропусков — строка без идентификаторов; без роста — пусто.

        Ловит мутацию: строка пишется и без роста либо несёт
        идентификатор теста.
        """
        base = [junit("a", "skipped"), junit("b")]
        self.assertEqual(gate.skip_growth(base, base), "")
        line = gate.skip_growth(base, [junit("a", "skipped"),
                                       junit("b", "skipped")])
        self.assertIn("пропуск", line)
        self.assertNotIn("::", line)

    def test_mandate_prefix_needs_separator(self):
        """Мандат: путь файла и префикс `путь::имя` с `::`, `[`, `#` или концом за ним покрывают; иной символ — нет.

        Ловит мутацию: покрытие `startswith` без сверки следующего
        символа — `путь::K` покрывает `путь::KOther::m`.
        """
        rel = "tests/test_a.py"
        cid = project_profile.test_id("py", rel, "K::m[a]")
        other = project_profile.test_id("py", rel, "KOther::m")
        again = project_profile.test_id("py", rel, "K::m", 2)
        self.assertEqual(gate.covering(cid, {rel: "ANSWER-1"}), "ANSWER-1")
        self.assertEqual(gate.covering(cid, {f"{rel}::K": "ANSWER-2"}), "ANSWER-2")
        self.assertEqual(gate.covering(cid, {f"{rel}::K::m": "ANSWER-3"}), "ANSWER-3")
        self.assertEqual(gate.covering(again, {f"{rel}::K::m": "ANSWER-3"}), "ANSWER-3")
        self.assertIsNone(gate.covering(other, {f"{rel}::K": "ANSWER-2"}))
        self.assertIsNone(gate.covering(cid, {"tests/test_b.py": "ANSWER-1"}))


if __name__ == "__main__":
    unittest.main()
