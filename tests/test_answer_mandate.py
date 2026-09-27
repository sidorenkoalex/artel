"""Юнит-тесты `orchestrator/advance_gates/mandate.py` (SPEC
01M3GKJBXEBHB6ZA48J7VG8Z8W, требования 1-2) — общий узел разбора строки
мандата Оператора и проверка её элементов при записи ответа.

Здесь только чистые функции узла и углы, которых планка задачи
(`tasks/01M3GKJBXEBHB6ZA48J7VG8Z8W/acceptance_tests/`) не кроет: она
работает через команду `answer` в настоящем git и потому не может
проверить ни молчание git на дереве кодовой ветки, ни отдельные формы
«не похож на путь», ни то, что оба гейта после переноса зовут ровно тот
же узел (у неё это видно только по совпадению трёх списков).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import answer, gitcmd  # noqa: E402
from orchestrator.advance_gates import mandate  # noqa: E402
from orchestrator.advance_gates import test_integrity, zones  # noqa: E402

ZONES = mandate._ZONES_MANDATE_MARKER
WEAKENING = mandate.TEST_WEAKENING_MANDATE_MARKER


class ElementsTest(unittest.TestCase):
    """`mandate.elements` — «маркер -> список элементов» одной строки."""

    def test_line_without_the_marker_gives_none(self):
        """Ловит мутацию: «строка не о мандате» возвращает пустой список
        вместо `None` — требование 2г не может отличить её от голого
        маркера, и проверка при записи начала бы отказывать на КАЖДОЙ
        обычной строке файла ответа."""
        self.assertIsNone(mandate.elements("Обычный ответ.", ZONES))

    def test_marker_not_at_line_start_gives_none(self):
        """Ловит мутацию: маркер ищется подстрокой где угодно в строке
        вместо `startswith` — процитированный в абзаце маркер («я читал
        про …») стал бы мандатом Оператора."""
        self.assertIsNone(mandate.elements(
            "я читал про «Расширение зон разрешено: docs/a.md» в скиле",
            ZONES))

    def test_bare_marker_gives_empty_list_not_none(self):
        """Ловит мутацию: голый маркер возвращает `None` наравне со
        строкой без маркера — отказ требования 2г не сработал бы, и
        Оператор, забывший дописать пути, получил бы ANSWER без мандата."""
        self.assertEqual([], mandate.elements(ZONES, ZONES))

    def test_leading_indent_and_empty_elements_are_dropped(self):
        """Ловит мутацию: разбор идёт по НЕ стрипнутой строке либо не
        отбрасывает пустые элементы — первым элементом мандата с отступом
        оказался бы путь с ведущими пробелами, и исправный мандат
        Оператора отказал бы как «элемент содержит пробел»."""
        self.assertEqual(
            ["a.py", "b/"],
            mandate.elements(f"   {ZONES}  a.py ,, b/  ", ZONES))

    def test_other_marker_on_the_same_line_is_not_matched(self):
        """Ловит мутацию: маркер при разборе игнорируется, а строка делится
        по запятым от начала — строка мандата зон читалась бы и как мандат
        ослабления тестов, и один и тот же путь получал бы оба разрешения
        разом."""
        self.assertIsNone(mandate.elements(f"{ZONES} tests/a.py", WEAKENING))


class ThreeConsumersShareOneNodeTest(unittest.TestCase):
    """Требование 1: разбор «маркер -> элементы» — один объект на все три
    места, а не три совпадающие копии."""

    def test_both_gates_import_the_same_parse_object(self):
        """Ловит мутацию: `zones.py` или `test_integrity.py` получили
        собственную копию разбора (скопированную функцию с тем же телом) —
        списки совпадали бы ровно до первой правки одной из копий, то есть
        ровно тот дефект, ради которого задача заведена."""
        self.assertIs(zones.elements, mandate.elements)
        self.assertIs(test_integrity.elements, mandate.elements)

    def test_markers_are_one_object_per_marker(self):
        """Ловит мутацию: маркер оставлен литералом по прежнему адресу и
        лишь «выглядит» тем же — правка текста маркера в одном месте
        разошлась бы с проверкой при записи, и мандат молча перестал бы
        распознаваться."""
        self.assertIs(zones._ZONES_MANDATE_MARKER,
                      mandate._ZONES_MANDATE_MARKER)
        self.assertIs(test_integrity.TEST_WEAKENING_MANDATE_MARKER,
                      mandate.TEST_WEAKENING_MANDATE_MARKER)

    def test_answer_is_the_third_consumer_of_the_same_parse(self):
        """Третий потребитель узла — сама команда `answer`: её
        `_zones_mandate_marker_paths` обязан отдавать то же, что отдаёт
        `mandate.elements` на той же строке.

        Ловит мутацию: `answer` вернул себе собственное отсечение префикса
        маркера (`line[len(МАРКЕР):]` без `strip` строки, как было до этой
        задачи) — мандат с отступом `answer` разобрал бы иначе, чем оба
        гейта, и запись журнала о мандате разошлась бы с тем, что гейт
        реально засчитал."""
        line = f"   {ZONES}  orchestrator/answer.py ,, tests/  "

        self.assertIs(answer.mandate, mandate)
        self.assertEqual(mandate.elements(line, ZONES),
                         answer._zones_mandate_marker_paths(line + "\n"))


class ThreeConsumersOnOneLineTest(unittest.TestCase):
    """AC-1, вторая половина: на ОДНОЙ и той же строке мандата все три
    потребителя получают один и тот же список элементов — проверяется не
    тождеством объекта функции, а результатом каждого потребителя на
    своём пути (`answer` — по тексту файла, оба гейта — по ANSWER-n.md
    ветки)."""

    TASK = "T777"
    BRANCH = "artifacts/T777"
    EXPECTED = {"tests/test_alpha.py", "tests/test_beta.py"}

    def text(self, marker: str) -> str:
        """Строка мандата с отступом и пустым элементом внутри перечня —
        углы, на которых три копии разбора разошлись бы первыми."""
        return f"   {marker}  tests/test_alpha.py ,, tests/test_beta.py  \n"

    def gate_elements(self, module, call) -> set:
        text = self.text(WEAKENING if module is test_integrity else ZONES)
        with mock.patch.object(
                gitcmd, "ls_tree_files",
                return_value=[f"tasks/{self.TASK}/ANSWER-1.md"]), \
             mock.patch.object(gitcmd, "show", return_value=(text, "")), \
             mock.patch.object(module, "_answer_commit_is_role_step_autocommit",
                               return_value=False):
            return set(call(self.BRANCH, self.TASK))

    def test_all_three_consumers_get_the_same_elements(self):
        """Ловит мутацию: один из потребителей перестал звать общий узел
        (вернул себе разбор с прежним поведением — без `strip` строки либо
        без отбрасывания пустых элементов) — списки разошлись бы ровно на
        этой строке, и мандат Оператора сработал бы у одного потребителя и
        не сработал у другого: дефект, ради которого задача заведена."""
        from_answer = set(answer._zones_mandate_marker_paths(self.text(ZONES)))
        from_zones = self.gate_elements(zones, zones._answer_zones_mandate)
        from_integrity = self.gate_elements(test_integrity,
                                            test_integrity._answer_mandate)

        self.assertEqual(self.EXPECTED, from_answer)
        self.assertEqual(self.EXPECTED, from_zones)
        self.assertEqual(self.EXPECTED, from_integrity)


class LooksLikePathTest(unittest.TestCase):
    """Правило 2а «не похож на путь репозитория» в отдельности."""

    def test_repo_paths_and_directory_form_pass(self):
        """Ловит мутацию: набор допустимых символов сужен (например без
        `-` или без `/` на конце) — штатные записи зон
        («orchestrator/advance_gates/», «scripts/ci_push_class.py»)
        отказывали бы исправному мандату."""
        for text in ("orchestrator/answer.py", "orchestrator/advance_gates/",
                     "tests/", "docs/adr/ADR-0002.md", "CLAUDE.md",
                     "scripts/ci_push_class.py"):
            with self.subTest(text=text):
                self.assertTrue(mandate._looks_like_path(text))

    def test_absolute_path_and_parent_segment_fail(self):
        """Ловит мутацию: проверка сведена к «непустая строка без
        пробелов» — мандат на `/etc/passwd` или `../../чужой-репозиторий`
        прошёл бы как путь репозитория, хотя зоной задачи не является
        ничего вне её рабочей копии."""
        for text in ("/etc/passwd", "../../other/repo", "a/../b", ""):
            with self.subTest(text=text):
                self.assertFalse(mandate._looks_like_path(text))


class RefusalsTest(unittest.TestCase):
    """`mandate.refusals` — проверка всех строк мандатов текста ответа."""

    TREE = ["orchestrator/answer.py", "tests/test_alpha.py"]

    def refusals(self, text: str) -> list:
        with mock.patch.object(mandate.gitcmd, "ls_tree_files",
                               return_value=self.TREE):
            return mandate.refusals(text, "task/branch")

    def test_valid_mandates_of_both_kinds_pass(self):
        """Ловит мутацию: проверка отказывает на исправном перечне (звонит
        правило мандата ослабления на строке мандата зон или наоборот) —
        Оператор не смог бы выдать ни один мандат вовсе."""
        text = (f"{ZONES} orchestrator/answer.py, orchestrator/\n\n"
                f"Основание: решение Оператора.\n\n"
                f"{WEAKENING} tests/test_alpha.py, tests/b.py::C::test_x\n")
        self.assertEqual([], self.refusals(text))

    def test_every_mandate_line_is_checked_not_only_the_first(self):
        """Ловит мутацию: проверяется только ПЕРВАЯ строка маркера (так
        вёл себя прежний разбор `answer`) — ошибочный мандат во второй
        строке того же файла проехал бы без проверки, и прецедент 26.09
        повторился бы на файле с двумя строками мандата."""
        text = (f"{ZONES} orchestrator/answer.py\n"
                f"{ZONES} orchestrator/net_takogo_puti.py\n"
                f"{WEAKENING} orchestrator/answer.py\n")

        found = self.refusals(text)

        self.assertEqual(2, len(found), found)
        self.assertIn("orchestrator/net_takogo_puti.py", found[0])
        self.assertIn("нет ни файла, ни каталога", found[0])
        self.assertIn("вне области tests/**/*.py", found[1])

    def test_refusal_names_the_line_the_element_and_the_reason(self):
        """Ловит мутацию: отказ называет только причину (или только
        элемент) — Оператор, писавший мандат в файле из нескольких строк,
        не знает, какую строку править."""
        line = f"{ZONES} orchestrator/artel.py — только разбор аргументов"

        found = self.refusals(line + "\n")

        self.assertEqual(1, len(found))
        self.assertIn(line, found[0])
        self.assertIn("orchestrator/artel.py — только разбор аргументов",
                      found[0])
        self.assertIn("пробел", found[0])

    def test_missing_zones_path_refuses_but_missing_weakening_path_does_not(self):
        """Требование 2б названо только для мандата зон: штатный предмет
        мандата ослабления — УДАЛЁННЫЙ файл тестов, которого в дереве
        ветки уже нет.

        Ловит мутацию: проверка существования применена к обоим маркерам —
        мандат на удаление `tests/test_x.py` (главный сценарий гейта
        неослабления тестов) отказывал бы всегда, и снять находку
        удаления стало бы нечем."""
        self.assertEqual(
            1, len(self.refusals(f"{ZONES} tests/test_udalyonnyy.py\n")))
        self.assertEqual(
            [], self.refusals(f"{WEAKENING} tests/test_udalyonnyy.py\n"))

    def test_git_silence_skips_only_the_existence_rule(self):
        """Молчание git на дереве кодовой ветки (ветки ещё нет, сбой
        команды) снимает проверку существования и НЕ снимает остальные
        правила.

        Ловит мутацию: на `None` от `ls_tree_files` проверка либо
        отказывает всему (Оператор не может ответить на эскалацию при
        молчащем git), либо пропускает файл целиком (элемент с пробелом
        проехал бы — ровно прецедент 26.09)."""
        with mock.patch.object(mandate.gitcmd, "ls_tree_files",
                               return_value=None):
            self.assertEqual(
                [], mandate.refusals(f"{ZONES} net_v_dereve.py\n", "task/x"))
            self.assertEqual(
                1, len(mandate.refusals(f"{ZONES} a.py — poyasnenie\n",
                                        "task/x")))

    def test_no_code_branch_does_not_read_git_at_all(self):
        """Ловит мутацию: пустая кодовая ветка (её у задачи может не быть)
        уходит в `git ls-tree` как имя ветки — git отвечает деревом
        ТЕКУЩЕЙ ревизии, и существование проверялось бы не по ветке
        задачи, а по тому, что случайно оказалось под HEAD."""
        with mock.patch.object(mandate.gitcmd, "ls_tree_files") as ls_tree:
            self.assertEqual([], mandate.refusals(f"{ZONES} net_v_dereve.py\n",
                                                  None))
        ls_tree.assert_not_called()

    def test_directory_element_with_trailing_slash_is_accepted(self):
        """Ловит мутацию: `/` на конце не снимается перед сверкой с
        деревом — «orchestrator/» искалось бы префиксом «orchestrator//»,
        и самая частая форма мандата зон (зона-каталог, как пишутся
        `config.COMMON_ZONES`) отказывала бы всегда."""
        self.assertEqual([], self.refusals(f"{ZONES} orchestrator/\n"))
        self.assertEqual([], self.refusals(f"{ZONES} orchestrator\n"))

    def test_broken_qualified_name_forms_refuse(self):
        """Ловит мутацию: форма `путь::имя` не проверяется, проверяется
        только префикс `tests/` — элемент `tests/test_alpha.py::` доехал
        бы до гейта, там не совпал ни с одной находкой, и мандат молча не
        сработал бы."""
        for tail in ("tests/test_alpha.py::",
                     "tests/test_alpha.py::Class::",
                     "tests/test_alpha.py::Class::test-x"):
            with self.subTest(tail=tail):
                found = self.refusals(f"{WEAKENING} {tail}\n")
                self.assertEqual(1, len(found), found)
                self.assertIn("форма", found[0])

    def test_bare_marker_refuses_naming_the_empty_element_list(self):
        """Требование 2г: после маркера нет ни одного непустого элемента —
        именованный отказ, а не молчаливый пропуск.

        Ловит мутацию: ветка пустого списка убрана из `refusals` (голый
        маркер трактуется как «строка не о мандате») — Оператор, забывший
        дописать пути или оставивший «Расширение зон разрешено: ,,»,
        получил бы ANSWER без единого элемента мандата, гейт зон отказал
        бы переходу как будто мандата нет вовсе, и причина снова была бы
        не названа."""
        for line in (ZONES, f"{WEAKENING}   ", f"   {ZONES} ,, "):
            with self.subTest(line=line):
                found = self.refusals(line + "\n")

                self.assertEqual(1, len(found), found)
                self.assertIn(line.strip(), found[0],
                              "отказ обязан назвать строку")
                self.assertIn("после маркера нет ни одного непустого "
                              "элемента", found[0])

    def test_weakening_element_under_tests_but_not_python_refuses(self):
        """Область гейта неослабления тестов — `tests/**/*.py`
        (`test_integrity._in_scope`), сверка элемента с находкой — точное
        вхождение: элемент «tests/» или «tests/fixtures/data.json» гейт не
        засчитает никогда (REVIEW итерация 1, R1-F2).

        Ловит мутацию: правило при записи сведено к префиксу `tests/` без
        `.py` — такой мандат записывается без отказа и молча не
        срабатывает, то есть остаётся ровно тот класс дефекта, который
        задача закрывает."""
        for element in ("tests/", "tests/fixtures/data.json", "tests"):
            with self.subTest(element=element):
                self.assertFalse(mandate.in_weakening_scope(element))
                self.assertFalse(test_integrity._in_scope(element),
                                 "область гейта и правило при записи "
                                 "обязаны совпадать")

                found = self.refusals(f"{WEAKENING} {element}\n")

                self.assertEqual(1, len(found), found)
                self.assertIn(element, found[0])

    def test_plain_text_answer_has_no_refusals(self):
        """Ловит мутацию: строкой мандата считается любая строка с
        двоеточием — обычный ответ Оператора по существу вопроса
        отказывал бы, и канал ответа на эскалацию закрылся бы целиком
        (`canary` коммитит именно такой синтетический ответ)."""
        self.assertEqual([], self.refusals(
            "Ответ Оператора: вариант A — продолжай штатным путём.\n"))


if __name__ == "__main__":
    unittest.main()
