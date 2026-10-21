"""Отказ `approve` на гейте SPEC о потере заявленной зависимости ведёт по исполнимому пути reject → эскалация аналитика → answer в escalated → approve (AC-8, AC-9).

Группа: долгоживущий
Красен до реализации: текст отказа `merge_after.spec_gate_declared_refusal` о потере заявленной зависимости кончается прежним хвостом «снять заявленную может только Оператор: мандат «Зависимости мержа: …» в ANSWER (artel.py answer <id> <файл>)…» — `reject`, `escalated` и `approve` в нём нет, первое `answer` стоит без `reject` перед ним (AC-8); test_ac9 зелёный с рождения — путь answer в escalated → сверка без отказа, отказ о добавке без обоснования и отказ гейта мержа держат прежнее поведение, которое правка обязана сохранить.

AC-8 — свойство текста одной функции: `spec_gate_declared_refusal` зовётся
напрямую на задаче, чья колонка `merge_after` несёт заявленные
зависимости, а значение поля SPEC теряет их часть (или поля нет). AC-9
держит связку `new --tz` («Порядок: после …») — `answer` в `escalated` —
сверка гейта SPEC в лёгкой песочнице переходов (`LightTransitionSandbox`).
Число зависимостей, какие из них потеряны и есть ли поле — от зерна; зерно
печатается и входит в текст каждого провала.
"""
import contextlib
import io
import os
import random
import unittest
from unittest import mock

from orchestrator import answer, catalog, config, merge_after, store
from tests.sandbox import (InitializedTmpRootTest, LightTransitionSandbox,
                           capture_new_task_id, disk_backed_ls_tree_files)

FIELD = "merge_after"
MANDATE = "Зависимости мержа:"
LOSS_START = (f"{FIELD} SPEC теряет зависимости, заявленные Оператором строкой "
              f"ТЗ «Порядок: после»: ")
OLD_TAIL = ("снять заявленную может только Оператор: мандат «Зависимости "
            "мержа: …» в ANSWER (artel.py answer {id} <файл>)")
ZONES = "orchestrator/catalog.py"

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: {zones}
budget_usd: 30
{field_line}---

# SPEC: фикстура подсказки гейта SPEC

## Контекст

Фикстура.

## Требования

1. Фикстура.

## Критерии приёмки

AC-1. Фикстура.
"""


def spec_text(task_id: str, value: str | None) -> str:
    field_line = "" if value is None else f"{FIELD}: {value}\n"
    return SPEC_TEXT.format(task=task_id, zones=ZONES, field_line=field_line)


def meta_of(value: str | None) -> dict:
    return {} if value is None else {FIELD: value}


class LossRefusalTextTest(InitializedTmpRootTest):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.counter = 0

    def task(self) -> str:
        self.counter += 1
        task_id = f"T6{self.rng.randrange(1000, 9999)}{self.counter:02d}"
        store.insert_task(self.conn, task_id, f"Задача {task_id}", "spec_gate",
                          f"task/{task_id.lower()}", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        return task_id

    def test_ac8_loss_refusal_leads_through_reject_and_escalated_answer(self):
        """Отказ о потере заявленной зависимости сохраняет начало и ведёт через reject, эскалацию аналитика, answer в escalated и approve.

        Сценарий: задача на `spec_gate` с одной-тремя заявленными
        зависимостями в колонке `merge_after`; поле SPEC от зерна либо
        отсутствует, либо несёт часть заявленных. Отказ начинается прежним
        текстом «merge_after SPEC теряет зависимости, заявленные Оператором
        строкой ТЗ «Порядок: после»: <полные id потерянных>»; содержит
        «reject», «эскалац», «аналитик», «answer», «Зависимости мержа:»,
        «escalated» и «approve»; первое «answer» стоит после первого
        «reject»; прежнего хвоста «снять заявленную может только Оператор:
        мандат … в ANSWER (artel.py answer <id> <файл>)» нет.

        Ловит мутацию: хвост отказа не заменён (по-прежнему советует answer
        мимо reject) — нет «reject»/«escalated», прежний хвост на месте;
        новый текст называет answer раньше reject — порядок не сходится;
        правка задела начало отказа (поле, фраза или список id) — начало
        расходится.
        """
        for _ in range(3):
            task_id = self.task()
            declared = [self.task() for _ in range(self.rng.randint(1, 3))]
            store.update_task(self.conn, task_id,
                              merge_after=merge_after.column(declared))
            kept = [d for d in declared if self.rng.random() < 0.5]
            if len(kept) == len(declared):
                kept.pop(self.rng.randrange(len(kept)))
            value = merge_after.column(kept) if kept and self.rng.random() < 0.7 else None
            lost = [d for d in declared if d not in merge_after.stored(value)]
            t = store.get_task(self.conn, task_id)

            added, reason = merge_after.spec_gate_declared_refusal(
                self.conn, task_id, t, meta_of(value), value,
                spec_text(task_id, value))

            note = (f"зерно: {self.seed}; заявлено {declared}, поле SPEC "
                    f"{value!r}; отказ: {reason!r}")
            self.assertEqual(added, [], note)
            self.assertIsNotNone(reason, note)
            self.assertTrue(reason.startswith(LOSS_START + ", ".join(lost)), note)
            for word in ("reject", "эскалац", "аналитик", "answer", MANDATE,
                         "escalated", "approve"):
                self.assertIn(word, reason, f"нет «{word}»: {note}")
            self.assertLess(reason.index("reject"), reason.index("answer"), note)
            self.assertNotIn(OLD_TAIL.format(id=task_id), reason, note)
            self.assertNotIn("снять заявленную может только Оператор: мандат",
                             reason, note)


class DeclaredPathTest(LightTransitionSandbox):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        path = self.root / ZONES
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# фикстура\n", encoding="utf-8")
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        env.start()
        self.addCleanup(env.stop)

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def run_cmd(self, fn, *args) -> str:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fn(*args)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    buf.write(f"\n{exc.code}")
        return buf.getvalue()

    def live_task(self) -> str:
        _, task_id = capture_new_task_id(
            catalog.cmd_new, f"Зависимость {self.rng.randrange(1 << 20)}")
        return task_id

    def declared_task(self, deps: list[str]) -> str:
        tz = self.root / f"tz-{self.rng.randrange(1 << 30)}.md"
        tz.write_text(f"Источник: фикстура {self.seed}.\n\nТребуется:\n"
                      f"1. Фикстура.\n\nПорядок: после {', '.join(deps)}\n\n"
                      f"Зоны: {ZONES}.\n", encoding="utf-8")
        out, task_id = capture_new_task_id(
            catalog.cmd_new, f"Задача {self.rng.randrange(1 << 20)}", str(tz))
        self.assertEqual(merge_after.stored(store.get_task(
            self.conn, task_id)["merge_after"]), deps,
            self.note(f"предпосылка: new не заявил {deps}:\n{out}"))
        return task_id

    def refusal(self, task_id: str, value: str | None) -> tuple[list, str | None]:
        return merge_after.spec_gate_declared_refusal(
            self.conn, task_id, store.get_task(self.conn, task_id),
            meta_of(value), value, spec_text(task_id, value))

    def no_code_tree(self, branch, rel, *, repo=None):
        if rel == ".":
            return None
        return disk_backed_ls_tree_files(branch, rel, repo=repo)

    def test_ac9_escalated_answer_unblocks_same_spec_and_other_refusals_unchanged(self):
        """`answer` с «Зависимости мержа: …» в escalated меняет колонку, и тот же SPEC проходит сверку; отказ о добавке и отказы гейта мержа — прежние.

        Сценарий: задача заведена `new` с одной-двумя заявленными
        зависимостями; SPEC теряет хотя бы одну (поле — часть заявленных
        либо его нет) — сверка отказывает. Задача уходит в `escalated` из
        `spec_writing`, `answer` со строкой «Зависимости мержа: <значение
        поля SPEC или «нет»>» меняет колонку на это значение; тот же SPEC
        проходит `spec_gate_declared_refusal` без отказа. Затем: SPEC с
        добавкой сверх заявленного без раздела обоснования — отказ прежним
        текстом; `merge_gate_refuses` на убитой и на незавершённой
        зависимости — прежние текст журнала и строка вывода.

        Ловит мутацию: правка текста отказа задела соседние ветки — отказ о
        добавке без обоснования или отказы гейта мержа сменили текст;
        `answer` в escalated перестал менять колонку (мандат не применён) —
        тот же SPEC снова отказан.
        """
        deps = [self.live_task() for _ in range(self.rng.randint(1, 2))]
        task_id = self.declared_task(deps)
        kept = deps[:self.rng.randint(0, len(deps) - 1)]
        value = merge_after.column(kept)
        _, before = self.refusal(task_id, value)
        self.assertIsNotNone(before, self.note(f"предпосылка: SPEC {value!r} "
                                               f"не отказан при заявленных {deps}"))

        self.conn.execute("UPDATE tasks SET state='escalated', "
                          "escalated_from='spec_writing' WHERE id=?", (task_id,))
        self.conn.commit()
        line = f"{MANDATE} {', '.join(kept) if kept else 'нет'}"
        source = self.root / f"answer-{self.rng.randrange(1 << 30)}.txt"
        source.write_text(f"{line}\n\nОснование: решение Оператора "
                          f"({self.seed}).\n", encoding="utf-8")
        with mock.patch("orchestrator.gitcmd.ls_tree_files", self.no_code_tree):
            out = self.run_cmd(answer.cmd_answer, task_id, str(source))
        self.assertEqual(merge_after.stored(store.get_task(
            self.conn, task_id)["merge_after"]), kept,
            self.note(f"answer «{line}» не сменил колонку:\n{out}"))
        self.conn.execute("UPDATE tasks SET state='spec_gate' WHERE id=?", (task_id,))
        self.conn.commit()
        added, after = self.refusal(task_id, value)
        self.assertIsNone(after, self.note(f"тот же SPEC {value!r} отказан после "
                                           f"answer: {after}"))
        self.assertEqual(added, [], self.note("добавки нет"))

        other = self.declared_task([self.live_task()])
        extra = self.live_task()
        declared = merge_after.stored(store.get_task(self.conn, other)["merge_after"])
        _, unjustified = self.refusal(other, merge_after.column(declared + [extra]))
        self.assertEqual(
            unjustified,
            f"{FIELD} SPEC добавляет зависимости сверх заявленных Оператором без "
            f"обоснования: {extra} — назови каждую в разделе «## Обоснование "
            f"зависимостей мержа» SPEC", self.note("отказ о добавке"))

        for dep_state in ("killed", "in_dev"):
            with self.subTest(dependency=dep_state):
                dep = self.live_task()
                gate = self.live_task()
                self.conn.execute("UPDATE tasks SET state=? WHERE id=?",
                                  (dep_state, dep))
                self.conn.execute("UPDATE tasks SET state='merge_gate', "
                                  "merge_after=? WHERE id=?", (dep, gate))
                self.conn.commit()
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    refused = merge_after.merge_gate_refuses(
                        self.conn, gate, store.get_task(self.conn, gate))
                if dep_state == "killed":
                    action = "approve отклонён: зависимость мержа убита"
                    reason = (f"зависимость мержа не завершится: {dep} (killed) — "
                              f"сними или замени её ответом Оператора: artel.py "
                              f"answer {gate} <файл> со строкой «{MANDATE} <id>, "
                              f"…» (или «{MANDATE} нет»)")
                else:
                    action = "approve отклонён: зависимости мержа не в done"
                    reason = (f"ждёт мержа зависимостей: {dep} (in_dev) — повтори, "
                              f"когда они будут в done: artel.py approve {gate}")
                rows = store.task_steps(self.conn, gate)
                note = self.note(f"вывод: {buf.getvalue()!r}")
                self.assertTrue(refused, note)
                self.assertEqual((rows[-1]["action"], rows[-1]["detail"]),
                                 (action, reason), note)
                self.assertEqual(buf.getvalue(), f"[{gate}] {action}: {reason}\n",
                                 note)


if __name__ == "__main__":
    unittest.main()
