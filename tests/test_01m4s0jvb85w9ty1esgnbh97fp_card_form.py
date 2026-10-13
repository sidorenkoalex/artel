"""Форма файла карточек знаний: разбор, отказы формы, повторы, пределы.

Свойство чистой функции `orchestrator.knowledge_cards.check_text` — без
песочницы и без чтения файлов: текст файла карточек собирается в тесте,
ответ — кортеж карточек `Card` либо отказ `Refusal` с кодом причины из
закрытого перечня `REFUSAL_CODES`, файлом, ключом, полем и номером строки.
Тексты значений полей, ключи карточек, имя файла и распределение длины
по полям — случайные при каждом запуске; зерно печатается и входит в
текст провала.

Группа: долгоживущий
Красен до реализации: модуля orchestrator/knowledge_cards.py и констант config.KNOWLEDGE_CARD_* ещё нет — импорт модуля падает, все тесты файла красны.
"""
import random
import re
import unittest
from unittest import mock

from orchestrator import config
try:
    from orchestrator import knowledge_cards as kc
except ImportError as exc:  # до реализации модуля нет: сбор проходит, тесты красны
    kc = None
    KC_IMPORT_ERROR = exc


def setUpModule() -> None:
    if kc is None:
        raise KC_IMPORT_ERROR

# Образец файла карточек из ТЗ задачи (карточка `merge-lock-order`).
TZ_SAMPLE = """\
cards:
  merge-lock-order:
    where: [orchestrator/merge_lock.py, orchestrator/fsm_merge_gate.py::merge_gate, orchestrator/advance_gates/*.py]
    rule: "Лок мержа берётся до чтения головы main: иначе гонка двух approve"
    why: инцидент двух одновременных мержей — второй перетёр первый
    check: "tests/test_invariants.py::MergeOnlyFromMergeGateTest"
    example: "with merge_lock.held(conn): head = gitcmd.rev_parse('origin/main')"
    incidents: [01M290PS4Z, T043]
"""

CYRILLIC = "абвгдежзиклмнопрстуфхцчшэюя"
LATIN = "abcdefghijklmnopqrstuvwxyz"
KEY_TAIL = LATIN + "0123456789-"

EXPECTED_CODES = {
    "GIT_NO_ANSWER": "git не ответил",
    "FILE_UNREADABLE": "файл не прочитан",
    "FILE_UNPARSED": "файл не разобран",
    "KEY_FORM": "ключ не по форме",
    "FIELD_FORM": "поле не по форме",
    "DUPLICATE": "повтор",
    "SIZE_LIMIT": "предел размера",
    "COUNT_LIMIT": "предел числа карточек",
}


class Inputs:
    """Случайные входы одного теста: ключи, тексты значений, имя файла."""

    def __init__(self):
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.used = set()

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def letters(self, n: int) -> str:
        """Слово из кириллицы длиной `n`: не число, не логическое, не null."""
        return "".join(self.rng.choice(CYRILLIC) for _ in range(n))

    def text(self, n: int) -> str:
        """Значение ровно из `n` символов: кириллица с одиночными пробелами
        внутри, без пробела по краям, без кавычек и `#`."""
        chars = [self.rng.choice(CYRILLIC) for _ in range(n)]
        for i in range(1, n - 1):
            if chars[i - 1] != " " and self.rng.random() < 0.15:
                chars[i] = " "
        return "".join(chars)

    def key(self, length: int | None = None) -> str:
        """Ключ карточки по форме `[a-z0-9][a-z0-9-]{0,47}`, не повторяющийся
        в пределах теста."""
        while True:
            n = length or self.rng.randrange(3, 20)
            first = self.rng.choice(LATIN + "0123456789")
            value = first + "".join(self.rng.choice(KEY_TAIL)
                                    for _ in range(n - 1))
            if value not in self.used:
                self.used.add(value)
                return value

    def file(self) -> str:
        return f"knowledge/{self.key()}.yaml"

    def path(self) -> str:
        return f"{self.key()}/{self.key()}.py"

    def base_fields(self) -> list:
        return [("where", f"[{self.path()}]"),
                ("rule", self.text(self.rng.randrange(5, 30))),
                ("why", self.text(self.rng.randrange(5, 30)))]


def render(cards: list) -> tuple:
    """Текст файла и номера строк: `(ключ, None)` — строка ключа карточки,
    `(ключ, поле)` — строка поля. Тело карточки — список пар
    `(поле, сырое значение)` либо строка-скаляр (`5`, `~`)."""
    lines = ["cards:"]
    where = {}
    for key, body in cards:
        if isinstance(body, str):
            lines.append(f"  {key}: {body}")
            where[(key, None)] = len(lines)
            continue
        lines.append(f"  {key}:")
        where[(key, None)] = len(lines)
        for name, raw in body:
            lines.append(f"    {name}:" if raw == "" else f"    {name}: {raw}")
            where[(key, name)] = len(lines)
    return "\n".join(lines) + "\n", where


def replaced(fields: list, name: str, raw: str) -> list:
    """Поля карточки с полем `name`, заменённым на `raw` (или добавленным)."""
    out = [(n, v) for n, v in fields if n != name]
    return out + [(name, raw)]


def without(fields: list, name: str) -> list:
    return [(n, v) for n, v in fields if n != name]


# Случаи требования 2 уровня поля: (подпись, поле, сырое значение).
FIELD_CASES = (
    ("rule пустая строка", "rule", '""'),
    ("rule без значения", "rule", ""),
    ("why из одних пробелов", "why", '"   "'),
    ("rule логическое значение", "rule", "true"),
    ("check число", "check", "12"),
    ("where строка", "where", "x.py"),
    ("where пустой список", "where", "[]"),
    ("where число в списке", "where", "[22]"),
    ("incidents не список", "incidents", "x"),
    ("число в incidents", "incidents", "[T1, 22]"),
    ("элемент where пуст", "where", "[a/b.py, ]"),
    ("элемент where абсолютный", "where", "[/a.py]"),
    ("элемент where с ..", "where", "[a/../b.py]"),
    ("элемент where с префиксом ./", "where", "[./a.py]"),
    ("* в пути элемента путь::символ", "where", "[a/*.py::f]"),
    ("символ не по форме", "where", "[a.py::1f]"),
    ("двойная кавычка внутри rule", "rule", 'сказал "да" сразу'),
    ("двойная кавычка внутри example", "example", 'a"b'),
)


def field_level_cases(inp: Inputs) -> list:
    """(подпись, текст, ключ, поле, строка) — отказы «поле не по форме»
    у карточки, стоящей среди других, верных."""
    out = []
    for label, name, raw in FIELD_CASES:
        bad = inp.key()
        cards = [(inp.key(), inp.base_fields()) for _ in range(inp.rng.randrange(0, 3))]
        cards.insert(inp.rng.randrange(len(cards) + 1),
                     (bad, replaced(inp.base_fields(), name, raw)))
        text, where = render(cards)
        out.append((label, text, bad, name, where[(bad, name)]))
    bad = inp.key()
    fields = inp.base_fields() + [("owner", inp.letters(5))]
    text, where = render([(bad, fields)])
    out.append(("неизвестное поле", text, bad, "owner", where[(bad, "owner")]))
    return out


def missing_field_cases(inp: Inputs) -> list:
    """(подпись, текст, ключ, поле) — нет обязательного поля."""
    out = []
    for name in ("rule", "where", "why"):
        bad = inp.key()
        text, _ = render([(inp.key(), inp.base_fields()),
                          (bad, without(inp.base_fields(), name))])
        out.append((f"нет {name}", text, bad, name))
    return out


def card_level_cases(inp: Inputs) -> list:
    """(подпись, текст, код, ключ, строка) — значение карточки не
    отображение и ключ не по форме."""
    out = []
    for raw in ("5", "~"):
        bad = inp.key()
        text, where = render([(inp.key(), inp.base_fields()), (bad, raw)])
        out.append((f"карточка «{raw}»", text, kc.FIELD_FORM, bad,
                    where[(bad, None)]))
    for bad in ("Bad_" + inp.rng.choice(LATIN) + "key", "-" + inp.key(),
                inp.key() + "_x", inp.key(49)):
        text, where = render([(inp.key(), inp.base_fields()),
                              (bad, inp.base_fields())])
        out.append((f"ключ {bad!r}", text, kc.KEY_FORM, bad,
                    where[(bad, None)]))
    return out


def file_level_cases(inp: Inputs) -> list:
    """(подпись, текст, код) — отказы уровня файла: ключа и поля нет."""
    unparsed, _ = render([(inp.key(), replaced(inp.base_fields(), "where",
                                               '["a.py"]'))])
    return [
        ("файл не разобран", unparsed, kc.FILE_UNPARSED),
        ("пустой файл — нет cards", "", kc.FIELD_FORM),
        ("только комментарий — нет cards", "# пусто\n", kc.FIELD_FORM),
        ("cards: {}", "cards: {}\n", kc.FIELD_FORM),
    ]


def section_cases(inp: Inputs) -> list:
    """(подпись, текст) — «неизвестный раздел» требования 3."""
    body, _ = render([(inp.key(), inp.base_fields())])
    more, _ = render([(inp.key(), inp.base_fields())])
    other = inp.key().replace("-", "x")
    return [
        ("раздел до cards", f"{other}: {inp.letters(4)}\n{body}"),
        ("раздел после cards", f"{body}{other}:\n  x: {inp.letters(4)}\n"),
        ("ключ верхнего уровня после cards со значением",
         f"{body}{other}: {inp.letters(3)}\n"),
        ("повтор cards:", body + more),
    ]


def duplicate_cases(inp: Inputs) -> list:
    """(подпись, текст, ключ, поле, строки повтора) — повтор ключа и поля,
    в том числе с пробелом перед двоеточием."""
    out = []
    for label, first, second in (("ключ", "  {k}:", "  {k}:"),
                                 ("ключ «a :»", "  {k} :", "  {k}:"),
                                 ("ключ «a:» затем «a :»", "  {k}:", "  {k} :")):
        key = inp.key()
        lines = ["cards:", first.format(k=key)]
        lines += [f"    {n}: {v}" for n, v in inp.base_fields()]
        lines.append(f"  {inp.key()}:")
        lines += [f"    {n}: {v}" for n, v in inp.base_fields()]
        rows = (2, len(lines) + 1)
        lines.append(second.format(k=key))
        lines += [f"    {n}: {v}" for n, v in inp.base_fields()]
        out.append((f"повтор {label}", "\n".join(lines) + "\n", key, None, rows))
    for label, first, second in (("поле", "    rule: {v}", "    rule: {v}"),
                                 ("поле «rule :»", "    rule : {v}",
                                  "    rule: {v}")):
        key = inp.key()
        fields = inp.base_fields()
        lines = ["cards:", f"  {key}:"] + [f"    {n}: {v}" for n, v in fields]
        rows = (lines.index(f"    rule: {dict(fields)['rule']}") + 1,
                len(lines) + 1)
        lines[rows[0] - 1] = first.format(v=dict(fields)["rule"])
        lines.append(second.format(v=inp.text(8)))
        out.append((f"повтор {label}", "\n".join(lines) + "\n", key, "rule",
                    rows))
    return out


def indent_cases(inp: Inputs) -> list:
    """(подпись, текст, строка) — карточки на отступе 3, поля на отступе 5."""
    out = []
    for dup in (False, True):
        key = inp.key()
        lines = ["cards:", f"   {key}:"]
        lines += [f"     {n}: {v}" for n, v in inp.base_fields()]
        lines.append(f"   {key if dup else inp.key()}:")
        lines += [f"     {n}: {v}" for n, v in inp.base_fields()]
        out.append(("отступ 3/5" + (" с повтором ключа" if dup else ""),
                    "\n".join(lines) + "\n", 2))
    return out


def card_texts(inp: Inputs, lengths: list) -> list:
    """Значения rule, why, check, example и двух элементов incidents с
    заданными длинами (все длины ≥ 1)."""
    return [inp.text(n) if i < 4 else inp.letters(n)
            for i, n in enumerate(lengths)]


def split_total(inp: Inputs, total: int, parts: int = 6) -> list:
    """Случайное разбиение `total` на `parts` положительных слагаемых."""
    cuts = sorted(inp.rng.sample(range(1, total), parts - 1))
    return [b - a for a, b in zip([0] + cuts, cuts + [total])]


def sized_card(inp: Inputs, key: str, total: int) -> str:
    """Файл из одной карточки с суммарной длиной текстовых полей `total`."""
    rule, why, check, example, inc1, inc2 = card_texts(
        inp, split_total(inp, total))
    text, _ = render([(key, [("where", f"[{inp.path()}]"), ("rule", rule),
                             ("why", why), ("check", check),
                             ("example", example),
                             ("incidents", f"[{inc1}, {inc2}]")])])
    return text


def many_cards(inp: Inputs, count: int) -> str:
    text, _ = render([(inp.key(), [("where", "[a.py]"), ("rule", "п"),
                                   ("why", "ч")]) for _ in range(count)])
    return text


class CardFormTest(unittest.TestCase):
    """Общее: сверка отказа с ожидаемыми кодом, файлом, ключом, полем."""

    def setUp(self):
        self.inp = Inputs()

    def refusal(self, text: str, label: str, file: str | None = None):
        file = file or self.inp.file()
        result = kc.check_text(text, file, kc.SYSTEM)
        self.assertIsInstance(result, kc.Refusal, self.inp.msg(
            f"{label}: ожидался отказ, получено {result!r}\n{text}"))
        self.assertEqual(result.file, file, self.inp.msg(label))
        self.assertIsInstance(result.detail, str, self.inp.msg(label))
        self.assertTrue(result.detail.strip(), self.inp.msg(label))
        return result

    def accepted(self, text: str, label: str, kind: str = "") -> tuple:
        result = kc.check_text(text, self.inp.file(), kind or kc.SYSTEM)
        self.assertNotIsInstance(result, kc.Refusal, self.inp.msg(
            f"{label}: отказ {result!r}\n{text}"))
        self.assertIsInstance(result, tuple, self.inp.msg(label))
        return result


class SampleAndKeyFormTest(CardFormTest):

    def test_ac1_tz_sample_parses_into_card_with_all_fields(self):
        """Образец карточки `merge-lock-order` из ТЗ разбирается без отказа.

        Сценарий: текст образца ТЗ подаётся `check_text` как проектный вид —
        ответ одна карточка с ключом `merge-lock-order`, тремя элементами
        `where` (маска, `путь::символ`, маска со `*`), текстами `rule`,
        `why`, `check`, `example` и инцидентами `01M290PS4Z`, `T043`;
        `kind` карточки — переданный вид.

        Ловит мутацию: элемент `путь::символ` проверяется как маска (`::`
        запрещён) либо `incidents` берётся как строка — образец ТЗ
        отвергается или поля карточки расходятся с образцом.
        """
        cards = self.accepted(TZ_SAMPLE, "образец ТЗ", kind=kc.PROJECT)
        self.assertEqual(len(cards), 1)
        card = cards[0]
        self.assertEqual(card.key, "merge-lock-order")
        self.assertEqual(card.kind, kc.PROJECT)
        self.assertEqual(card.where, (
            "orchestrator/merge_lock.py",
            "orchestrator/fsm_merge_gate.py::merge_gate",
            "orchestrator/advance_gates/*.py"))
        self.assertEqual(card.rule, "Лок мержа берётся до чтения головы main: "
                                    "иначе гонка двух approve")
        self.assertEqual(card.why, "инцидент двух одновременных мержей — "
                                   "второй перетёр первый")
        self.assertEqual(card.check,
                         "tests/test_invariants.py::MergeOnlyFromMergeGateTest")
        self.assertTrue(card.example.startswith("with merge_lock.held(conn)"))
        self.assertEqual(card.incidents, ("01M290PS4Z", "T043"))

    def test_ac1_empty_cards_section_gives_zero_cards(self):
        """Пустой раздел `cards:` — ноль карточек, не отказ.

        Сценарий: файл из одной строки `cards:` (с комментарием и пустыми
        строками вокруг или без них) — ответ пустой кортеж.

        Ловит мутацию: значение `None` раздела `cards:` трактуется как «нет
        раздела `cards`» — пустой файл карточек отвергается отказом.
        """
        for text in ("cards:\n", "# карточки\n\ncards:\n\n",
                     "cards:   # пока пусто\n"):
            with self.subTest(text=text):
                self.assertEqual(self.accepted(text, repr(text)), ())

    def test_ac1_key_length_48_accepted_49_refused(self):
        """Ключ из 48 символов формы принят, из 49 — отказ «ключ не по форме».

        Сценарий: случайный ключ длиной 48 и случайный длиной 49 (первый
        символ — буква или цифра, далее `[a-z0-9-]`) в карточке с верными
        полями.

        Ловит мутацию: квантификатор `{0,47}` заменён на `{0,48}` (или
        длина не ограничена) — ключ из 49 символов принят; либо `{0,46}` —
        ключ из 48 отвергнут.
        """
        for _ in range(3):
            ok = self.inp.key(48)
            text, _ = render([(ok, self.inp.base_fields())])
            cards = self.accepted(text, f"ключ {ok}")
            self.assertEqual([c.key for c in cards], [ok], self.inp.msg(ok))
            bad = self.inp.key(49)
            text, where = render([(bad, self.inp.base_fields())])
            refusal = self.refusal(text, f"ключ {bad}")
            self.assertEqual(refusal.code, kc.KEY_FORM, self.inp.msg(bad))
            self.assertEqual(refusal.key, bad, self.inp.msg(bad))

    def test_ac1_sample_passes_and_is_quoted_in_module_docstring(self):
        """`SAMPLE` проходит `check_text`, docstring модуля несёт его
        дословно и пометку о буквах в идентификаторах инцидентов.

        Сценарий: `check_text(SAMPLE, …)` — кортеж хотя бы из одной
        карточки; `SAMPLE` — подстрока `knowledge_cards.__doc__`; в
        docstring рядом со словом «инцидент» сказано про букву.

        Ловит мутацию: образец в docstring правлен отдельно от константы
        `SAMPLE` (или константа несёт число в потоковом списке `incidents`)
        — образец не входит в docstring дословно либо сам отвергается.
        """
        self.assertIsInstance(kc.SAMPLE, str)
        cards = self.accepted(kc.SAMPLE, "SAMPLE")
        self.assertTrue(cards, "SAMPLE не содержит ни одной карточки")
        doc = kc.__doc__ or ""
        self.assertIn(kc.SAMPLE.strip("\n"), doc)
        self.assertRegex(doc, re.compile(r"инцидент[\s\S]{0,300}?букв",
                                         re.IGNORECASE))


class FormRefusalTest(CardFormTest):

    def test_ac2_field_level_refusals_name_file_key_field_line(self):
        """Каждый отказ уровня поля требования 2 — «поле не по форме» с
        файлом, ключом, полем и номером строки поля.

        Сценарий: среди 0–2 верных карточек в случайной позиции стоит
        карточка с одним дефектом: пустой/без значения/из пробелов `rule`
        и `why`, `rule: true`, число в `check`, `where` строкой, пустым
        списком, с числом, с пустым, абсолютным, `..`-, `./`-элементом, `*`
        в пути `путь::символ`, символ не по форме, число в `incidents` и
        `incidents` строкой, двойная кавычка внутри значения, неизвестное
        поле.

        Ловит мутацию: проверка `strip()` у `rule`/`why` снята, тип
        элементов списка не проверяется (`[22]` и число в `incidents`
        проходят), префикс `./` или `*` в `путь::символ` не отвергаются,
        либо номер строки и ключ берутся у первой карточки файла — тест
        красен на принятом тексте или на поле/строке отказа.
        """
        for label, text, key, field, line in field_level_cases(self.inp):
            with self.subTest(case=label):
                refusal = self.refusal(text, label)
                self.assertEqual(refusal.code, kc.FIELD_FORM,
                                 self.inp.msg(f"{label}: {refusal!r}"))
                self.assertEqual(refusal.key, key, self.inp.msg(label))
                self.assertEqual(refusal.field, field, self.inp.msg(label))
                self.assertEqual(refusal.line, line,
                                 self.inp.msg(f"{label}: {refusal!r}\n{text}"))

    def test_ac2_missing_required_field_names_key_and_field(self):
        """Нет `rule`, нет `where`, нет `why` — «поле не по форме» с ключом
        карточки и именем недостающего поля.

        Ловит мутацию: обязательность проверяется только у `rule`/`why`
        (`where` забыт) либо отсутствие поля читается как пустая строка
        необязательного поля — карточка без `where` принята.
        """
        for label, text, key, field in missing_field_cases(self.inp):
            with self.subTest(case=label):
                refusal = self.refusal(text, label)
                self.assertEqual(refusal.code, kc.FIELD_FORM,
                                 self.inp.msg(f"{label}: {refusal!r}"))
                self.assertEqual(refusal.key, key, self.inp.msg(label))
                self.assertEqual(refusal.field, field, self.inp.msg(label))

    def test_ac2_card_value_and_key_form_refusals(self):
        """`a: 5`, `a: ~` — «поле не по форме»; ключ не по форме (заглавные,
        подчёркивание, ведущий дефис, 49 символов) — «ключ не по форме»;
        оба называют ключ и его строку, поля нет.

        Ловит мутацию: значение карточки `None` (`a: ~`) пропускается как
        пустая карточка, либо ключ сверяется `re.match` без якоря конца —
        `ключ_x` принят.
        """
        for label, text, code, key, line in card_level_cases(self.inp):
            with self.subTest(case=label):
                refusal = self.refusal(text, label)
                self.assertEqual(refusal.code, code,
                                 self.inp.msg(f"{label}: {refusal!r}"))
                self.assertEqual(refusal.key, key, self.inp.msg(label))
                self.assertIsNone(refusal.field, self.inp.msg(label))
                self.assertEqual(refusal.line, line, self.inp.msg(label))

    def test_ac2_file_level_refusals_carry_no_key_or_field(self):
        """Неразобранный файл — «файл не разобран»; нет раздела `cards` и
        `cards: {}` — «поле не по форме»; у этих отказов нет ключа и поля.

        Ловит мутацию: строка `'{}'` от `cards: {}` принимается за ноль
        карточек, либо `YamlError` выходит исключением вместо отказа, либо
        пустой файл даёт ноль карточек.
        """
        for label, text, code in file_level_cases(self.inp):
            with self.subTest(case=label):
                refusal = self.refusal(text, label)
                self.assertEqual(refusal.code, code,
                                 self.inp.msg(f"{label}: {refusal!r}"))
                self.assertIsNone(refusal.key, self.inp.msg(label))
                self.assertIsNone(refusal.field, self.inp.msg(label))

    def test_ac2_dot_mask_and_empty_optional_fields_accepted(self):
        """Без отказа: маска `.github/workflows/*.yml`, `check:` и
        `example:` без значения, `check: ""`, `incidents:` без значения —
        пустые необязательные поля дают `""` и `()`.

        Ловит мутацию: правило «ведущая точка» понято как любая ведущая
        точка (маска `.github/…` отвергнута), либо `None` от `check:`
        считается «значение не строка».
        """
        variants = (
            [("where", "[.github/workflows/*.yml]")],
            [("check", ""), ("example", "")],
            [("check", '""')],
            [("incidents", "")],
            [("check", ""), ("example", ""), ("incidents", ""),
             ("where", f"[.github/workflows/*.yml, {self.inp.path()}]")],
        )
        for extra in variants:
            fields = self.inp.base_fields()
            for name, raw in extra:
                fields = replaced(fields, name, raw)
            key = self.inp.key()
            text, _ = render([(key, fields)])
            with self.subTest(extra=extra):
                cards = self.accepted(text, repr(extra))
                self.assertEqual(len(cards), 1, self.inp.msg(text))
                card = cards[0]
                self.assertEqual(card.key, key)
                self.assertIsInstance(card.check, str)
                self.assertIsInstance(card.example, str)
                self.assertIsInstance(card.incidents, tuple)
                given = dict(extra)
                if "check" in given:
                    self.assertEqual(card.check, "", self.inp.msg(text))
                if "example" in given:
                    self.assertEqual(card.example, "", self.inp.msg(text))
                if "incidents" in given:
                    self.assertEqual(card.incidents, (), self.inp.msg(text))


class SectionAndDuplicateTest(CardFormTest):

    def test_ac3_unknown_top_level_section_and_repeated_cards(self):
        """Ключ верхнего уровня до и после `cards` и повтор `cards:` —
        «поле не по форме» с подробностью «неизвестный раздел».

        Ловит мутацию: проверяется только наличие ключа `cards` в словаре
        `yamlmini` (лишние ключи и повтор, который `yamlmini` затирает,
        проходят молча) — тест красен на принятом тексте.
        """
        for label, text in section_cases(self.inp):
            with self.subTest(case=label):
                refusal = self.refusal(text, label)
                self.assertEqual(refusal.code, kc.FIELD_FORM,
                                 self.inp.msg(f"{label}: {refusal!r}"))
                self.assertIn("неизвестный раздел", refusal.detail,
                              self.inp.msg(label))

    def test_ac3_duplicate_card_key_and_field_refused(self):
        """Повтор ключа карточки (отступ 2) и повтор поля (отступ 4) —
        «повтор», в том числе при пробеле перед двоеточием в одной из
        строк; отказ называет ключ (и поле) и строку одного из повторов.

        Ловит мутацию: построчный проход сравнивает ключ строки без обрезки
        пробелов (`a :` и `a:` — разные) либо проход не заведён вовсе и
        `yamlmini` молча оставляет последнее значение.
        """
        for label, text, key, field, rows in duplicate_cases(self.inp):
            with self.subTest(case=label):
                refusal = self.refusal(text, label)
                self.assertEqual(refusal.code, kc.DUPLICATE,
                                 self.inp.msg(f"{label}: {refusal!r}\n{text}"))
                self.assertEqual(refusal.key, key, self.inp.msg(label))
                if field is not None:
                    self.assertEqual(refusal.field, field, self.inp.msg(label))
                self.assertIn(refusal.line, rows, self.inp.msg(label))

    def test_ac3_indent_3_and_5_refused_with_line(self):
        """Карточки на отступе 3, поля на отступе 5 (и с повтором ключа на
        этом отступе) — «поле не по форме», подробность «отступ», номер
        первой такой строки.

        Ловит мутацию: проход считает строки с отступом, отличным от 2 и 4,
        «не своими» и пропускает их — `yamlmini` принимает отступ 3/5, и
        файл (с затёртым повтором) проходит.
        """
        for label, text, line in indent_cases(self.inp):
            with self.subTest(case=label):
                refusal = self.refusal(text, label)
                self.assertEqual(refusal.code, kc.FIELD_FORM,
                                 self.inp.msg(f"{label}: {refusal!r}"))
                self.assertIn("отступ", refusal.detail, self.inp.msg(label))
                self.assertEqual(refusal.line, line, self.inp.msg(label))

    def test_ac3_blank_and_comment_lines_give_no_false_refusal(self):
        """Пустые строки и строки-комментарии с любым отступом между
        карточками и между полями — ни ложного повтора, ни отказа по
        отступу.

        Сценарий: три карточки; между ними и между их полями вставлены
        случайным образом пустые строки, строки из пробелов и комментарии
        на отступах 0–6, в том числе похожие на ключ (`  # a:`) и на поле
        (`    # rule: x`) соседней карточки.

        Ловит мутацию: проход не пропускает комментарии (комментарий `  #
        a:` считан ключом `#` дважды — повтор; комментарий на отступе 3 —
        отказ «отступ») или пустую строку из пробелов.
        """
        for _ in range(4):
            keys = [self.inp.key() for _ in range(3)]
            fillers = ["", "   ", "# общий", "  # " + keys[0] + ":",
                       "   # отступ три", "    # rule: x", "     # пять",
                       "      #"]
            lines = ["cards:"]
            for key in keys:
                lines.append(self.inp.rng.choice(fillers))
                lines.append(f"  {key}:")
                for name, raw in self.inp.base_fields():
                    if self.inp.rng.random() < 0.6:
                        lines.append(self.inp.rng.choice(fillers))
                    lines.append(f"    {name}: {raw}")
            text = "\n".join(lines) + "\n"
            cards = self.accepted(text, "пустые строки и комментарии")
            self.assertEqual(sorted(c.key for c in cards), sorted(keys),
                             self.inp.msg(text))


class LimitTest(CardFormTest):

    def test_ac4_card_size_limit_from_config(self):
        """Суммарная длина `rule`+`why`+`check`+`example`+элементов
        `incidents`, равная `config.KNOWLEDGE_CARD_MAX_CHARS`, принята, на
        символ больше — «предел размера» с ключом и фактической длиной.

        Сценарий: длина случайно распределена по шести значениям (кириллица
        — символ не равен байту).

        Ловит мутацию: сравнение `>=` вместо `>` (карточка ровно на пределе
        отвергнута), в сумму не входят элементы `incidents` или `example`
        (карточка сверх предела принята), длина считается в байтах UTF-8.
        """
        limit = config.KNOWLEDGE_CARD_MAX_CHARS
        for _ in range(3):
            key = self.inp.key()
            self.accepted(sized_card(self.inp, key, limit), f"ровно {limit}")
            refusal = self.refusal(sized_card(self.inp, key, limit + 1),
                                   f"{limit + 1}")
            self.assertEqual(refusal.code, kc.SIZE_LIMIT,
                             self.inp.msg(repr(refusal)))
            self.assertEqual(refusal.key, key, self.inp.msg(repr(refusal)))
            self.assertIn(str(limit + 1), refusal.detail,
                          self.inp.msg(repr(refusal)))

    def test_ac4_card_count_limit_from_config(self):
        """Файл с `config.KNOWLEDGE_CARD_MAX_PER_FILE` карточками принят, с
        одной сверх — «предел числа карточек» с фактическим числом.

        Ловит мутацию: сравнение `>=` вместо `>` либо предел не проверяется
        вовсе — файл ровно на пределе отвергнут или сверх предела принят.
        """
        limit = config.KNOWLEDGE_CARD_MAX_PER_FILE
        cards = self.accepted(many_cards(self.inp, limit), f"{limit} карточек")
        self.assertEqual(len(cards), limit)
        refusal = self.refusal(many_cards(self.inp, limit + 1),
                               f"{limit + 1} карточек")
        self.assertEqual(refusal.code, kc.COUNT_LIMIT, self.inp.msg(repr(refusal)))
        self.assertIn(str(limit + 1), refusal.detail, self.inp.msg(repr(refusal)))

    def test_ac4_patched_config_constants_move_thresholds(self):
        """Подмена `config.KNOWLEDGE_CARD_MAX_CHARS` и
        `config.KNOWLEDGE_CARD_MAX_PER_FILE` во время теста двигает порог.

        Сценарий: случайные малые пределы (20–60 символов, 2–6 карточек):
        ровно на пределе — принято, на единицу больше — отказ.

        Ловит мутацию: предел взят литералом модуля (`1200`/`80`) или
        скопирован из `config` при импорте — после подмены карточка сверх
        малого предела принята.
        """
        chars = self.inp.rng.randrange(20, 61)
        count = self.inp.rng.randrange(2, 7)
        with mock.patch.object(config, "KNOWLEDGE_CARD_MAX_CHARS", chars), \
                mock.patch.object(config, "KNOWLEDGE_CARD_MAX_PER_FILE", count):
            key = self.inp.key()
            self.accepted(sized_card(self.inp, key, chars), f"ровно {chars}")
            refusal = self.refusal(sized_card(self.inp, key, chars + 1),
                                   f"{chars + 1}")
            self.assertEqual(refusal.code, kc.SIZE_LIMIT,
                             self.inp.msg(repr(refusal)))
            self.accepted(many_cards(self.inp, count), f"{count} карточек")
            refusal = self.refusal(many_cards(self.inp, count + 1),
                                   f"{count + 1} карточек")
            self.assertEqual(refusal.code, kc.COUNT_LIMIT,
                             self.inp.msg(repr(refusal)))


class RefusalCodesTest(CardFormTest):

    def test_ac10_refusal_codes_are_closed_list_of_eight(self):
        """`REFUSAL_CODES` — ровно восемь кодов требования 7, константы
        кодов и исходов несут свои строки; «неизвестный раздел» и «отступ»
        — не коды.

        Ловит мутацию: в перечень добавлен девятый код («неизвестный
        раздел»/«отступ») либо константа кода несёт другой текст — тест
        красен на составе перечня.
        """
        self.assertIsInstance(kc.REFUSAL_CODES, tuple)
        self.assertEqual(len(kc.REFUSAL_CODES), 8)
        self.assertEqual(set(kc.REFUSAL_CODES), set(EXPECTED_CODES.values()))
        for name, value in EXPECTED_CODES.items():
            self.assertEqual(getattr(kc, name), value, name)
        self.assertNotIn("неизвестный раздел", kc.REFUSAL_CODES)
        self.assertNotIn("отступ", kc.REFUSAL_CODES)
        self.assertEqual((kc.CARDS, kc.NOT_SET_UP, kc.REFUSED),
                         ("cards", "not_set_up", "refused"))
        self.assertEqual((kc.SYSTEM, kc.PROJECT), ("system", "project"))

    def test_ac10_every_form_refusal_code_is_in_closed_list(self):
        """Каждый отказ формы AC-2, AC-3, AC-4 несёт код из `REFUSAL_CODES`
        и подробность отдельным непустым полем.

        Ловит мутацию: отказ «неизвестный раздел» или «отступ» отдаёт
        подробность в поле кода (`code="неизвестный раздел"`) — код вне
        перечня.
        """
        texts = [t for _l, t, *_ in field_level_cases(self.inp)]
        texts += [t for _l, t, *_ in missing_field_cases(self.inp)]
        texts += [t for _l, t, *_ in card_level_cases(self.inp)]
        texts += [t for _l, t, _c in file_level_cases(self.inp)]
        texts += [t for _l, t in section_cases(self.inp)]
        texts += [t for _l, t, *_ in duplicate_cases(self.inp)]
        texts += [t for _l, t, _n in indent_cases(self.inp)]
        limit = config.KNOWLEDGE_CARD_MAX_CHARS
        texts.append(sized_card(self.inp, self.inp.key(), limit + 1))
        texts.append(many_cards(self.inp, config.KNOWLEDGE_CARD_MAX_PER_FILE + 1))
        for text in texts:
            refusal = self.refusal(text, "отказ формы")
            self.assertIn(refusal.code, kc.REFUSAL_CODES,
                          self.inp.msg(f"{refusal!r}\n{text}"))


if __name__ == "__main__":
    unittest.main()
