"""Предполёт шага задачи с набором моделей: CLI и вход провайдера ШАГА
(модели набора), а не боевого провайдера роли; `doctor` дополнительно
проверяет провайдеров наборов задач в работе.

Группа: долгоживущий

Красен до реализации: предполёт шага (`doctor.preflight_checks(role, target)`) выбирает провайдера по роли — у задачи, где набор переводит роль на Codex, он проверяет CLI и токен Claude (без токена Claude в keychain шаг Codex отклоняется, AC-1), а вход Codex не спрашивает вовсе (шаг уходит в запуск агента, AC-4), отказ по CLI Codex не называет набор (AC-2), а при невыполненном входе боевого Codex шаг набора на модели Claude отклоняется (AC-3); склейка `doctor` спрашивает только провайдеров ролей карты — строк `codex-cli-found`/`codex-chatgpt-auth` от набора задачи в работе нет (AC-5).

Файл провалидирован временным стабом реализации: провайдер шага и имя
набора переданы в предполёт, провалы предполёта задачи с набором дописаны
провайдером, ролью и набором, склейка `doctor` дополнена провайдерами
`models.live_task_set_providers`. Все методы зелёные в нескольких прогонах
с разными зёрнами. Мутации стаба: предполёт по провайдеру роли красит AC-3
(«шаг, а не роль») и AC-4; провайдер набора, протёкший на соседнюю задачу,
красит AC-3 («соседняя»). Стаб удалён, код репозитория не тронут.
AC-1 — в прочтении ANSWER-1 (вариант Б): CLI `claude` на машине есть
(обязательный инструмент манифеста), но токена Claude в keychain нет;
предполёт шага на Codex этого не спрашивает, агент запускается.

Публичная поверхность, которую читает файл:

- задача с набором — `artel.py new <название> --tz <файл> --set <набор>`
  (`artel.main`); набор допущен, когда его не-боевые пары записаны в
  `model_sets.yaml` (`models.model_sets_path()`) со `state: допущена` и
  есть зелёный прогон канарейки набором целиком на трудном шаблоне
  (`store.insert_canary_run`);
- шаг роли — `runner.cmd_run(<id>)` с подменённым `runner.spawn_agent`:
  «агент запущен» — вызов `spawn_agent`, его argv[0] — CLI шага;
  отказ — `SystemExit`, печать и новые записи `store.task_steps`;
- наличие CLI на машине — `shutil.which` (им смотрят и предполёт, и
  резолв манифеста); вход Codex — ответ `codex login status`, вызов
  `subprocess.run` подменён ответом сценария, прочие вызовы проходят к
  прежнему исполнителю;
- `doctor` — `doctor.all_checks(conn)`, имена строк — `Check.name`.

Окружение — фикстуры `tests/sandbox.py` (`LightTransitionSandbox`,
`use_catalog_fixture`, `use_role_map`): модель Codex — `FIXTURE_CODEX_MODEL`
каталога-фикстуры (experimental, разрешена локальным слоем сценария).
Имена наборов, состав, вид невыполненного входа и состояния задачи
выбираются случайно; зерно печатается и входит в текст провала.
"""
import contextlib
import io
import os
import random
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import artel, config, doctor, keychain, models, runner, store
from tests.sandbox import (FIXTURE_CODEX_MODEL, FIXTURE_OTHER_MODEL,
                           FIXTURE_ROLES, FIXTURE_TIER, FIXTURE_TIER_MODEL,
                           FakeProc, LightTransitionSandbox, TimeWithSleep,
                           event,
                           seed_developer_brief_fixtures,
                           sync_spec_from_worktree)

#: Корень репозитория — источник `templates/`/`skills/` для брифа шага.
REPO_ROOT = Path(__file__).resolve().parent.parent

#: Роль шага под тестом: `in_dev` исполняет developer.
ROLE = "developer"

#: agent-роли фикстуры карты исполнителей, кроме роли шага.
OTHER_ROLES = tuple(name for name, fields in FIXTURE_ROLES.items()
                    if fields.get("executor") == "agent" and name != ROLE)

CLAUDE, CODEX = "claude", "codex"
STUB_BIN = "/artel-test-stub-bin"

#: Невыполненный вход Codex: (код выхода, stderr) `codex login status`.
NOT_LOGGED_IN = (
    (1, "Not logged in\n"),
    (0, "Not logged in\n"),
    (0, "Logged in using an API key - sk-***\n"),
)
LOGGED_IN = (0, "Logged in using ChatGPT\n")

LIVE_STATES = ("spec_gate", "tests_writing", "in_dev", "review",
               "acceptance", "merge_gate", "escalated")
CLOSED_STATES = ("done", "killed")


def model_sets_text(sets: dict, pairs: dict, templates: dict) -> str:
    """Текст `model_sets.yaml` в подмножестве YAML пульта."""
    lines = ["sets:"]
    for name, members in sets.items():
        lines.append(f"  {name}:")
        lines += [f"    {role}: {model}" for role, model in members.items()]
    lines.append("pairs:")
    for role, entries in pairs.items():
        lines.append(f"  {role}:")
        for model in entries:
            lines += [f"    {model}:", "      date: 2026-10-01",
                      "      basis: решение Оператора",
                      "      state: допущена"]
    lines.append("canary_templates:")
    lines += [f"  {title}: {cls}" for title, cls in templates.items()]
    return "\n".join(lines) + "\n"


class SetPreflightSandbox(LightTransitionSandbox):
    """Лёгкая песочница переходов с брифом шага и НАСТОЯЩИМ предполётом:
    CLI агента подменён (`runner.spawn_agent`), слот keychain отдаёт токен,
    наличие CLI и вход Codex задаёт сценарий (`self.missing`,
    `self.login`)."""

    TOKEN = "tok-test"

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rnd = random.Random(self.seed)
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates",
                        dirs_exist_ok=True)
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills",
                        dirs_exist_ok=True)
        seed_developer_brief_fixtures(self.root)
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        env.start()
        self.addCleanup(env.stop)
        # Вход Claude сверяется по слоту keychain: ambient-токен процесса
        # прогона сильнее слота и подменил бы предмет проверки.
        for name in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY"):
            os.environ.pop(name, None)
        self.patch(runner, "time", TimeWithSleep(lambda _: None))
        self.patch(keychain, "token", lambda slot: self.TOKEN)

        self.missing = set()
        self.login = LOGGED_IN
        previous_which = shutil.which
        previous_run = subprocess.run

        def which(name, *args, **kwargs):
            if name in self.missing:
                return None
            if name in (CLAUDE, CODEX, "gh"):
                return f"{STUB_BIN}/{name}"
            return previous_which(name, *args, **kwargs)

        def run(cmd, *args, **kwargs):
            if isinstance(cmd, (list, tuple)) and cmd:
                argv = [str(part) for part in cmd]
                tool = Path(argv[0]).name
                if tool in self.missing:
                    raise FileNotFoundError(f"песочница: {tool} не установлен")
                if tool == CODEX and "login" in argv and "status" in argv:
                    code, err = self.login
                    return subprocess.CompletedProcess(argv, code, "", err)
                if tool == CODEX and "--version" in argv:
                    return subprocess.CompletedProcess(
                        argv, 0, "codex-cli 0.155.1\n", "")
                if tool == CLAUDE and "--version" in argv:
                    return subprocess.CompletedProcess(
                        argv, 0, "2.1.300 (Claude Code)\n", "")
            return previous_run(cmd, *args, **kwargs)

        self.patch(shutil, "which", which)
        self.patch(subprocess, "run", run)

        self.use_catalog_fixture()
        self.use_role_map(allow_experimental=(FIXTURE_CODEX_MODEL,))
        self.combat = {role: FIXTURE_TIER_MODEL
                       for role in (ROLE,) + OTHER_ROLES}
        self.hard = f"canary-trudnyy-{self.rnd.randrange(10 ** 6)}"
        self.templates = {self.hard: "трудный"}
        self.sets, self.pairs = {}, {}
        self.run_no = 0
        self.title_no = 0
        self.neighbour = self.TASK

    def patch(self, target, attr, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def note(self, extra: str = "") -> str:
        return f"зерно {self.seed}. {extra}"

    # ------------------------------------------------------------ набор

    def register_set(self, members: dict) -> str:
        """Допущенный набор: не-боевые пары записаны допущенными, есть
        зелёный прогон набором целиком на трудном шаблоне. Имя набора."""
        name = f"nabor-{self.rnd.randrange(10 ** 6)}"
        self.sets[name] = dict(members)
        for role, model in members.items():
            if model != self.combat.get(role):
                self.pairs.setdefault(role, {})[model] = True
        models.model_sets_path().write_text(
            model_sets_text(self.sets, self.pairs, self.templates),
            encoding="utf-8")
        self.run_no += 1
        pairs = dict(self.combat)
        pairs.update(members)
        named = ", ".join(f"{role} → {model}" for role, model in pairs.items())
        store.insert_canary_run(
            store.db(), f"stamp-{self.run_no}", self.hard,
            f"T-RUN-{self.run_no}", 10, 1.0, 0, 0, "merge_gate", None, False,
            False, main_sha="0" * 40, verdict="green",
            models_summary=f"{named}; источник: слой пульта")
        return name

    def cli(self, *argv: str) -> tuple:
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

    def new_set_task(self, set_name: str) -> str:
        self.title_no += 1
        title = f"Задача набора {self.title_no}-{self.rnd.randrange(10 ** 6)}"
        tz = config.ROOT / ".artel" / f"tz-{self.title_no}.md"
        tz.parent.mkdir(parents=True, exist_ok=True)
        tz.write_text("Учебное ТЗ задачи на наборе моделей.\n", encoding="utf-8")
        ok, output = self.cli("new", title, "--tz", str(tz), "--set", set_name)
        ids = [row["id"] for row in store.all_tasks(store.db())
               if row["title"] == title]
        self.assertTrue(ok and ids, self.note(f"new --set {set_name}:\n{output}"))
        return ids[0]

    def codex_set(self) -> tuple:
        """(имя набора, задача) — набор переводит роль шага на модель Codex,
        случайные другие роли — на модель Codex либо другую модель Claude."""
        members = {ROLE: FIXTURE_CODEX_MODEL}
        for role in self.rnd.sample(OTHER_ROLES, self.rnd.randint(0, 2)):
            members[role] = self.rnd.choice([FIXTURE_CODEX_MODEL,
                                             FIXTURE_OTHER_MODEL])
        name = self.register_set(members)
        return name, self.new_set_task(name)

    # ------------------------------------------------------------- шаг

    def run_step(self, task_id: str) -> dict:
        """Шаг роли задачи в `in_dev`: вызовы `spawn_agent`, отказ шага,
        печать, новые записи журнала."""
        conn = store.db()
        store.update_task(conn, task_id, state="in_dev", paused=0)
        sync_spec_from_worktree(task_id)
        plan_dir = self.wt_path / config.TASKS.name / task_id
        plan_dir.mkdir(parents=True, exist_ok=True)
        (plan_dir / "PLAN.md").write_text("маркер\n", encoding="utf-8")
        rows = store.task_steps(conn, task_id)
        before = rows[-1]["id"] if rows else 0
        calls = []

        def spawn(cmd, *args, **kwargs):
            calls.append(list(cmd))
            return FakeProc([event(type="result", subtype="success",
                                   is_error=False, result="готово",
                                   total_cost_usd=0.1)])

        refusal, buf = "", io.StringIO()
        with mock.patch.object(runner, "spawn_agent", side_effect=spawn), \
                contextlib.redirect_stdout(buf):
            try:
                runner.cmd_run(task_id)
            except SystemExit as exc:
                refusal = str(exc.code)
        # Задача, отработавшая шаг, уходит с дороги соседей: ручной гейт.
        store.update_task(conn, task_id, state="spec_gate")
        new_rows = [row for row in store.task_steps(conn, task_id)
                    if row["id"] > before]
        # Актор записи журнала в строку не входит: роль обязана стоять в
        # самой причине отказа, а не в подписи записи.
        lines = refusal.splitlines() + buf.getvalue().splitlines()
        lines += [f"{row['action']}: {row['detail'] or ''}" for row in new_rows]
        return {"calls": calls, "rows": new_rows, "lines": lines,
                "text": "\n".join(lines)}

    def assert_refused_before_start(self, step: dict, why: str) -> None:
        """Агент не запускался ни разу, повторов нет, и шаг не дошёл до
        фазы запуска агента (ни одной записи журнала `agent run …`, в том
        числе `agent run SKIPPED` сборки окружения запуска)."""
        self.assertEqual(step["calls"], [], self.note(
            f"{why}: агент запущен:\n{step['text']}"))
        retries = [row for row in step["rows"] if "retry" in row["action"]]
        self.assertEqual(retries, [], self.note(f"{why}: повтор:\n{step['text']}"))
        launch = [row for row in step["rows"]
                  if row["action"].startswith("agent run")]
        self.assertEqual(launch, [], self.note(
            f"{why}: шаг дошёл до запуска агента:\n{step['text']}"))

    def refusal_lines(self, step: dict, *needles: str) -> list:
        """Строки отказа (текст выхода, печать, журнал), несущие каждую из
        `needles` (без учёта регистра)."""
        return [line for line in step["lines"]
                if all(needle.lower() in line.lower() for needle in needles)]

    def assert_launched(self, step: dict, cli: str, model: str,
                        why: str) -> None:
        self.assertTrue(step["calls"], self.note(
            f"{why}: агент не запущен:\n{step['text']}"))
        argv = step["calls"][0]
        self.assertEqual(Path(argv[0]).name, cli, self.note(f"{why}: {argv}"))
        self.assertIn(model, argv, self.note(f"{why}: {argv}"))


class SetStepPreflightTest(SetPreflightSandbox):

    def test_ac1_set_step_on_codex_starts_without_claude_login(self):
        """Набор переводит роль на Codex, вход Claude в слоте keychain не годится.

        Сценарий: CLI `claude` на машине есть (обязательный инструмент
        манифеста), но ни один слот keychain не отдаёт токен Claude
        (случайно: пусто либо `None`); CLI `codex` есть, вход Codex
        выполнен. Соседняя задача без набора (та же роль) отклонена до
        запуска агента — Claude в этом сценарии действительно не годится;
        шаг developer задачи с набором проходит предполёт, и агент
        запущен CLI `codex` с моделью набора. Порядок шагов — случайный.

        Ловит мутацию: предполёт шага задачи с набором проверяет вход
        боевого провайдера роли (`check_token` Claude) — шаг отклоняется
        `pre-flight FAILED: token: … токен не найден`, `spawn_agent` не
        вызван ни разу."""
        name, task = self.codex_set()
        empty = self.rnd.choice((None, ""))
        self.patch(keychain, "token", lambda slot: empty)
        order = [("neighbour", self.neighbour), ("set", task)]
        self.rnd.shuffle(order)

        steps = {kind: self.run_step(task_id) for kind, task_id in order}

        self.assert_refused_before_start(
            steps["neighbour"], "соседняя без набора, нет токена Claude")
        self.assert_launched(steps["set"], CODEX, FIXTURE_CODEX_MODEL,
                             f"набор {name}, нет токена Claude")

    def test_ac2_missing_codex_cli_refuses_set_step_naming_provider_role_set(self):
        """Набор переводит роль на Codex, CLI `codex` на машине нет.

        Сценарий: задача заведена с допущенным набором (developer — модель
        Codex, случайные другие роли), затем `codex` пропадает из системы;
        шаг developer этой задачи отклонён до запуска агента —
        `spawn_agent` не вызван ни разу, записей повтора нет, — и среди
        строк отказа есть строка, называющая `codex`, роль и имя набора.

        Ловит мутацию: отказ по CLI провайдера шага собран без набора
        (Оператор видит «codex не найден», но не видит, что его требует
        набор задачи, а не ярус) либо без роли — строки с `codex`, ролью
        и набором среди строк отказа нет."""
        name, task = self.codex_set()
        self.missing = {CODEX}

        step = self.run_step(task)

        self.assert_refused_before_start(step, f"набор {name}, нет codex")
        self.assertTrue(self.refusal_lines(step, CODEX, ROLE, name), self.note(
            f"нет строки отказа с codex, {ROLE} и {name}:\n{step['text']}"))

    def test_ac4_codex_login_missing_refuses_set_step_naming_provider_role_set(self):
        """Набор переводит роль на Codex, CLI есть, вход Codex не выполнен.

        Сценарий: `codex login status` отвечает невыполненным входом
        (случайно: код 1 «Not logged in», код 0 «Not logged in» либо вход
        ключом API); шаг developer задачи с набором отклонён до запуска
        агента без повтора, и строка отказа называет `codex`, роль, набор
        и говорит о входе.

        Ловит мутацию: предполёт шага проверяет токен Claude (провайдер
        роли) вместо входа Codex (провайдер шага) — токен в слоте есть,
        предполёт зелёный, и шаг уходит платной попыткой в
        неавторизованный CLI; либо отказ по входу не называет набор."""
        name, task = self.codex_set()
        self.login = self.rnd.choice(NOT_LOGGED_IN)

        step = self.run_step(task)

        self.assert_refused_before_start(step, f"набор {name}, вход {self.login}")
        named = self.refusal_lines(step, CODEX, ROLE, name)
        self.assertTrue(named, self.note(
            f"нет строки отказа с codex, {ROLE} и {name}:\n{step['text']}"))
        self.assertTrue(
            any(word in line.lower() for line in named
                for word in ("вход", "login", "auth")),
            self.note(f"отказ не говорит о входе:\n{step['text']}"))


class NeighbourPreflightTest(SetPreflightSandbox):

    def test_ac3_neighbour_without_set_refused_naming_combat_provider_cli(self):
        """Соседняя задача без набора — предполёт по боевому провайдеру роли.

        Сценарий: рядом живёт задача с набором, переводящим developer на
        Codex (CLI `codex` есть, вход выполнен); CLI `claude` пропал.
        Шаг developer соседней задачи без набора отклонён до запуска
        агента, и среди строк отказа есть строка, называющая `claude` и не
        называющая `codex`, — как до задачи.

        Ловит мутацию: провайдер шага задачи без набора берётся из
        набора другой живой задачи (или из перечня провайдеров наборов
        в работе) — соседняя задача проверяет Codex, и её отказ говорит
        о входе Codex (пусть и с `claude` в тексте), а не о CLI Claude;
        либо предполёт задачи без набора перестаёт проверять CLI вовсе, и
        шаг доходит до запуска агента."""
        self.codex_set()
        self.missing = {CLAUDE}

        step = self.run_step(self.neighbour)

        self.assert_refused_before_start(step, "соседняя без набора, нет claude")
        own = [line for line in self.refusal_lines(step, CLAUDE)
               if CODEX not in line.lower()]
        self.assertTrue(own, self.note(
            f"нет отказа по claude, не приписанного codex:\n{step['text']}"))

    def test_ac3_preflight_follows_step_provider_not_role_provider(self):
        """Боевой провайдер роли — Codex без входа; набор ведёт роль на Claude.

        Сценарий: карта исполнителей держит developer на `codex` с ярусом,
        разрешающимся в модель Codex; вход Codex не выполнен (вид —
        случайно). Соседняя задача без набора: шаг developer отклонён до
        запуска агента, отказ называет `codex`. Задача с набором,
        переводящим developer на модель Claude: предполёт проходит, агент
        запущен CLI `claude` с моделью набора.

        Ловит мутацию: предполёт по провайдеру роли, а не шага — шаг
        задачи с набором проверяет вход Codex и отклоняется, хотя идёт
        CLI Claude."""
        tier = next(t for t in models.TIERS if t != FIXTURE_TIER)
        self.use_role_map(roles={ROLE: {"provider": CODEX, "model_tier": tier}},
                          tiers={tier: FIXTURE_CODEX_MODEL},
                          allow_experimental=(FIXTURE_CODEX_MODEL,))
        self.combat[ROLE] = FIXTURE_CODEX_MODEL
        name = self.register_set({ROLE: FIXTURE_OTHER_MODEL})
        task = self.new_set_task(name)
        self.login = self.rnd.choice(NOT_LOGGED_IN)
        order = [("neighbour", self.neighbour), ("set", task)]
        self.rnd.shuffle(order)

        steps = {kind: self.run_step(task_id) for kind, task_id in order}

        neighbour = steps["neighbour"]
        self.assert_refused_before_start(neighbour, "соседняя, боевой codex")
        self.assertTrue(self.refusal_lines(neighbour, CODEX), self.note(
            f"отказ соседней не называет codex:\n{neighbour['text']}"))
        self.assert_launched(steps["set"], CLAUDE, FIXTURE_OTHER_MODEL,
                             f"набор {name} на модели Claude")


class DoctorSetProvidersTest(SetPreflightSandbox):

    def checks(self) -> set:
        """Имена строк `doctor.all_checks`; внешние процессы не
        исполняются, пул канарейки ищется во временном доме."""
        home = self.root / "dom"
        home.mkdir(exist_ok=True)

        def no_process(*args, **kwargs):
            raise FileNotFoundError("песочница: внешний процесс не запускается")

        with mock.patch.object(Path, "home", lambda *a, **k: home), \
                mock.patch.object(doctor.subprocess, "run",
                                  side_effect=no_process), \
                mock.patch.object(doctor.subprocess, "Popen",
                                  side_effect=no_process), \
                contextlib.redirect_stdout(io.StringIO()):
            return {check.name for check in doctor.all_checks(store.db())}

    def test_ac5_doctor_adds_set_provider_lines_only_for_live_tasks(self):
        """`doctor` спрашивает провайдера набора задачи в работе.

        Сценарий: боевой набор — только Claude; задача с набором,
        переводящим developer на Codex, в случайном незакрытом состоянии.
        Строки `doctor` несут проверки CLI и входа Codex
        (`codex-cli-found`, строка входа Codex) рядом со строками Claude
        (`cli-found`, `token`). Та же задача в `done` или `killed`
        (случайно) — строк Codex нет, строки Claude на месте.

        Ловит мутацию: склейка `doctor` спрашивает только провайдеров
        ролей карты — набор задачи в работе не добавляет строк Codex; либо
        добавка не фильтрует закрытые задачи, и набор `done`/`killed`
        задачи продолжает требовать вход Codex."""
        name, task = self.codex_set()
        live = self.rnd.choice(LIVE_STATES)
        closed = self.rnd.choice(CLOSED_STATES)
        conn = store.db()
        codex_lines = ("codex-cli-found", doctor.CODEX_AUTH_CHECK)

        store.update_task(conn, task, state=live)
        names = self.checks()
        for line in ("cli-found", "token") + codex_lines:
            self.assertIn(line, names, self.note(
                f"{live}, набор {name}: нет строки {line}: {sorted(names)}"))

        store.update_task(conn, task, state=closed)
        names = self.checks()
        for line in ("cli-found", "token"):
            self.assertIn(line, names, self.note(f"{closed}: {sorted(names)}"))
        for line in codex_lines:
            self.assertNotIn(line, names, self.note(
                f"{closed}, набор {name}: строка {line}: {sorted(names)}"))


if __name__ == "__main__":
    unittest.main()
