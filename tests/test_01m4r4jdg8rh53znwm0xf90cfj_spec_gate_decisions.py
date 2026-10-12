"""Бриф аудитора SPEC несёт решения Оператора, переданные причиной возврата с гейта SPEC.

Группа: долгоживущий
Красен до реализации: spec_auditor_brief не собирает раздел «Решения Оператора на гейте SPEC» — ни метки «Решение Оператора на гейте SPEC №k из n», ни текста причины reject на spec_gate в брифе аудитора нет, указания «полный текст — artel.py log <id>» тоже; зелёна с рождения только отрицательная часть AC-2 (задача лишь с fail-возвратами аудитора) и вторая половина AC-9 (компонент крупного SPEC велит читать файл адресно).

Песочница — `tests.sandbox.LightTransitionSandbox`: документы задачи
читаются с диска песочницы, git заглушён, карта кодовой базы — фикстура
в корне песочницы со свежим `built_at_sha` (сверка свежести отвечает
«расхождений нет»). Связка, которую держит файл: журнал переходов,
записанный настоящими командами пульта (`fsm.cmd_reject` на `spec_gate`,
выход аудита по вердикту fail `advance_gates.spec_audit.leave`), — сборка
брифа аудитора `brief.spec_auditor_brief`. Прочие переходы между
визитами (вход в аудит, выход аудита на гейт, эскалация) — штатным
`store.set_state` с тем исполнителем, что пишет их пульт.

Идентификатор прогона брифа фиксируется подменой публичного
`brief.new_run_id`, чтобы граничные маркеры были известны тесту
(`brief.wrap_boundary`). Тексты причин, метки фикстур и число возвратов
берутся из `random`; зерно печатается и входит в текст каждого провала.

Файл провалидирован временным стабом реализации в `spec_auditor_brief`
(отбор по журналу, снятие префикса, компонент на причину, указание
журнала у крупной): все методы зелёные; мутации стаба — отбор по
подстроке, отбор без исполнителя и предшественника, префикс не снят,
обратный порядок, крупная причина общим путём, компонент без границ,
раздел до ANSWER-n — красили соответствующие методы; стаб удалён.
"""
import contextlib
import io
import random
import re
import unittest
from unittest import mock

from orchestrator import brief, catalog, config, fsm, store
from orchestrator.advance_gates import spec_audit as audit_gate
from tests.sandbox import LightTransitionSandbox, capture_new_task_id

SECTION_TITLE = "Решения Оператора на гейте SPEC"
LABEL_STEM = "Решение Оператора на гейте SPEC"
LABEL_RE = re.compile(r"Решение Оператора на гейте SPEC №\d+ из \d+")
GATE_PREFIX = "возврат из spec_gate: "
LOG_HINT = "полный текст — artel.py log "
READ_TOOL_HINT = "инструментом чтения"
RU = "абвгдежзиклмнопрстуфхцчшэюя"


def label(k: int, n: int) -> str:
    return f"{LABEL_STEM} №{k} из {n}"


class SpecGateDecisionsSandbox(LightTransitionSandbox):
    """Лёгкая песочница переходов с картой, ТЗ и SPEC задачи на диске и
    известным идентификатором прогона брифа."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.run_id = "%032x" % self.rng.getrandbits(128)
        patcher = mock.patch.object(brief, "new_run_id",
                                    return_value=self.run_id)
        patcher.start()
        self.addCleanup(patcher.stop)
        opening, _, closing = brief.wrap_boundary(
            self.run_id, "ТЕЛО").partition("\nТЕЛО\n")
        self.open_marker, self.close_marker = opening, closing

        docs = self.root / "docs"
        docs.mkdir(parents=True, exist_ok=True)
        (docs / "codebase-map.md").write_text(
            f"---\nbuilt_at_sha: {'a' * 40}\n---\n\n# Карта {self.word()}\n",
            encoding="utf-8")
        self.seed_docs(self.TASK)

    # ------------------------------------------------------------ обвязка

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def word(self, length: int = 8) -> str:
        return "".join(self.rng.choice(RU) for _ in range(length))

    def reason(self) -> str:
        """Причина reject: многострочная, с кавычками и разметкой — чтобы
        «дословно» не совпало случайно с нормализованным текстом."""
        return (f"Снять сценарий {self.word()} из ТЗ: «{self.word()}» не "
                f"нужен, `{self.word(5)}` — 50%.\nВторая строка "
                f"{self.word()} * {self.rng.randrange(10, 99)}.")

    def big_reason(self, mark: str) -> str:
        line = f"Длинная причина {mark} {self.word()}.\n"
        count = config.CONTEXT_FILE_MAX_BYTES // len(line.encode("utf-8")) + 2
        return (line * count).strip()

    def rel(self, task: str, name: str) -> str:
        return (config.TASKS / task / name).relative_to(config.ROOT).as_posix()

    def seed_docs(self, task: str, spec: str | None = None,
                  answers: int = 0) -> None:
        tdir = config.TASKS / task
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "TZ.md").write_text(f"# ТЗ {self.word()}\n", encoding="utf-8")
        (tdir / "SPEC.md").write_text(
            spec or f"# SPEC {self.word()}\n\nAC-1. Критерий.\n",
            encoding="utf-8")
        for n in range(1, answers + 1):
            (tdir / f"ANSWER-{n}.md").write_text(
                f"# ANSWER-{n}\n\nОтвет {self.word()}.\n", encoding="utf-8")

    def new_task(self) -> str:
        _, task = capture_new_task_id(catalog.cmd_new,
                                      f"Задача {self.word()}")
        self.seed_docs(task)
        return task

    def state_of(self, task: str) -> str:
        return store.get_task(store.db(), task)["state"]

    def journal(self, task: str) -> str:
        return "\n".join(f"{r['actor']} | {r['action']} | "
                         f"{(r['detail'] or '')[:200]}"
                         for r in store.task_steps(store.db(), task))

    def move(self, task: str, state: str, actor: str = "fsm",
             detail: str = "") -> None:
        store.set_state(store.db(), task, state, actor,
                        expected_state=self.state_of(task), detail=detail)

    # ------------------------------------------------------------ события

    def gate_reject(self, task: str, reason: str) -> None:
        """Из `spec_writing`: аудит, гейт SPEC, настоящий `reject`."""
        self.move(task, "spec_audit", detail="SPEC готов — аудит")
        self.move(task, "spec_gate",
                  detail="аудит SPEC: вердикт pass — SPEC ждёт approve")
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            fsm.cmd_reject(task, reason)
        self.assertEqual(self.state_of(task), "spec_writing", self.msg(
            f"reject не вернул задачу:\n{out.getvalue()}\n{self.journal(task)}"))

    def fail_return(self, task: str, deviation: str) -> None:
        """Из `spec_writing`: аудит и выход аудита по вердикту fail."""
        self.move(task, "spec_audit", detail="SPEC готов — аудит")
        audit = (f"---\ntask: {task}\ntype: spec_audit\nverdict: fail\n---\n\n"
                 f"# SPEC-AUDIT\n\n## Вердикт\n\n{deviation}\n")
        out = io.StringIO()
        with mock.patch.object(config, "SPEC_AUDIT_FAIL_RETURNS", 1000), \
                contextlib.redirect_stdout(out):
            audit_gate.leave(store.db(), task, "spec_audit", "fail", audit)
        self.assertEqual(self.state_of(task), "spec_writing", self.msg(
            f"fail не вернул задачу:\n{out.getvalue()}\n{self.journal(task)}"))

    def auditor_brief(self, task: str) -> str:
        self.move(task, "spec_audit", detail="SPEC готов — аудит")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            return brief.spec_auditor_brief(store.db(), task)

    # ------------------------------------------------------------ разбор

    def map_start(self, text: str) -> int:
        positions = [p for p in (text.find(brief.MAP_PROJECTION_NOTE.strip()),
                                 text.find(f"### {brief.MAP_PROJECTION_LABEL}"))
                     if p != -1]
        self.assertTrue(positions, self.msg(f"нет компонента карты:\n{text}"))
        return min(positions)

    def component(self, text: str, start_label: str) -> str:
        """Кусок брифа от метки до следующего заголовка компонента."""
        start = text.find(start_label)
        self.assertNotEqual(start, -1, self.msg(
            f"нет «{start_label}» в брифе:\n{text[:4000]}"))
        end = text.find("\n### ", start + 1)
        return text[start:end if end != -1 else len(text)]

    def assert_reasons_in_order(self, text: str, reasons: list) -> None:
        """Метки №1..№n по порядку; причина k — дословно между меткой k и
        следующей меткой (последняя — до карты)."""
        n = len(reasons)
        stops = [text.find(label(k, n)) for k in range(1, n + 1)]
        context = self.msg(f"бриф:\n{text[:6000]}")
        for k, pos in enumerate(stops, 1):
            self.assertNotEqual(pos, -1, f"нет метки {label(k, n)}; {context}")
        self.assertEqual(stops, sorted(stops), f"метки не по порядку; {context}")
        bounds = stops[1:] + [self.map_start(text)]
        for k, reason in enumerate(reasons):
            if reason is None:
                continue
            segment = text[stops[k]:bounds[k]]
            self.assertIn(reason, segment,
                          f"причина №{k + 1} не дословно под своей меткой; "
                          f"{context}")


# ---------------------------------------------------------------- AC-1

class GateReasonReachesAuditorTest(SpecGateDecisionsSandbox):

    def test_ac1_gate_reject_reason_in_auditor_brief_without_prefix(self):
        """Причина настоящего reject на spec_gate — в разделе брифа аудитора, без префикса.

        Сценарий: задача проходит аудит до `spec_gate`, Оператор делает
        `fsm.cmd_reject` со случайной многострочной причиной, задача снова
        входит в `spec_audit`. Бриф аудитора несёт заголовок раздела
        «Решения Оператора на гейте SPEC», метку «Решение Оператора на
        гейте SPEC №1 из 1», после них — текст причины дословно; строки
        «возврат из spec_gate: <причина>» в брифе нет.

        Ловит мутацию: раздел не собирается (причина в бриф аудитора не
        попадает); либо в раздел идёт `detail` записи перехода целиком —
        в брифе появляется префикс «возврат из spec_gate: » перед причиной.
        """
        reason = self.reason()
        self.gate_reject(self.TASK, reason)
        text = self.auditor_brief(self.TASK)
        context = self.msg(f"бриф:\n{text[:6000]}")
        title = text.find(SECTION_TITLE)
        self.assertNotEqual(title, -1, context)
        first = text.find(label(1, 1))
        self.assertGreater(first, title, context)
        self.assertGreater(text.find(reason, first), first, context)
        self.assertNotIn(GATE_PREFIX + reason, text, context)


# ---------------------------------------------------------------- AC-2

class NonGateReturnsExcludedTest(SpecGateDecisionsSandbox):

    def test_ac2_fail_and_non_gate_returns_stay_out_of_section(self):
        """Fail-возврат аудитора и возврат Оператора не с гейта — вне раздела даже с префиксом в тексте.

        Сценарий (две задачи): (а) у задачи только 1-2 возврата по fail
        аудитора, отклонения которых содержат «возврат из spec_gate: <метка>»
        — бриф аудитора без заголовка раздела и без единой метки «Решение
        Оператора на гейте SPEC»; (б) у задачи в случайном порядке один
        настоящий reject на spec_gate, один fail-возврат аудитора с
        префиксом в тексте и одна запись `state -> spec_writing`
        исполнителя `operator` из состояния, отличного от `spec_gate`
        (случайно `escalated` или `spec_audit`), с текстом «возврат из
        spec_gate: <метка>» — в брифе ровно одна метка «№1 из 1» и
        причина reject, меток fail-возврата и не-гейтовой записи нет.

        Ловит мутацию: отбор по подстроке «возврат из spec_gate: » вместо
        предыдущего состояния — в разделе «№k из 3» и метки чужих записей;
        отбор только по целевому состоянию `spec_writing` без исполнителя/
        предшественника — в раздел попадает причина fail-возврата.
        """
        only_fail = self.new_task()
        marks = []
        for _ in range(self.rng.randint(1, 2)):
            mark = f"fail{self.word()}"
            marks.append(mark)
            self.fail_return(only_fail, f"Отклонение: {GATE_PREFIX}{mark}.")
        text = self.auditor_brief(only_fail)
        context = self.msg(f"только fail:\n{text[:6000]}")
        self.assertNotIn(SECTION_TITLE, text, context)
        self.assertNotIn(LABEL_STEM, text, context)

        reason = self.reason()
        fail_mark, other_mark = f"fail{self.word()}", f"chuzh{self.word()}"
        other_state = self.rng.choice(("escalated", "spec_audit"))

        def operator_non_gate():
            self.move(self.TASK, other_state, detail="промежуточный переход")
            self.move(self.TASK, "spec_writing", actor="operator",
                      detail=f"{GATE_PREFIX}{other_mark}")

        events = [lambda: self.gate_reject(self.TASK, reason),
                  lambda: self.fail_return(
                      self.TASK, f"Отклонение: {GATE_PREFIX}{fail_mark}."),
                  operator_non_gate]
        self.rng.shuffle(events)
        for run in events:
            run()
        text = self.auditor_brief(self.TASK)
        context = self.msg(f"смешанные возвраты ({other_state}):\n"
                           f"{text[:6000]}\n{self.journal(self.TASK)}")
        self.assertEqual(LABEL_RE.findall(text), [label(1, 1)], context)
        self.assertIn(reason, text, context)
        self.assertNotIn(fail_mark, text, context)
        self.assertNotIn(other_mark, text, context)


# ---------------------------------------------------------------- AC-3

class OrderAndPlacementTest(SpecGateDecisionsSandbox):

    def test_ac3_all_gate_reasons_in_journal_order_between_answers_or_spec_and_map(self):
        """Несколько reject — все, по порядку журнала, дословно; раздел между последним ANSWER (или SPEC) и картой.

        Сценарий: задача (а) с ТЗ, SPEC, ANSWER-1..ANSWER-m (m — 1..3) и
        2-4 reject на spec_gate со случайными причинами; задача (б) с ТЗ,
        SPEC, без ANSWER и 1-3 reject. В брифе каждой: метки «№k из n» по
        возрастанию позиции, причина k дословно между меткой k и следующей
        меткой (последняя — до карты); заголовок раздела и все метки стоят
        после закрывающего граничного маркера последнего ANSWER (а) / SPEC
        (б) и до компонента карты кодовой базы.

        Ловит мутацию: причины отобраны в обратном порядке или берётся
        только последняя; раздел вставлен до ANSWER-n (сразу после SPEC при
        наличии ответов), после карты или в начало брифа; при отсутствии
        ANSWER раздел не после SPEC.
        """
        answers = self.rng.randint(1, 3)
        self.seed_docs(self.TASK, answers=answers)
        reasons = [self.reason() for _ in range(self.rng.randint(2, 4))]
        for reason in reasons:
            self.gate_reject(self.TASK, reason)
        text = self.auditor_brief(self.TASK)
        self.assert_reasons_in_order(text, reasons)
        self.assert_section_between(
            text, self.rel(self.TASK, f"ANSWER-{answers}.md"), len(reasons))

        bare = self.new_task()
        reasons = [self.reason() for _ in range(self.rng.randint(1, 3))]
        for reason in reasons:
            self.gate_reject(bare, reason)
        text = self.auditor_brief(bare)
        self.assertNotIn("ANSWER-", text, self.msg(text[:4000]))
        self.assert_reasons_in_order(text, reasons)
        self.assert_section_between(text, self.rel(bare, "SPEC.md"),
                                    len(reasons))

    def assert_section_between(self, text: str, before_rel: str, n: int) -> None:
        context = self.msg(f"раздел после {before_rel}:\n{text[:8000]}")
        heading = text.find(f"### {before_rel}")
        self.assertNotEqual(heading, -1, context)
        before_end = text.find(self.close_marker, heading)
        self.assertNotEqual(before_end, -1, context)
        map_start = self.map_start(text)
        positions = [text.find(SECTION_TITLE)] + [
            text.find(label(k, n)) for k in range(1, n + 1)]
        for pos in positions:
            self.assertGreater(pos, before_end, context)
            self.assertLess(pos, map_start, context)


# ---------------------------------------------------------------- AC-4

class OversizedReasonKeepsOthersTest(SpecGateDecisionsSandbox):

    def test_ac4_oversized_reason_does_not_hide_other_reasons(self):
        """Одна причина крупнее лимита компонента — остальные компоненты на месте со своим текстом.

        Сценарий: 2-4 reject на spec_gate, причина на случайной позиции —
        крупнее `config.CONTEXT_FILE_MAX_BYTES`, прочие — короткие. В
        брифе аудитора есть все n меток «№k из n» по порядку, каждая
        короткая причина — дословно под своей меткой.

        Ловит мутацию: все причины склеены в один компонент — превышение
        лимита скрывает его целиком (короткие причины пропадают из брифа);
        цикл сборки обрывается на первой крупной причине — метки после неё
        отсутствуют.
        """
        n = self.rng.randint(2, 4)
        big = self.rng.randrange(n)
        reasons = [self.reason() for _ in range(n)]
        reasons[big] = self.big_reason(f"big{self.word()}")
        for reason in reasons:
            self.gate_reject(self.TASK, reason)
        text = self.auditor_brief(self.TASK)
        expected = list(reasons)
        expected[big] = None
        self.assert_reasons_in_order(text, expected)


# ---------------------------------------------------------------- AC-8

class ReasonBodyInsideBoundaryTest(SpecGateDecisionsSandbox):

    def test_ac8_each_reason_body_inside_run_boundary_markers(self):
        """Тело каждого компонента причины — между парой граничных маркеров идентификатора прогона.

        Сценарий: 1-4 reject на spec_gate. Для каждой метки «№k из n»:
        после неё до следующего заголовка компонента идёт открывающий
        маркер прогона, затем текст причины, затем закрывающий маркер; иных
        открывающих маркеров между открывающим и причиной нет.

        Ловит мутацию: компонент причины собран без `wrap_boundary` (тело
        после заголовка голым текстом) — открывающего маркера между меткой
        и причиной нет.
        """
        reasons = [self.reason() for _ in range(self.rng.randint(1, 4))]
        for reason in reasons:
            self.gate_reject(self.TASK, reason)
        text = self.auditor_brief(self.TASK)
        n = len(reasons)
        for k, reason in enumerate(reasons, 1):
            part = self.component(text, label(k, n))
            context = self.msg(f"компонент №{k}:\n{part[:3000]}")
            opened = part.find(self.open_marker)
            self.assertNotEqual(opened, -1, context)
            body = part.find(reason, opened)
            self.assertGreater(body, opened, context)
            self.assertEqual(part.rfind(self.open_marker, 0, body), opened,
                             context)
            closed = part.find(self.close_marker, body)
            self.assertGreaterEqual(closed, body + len(reason), context)


# ---------------------------------------------------------------- AC-9

class OversizedReasonPointsToLogTest(SpecGateDecisionsSandbox):

    def test_ac9_oversized_reason_points_to_log_and_oversized_file_to_read_tool(self):
        """Крупная причина — указание журнала задачи; крупный SPEC в том же брифе — по-прежнему указание читать файл.

        Сценарий: SPEC.md задачи крупнее `config.CONTEXT_FILE_MAX_BYTES`;
        1-3 reject на spec_gate, одна из причин (случайная) крупнее того же
        лимита. Компонент крупной причины несёт «полный текст — artel.py
        log <id задачи>», не несёт указания читать «инструментом чтения» и
        не несёт тела причины (её метки нет во всём брифе). Компонент
        SPEC.md несёт указание «инструментом чтения» и не несёт
        «полный текст — artel.py log».

        Ловит мутацию: крупная причина идёт общим путём компонентов файлов
        (аудитору велено читать несуществующий файл по метке); указание
        журнала добавлено в общий путь — оно появляется у компонента SPEC;
        крупная причина включена телом.
        """
        spec_line = f"Строка SPEC {self.word()}.\n"
        spec = spec_line * (config.CONTEXT_FILE_MAX_BYTES
                            // len(spec_line.encode("utf-8")) + 2)
        self.seed_docs(self.TASK, spec=spec)
        n = self.rng.randint(1, 3)
        big = self.rng.randrange(n)
        mark = f"big{self.word()}"
        reasons = [self.reason() for _ in range(n)]
        reasons[big] = self.big_reason(mark)
        for reason in reasons:
            self.gate_reject(self.TASK, reason)
        text = self.auditor_brief(self.TASK)
        self.assertNotIn(mark, text, self.msg("тело крупной причины в брифе"))

        part = self.component(text, label(big + 1, n))
        context = self.msg(f"компонент крупной причины:\n{part[:3000]}")
        self.assertIn(LOG_HINT + self.TASK, part, context)
        self.assertNotIn(READ_TOOL_HINT, part, context)

        part = self.component(text, f"### {self.rel(self.TASK, 'SPEC.md')}")
        context = self.msg(f"компонент SPEC:\n{part[:3000]}")
        self.assertIn(READ_TOOL_HINT, part, context)
        self.assertNotIn(LOG_HINT, part, context)


if __name__ == "__main__":
    unittest.main()
