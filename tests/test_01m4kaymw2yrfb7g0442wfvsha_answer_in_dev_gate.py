"""ANSWER Оператора в `in_dev` — основание шага developer, а не переход по готовым артефактам.

Рубеж `in_dev -> verifying` отклоняет переход, пока в журнале задачи есть
запись ANSWER Оператора, сделанная после последнего завершённого шага
developer: отказ класса «чинит роль», текст называет `ANSWER-n.md`. Цикл
`auto` на этот отказ запускает шаг developer (бриф несёт ANSWER), повтор
того же отказа после шага developer в этом визите — остановка цикла. После
шага developer, начатого позже ANSWER, переход идёт по обычным условиям;
задача без ANSWER и задача с ANSWER, отработанным до текущего входа в
`in_dev`, проходят как прежде. Ручной `advance` держится тем же гейтом.

Группа: долгоживущий
Красен до реализации: рубеж in_dev -> verifying журнал ANSWER не смотрит — advance с неотработанным указанием уводит задачу в verifying («шаг developer не нужен» у auto), отказа с именем ANSWER-n.md нет — AC-1, AC-2, AC-4, AC-6 падают; AC-3 и AC-5 держат сегодняшнее поведение и зелены с рождения.

Песочница — `tests.sandbox.LightTransitionSandbox` (связка «команда —
FSM — журнал»): SPEC.md (`schema_version: 1`, без планки) и PLAN.md
задачи лежат на диске `config.TASKS/<id>/`, FSM читает их через
`disk_backed_show`. Задача входит в `in_dev` штатным `approve` гейта SPEC.
ANSWER даёт штатная команда `answer` (файл указания без строк мандатов):
её запись в ссылку документов подменена записью файла на тот же диск
(`artifact_branch.commit_files`/`artifact_branch.ls_tree`), так что
`ANSWER-n.md` видят и FSM, и бриф. Шаг developer — подменённый
`runner.cmd_run`: журналирует `agent run started`/`agent run finished`
под ролью developer, как настоящий успешный шаг, кода не меняет и
запоминает состояние задачи и бриф `brief.developer_brief` на момент шага.
Подменены только проверки вне предмета: отставание ветки от main
(`rev-list --count` -> 0) и Draft MR форжа. Чтобы цикл `auto` кончился,
первый `advance` из `verifying` уводит задачу в ручной гейт `acceptance`.
Тексты указаний, число ANSWER и порядок случаев — от зерна; зерно
печатается и входит в текст каждого провала.
"""
import os
import random
import signal
import subprocess
import unittest
from pathlib import PurePosixPath
from unittest import mock

from orchestrator import (answer, auto, brief, catalog, config, fsm,
                          github_adapter, runner, store)
from orchestrator.advance_gates import refusal_classes
from tests.sandbox import (LightTransitionSandbox, capture_new_task_id,
                           disk_backed_ls_tree_files,
                           seed_developer_brief_fixtures)

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
---

# SPEC: фикстура ANSWER в in_dev

## Контекст

Фикстура.

## Требования

1. Фикстура.

## Критерии приёмки

Фикстура.

## Не входит

Ничего.
"""

PLAN_TEXT = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: фикстура ANSWER в in_dev

## Подход

Фикстура.

## Шаги

1. Фикстура.

## Покрытие требований

Фикстура.

## Влияние на систему

- Порядок мержа не меняется (фикстура {marker}).
"""

WORDS = ("причина", "падение", "красный", "импорт", "порядок", "модуль",
         "ветка", "журнал", "проверка", "сборка", "тест", "шаг")

NOT_NEEDED = "шаг developer не нужен"
REFUSAL_PREFIX = "переход отклонён"
STOP_ACTION = "auto остановлен"
MANUAL_STOP = "acceptance"


class AnswerGateSandbox(LightTransitionSandbox):
    """Задача в `in_dev` после `approve` гейта SPEC, `answer` и шаг
    developer — штатными командами поверх лёгкой песочницы."""

    def setUp(self):
        super().setUp()
        seed_developer_brief_fixtures(self.root)
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        previous = signal.getsignal(signal.SIGTERM)
        self.addCleanup(signal.signal, signal.SIGTERM, previous)
        self.in_repo_handlers.append(self.branch_not_behind)
        self.real_advance = fsm.cmd_advance
        self.steps: list = []
        self.after_step = None
        patchers = (
            mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}),
            mock.patch.object(github_adapter, "ensure_draft_mr",
                              lambda conn, task_id, t: None),
            mock.patch("orchestrator.artifact_branch.commit_files",
                       self.commit_to_disk),
            mock.patch("orchestrator.artifact_branch.ls_tree",
                       lambda task_id, rev, rel_dir:
                       disk_backed_ls_tree_files(rev, rel_dir)),
            mock.patch.object(fsm, "cmd_advance", self.advance_until_verifying),
            mock.patch.object(runner, "cmd_run", self.developer_step),
        )
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.counter = 0

    # --- подмены -------------------------------------------------------------

    @staticmethod
    def branch_not_behind(repo, *args):
        """Ветка задачи не отстала от main (`rev-list --count` -> 0)."""
        if args[:2] == ("rev-list", "--count"):
            return subprocess.CompletedProcess(list(args), 0, "0\n", "")
        return None

    def commit_to_disk(self, task_id, files, message, *args, **kwargs) -> str:
        """Запись документов задачи — на диск `config.TASKS`, откуда их
        читает песочница вместо ссылки документов."""
        for rel, text in files.items():
            path = config.TASKS.joinpath(*PurePosixPath(rel).parts[1:])
            path.parent.mkdir(parents=True, exist_ok=True)
            data = text if isinstance(text, str) else text.decode("utf-8")
            path.write_text(data, encoding="utf-8")
        return "c0ffee" + f"{self.rng.randrange(1 << 40):010x}"

    def advance_until_verifying(self, task_id, *args, **kwargs):
        """Настоящий `advance`; из `verifying` — в ручной гейт, чтобы цикл
        `auto` кончился, не опрашивая CI."""
        task_id = store.resolve_task_id(self.conn, task_id)
        if store.get_task(self.conn, task_id)["state"] == "verifying":
            store.set_state(self.conn, task_id, MANUAL_STOP, "fsm",
                            expected_state="verifying", detail="сценарий теста")
            return False
        return self.real_advance(task_id, *args, **kwargs)

    def developer_step(self, task_id, *args, **kwargs) -> None:
        """Шаг developer: запоминает состояние и бриф, журналирует старт и
        успешное завершение шага; кода не меняет."""
        task_id = store.resolve_task_id(self.conn, task_id)
        if len(self.steps) > config.AUTO_MAX_STEPS + 1:
            raise AssertionError(self.note("цикл не остановился: шагов developer "
                                           f"больше {config.AUTO_MAX_STEPS + 1}"))
        t = store.get_task(self.conn, task_id)
        store.journal(self.conn, task_id, "developer", "agent run started",
                      "тестовая заглушка шага developer")
        self.steps.append({"task": task_id, "state": t["state"],
                           "brief": brief.developer_brief(self.conn, task_id)})
        store.journal(self.conn, task_id, "developer", "agent run finished",
                      "rc=0, тестовая заглушка шага developer")
        if self.after_step is not None:
            self.after_step(task_id)

    # --- сценарий ------------------------------------------------------------

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def text(self) -> str:
        words = " ".join(self.rng.choice(WORDS)
                         for _ in range(self.rng.randrange(4, 10)))
        return f"Указание {self.rng.randrange(10 ** 9)}: {words}."

    def doc(self, task_id: str, name: str, text: str) -> None:
        tdir = config.TASKS / task_id
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / name).write_text(text, encoding="utf-8")

    def task_in_dev(self) -> str:
        """Свежая задача: SPEC и готовый PLAN на диске, `approve` гейта SPEC
        уводит её в `in_dev`; предпосылка — задача в `in_dev`."""
        self.counter += 1
        task_id = self.TASK if self.counter == 1 else self.new_task()
        self.doc(task_id, "SPEC.md", SPEC_TEXT.format(task=task_id))
        self.doc(task_id, "PLAN.md", PLAN_TEXT.format(
            task=task_id, marker=self.rng.randrange(1 << 30)))
        store.update_task(self.conn, task_id, state="spec_gate")
        out = self.capture(fsm.cmd_approve, task_id)
        self.assertEqual(self.state_of(task_id), "in_dev", self.note(
            f"предпосылка: approve гейта SPEC не увёл {task_id} в in_dev:\n{out}"))
        return task_id

    def new_task(self) -> str:
        _, task_id = capture_new_task_id(
            catalog.cmd_new, f"ANSWER в in_dev {self.rng.randrange(1 << 20)}")
        return task_id

    def give_answer(self, task_id: str) -> tuple[str, str]:
        """Штатный `answer` с файлом указания; (имя ANSWER-n.md, текст)."""
        text = self.text()
        path = self.root / f"otvet-{self.rng.randrange(1 << 40)}.txt"
        path.write_text(text + "\n", encoding="utf-8")
        before = self.last_id(task_id)
        out = self.capture(answer.cmd_answer, task_id, str(path))
        names = [PurePosixPath(r["detail"]).name for r in self.rows_since(task_id, before)
                 if r["actor"] == "operator" and r["action"].startswith("ANSWER создан")]
        self.assertEqual(len(names), 1, self.note(
            f"предпосылка: answer не записал ANSWER:\n{out}\n{self.journal(task_id)}"))
        self.assertTrue((config.TASKS / task_id / names[0]).is_file(),
                        self.note(f"предпосылка: {names[0]} нет на диске\n{out}"))
        return names[0], text

    def run_auto(self, task_id: str) -> str:
        return self.capture(auto.cmd_auto, task_id)

    def manual_advance(self, task_id: str) -> str:
        return self.capture(self.real_advance, task_id)

    def state_of(self, task_id: str) -> str:
        return store.get_task(self.conn, task_id)["state"]

    def last_id(self, task_id: str) -> int:
        rows = store.task_steps(self.conn, task_id)
        return rows[-1]["id"] if rows else 0

    def rows_since(self, task_id: str, since: int) -> list:
        return [r for r in store.task_steps(self.conn, task_id) if r["id"] > since]

    def journal(self, task_id: str) -> str:
        return "\n".join(f"{r['id']} {r['actor']} | {r['action']} | {r['detail'] or ''}"
                         for r in store.task_steps(self.conn, task_id))

    def refusals_naming(self, task_id: str, name: str, since: int = 0) -> list:
        """Отказы рубежа (актор fsm), чей текст называет `name`."""
        return [r for r in self.rows_since(task_id, since)
                if r["actor"] == "fsm" and r["action"].startswith(REFUSAL_PREFIX)
                and name in f"{r['action']} {r['detail'] or ''}"]

    def steps_of(self, task_id: str) -> list:
        return [s for s in self.steps if s["task"] == task_id]

    def journaled_developer_step(self, task_id: str) -> None:
        self.developer_step(task_id)

    def assert_went_to_verifying(self, task_id: str, since: int, out: str,
                                 why: str, final: str = "verifying") -> None:
        """Переход в `verifying` состоялся (`final` — состояние, где задача
        оказалась: у цикла `auto` сценарий уводит её из `verifying` в ручной
        гейт), отказа с именем ANSWER нет."""
        rows = self.rows_since(task_id, since)
        context = self.note(f"{why}\nвывод:\n{out}\nжурнал:\n{self.journal(task_id)}")
        self.assertEqual(self.state_of(task_id), final, context)
        self.assertTrue([r for r in rows if r["action"] == "state -> verifying"],
                        context)
        self.assertFalse([r for r in rows if r["actor"] == "fsm"
                          and r["action"].startswith(REFUSAL_PREFIX)
                          and "ANSWER-" in f"{r['action']} {r['detail'] or ''}"],
                         context)


class AutoRunsDeveloperOnAnswerTest(AnswerGateSandbox):

    def test_ac1_auto_runs_developer_step_instead_of_advancing_past_answer(self):
        """Случай 10.10: `approve` -> `in_dev`, указание `answer`, готовый PLAN — `auto` зовёт developer, не уходит в `verifying` до шага.

        Сценарий: задача после `approve` гейта SPEC в `in_dev`, PLAN.md
        готов к переходу; от зерна — до указания уже был шаг developer
        (ANSWER дан после него) или не было ни одного. Оператор даёт
        указание штатным `answer`, затем `auto`. Цикл запускает ровно один
        шаг developer, в момент шага задача ещё в `in_dev`; до завершения
        этого шага записи «шаг developer не нужен» и записи `state ->
        verifying` в журнале нет. (Та же запись после шага developer —
        штатный переход по обычным условиям, требование 4: цикл, отработав
        шаг роли, переходит предварительным advance.)

        Ловит мутацию: гейт не смотрит журнал ANSWER (рубеж `in_dev ->
        verifying` прежний) — предварительный advance уводит задачу в
        `verifying` до шага developer, в журнале «шаг developer не нужен:
        переход выполнен по готовым артефактам», шагов developer ноль.
        """
        task_id = self.task_in_dev()
        if self.rng.random() < 0.5:
            self.journaled_developer_step(task_id)
        steps_before = len(self.steps_of(task_id))
        name, _text = self.give_answer(task_id)
        since = self.last_id(task_id)

        out = self.run_auto(task_id)

        rows = self.rows_since(task_id, since)
        context = self.note(f"{name}\nвывод:\n{out}\nжурнал:\n{self.journal(task_id)}")
        steps = self.steps_of(task_id)[steps_before:]
        self.assertEqual(len(steps), 1, context)
        self.assertEqual(steps[0]["state"], "in_dev", context)
        finished = [r["id"] for r in rows if r["actor"] == "developer"
                    and r["action"] == "agent run finished"]
        self.assertTrue(finished, context)
        not_needed = [r["id"] for r in rows if r["action"].startswith(NOT_NEEDED)]
        entered = [r["id"] for r in rows if r["action"] == "state -> verifying"]
        for row_id in not_needed + entered:
            self.assertGreater(row_id, finished[0], context)


class RefusalClassAndBriefTest(AnswerGateSandbox):

    def test_ac2_refusal_is_role_fixable_and_the_step_brief_carries_the_answer(self):
        """Отказ рубежа по неотработанному ANSWER — класса «чинит роль»; бриф шага developer несёт текст ANSWER.

        Сценарий: задача в `in_dev` с готовым PLAN, Оператор даёт указание
        `answer` (случайный текст), затем `auto`. В журнале есть отказ
        рубежа (актор fsm), называющий `ANSWER-n.md`;
        `refusal_classes.refusal_class` его действия — «чинит роль»; бриф
        `brief.developer_brief`, собранный на запущенном шаге developer,
        содержит текст указания.

        Ловит мутацию: действие нового отказа не внесено в перечень
        `refusal_classes.REFUSAL_CLASSES` — класс по умолчанию «чинит
        Оператор», `auto` останавливается без шага developer; либо отказа
        нет вовсе — задача уходит в `verifying`, отказа с именем ANSWER в
        журнале нет.
        """
        task_id = self.task_in_dev()
        name, text = self.give_answer(task_id)
        since = self.last_id(task_id)

        out = self.run_auto(task_id)

        context = self.note(f"{name}\nвывод:\n{out}\nжурнал:\n{self.journal(task_id)}")
        refusals = self.refusals_naming(task_id, name, since)
        self.assertTrue(refusals, context)
        for row in refusals:
            self.assertEqual(refusal_classes.refusal_class(row["action"]),
                             refusal_classes.ROLE_FIXES, context)
        steps = self.steps_of(task_id)
        self.assertTrue(steps, context)
        self.assertIn(text, steps[0]["brief"], context)


class DeveloperStepAfterAnswerPassesTest(AnswerGateSandbox):

    def test_ac3_developer_step_started_after_answer_lets_the_transition_through(self):
        """Шаг developer, начатый после ANSWER (без правки кода), — `advance` уводит задачу в `verifying`.

        Сценарий: задача в `in_dev`; от зерна 1–3 раунда «указание
        `answer` — шаг developer» (шаг кода не меняет), последний раунд
        всегда кончается шагом developer. Ручной `advance` (от зерна — или
        цикл `auto`) переводит задачу в `verifying`: запись `state ->
        verifying` есть, отказа с именем ANSWER нет.

        Ловит мутацию: гейт сравнивает ANSWER не с последним шагом
        developer, а с первым (или с коммитом кода developer) — шаг без
        правки кода не снимает отказ, задача остаётся в `in_dev` с отказом
        «ANSWER-n.md».
        """
        task_id = self.task_in_dev()
        for _ in range(self.rng.randint(1, 3)):
            self.give_answer(task_id)
            self.journaled_developer_step(task_id)
        since = self.last_id(task_id)
        via_auto = self.rng.random() < 0.5
        steps_before = len(self.steps_of(task_id))
        out = (self.run_auto if via_auto else self.manual_advance)(task_id)

        self.assert_went_to_verifying(
            task_id, since, out, f"через {'auto' if via_auto else 'advance'}",
            final=MANUAL_STOP if via_auto else "verifying")
        self.assertEqual(len(self.steps_of(task_id)), steps_before, self.note(
            f"шаг developer повторён, хотя ANSWER уже отработан\n{out}"))


class RepeatedAnswerRefusalStopsAutoTest(AnswerGateSandbox):

    def test_ac4_same_refusal_after_developer_step_stops_auto(self):
        """Тот же отказ по ANSWER после шага developer в этом визите — `auto` встаёт, второго шага developer нет.

        Сценарий: задача в `in_dev` с готовым PLAN; указание `answer`, затем
        `auto`. Сразу после шага developer Оператор даёт ещё одно указание
        (новый ANSWER позже шага) — следующий предварительный `advance`
        отказывает тем же действием. Цикл делает ровно один шаг developer,
        задача остаётся в `in_dev`, в журнале запись «auto остановлен».

        Ловит мутацию: действие нового отказа отнесено к подклассу «роль
        ещё не закончила» (`ROLE_NOT_FINISHED_REFUSAL_ACTIONS`), который
        освобождён от повтор-остановки, — цикл запускает второй шаг
        developer подряд по тому же отказу.
        """
        task_id = self.task_in_dev()
        self.give_answer(task_id)
        late = []

        def answer_after_first_step(step_task):
            if not late:
                late.append(self.give_answer(step_task)[0])

        self.after_step = answer_after_first_step
        since = self.last_id(task_id)

        out = self.run_auto(task_id)

        context = self.note(f"вывод:\n{out}\nжурнал:\n{self.journal(task_id)}")
        self.assertEqual(len(late), 1, context)
        self.assertTrue(self.refusals_naming(task_id, late[0], since), context)
        self.assertEqual(len(self.steps_of(task_id)), 1, context)
        self.assertEqual(self.state_of(task_id), "in_dev", context)
        self.assertTrue([r for r in self.rows_since(task_id, since)
                         if r["action"] == STOP_ACTION], context)


class NoUnprocessedAnswerPassesTest(AnswerGateSandbox):

    def test_ac5_task_without_answer_passes_as_today(self):
        """Задача без ANSWER — ручной `advance` из `in_dev` уводит её в `verifying` без отказа.

        Сценарий: задача после `approve` гейта SPEC в `in_dev` с готовым
        PLAN; от зерна — до `advance` был шаг developer или не было. ANSWER
        нет. После `advance` задача в `verifying`, отказа с именем ANSWER нет.

        Ловит мутацию: гейт отказывает при отсутствии шага developer в
        визите независимо от ANSWER — задача без ANSWER и без шага остаётся
        в `in_dev`.
        """
        task_id = self.task_in_dev()
        if self.rng.random() < 0.5:
            self.journaled_developer_step(task_id)
        since = self.last_id(task_id)

        out = self.manual_advance(task_id)

        self.assert_went_to_verifying(task_id, since, out, "задача без ANSWER")

    def test_ac5_answer_processed_before_current_in_dev_entry_passes(self):
        """ANSWER, отработанный шагом developer до текущего входа в `in_dev`, — переход без отказа.

        Сценарий: задача в `in_dev`; указание `answer`, шаг developer; затем
        задача покидает `in_dev` (эскалация) и возвращается в него — новый
        визит без новых ANSWER и без нового шага developer. Ручной
        `advance` уводит её в `verifying`, отказа с именем ANSWER нет.

        Ловит мутацию: гейт смотрит ANSWER не относительно последнего шага
        developer, а относительно входа в текущий визит `in_dev` (или
        отказывает на любом ANSWER в журнале) — отработанный ANSWER снова
        даёт отказ, задача остаётся в `in_dev`.
        """
        task_id = self.task_in_dev()
        name, _text = self.give_answer(task_id)
        self.journaled_developer_step(task_id)
        store.set_state(self.conn, task_id, "escalated", "fsm",
                        expected_state="in_dev", detail="сценарий теста: эскалация")
        store.set_state(self.conn, task_id, "in_dev", "operator",
                        expected_state="escalated",
                        detail="сценарий теста: возврат в in_dev")
        since = self.last_id(task_id)

        out = self.manual_advance(task_id)

        self.assert_went_to_verifying(task_id, since, out,
                                      f"{name} отработан до входа в визит")


class ManualAdvanceRefusedTest(AnswerGateSandbox):

    def test_ac6_manual_advance_with_unprocessed_answer_is_refused_naming_it(self):
        """Ручной `advance` в `in_dev` при неотработанном ANSWER — отказ с именем `ANSWER-n.md`, задача в `in_dev`.

        Сценарий: задача в `in_dev` с готовым PLAN; от зерна 0–2 раунда
        «указание — шаг developer», затем последнее указание без шага.
        Ручной `advance`: задача остаётся в `in_dev`, перехода в `verifying`
        нет, в журнале отказ (актор fsm), чей текст называет имя последнего
        `ANSWER-n.md`.

        Ловит мутацию: гейт держит только цикл `auto` (стоит в
        `auto._pre_advance_step`, а не в рубеже FSM) — ручной `advance`
        уводит задачу в `verifying`; либо текст отказа называет первый
        ANSWER журнала, а не неотработанный — имени последнего в отказе нет.
        """
        task_id = self.task_in_dev()
        for _ in range(self.rng.randint(0, 2)):
            self.give_answer(task_id)
            self.journaled_developer_step(task_id)
        name, _text = self.give_answer(task_id)
        since = self.last_id(task_id)

        out = self.manual_advance(task_id)

        rows = self.rows_since(task_id, since)
        context = self.note(f"{name}\nвывод:\n{out}\nжурнал:\n{self.journal(task_id)}")
        self.assertEqual(self.state_of(task_id), "in_dev", context)
        self.assertFalse([r for r in rows if r["action"] == "state -> verifying"],
                         context)
        self.assertTrue(self.refusals_naming(task_id, name, since), context)


if __name__ == "__main__":
    unittest.main()
