"""Пробный период набора задачи, автоматическая приостановка пары набора,
команда `pair-resume` и чистота прогона канарейки с ожидаемой эскалацией.

Группа: долгоживущий

Красен до реализации: автогейт отказывает любой задаче с набором безусловной причиной «приёмка задачи с набором только ручная» (нет ни «пробная задача набора S, N из 3», ни прохода четвёртой задачи), возвраты ревью и отказ автогейта пару не приостанавливают (`new --set` проходит, алерта нет), команды `pair-resume` в диспетчере `artel.main` нет, а `unclean_reason` засчитывает чистым прогон с выполненной ожидаемой эскалацией при `escalations > 1`.

Планка провалидирована временным стабом реализации (все методы зелёные в
двенадцати прогонах с разными зёрнами; мутации стаба — счётчик без
прибавки единицы, счёт канареечных задач и счёт по имени набора,
приостановка по любой вине и пара не той роли, `pair-resume` без отметки
снятия и без записи журнала, одобрение как возврат, одиночный возврат,
шаг и `new --set` без сверки приостановки, прежнее `unclean_reason` —
красили соответствующие методы; стаб удалён, код репозитория не тронут).

Публичная поверхность, которую читает этот файл (SPEC называет команды и
поведение, но не внутренние имена):

- `artel.py new <название> --tz <файл ТЗ> --set <набор>` — заведение
  задачи с набором; отказ `new --set` — наблюдаемое следствие
  автоматической приостановки пары (в `model_sets.yaml` пара остаётся
  `state: допущена`, значит отказ даёт только запись пульта в БД);
- `artel.py pair-resume <роль> <модель> "<решение>"`;
- шаг роли — `runner.cmd_run(<id>)` с подменённым `runner.spawn_agent`:
  модель шага — значение `--model` в argv;
- возврат ревью — `fsm.cmd_advance` из `review` с вердиктом
  `changes_requested` в REVIEW.md свежей итерации (задача уходит в
  `in_dev`); одобрение — тот же вызов с `approved`;
- приёмка — вход в `acceptance` из `review` публичным `fsm.cmd_advance`
  при политике гейта `auto` (`gates.policy`), исходе полного набора
  (`acceptance.full_suite`) и worktree на ветке задачи
  (`workspace.on_task_branch`);
- журнал — таблица `steps` (`store.journal`/`store.task_steps`), алерты —
  `store.alerts_since`/`store.max_alert_id`, строки задач —
  `store.all_tasks`/`store.update_task`;
- чистота прогона — `models.unclean_reason`, `models.clean_run`,
  `models.pair_admission` над строками `store.all_canary_runs`.

Окружение — фикстуры `tests/sandbox.py` (`LightTransitionSandbox`, каталог
моделей с третьей моделью раздела `claude`, карта исполнителей фикстуры:
боевая модель каждой agent-роли — `FIXTURE_TIER_MODEL`). `model_sets.yaml`
пишется в корень песочницы (`models.model_sets_path()`); набор допущен
проверкой части 1, когда его не-боевые пары записаны `state: допущена` и
есть зелёный прогон набором целиком на шаблоне класса `трудный`.

Имена наборов, модели пар, число задач в `done`, шум счётчика, порядок
случаев и текст решения выбираются случайно; зерно печатается и входит в
текст провала.
"""
import contextlib
import io
import os
import random
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, artel, config, fsm, gates, models,
                          runner, store, workspace)
from tests.sandbox import (CATALOG_FIXTURE_TEXT, FIXTURE_OTHER_MODEL,
                           FIXTURE_ROLES, FIXTURE_TIER_MODEL, FakeProc,
                           LightTransitionSandbox, event,
                           TimeWithSleep, seed_developer_brief_fixtures,
                           sync_spec_from_worktree)

#: Корень репозитория — источник `templates/`/`skills/` для брифа шага.
REPO_ROOT = Path(__file__).resolve().parent.parent

#: agent-роли фикстуры карты исполнителей.
AGENT_ROLES = tuple(name for name, fields in FIXTURE_ROLES.items()
                    if fields.get("executor") == "agent")

#: Третья модель раздела `claude` каталога сценария — вторая не-боевая
#: модель рядом с `FIXTURE_OTHER_MODEL`.
GAMMA = "model-gamma-probnyy"
GAMMA_BLOCK = f"""\
      {GAMMA}:
        min_cli_version: 1.0.0
        status: supported
        list_price_usd_per_mtok:
          input: 3.0
          output: 15.0
          cache_write: 3.75
          cache_read: 0.30
        price_date: 2026-09-20
"""
_OTHER_ANCHOR = f"      {FIXTURE_OTHER_MODEL}:\n"
CATALOG_WITH_GAMMA = CATALOG_FIXTURE_TEXT.replace(
    _OTHER_ANCHOR, GAMMA_BLOCK + _OTHER_ANCHOR, 1)

#: Не-боевые модели сценариев.
SET_MODELS = (FIXTURE_OTHER_MODEL, GAMMA)

ADMITTED = "допущена"
SUSPENDED = "приостановлена"

#: Число пробных задач набора — ADR-0019 п.5 (SPEC, «Не входит»: числа
#: допуска не меняются).
TRIAL_TASKS = 3

#: Фраза безусловной ручной приёмки части 2 — требование 2 её снимает.
OLD_MANUAL_PHRASE = "только ручная"

REVIEW_TEXT = """---
task: {task}
type: review
author_role: reviewer
status: {status}
iteration: {iteration}
schema_version: 2
---

# REVIEW: песочница

## Соответствие SPEC

{conformity}

## Замечания

{remarks}

## Проверено исполнением

Прогон планки песочницы.

## Вердикт

{status}
"""

#: Строка ручного критерия планки песочницы собирается из частей: целой
#: строкой в исходнике её прочёл бы разбор пометок самой планки этой задачи.
MANUAL_MARK = "# AC" + "-1: " + "manual" + " — визуальный результат проверяет Оператор"

MANUAL_PLANK = f'''"""Планка песочницы с ручным критерием."""
import unittest

{MANUAL_MARK}


class ManualPlankTest(unittest.TestCase):

    def test_stub(self):
        pass
'''


def model_sets_text(sets: dict, pairs: dict, templates: dict) -> str:
    """Текст `model_sets.yaml` в подмножестве YAML пульта."""
    lines = ["sets:"]
    for name, members in sets.items():
        lines.append(f"  {name}:")
        lines += [f"    {role}: {model}" for role, model in members.items()]
    lines.append("pairs:")
    for role, entries in pairs.items():
        lines.append(f"  {role}:")
        for model, state in entries.items():
            lines += [f"    {model}:", "      date: 2026-10-01",
                      "      basis: решение Оператора",
                      f"      state: {state}"]
    lines.append("canary_templates:")
    lines += [f"  {title}: {cls}" for title, cls in templates.items()]
    return "\n".join(lines) + "\n"


def result_event(**fields) -> str:
    return event(type="result", subtype="success", is_error=False,
                 result="готово", **fields)


def full_suite_run(green: bool, detail: str) -> acceptance.FullSuiteRun:
    outcome = (acceptance.FULL_SUITE_GREEN if green
               else acceptance.FULL_SUITE_RED)
    return acceptance.FullSuiteRun(green, outcome, "1 passed" if green
                                   else "1 failed", None, detail)


GREEN_SUITE = full_suite_run(True, "зелёный прогон")
RED_SUITE = full_suite_run(False, "полный набор tests/ красный: 1 failed")


class SetSandbox(LightTransitionSandbox):
    """Лёгкая песочница переходов с брифом шага и файлом наборов: CLI
    агента подменён (`runner.spawn_agent`), токен слота — `tok-test`,
    предполёт окружения пуст. Лимит итераций ревью поднят до числа, при
    котором три возврата подряд остаются возвратами в `in_dev` (сам лимит
    — крутилка Оператора, предмет этого файла — не он)."""

    TOKEN = "tok-test"

    def setUp(self):
        super().setUp()
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates",
                        dirs_exist_ok=True)
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills",
                        dirs_exist_ok=True)
        seed_developer_brief_fixtures(self.root)
        for target, attr, value in (
                (runner, "time", TimeWithSleep(lambda _: None)),
                (runner.keychain, "token", lambda slot: self.TOKEN),
                (config, "LIMIT_REVIEW_ITERS",
                 max(config.LIMIT_REVIEW_ITERS, 4))):
            patcher = mock.patch.object(target, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        preflight = mock.patch("orchestrator.doctor.preflight_checks",
                               lambda role, target, **step: [])
        preflight.start()
        self.addCleanup(preflight.stop)
        self.neighbour = self.TASK

        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rnd = random.Random(self.seed)
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        env.start()
        self.addCleanup(env.stop)
        for name in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY"):
            os.environ.pop(name, None)
        self.assertIn(GAMMA, CATALOG_WITH_GAMMA, "якорь каталога фикстуры")
        self.use_catalog_fixture(CATALOG_WITH_GAMMA)
        self.hard = f"canary-trudnyy-{self.rnd.randrange(10 ** 6)}"
        self.medium = f"canary-sredniy-{self.rnd.randrange(10 ** 6)}"
        self.fast = f"canary-bystryy-{self.rnd.randrange(10 ** 6)}"
        self.templates = {self.hard: "трудный", self.medium: "средний",
                          self.fast: "быстрый"}
        self.sets, self.pairs = {}, {}
        self.run_no = 0
        self.title_no = 0
        self.write_model_sets()

    # ------------------------------------------------------------- файл

    def note(self, extra: str = "") -> str:
        return f"зерно {self.seed}. {extra}"

    def set_name(self, stem: str = "nabor") -> str:
        return f"{stem}-{self.rnd.randrange(10 ** 6)}"

    def write_model_sets(self) -> None:
        models.model_sets_path().write_text(
            model_sets_text(self.sets, self.pairs, self.templates),
            encoding="utf-8")

    def model_sets_bytes(self) -> bytes:
        return models.model_sets_path().read_bytes()

    def register_set(self, name: str, members: dict) -> None:
        """Набор в `sets:`, его не-боевые пары — `state: допущена`, зелёный
        прогон набором целиком на трудном шаблоне."""
        self.sets[name] = dict(members)
        for role, model in members.items():
            if model != FIXTURE_TIER_MODEL:
                self.pairs.setdefault(role, {})[model] = ADMITTED
        self.add_run(self.hard, members)
        self.write_model_sets()

    def add_run(self, title: str, members: dict, **fields) -> None:
        """Строка `canary_runs`: сводка «роль → модель» — боевая модель
        каждой agent-роли, поверх неё — `members`."""
        self.run_no += 1
        pairs = {role: FIXTURE_TIER_MODEL for role in AGENT_ROLES}
        pairs.update(members)
        named = ", ".join(f"{role} → {model}" for role, model in pairs.items())
        row = {"review_iterations": 0, "escalations": 0,
               "expected_escalation": None, "actual_escalation": False,
               "marker_mismatch": False, "verdict": "green"}
        row.update(fields)
        store.insert_canary_run(
            store.db(), f"stamp-{self.run_no}", title, f"T-RUN-{self.run_no}",
            10, 1.0, row["review_iterations"], row["escalations"],
            "merge_gate", row["expected_escalation"],
            row["actual_escalation"], row["marker_mismatch"],
            main_sha="0" * 40, verdict=row["verdict"],
            models_summary=f"{named}; источник: слой пульта")

    # ---------------------------------------------------------- команды

    def cli(self, *argv: str) -> tuple:
        """(успех, stdout + текст отказа) команды `artel.py <argv>`."""
        out = io.StringIO()
        ok, tail = True, ""
        with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                contextlib.redirect_stdout(out):
            try:
                artel.main()
            except SystemExit as exc:
                if exc.code not in (0, None):
                    ok, tail = False, f"\n{exc.code}"
        return ok, out.getvalue() + tail

    def task_ids(self) -> list:
        return [row["id"] for row in store.all_tasks(store.db())]

    def new_task(self, set_name: str) -> tuple:
        """(успех, вывод, id задачи либо `None`) — `new <название> --tz
        <файл> --set <набор>`."""
        self.title_no += 1
        title = f"Задача набора {self.title_no}-{self.rnd.randrange(10 ** 6)}"
        tz = config.ROOT / ".artel" / f"tz-{self.title_no}.md"
        tz.parent.mkdir(parents=True, exist_ok=True)
        tz.write_text("Учебное ТЗ задачи на наборе моделей.\n", encoding="utf-8")
        ok, output = self.cli("new", title, "--tz", str(tz), "--set", set_name)
        ids = [row["id"] for row in store.all_tasks(store.db())
               if row["title"] == title]
        return ok, output, (ids[0] if ids else None)

    def new_set_task(self, set_name: str) -> str:
        ok, output, task_id = self.new_task(set_name)
        self.assertTrue(ok and task_id, self.note(f"new --set {set_name}:\n"
                                                  f"{output}"))
        return task_id

    def done_task(self, set_name: str, *, canary: bool = False) -> str:
        """Задача набора, закрытая в `done` (настоящая либо канареечная)."""
        task_id = self.new_set_task(set_name)
        store.update_task(store.db(), task_id, state="done",
                          is_canary=int(canary))
        return task_id

    def pair_resume(self, role: str, model: str, decision: str) -> tuple:
        return self.cli("pair-resume", role, model, decision)

    # ------------------------------------------------------- наблюдение

    def last_step_id(self, task_id: str) -> int:
        rows = store.task_steps(store.db(), task_id)
        return rows[-1]["id"] if rows else 0

    def steps_after(self, task_id: str, step_id: int) -> list:
        return [row for row in store.task_steps(store.db(), task_id)
                if row["id"] > step_id]

    @staticmethod
    def steps_text(rows) -> str:
        return "\n".join(f"{row['actor']} | {row['action']} | "
                         f"{row['detail'] or ''}" for row in rows)

    def alert_base(self) -> int:
        return store.max_alert_id(store.db())

    def alerts_after(self, base: int) -> list:
        return [f"{row['target'] or ''} | {row['kind']} | {row['source']} | "
                f"{row['message']}"
                for row in store.alerts_since(store.db(), base)]

    def alerts_naming(self, base: int, *needles: str) -> list:
        return [text for text in self.alerts_after(base)
                if all(needle in text for needle in needles)]

    def pair_blocked(self, role: str, model: str) -> tuple:
        """(отказал ли `new --set` по набору из одной пары «роль → модель»,
        вывод). Набор-зонд допущен проверкой части 1 (пара `допущена`,
        трудный прогон есть) — отказ даёт только приостановка пульта."""
        probe = self.set_name(f"zond-{role}")
        self.register_set(probe, {role: model})
        before = self.task_ids()
        ok, output, task_id = self.new_task(probe)
        if ok and task_id:
            return False, output
        self.assertEqual(before, self.task_ids(), self.note(
            f"отказ new --set {probe} оставил строку задачи:\n{output}"))
        return True, output

    def assert_pair_suspended(self, role: str, model: str, why: str) -> None:
        blocked, output = self.pair_blocked(role, model)
        self.assertTrue(blocked, self.note(
            f"{why}: пара {role} → {model} не приостановлена — new --set "
            f"принят:\n{output}"))

    def assert_pair_free(self, role: str, model: str, why: str) -> None:
        blocked, output = self.pair_blocked(role, model)
        self.assertFalse(blocked, self.note(
            f"{why}: пара {role} → {model} приостановлена:\n{output}"))

    # ----------------------------------------------------- шаги и вердикты

    def run_step(self, task_id: str) -> dict:
        """Шаг developer задачи в `in_dev`: argv запуска агента (`None` —
        агент не запускался), отказ шага, новые записи журнала. Задача
        уходит на ручной гейт — с дороги соседей."""
        conn = store.db()
        store.update_task(conn, task_id, state="in_dev", paused=0)
        sync_spec_from_worktree(task_id)
        plan_dir = self.wt_path / config.TASKS.name / task_id
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "PLAN.md").write_text("маркер\n", encoding="utf-8")
        before = self.last_step_id(task_id)
        calls = []

        def spawn(cmd, *args, **kwargs):
            calls.append(list(cmd))
            return FakeProc([result_event(total_cost_usd=0.1)])

        refusal = None
        buf = io.StringIO()
        with mock.patch.object(runner, "spawn_agent", side_effect=spawn), \
                contextlib.redirect_stdout(buf):
            try:
                runner.cmd_run(task_id)
            except SystemExit as exc:
                refusal = str(exc.code)
        store.update_task(conn, task_id, state="spec_gate")
        return {"argv": calls[0] if calls else None, "refusal": refusal,
                "output": buf.getvalue(),
                "rows": self.steps_after(task_id, before)}

    @staticmethod
    def step_model(step: dict):
        argv = step["argv"]
        if argv is None or "--model" not in argv:
            return None
        return argv[argv.index("--model") + 1]

    def assert_step_model(self, step: dict, model: str, why: str) -> None:
        self.assertIsNotNone(step["argv"], self.note(
            f"{why}: агент не запущен: {step['refusal']}\n{step['output']}"))
        self.assertEqual(self.step_model(step), model,
                         self.note(f"{why}: argv {step['argv']}"))

    def advance_review(self, task_id: str, status: str, *,
                       suite: acceptance.FullSuiteRun = GREEN_SUITE,
                       plank: str = None) -> tuple:
        """Вердикт ревьювера свежей итерации и `advance` из `review`:
        (состояние после, вывод + новые записи журнала)."""
        conn = store.db()
        row = store.get_task(conn, task_id)
        self.TASK = task_id
        self.tdir = config.TASKS / task_id
        self.write_acceptance_plank()
        if plank is not None:
            (self.tdir / "acceptance_tests" / "test_manual.py").write_text(
                plank, encoding="utf-8")
        approved = status == "approved"
        (self.tdir / "REVIEW.md").write_text(REVIEW_TEXT.format(
            task=task_id, status=status,
            iteration=(row["reviewed_iter"] or 0) + 1,
            conformity="Соответствует." if approved else "Частично.",
            remarks="Нет." if approved else "1. Поправить обработку ошибки."),
            encoding="utf-8")
        self.wt_path.mkdir(parents=True, exist_ok=True)
        store.update_task(conn, task_id, state="review")
        before = self.last_step_id(task_id)
        buf = io.StringIO()
        with mock.patch.object(gates, "policy", return_value=gates.AUTO), \
                mock.patch.object(acceptance, "full_suite", return_value=suite), \
                mock.patch.object(workspace, "on_task_branch", return_value=True), \
                contextlib.redirect_stdout(buf):
            fsm.cmd_advance(task_id)
        text = buf.getvalue() + "\n" + self.steps_text(
            self.steps_after(task_id, before))
        return store.get_task(store.db(), task_id)["state"], text

    def review_return(self, task_id: str) -> str:
        """Возврат ревью: `review -> in_dev` по `changes_requested`."""
        state, text = self.advance_review(task_id, "changes_requested")
        self.assertEqual(state, "in_dev", self.note(
            f"возврат ревью задачи {task_id} не дошёл до in_dev:\n{text}"))
        return text

    def dev_cycle(self, task_id: str, model: str) -> None:
        """Шаг developer на модели `model` набора и возврат ревью."""
        self.assert_step_model(self.run_step(task_id), model,
                               f"шаг developer задачи {task_id}")
        self.review_return(task_id)

    def enter_acceptance(self, task_id: str, **kwargs) -> tuple:
        return self.advance_review(task_id, "approved", **kwargs)


# ======================================================== пробный период


class TrialPeriodTest(SetSandbox):

    def trial_phrase(self, name: str, n: int) -> str:
        return f"пробная задача набора {name}, {n} из {TRIAL_TASKS}"

    def test_ac1_first_three_tasks_stay_on_manual_gate_with_counter(self):
        """Первые три настоящие задачи набора — ручной гейт со счётчиком.

        Сценарий: набор `S` (developer и, случайно, ещё роль на не-боевых
        моделях); три настоящие задачи `S` по очереди входят в
        `acceptance` при выполненных условиях автогейта, после входа
        каждая закрывается в `done`. Каждая остаётся в `acceptance`, а
        причина (вывод или журнал входа) несёт «пробная задача набора S, N
        из 3» с N = 1, 2, 3.

        Ловит мутацию: счётчик не прибавляет единицу к числу задач в
        `done` (N = 0, 1, 2); `done`-задачи не считаются (N всегда 1);
        третья задача уже проходит автогейт (сравнение `<= 2` вместо
        `< 3` по числу задач в `done`)."""
        name = self.set_name()
        members = {"developer": self.rnd.choice(SET_MODELS)}
        if self.rnd.random() < 0.5:
            other = self.rnd.choice([r for r in AGENT_ROLES if r != "developer"])
            members[other] = self.rnd.choice(SET_MODELS)
        self.register_set(name, members)
        for n in range(1, TRIAL_TASKS + 1):
            task = self.new_set_task(name)
            state, text = self.enter_acceptance(task)
            self.assertEqual(state, "acceptance", self.note(
                f"задача {n} набора прошла автогейт:\n{text}"))
            self.assertIn(self.trial_phrase(name, n), text, self.note(
                f"задача {n}: нет причины пробного периода:\n{text}"))
            store.update_task(store.db(), task, state="done")

    def test_ac2_counter_counts_only_done_real_tasks_of_same_composition(self):
        """Счётчик — только настоящие задачи в `done` с тем же составом.

        Сценарий: набор `S` с составом C1; k (случайно 0..2) настоящих
        задач C1 в `done`; шум: задачи C1 в других состояниях,
        канареечная задача C1 в `done`, настоящие задачи в `done` под тем
        же именем `S`, но с другим составом C2 (набор в файле временно
        переписан и возвращён к C1). Новая задача C1 входит в
        `acceptance`: причина — «пробная задача набора S, k+1 из 3»;
        `model_sets.yaml` после решения автогейта байт-в-байт прежний.

        Ловит мутацию: счёт по имени набора, а не по составу (C2
        засчитаны); канареечные или незакрытые задачи засчитаны (N больше
        k+1 либо автогейт пройден); счётчик записан в `model_sets.yaml`."""
        name = self.set_name()
        dev_model, other_model = self.rnd.sample(SET_MODELS, 2)
        c1 = {"developer": dev_model}
        c2 = {"developer": other_model}
        self.register_set(name, c1)
        k = self.rnd.randint(0, TRIAL_TASKS - 1)
        for _ in range(k):
            self.done_task(name)
        for state in self.rnd.sample(
                ["acceptance", "merge_gate", "killed", "in_dev", "escalated"],
                2):
            store.update_task(store.db(), self.new_set_task(name), state=state)
        self.done_task(name, canary=True)
        self.register_set(name, c2)
        for _ in range(self.rnd.randint(1, 2)):
            self.done_task(name)
        self.register_set(name, c1)
        task = self.new_set_task(name)
        before = self.model_sets_bytes()

        state, text = self.enter_acceptance(task)

        self.assertEqual(state, "acceptance", self.note(
            f"k={k}: задача прошла автогейт:\n{text}"))
        self.assertIn(self.trial_phrase(name, k + 1), text, self.note(
            f"k={k}: счётчик не по составу/состоянию/канарейке:\n{text}"))
        self.assertEqual(before, self.model_sets_bytes(), self.note(
            "model_sets.yaml изменён решением автогейта"))

    def test_ac3_fourth_task_passes_autogate_and_old_manual_reason_gone(self):
        """Четвёртая задача набора проходит автогейт; ручной причины нет.

        Сценарий: три настоящие задачи набора `S` в `done`; четвёртая
        задача `S` и задача другого набора `R` без задач в `done` входят
        в `acceptance` при выполненных общих условиях (порядок случаен),
        контроль — задача без набора. Четвёртая и контроль уходят в
        `merge_gate` автогейтом, задача `R` остаётся в `acceptance` с
        причиной пробного периода; фразы «только ручная» нет ни в одном
        выводе.

        Ловит мутацию: безусловный отказ части 2 оставлен (четвёртая
        остаётся в `acceptance`, фраза «только ручная» в выводе); порог
        пробного периода снят целиком (`R` проходит автогейт)."""
        name, other = self.set_name("s"), self.set_name("r")
        # Состав `R` обязан отличаться от `S`: счётчик идёт по составу, и
        # `R` с тем же составом законно унаследовал бы три задачи `S`.
        s_model, r_model = self.rnd.sample(SET_MODELS, 2)
        self.register_set(name, {"developer": s_model})
        self.register_set(other, {"developer": r_model})
        for _ in range(TRIAL_TASKS):
            self.done_task(name)
        fourth, trial = self.new_set_task(name), self.new_set_task(other)
        order = [fourth, trial, self.neighbour]
        self.rnd.shuffle(order)
        outcome = {task_id: self.enter_acceptance(task_id) for task_id in order}

        for task_id, why in ((fourth, f"четвёртая задача {name}"),
                             (self.neighbour, "задача без набора")):
            state, text = outcome[task_id]
            self.assertEqual(state, "merge_gate", self.note(f"{why}:\n{text}"))
        state, text = outcome[trial]
        self.assertEqual(state, "acceptance", self.note(f"набор {other}:\n{text}"))
        self.assertIn(self.trial_phrase(other, 1), text, self.note(text))
        for task_id, (_, text) in outcome.items():
            self.assertNotIn(OLD_MANUAL_PHRASE, text, self.note(
                f"{task_id}: осталась безусловная ручная приёмка:\n{text}"))


# ============================================== приостановка по возвратам


class ReviewReturnSuspensionTest(SetSandbox):

    def test_ac4_second_return_in_one_task_suspends_pair_with_alert(self):
        """Второй возврат ревью в одной задаче приостанавливает пару.

        Сценарий: набор `S` переводит developer на не-боевую модель `M`
        (случайно); настоящая задача `S` — два цикла «шаг developer на `M`
        → возврат ревью». После второго возврата: среди новых алертов есть
        алерт, называющий developer, `M`, `S` и задачу; `new --set` набором
        из пары developer → `M` (пара в файле `допущена`) отказывает;
        `model_sets.yaml` байт-в-байт прежний.

        Ловит мутацию: возвраты ревью не засчитываются паре (нет алерта,
        `new --set` принят); приостановка без алерта либо алерт без имени
        набора или задачи; приостановка записана правкой
        `model_sets.yaml`."""
        model = self.rnd.choice(SET_MODELS)
        name = self.set_name()
        self.register_set(name, {"developer": model})
        task = self.new_set_task(name)
        before = self.model_sets_bytes()
        base = self.alert_base()

        self.dev_cycle(task, model)
        self.dev_cycle(task, model)

        after = self.model_sets_bytes()
        alerts = self.alerts_after(base)
        self.assertTrue(self.alerts_naming(base, "developer", model, name, task),
                        self.note("нет алерта с ролью, моделью, набором и "
                                  "задачей:\n" + "\n".join(alerts)))
        self.assertEqual(before, after, self.note("model_sets.yaml изменён"))
        self.assert_pair_suspended("developer", model, "два возврата в задаче")

    def test_ac5_return_after_predecessor_return_suspends_single_does_not(self):
        """Возврат подряд за возвратом предыдущей задачи пары — приостановка.

        Сценарий (две независимые пары developer → `M1`/`M2`, модели
        случайны): (а) задача P на `M1` — шаг и один возврат: пара не
        приостановлена (одиночный возврат, предшественника нет); затем
        задача Q на той же паре (тот же набор либо другой набор с той же
        парой, случайно) — шаг и возврат: пара приостановлена, алерт
        называет developer и `M1`. (б) задача P2 на `M2` — шаг и одобрение
        ревью; задача Q2 на `M2` — шаг и возврат: пара не приостановлена,
        алерта о `M2` нет.

        Ловит мутацию: «подряд» не смотрит на предыдущую задачу пары
        (случай (а) не приостанавливает); одиночный возврат уже
        приостанавливает (P либо Q2 блокирует пару); одобренный
        предшественник засчитан как возврат (Q2 приостанавливает)."""
        m1, m2 = self.rnd.sample(SET_MODELS, 2)
        s1 = self.set_name("s1")
        self.register_set(s1, {"developer": m1})
        if self.rnd.random() < 0.5:
            q_set = s1
        else:
            q_set = self.set_name("s1b")
            other = self.rnd.choice([r for r in AGENT_ROLES if r != "developer"])
            self.register_set(q_set, {"developer": m1, other: m2})
        s2 = self.set_name("s2")
        self.register_set(s2, {"developer": m2})
        p, q = self.new_set_task(s1), self.new_set_task(q_set)
        p2, q2 = self.new_set_task(s2), self.new_set_task(s2)

        base = self.alert_base()
        self.dev_cycle(p, m1)
        self.assertFalse(self.alerts_naming(base, "developer", m1), self.note(
            "одиночный возврат поднял алерт:\n"
            + "\n".join(self.alerts_after(base))))
        self.assert_pair_free("developer", m1, "одиночный возврат без "
                              "предшественника")
        self.dev_cycle(q, m1)
        self.assertTrue(self.alerts_naming(base, "developer", m1), self.note(
            f"возврат подряд ({q_set}) без алерта:\n"
            + "\n".join(self.alerts_after(base))))
        self.assert_pair_suspended("developer", m1, "возврат подряд за "
                                   "возвратом предыдущей задачи")

        base = self.alert_base()
        self.assert_step_model(self.run_step(p2), m2, "шаг P2")
        state, text = self.enter_acceptance(p2)
        self.assertEqual(state, "acceptance", self.note(text))
        self.dev_cycle(q2, m2)
        self.assertFalse(self.alerts_naming(base, "developer", m2), self.note(
            "возврат после одобренного предшественника поднял алерт:\n"
            + "\n".join(self.alerts_after(base))))
        self.assert_pair_free("developer", m2, "предшественник одобрен")

    def test_ac6_next_developer_step_after_suspension_runs_on_combat_model(self):
        """После приостановки шаг developer той же задачи — на боевой модели.

        Сценарий: набор переводит developer на `M`; два возврата ревью в
        задаче приостанавливают пару; следующий шаг developer этой задачи
        идёт с `--model` боевой модели, среди записей журнала шага есть
        запись, называющая developer, `M`, боевую модель и причину
        (возвраты ревью), а записи старта шага с моделью `M` нет.

        Ловит мутацию: разрешение модели шага не сверяет приостановку
        пульта (шаг на `M` — в файле пара `допущена`); откат молчаливый
        либо запись не называет боевую модель или причину."""
        model = self.rnd.choice(SET_MODELS)
        name = self.set_name()
        self.register_set(name, {"developer": model})
        task = self.new_set_task(name)
        self.dev_cycle(task, model)
        self.dev_cycle(task, model)

        step = self.run_step(task)

        self.assert_step_model(step, FIXTURE_TIER_MODEL, "шаг после приостановки")
        rows = step["rows"]
        text = self.steps_text(rows)
        named = [row for row in rows
                 if all(needle in self.steps_text([row])
                        for needle in ("developer", model, FIXTURE_TIER_MODEL))
                 and "ревью" in self.steps_text([row])]
        self.assertTrue(named, self.note(
            f"нет записи с ролью, моделью набора, боевой моделью и причиной:"
            f"\n{text}"))
        started = [row for row in rows if row["action"] == "agent run started"]
        self.assertFalse(any(model in (row["detail"] or "") for row in started),
                         self.note(f"шаг стартовал на {model}:\n{text}"))


# =========================================== приостановка по отказу автогейта


class AutogateSuspensionTest(SetSandbox):

    def test_ac7_role_blame_refusal_suspends_guilty_pair_pult_does_not(self):
        """Отказ автогейта по вине роли приостанавливает пару виновной роли.

        Сценарий: набор `S` — developer → `Md`, test_author → `Mt`; три
        настоящие задачи `S` в `done` (пробный период пройден); четыре
        задачи `S` входят в `acceptance`: (1) бюджет задачи исчерпан
        (вина «пульт/пул») и (2) полный набор не зелёный с причиной вне
        перечней правила вины («не установлена») — ни одна пара не
        приостановлена, алертов о парах нет; затем (3) полный набор
        `tests/` красный (вина developer) — пара developer → `Md`
        приостановлена, пара test_author свободна, алерт называет
        developer и `Md`; (4) критерий `manual` в планке (вина test_author)
        — пара test_author → `Mt` приостановлена, алерт называет
        test_author и `Mt`.

        Ловит мутацию: отказ по вине роли не приостанавливает пару (3, 4);
        приостанавливается пара не той роли (developer за `manual`);
        вина «пульт/пул» или «не установлена» тоже приостанавливает (1,
        2)."""
        md, mt = (self.rnd.choice(SET_MODELS) for _ in range(2))
        name = self.set_name()
        self.register_set(name, {"developer": md, "test_author": mt})
        for _ in range(TRIAL_TASKS):
            self.done_task(name)
        budget_task, unknown_task, red_task, manual_task = (
            self.new_set_task(name) for _ in range(4))
        unknown_detail = f"прогон оборвался странно {self.rnd.randrange(10 ** 6)}"
        self.assertEqual(
            models.autogate_refusal_blame(
                models.AUTOGATE_REFUSAL_PREFIX + unknown_detail),
            models.BLAME_UNKNOWN, "фикстура причины «не установлена»")

        base = self.alert_base()
        row = store.get_task(store.db(), budget_task)
        store.update_task(store.db(), budget_task,
                          spent_usd=(row["budget_usd"] or 0.0) + 1.0)
        pult_cases = [
            ("пульт/пул", budget_task, {}),
            ("не установлена", unknown_task,
             {"suite": full_suite_run(False, unknown_detail)}),
        ]
        self.rnd.shuffle(pult_cases)
        for why, task, kwargs in pult_cases:
            state, text = self.enter_acceptance(task, **kwargs)
            self.assertEqual(state, "acceptance", self.note(f"{why}:\n{text}"))
        for role, model in (("developer", md), ("test_author", mt)):
            self.assertFalse(self.alerts_naming(base, role, model), self.note(
                f"отказ не по вине роли поднял алерт о паре {role}:\n"
                + "\n".join(self.alerts_after(base))))
        self.assert_pair_free("developer", md, "отказ «пульт/пул»/«не установлена»")
        self.assert_pair_free("test_author", mt, "отказ «пульт/пул»/«не установлена»")

        base = self.alert_base()
        state, text = self.enter_acceptance(red_task, suite=RED_SUITE)
        self.assertEqual(state, "acceptance", self.note(text))
        self.assertTrue(self.alerts_naming(base, "developer", md), self.note(
            "красный полный набор без алерта о паре developer:\n"
            + "\n".join(self.alerts_after(base))))
        self.assert_pair_suspended("developer", md, "красный полный набор")
        self.assert_pair_free("test_author", mt, "красный полный набор")

        base = self.alert_base()
        state, text = self.enter_acceptance(manual_task, plank=MANUAL_PLANK)
        self.assertEqual(state, "acceptance", self.note(text))
        self.assertTrue(self.alerts_naming(base, "test_author", mt), self.note(
            "критерий manual без алерта о паре test_author:\n"
            + "\n".join(self.alerts_after(base))))
        self.assert_pair_suspended("test_author", mt, "критерий manual")


# ================================================== new --set и pair-resume


class SuspendedPairCommandsTest(SetSandbox):

    def suspend_by_returns(self, model: str) -> tuple:
        """(набор, задача) — пара developer → `model` приостановлена двумя
        возвратами ревью в одной задаче набора."""
        name = self.set_name()
        members = {"developer": model}
        if self.rnd.random() < 0.5:
            other = self.rnd.choice([r for r in AGENT_ROLES if r != "developer"])
            members[other] = self.rnd.choice(SET_MODELS)
        self.register_set(name, members)
        task = self.new_set_task(name)
        self.dev_cycle(task, model)
        self.dev_cycle(task, model)
        return name, task

    def test_ac8_new_set_with_suspended_pair_refused_task_not_created(self):
        """`new --set` с автоматически приостановленной парой — отказ.

        Сценарий: пара developer → `M` набора `S` приостановлена двумя
        возвратами ревью; в `model_sets.yaml` у неё по-прежнему
        `state: допущена`. `new --set S` — отказ с ненулевым кодом, текст
        называет developer, `M` и приостановку; строк задач столько же,
        сколько до команды.

        Ловит мутацию: `new --set` сверяет только `model_sets.yaml`
        (задача заведена); проверка после заведения строки задачи; отказ
        не называет пару или причину."""
        model = self.rnd.choice(SET_MODELS)
        name, _ = self.suspend_by_returns(model)
        state = models.load_model_sets()[models.PAIRS_KEY]["developer"][model][
            models.PAIR_STATE_KEY]
        self.assertEqual(state, ADMITTED, self.note("пара в файле не допущена"))
        before = self.task_ids()

        ok, output, task_id = self.new_task(name)

        self.assertFalse(ok, self.note(f"new --set {name} принят:\n{output}"))
        self.assertIsNone(task_id, self.note(output))
        self.assertEqual(before, self.task_ids(), self.note("строка задачи"))
        for needle in ("developer", model, "приостанов"):
            self.assertIn(needle, output, self.note(f"нет «{needle}»:\n{output}"))

    def test_ac9_pair_resume_lifts_suspension_and_refuses_unsuspended(self):
        """`pair-resume` снимает приостановку; для свободной пары — отказ.

        Сценарий: пара developer → `M` набора `S` приостановлена двумя
        возвратами ревью. `pair-resume developer M "<решение>"` (текст
        решения случаен) — успех; среди новых записей журнала есть
        запись с developer, `M` и текстом решения; `new --set S` заводит
        задачу. Затем `pair-resume` для пары без автоматической
        приостановки (случайно: пара, ни разу не приостановленная, либо
        пара, записанная `state: приостановлена` только в файле) — отказ
        с ненулевым кодом, дамп БД до и после совпадает.

        Ловит мутацию: команда не снимает приостановку (`new --set`
        отказывает); снятие без записи в журнал или без текста решения;
        команда для неприостановленной пары завершается успехом либо
        пишет в БД."""
        model = self.rnd.choice(SET_MODELS)
        name, _ = self.suspend_by_returns(model)
        decision = f"разобрано Оператором {self.rnd.randrange(10 ** 6)}"
        conn = store.db()
        step_base = conn.execute("SELECT MAX(id) FROM steps").fetchone()[0] or 0

        ok, output = self.pair_resume("developer", model, decision)

        self.assertTrue(ok, self.note(f"pair-resume отказал:\n{output}"))
        rows = conn.execute("SELECT * FROM steps WHERE id > ? ORDER BY id",
                            (step_base,)).fetchall()
        self.assertTrue(any(all(needle in self.steps_text([row])
                                for needle in ("developer", model, decision))
                            for row in rows),
                        self.note("нет записи журнала с ролью, моделью и "
                                  f"решением:\n{self.steps_text(rows)}"))
        self.new_set_task(name)

        role = self.rnd.choice([r for r in AGENT_ROLES if r != "developer"])
        free_model = self.rnd.choice(SET_MODELS)
        if self.rnd.random() < 0.5:
            self.pairs.setdefault(role, {})[free_model] = SUSPENDED
            self.write_model_sets()
        dump_before = list(store.db().iterdump())
        ok, output = self.pair_resume(role, free_model, decision)
        self.assertFalse(ok, self.note(
            f"pair-resume {role} {free_model} без приостановки принят:\n"
            f"{output}"))
        self.assertEqual(dump_before, list(store.db().iterdump()),
                         self.note("отказ pair-resume записал в БД"))

    def test_ac10_returns_before_resume_do_not_count_as_consecutive(self):
        """После `pair-resume` одиночный возврат пару не приостанавливает.

        Сценарий: пара developer → `M` приостановлена двумя возвратами в
        задаче A; `pair-resume`; затем один новый возврат ревью на паре —
        случайно в той же задаче A (шаг снова на `M`) либо в новой задаче
        B набора. Пара не приостановлена (`new --set` принят), алерта о
        паре после снятия нет.

        Ловит мутацию: «подряд» считает возвраты до снятия приостановки —
        возврат после снятия сразу снова приостанавливает пару."""
        model = self.rnd.choice(SET_MODELS)
        name, task_a = self.suspend_by_returns(model)
        ok, output = self.pair_resume("developer", model, "разобрано")
        self.assertTrue(ok, self.note(f"pair-resume отказал:\n{output}"))
        base = self.alert_base()
        variant = self.rnd.choice(["same", "next"])
        task = task_a if variant == "same" else self.new_set_task(name)

        self.dev_cycle(task, model)

        self.assertFalse(self.alerts_naming(base, "developer", model), self.note(
            f"{variant}: возврат после снятия поднял алерт:\n"
            + "\n".join(self.alerts_after(base))))
        self.assert_pair_free("developer", model, f"{variant}: возврат после "
                              "pair-resume")


# =============================================== чистота прогона канарейки


class ExpectedEscalationCleanlinessTest(SetSandbox):

    def test_ac12_expected_escalation_clean_only_with_one_escalation(self):
        """Прогон с выполненной ожидаемой эскалацией чист только при одной.

        Сценарий: строки `canary_runs` пары (роль не analyst, модель
        случайна) — `green`, ноль итераций ревью, без отказа автогейта,
        ожидаемая эскалация выполнена (маркер задан,
        `actual_escalation = 1`, маркер совпал). При `escalations = 1`:
        `unclean_reason` — `None`, `clean_run` — истина; при
        `escalations = k` (k случайно 2..6): причина непуста и содержит
        число k, `clean_run` — ложь. Три прогона пары на трёх шаблонах
        (средний, быстрый, трудный), один из них (случайный) — с `k`
        эскалациями: `pair_admission` возвращает непустой перечень
        недостающего; те же три с одной эскалацией — пустой.

        Ловит мутацию: escalations > 1 при выполненной ожидаемой засчитан
        чистым (причина `None`, допуск без недостающего); причина не
        называет число эскалаций."""
        role = self.rnd.choice([r for r in AGENT_ROLES
                                if r != models.ADMIT_TZ_AMBIGUITY_ROLE])
        clean_model, dirty_model = self.rnd.sample(SET_MODELS, 2)
        marker = f"ESCALATE-{self.rnd.randrange(1000)}"
        k = self.rnd.randint(2, 6)
        conn = store.db()
        for model, special in ((clean_model, 1), (dirty_model, k)):
            titles = [self.medium, self.fast, self.hard]
            pick = self.rnd.randrange(len(titles))
            for i, title in enumerate(titles):
                self.add_run(title, {role: model},
                             escalations=special if i == pick else 1,
                             expected_escalation=marker,
                             actual_escalation=True, marker_mismatch=False)
        rows = {model: [row for row in store.all_canary_runs(conn)
                        if models.summary_models(
                            row["models_summary"]).get(role) == model]
                for model in (clean_model, dirty_model)}
        self.assertEqual([len(rows[m]) for m in (clean_model, dirty_model)],
                         [3, 3], self.note("фикстура прогонов"))
        for row in rows[clean_model] + rows[dirty_model]:
            self.assertTrue(models.expected_escalation_met(row),
                            self.note("фикстура ожидаемой эскалации"))

        for row in rows[clean_model] + [r for r in rows[dirty_model]
                                        if r["escalations"] == 1]:
            self.assertIsNone(models.unclean_reason(row), self.note(
                f"escalations=1: {models.unclean_reason(row)}"))
            self.assertTrue(models.clean_run(row), self.note("escalations=1"))
        dirty = [row for row in rows[dirty_model] if row["escalations"] == k]
        self.assertEqual(len(dirty), 1, self.note("фикстура прогона с k"))
        reason = models.unclean_reason(dirty[0])
        self.assertTrue(reason, self.note(f"escalations={k} засчитан чистым"))
        self.assertIn(str(k), reason, self.note(f"причина без числа: {reason}"))
        self.assertFalse(models.clean_run(dirty[0]), self.note(f"k={k}"))

        document = models.load_model_sets()
        _, missing = models.pair_admission(conn, role, clean_model, document)
        self.assertEqual(missing, [], self.note(
            f"три прогона с одной ожидаемой эскалацией: {missing}"))
        _, missing = models.pair_admission(conn, role, dirty_model, document)
        self.assertTrue(missing, self.note(
            f"прогон с {k} эскалациями засчитан в допуск пары"))

if __name__ == "__main__":
    unittest.main()
