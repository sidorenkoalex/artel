"""Раздел SPEC «## Заменяемые тесты» в guard, сигнал аудита SPEC, запреты планки и трассируемость шаблонной таблицы `.each` (AC-1 — половина CLI, AC-2, AC-3, AC-10, AC-12, AC-13, AC-14).

Группа: долгоживущий
Красен до реализации: guard раздела «Заменяемые тесты» не знает — SPEC с негодной строкой раздела проходит CLI с кодом 0 и «GUARD: ок», `guard.REPLACED_TESTS_SECTION` нет; `spec_audit.signals` сигнала «а) раздел «Заменяемые тесты» непуст» не выдаёт; `_ban_findings` шаблонную таблицу `it.each`…`` не узнаёт (за `.each` идёт не `(`), `suite` с меткой в начале имени не запрещён; `_test_calls` имя теста шаблонной таблицы не читает — критерий без теста. Зелены с рождения методы прежнего поведения: SPEC без раздела, с пустым разделом и с заглушкой не получает ошибок (AC-3), `describe` с меткой — находка, как прежде (контроль AC-13).

Свойства — чистые функции и CLI без песочницы: `scripts/guard.py <SPEC.md>`
отдельным процессом из корня репозитория (тот вызов, которым analyst
проверяет SPEC), `guard.check_content`, `project_profile.parse_test_id`,
`spec_audit.signals`, `guard.plank_ban_errors`, `guard.scan_ac_content`,
`guard.plank_test_names`. Правило планки — `guard.PlankRule` с одним
компонентом с меткой `AC-<n>: `.

Имена компонентов, путей, тестов, номера критериев и числа — из `random`;
зерно печатается и входит в текст каждого провала.
"""
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from orchestrator import project_profile
from orchestrator.advance_gates import spec_audit
from scripts import guard

REPO = Path(__file__).resolve().parent.parent
GUARD = REPO / "scripts" / "guard.py"
OK_OUTPUT = "GUARD: ок (1 файлов)\n"
SECTION = "Заменяемые тесты"
LETTERS = "abcdefghijkmnpqrstuvwxyz"
CRITERIA = 5
BEHAVIOR_SIGNAL = "а) раздел «Меняемое поведение» непуст"
REPLACED_SIGNAL = "а) раздел «Заменяемые тесты» непуст"

SPEC_TEXT = """---
task: T001
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: tests/
budget_usd: 30
---

# SPEC: фикстура раздела заменяемых тестов

## Контекст

Фикстура.

## Требования

1. Требование фикстуры.

## Критерии приёмки

{criteria}
{behavior}{section}
## Не входит

Ничего.
"""


def criteria_text() -> str:
    return "\n\n".join(f"AC-{n}. Фикстурный критерий номер {n}."
                       for n in range(1, CRITERIA + 1))


def spec(section_lines=None, behavior=None, raw_body=None) -> str:
    """SPEC фикстуры: `section_lines` — строки раздела «Заменяемые тесты»
    (`None` — раздела нет), `raw_body` — тело раздела как есть,
    `behavior` — строки раздела «Меняемое поведение»."""
    body = ""
    if raw_body is not None:
        body = f"\n## {SECTION}\n{raw_body}\n"
    elif section_lines is not None:
        body = f"\n## {SECTION}\n\n" + "\n".join(section_lines) + "\n"
    change = ""
    if behavior is not None:
        change = ("\n## Меняемое поведение\n\nСмены фикстуры.\n\n"
                  + "\n".join(behavior) + "\n")
    return SPEC_TEXT.format(criteria=criteria_text(), behavior=change,
                            section=body)


def labelled_rule(component: str) -> guard.PlankRule:
    return guard.PlankRule(components=(guard.PlankComponent(
        component, ("src/**/*.test.jsx",), guard.LABEL_AC,
        guard.MARKER_SLASH),))


class SeededTest(unittest.TestCase):

    def setUp(self):
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used: set = set()

    def word(self, size: int = 6) -> str:
        while True:
            text = "".join(self.rng.choice(LETTERS) for _ in range(size))
            if text not in self.used:
                self.used.add(text)
                return text

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def make_id(self) -> str:
        """Годный идентификатор Vitest: пробелы и « > » в полном имени."""
        return project_profile.test_id(
            f"c{self.word(4)}", f"src/{self.word(4)}/{self.word()}.test.jsx",
            f"{self.word()} > {self.word(4)} {self.word(5)}")

    def line(self, test_id: str, n: int | None = None,
             reason: str | None = None) -> str:
        number = self.rng.randint(1, CRITERIA) if n is None else n
        why = f"замена по требованию {self.word()}" if reason is None else reason
        return f"- `{test_id}` → AC-{number}: {why}"


# ---------------------------------------------------------------- AC-1 (CLI)

class Ac1SectionFormCliTest(SeededTest):

    def guard_cli(self, text: str) -> tuple:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "SPEC.md"
            path.write_text(text, encoding="utf-8")
            res = subprocess.run([sys.executable, str(GUARD), str(path)],
                                 cwd=REPO, capture_output=True, text=True,
                                 timeout=120)
        return res.returncode, res.stdout + res.stderr

    def test_ac1_valid_section_passes_cli(self):
        """Годный раздел — строки пунктов вперемешку с пустыми строками — CLI отвечает «GUARD: ок» с кодом 0.

        Сценарий: SPEC с разделом «## Заменяемые тесты», где каждый пункт —
        `` - `<компонент>:<путь>::<имя>` → AC-<n>: <причина> `` с номером из
        «Критерии приёмки», между пунктами — пустые строки. Вызов
        `scripts/guard.py <SPEC.md>`.

        Ловит мутацию: пустая строка непустого раздела считается строкой
        без «- » — код 1; полное имя с пробелами и « > » не принимается
        разбором идентификатора — код 1.
        """
        code, out = self.guard_cli(spec([self.line(self.make_id()), "",
                                         self.line(self.make_id())]))
        self.assertEqual((code, out), (0, OK_OUTPUT), self.note(out))

    def test_ac1_each_violation_named_by_cli(self):
        """Каждое нарушение формы раздела — ненулевой код CLI, ошибка называет свою строку, а годные соседние строки не названы.

        Случаи: идентификатор не в обратных кавычках; идентификатор не той
        формы (без `::`); нет `→ AC-<n>:`; критерия `AC-<n>` нет в
        «Критерии приёмки»; пустая причина; повтор идентификатора; строка
        непустого раздела начинается не с «- ». Строка с нарушением несёт
        случайный идентификатор; рядом — годная строка.

        Ловит мутацию: строка без обратных кавычек читается как свободный
        текст — код 0; номер критерия не сверяется с разделом «Критерии
        приёмки» — код 0; пустая причина принимается — код 0; повтор
        идентификатора не отслеживается — код 0; строка «* …» непустого
        раздела молча пропускается, как свободный текст «Меняемое
        поведение», — код 0; ошибка называет не строку, а раздел целиком —
        годный соседний идентификатор назван в выводе.
        """
        for case in ("без кавычек", "не та форма", "нет стрелки",
                     "нет критерия", "пустая причина", "повтор",
                     "не с «- »"):
            with self.subTest(case=case, seed=self.seed):
                good = self.make_id()
                bad = self.make_id()
                n = self.rng.randint(1, CRITERIA)
                why = f"причина {self.word()}"
                named = bad
                lines = [self.line(good)]
                if case == "без кавычек":
                    lines.append(f"- {bad} → AC-{n}: {why}")
                elif case == "не та форма":
                    named = bad.split("::", 1)[0]
                    lines.append(f"- `{named}` → AC-{n}: {why}")
                elif case == "нет стрелки":
                    lines.append(f"- `{bad}` {why}")
                elif case == "нет критерия":
                    lines.append(self.line(bad, CRITERIA + self.rng.randint(1, 40)))
                elif case == "пустая причина":
                    lines.append(f"- `{bad}` → AC-{n}:")
                elif case == "повтор":
                    lines += [self.line(bad), self.line(bad)]
                else:
                    lines.append(f"* `{bad}` → AC-{n}: {why}")
                self.rng.shuffle(lines)
                code, out = self.guard_cli(spec(lines))
                context = self.note(f"раздел:\n{chr(10).join(lines)}\nвывод:\n{out}")
                self.assertNotEqual(code, 0, context)
                self.assertIn(named, out, context)
                self.assertNotIn(good, out, context)


# ---------------------------------------------------------------- AC-2

class Ac2SameParseTest(SeededTest):

    def examples(self) -> list:
        """Годные и негодные идентификаторы: постоянный набор и случайные."""
        comp, path, name = (f"c{self.word(4)}",
                            f"src/{self.word(4)}/{self.word()}.test.jsx",
                            f"{self.word()} > {self.word(5)}")
        fixed = [f"{comp}:{path}::{name}", f"{comp}:{path}::{name}#3",
                 f"{comp}:{path}::{self.word()}::{self.word()}",
                 f"{comp}:{path}::{name}#", f"{comp}:{path}::#7",
                 f"{comp}:{path}", f":{path}::{name}", f"{comp}:::{name}",
                 f"{comp}:{path}::", f"{comp}{path}::{name}",
                 f"{comp}::{name}", f"{comp}:{path}:{name}"]
        pieces = [comp, ":", path, "::", name, "#", "2", ":", " "]
        randoms = []
        for _ in range(12):
            parts = [self.rng.choice(pieces)
                     for _ in range(self.rng.randint(2, 6))]
            text = "".join(parts).strip()
            if text and "`" not in text:
                randoms.append(text)
        seen, out = set(), []
        for text in fixed + randoms:
            if text not in seen:
                seen.add(text)
                out.append(text)
        return out

    def test_ac2_guard_and_parse_test_id_agree(self):
        """На одном наборе идентификаторов guard и `project_profile.parse_test_id` дают одинаковый исход: принят или отвергнут.

        Сценарий: для каждого примера — SPEC с единственным пунктом
        раздела `` - `<пример>` → AC-1: <причина> ``; guard
        (`check_content`) «принял» — ошибок нет, «отверг» — ошибка
        называет пример; `parse_test_id` «принял» — вернул кортеж,
        «отверг» — `ValueError`. Набор: годные (с `#<n>`, с `::` внутри
        имени) и негодные (без `::`, пустой компонент, путь или имя) плюс
        случайные склейки частей. Контроль: в наборе есть и принятые, и
        отвергнутые `parse_test_id`.

        Ловит мутацию: guard сверяет идентификатор своим регулярным
        выражением, требующим `.test.` в пути или запрещающим `#` в имени, —
        исходы расходятся; guard не проверяет пустой путь — `c:::имя`
        принят guard и отвергнут `parse_test_id`.
        """
        accepted_by_parse = set()
        for example in self.examples():
            with self.subTest(example=example, seed=self.seed):
                try:
                    project_profile.parse_test_id(example)
                    parsed = True
                except ValueError:
                    parsed = False
                if parsed:
                    accepted_by_parse.add(example)
                text = spec([f"- `{example}` → AC-1: причина {self.word()}"])
                errors = guard.check_content("SPEC.md", text)
                context = self.note(f"пример {example!r}: ошибки {errors}")
                if parsed:
                    self.assertEqual(errors, [], context)
                else:
                    self.assertTrue(any(example in e for e in errors), context)
        self.assertTrue(accepted_by_parse, self.note("нет принятых примеров"))


# ---------------------------------------------------------------- AC-3

class Ac3NoNewErrorsTest(SeededTest):

    def test_ac3_absent_empty_or_placeholder_section_no_errors(self):
        """SPEC без раздела «Заменяемые тесты», с пустым разделом или с шаблонной заглушкой `<…>` не получает от guard ни одной ошибки.

        Сценарий: один и тот же SPEC фикстуры (годный во всём остальном)
        без раздела, с заголовком раздела без тела, с телом из пробелов и
        пустых строк и с телом-заглушкой `<…>` (текст заглушки — со строкой
        пункта внутри угловых скобок). `guard.check_content` — пустой
        список в каждом случае.

        Ловит мутацию: заглушка шаблона разбирается как строка пункта
        (не начинается с «- ») — ошибка; пустой раздел считается
        нарушением «нет ни одного пункта» — ошибка.
        """
        placeholder = (f"<- `<компонент>:<путь>::<имя>` → AC-<n>: <причина> "
                       f"{self.word()}>")
        for case, text in (("нет раздела", spec()),
                           ("пустой", spec(raw_body="")),
                           ("пробелы", spec(raw_body="\n   \n\n")),
                           ("заглушка", spec(raw_body=f"\n{placeholder}\n"))):
            with self.subTest(case=case, seed=self.seed):
                errors = guard.check_content("SPEC.md", text)
                self.assertEqual(errors, [], self.note(f"{case}: {errors}"))


# ---------------------------------------------------------------- AC-10

class Ac10AuditSignalTest(SeededTest):

    def behavior_line(self) -> str:
        return (f"- `tests/test_{self.word()}.py::{self.word().capitalize()}Test"
                f"::test_{self.word()}`: `1` → `2` (требование 1)")

    def test_ac10_signal_after_behavior_signal(self):
        """Непустой раздел «Заменяемые тесты» даёт сигнал аудита сразу после сигнала «Меняемое поведение»; заглушка тоже его даёт.

        Сценарий: `spec_audit.signals` (а) SPEC с непустыми разделами
        «Меняемое поведение» и «Заменяемые тесты» — новый сигнал стоит
        следующим за «а) раздел «Меняемое поведение» непуст»; (б) SPEC,
        где раздел «Заменяемые тесты» несёт одну заглушку `<…>`, — сигнал
        есть; (в) тот же SPEC без раздела — список сигналов равен списку
        (а) без нового сигнала, порядок прежний.

        Ловит мутацию: сигнал добавлен в конец списка, а не сразу после
        «Меняемое поведение», — индекс не тот; сигнал считает заглушку
        пустым разделом (правило формы, а не `strip()`) — (б) без сигнала;
        сигнал срабатывает без раздела — (в) несёт лишнюю строку.
        """
        lines = [self.line(self.make_id())]
        meta = {"zones": f"lib{self.word()}/"}
        both = spec_audit.signals(spec(lines, behavior=[self.behavior_line()]),
                                  meta, "", [])
        context = self.note(f"сигналы: {both}")
        self.assertIn(BEHAVIOR_SIGNAL, both, context)
        self.assertIn(REPLACED_SIGNAL, both, context)
        self.assertEqual(both.index(REPLACED_SIGNAL),
                         both.index(BEHAVIOR_SIGNAL) + 1, context)
        placeholder = spec_audit.signals(
            spec(raw_body=f"\n<пункт {self.word()}>\n"), meta, "", [])
        self.assertIn(REPLACED_SIGNAL, placeholder,
                      self.note(f"заглушка: {placeholder}"))
        behavior = [self.behavior_line()]
        with_section = spec_audit.signals(spec(lines, behavior=behavior),
                                          meta, "", [])
        without = spec_audit.signals(spec(None, behavior=behavior), meta, "", [])
        self.assertEqual(without,
                         [s for s in with_section if s != REPLACED_SIGNAL],
                         self.note(f"с разделом {with_section}, без {without}"))


# ---------------------------------------------------------------- AC-12..14

class BanSourcesTest(SeededTest):

    def setUp(self):
        super().setUp()
        self.comp = f"c{self.word(4)}"
        self.rule = labelled_rule(self.comp)
        self.label = f"acceptance_tests/a{self.word()}.test.jsx"

    def table_call(self, tail: str = "", name: str | None = None) -> str:
        """Файл с меткой: шаблонная таблица с подстановками `${…}`,
        вызванная `('<имя>', fn<tail>)`."""
        a = self.rng.randint(1, 50)
        name = name or f"AC-1: сумма {self.word()} $a"
        return ("// Группа: разовый\n"
                f"// Красен до реализации: фикстура {self.word()}.\n"
                "import { expect, it } from 'vitest';\n\n"
                "it.each`\n"
                "  a      | b\n"
                f"  ${{{a}}} | ${{{a + 1}}}\n"
                f"`('{name}', ({{ a, b }}) => {{\n"
                "  expect(a + 1).toBe(b);\n"
                f"}}{tail});\n")

    def errors(self, text: str) -> list:
        return guard.plank_ban_errors([(self.label, text)], self.rule)


class Ac12TemplateTableBansTest(BanSourcesTest):

    def test_ac12_template_table_number_and_timeout_object_found(self):
        """Шаблонная таблица `it.each`…`` с `5000` или `{ timeout: 1 }` в первой паре скобок после литерала — находка запрета; без них — находок нет.

        Сценарий: файл с меткой, `it.each` с многострочной таблицей с
        подстановками `${…}`, вызов `('AC-1: …', fn, <аргумент>)`:
        числовой литерал `5000`, случайное число и объект
        `{ timeout: 1 }`. Каждая — ошибка `plank_ban_errors` «<файл>:<строка>:
        … — запрещено в тексте планки». Контроль: тот же вызов без третьего
        аргумента — ошибок нет.

        Ловит мутацию: цепочка `.each` узнаётся только со скобкой `(` после
        неё — таблица-литерал пропущена, находок нет; аргументами считается
        первая пара скобок после `.each` в маске (её нет) — находок нет;
        ключ объекта не сверяется с `retry`/`timeout` у таблицы — объект
        без находки.
        """
        number = self.rng.randint(10, 99999)
        for case, tail in (("5000", ", 5000"), ("число", f", {number}"),
                           ("timeout", ", { timeout: 1 }")):
            with self.subTest(case=case, seed=self.seed):
                text = self.table_call(tail)
                errors = self.errors(text)
                context = self.note(f"{case}: {errors}\n{text}")
                self.assertTrue(errors, context)
                self.assertTrue(all(e.startswith(f"{self.label}:") and
                                    guard.PLANK_BAN_TAIL in e for e in errors),
                                context)
        clean = self.table_call()
        self.assertEqual(self.errors(clean), [], self.note(clean))


class Ac13SuiteLabelTest(BanSourcesTest):

    def test_ac13_suite_with_label_found_like_describe(self):
        """`suite('AC-<n>: …')` даёт находку запрета, как `describe('AC-<n>: …')`; `suite` без метки в начале — нет.

        Сценарий: файл с меткой, где группа — `describe` либо `suite` с
        литералом имени `'AC-<n>: …'` (номер и текст из зерна), внутри —
        годный `it('AC-<n>: …')`. Обе группы — ошибка `plank_ban_errors` на
        строке группы. Контроль: `suite('группа …')` без метки — ошибок нет.

        Ловит мутацию: запрет метки в начале имени проверяет только
        `m.group(1) == "describe"` — `suite` проходит без находки; запрет
        применён к любому имени `suite` — контроль с находкой.
        """
        n = self.rng.randint(1, 30)
        for head in ("describe", "suite"):
            with self.subTest(head=head, seed=self.seed):
                text = ("// Группа: разовый\n"
                        f"// Красен до реализации: фикстура {self.word()}.\n"
                        f"import {{ {head}, expect, it }} from 'vitest';\n\n"
                        f"{head}('AC-{n}: группа {self.word()}', () => {{\n"
                        f"  it('AC-{n}: кнопка {self.word()}', () => {{ "
                        f"expect(1).toBe(1); }});\n}});\n")
                errors = self.errors(text)
                context = self.note(f"{head}: {errors}\n{text}")
                self.assertTrue(any(e.startswith(f"{self.label}:5:")
                                    for e in errors), context)
        plain = ("// Группа: разовый\n"
                 f"// Красен до реализации: фикстура {self.word()}.\n"
                 "import { suite, expect, it } from 'vitest';\n\n"
                 f"suite('группа {self.word()}', () => {{\n"
                 f"  it('AC-{n}: кнопка {self.word()}', () => {{ "
                 f"expect(1).toBe(1); }});\n}});\n")
        self.assertEqual(self.errors(plain), [], self.note(plain))


class Ac14TemplateTableNameTest(BanSourcesTest):

    def test_ac14_template_table_name_covers_criterion(self):
        """Имя теста шаблонной таблицы `it.each`…`('AC-<n>: …', …)` покрывает критерий так же, как имя `.each(…)(…)`.

        Сценарий: файл с меткой с одним вызовом — шаблонная таблица с
        подстановками либо `.each([...])`; имя `'AC-<n>: …'` (номер из
        зерна). `guard.scan_ac_content([(файл, текст)], правило)` относит
        `AC-<n>` к покрытым тестом; `guard.plank_test_names` несёт имя.

        Ловит мутацию: голова вызова ищет `.each(` и после таблицы-литерала
        не читает имя — `AC-<n>` не покрыт, `plank_test_names` пуст;
        литерал таблицы принимается за имя теста — имя другое, критерий не
        покрыт.
        """
        n = self.rng.randint(1, 30)
        name = f"AC-{n}: сумма {self.word()} $a"
        table = self.table_call(name=name)
        array = ("// Группа: разовый\n"
                 f"// Красен до реализации: фикстура {self.word()}.\n"
                 "import { expect, it } from 'vitest';\n\n"
                 "it.each([[1, 2], [3, 4]])"
                 f"('{name}', (a, b) => {{ expect(a + 1).toBe(b); }});\n")
        for case, text in (("шаблонная таблица", table), (".each(…)", array)):
            with self.subTest(case=case, seed=self.seed):
                tested, _markers = guard.scan_ac_content([(self.label, text)],
                                                         rule=self.rule)
                context = self.note(f"{case}: покрыты {tested}\n{text}")
                self.assertIn(n, {int(str(x).removeprefix("AC-"))
                                  for x in tested}, context)
                self.assertIn(name, guard.plank_test_names(text), context)


if __name__ == "__main__":
    unittest.main()
