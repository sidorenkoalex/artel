"""Матрица неослабления — обязательная форма мандата в `answer` и `zones-extend` (ADR-0022 п.4).

Группа: долгоживущий
Красен до реализации: `mandate.matrix_refusals` нет (AC-6, AC-12 падают на атрибуте), `answer` принимает мандат без раздела матрицы и без строки «Независимая проверка:» (AC-1, AC-2, AC-4, AC-5, AC-7, AC-10 — ANSWER создаётся), `zones-extend` без `--matrix` создаёт ANSWER, а `cmd_zones_extend` не знает `matrix_path` (AC-8, AC-9 — TypeError); AC-3, AC-11, AC-13 и проходные половины AC-5/AC-7 держат сегодняшнее поведение и зелены с рождения.

Песочница — настоящий git (`tests.sandbox.RealGitSandbox`), связка
«команда — БД — ссылка документов»: ссылка документов задачи
`refs/artifacts/<id>` живёт в репозитории песочницы, появление
`ANSWER-n.md` и сдвиг её головы наблюдаются по самой ссылке. Задачи
заводятся прямой строкой БД в состоянии сценария; кодовой ветки задачи в
песочнице нет, поэтому проверка существования путей мандата зон не
применяется (`mandate.refusals`). Окружение роли снято переменной
`config.ARTEL_ROLE_ENV`. `zones-extend` зовётся и функцией
`answer.cmd_zones_extend`, и диспетчером `artel.main` с подменённым
`sys.argv`. Свойства формы таблицы (требование 3) — модульно, прямым
вызовом `mandate.matrix_refusals`. Элементы мандатов, их число и обёртки в
ячейке, разделители, проходные сочетания ячеек, позиция строки-нарушителя
и состояния задач — от зерна; зерно печатается и входит в текст каждого
провала.
"""
import contextlib
import io
import itertools
import os
import random
import re
import sys
import unittest
from unittest import mock

from orchestrator import answer, artel, config, idgen, store
from orchestrator.advance_gates import mandate
from tests.sandbox import RealGitSandbox

ZONES = "Расширение зон разрешено:"
WEAKEN = "Ослабление тестов разрешено:"
DEPS = "Зависимости мержа:"
CHECK = "Независимая проверка:"
SECTION = "## Матрица неослабления"
DOC = "docs/operator-gates.md"
DOC_TITLE = "Матрица неослабления"
DOCS_REF_PREFIX = "refs/artifacts/"
# Канон заголовков — `docs/operator-gates.md`, раздел «Матрица неослабления».
HEADERS = (
    "Что меняется",
    "Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка)",
    "Остаётся ли свойство после изменения",
    "Чем покрыто после (тест файл:строка) или «не покрыто»",
    "Решение",
)
MANDATE_STATES = ("escalated", "in_dev")
# Обёртки элемента в ячейке «Что меняется» и разделители элементов —
# допустимые границы токена (требование 2).
WRAPS = ("{}", "`{}`", "«{}»", "({})")
JOINS = (", ", "; ", " ")
PREFIXES = ("", "удаляется ", "меняется: ")
# Сочетания «Остаётся ли / Чем покрыто / Решение», годные по требованию 3.
GOOD_VERDICTS = (
    ("да", "`tests/test_cover_{r}.py::Cover::test_m`", "ок"),
    ("Да, остаётся (переезжает)", "tests/test_cover_{r}.py:12", "ок"),
    ("исчезает", "не покрыто", "ок"),
    ("нет", "—", "ок"),
    ("остаётся", "не покрыто", "ок при условии: тест-замена tests/test_new_{r}.py"),
)


def names(text: str, element: str) -> bool:
    """`element` стоит в `text` отдельным именем: не продолжен словом,
    `::имя`, `/имя` или `.расширение` и не продолжает чужое имя."""
    return re.search(r"(?<![\w/.:])" + re.escape(element) + r"(?!\w|::|\.\w|/\w)",
                     text) is not None


class MatrixSandbox(RealGitSandbox):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.add_synced_origin()
        self.conn = store.db()
        patcher = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        patcher.start()
        self.addCleanup(patcher.stop)

    # --- входы ---------------------------------------------------------------

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def r(self) -> int:
        return self.rng.randrange(10 ** 6)

    def insert(self, state: str) -> str:
        task_id = idgen.new_task_id()
        store.insert_task(self.conn, task_id, f"Фикстура {task_id}", state,
                          f"task/{task_id.lower()}-fixture",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        return task_id

    def zone_paths(self, k: int) -> list[str]:
        forms = ("docs/zz_{}.md", "orchestrator/zz_{}.py", "scripts/zz_{}")
        return [self.rng.choice(forms).format(self.r()) for _ in range(k)]

    def weaken_elements(self, k: int) -> list[str]:
        out = []
        for _ in range(k):
            n = self.r()
            out.append(self.rng.choice((
                f"tests/test_q{n}.py", f"tests/test_q{n}.py::Q{n}",
                f"tests/test_q{n}.py::Q{n}::test_m{n}")))
        return out

    def name_cell(self, elements) -> str:
        wrapped = [self.rng.choice(WRAPS).format(e) for e in elements]
        return self.rng.choice(PREFIXES) + self.rng.choice(JOINS).join(wrapped)

    def row(self, what: str, verdict=None, holds: str | None = None) -> tuple:
        n = self.r()
        remains, covered, decision = verdict or self.rng.choice(GOOD_VERDICTS)
        return (what, holds or f"держит-{n} — orchestrator/x.py:{n % 900 + 1}",
                remains.format(r=n), covered.format(r=n), decision.format(r=n))

    def rows_naming(self, elements) -> list[tuple]:
        """Годные строки данных, вместе называющие все `elements`."""
        elements = list(elements)
        self.rng.shuffle(elements)
        rows, i = [], 0
        while i < len(elements):
            k = self.rng.randint(1, len(elements) - i)
            rows.append(self.row(self.name_cell(elements[i:i + k])))
            i += k
        if self.rng.random() < 0.3:
            rows.insert(self.rng.randrange(len(rows) + 1),
                        self.row(f"прочее {self.r()}"))
        return rows

    def matrix(self, rows, headers=HEADERS, heading: str = SECTION) -> str:
        lines = [heading, ""]
        if self.rng.random() < 0.5:
            lines += [f"Свёрка {self.r()}.", ""]
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("|" + "---|" * len(headers))
        lines += ["| " + " | ".join(row) + " |" for row in rows]
        return "\n".join(lines) + "\n"

    def body(self, mandate_lines, matrix_text: str | None = None,
             check: bool | str = True) -> str:
        parts = [f"Ответ Оператора {self.r()}.", "", *mandate_lines]
        if check is True:
            parts.append(f"{CHECK} матрица подтверждена {self.r()}")
        elif isinstance(check, str):
            parts.append(check)
        text = "\n".join(parts) + "\n"
        if matrix_text is not None:
            text += "\n" + matrix_text
        return text

    def file(self, text: str) -> str:
        path = self.root / ".artel" / f"vhod-{self.rng.randrange(1 << 40)}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return str(path)

    # --- команды -------------------------------------------------------------

    @staticmethod
    def run_cmd(fn, *args, **kwargs) -> tuple[str, bool]:
        """(вывод вместе с текстом отказа, был ли ненулевой `SystemExit`)."""
        buf = io.StringIO()
        failed = False
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fn(*args, **kwargs)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    failed = True
                    buf.write(f"\n{exc.code}")
        return buf.getvalue(), failed

    def run_answer(self, task_id: str, text: str) -> tuple[str, bool]:
        return self.run_cmd(answer.cmd_answer, task_id, self.file(text))

    def run_zones(self, task_id: str, paths, matrix_text: str | None,
                  via: str = "function") -> tuple[str, bool]:
        """`zones-extend`: `via` — «function» (`cmd_zones_extend`) или
        «cli» (`artel.main`); `matrix_text` None — без матрицы вовсе."""
        paths_arg = ", ".join(paths)
        matrix = self.file(matrix_text) if matrix_text is not None else None
        if via == "cli":
            argv = ["artel.py", "zones-extend", task_id, paths_arg]
            if matrix is not None:
                argv += ["--matrix", matrix]
            with mock.patch.object(sys, "argv", argv):
                return self.run_cmd(artel.main)
        if matrix is None:
            return self.run_cmd(answer.cmd_zones_extend, task_id, paths_arg)
        return self.run_cmd(answer.cmd_zones_extend, task_id, paths_arg,
                            matrix_path=matrix)

    # --- наблюдения ----------------------------------------------------------

    def head(self, task_id: str) -> str:
        return self.git("for-each-ref", "--format=%(objectname)",
                        DOCS_REF_PREFIX + task_id).strip()

    def answers(self, task_id: str) -> dict:
        """Имя `ANSWER-n.md` -> путь в дереве ссылки документов."""
        ref = DOCS_REF_PREFIX + task_id
        if not self.head(task_id):
            return {}
        return {p.rsplit("/", 1)[-1]: p for p in self.git(
            "ls-tree", "-r", "--name-only", ref).splitlines()
            if p.rsplit("/", 1)[-1].startswith("ANSWER-")}

    def answer_text(self, task_id: str, name: str) -> str:
        return self.git("show", f"{DOCS_REF_PREFIX}{task_id}:"
                        f"{self.answers(task_id)[name]}")

    def state(self, task_id: str) -> str:
        return store.get_task(self.conn, task_id)["state"]

    def seeded(self, state: str) -> str:
        """Задача в `state` с уже принятым ANSWER: голова ссылки документов
        есть, её неподвижность при отказе наблюдаема."""
        task_id = self.insert(state)
        if state == "merge_gate":
            self.set_state(task_id, "escalated")
        self.accepted(task_id, lambda: self.run_answer(
            task_id, f"Указание Оператора {self.r()}: продолжай.\n"), "посев")
        if state == "merge_gate":
            self.set_state(task_id, "merge_gate")
        return task_id

    def set_state(self, task_id: str, state: str) -> None:
        self.conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
        self.conn.commit()

    def accepted(self, task_id: str, run, what: str) -> str:
        """Команда принята: нет отказа, ANSWER прибавился ровно один;
        возврат — имя нового ANSWER."""
        before = set(self.answers(task_id))
        out, failed = run()
        context = self.note(f"{what}\nвывод:\n{out}")
        self.assertFalse(failed, context)
        new = set(self.answers(task_id)) - before
        self.assertEqual(len(new), 1, context)
        return new.pop()

    def refused(self, task_id: str, run, what: str) -> str:
        """Команда отказала до записи: ненулевой выход, ANSWER не прибавился,
        голова ссылки документов на месте; возврат — текст вывода."""
        before = set(self.answers(task_id))
        head = self.head(task_id)
        out, failed = run()
        context = self.note(f"{what}\nвывод:\n{out}")
        self.assertTrue(failed, context)
        self.assertEqual(set(self.answers(task_id)), before, context)
        self.assertEqual(self.head(task_id), head, context)
        return out

    def assert_names(self, out: str, elements, what: str) -> None:
        for element in elements:
            self.assertTrue(names(out, element), self.note(
                f"{what}: отказ не называет «{element}»\nвывод:\n{out}"))


class AnswerWithoutSectionTest(MatrixSandbox):

    def test_ac1_weakening_mandate_without_section_is_refused(self):
        """Мандат тестов без раздела `## Матрица неослабления` — отказ в `escalated` и в `in_dev`, ссылка документов не сдвинута.

        Сценарий: для каждого состояния — задача с уже принятым ANSWER
        (голова ссылки есть). Файл: строка «Ослабление тестов разрешено:»
        на 1–3 элемента, строка «Независимая проверка:»; раздела матрицы
        нет, а от зерна — таблица с каноническими заголовками стоит под
        другим заголовком. `answer` отказывает: новый ANSWER не появился,
        голова ссылки прежняя.

        Ловит мутацию: проверка матрицы стоит только в ветке `escalated`
        (или только в `in_dev`) — в другом состоянии ANSWER создаётся;
        либо раздел ищется по любой таблице файла — таблица под чужим
        заголовком засчитывается, ANSWER создаётся.
        """
        for state in MANDATE_STATES:
            with self.subTest(state=state):
                task_id = self.seeded(state)
                elements = self.weaken_elements(self.rng.randint(1, 3))
                matrix_text = None
                if self.rng.random() < 0.5:
                    matrix_text = self.matrix(self.rows_naming(elements),
                                              heading="## Заметки Оператора")
                text = self.body([f"{WEAKEN} {', '.join(elements)}"], matrix_text)
                self.refused(task_id, lambda: self.run_answer(task_id, text),
                             f"{state}: мандат тестов без раздела\n{text}")


class AnswerTableFormTest(MatrixSandbox):

    def broken_matrix(self, variant: str, paths) -> str | None:
        if variant == "нет раздела":
            return None
        if variant == "нет строк данных":
            return self.matrix([])
        headers = list(HEADERS)
        i = self.rng.randrange(len(headers))
        if self.rng.random() < 0.5:
            del headers[i]
        else:
            headers[i] = f"Примечание {self.r()}"
        rows = [row[:len(headers)] for row in self.rows_naming(paths)]
        return self.matrix(rows, headers=headers)

    def test_ac2_zones_mandate_with_missing_or_malformed_table_is_refused(self):
        """Мандат зон без раздела, без канонического заголовка или без строк данных — отказ в `escalated`, `in_dev` и `merge_gate`.

        Сценарий: для каждого из трёх вариантов и каждого из состояний
        `escalated`/`in_dev` — задача с принятым ANSWER и файл со строкой
        «Расширение зон разрешено:» на 1–3 пути: (1) раздела матрицы нет;
        (2) таблица без одного из пяти канонических заголовков (от зерна —
        столбец выброшен либо заголовок заменён чужим); (3) таблица только
        из заголовков и разделителя. Вдобавок задача в `merge_gate` с файлом
        «Зависимости мержа: нет» + «Расширение зон разрешено: <путь>» без
        раздела. Каждый раз — отказ, ANSWER не создан.

        Ловит мутацию: проверяется только наличие раздела, а не число и
        заголовки столбцов или наличие строк данных — варианты (2)/(3)
        создают ANSWER; либо ветка `merge_gate` пропускает проверку
        матрицы — ANSWER со строкой мандата зон создаётся.
        """
        for variant, state in itertools.product(
                ("нет раздела", "нет заголовка", "нет строк данных"), MANDATE_STATES):
            with self.subTest(variant=variant, state=state):
                task_id = self.seeded(state)
                paths = self.zone_paths(self.rng.randint(1, 3))
                text = self.body([f"{ZONES} {', '.join(paths)}"],
                                 self.broken_matrix(variant, paths),
                                 check=self.rng.random() < 0.5)
                self.refused(task_id, lambda: self.run_answer(task_id, text),
                             f"{state}, {variant}\n{text}")
        with self.subTest(state="merge_gate"):
            task_id = self.seeded("merge_gate")
            text = self.body([f"{DEPS} нет", f"{ZONES} {self.zone_paths(1)[0]}"],
                             check=False)
            self.refused(task_id, lambda: self.run_answer(task_id, text),
                         f"merge_gate без раздела\n{text}")


class AnswerFullMatrixAcceptedTest(MatrixSandbox):

    def test_ac3_weakening_mandate_with_full_matrix_and_check_is_accepted(self):
        """Мандат тестов с полной матрицей и строкой «Независимая проверка:» — ANSWER создан и закоммичен, как до задачи.

        Сценарий: для `escalated` и `in_dev` — задача с принятым ANSWER;
        файл: «Ослабление тестов разрешено:» на 1–4 элемента (файл, класс
        или метод — от зерна), «Независимая проверка: <вердикт>», раздел
        матрицы из пяти канонических столбцов, строки которой называют все
        элементы в разных обёртках и разделителях и несут годные сочетания
        «остаётся/покрыто/решение». ANSWER прибавился, голова ссылки
        сдвинулась, текст ANSWER несёт строку мандата.

        Ловит мутацию: ссылка на тест вида `tests/…py::Класс::метод` или
        `tests/…py:12` не признаётся покрытием (регулярное выражение ждёт
        только одну из форм) — строка «да + покрыто + ок» даёт отказ; либо
        элемент в обёртке `«…»`/`(…)`/`` `…` `` не признаётся названным —
        отказ «элемент не назван», ANSWER не создан.
        """
        for state in MANDATE_STATES:
            with self.subTest(state=state):
                task_id = self.seeded(state)
                head = self.head(task_id)
                elements = self.weaken_elements(self.rng.randint(1, 4))
                line = f"{WEAKEN} {', '.join(elements)}"
                text = self.body([line], self.matrix(self.rows_naming(elements)))
                name = self.accepted(task_id, lambda: self.run_answer(task_id, text),
                                     f"{state}: полная матрица\n{text}")
                self.assertNotEqual(self.head(task_id), head, self.note(text))
                self.assertIn(line, self.answer_text(task_id, name), self.note(text))


class UnnamedElementTest(MatrixSandbox):

    def test_ac4_every_unnamed_mandate_element_is_refused_by_name(self):
        """Неназванный элемент мандата — отказ, текст называет все неназванные элементы.

        Сценарий (от зерна состояние `escalated`/`in_dev`): (а) мандат зон
        или тестов на 2–4 элемента, таблица называет лишь часть, а
        неназванные от зерна стоят в столбце «Какое свойство сейчас
        держит»; (б) две строки «Расширение зон разрешено:», таблица
        называет только элементы первой; (в) мандат тестов на файл
        `tests/<…>.py` целиком, таблица называет только
        `tests/<…>.py::Класс::метод` того же файла. Каждый раз — отказ без
        ANSWER, текст называет каждый неназванный элемент отдельным именем.

        Ловит мутацию: элементы берутся из первой строки маркера
        (`_zones_mandate_marker_paths`) — сценарий (б) проходит; элемент
        ищется во всей строке таблицы — сценарий (а) проходит; совпадение
        подстрокой — `…py::Класс::метод` называет файл, (в) проходит; отказ
        перечисляет только первый неназванный — имён остальных в тексте нет.
        """
        state = self.rng.choice(MANDATE_STATES)
        with self.subTest(case="а"):
            task_id = self.seeded(state)
            marker = self.rng.choice((ZONES, WEAKEN))
            k = self.rng.randint(2, 4)
            elements = (self.zone_paths(k) if marker == ZONES
                        else self.weaken_elements(k))
            missing = self.rng.sample(elements, self.rng.randint(1, k - 1))
            named = [e for e in elements if e not in missing]
            rows = self.rows_naming(named)
            if self.rng.random() < 0.5:
                rows.append(self.row(f"прочее {self.r()}",
                                     holds=", ".join(missing)))
            text = self.body([f"{marker} {', '.join(elements)}"], self.matrix(rows))
            out = self.refused(task_id, lambda: self.run_answer(task_id, text),
                               f"(а) {state}\n{text}")
            self.assert_names(out, missing, "(а)")
        with self.subTest(case="б"):
            task_id = self.seeded(state)
            first = self.zone_paths(self.rng.randint(1, 2))
            second = self.zone_paths(self.rng.randint(1, 2))
            text = self.body([f"{ZONES} {', '.join(first)}",
                              f"{ZONES} {', '.join(second)}"],
                             self.matrix(self.rows_naming(first)), check=False)
            out = self.refused(task_id, lambda: self.run_answer(task_id, text),
                               f"(б) {state}\n{text}")
            self.assert_names(out, second, "(б)")
        with self.subTest(case="в"):
            task_id = self.seeded(state)
            n = self.r()
            whole = f"tests/test_w{n}.py"
            text = self.body([f"{WEAKEN} {whole}"], self.matrix(
                [self.row(self.name_cell([f"{whole}::W{n}::test_m{n}"]))]))
            out = self.refused(task_id, lambda: self.run_answer(task_id, text),
                               f"(в) {state}\n{text}")
            self.assert_names(out, [whole], "(в)")


class SubstringDoesNotNameTest(MatrixSandbox):

    def test_ac5_substring_occurrence_does_not_name_an_element(self):
        """Вхождение подстрокой не называет элемент: `…::A::m` при `…::A::m2` и `tests/` при `tests/<…>.py` — отказ; `tests/` при «`tests`» — проход.

        Сценарий (от зерна `escalated`/`in_dev`): (1) мандат тестов на
        `tests/<…>.py::A::m`, таблица называет только
        `tests/<…>.py::A::m2` — отказ с именем `…::A::m`; (2) мандат зон на
        каталог `tests/`, таблица называет только `tests/<…>.py` — отказ с
        именем `tests/`; (3) мандат зон на `tests/`, ячейка «`tests`» —
        ANSWER создан.

        Ловит мутацию: «назван» проверяется вхождением подстроки (`in`) —
        (1) и (2) проходят; либо `/` на конце не снимается у элемента зон —
        (3) получает отказ «tests/ не назван».
        """
        state = self.rng.choice(MANDATE_STATES)
        with self.subTest(case="метод"):
            task_id = self.seeded(state)
            n = self.r()
            element = f"tests/test_s{n}.py::A::m"
            text = self.body([f"{WEAKEN} {element}"], self.matrix(
                [self.row(self.name_cell([f"{element}2"]))]))
            out = self.refused(task_id, lambda: self.run_answer(task_id, text),
                               f"метод {state}\n{text}")
            self.assert_names(out, [element], "метод")
        with self.subTest(case="каталог"):
            task_id = self.seeded(state)
            text = self.body([f"{ZONES} tests/"], self.matrix(
                [self.row(self.name_cell([f"tests/test_s{self.r()}.py"]))]),
                check=False)
            out = self.refused(task_id, lambda: self.run_answer(task_id, text),
                               f"каталог {state}\n{text}")
            self.assert_names(out, ["tests/"], "каталог")
        with self.subTest(case="без слэша"):
            task_id = self.seeded(state)
            text = self.body([f"{ZONES} tests/"], self.matrix(
                [self.row(self.rng.choice(PREFIXES) + "`tests`")]), check=False)
            self.accepted(task_id, lambda: self.run_answer(task_id, text),
                          f"«`tests`» {state}\n{text}")


class RowDecisionTest(MatrixSandbox):

    def table_with(self, verdict) -> tuple[str, list[str], int]:
        """Текст файла с матрицей: годные строки и одна строка `verdict`
        на случайной позиции; (текст, элементы, номер строки `verdict`)."""
        elements = self.zone_paths(self.rng.randint(1, 3))
        rows = self.rows_naming(elements)
        own = f"docs/own_{self.r()}.md"
        position = self.rng.randrange(len(rows) + 1)
        rows.insert(position, self.row(self.name_cell([own]), verdict))
        text = f"Ответ {self.r()}.\n\n{ZONES} {', '.join(elements + [own])}\n\n"
        return text + self.matrix(rows), elements + [own], position + 1

    def test_ac6_remaining_uncovered_row_needs_conditional_decision(self):
        """Строка «остаётся» + «не покрыто» без «ок при условии <замены>» — отказ с номером строки; три проходных сочетания — без отказа.

        Сценарий: `mandate.matrix_refusals` над таблицей из годных строк и
        одной проверяемой строки на случайной позиции. Отказ (непустой
        список, текст содержит номер строки данных) — для каждого
        сочетания «Остаётся ли» ∈ {да, Да, остаётся (переезжает), пусто} ×
        «Чем покрыто» ∈ {не покрыто, пусто, —, AC-3} с решением «ок», «ок
        при условии», «ок при условии:» или «принято: замена» (от зерна), и
        для «не покрыто — `tests/x.py::A::m` удаляется», «`tests/x.py::A::m`
        удаляется — не покрыто», «- tests/x.py удаляется» с решением «ок».
        Проход (пустой список) — «исчезает» + «не покрыто» + «ок»; «да» +
        `tests/test_x.py:12` + «ок»; «да» + «не покрыто» + «ок при условии:
        тест-замена X». Вдобавок одна строка-нарушитель через `answer`
        (от зерна `escalated`/`in_dev`) — отказ без ANSWER.

        Ловит мутацию: ссылка на тест засчитывается покрытием даже рядом с
        «не покрыто» или после тире — три особых ячейки проходят; пустая
        ячейка «Остаётся ли» считается «не остаётся» — сочетания с пустой
        ячейкой проходят; «ок при условии» без перечня принимается; номер
        строки считается с нуля — текст отказа называет соседний номер.
        """
        bad_decisions = ("ок", "ок при условии", "ок при условии:",
                         "принято: замена тестом")
        cases = [(remains, covered, self.rng.choice(bad_decisions))
                 for remains, covered in itertools.product(
                     ("да", "Да, остаётся (переезжает)", ""),
                     ("не покрыто", "", "—", "AC-3"))]
        cases += [("да", "не покрыто — `tests/x.py::A::m` удаляется", "ок"),
                  ("да", "`tests/x.py::A::m` удаляется — не покрыто", "ок"),
                  ("да", "- tests/x.py удаляется", "ок")]
        for verdict in cases:
            with self.subTest(verdict=verdict):
                text, elements, number = self.table_with(verdict)
                reasons = mandate.matrix_refusals(text, elements)
                joined = "\n".join(reasons)
                context = self.note(f"{verdict}, строка {number}\n{text}\n"
                                    f"причины: {reasons}")
                self.assertTrue(reasons, context)
                self.assertRegex(joined, rf"(?<!\d){number}(?!\d)", context)
        for verdict in (("исчезает", "не покрыто", "ок"),
                        ("да", "tests/test_x.py:12", "ок"),
                        ("да", "не покрыто", "ок при условии: тест-замена X")):
            with self.subTest(verdict=verdict):
                text, elements, _number = self.table_with(verdict)
                reasons = mandate.matrix_refusals(text, elements)
                self.assertEqual(reasons, [], self.note(f"{verdict}\n{text}"))
        with self.subTest(channel="answer"):
            task_id = self.seeded(self.rng.choice(MANDATE_STATES))
            text, _elements, _number = self.table_with(
                ("да", "не покрыто", self.rng.choice(bad_decisions)))
            self.refused(task_id, lambda: self.run_answer(task_id, text),
                         f"answer, строка-нарушитель\n{text}")


class IndependentCheckTest(MatrixSandbox):

    def test_ac7_weakening_mandate_needs_independent_check_line(self):
        """Мандат тестов с полной матрицей без непустой «Независимая проверка:» — отказ; мандат зон без неё — проход.

        Сценарий (от зерна `escalated`/`in_dev`): мандат «Ослабление тестов
        разрешено:» с полной матрицей и (1) без строки «Независимая
        проверка:», (2) со строкой без текста после двоеточия, (3) со
        строкой из одних пробелов после двоеточия — каждый раз отказ без
        ANSWER. Мандат «Расширение зон разрешено:» с полной матрицей без
        этой строки — ANSWER создан.

        Ловит мутацию: проверяется только наличие маркера строки, а не
        непустой вердикт — (2)/(3) проходят; либо строка требуется от любого
        мандата — мандат зон получает отказ.
        """
        state = self.rng.choice(MANDATE_STATES)
        for check in (False, CHECK, f"{CHECK}   "):
            with self.subTest(check=check):
                task_id = self.seeded(state)
                elements = self.weaken_elements(self.rng.randint(1, 3))
                text = self.body([f"{WEAKEN} {', '.join(elements)}"],
                                 self.matrix(self.rows_naming(elements)), check=check)
                self.refused(task_id, lambda: self.run_answer(task_id, text),
                             f"{state}, проверка {check!r}\n{text}")
        with self.subTest(check="мандат зон"):
            task_id = self.seeded(state)
            paths = self.zone_paths(self.rng.randint(1, 3))
            text = self.body([f"{ZONES} {', '.join(paths)}"],
                             self.matrix(self.rows_naming(paths)), check=False)
            self.accepted(task_id, lambda: self.run_answer(task_id, text),
                          f"{state}, мандат зон без проверки\n{text}")


class ZonesExtendMatrixTest(MatrixSandbox):

    def test_ac8_zones_extend_requires_well_formed_matrix(self):
        """`zones-extend` без матрицы — отказ; с матрицей, называющей все пути, — ANSWER несёт её таблицу; с негодной матрицей — отказ.

        Сценарий: задача в `in_dev` с принятым ANSWER, 1–3 пути. Отказ без
        ANSWER: CLI `zones-extend <id> <пути>` без `--matrix`; вызов
        `answer.cmd_zones_extend(<id>, <пути>)` без `matrix_path`; матрица
        не называет один из путей (текст называет его); матрица без
        раздела; без одного из пяти канонических заголовков; без строк
        данных; со строкой «остаётся» + «не покрыто» и решением «ок».
        Проход — и CLI с `--matrix <файл>`, и `matrix_path=<файл>`: ANSWER
        создан, несёт канонические заголовки и содержимое строк таблицы.

        Ловит мутацию: `--matrix` разбирается только в CLI, а
        `cmd_zones_extend` без `matrix_path` создаёт ANSWER по-старому; либо
        `zones-extend` проверяет лишь наличие файла матрицы, не зовя
        `matrix_refusals`, — негодные таблицы проходят; либо таблица в
        ANSWER не переносится — заголовков и ячеек строк в ANSWER нет.
        """
        def task_and_paths():
            return self.seeded("in_dev"), self.zone_paths(self.rng.randint(1, 3))

        for via in ("cli", "function"):
            with self.subTest(case=f"без матрицы, {via}"):
                task_id, paths = task_and_paths()
                self.refused(task_id, lambda: self.run_zones(task_id, paths, None, via),
                             f"без матрицы, {via}")
        for via in ("cli", "function"):
            with self.subTest(case=f"годная матрица, {via}"):
                task_id, paths = task_and_paths()
                rows = self.rows_naming(paths)
                text = self.matrix(rows)
                name = self.accepted(
                    task_id, lambda: self.run_zones(task_id, paths, text, via),
                    f"годная матрица, {via}\n{text}")
                body = self.answer_text(task_id, name)
                for piece in [*HEADERS, *(row[1] for row in rows)]:
                    self.assertIn(piece, body, self.note(
                        f"{via}: в ANSWER нет «{piece}»\n{body}"))
        with self.subTest(case="путь не назван"):
            task_id, paths = task_and_paths()
            missing = self.zone_paths(1)[0]
            text = self.matrix(self.rows_naming(paths))
            out = self.refused(
                task_id, lambda: self.run_zones(task_id, paths + [missing], text),
                f"путь не назван\n{text}")
            self.assert_names(out, [missing], "путь не назван")
        for variant in ("нет раздела", "нет заголовка", "нет строк данных",
                        "остаётся не покрыто"):
            with self.subTest(case=variant):
                task_id, paths = task_and_paths()
                if variant == "нет раздела":
                    text = f"Свёрка {self.r()}.\n\n" + self.matrix(
                        self.rows_naming(paths), heading="## Заметки")
                elif variant == "нет заголовка":
                    headers = list(HEADERS)
                    del headers[self.rng.randrange(len(headers))]
                    text = self.matrix([row[:4] for row in self.rows_naming(paths)],
                                       headers=headers)
                elif variant == "нет строк данных":
                    text = self.matrix([])
                else:
                    rows = self.rows_naming(paths)
                    rows.append(self.row(self.name_cell(paths),
                                         ("да", "не покрыто", "ок")))
                    text = self.matrix(rows)
                self.refused(task_id, lambda: self.run_zones(task_id, paths, text),
                             f"{variant}\n{text}")


class ZonesExtendForeignMandateTest(MatrixSandbox):

    def test_ac9_matrix_file_carries_no_mandate_lines_and_only_section_goes_to_answer(self):
        """Файл `--matrix` со строкой мандата тестов или зависимостей — отказ; абзац вне раздела в ANSWER не попадает.

        Сценарий: задача в `in_dev` с принятым ANSWER, 1–3 пути, полная
        матрица. Отказ без ANSWER, если в файле: строка «Ослабление тестов
        разрешено: tests/<…>.py» вне раздела; та же строка внутри раздела
        (после таблицы); строка «Зависимости мержа: …» (от зерна внутри или
        вне раздела). Проход: полная матрица и абзац с уникальным словом
        вне раздела (от зерна — перед разделом или под следующим
        заголовком `## …`): ANSWER создан, несёт ячейки таблицы и не несёт
        слова абзаца.

        Ловит мутацию: в ANSWER копируется весь файл матрицы — строка
        мандата тестов попадает в ANSWER мимо `mandate.refusals`, абзац вне
        раздела оказывается в ANSWER; либо строки мандатов ищутся только
        вне раздела — строка внутри раздела проходит.
        """
        def task_paths_matrix():
            task_id = self.seeded("in_dev")
            paths = self.zone_paths(self.rng.randint(1, 3))
            return task_id, paths, self.rows_naming(paths)

        weaken_line = f"{WEAKEN} tests/test_f{self.r()}.py"
        deps_line = f"{DEPS} нет"
        for case, line, inside in (("мандат тестов вне раздела", weaken_line, False),
                                   ("мандат тестов в разделе", weaken_line, True),
                                   ("зависимости мержа", deps_line,
                                    self.rng.random() < 0.5)):
            with self.subTest(case=case):
                task_id, paths, rows = task_paths_matrix()
                section = self.matrix(rows)
                text = (section + f"\n{line}\n" if inside
                        else f"{line}\n\n" + section)
                self.refused(task_id, lambda: self.run_zones(task_id, paths, text),
                             f"{case}\n{text}")
        with self.subTest(case="абзац вне раздела"):
            task_id, paths, rows = task_paths_matrix()
            word = f"абзац{self.r()}слово"
            paragraph = f"Пояснение Оператора: {word} — к матрице не относится.\n"
            section = self.matrix(rows)
            text = (f"{paragraph}\n{section}" if self.rng.random() < 0.5
                    else f"{section}\n## Прочее\n\n{paragraph}")
            name = self.accepted(task_id, lambda: self.run_zones(task_id, paths, text),
                                 f"абзац вне раздела\n{text}")
            body = self.answer_text(task_id, name)
            context = self.note(f"{text}\nANSWER:\n{body}")
            for row in rows:
                self.assertIn(row[1], body, context)
            self.assertNotIn(word, body, context)


class RefusalTextTest(MatrixSandbox):

    def test_ac10_every_matrix_refusal_points_to_operator_gates_doc(self):
        """Каждый отказ по матрице в обоих каналах ссылается на `docs/operator-gates.md` и «Матрица неослабления».

        Сценарий: отказы AC-1, AC-2, AC-4–AC-9 по одному представителю —
        `answer` (от зерна `escalated`/`in_dev`): нет раздела; нет
        канонического заголовка; нет строк данных; элемент не назван;
        строка «остаётся, не покрыто» с «ок»; мандат тестов без
        «Независимая проверка:»; `zones-extend`: CLI без `--matrix`; функция
        без `matrix_path`; нет раздела; путь не назван; строка мандата тестов
        в файле матрицы. Каждый — отказ без ANSWER, текст содержит оба
        адреса.

        Ловит мутацию: отказ одной из проверок (например, «не назван»,
        «нет строки Независимая проверка» или «без --matrix») собран своим
        текстом без ссылки на канон — у этого представителя адреса нет.
        """
        state = self.rng.choice(MANDATE_STATES)

        def answer_case(build):
            task_id = self.seeded(state)
            text = build()
            return task_id, lambda: self.run_answer(task_id, text), text

        def zones_case(matrix_of, via="function"):
            task_id = self.seeded("in_dev")
            paths = self.zone_paths(self.rng.randint(1, 2))
            text = matrix_of(paths)
            return task_id, lambda: self.run_zones(task_id, paths, text, via), text

        def weaken(rows_of, check=True, headers=HEADERS):
            elements = self.weaken_elements(self.rng.randint(1, 2))
            rows = rows_of(elements)
            matrix_text = (None if rows is None
                           else self.matrix(rows, headers=headers))
            return self.body([f"{WEAKEN} {', '.join(elements)}"], matrix_text, check)

        cases = {
            "answer: нет раздела": lambda: answer_case(lambda: weaken(lambda e: None)),
            "answer: нет заголовка": lambda: answer_case(lambda: weaken(
                lambda e: [r[:4] for r in self.rows_naming(e)], headers=HEADERS[:4])),
            "answer: нет строк данных": lambda: answer_case(
                lambda: weaken(lambda e: [])),
            "answer: не назван": lambda: answer_case(lambda: weaken(
                lambda e: [self.row(f"прочее {self.r()}")])),
            "answer: остаётся не покрыто": lambda: answer_case(lambda: weaken(
                lambda e: [self.row(self.name_cell(e), ("да", "не покрыто", "ок"))])),
            "answer: нет независимой проверки": lambda: answer_case(
                lambda: weaken(self.rows_naming, check=False)),
            "zones-extend: CLI без --matrix": lambda: zones_case(lambda p: None, "cli"),
            "zones-extend: функция без matrix_path": lambda: zones_case(lambda p: None),
            "zones-extend: нет раздела": lambda: zones_case(lambda p: self.matrix(
                self.rows_naming(p), heading="## Заметки")),
            "zones-extend: не назван": lambda: zones_case(lambda p: self.matrix(
                [self.row(f"прочее {self.r()}")])),
            "zones-extend: мандат тестов в файле": lambda: zones_case(
                lambda p: f"{WEAKEN} tests/test_f{self.r()}.py\n\n"
                          + self.matrix(self.rows_naming(p))),
        }
        for case, make in cases.items():
            with self.subTest(case=case):
                task_id, run, text = make()
                out = self.refused(task_id, run, f"{case}\n{text}")
                for address in (DOC, DOC_TITLE):
                    self.assertIn(address, out, self.note(
                        f"{case}: отказ без «{address}»\nвывод:\n{out}"))


class WithoutMandateUnchangedTest(MatrixSandbox):

    def test_ac11_files_without_mandate_lines_pass_as_before(self):
        """Указание без строк мандатов и файл только с «Зависимости мержа:» проходят `answer` без матрицы, как до задачи.

        Сценарий: (1) задача в `in_dev`, файл-указание без строк мандатов —
        ANSWER создан, журнал несёт запись указания Оператора, состояние
        `in_dev`; (2) задача в `escalated` и (3) задача в `merge_gate` —
        файл только со строкой «Зависимости мержа: <живая задача>» (от
        зерна) либо «… нет» без раздела матрицы — ANSWER создан, состояние
        прежнее.

        Ловит мутацию: строка «Зависимости мержа:» засчитана строкой
        мандата (общий перечень `MANDATE_MARKERS` вместо двух маркеров) —
        файл (2)/(3) без матрицы получает отказ; либо проверка матрицы
        зовётся на любом файле `answer` — указание (1) получает отказ.
        """
        with self.subTest(case="указание в in_dev"):
            task_id = self.seeded("in_dev")
            text = f"Указание Оператора {self.r()}: поправь разбор.\n"
            self.accepted(task_id, lambda: self.run_answer(task_id, text), "указание")
            actions = [r["action"] for r in store.task_steps(self.conn, task_id)]
            self.assertEqual(actions.count(answer.INSTRUCTION_ACTION), 2,
                             self.note(f"журнал: {actions}"))
            self.assertEqual(self.state(task_id), "in_dev", self.note("указание"))
        for state in ("escalated", "merge_gate"):
            with self.subTest(case=f"зависимости мержа, {state}"):
                task_id = self.seeded(state)
                dep = (self.insert("acceptance") if self.rng.random() < 0.5
                       else None)
                text = self.body([f"{DEPS} {dep or 'нет'}"], check=False)
                self.accepted(task_id, lambda: self.run_answer(task_id, text),
                              f"{state}\n{text}")
                self.assertEqual(self.state(task_id), state, self.note(text))


class SingleCheckFunctionTest(MatrixSandbox):

    def test_ac12_disabled_matrix_check_is_visible_in_both_channels(self):
        """Мутация «`mandate.matrix_refusals` всегда пуст» снимает отказ AC-1 в `answer` и AC-8 в `zones-extend` одновременно.

        Сценарий: (1) без подмены — `answer` (от зерна `escalated`/`in_dev`)
        с мандатом тестов, «Независимая проверка:» и без раздела матрицы —
        отказ; `zones-extend` с `matrix_path` на файл, где таблица раздела
        без строк данных (сценарий AC-8), — отказ.
        (2) `mandate.matrix_refusals` подменена функцией, возвращающей
        пустой список, — те же сценарии на свежих задачах создают ANSWER в
        обоих каналах.

        Ловит мутацию: один из каналов проверяет форму своей копией
        проверки (или зовёт её мимо `mandate.matrix_refusals`) — под
        подменой этот канал по-прежнему отказывает, ANSWER не создаётся.
        """
        state = self.rng.choice(MANDATE_STATES)

        def answer_scenario():
            task_id = self.seeded(state)
            elements = self.weaken_elements(self.rng.randint(1, 2))
            text = self.body([f"{WEAKEN} {', '.join(elements)}"])
            return task_id, lambda: self.run_answer(task_id, text)

        def zones_scenario():
            task_id = self.seeded("in_dev")
            paths = self.zone_paths(self.rng.randint(1, 2))
            text = self.matrix([])
            return task_id, lambda: self.run_zones(task_id, paths, text)

        for channel, scenario in (("answer", answer_scenario),
                                  ("zones-extend", zones_scenario)):
            with self.subTest(channel=channel):
                task_id, run = scenario()
                self.refused(task_id, run, f"{channel}: без подмены")
                task_id, run = scenario()
                with mock.patch.object(mandate, "matrix_refusals",
                                       lambda *args, **kwargs: []):
                    self.accepted(task_id, run, f"{channel}: проверка отключена")


class MandateRefusalsFirstTest(MatrixSandbox):

    def test_ac13_mandate_refusals_precede_matrix_check_with_same_text(self):
        """Негодная строка мандата тестов (путь вне `tests/**/*.py`) — отказ `mandate.refusals` прежним текстом, раньше проверки матрицы.

        Сценарий (от зерна `escalated`/`in_dev`): строка «Ослабление тестов
        разрешено: orchestrator/<…>.py» и «Независимая проверка:»; (1) с
        матрицей, называющей этот путь, — отказ без ANSWER, текст несёт
        «строка мандата не прошла проверку» и каждую причину
        `mandate.refusals` над тем же текстом; (2) без раздела матрицы — тот
        же отказ, и ни ссылки на канон матрицы, ни слов «Матрица
        неослабления» в тексте нет.

        Ловит мутацию: `matrix_refusals` зовётся до `mandate.refusals` (или
        причины обеих проверок сливаются в один отказ) — в (2) текст несёт
        причину по матрице; либо текст отказа `mandate.refusals` переписан
        — прежних строк причин в выводе нет.
        """
        state = self.rng.choice(MANDATE_STATES)
        for with_matrix in (True, False):
            with self.subTest(with_matrix=with_matrix):
                task_id = self.seeded(state)
                path = f"orchestrator/x_{self.r()}.py"
                matrix_text = (self.matrix([self.row(self.name_cell([path]))])
                               if with_matrix else None)
                text = self.body([f"{WEAKEN} {path}"], matrix_text)
                out = self.refused(task_id, lambda: self.run_answer(task_id, text),
                                   f"матрица: {with_matrix}\n{text}")
                expected = mandate.refusals(text, None)
                context = self.note(f"{text}\nвывод:\n{out}\nожидалось: {expected}")
                self.assertTrue(expected, context)
                self.assertIn("строка мандата не прошла проверку", out, context)
                for reason in expected:
                    self.assertIn(f"  {reason}", out, context)
                if not with_matrix:
                    self.assertNotIn(DOC, out, context)
                    self.assertNotIn(DOC_TITLE, out, context)


if __name__ == "__main__":
    unittest.main()
