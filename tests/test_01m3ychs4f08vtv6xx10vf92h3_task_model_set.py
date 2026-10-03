"""Набор моделей задачи: `new --set`, модель, провайдер и стоимость шага с
учётом задачи, снятый допуск пары, видимость набора, `set-models`, ручная
приёмка задачи с набором.

Группа: долгоживущий

Красен до реализации: команда `new` не знает флага `--set` («Нераспознанный аргумент: --set»), команды `set-models` в диспетчере `artel.main` нет («Неизвестная команда set-models») — задача с набором не заводится, и каждый сценарий падает на её заведении либо на отказе команды.

Планка провалидирована временным стабом реализации (все методы зелёные в
шести прогонах с разными зёрнами; мутации стаба — снятая сверка допуска
пары, снятый запрет автогейта, разрешение без задачи, снятая сверка
состояния `set-models` — красили соответствующие методы; стаб удалён,
код репозитория не тронут).

Публичная поверхность, которую читает этот файл (SPEC называет команды,
но не внутренние имена):

- `artel.py new <название> --tz <файл ТЗ> --set <набор>` — форма `new`
  с ТЗ (`<тз>` SPEC — существующий флаг `--tz`) и новым флагом набора;
- `artel.py set-models <id> <набор>` и `artel.py set-models <id>
  --default`;
- шаг роли — `runner.cmd_run(<id>)` с подменённым `runner.spawn_agent`:
  модель шага — значение флага `--model` в argv, провайдер и CLI — имя
  argv[0], вход — окружение `env=` запуска;
- стоимость шага — `spent_usd` строки задачи (`store.get_task`);
- журнал — `store.task_steps`; строка задачи — `store.get_task` (имя и
  состав набора ищутся среди значений строки, имена колонок планка не
  навязывает);
- `status` — `catalog.cmd_status()`; подсказки гейтов —
  `auto.auto_stop_advice(conn, <id>, <состояние>)`, единственный сборщик
  подсказки «approve» на остановке у гейта;
- приёмка — вход в `acceptance` из `review` публичным `fsm.cmd_advance`
  при политике гейта `auto` (`gates.policy`), зелёном полном наборе
  (`acceptance.full_suite`) и worktree на ветке задачи
  (`workspace.on_task_branch`): задача без набора в той же песочнице
  проходит автогейт в `merge_gate` (контрольный сценарий).

Окружение — фикстуры `tests/sandbox.py`: каталог моделей
(`use_catalog_fixture`, дополнен моделью `GAMMA` раздела `claude`), карта
исполнителей и локальный слой (`use_role_map`); боевая модель каждой
agent-роли — `FIXTURE_TIER_MODEL`. Файл решений Оператора `model_sets.yaml`
пишется в корень песочницы (`models.model_sets_path()`), прогоны канарейки
— публичным `store.insert_canary_run`: набор допущен проверкой части 1,
когда его не-боевые пары записаны `state: допущена` и есть зелёный прогон
набором целиком на шаблоне класса `трудный`.

Имена наборов, состав, число токенов, состояние задачи, способ снятия
допуска и правки файла выбираются случайно; зерно печатается и входит в
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

from orchestrator import (acceptance, artel, artifact_branch, auto, catalog,
                          config, fsm, gates,
                          models, pause, runner, spend, store, workspace)
from tests.sandbox import (CATALOG_FIXTURE_TEXT, FIXTURE_CODEX_MODEL,
                           FIXTURE_OTHER_MODEL, FIXTURE_ROLES,
                           FIXTURE_TIER_MODEL, FakeProc, LightTransitionSandbox,
                           RealGitSandbox, capture, event,
                           seed_developer_brief_fixtures,
                           sync_spec_from_worktree)

#: Корень репозитория — источник `templates/`/`skills/` для брифа шага.
REPO_ROOT = Path(__file__).resolve().parent.parent

#: agent-роли фикстуры карты исполнителей.
AGENT_ROLES = tuple(name for name, fields in FIXTURE_ROLES.items()
                    if fields.get("executor") == "agent")

#: Роли, которые могут стоять в наборе рядом с developer (шаг под тестом —
#: developer в `in_dev`).
OTHER_ROLES = tuple(role for role in AGENT_ROLES if role != "developer")

#: Третья модель раздела `claude` каталога сценария: её можно убрать из
#: каталога, не трогая модели фикстуры, на которых стоят ярусы.
GAMMA = "model-gamma-nabora"
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

ADMITTED = "допущена"
SUSPENDED = "приостановлена"

#: Состояния, в которых `set-models` разрешена (требование 9 SPEC).
SET_MODELS_STATES = ("spec_gate", "acceptance", "merge_gate", "escalated")
#: Состояния FSM вне этого перечня.
OTHER_STATES = ("spec_writing", "tests_writing", "in_dev", "verifying",
                "review", "done", "killed")

REVIEW_APPROVED = """---
task: {task}
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 2
---

# REVIEW: песочница

## Соответствие SPEC

Соответствует.

## Замечания

Нет.

## Проверено исполнением

Прогон планки песочницы — зелёный.

## Вердикт

approved
"""


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


class ModelSetsMixin:
    """Файл наборов, прогоны канарейки и команды пульта сценария."""

    def init_model_sets(self) -> None:
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rnd = random.Random(self.seed)
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        env.start()
        self.addCleanup(env.stop)
        # Вход шага сверяется по окружению запуска: ambient-токен процесса
        # прогона сильнее слота keychain и подменил бы предмет проверки.
        for name in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY"):
            os.environ.pop(name, None)
        self.assertIn(GAMMA, CATALOG_WITH_GAMMA, "якорь каталога фикстуры")
        self.use_catalog_fixture(CATALOG_WITH_GAMMA)
        self.hard = f"canary-trudnyy-{self.rnd.randrange(10 ** 6)}"
        self.medium = f"canary-sredniy-{self.rnd.randrange(10 ** 6)}"
        self.templates = {self.hard: "трудный", self.medium: "средний"}
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

    def register_set(self, name: str, members: dict, *,
                     pair_states: dict = None, hard_run: bool = True) -> None:
        """Набор в `sets:`; его не-боевые пары — в `pairs:` с состоянием
        из `pair_states` (по умолчанию «допущена»; `None` — пара не
        записана); `hard_run` — зелёный прогон набором целиком на трудном
        шаблоне."""
        self.sets[name] = dict(members)
        for role, model in members.items():
            if model == FIXTURE_TIER_MODEL:
                continue
            state = (pair_states or {}).get(role, ADMITTED)
            if state is not None:
                self.pairs.setdefault(role, {})[model] = state
        if hard_run:
            self.add_run(self.hard, members)
        self.write_model_sets()

    def set_pair_state(self, role: str, model: str, state) -> None:
        """Состояние пары в файле; `None` — запись пары снята."""
        entries = self.pairs.setdefault(role, {})
        if state is None:
            entries.pop(model, None)
        else:
            entries[model] = state
        self.write_model_sets()

    def add_run(self, title: str, members: dict, verdict: str = "green") -> None:
        """Строка `canary_runs`: сводка «роль → модель» — боевая модель
        каждой agent-роли, поверх неё — `members`."""
        self.run_no += 1
        pairs = {role: FIXTURE_TIER_MODEL for role in AGENT_ROLES}
        pairs.update(members)
        named = ", ".join(f"{role} → {model}" for role, model in pairs.items())
        store.insert_canary_run(
            store.db(), f"stamp-{self.run_no}", title, f"T-RUN-{self.run_no}",
            10, 1.0, 0, 0, "merge_gate", None, False, False,
            main_sha="0" * 40, verdict=verdict,
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

    def new_task(self, set_name: str = None) -> tuple:
        """(успех, вывод, id задачи либо `None`) — `new <название> --tz
        <файл> [--set <набор>]`."""
        self.title_no += 1
        title = f"Задача набора {self.title_no}-{self.rnd.randrange(10 ** 6)}"
        tz = config.ROOT / ".artel" / f"tz-{self.title_no}.md"
        tz.parent.mkdir(parents=True, exist_ok=True)
        tz.write_text("Учебное ТЗ задачи на наборе моделей.\n", encoding="utf-8")
        argv = ["new", title, "--tz", str(tz)]
        if set_name is not None:
            argv += ["--set", set_name]
        ok, output = self.cli(*argv)
        ids = [row["id"] for row in store.all_tasks(store.db())
               if row["title"] == title]
        return ok, output, (ids[0] if ids else None)

    def new_set_task(self, set_name: str) -> str:
        ok, output, task_id = self.new_task(set_name)
        self.assertTrue(ok and task_id, self.note(f"new --set {set_name}:\n"
                                                  f"{output}"))
        return task_id

    # ------------------------------------------------------- наблюдение

    def row_values(self, task_id: str) -> list:
        row = store.get_task(store.db(), task_id)
        return [str(value) for value in dict(row).values() if value is not None]

    def row_has_set(self, task_id: str, name: str, members: dict) -> bool:
        """В строке задачи есть значение-имя набора и значение, несущее
        каждую пару «роль, модель» его состава."""
        values = self.row_values(task_id)
        has_name = name in values
        has_members = any(all(role in value and model in value
                              for role, model in members.items())
                          for value in values)
        return has_name and has_members

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


class StepSandbox(ModelSetsMixin, LightTransitionSandbox):
    """Лёгкая песочница переходов с брифом шага: `templates/`, `skills/` и
    фикстуры брифа в корне, CLI агента подменён (`runner.spawn_agent`),
    токен слота — `tok-test`, предполёт окружения пуст. Задача песочницы
    `self.TASK` заведена без набора — соседняя задача сценариев."""

    TOKEN = "tok-test"

    def setUp(self):
        super().setUp()
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates",
                        dirs_exist_ok=True)
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills",
                        dirs_exist_ok=True)
        seed_developer_brief_fixtures(self.root)
        for target, attr, value in (
                (runner.time, "sleep", lambda _: None),
                (runner.keychain, "token", lambda slot: self.TOKEN)):
            patcher = mock.patch.object(target, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        preflight = mock.patch("orchestrator.doctor.preflight_checks",
                               lambda role, target, **step: [])
        preflight.start()
        self.addCleanup(preflight.stop)
        self.neighbour = self.TASK
        self.init_model_sets()

    def run_step(self, task_id: str, *, usage: dict = None,
                 cost: float = 0.1) -> dict:
        """Шаг developer задачи в `in_dev`: argv и окружение запуска агента
        (`None` — агент не запускался), отказ шага, новые записи журнала."""
        conn = store.db()
        store.update_task(conn, task_id, state="in_dev", paused=0)
        sync_spec_from_worktree(task_id)
        plan_dir = artifact_branch.docs_dir(task_id, config.DEFAULT_TARGET)
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "PLAN.md").write_text("маркер\n", encoding="utf-8")
        before = self.last_step_id(task_id)
        fields = {"usage": usage} if usage is not None else {}
        if cost is not None:
            fields["total_cost_usd"] = cost
        calls = []

        def spawn(cmd, *args, **kwargs):
            calls.append((list(cmd), kwargs.get("env") or {}))
            return FakeProc([result_event(**fields)])

        refusal, output = None, ""
        with mock.patch.object(runner, "spawn_agent", side_effect=spawn):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                try:
                    runner.cmd_run(task_id)
                except SystemExit as exc:
                    refusal = str(exc.code)
            output = buf.getvalue()
        # Задача, отработавшая шаг, уходит с дороги соседей: ручной гейт.
        store.update_task(conn, task_id, state="spec_gate")
        argv, env = calls[0] if calls else (None, None)
        return {"argv": argv, "env": env, "refusal": refusal,
                "output": output, "rows": self.steps_after(task_id, before)}

    def step_model(self, step: dict):
        argv = step["argv"]
        if argv is None or "--model" not in argv:
            return None
        return argv[argv.index("--model") + 1]

    def assert_step_model(self, step: dict, model: str, why: str) -> None:
        self.assertIsNotNone(step["argv"], self.note(
            f"{why}: агент не запущен: {step['refusal']}\n{step['output']}"))
        self.assertEqual(self.step_model(step), model,
                         self.note(f"{why}: argv {step['argv']}"))


class StepModelTest(StepSandbox):

    def test_ac1_set_role_on_set_model_other_roles_and_neighbour_on_combat(self):
        """Модель шага зависит от набора задачи, а не только от роли.

        Сценарий: задача A заведена с набором, где developer назван
        моделью `FIXTURE_OTHER_MODEL` (плюс случайные другие роли); задача
        B — с допущенным набором, где developer НЕ записан (только
        случайная другая роль); соседняя задача песочницы — без набора.
        Шаг developer каждой: A — на модели набора, B и соседняя — на
        боевой модели `FIXTURE_TIER_MODEL`.

        Ловит мутацию: разрешение модели без учёта задачи (A уходит на
        боевую модель); набор применяется к роли без записи в нём (B
        получает модель другой роли набора либо отказ); набор одной
        задачи протекает на соседнюю (соседняя на модели набора)."""
        extra = self.rnd.sample(OTHER_ROLES, self.rnd.randint(0, 2))
        with_dev = self.set_name("s-dev")
        self.register_set(with_dev, {"developer": FIXTURE_OTHER_MODEL,
                                     **{r: FIXTURE_OTHER_MODEL for r in extra}})
        without_dev = self.set_name("s-bez-dev")
        self.register_set(without_dev,
                          {self.rnd.choice(OTHER_ROLES): FIXTURE_OTHER_MODEL})
        task_a = self.new_set_task(with_dev)
        task_b = self.new_set_task(without_dev)

        self.assert_step_model(self.run_step(task_a), FIXTURE_OTHER_MODEL,
                               f"задача с набором {with_dev}")
        self.assert_step_model(self.run_step(task_b), FIXTURE_TIER_MODEL,
                               f"набор {without_dev} без developer")
        self.assert_step_model(self.run_step(self.neighbour),
                               FIXTURE_TIER_MODEL, "соседняя задача без набора")

    def test_ac2_step_cost_by_tariff_of_set_model(self):
        """Стоимость шага задачи с набором — по тарифу модели набора.

        Сценарий: набор переводит developer на `GAMMA`; итог запуска
        несёт разбивку usage (случайные числа токенов) без цены CLI —
        шаг считается по тарифу. `spent_usd` задачи равен стоимости
        разбивки по действующему тарифу `GAMMA` и отличается от стоимости
        по тарифу боевой модели.

        Ловит мутацию: тариф шага берётся цепочкой РОЛИ (боевая модель),
        а не моделью, на которой шаг шёл, — `spent_usd` совпадает с
        расчётом по боевому тарифу."""
        name = self.set_name()
        self.register_set(name, {"developer": GAMMA})
        task = self.new_set_task(name)
        usage = {"input_tokens": self.rnd.randint(10_000, 900_000),
                 "output_tokens": self.rnd.randint(1_000, 90_000)}

        step = self.run_step(task, usage=usage, cost=None)

        self.assert_step_model(step, GAMMA, "шаг набора")
        spent = store.get_task(store.db(), task)["spent_usd"]
        expected = spend.tariff_cost_usd(models.resolve_model(GAMMA).tariff,
                                         usage)
        combat = spend.tariff_cost_usd(
            models.resolve_model(FIXTURE_TIER_MODEL).tariff, usage)
        self.assertNotAlmostEqual(expected, combat, places=6,
                                  msg=self.note("тарифы фикстуры совпали"))
        self.assertAlmostEqual(spent, expected, places=6, msg=self.note(
            f"usage {usage}: списано {spent}, по тарифу набора {expected}, "
            f"по боевому {combat}\n{self.steps_text(step['rows'])}"))


class StepProviderTest(StepSandbox):

    def test_ac3_provider_cli_and_entry_follow_the_set_model(self):
        """Провайдер, CLI и вход шага — от модели набора, не от карты ролей.

        Сценарий: карта исполнителей называет developer провайдером
        `codex`; набор задачи переводит developer на модель раздела
        `claude` (`FIXTURE_OTHER_MODEL` либо `GAMMA`, случайно). Шаг
        запускает CLI `claude` с `--model` набора, а окружение несёт вход
        провайдера Claude — каталог конфига роли и токен слота.

        Ловит мутацию: провайдер шага по-прежнему берётся из карты
        исполнителей (`providers.for_role` без задачи) — argv собран
        провайдером codex (`-m`, а не `--model`; другое имя CLI) либо шаг
        не стартует; окружение собрано провайдером карты — нет
        `CLAUDE_CONFIG_DIR` и токена."""
        self.use_role_map(roles={"developer": {"provider": "codex"}})
        model = self.rnd.choice([FIXTURE_OTHER_MODEL, GAMMA])
        name = self.set_name()
        self.register_set(name, {"developer": model})
        task = self.new_set_task(name)

        step = self.run_step(task)

        self.assert_step_model(step, model, "шаг набора с чужим провайдером")
        self.assertEqual(Path(step["argv"][0]).name, "claude",
                         self.note(f"argv {step['argv']}"))
        env = step["env"]
        self.assertEqual(env.get("CLAUDE_CONFIG_DIR"),
                         str(config.ROLE_CONFIG_DIR), self.note(f"{env}"))
        self.assertEqual(env.get("CLAUDE_CODE_OAUTH_TOKEN"), self.TOKEN,
                         self.note("токен слота не дошёл до шага"))

    def test_ac3_set_model_failing_fail_closed_refuses_the_step(self):
        """Модель набора без места в каталоге либо `experimental` без
        разрешения — отказ шага, агент не запускается.

        Сценарий (оба случая в одном прогоне, порядок случаен): (а) набор
        переводит developer на `GAMMA`, после `new` модель снята из
        каталога; (б) набор переводит developer на experimental-модель
        `FIXTURE_CODEX_MODEL`, разрешённую локальным слоем на момент
        `new`, разрешение снято до шага. Шаг каждой задачи — отказ
        (`SystemExit`) с именем модели, агент не запущен.

        Ловит мутацию: модель набора не проходит звенья fail-closed
        `role_models:` — шаг молча идёт на боевой модели (агент запущен)
        либо стартует с моделью вне каталога / неразрешённой
        experimental-моделью."""
        cases = ["catalog", "experimental"]
        self.rnd.shuffle(cases)
        for case in cases:
            if case == "catalog":
                self.use_catalog_fixture(CATALOG_WITH_GAMMA)
                self.use_role_map()
                model = GAMMA
            else:
                self.use_catalog_fixture(CATALOG_WITH_GAMMA)
                self.use_role_map(allow_experimental=(FIXTURE_CODEX_MODEL,))
                model = FIXTURE_CODEX_MODEL
            name = self.set_name(f"s-{case}")
            self.register_set(name, {"developer": model})
            task = self.new_set_task(name)
            if case == "catalog":
                self.use_catalog_fixture(CATALOG_FIXTURE_TEXT)
            else:
                self.use_role_map()

            step = self.run_step(task)

            self.assertIsNone(step["argv"], self.note(
                f"{case}: агент запущен: {step['argv']}"))
            self.assertIsNotNone(step["refusal"], self.note(
                f"{case}: шаг не отказал явно\n{step['output']}"))
            self.assertIn(model, step["refusal"] + step["output"],
                          self.note(f"{case}: отказ не называет модель"))


class SetStabilityTest(StepSandbox):

    def test_ac8_editing_the_set_after_new_does_not_move_the_task(self):
        """Правка состава набора в файле после `new` не меняет модель шага.

        Сценарий: набор переводит developer на `FIXTURE_OTHER_MODEL`,
        задача заведена; затем в `model_sets.yaml` (случайно одно из):
        developer переведён на `GAMMA` (пара допущена), developer снят из
        набора, набор удалён целиком. Пары исходного состава остаются
        допущенными. Шаг developer идёт на `FIXTURE_OTHER_MODEL`.

        Ловит мутацию: модель шага разрешается по текущему файлу наборов
        по имени набора, а не по составу, записанному при `new`, — шаг
        уходит на `GAMMA`, на боевую модель или в отказ."""
        name = self.set_name()
        self.register_set(name, {"developer": FIXTURE_OTHER_MODEL})
        task = self.new_set_task(name)
        edit = self.rnd.choice(["gamma", "drop-role", "drop-set"])
        if edit == "gamma":
            self.pairs.setdefault("developer", {})[GAMMA] = ADMITTED
            self.sets[name] = {"developer": GAMMA}
        elif edit == "drop-role":
            self.sets[name] = {self.rnd.choice(OTHER_ROLES): GAMMA}
        else:
            del self.sets[name]
        self.write_model_sets()

        self.assert_step_model(self.run_step(task), FIXTURE_OTHER_MODEL,
                               f"правка файла: {edit}")

    def test_ac9_withdrawn_pair_falls_back_to_combat_with_journal_record(self):
        """Пара, снятая с допуска к старту шага, — шаг на боевой модели и
        запись в журнал.

        Сценарий: набор переводит developer на `FIXTURE_OTHER_MODEL`,
        задача заведена; затем пара developer → `FIXTURE_OTHER_MODEL` в
        `pairs:` переведена в `state: приостановлена` либо её запись
        снята (случайно). Шаг developer идёт на `FIXTURE_TIER_MODEL`, а
        среди записей журнала задачи, появившихся за шаг, есть запись,
        называющая снятую модель набора.

        Ловит мутацию: состояние пары на старте шага не сверяется — шаг
        идёт на снятой паре; откат на боевую модель молчаливый — записи о
        снятой паре в журнале шага нет."""
        name = self.set_name()
        self.register_set(name, {"developer": FIXTURE_OTHER_MODEL})
        task = self.new_set_task(name)
        mode = self.rnd.choice([SUSPENDED, None])
        self.set_pair_state("developer", FIXTURE_OTHER_MODEL, mode)

        step = self.run_step(task)

        self.assert_step_model(step, FIXTURE_TIER_MODEL,
                               f"пара снята ({mode or 'запись удалена'})")
        text = self.steps_text(step["rows"])
        self.assertIn(FIXTURE_OTHER_MODEL, text, self.note(
            f"нет записи о снятой паре в журнале шага:\n{text}"))


class VisibilityTest(StepSandbox):

    def test_ac10_status_shows_the_set_next_to_the_budget(self):
        """`status` называет набор задачи в её строке, рядом с бюджетом.

        Сценарий: задача с набором и соседняя задача без набора;
        `catalog.cmd_status()`. Строка задачи с набором несёт имя набора
        и её бюджет; строка соседней задачи имени набора не несёт.

        Ловит мутацию: `status` набор не печатает вовсе либо печатает его
        не в строке задачи (отдельной секцией), либо у каждой задачи."""
        name = self.set_name()
        self.register_set(name, {self.rnd.choice(AGENT_ROLES): GAMMA})
        task = self.new_set_task(name)
        out = capture(catalog.cmd_status)
        lines = {tid: [line for line in out.splitlines() if tid in line]
                 for tid in (task, self.neighbour)}
        budget = f"/{store.get_task(store.db(), task)['budget_usd']:.2f}"
        self.assertTrue(any(name in line and budget in line
                            for line in lines[task]),
                        self.note(f"строка задачи без набора/бюджета:\n{out}"))
        self.assertFalse(any(name in line for line in lines[self.neighbour]),
                         self.note(out))

    def test_ac10_step_start_record_names_role_model_and_source(self):
        """Запись старта шага называет роль, модель и источник модели.

        Сценарий: шаг developer задачи с набором (`GAMMA`), шаг соседней
        задачи без набора (ярус) и, после записи `role_models:
        developer: FIXTURE_OTHER_MODEL` в локальный слой, ещё один шаг
        соседней задачи. Запись «agent run started» каждого шага — от
        актора developer, с моделью шага и источником: «набор» у задачи
        с набором, «ярус» у соседней, `role_models` после записи слоя.

        Ловит мутацию: источник модели не пишется или пишется одним
        словом для всех путей разрешения — запись шага набора не говорит
        «набор», запись шага по `role_models:` не отличается от яруса."""
        name = self.set_name()
        self.register_set(name, {"developer": GAMMA})
        task = self.new_set_task(name)
        cases = [(task, GAMMA, "набор"), (self.neighbour, FIXTURE_TIER_MODEL,
                                         "ярус")]
        for task_id, model, source in cases:
            self.assert_started_record(self.run_step(task_id), model, source)
        layer = Path(config.MODELS_LOCAL)
        layer.write_text(layer.read_text(encoding="utf-8")
                         + f"\nrole_models:\n  developer: {FIXTURE_OTHER_MODEL}\n",
                         encoding="utf-8")
        self.assert_started_record(self.run_step(self.neighbour),
                                   FIXTURE_OTHER_MODEL, "role_models")

    def assert_started_record(self, step: dict, model: str, source: str) -> None:
        started = [row for row in step["rows"]
                   if row["action"] == "agent run started"]
        self.assertTrue(started, self.note(
            f"нет записи старта шага:\n{self.steps_text(step['rows'])}"))
        row = started[-1]
        detail = row["detail"] or ""
        self.assertEqual(row["actor"], "developer", self.note(detail))
        self.assertIn(model, detail, self.note(detail))
        self.assertIn(source, detail.lower(), self.note(
            f"источник «{source}» не назван: {detail}"))

    def test_ac10_approve_hints_on_gates_name_the_set(self):
        """Подсказки остановки у гейтов SPEC, приёмки и мержа называют набор.

        Сценарий: задача с набором поочерёдно в `spec_gate`, `acceptance`,
        `merge_gate` (порядок случаен); `auto.auto_stop_advice` даёт
        причину и подсказку `approve` — имя набора есть в тексте каждого
        гейта, команда `artel.py approve` в подсказке осталась.

        Ловит мутацию: набор добавлен в подсказку одного гейта из трёх
        (например, только `merge_gate`) либо подсказка задачи с набором
        больше не несёт команду `approve`."""
        name = self.set_name()
        self.register_set(name, {self.rnd.choice(AGENT_ROLES): GAMMA})
        task = self.new_set_task(name)
        conn = store.db()
        gates_order = ["spec_gate", "acceptance", "merge_gate"]
        self.rnd.shuffle(gates_order)
        for state in gates_order:
            store.update_task(conn, task, state=state)
            reason, hint = auto.auto_stop_advice(conn, task, state)
            text = f"{reason} {hint}"
            self.assertIn(name, text, self.note(f"{state}: {text}"))
            self.assertIn("artel.py approve", hint, self.note(f"{state}: {hint}"))


class SetModelsCommandTest(StepSandbox):

    def test_ac11_set_models_changes_the_set_in_allowed_states(self):
        """`set-models` меняет набор в допустимых состояниях и на паузе.

        Сценарий: задача заведена с набором S1; в случайном состоянии из
        `spec_gate`/`acceptance`/`merge_gate`/`escalated` либо в `in_dev`
        на паузе (`pause`) — `set-models <id> S2` с допущенным S2: строка
        задачи несёт имя и состав S2, имени S1 в ней нет, в журнале новая
        запись с именем S2. Затем `set-models <id> S3` с недопущенным S3
        (пара не записана) — отказ, строка задачи прежняя (S2). Затем
        `set-models <id> --default` — набор снят, в журнале новая
        запись, следующий шаг developer — на боевой модели.

        Ловит мутацию: команда меняет только имя набора, не состав (шаг
        шёл бы по старому составу); допуск нового набора не проверяется
        (S3 принят); `--default` не снимает состав — шаг остаётся на
        модели набора; смена без записи в журнал."""
        s1, s2, s3 = (self.set_name(s) for s in ("s1", "s2", "s3"))
        self.register_set(s1, {"developer": FIXTURE_OTHER_MODEL})
        members2 = {"developer": GAMMA,
                    self.rnd.choice(OTHER_ROLES): FIXTURE_OTHER_MODEL}
        self.register_set(s2, members2)
        self.register_set(s3, {"developer": FIXTURE_CODEX_MODEL},
                          pair_states={"developer": None})
        task = self.new_set_task(s1)
        conn = store.db()
        state = self.rnd.choice(SET_MODELS_STATES + ("paused",))
        if state == "paused":
            store.update_task(conn, task, state="in_dev")
            ok, out = self.cli("pause", task)
            self.assertTrue(ok, self.note(out))
        else:
            store.update_task(conn, task, state=state)

        before = self.last_step_id(task)
        ok, out = self.cli("set-models", task, s2)
        self.assertTrue(ok, self.note(f"{state}: {out}"))
        self.assertTrue(self.row_has_set(task, s2, members2),
                        self.note(f"{state}: {self.row_values(task)}"))
        self.assertNotIn(s1, self.row_values(task), self.note(state))
        self.assertIn(s2, self.steps_text(self.steps_after(task, before)),
                      self.note(f"{state}: смена набора не в журнале"))

        snapshot = self.row_values(task)
        ok, out = self.cli("set-models", task, s3)
        self.assertFalse(ok, self.note(f"недопущенный {s3} принят:\n{out}"))
        self.assertEqual(snapshot, self.row_values(task), self.note(state))

        before = self.last_step_id(task)
        ok, out = self.cli("set-models", task, "--default")
        self.assertTrue(ok, self.note(f"{state} --default: {out}"))
        self.assertNotIn(s2, self.row_values(task), self.note(state))
        self.assertTrue(self.steps_after(task, before),
                        self.note("--default без записи в журнал"))
        self.assert_step_model(self.run_step(task), FIXTURE_TIER_MODEL,
                               "после --default")

    def test_ac12_set_models_refused_in_other_states_names_allowed(self):
        """`set-models` вне допустимых состояний — отказ с их перечнем.

        Сценарий: задача с набором S1 в случайном состоянии вне
        `spec_gate`/`acceptance`/`merge_gate`/`escalated`, без паузы
        (два разных состояния за прогон); `set-models <id> S2` с
        допущенным S2 — отказ, текст называет все четыре допустимых
        состояния и паузу; строка задачи не изменилась.

        Ловит мутацию: проверка состояния пропущена (набор сменён);
        перечень в отказе неполный (нет `escalated` или паузы); пауза
        признаётся по состоянию, а не по пометке `pause`."""
        s1, s2 = self.set_name("s1"), self.set_name("s2")
        self.register_set(s1, {"developer": FIXTURE_OTHER_MODEL})
        self.register_set(s2, {"developer": GAMMA})
        task = self.new_set_task(s1)
        conn = store.db()
        for state in self.rnd.sample(OTHER_STATES, 2):
            store.update_task(conn, task, state=state, paused=0)
            snapshot = self.row_values(task)
            ok, out = self.cli("set-models", task, s2)
            self.assertFalse(ok, self.note(f"{state}: набор сменён:\n{out}"))
            for allowed in SET_MODELS_STATES:
                self.assertIn(allowed, out, self.note(f"{state}: {out}"))
            self.assertTrue("pause" in out.lower() or "пауз" in out.lower(),
                            self.note(f"{state}: пауза не названа: {out}"))
            self.assertEqual(snapshot, self.row_values(task),
                             self.note(f"{state}: строка задачи изменилась"))


class ManualAcceptanceTest(ModelSetsMixin, LightTransitionSandbox):
    """Вход в `acceptance` из `review` публичным `advance` при политике
    гейта `auto`, зелёном полном наборе и worktree на ветке задачи."""

    def setUp(self):
        super().setUp()
        self.neighbour = self.TASK
        self.init_model_sets()

    def enter_acceptance(self, task_id: str) -> tuple:
        """(состояние после advance, вывод + новые записи журнала)."""
        self.TASK = task_id
        self.tdir = config.TASKS / task_id
        self.write_acceptance_plank()
        (self.tdir / "REVIEW.md").write_text(
            REVIEW_APPROVED.format(task=task_id), encoding="utf-8")
        self.wt_path.mkdir(parents=True, exist_ok=True)
        conn = store.db()
        store.update_task(conn, task_id, state="review", reviewed_iter=0)
        before = self.last_step_id(task_id)
        green = acceptance.FullSuiteRun(True, acceptance.FULL_SUITE_GREEN,
                                        "1 passed", None, "зелёный прогон")
        buf = io.StringIO()
        with mock.patch.object(gates, "policy", return_value=gates.AUTO), \
                mock.patch.object(acceptance, "full_suite", return_value=green), \
                mock.patch.object(workspace, "on_task_branch", return_value=True), \
                contextlib.redirect_stdout(buf):
            fsm.cmd_advance(task_id)
        text = buf.getvalue() + "\n" + self.steps_text(
            self.steps_after(task_id, before))
        return store.get_task(store.db(), task_id)["state"], text

    def test_ac13_task_with_set_stays_on_manual_acceptance_naming_the_set(self):
        """Задача с набором не проходит приёмку автогейтом.

        Сценарий: в одной песочнице задача без набора (контроль) и задача
        с допущенным набором (случайная роль на `GAMMA`) входят в
        `acceptance` при выполненных условиях автогейта. Контрольная
        уходит в `merge_gate` автогейтом; задача с набором остаётся в
        `acceptance`, и причина (вывод или журнал входа) называет набор.

        Ловит мутацию: условие «у задачи нет набора» не добавлено в
        автогейт (задача с набором в `merge_gate`); отказ без имени
        набора; набор блокирует автогейт и задачам без набора (контроль
        остаётся в `acceptance`)."""
        name = self.set_name()
        self.register_set(name, {self.rnd.choice(AGENT_ROLES): GAMMA})
        task = self.new_set_task(name)
        order = [self.neighbour, task]
        self.rnd.shuffle(order)
        outcome = {task_id: self.enter_acceptance(task_id) for task_id in order}

        state, text = outcome[self.neighbour]
        self.assertEqual(state, "merge_gate", self.note(f"контроль:\n{text}"))
        state, text = outcome[task]
        self.assertEqual(state, "acceptance", self.note(f"набор {name}:\n{text}"))
        self.assertIn(name, text, self.note(f"причина без набора:\n{text}"))


class NewSetSandbox(ModelSetsMixin, RealGitSandbox):
    """Главная копия на настоящем git: отказ `new` проверяется по строкам
    задач в БД и по ссылкам репозитория."""

    def setUp(self):
        super().setUp()
        self.use_role_map()
        self.init_model_sets()

    def refs(self) -> list:
        return sorted(self.git("for-each-ref", "--format=%(refname)").split())

    def tasks(self) -> list:
        return [row["id"] for row in store.all_tasks(store.db())]

    def assert_refused_before_creation(self, name: str, *needles: str) -> str:
        refs, tasks = self.refs(), self.tasks()
        ok, output, task_id = self.new_task(name)
        self.assertFalse(ok, self.note(f"new --set {name} принят:\n{output}"))
        self.assertIsNone(task_id, self.note(output))
        self.assertEqual(tasks, self.tasks(), self.note("строка задачи в БД"))
        self.assertEqual(refs, self.refs(), self.note("заведена ветка"))
        for needle in needles:
            self.assertIn(needle, output, self.note(f"нет «{needle}»:\n{output}"))
        return output


class NewSetTest(NewSetSandbox):

    def test_ac4_admitted_set_creates_task_with_name_and_composition(self):
        """`new --set` с допущенным набором записывает имя и состав в строку.

        Сценарий: набор из случайного непустого подмножества agent-ролей
        на `FIXTURE_OTHER_MODEL`/`GAMMA` (одна роль — на боевой модели,
        её пара допуска не требует), пары допущены, есть зелёный трудный
        прогон набором. `new --set` заводит задачу; среди значений строки
        задачи — имя набора и значение, несущее каждую пару «роль,
        модель» состава.

        Ловит мутацию: в строку пишется только имя набора (состав
        читается из файла позже); флаг принят, но набор не записан."""
        roles = self.rnd.sample(AGENT_ROLES, self.rnd.randint(2, len(AGENT_ROLES)))
        members = {role: self.rnd.choice([FIXTURE_OTHER_MODEL, GAMMA])
                   for role in roles}
        members[roles[0]] = FIXTURE_TIER_MODEL
        name = self.set_name()
        self.register_set(name, members)

        ok, output, task_id = self.new_task(name)

        self.assertTrue(ok and task_id, self.note(output))
        self.assertTrue(self.row_has_set(task_id, name, members),
                        self.note(f"{members}: {self.row_values(task_id)}"))

    def test_ac5_unadmitted_pair_refuses_before_creation(self):
        """Набор с недопущенной парой — отказ `new` до заведения задачи.

        Сценарий: набор из двух ролей на `GAMMA`; пара одной (случайной)
        роли в `pairs:` не записана; трудный прогон набором есть. `new
        --set` — отказ: строк задач и ссылок git столько же, сколько до
        команды; текст называет роль и модель пары и причину «не
        допущена».

        Ловит мутацию: допуск набора не проверяется на `new` (задача
        заведена); проверка идёт после заведения строки или ветки (они
        остаются); отказ без имени пары."""
        role, other = self.rnd.sample(AGENT_ROLES, 2)
        name = self.set_name()
        self.register_set(name, {role: GAMMA, other: GAMMA},
                          pair_states={role: None})
        output = self.assert_refused_before_creation(name, role, GAMMA)
        self.assertIn("допущ", output, self.note(output))

    def test_ac6_suspended_pair_refuses_before_creation(self):
        """Набор с приостановленной парой — отказ `new` до заведения задачи.

        Сценарий: как в AC-5, но пара случайной роли записана
        `state: приостановлена`. Отказ: ни строки задачи, ни новой ссылки
        git; текст называет роль, модель и «приостановлена».

        Ловит мутацию: состояние пары не сверяется (запись пары есть —
        значит допущена); отказ без причины."""
        role, other = self.rnd.sample(AGENT_ROLES, 2)
        name = self.set_name()
        self.register_set(name, {role: GAMMA, other: FIXTURE_OTHER_MODEL},
                          pair_states={role: SUSPENDED})
        self.assert_refused_before_creation(name, role, GAMMA, SUSPENDED)

    def test_ac7_no_green_hard_run_of_whole_set_refuses_before_creation(self):
        """Набор без зелёного трудного прогона целиком — отказ `new`.

        Сценарий: пары набора допущены; в `canary_runs` — зелёный прогон
        набором на среднем шаблоне и (случайно) красный трудный прогон
        набором либо зелёный трудный прогон, где набору соответствует
        только часть ролей. Отказ: ни строки задачи, ни ссылки git; текст
        называет набор и причину — трудный класс.

        Ловит мутацию: `new` сверяет только пары и не требует прогона
        набором (задача заведена); засчитан прогон не того класса или
        не того вердикта; отказ без имени набора."""
        roles = self.rnd.sample(AGENT_ROLES, 2)
        members = {role: GAMMA for role in roles}
        name = self.set_name()
        self.register_set(name, members, hard_run=False)
        self.add_run(self.medium, members)
        if self.rnd.random() < 0.5:
            self.add_run(self.hard, members, verdict="red")
        else:
            self.add_run(self.hard, {roles[0]: GAMMA})
        output = self.assert_refused_before_creation(name, name)
        self.assertIn("трудн", output, self.note(output))


if __name__ == "__main__":
    unittest.main()
