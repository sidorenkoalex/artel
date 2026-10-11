"""Матрица последствий в QUESTIONS.md: отказ guard по форме вариантов и
вопросов при любом статусе и неэскалация задачи на `advance` из
`spec_writing` с таким батчем (AC-1, AC-2, AC-3).

Группа: долгоживущий

Красен до реализации: guard проверяет у QUESTIONS.md только раздел «Вопросы» и статус — файл без меток матрицы, без вариантов, без нумерованного вопроса и с кириллической буквой варианта проходит с кодом 0, а `advance` из `spec_writing` с таким черновиком эскалирует задачу; AC-2 (полная матрица проходит) зелен с рождения.

Guard — командой `python3 scripts/guard.py <файл>` (так его называет
AC-1), файл во временном каталоге. Состав батча (число вопросов и
вариантов, отступы, номер «плохого» вопроса и буква «плохого» варианта,
недостающая метка, тексты) — из `random`; зерно печатается и входит в
текст каждого провала. Тексты пунктов — кириллица: латинская буква в
выводе guard тогда может быть только буквой варианта.

`advance` (AC-3) — в `tests.sandbox.LightTransitionSandbox`: QUESTIONS.md
на диске каталога задачи песочницы, задача в `spec_writing`,
`fsm.cmd_advance`. Связка «guard — переход `spec_writing` — FSM» и есть
предмет этой половины AC-3.

Провалидирован временным стабом проверки матрицы в guard (откачен, не
закоммичен): все тесты зелены; мутанты стаба «строка дефолта не обрывает
вариант», «`draft` освобождён», «кириллическая буква не ошибка», «пустой
перечень вопросов — нарушений нет», «вопрос без вариантов не проверяется»
красят свои тесты.
"""
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from orchestrator import fsm
from tests.sandbox import LightTransitionSandbox

REPO_ROOT = Path(__file__).resolve().parent.parent
GUARD = REPO_ROOT / "scripts" / "guard.py"

LABELS = ("ломается:", "ослабляется:", "цена:", "чьё решение:")
LETTERS = "ABCDEFGH"
CYRILLIC = "абвгдежзиклмнопрстуфхцчшэюя"


def cword(rng: random.Random, length: int = 6) -> str:
    return "".join(rng.choice(CYRILLIC) for _ in range(length))


def label_line(rng: random.Random, label: str) -> str:
    """Пункт матрицы: отступ, `- `, метка и кириллический текст."""
    indent = rng.choice(["   ", "     ", "      "])
    tail = {
        "ломается:": f"сценарий {cword(rng)}",
        "ослабляется:": f"свойство {cword(rng)} (scripts/guard.py, {cword(rng)})",
        "цена:": rng.choice(["полчаса", "час работы", "один цикл роли"]),
        "чьё решение:": rng.choice(["Оператор", "роль аналитика"]),
    }[label]
    return f"{indent}- {label} {tail}"


def variant_lines(rng: random.Random, letter: str, labels) -> list:
    """Вариант `- <буква>) …` и его пункты матрицы `labels` по порядку."""
    indent = rng.choice(["", "  ", "   "])
    lines = [f"{indent}- {letter}) вариант {cword(rng)}"]
    lines += [label_line(rng, label) for label in labels]
    return lines


def default_line(rng: random.Random, letter: str) -> str:
    indent = rng.choice(["", "  ", "   "])
    return f"{indent}- дефолт: {letter} — {cword(rng)}"


def question_head(number: int, rng: random.Random) -> str:
    return f"{number}. **Вопрос {cword(rng)}?**"


def full_question(rng: random.Random, number: int, n_variants: int) -> list:
    """Вопрос, у каждого варианта которого все четыре метки (порядок меток
    случаен)."""
    lines = [question_head(number, rng)]
    for letter in LETTERS[:n_variants]:
        lines += variant_lines(rng, letter, rng.sample(LABELS, len(LABELS)))
    lines.append(default_line(rng, rng.choice(LETTERS[:n_variants])))
    return lines


def questions_doc(status: str, body_lines: list, task: str = "T999") -> str:
    body = "\n".join(body_lines)
    return (f"---\ntask: {task}\ntype: questions\nauthor_role: analyst\n"
            f"status: {status}\nschema_version: 2\n---\n\n"
            f"# QUESTIONS: батч фикстуры\n\n## Вопросы\n\n{body}\n")


def full_batch(rng: random.Random) -> list:
    """Строки раздела «Вопросы»: от одного до трёх вопросов, у каждого от
    двух до четырёх вариантов, все с полной матрицей."""
    lines = []
    for number in range(1, rng.randrange(1, 4) + 1):
        if lines:
            lines.append("")
        lines += full_question(rng, number, rng.randrange(2, 5))
    return lines


class GuardCliCase(unittest.TestCase):
    """Запуск `python3 scripts/guard.py <файл>` на тексте QUESTIONS.md."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def note(self, text: str) -> str:
        return f"{text} (зерно: {self.seed})"

    def run_guard(self, text: str) -> tuple:
        """(код выхода, вывод guard без пути файла)."""
        path = self.dir / "QUESTIONS.md"
        path.write_text(text, encoding="utf-8")
        res = subprocess.run([sys.executable, str(GUARD), str(path)],
                             cwd=REPO_ROOT, capture_output=True, text=True,
                             timeout=60)
        out = res.stdout + res.stderr
        for form in {str(path), str(path.resolve()), path.name}:
            out = out.replace(form, "")
        return res.returncode, out

    def assert_refused(self, text: str, number=None, letter=None) -> str:
        """Ненулевой код выхода; вывод называет номер вопроса `number` и
        букву варианта `letter` (если заданы)."""
        code, out = self.run_guard(text)
        context = self.note(f"код {code}, вывод guard:\n{out}\nфайл:\n{text}")
        self.assertNotEqual(code, 0, context)
        if number is not None:
            self.assertRegex(out, rf"(?<!\d){number}(?!\d)", context)
        if letter is not None:
            self.assertRegex(out, rf"(?<![A-Za-z]){letter}(?![A-Za-z])", context)
        return out

    def assert_passes(self, text: str) -> None:
        code, out = self.run_guard(text)
        self.assertEqual(code, 0, self.note(f"вывод guard:\n{out}\nфайл:\n{text}"))


# ---------------------------------------------------------------------------
# AC-1: отказ guard по форме матрицы, вариантов и вопросов (status: ready).

class MatrixRefusalTest(GuardCliCase):

    def test_ac1_variant_missing_label_present_in_sibling_is_refused_with_question_and_letter(self):
        """Вариант без одной метки отказан, даже когда эта метка есть у соседнего варианта того же вопроса.

        Сценарий: батч из одного–трёх вопросов с полной матрицей; в
        случайном вопросе у случайного варианта убрана случайная метка, у
        остальных вариантов того же вопроса она есть. `status: ready`.
        guard выходит с ненулевым кодом, вывод называет номер этого
        вопроса и букву этого варианта.

        Ловит мутацию: проверка матрицы отключена — код 0; метки
        считаются на весь вопрос, а не на вариант — у вопроса все четыре
        метки есть (у соседа), код 0; отказ без номера вопроса или буквы
        варианта — регулярка не находит их в выводе.
        """
        questions = []
        for number in range(1, self.rng.randrange(1, 4) + 1):
            questions.append((number, self.rng.randrange(2, 5)))
        bad_number, bad_count = self.rng.choice(questions)
        bad_letter = self.rng.choice(LETTERS[:bad_count])
        missing = self.rng.choice(LABELS)
        lines = []
        for number, count in questions:
            if lines:
                lines.append("")
            lines.append(question_head(number, self.rng))
            for letter in LETTERS[:count]:
                labels = self.rng.sample(LABELS, len(LABELS))
                if (number, letter) == (bad_number, bad_letter):
                    labels.remove(missing)
                lines += variant_lines(self.rng, letter, labels)
            lines.append(default_line(self.rng, LETTERS[0]))
        self.assert_refused(questions_doc("ready", lines), bad_number, bad_letter)

    def test_ac1_label_after_default_line_is_not_counted_for_variant(self):
        """Метка, стоящая после строки дефолта, не засчитывается последнему варианту — отказ с номером и буквой.

        Сценарий: один вопрос, у последнего варианта нет случайной метки;
        она же написана строкой ниже строки `- дефолт: …` этого вопроса.
        guard отказывает и называет номер вопроса и букву последнего
        варианта.

        Ловит мутацию: граница варианта не обрывается строкой дефолта —
        метка после дефолта засчитывается последнему варианту, код 0.
        """
        number = self.rng.randrange(1, 9)
        count = self.rng.randrange(2, 5)
        last = LETTERS[count - 1]
        missing = self.rng.choice(LABELS)
        lines = [question_head(number, self.rng)]
        for letter in LETTERS[:count]:
            labels = self.rng.sample(LABELS, len(LABELS))
            if letter == last:
                labels.remove(missing)
            lines += variant_lines(self.rng, letter, labels)
        lines.append(default_line(self.rng, last))
        lines.append(label_line(self.rng, missing))
        self.assert_refused(questions_doc("ready", lines), number, last)

    def test_ac1_question_without_variant_lines_is_refused_with_number(self):
        """Вопрос, у которого варианты записаны в строку, а не `- <буква>)`, отказан с номером вопроса.

        Сценарий: батч из двух–трёх вопросов; один (случайный) — старой
        формы «варианты: A) …; B) … — дефолт: A» одной строкой, остальные
        — с полной матрицей. guard отказывает, вывод называет номер этого
        вопроса.

        Ловит мутацию: вопрос без вариантов не проверяется (матрицу
        требуют только у найденных вариантов, а их нет) — код 0.
        """
        total = self.rng.randrange(2, 4)
        bad = self.rng.randrange(1, total + 1)
        lines = []
        for number in range(1, total + 1):
            if lines:
                lines.append("")
            if number == bad:
                lines.append(f"{number}. **Вопрос {cword(self.rng)}?** — "
                             f"варианты: A) {cword(self.rng)}; B) "
                             f"{cword(self.rng)} — дефолт: A.")
            else:
                lines += full_question(self.rng, number, self.rng.randrange(2, 4))
        self.assert_refused(questions_doc("ready", lines), bad)

    def test_ac1_section_without_numbered_question_is_refused(self):
        """Раздел «Вопросы» без единой строки `<N>. ` отказан.

        Сценарий: раздел несёт вопросы маркированным списком или
        свободным текстом (форма — из зерна), варианты с полной матрицей
        под ними есть, но строки вопроса `<N>. ` без отступа нет. guard
        выходит с ненулевым кодом.

        Ловит мутацию: пустой перечень вопросов считается «нарушений нет»
        — код 0.
        """
        shape = self.rng.choice(["bullet", "prose"])
        head = {"bullet": f"- **Вопрос {cword(self.rng)}?**",
                "prose": f"Вопрос {cword(self.rng)}: как быть?"}[shape]
        lines = [head]
        for letter in LETTERS[:self.rng.randrange(2, 4)]:
            lines += variant_lines(self.rng, letter, list(LABELS))
        lines.append(default_line(self.rng, "A"))
        self.assert_refused(questions_doc("ready", lines))

    def test_ac1_non_latin_variant_letter_is_refused_with_number(self):
        """Строка варианта с кириллической буквой `- А) ` внутри вопроса отказана с номером вопроса.

        Сценарий: батч с полной матрицей у всех латинских вариантов; в
        случайный вопрос добавлен вариант с кириллической буквой (А, Б или
        В) со всеми четырьмя метками. guard отказывает, вывод называет
        номер этого вопроса.

        Ловит мутацию: строка `- А) ` не узнаётся ни вариантом, ни
        ошибкой — её метки уходят предыдущему (полному) варианту, код 0.
        """
        total = self.rng.randrange(1, 4)
        bad = self.rng.randrange(1, total + 1)
        letter = self.rng.choice("АБВ")
        lines = []
        for number in range(1, total + 1):
            if lines:
                lines.append("")
            block = full_question(self.rng, number, self.rng.randrange(2, 4))
            if number == bad:
                block = block[:-1] + variant_lines(
                    self.rng, letter, list(LABELS)) + block[-1:]
            lines += block
        self.assert_refused(questions_doc("ready", lines), bad)


# ---------------------------------------------------------------------------
# AC-2: полная матрица проходит guard при обоих статусах.

class MatrixPassTest(GuardCliCase):

    def test_ac2_full_matrix_passes_ready_and_draft(self):
        """Батч, у каждого варианта которого все четыре метки, проходит guard со `status: ready` и `status: draft`.

        Сценарий: три случайных батча (вопросы, варианты, отступы, порядок
        меток — из зерна) с полной матрицей; каждый — с обоими статусами.
        guard выходит с кодом 0.

        Ловит мутацию: метка с отступом и `- ` не узнаётся (ищется только
        с начала строки) — отказ полному батчу; граница варианта
        обрывается первой же строкой метки — у варианта засчитана одна
        метка, отказ; проверка буквы варианта требует отсутствия отступа —
        вариант с отступом не найден, отказ.
        """
        for _ in range(3):
            lines = full_batch(self.rng)
            for status in ("ready", "draft"):
                with self.subTest(status=status):
                    self.assert_passes(questions_doc(status, lines))


# ---------------------------------------------------------------------------
# AC-3: черновик без матрицы — отказ guard и неэскалация на `advance`.

class DraftMatrixRefusalTest(GuardCliCase):

    def test_ac3_draft_without_matrix_is_refused_with_question_and_letter(self):
        """Черновик QUESTIONS.md (`status: draft`) с вариантом без метки отказан с номером вопроса и буквой варианта.

        Сценарий: батч с полной матрицей, у случайного варианта случайного
        вопроса убрана случайная метка; `status: draft`. guard выходит с
        ненулевым кодом и называет номер вопроса и букву варианта.

        Ловит мутацию: `draft` освобождён от проверки матрицы — код 0.
        """
        questions = [(number, self.rng.randrange(2, 5))
                     for number in range(1, self.rng.randrange(1, 4) + 1)]
        bad_number, bad_count = self.rng.choice(questions)
        bad_letter = self.rng.choice(LETTERS[:bad_count])
        lines = []
        for number, count in questions:
            if lines:
                lines.append("")
            lines.append(question_head(number, self.rng))
            for letter in LETTERS[:count]:
                labels = list(LABELS)
                if (number, letter) == (bad_number, bad_letter):
                    labels.remove(self.rng.choice(LABELS))
                lines += variant_lines(self.rng, letter, labels)
            lines.append(default_line(self.rng, "A"))
        self.assert_refused(questions_doc("draft", lines), bad_number, bad_letter)


class DraftQuestionsAdvanceTest(LightTransitionSandbox):
    """Связка guard — переход `spec_writing` — FSM: черновик QUESTIONS.md
    без матрицы на диске каталога задачи песочницы."""

    TASK_TITLE = "Матрица последствий в вопросах"

    def test_ac3_spec_writing_advance_with_draft_questions_without_matrix_does_not_escalate(self):
        """`advance` из `spec_writing` с черновиком QUESTIONS.md без матрицы оставляет задачу в `spec_writing`.

        Сценарий: в каталоге задачи песочницы QUESTIONS.md со
        `status: draft`, у случайного варианта нет случайной метки
        матрицы; задача в `spec_writing`; `fsm.cmd_advance`. Задача не в
        `escalated` и остаётся в `spec_writing`.

        Ловит мутацию: `draft` освобождён от проверки матрицы — guard
        пропускает батч, и переход эскалирует задачу (`escalated`).
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        count = rng.randrange(2, 5)
        bad = rng.choice(LETTERS[:count])
        lines = [question_head(1, rng)]
        for letter in LETTERS[:count]:
            labels = list(LABELS)
            if letter == bad:
                labels.remove(rng.choice(LABELS))
            lines += variant_lines(rng, letter, labels)
        lines.append(default_line(rng, "A"))
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "QUESTIONS.md").write_text(
            questions_doc("draft", lines, task=self.TASK), encoding="utf-8")
        self.set_state("spec_writing")
        try:
            out = self.capture(fsm.cmd_advance, self.TASK)
        except SystemExit as exc:
            out = f"SystemExit: {exc.code}"
        context = f"вывод advance:\n{out}\n(зерно: {seed})"
        self.assertNotEqual(self.state(), "escalated", context)
        self.assertEqual(self.state(), "spec_writing", context)


if __name__ == "__main__":
    unittest.main()
