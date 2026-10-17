"""Шаг роли задачи внешнего проекта: проектные скилы в брифе, белый список
и окружение роли, явное определение проекта задачи на пути запуска шага.

Группа: долгоживущий

Красен до реализации: бриф шага несёт только скилы роли из `roles.yaml` — текстов `project_skills` в нём нет (AC-2), а неверное имя скила не отказывает (AC-3); argv роли Claude задачи внешнего проекта несёт `Bash(python3:*)`, а окружение шага любого провайдера — без `GIT_CONFIG_NOSYSTEM=1` (AC-4, AC-6); шаг задачи с необъявленным проектом или при нечитаемом `targets.yaml` не отказывает именованным отказом, называющим задачу и причину (AC-8).

Файл провалидирован временным стабом реализации в `runner`: проект задачи
— `targets.target(t["target"])` с отказом `run отклонён: проект задачи не
определён`, проектные скилы — проверка имени и `gitcmd.show` головы main
после скилов роли, `GIT_CONFIG_NOSYSTEM=1` и правило `artel.py` — для
задачи не артели. Все методы зелёные в нескольких прогонах с разными
зёрнами. Мутации стаба: меры для всех задач красят AC-1 и контроль AC-6;
проверка имени только по существованию красит AC-3 (родительский каталог,
абсолютный путь, подкаталог). Стаб удалён, код репозитория не тронут.

Публичная поверхность, которую читает файл:

- шаг роли — `runner.cmd_run(<id>)` с подменённым `runner.spawn_agent`:
  «агент запущен» — вызов `spawn_agent`; его argv, `env=` и промпт
  (файл на `stdin=`) — то, что шаг передал в запуск агента; отказ —
  `SystemExit`, печать и новые записи `store.task_steps`;
- проект задачи — колонка `target` строки задачи (`store.update_task`),
  запись проекта — `config.TARGETS` песочницы, `targets.load()`;
- голова `main` пульта — в `LightTransitionSandbox` её чтение
  (`gitcmd.show`) отвечает диском `config.ROOT` песочницы: скил «есть в
  голове main» — файл `config.ROOT/skills/<имя>.md` песочницы. Различие
  «голова main / только диск пульта» (SPEC, требование 2) этому файлу
  недоступно — его держит разовая планка задачи;
- скилы роли — `roles.skills(role)` карты-фикстуры (`use_role_map`).

Окружение — `tests/sandbox.py` (`LightTransitionSandbox`,
`use_catalog_fixture`, `use_role_map`, `seed_developer_brief_fixtures`).
Имена проектов, скилов, их тексты, порядок поля, роль шага и вид поломки
`targets.yaml` выбираются модулем `random`; зерно печатается и входит в
текст провала.
"""
import contextlib
import io
import os
import random
import shutil
import string
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (catalog, config, keychain, models, roles, runner,
                          store, targets)
from tests.sandbox import (FIXTURE_CODEX_MODEL, FIXTURE_TIER, FakeProc,
                           LightTransitionSandbox, TimeWithSleep,
                           capture_new_task_id, event,
                           seed_developer_brief_fixtures,
                           sync_spec_from_worktree)

#: Корень репозитория — источник `templates/`/`skills/` для брифа шага.
REPO_ROOT = Path(__file__).resolve().parent.parent

CLAUDE, CODEX = "claude", "codex"
STUB_BIN = "/artel-test-stub-bin"
LOGGED_IN = (0, "Logged in using ChatGPT\n")

#: Состояния агентских шагов без подтяжки main и без занятости зоны.
STEP_STATES = {"tests_writing": "test_author", "review": "reviewer"}

ARTEL_WHITELIST = "Bash(git:*),Bash(python3:*)"
NOSYSTEM = "GIT_CONFIG_NOSYSTEM"

PROJECT_ENTRY = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: [{skills}]
    merge_gate: operator
"""


def word(rnd: random.Random, k: int = 6) -> str:
    return "".join(rnd.choices(string.ascii_lowercase, k=k))


class ProjectStepSandbox(LightTransitionSandbox):
    """Лёгкая песочница переходов с брифом шага и настоящим предполётом:
    CLI агента подменён (`runner.spawn_agent`), слот keychain отдаёт токен,
    голова `main` пульта — диск `config.ROOT` песочницы."""

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
        for name in ("CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY", NOSYSTEM):
            os.environ.pop(name, None)
        self.patch(runner, "time", TimeWithSleep(lambda _: None))
        # Предмет — то, что шаг передал в первый запуск агента; повторы
        # попыток после него ничего не добавляют.
        self.patch(config, "AGENT_ATTEMPTS", 1)
        self.patch(keychain, "token", lambda slot: self.TOKEN)

        previous_which = shutil.which
        previous_run = subprocess.run

        def which(name, *args, **kwargs):
            if name in (CLAUDE, CODEX, "gh"):
                return f"{STUB_BIN}/{name}"
            return previous_which(name, *args, **kwargs)

        def run(cmd, *args, **kwargs):
            if isinstance(cmd, (list, tuple)) and cmd:
                argv = [str(part) for part in cmd]
                tool = Path(argv[0]).name
                if tool == CODEX and "login" in argv and "status" in argv:
                    code, err = LOGGED_IN
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
        self.use_role_map()

        self.task_no = 0

    def patch(self, target, attr, value) -> None:
        patcher = mock.patch.object(target, attr, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def note(self, extra: str = "") -> str:
        return f"зерно {self.seed}. {extra}"

    # ------------------------------------------------------ голова main

    def place_in_main(self, rel: str, text: str) -> None:
        """Кладёт файл `rel` в голову `main` пульта песочницы — её диск
        `config.ROOT` (`LightTransitionSandbox` читает `gitcmd.show`
        головы main с диска)."""
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def main_text(self, rel: str) -> str:
        """Текст файла `rel` головы `main` пульта песочницы."""
        return (self.root / rel).read_text(encoding="utf-8")

    # ------------------------------------------------------- проекты

    def declare_project(self, name: str, skills: list) -> None:
        """Запись проекта `name` с полем `project_skills` в `config.TARGETS`."""
        listed = ", ".join(skills)
        text = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(
            text.rstrip("\n") + "\n" + PROJECT_ENTRY.format(
                name=name, base=config.MAIN_BRANCH, skills=listed),
            encoding="utf-8")

    def project_skill(self, tag: str) -> tuple:
        """(имя, текст) нового проектного скила `skills/<имя>.md` головы main."""
        name = f"proekt-{tag}-{word(self.rnd)}"
        text = f"# Проектный скил {name}\n\nПравило {word(self.rnd, 12)}.\n"
        self.place_in_main(f"skills/{name}.md", text)
        return name, text

    def new_task(self, target: str) -> str:
        self.task_no += 1
        title = f"Задача проекта {self.task_no} {word(self.rnd)}"
        _, task_id = capture_new_task_id(catalog.cmd_new, title)
        store.update_task(store.db(), task_id, target=target)
        return task_id

    # ------------------------------------------------------------- шаг

    def run_step(self, task_id: str, state: str = None) -> dict:
        """Шаг роли задачи: вызовы `spawn_agent` (argv, env, промпт),
        текст отказа, печать, новые записи журнала."""
        conn = store.db()
        if state is None:
            state = self.rnd.choice(sorted(STEP_STATES))
        store.update_task(conn, task_id, state=state, paused=0)
        sync_spec_from_worktree(task_id)
        rows = store.task_steps(conn, task_id)
        before = rows[-1]["id"] if rows else 0
        calls = []

        def spawn(cmd, *args, **kwargs):
            stdin = kwargs.get("stdin")
            calls.append({"argv": list(cmd), "env": dict(kwargs.get("env") or {}),
                          "prompt": stdin.read() if stdin is not None else ""})
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
        store.update_task(conn, task_id, state="spec_gate")
        new_rows = [row for row in store.task_steps(conn, task_id)
                    if row["id"] > before]
        lines = refusal.splitlines() + buf.getvalue().splitlines()
        journal = [f"{row['action']}: {row['detail'] or ''}" for row in new_rows]
        return {"calls": calls, "rows": new_rows, "refusal": refusal,
                "lines": lines, "role": STEP_STATES[state], "state": state,
                "text": "\n".join(lines + journal)}

    def assert_launched(self, step: dict, why: str) -> dict:
        self.assertTrue(step["calls"], self.note(
            f"{why}: агент не запущен:\n{step['text']}"))
        return step["calls"][0]

    def assert_not_launched(self, step: dict, why: str) -> None:
        argv = step["calls"][0]["argv"] if step["calls"] else None
        self.assertEqual(len(step["calls"]), 0, self.note(
            f"{why}: агент запущен, argv {argv}:\n{step['text']}"))

    def allowed_tools(self, call: dict) -> str:
        argv = call["argv"]
        self.assertIn("--allowedTools", argv, self.note(str(argv)))
        return argv[argv.index("--allowedTools") + 1]

    def use_codex_role_map(self) -> None:
        """Обе роли шага — на провайдере Codex (ярус с моделью Codex)."""
        tier = next(t for t in models.TIERS if t != FIXTURE_TIER)
        self.use_role_map(
            roles={role: {"provider": CODEX, "model_tier": tier}
                   for role in STEP_STATES.values()},
            tiers={tier: FIXTURE_CODEX_MODEL},
            allow_experimental=(FIXTURE_CODEX_MODEL,))


def project_whitelist() -> str:
    artel_py = config.ROOT / "orchestrator" / "artel.py"
    return f"Bash(git:*),Bash(python3 {artel_py}:*)"


class ArtelStepTest(ProjectStepSandbox):

    def test_ac1_artel_step_keeps_artel_whitelist_and_environment(self):
        """Задача артели: шаг Claude идёт с прежним белым списком и окружением.

        Сценарий: задача артели (`project_skills: []` записи песочницы) в
        случайном агентском состоянии; рядом объявлен внешний проект с
        непустым `project_skills`. Шаг доходит до запуска агента;
        `--allowedTools` argv целиком равно `Bash(git:*),Bash(python3:*)`;
        в окружении шага нет `GIT_CONFIG_NOSYSTEM`; в промпте нет текста
        проектного скила соседнего проекта.

        Ловит мутацию: меры для роли внешнего проекта применены ко всем
        задачам (условие по проекту перевёрнуто или пропущено) — у шага
        артели белый список с `artel.py` вместо `Bash(python3:*)` либо
        `GIT_CONFIG_NOSYSTEM=1` в окружении; либо проектные скилы берутся
        не из записи проекта задачи — в брифе артели текст чужого скила."""
        skill, text = self.project_skill("sosed")
        self.declare_project(f"sosed{word(self.rnd)}", [skill])

        step = self.run_step(self.TASK)

        call = self.assert_launched(step, "задача артели")
        self.assertEqual(self.allowed_tools(call), ARTEL_WHITELIST,
                         self.note(str(call["argv"])))
        self.assertNotIn(NOSYSTEM, call["env"], self.note(
            f"окружение шага артели: {sorted(call['env'])}"))
        self.assertFalse(text.strip() in call["prompt"], self.note(
            "в бриф артели попал проектный скил соседнего проекта"))


class ProjectSkillsBriefSandbox(ProjectStepSandbox):
    """Сценарии брифа с проектными скилами — общие для этого файла и для
    сценариев, где голова main отличается от диска пульта."""

    def brief_with_project_skills(self) -> tuple:
        """(скилы [(имя, текст)] в порядке поля, промпт, роль шага) —
        шаг задачи внешнего проекта с 2–4 проектными скилами в случайном
        порядке поля дошёл до запуска агента; тексты скилов роли и
        проектных скилов в промпте, проектные — после всех скилов роли и
        в порядке поля."""
        skills = [self.project_skill(f"s{i}")
                  for i in range(self.rnd.randint(2, 4))]
        self.rnd.shuffle(skills)
        project = f"proekt{word(self.rnd)}"
        self.declare_project(project, [name for name, _ in skills])
        task = self.new_task(project)

        step = self.run_step(task)

        call = self.assert_launched(step, f"проект {project}, скилы {skills}")
        prompt = call["prompt"]
        role_positions = []
        for name in roles.skills(step["role"]):
            role_text = self.main_text(f"skills/{name}.md")
            self.assertTrue(role_text in prompt, self.note(
                f"нет скила роли {name}"))
            role_positions.append(prompt.find(role_text))
        last_role = max(role_positions) if role_positions else -1
        positions = []
        for name, text in skills:
            self.assertTrue(text in prompt, self.note(
                f"нет текста проектного скила {name} из головы main"))
            positions.append(prompt.find(text))
        self.assertTrue(all(pos > last_role for pos in positions), self.note(
            f"проектный скил раньше скилов роли: {positions} при {last_role}"))
        self.assertEqual(positions, sorted(positions), self.note(
            f"порядок поля {[n for n, _ in skills]} нарушен: {positions}"))
        return skills, prompt, step["role"]

    def assert_invalid_name_refused(self, kind: str, bad: str) -> None:
        """Проект с неверным именем `bad` среди верных проектных скилов (в
        случайной позиции): шаг его задачи не запускает агента, строка
        отказа называет проект, `project_skills` и `bad`; `targets.load()`
        читает файл с этой записью; задача соседнего проекта с верным
        полем доходит до запуска агента с его скилом в брифе."""
        good, good_text = self.project_skill("verno")
        good_project = f"verno{word(self.rnd)}"
        self.declare_project(good_project, [good])
        others = [self.project_skill(f"o{i}")[0]
                  for i in range(self.rnd.randint(0, 2))]
        field = list(others)
        field.insert(self.rnd.randint(0, len(field)), bad)
        project = f"slom{word(self.rnd)}"
        self.declare_project(project, field)
        task = self.new_task(project)

        step = self.run_step(task)

        why = f"{kind}: проект {project}, поле {field}"
        self.assert_not_launched(step, why)
        named = [line for line in step["lines"]
                 if project in line and "project_skills" in line
                 and bad in line]
        self.assertTrue(named, self.note(
            f"{why}: нет строки отказа с проектом, project_skills и "
            f"именем {bad!r}:\n{step['text']}"))
        self.assertIn(project, targets.load(), self.note(why))

        ok = self.run_step(self.new_task(good_project))
        call = self.assert_launched(ok, f"{why}: соседний {good_project}")
        self.assertTrue(good_text in call["prompt"], self.note(
            f"{why}: нет скила {good} в брифе {good_project}"))


class ProjectSkillsBriefTest(ProjectSkillsBriefSandbox):

    def test_ac2_project_skills_after_role_skills_in_field_order(self):
        """Тексты `project_skills` — в брифе после скилов роли, в порядке поля.

        Сценарий: внешний проект объявлен с 2–4 проектными скилами
        (`skills/<имя>.md` головы main пульта песочницы) в случайном
        порядке поля. Шаг задачи проекта в случайном агентском состоянии
        доходит до запуска агента; в промпте есть текст каждого скила
        роли (`roles.skills`) и каждого проектного скила; каждый проектный
        текст стоит позже всех текстов скилов роли, проектные тексты — в
        порядке поля.

        Ловит мутацию: проектные скилы не добавлены в бриф (их текстов в
        промпте нет); вставлены перед скилами роли; отсортированы по имени
        или взяты в порядке файлов каталога, а не поля."""
        self.brief_with_project_skills()

    def test_ac3_invalid_project_skill_refuses_brief_naming_project_field_skill(self):
        """Неверное имя `project_skills` — отказ сборки брифа с проектом, полем и именем.

        Сценарий (`subTest` на вид): выход в родительский каталог
        (`../CLAUDE`, `../templates/PLAN`), абсолютный путь к тому же
        файлу, подкаталог `skills/` (`sub/name`), имя несуществующего
        файла. Файлы первых трёх видов в голове main песочницы есть —
        отказ обязан следовать из самого имени. Для каждого вида свой
        внешний проект, неверное имя — среди верных проектных скилов.
        Шаг его задачи не запускает агента; строка отказа (текст выхода,
        печать) называет проект, `project_skills` и неверное имя;
        `targets.load()` читает файл; задача соседнего проекта с верным
        полем доходит до запуска агента с его скилом в брифе.

        Ловит мутацию: имя проверяется только на существование файла —
        `../CLAUDE`, абсолютный путь и `sub/name` проходят, шаг уходит в
        запуск агента; неверное имя молча пропускается; отказ не называет
        проект или поле; проверка перенесена в `targets.py` и делает
        `targets.yaml` негодным для всех проектов (`targets.load()`
        отказывает, соседний проект не стартует)."""
        sub = f"pod{word(self.rnd)}/imya{word(self.rnd)}"
        self.place_in_main(f"skills/{sub}.md", "# скил в подкаталоге\n")
        outside = self.rnd.choice(["CLAUDE", "templates/PLAN"])
        absolute = str(self.root / outside)
        # Абсолютное имя в форме `skills/<имя>.md` — путь внутри `skills/`.
        self.place_in_main(f"skills/{absolute.lstrip('/')}.md", "# абс\n")
        kinds = {
            "родительский каталог": f"../{outside}",
            "абсолютный путь": absolute,
            "подкаталог skills/": sub,
            "нет файла": f"net{word(self.rnd)}",
        }
        for kind, bad in kinds.items():
            with self.subTest(kind=kind, name=bad):
                self.assert_invalid_name_refused(kind, bad)


class ProjectRoleMeasuresTest(ProjectStepSandbox):

    def test_ac4_external_claude_step_artel_py_whitelist_and_nosystem(self):
        """Задача внешнего проекта: белый список Claude — git и `artel.py` по абсолютному пути.

        Сценарий: внешний проект (с пустым либо непустым `project_skills`
        — случайно), шаг его задачи в случайном агентском состоянии на
        провайдере Claude доходит до запуска агента. Значение
        `--allowedTools` argv целиком равно
        `Bash(git:*),Bash(python3 <config.ROOT>/orchestrator/artel.py:*)`;
        окружение шага содержит `GIT_CONFIG_NOSYSTEM=1`.

        Ловит мутацию: `Bash(python3:*)` оставлен рядом с правилом
        `artel.py` либо вместо него; путь в правиле относительный или
        собран не от `config.ROOT`; `GIT_CONFIG_NOSYSTEM` не поставлен
        (или поставлен не `1`) у задачи внешнего проекта."""
        skills = ([self.project_skill("m")[0]] if self.rnd.random() < 0.5
                  else [])
        project = f"proekt{word(self.rnd)}"
        self.declare_project(project, skills)
        task = self.new_task(project)

        step = self.run_step(task)

        call = self.assert_launched(step, f"проект {project}")
        self.assertEqual(self.allowed_tools(call), project_whitelist(),
                         self.note(str(call["argv"])))
        self.assertEqual(call["env"].get(NOSYSTEM), "1", self.note(
            f"окружение шага: {sorted(call['env'])}"))

    def test_ac6_external_codex_step_env_has_nosystem(self):
        """Шаг роли на Codex задачи внешнего проекта — `GIT_CONFIG_NOSYSTEM=1` в окружении.

        Сценарий: обе агентские роли шага — на провайдере Codex; задача
        внешнего проекта в случайном агентском состоянии; шаг доходит до
        запуска CLI `codex`, окружение запуска содержит
        `GIT_CONFIG_NOSYSTEM=1`. Задача артели на том же провайдере —
        без `GIT_CONFIG_NOSYSTEM` (контрольная).

        Ловит мутацию: `GIT_CONFIG_NOSYSTEM` кладёт только провайдер
        Claude (в `environment` Claude, а не на общем пути окружения
        шага) — у шага Codex его нет."""
        self.use_codex_role_map()
        project = f"proekt{word(self.rnd)}"
        self.declare_project(project, [])
        task = self.new_task(project)

        step = self.run_step(task)
        artel = self.run_step(self.TASK)

        call = self.assert_launched(step, f"codex, проект {project}")
        self.assertEqual(Path(call["argv"][0]).name, CODEX, self.note(
            str(call["argv"])))
        self.assertEqual(call["env"].get(NOSYSTEM), "1", self.note(
            f"окружение шага codex: {sorted(call['env'])}"))
        control = self.assert_launched(artel, "codex, артель")
        self.assertNotIn(NOSYSTEM, control["env"], self.note(
            f"окружение шага codex артели: {sorted(control['env'])}"))


class ProjectResolutionTest(ProjectStepSandbox):

    def test_ac8_undetermined_project_refuses_step_without_launch(self):
        """Проект задачи не определён — шаг отказывает именованным отказом.

        Сценарий (два случая, `subTest`): (а) target задачи внешнего
        проекта не объявлен в `targets.yaml`; (б) задача объявленного
        внешнего проекта, а `targets.yaml` не читается (случайно: файла
        нет, либо он не разбирается). Шаг в случайном агентском состоянии
        не запускает агента; среди строк отказа (текст выхода, печать)
        есть строка с id задачи и причиной: в (а) — именем
        необъявленного проекта, в (б) — именем файла `targets.yaml`.

        Ловит мутацию: на пути шага проект берётся из колонки задачи без
        сверки с `targets.yaml` либо сбой его определения откатывается на
        проект артели (`store.task_target`, `or config.DEFAULT_TARGET`) —
        шаг уходит в запуск агента с белым списком и окружением артели;
        либо отказ не называет задачу или причину."""
        undeclared = f"neob{word(self.rnd)}"
        task = self.new_task(undeclared)
        step = self.run_step(task)
        self.assert_not_launched(step, f"проект {undeclared} не объявлен")
        named = [line for line in step["lines"]
                 if task in line and undeclared in line]
        self.assertTrue(named, self.note(
            f"нет строки отказа с {task} и {undeclared}:\n{step['text']}"))

        project = f"proekt{word(self.rnd)}"
        self.declare_project(project, [])
        task = self.new_task(project)
        breakage = self.rnd.choice(["нет файла", "не разбирается"])
        with self.subTest(breakage=breakage):
            if breakage == "нет файла":
                config.TARGETS.unlink()
            else:
                config.TARGETS.write_text("targets:\n  - [не: отображение\n",
                                          encoding="utf-8")
            step = self.run_step(task)
            self.assert_not_launched(step, f"targets.yaml: {breakage}")
            named = [line for line in step["lines"]
                     if task in line and config.TARGETS.name in line]
            self.assertTrue(named, self.note(
                f"нет строки отказа с {task} и {config.TARGETS.name}:\n"
                f"{step['text']}"))


if __name__ == "__main__":
    unittest.main()
