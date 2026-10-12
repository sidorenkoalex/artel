"""Команда `answer` на гейте SPEC: приём только мандата тестов, именованные отказы, рубеж окружения роли, lease, прежний отказ прочих состояний (AC-2, AC-3, AC-4, AC-5, AC-9, AC-10).

Группа: долгоживущий
Красен до реализации: на `spec_gate` `answer` отказывает любому файлу общим отказом «answer доступна только для задачи в состоянии escalated» — без слова reject (AC-2, AC-3), не теми сообщениями, что в `in_dev` (AC-4), не текстом рубежа окружения роли (AC-5), без отказа lease при чужом живом lease и без приёма корректного мандата после его освобождения (AC-10); AC-9 и проверка порядка разбора аргументов `artel.py answer` (AC-5) держат сегодняшнее поведение и зелены с рождения.

Песочница — настоящий git (`tests.sandbox.RealGitSandbox`), связка
«команда — БД — ссылка документов — lease»: ссылка документов задачи
`refs/artifacts/<id>` живёт в репозитории песочницы, появление `ANSWER-n.md`
и сдвиг её головы наблюдаются по самой ссылке. Задачи заводятся прямой
строкой БД в состоянии сценария; кодовой ветки задачи в песочнице нет,
поэтому проверка существования путей мандата зон не применяется. Окружение
роли снято переменной `config.ARTEL_ROLE_ENV` (пустое значение); сценарий
«вызов из окружения роли» ставит её непустой.

«Те же сообщения, что в `in_dev`» читаются сравнением: тот же файл подаётся
`answer` для задачи-двойника в `in_dev`, текст её отказа (с id двойника,
заменённым на id задачи) обязан совпасть с текстом отказа на `spec_gate`.
Так же читается текст рубежа окружения роли — его даёт `answer` двойнику в
`in_dev` из окружения роли.

Элементы мандатов, их число, формы строк, отступы, варианты файлов и порядок
случаев — от зерна; зерно печатается и входит в текст каждого провала.

Провалидировано временным стабом ветки `spec_gate` в `answer._cmd_answer`
(откачен, не закоммичен): все методы зелёные; мутанты «детектор строк зон и
зависимостей `startswith` без `strip`», «проверка матрицы заменена наличием
раздела», «ветка `spec_gate` мимо `lease.run_locked`» красят AC-3, AC-4 и
AC-10.
"""
import contextlib
import io
import os
import random
import socket
import sys
import unittest
from unittest import mock

from orchestrator import answer, artel, config, idgen, lease, store
from tests import mandate_matrix
from tests.sandbox import RealGitSandbox, _alive_foreign_pid

WEAKEN = "Ослабление тестов разрешено:"
ZONES = "Расширение зон разрешено:"
DEPS = "Зависимости мержа:"
DOCS_REF_PREFIX = "refs/artifacts/"
OLD_REFUSAL = "answer доступна только для задачи в состоянии escalated"
NOT_PASSED = "не прошла проверку"
NOT_NAMED = "в столбце «Что меняется» не названы элементы мандата"
NO_FILE = "answer: файла ответа нет:"
LEASE_REFUSAL = "задачу ведёт сессия"
MANDATE_ACTION = "ANSWER создан (мандат на ослабление тестов: "
INDENTS = ("", "  ", "    ", "\t", " \t")
OTHER_STATES = ("spec_writing", "spec_audit", "tests_writing", "acceptance",
                "verifying")


class SpecGateAnswerSandbox(RealGitSandbox):
    """Задачи прямой строкой БД; `answer` — `answer.cmd_answer`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.add_synced_origin()
        self.conn = store.db()
        self.role_env("")

    # --- входы ---------------------------------------------------------------

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def r(self) -> int:
        return self.rng.randrange(10 ** 6)

    def role_env(self, value: str) -> None:
        patcher = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: value})
        patcher.start()
        self.addCleanup(patcher.stop)

    def insert(self, state: str) -> str:
        task_id = idgen.new_task_id()
        store.insert_task(self.conn, task_id, f"Фикстура {task_id}", state,
                          f"task/{task_id.lower()}-fixture",
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        return task_id

    def weaken_elements(self, k: int) -> list[str]:
        out: list[str] = []
        while len(out) < k:
            n = self.r()
            element = self.rng.choice((
                f"tests/test_q{n}.py", f"tests/test_q{n}.py::Q{n}",
                f"tests/test_q{n}.py::Q{n}::test_m{n}"))
            if element not in out:
                out.append(element)
        return out

    def mandate_text(self, elements, *, matrix_elements=None, matrix=True,
                     check=True, extra_lines=()) -> str:
        """Файл ответа: абзац, строка мандата тестов на `elements`, строки
        `extra_lines`, строка независимой проверки и раздел матрицы на
        `matrix_elements` (по умолчанию — те же элементы)."""
        parts = [f"Ответ Оператора {self.r()}.", ""]
        parts.append(f"{WEAKEN} {', '.join(elements)}")
        parts += list(extra_lines)
        if check:
            parts.append(mandate_matrix.INDEPENDENT_CHECK_LINE)
        text = "\n".join(parts) + "\n"
        if matrix:
            text += "\n" + mandate_matrix.matrix(
                elements if matrix_elements is None else matrix_elements)
        return text

    def valid_mandate(self) -> tuple[str, list[str]]:
        elements = self.weaken_elements(self.rng.randint(1, 3))
        return self.mandate_text(elements), elements

    def file(self, text: str) -> str:
        path = self.root / ".artel" / f"otvet-{self.rng.randrange(1 << 40)}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return str(path)

    def missing_path(self) -> str:
        return str(self.root / ".artel" / f"net-{self.rng.randrange(1 << 40)}.md")

    # --- команды -------------------------------------------------------------

    @staticmethod
    def run_cmd(fn, *args) -> tuple[str, str | None]:
        """(вывод вместе с текстом отказа, текст ненулевого `SystemExit` либо
        `None`)."""
        buf = io.StringIO()
        exit_text = None
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fn(*args)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    exit_text = str(exc.code)
                    buf.write(f"\n{exc.code}")
        return buf.getvalue(), exit_text

    def run_answer(self, task_id: str, path: str) -> tuple[str, str | None]:
        return self.run_cmd(answer.cmd_answer, task_id, path)

    # --- наблюдения ----------------------------------------------------------

    def head(self, task_id: str) -> str:
        return self.git("for-each-ref", "--format=%(objectname)",
                        DOCS_REF_PREFIX + task_id).strip()

    def answers(self, task_id: str) -> list[str]:
        if not self.head(task_id):
            return []
        return sorted(p for p in self.git(
            "ls-tree", "-r", "--name-only", DOCS_REF_PREFIX + task_id).splitlines()
            if p.rsplit("/", 1)[-1].startswith("ANSWER-"))

    def row(self, task_id: str):
        return store.get_task(self.conn, task_id)

    def journal(self, task_id: str) -> list[str]:
        return [r["action"] for r in store.task_steps(self.conn, task_id)]

    def refused(self, task_id: str, path: str, what: str) -> str:
        """`answer` отказала до записи: ненулевой выход, ANSWER не
        прибавился, голова ссылки документов, состояние и `merge_after`
        прежние. Возврат — текст отказа."""
        answers, head = self.answers(task_id), self.head(task_id)
        row = self.row(task_id)
        out, exit_text = self.run_answer(task_id, path)
        context = self.note(f"{what}\nвывод:\n{out}")
        self.assertIsNotNone(exit_text, context)
        self.assertEqual(self.answers(task_id), answers, context)
        self.assertEqual(self.head(task_id), head, context)
        self.assertEqual(self.row(task_id)["state"], row["state"], context)
        self.assertEqual(self.row(task_id)["merge_after"], row["merge_after"],
                         context)
        return exit_text

    def in_dev_refusal(self, task_id: str, path: str) -> str:
        """Текст отказа `answer` с тем же файлом для двойника в `in_dev`, с
        id двойника, заменённым на `task_id`."""
        twin = self.insert("in_dev")
        exit_text = self.refused(twin, path, "двойник в in_dev")
        return exit_text.replace(twin, task_id)


# ---------------------------------------------------------------- AC-2

class NoTestMandateRefusedTest(SpecGateAnswerSandbox):

    def test_ac2_spec_gate_file_without_test_mandate_line_is_refused_naming_reject(self):
        """Файл без строки «Ослабление тестов разрешено:» на `spec_gate` — именованный отказ со словом reject, ANSWER нет.

        Сценарий: задача на `spec_gate`; файл — свободный текст ответа
        Оператора (от зерна в середине строки процитирован маркер мандата
        тестов — строкой мандата это не делает). `answer` отказывает:
        ANSWER не прибавился, голова ссылки документов и состояние прежние,
        текст отказа называет reject (решения по SPEC передаются им).

        Ловит мутацию: ветка `spec_gate` принимает любой файл как указание
        Оператора (путь `in_dev`) — ANSWER-1.md появляется в ссылке; либо
        файл без мандата получает общий отказ состояния — в тексте нет
        «reject».
        """
        task_id = self.insert("spec_gate")
        for quoted in (False, True):
            with self.subTest(quoted=quoted):
                text = f"Ответ Оператора {self.r()}: SPEC годится, правь AC-{self.r() % 9 + 1}.\n"
                if quoted:
                    text += (f"Как в прошлой задаче: «{WEAKEN} "
                             f"{self.weaken_elements(1)[0]}».\n")
                exit_text = self.refused(task_id, self.file(text),
                                         f"свободный текст:\n{text}")
                self.assertIn("reject", exit_text, self.note(exit_text))


# ---------------------------------------------------------------- AC-3

class ZonesAndDepsRefusedTest(SpecGateAnswerSandbox):

    def zones_line(self, indent: str) -> str:
        paths = []
        for _ in range(self.rng.randint(1, 3)):
            n = self.r()
            paths.append(self.rng.choice((
                f"orchestrator/zz_{n}.py", f"docs/zz_{n}.md",
                f"scripts/zz_{n}.py — пояснение {n}")))
        return f"{indent}{ZONES} {', '.join(paths)}"

    def deps_line(self, indent: str) -> str:
        value = self.rng.choice((
            "нет", self.insert("in_dev"), idgen.new_task_id(),
            ", ".join(self.insert("acceptance") for _ in range(2))))
        return f"{indent}{DEPS} {value}"

    def test_ac3_zones_or_deps_line_refused_before_form_and_matrix(self):
        """Строка зон или зависимостей на `spec_gate` — именованный отказ раньше формы и матрицы, при любом отступе строки.

        Сценарий: задача на `spec_gate` с `merge_after` от зерна (пусто или
        живая задача). Для каждого вида строки (зоны, зависимости), каждого
        отступа (нет, пробелы, табуляция, смесь) и каждого варианта файла:
        (1) только эта строка, без матрицы и строки независимой проверки;
        (2) вместе с корректным мандатом тестов, матрица которого называет
        только элементы мандата тестов; (3) вместе с мандатом тестов без
        матрицы и без строки независимой проверки. Элементы строки зон и
        зависимостей от зерна бывают и негодными (путь с пробелом,
        несуществующая задача). Каждый раз `answer` отказывает: ANSWER нет,
        `merge_after` и голова ссылки прежние; текст отказа называет reject
        и escalated, говорит о зонах и зависимостях и не является отказом
        формы или матрицы («не прошла проверку»).

        Ловит мутацию: отказ по строкам зон/зависимостей стоит после
        `_read_checked_answer_file` — вариант (3) и негодные элементы дают
        отказ «матрица/строка мандата не прошла проверку»; свой детектор
        `line.startswith(маркер)` без `strip` — строка с отступом не
        распознана, вариант (2) принят и ANSWER создан (а строка
        зависимостей переписывает `merge_after`).
        """
        task_id = self.insert("spec_gate")
        if self.rng.random() < 0.5:
            store.update_task(self.conn, task_id,
                              merge_after=self.insert("in_dev"))
        cases = [(kind, indent, variant) for kind in ("zones", "deps")
                 for indent in INDENTS for variant in (1, 2, 3)]
        self.rng.shuffle(cases)
        for kind, indent, variant in cases:
            with self.subTest(kind=kind, indent=repr(indent), variant=variant):
                line = (self.zones_line(indent) if kind == "zones"
                        else self.deps_line(indent))
                if variant == 1:
                    text = f"Ответ Оператора {self.r()}.\n\n{line}\n"
                else:
                    elements = self.weaken_elements(self.rng.randint(1, 2))
                    text = self.mandate_text(elements, matrix=variant == 2,
                                             check=variant == 2,
                                             extra_lines=[line])
                exit_text = self.refused(task_id, self.file(text),
                                         f"{kind}, вариант {variant}:\n{text}")
                context = self.note(f"{text}\nотказ:\n{exit_text}")
                self.assertIn("reject", exit_text, context)
                self.assertIn("escalated", exit_text, context)
                self.assertIn("зон", exit_text.lower(), context)
                self.assertIn("зависимост", exit_text.lower(), context)
                self.assertNotIn(NOT_PASSED, exit_text, context)


# ---------------------------------------------------------------- AC-4

class FormAndMatrixRefusedTest(SpecGateAnswerSandbox):

    def test_ac4_spec_gate_form_and_matrix_refusals_match_in_dev(self):
        """Мандат тестов с негодной матрицей или формой на `spec_gate` — отказ тем же текстом, что в `in_dev`, ANSWER нет.

        Сценарий: задача на `spec_gate`; варианты файла со строкой
        «Ослабление тестов разрешено:» на 1–3 элемента: без раздела
        матрицы; без строки «Независимая проверка:»; матрица называет
        другие элементы; элемент вне `tests/**/*.py`; элемент с пробелом.
        Каждый раз `answer` отказывает (ANSWER нет, голова ссылки прежняя),
        и текст отказа совпадает с текстом отказа того же файла у
        двойника в `in_dev`; для матрицы без элемента мандата текст несёт
        «в столбце «Что меняется» не названы элементы мандата».

        Ловит мутацию: `_matrix_problems` на `spec_gate` заменён проверкой
        наличия раздела «## Матрица неослабления» — файл с разделом без
        элемента мандата принят, ANSWER создан; либо на `spec_gate` не
        зовётся `mandate.refusals` — элемент вне `tests/` или с пробелом
        принят.
        """
        task_id = self.insert("spec_gate")
        variants = ["нет матрицы", "нет проверки", "матрица без элемента",
                    "вне tests", "пробел"]
        self.rng.shuffle(variants)
        for variant in variants:
            with self.subTest(variant=variant):
                elements = self.weaken_elements(self.rng.randint(1, 3))
                if variant == "нет матрицы":
                    text = self.mandate_text(elements, matrix=False)
                elif variant == "нет проверки":
                    text = self.mandate_text(elements, check=False)
                elif variant == "матрица без элемента":
                    text = self.mandate_text(
                        elements, matrix_elements=self.weaken_elements(1))
                else:
                    n = self.r()
                    bad = (self.rng.choice((f"orchestrator/zz_{n}.py",
                                            f"docs/zz_{n}.md",
                                            f"tests/fixtures/zz_{n}.json"))
                           if variant == "вне tests"
                           else f"tests/test_q{n}.py пояснение")
                    elements = elements + [bad]
                    text = self.mandate_text(elements)
                path = self.file(text)
                exit_text = self.refused(task_id, path, f"{variant}:\n{text}")
                expected = self.in_dev_refusal(task_id, path)
                context = self.note(f"{variant}\n{text}\nspec_gate:\n{exit_text}"
                                    f"\nin_dev:\n{expected}")
                self.assertEqual(exit_text, expected, context)
                if variant == "матрица без элемента":
                    self.assertIn(NOT_NAMED, exit_text, context)


# ---------------------------------------------------------------- AC-5

class RoleEnvironmentRefusedTest(SpecGateAnswerSandbox):

    def test_ac5_role_environment_refusal_on_spec_gate_is_the_role_env_text(self):
        """Вызов `answer.cmd_answer` из окружения роли на `spec_gate` — отказ текстом рубежа окружения роли, до чтения файла.

        Сценарий: задача на `spec_gate`, процесс в окружении роли
        (`config.ARTEL_ROLE_ENV` непуст, роль от зерна). Файл — от зерна
        порядок двух случаев: несуществующий путь и корректный мандат тестов
        (матрица, строка независимой проверки). Каждый раз `answer`
        отказывает, ANSWER нет, голова ссылки прежняя, и текст отказа равен
        тексту отказа двойника в `in_dev` из окружения роли на том же
        несуществующем пути (рубеж окружения роли, не отказ чтения файла,
        формы или состояния). Контроль: тот же корректный файл вне окружения
        роли принят.

        Ловит мутацию: ветка `spec_gate` проверяет окружение роли после
        `_read_checked_answer_file` (или не проверяет вовсе) — несуществующий
        путь даёт «файл ответа не прочитан», корректный файл принят и
        ANSWER создан из окружения роли.
        """
        task_id = self.insert("spec_gate")
        text, _elements = self.valid_mandate()
        valid = self.file(text)
        missing = self.missing_path()
        self.role_env(self.rng.choice(("developer", "reviewer", "analyst")))
        expected = self.in_dev_refusal(task_id, missing)
        cases = [("нет файла", missing), ("корректный мандат", valid)]
        self.rng.shuffle(cases)
        for what, path in cases:
            with self.subTest(case=what):
                exit_text = self.refused(task_id, path, what)
                self.assertEqual(exit_text, expected, self.note(
                    f"{what}\nspec_gate:\n{exit_text}\nin_dev:\n{expected}"))
        self.role_env("")
        out, exit_text = self.run_answer(task_id, valid)
        self.assertIsNone(exit_text, self.note(f"контроль вне окружения роли:\n{out}"))
        self.assertEqual(len(self.answers(task_id)), 1, self.note(out))

    def test_ac5_cli_missing_file_refused_by_argument_parsing_before_lease(self):
        """`artel.py answer <id> <нет файла>` для задачи на `spec_gate` — по-прежнему отказ разбора аргументов «файла ответа нет».

        Сценарий: задача на `spec_gate`; диспетчер `artel.main` с
        несуществующим путём файла (вне окружения роли). Вывод несёт
        «answer: файла ответа нет:», ANSWER нет, записи «lease взят» в
        журнале задачи нет, состояние прежнее.

        Ловит мутацию: ветку `spec_gate` поставили в `artel.py` до разбора
        аргументов `_answer_args` (или проверку существования файла
        перенесли за lease) — первым срабатывает отказ гейта SPEC или в
        журнале появляется «lease взят».
        """
        task_id = self.insert("spec_gate")
        argv = ["artel.py", "answer", task_id, self.missing_path()]
        with mock.patch.object(sys, "argv", argv):
            out, exit_text = self.run_cmd(artel.main)
        context = self.note(f"вывод:\n{out}\nжурнал: {self.journal(task_id)}")
        self.assertIsNotNone(exit_text, context)
        self.assertIn(NO_FILE, exit_text, context)
        self.assertEqual(self.answers(task_id), [], context)
        self.assertNotIn("lease взят", self.journal(task_id), context)
        self.assertEqual(self.row(task_id)["state"], "spec_gate", context)


# ---------------------------------------------------------------- AC-9

class OtherStatesKeepOldRefusalTest(SpecGateAnswerSandbox):

    def test_ac9_mandate_outside_spec_gate_keeps_old_state_refusal(self):
        """Корректный мандат тестов в `spec_writing`/`spec_audit`/`tests_writing`/`acceptance`/`verifying` — прежний отказ состояния.

        Сценарий: для каждого состояния (порядок от зерна) — своя задача и
        корректный файл мандата тестов (матрица, строка независимой
        проверки). `answer` отказывает текстом «answer доступна только для
        задачи в состоянии escalated…», ANSWER нет, голова ссылки и
        состояние прежние.

        Ловит мутацию: новая ветка открыта условием «состояние вне
        escalated/in_dev/review/merge_gate» вместо равенства `spec_gate` —
        мандат принят в любом из этих состояний, ANSWER создан.
        """
        states = list(OTHER_STATES)
        self.rng.shuffle(states)
        for state in states:
            with self.subTest(state=state):
                task_id = self.insert(state)
                text, _elements = self.valid_mandate()
                exit_text = self.refused(task_id, self.file(text), state)
                self.assertIn(OLD_REFUSAL, exit_text, self.note(exit_text))


# ---------------------------------------------------------------- AC-10

class ForeignLeaseRefusedTest(SpecGateAnswerSandbox):

    def test_ac10_foreign_live_lease_refuses_then_released_lease_accepts(self):
        """Чужой живой lease задачи на `spec_gate` — отказ lease без ANSWER; после освобождения тот же файл принят.

        Сценарий: задача на `spec_gate`; lease держит чужая сессия (имя от
        зерна) с живым pid на этом host и свежим heartbeat. `answer` с
        корректным мандатом тестов отказывает отказом lease («задачу ведёт
        сессия <чужая>»), ANSWER нет, голова ссылки прежняя, строка lease
        не изменена. Затем lease освобождён (`lease.release`) — тот же файл
        принят: один ANSWER, задача на `spec_gate`, запись «ANSWER создан
        (мандат на ослабление тестов: …)».

        Ловит мутацию: ветка `spec_gate` исполняется без `lease.run_locked`
        (как указание Оператора в `in_dev`) — при чужом живом lease ANSWER
        создан и отказа lease нет.
        """
        task_id = self.insert("spec_gate")
        foreign = f"chuzhaya-sessiya-{self.r()}"
        store.insert_lease(self.conn, task_id, foreign, _alive_foreign_pid(self),
                           socket.gethostname(), store.now())
        before = dict(store.lease_row(self.conn, task_id))
        text, elements = self.valid_mandate()
        path = self.file(text)

        exit_text = self.refused(task_id, path, "чужой живой lease")

        context = self.note(f"отказ:\n{exit_text}")
        self.assertIn(f"{LEASE_REFUSAL} {foreign}", exit_text, context)
        self.assertEqual(dict(store.lease_row(self.conn, task_id)), before, context)

        lease.release(self.conn, task_id, foreign)
        out, exit_text = self.run_answer(task_id, path)
        context = self.note(f"после освобождения:\n{out}")
        self.assertIsNone(exit_text, context)
        self.assertEqual(len(self.answers(task_id)), 1, context)
        self.assertEqual(self.row(task_id)["state"], "spec_gate", context)
        self.assertIn(f"{MANDATE_ACTION}{', '.join(elements)})",
                      self.journal(task_id), context)


if __name__ == "__main__":
    unittest.main()
