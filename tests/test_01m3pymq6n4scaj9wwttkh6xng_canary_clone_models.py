"""Слой эфемерного клона канарейки из боевого слоя пульта, набор по
ролям, сводка моделей всех ролей, подпись «код клона» и несравнимая
базовая линия при смене моделей.

Группа: долгоживущий

Критерии приёмки, которые покрывает файл:

AC-1. Прогон без `--set` при читаемом слое пульта, где ярусы указывают
модели, отличные от шаблона: ярусы слоя клона равны ярусам слоя пульта (а
не шаблона); в слой клона перенесены разрешения `experimental` для моделей
этих ярусов, переопределения тарифа этих моделей, `role_providers:` и
`role_models:` пульта; раздела `canary_sets:` в слое клона нет.

AC-2. Слой пульта отсутствует или не разбирается: прогон не отказывает,
слой клона — шаблон `models.LOCAL_TEMPLATE`, а первая строка прогона
называет источник «шаблон» и то, что слой пульта не прочитан.

AC-6. `canary --set <набор>` с набором, называющим одну роль: в слое
клона эта роль получает модель (и провайдера) набора, три прочие
агентские роли разрешаются в слое клона в те же модели, что в слое
пульта; ярусы слоя клона равны ярусам слоя пульта.

AC-7. Набор, называющий две роли одного яруса с разными моделями,
принимается: каждая роль получает в слое клона свою модель.

AC-8. Набор с ролью вне карты исполнителей, с моделью вне каталога или с
провайдером записи, не совпадающим с провайдером модели в каталоге, —
именованный отказ `canary` до эфемерного клона: `git clone` не
вызывается, строка в `tasks` не заводится.

AC-9. Набор, называющий одну роль на модели провайдера Codex, при соседях
по ярусу на провайдере `claude`: проверка входа Codex и перенос указателя
касаются ровно этой роли; при недоказанном входе — именованный отказ до
клона, как сейчас.

AC-10. Первая строка прогона и строка итога задачи — как без набора, так
и с набором — называют модель каждой из агентских ролей прогона в виде
«<роль> → <модель>» и источник; поле `models_summary` строки
`canary_runs` несёт модели всех агентских ролей и источник.

AC-11. Строка итога задачи несёт подпись «код клона <sha>», где `<sha>` —
коммит, сообщённый процессом клона; подписи «код пина» в выводе прогона
нет, в том числе когда проверяемый sha совпадает с HEAD главной копии.

AC-12. Штатный прогон пары, чья последняя штатная строка `canary_runs`
несёт другие модели ролей (или не несёт сводки моделей всех ролей), при
существующей базовой линии: алерт `threshold` не поднимается, базовая
линия перезаписана числами прогона, примечание — предупреждение о
несравнимой базовой линии со сменой моделей, вердикт `green`.

AC-13. Штатный прогон пары с теми же моделями ролей, что у последней
штатной строки пары: отклонение сверх `CANARY_DEVIATION_RATIO` поднимает
алерт `threshold`, прежнее примечание, базовая линия не перезаписывается.

Песочница: `self.root` — настоящий git-репозиторий «пульта»
(`RealGitSandbox`) с входом ведения `canary.CANARY_DRIVE_ENTRY` в коммите;
`canary.cmd_canary` исполняется целиком — настоящий эфемерный клон,
настоящий `catalog.cmd_init` в нём, настоящая запись `canary_runs` и
базовой линии. Подменён только запуск процесса клона (`subprocess.Popen`
с модулем `canary.CANARY_DRIVE_MODULE`): в момент запуска — пока клон жив
и `config` переадресован в него — подмена снимает локальный слой клона
(`config.MODELS_LOCAL`) и разрешение `models.resolve_role` каждой
агентской роли в нём, то есть ровно то, чем шли бы шаги ролей клона, и
пишет файл результата штатной учебной задачи. Каталог моделей и карта
исполнителей — фикстуры песочницы; пул шаблонов — во временном «доме»
(`Path.home`). Роли, модели ярусов и записи наборов выбираются случайно;
зерно печатается и входит в текст провала.

Красен до реализации: без `--set` слой клона — шаблон, а набор сдвигает
ярус целиком (AC-1, AC-6, AC-7 — отказ «две разные модели ярусу», AC-9 —
соседи по ярусу уходят в Codex); первая строка не называет источник и
модели всех ролей (AC-2, AC-10); подпись — «код пина» (AC-11); смена
моделей не делает базовую линию несравнимой (AC-12). Методы AC-8, AC-13
и `test_ac9_unconfirmed_login_is_a_named_refusal` держат уже существующее
поведение (отказы набора до клона, отказ недоказанного входа Codex,
прежнее сравнение с базовой линией) и зелены с рождения.
"""
import io
import json
import os
import random
import sqlite3
import subprocess
import sys
import tempfile
import shutil
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import canary, config, doctor, models, store, yamlmini
from tests.sandbox import RealGitSandbox

AGENT_ROLES = ("analyst", "test_author", "developer", "reviewer")

POOL_TITLE = "uchebnyj-shablon"
POOL_TEXT = "# Учебная задача песочницы\n\nОдна строка описания проекта.\n"

CLAUDE_MODELS = ("m-alfa-fikstury", "m-beta-fikstury", "m-gamma-fikstury",
                 "m-delta-fikstury")
CLAUDE_EXPERIMENTAL = "m-eksperiment-fikstury"
CODEX_MODEL = "m-kodeks-fikstury"

#: Модели шаблона локального слоя — в каталоге-фикстуре, чтобы слой клона
#: из шаблона (AC-2) разрешался так же, как у настоящего пульта.
TEMPLATE_TIERS = dict(models.local_template_layer().tiers)
TEMPLATE_MODELS = tuple(sorted(set(TEMPLATE_TIERS.values())))

#: Относительный путь указателя связки ключей в доме роли — тот, что
#: `codex login` ищет от HOME (проверка входа Codex прогона читает его из
#: `config.ROLE_HOME` пульта до клона).
KEYCHAIN_POINTER = Path("Library/Preferences/com.apple.security.plist")


def model_block(model_id: str, status: str, min_cli: str) -> str:
    return (f"      {model_id}:\n"
            f"        min_cli_version: {min_cli}\n"
            f"        status: {status}\n"
            f"        list_price_usd_per_mtok:\n"
            f"          input: 5.0\n"
            f"          output: 25.0\n"
            f"          cache_write: 6.25\n"
            f"          cache_read: 0.50\n"
            f"        price_date: 2026-09-20\n")


CATALOG_TEXT = (
    "providers:\n"
    "  claude:\n"
    "    cli: claude\n"
    "    min_cli_version: 1.0.0\n"
    "    cost_from_cli: true\n"
    "    models:\n"
    + "".join(model_block(m, "supported", "1.0.0")
              for m in (*TEMPLATE_MODELS, *CLAUDE_MODELS))
    + model_block(CLAUDE_EXPERIMENTAL, "experimental", "1.0.0")
    + "  codex:\n"
    "    cli: codex\n"
    "    min_cli_version: 0.155.1\n"
    "    cost_from_cli: false\n"
    "    models:\n"
    + model_block(CODEX_MODEL, "supported", "0.155.1"))

PROVIDER_OF = {**{m: "claude" for m in (*TEMPLATE_MODELS, *CLAUDE_MODELS,
                                         CLAUDE_EXPERIMENTAL)},
               CODEX_MODEL: "codex"}


def layer_text(tiers: dict, allow=(), overrides: dict = None,
               role_providers: dict = None, role_models: dict = None,
               canary_sets: dict = None) -> str:
    """Локальный слой: `overrides` — {модель: (input, output, cache_write,
    cache_read)}, `canary_sets` — {набор: {роль: (провайдер, модель)}}."""
    text = "tiers:\n" + "".join(f"  {t}: {m}\n" for t, m in tiers.items())
    if allow:
        text += "allow_experimental:\n" + "".join(f"  {m}: true\n" for m in allow)
    if overrides:
        text += "overrides:\n"
        for model_id, prices in overrides.items():
            text += f"  {model_id}:\n" + "".join(
                f"    {kind}: {price}\n"
                for kind, price in zip(models.PRICE_KINDS, prices))
            text += "    calibrated_at: 2026-09-21\n    source: fikstura pulta\n"
    if role_providers:
        text += "role_providers:\n" + "".join(
            f"  {r}: {p}\n" for r, p in role_providers.items())
    if role_models:
        text += "role_models:\n" + "".join(
            f"  {r}: {m}\n" for r, m in role_models.items())
    if canary_sets:
        text += "canary_sets:\n"
        for name, entries in canary_sets.items():
            text += f"  {name}:\n"
            for role, (provider, model) in entries.items():
                text += (f"    {role}:\n      provider: {provider}\n"
                         f"      model: {model}\n")
    return text


class CanaryCloneSandbox(RealGitSandbox):
    """`canary.cmd_canary` целиком на git-песочнице пульта; процесс клона
    подменён наблюдателем слоя клона."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

        entry = self.root / canary.CANARY_DRIVE_ENTRY
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text("# вход ведения песочницы — процесс клона подменён\n",
                         encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "вход ведения песочницы")
        self.sha = self.git("rev-parse", "HEAD").strip()
        self.first_sha = self.git("rev-list", "--max-parents=0", "HEAD").strip()

        self.use_catalog_fixture(CATALOG_TEXT)
        self.cheap_role = self.rng.choice(AGENT_ROLES)
        self.use_role_map(roles={self.cheap_role: {"model_tier": "cheap"}})
        self.tier_of = {role: ("cheap" if role == self.cheap_role else "strong")
                        for role in AGENT_ROLES}
        self.strong_roles = [r for r in AGENT_ROLES if r != self.cheap_role]

        home = Path(tempfile.mkdtemp(prefix="planka-dom-"))
        self.addCleanup(shutil.rmtree, home, ignore_errors=True)
        pool = home / config.CANARY_POOL_DIRNAME
        pool.mkdir()
        (pool / f"{POOL_TITLE}.md").write_text(POOL_TEXT, encoding="utf-8")
        self.patch(Path, "home", lambda *a, **k: home)

        self.clone_dirs = []
        real_mkdtemp = tempfile.mkdtemp

        def tracking_mkdtemp(*args, **kwargs):
            path = real_mkdtemp(*args, **kwargs)
            prefix = kwargs.get("prefix") or (args[1] if len(args) > 1 else "")
            if str(prefix or "").startswith("artel-canary"):
                self.clone_dirs.append(path)
            return path
        self.patch(tempfile, "mkdtemp", tracking_mkdtemp)

        self.clone_calls = []
        real_run = subprocess.run

        def tracking_run(cmd, *args, **kwargs):
            if isinstance(cmd, (list, tuple)) and len(cmd) > 1:
                words = [os.fsdecode(x) for x in cmd]
                if Path(words[0]).name == "git" and "clone" in words:
                    self.clone_calls.append(words)
            return real_run(cmd, *args, **kwargs)
        self.patch(subprocess, "run", tracking_run)

        self.drives = []
        self.report_head = None
        self.drive_steps = 10
        self.drive_cost = 1.0
        real_popen = subprocess.Popen

        def drive_popen(args, *a, **kwargs):
            if (isinstance(args, (list, tuple))
                    and canary.CANARY_DRIVE_MODULE in [os.fsdecode(x) for x in args]):
                self.fake_drive([os.fsdecode(x) for x in args])
                return real_popen([sys.executable, "-c", "pass"], *a, **kwargs)
            return real_popen(args, *a, **kwargs)
        self.patch(subprocess, "Popen", drive_popen)

    # --- подготовка -------------------------------------------------------

    def patch(self, target, name, value):
        patcher = mock.patch.object(target, name, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def msg(self, text: str = "") -> str:
        return f"зерно {self.seed}: {text}\n--- вывод прогона ---\n" + getattr(
            self, "output", "")

    def write_pult_layer(self, text: str) -> None:
        path = Path(config.MODELS_LOCAL)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def random_tiers(self) -> dict:
        """Ярусы пульта на трёх разных моделях каталога, ни одна не из
        шаблона."""
        chosen = self.rng.sample(CLAUDE_MODELS, len(models.TIERS))
        return dict(zip(models.TIERS, chosen))

    def pult_models(self, tiers: dict, role_models: dict = None) -> dict:
        """Модель каждой агентской роли по слою пульта: запись
        `role_models:`, иначе модель яруса роли."""
        role_models = role_models or {}
        return {role: role_models.get(role, tiers[self.tier_of[role]])
                for role in AGENT_ROLES}

    # --- подменённый процесс клона ---------------------------------------

    def fake_drive(self, argv: list) -> None:
        if "--result" in argv:
            result_path = Path(argv[argv.index("--result") + 1])
        else:
            result_path = Path(next(x for x in argv if x.endswith(".json")))
        layer_path = Path(config.MODELS_LOCAL)
        text = (layer_path.read_text(encoding="utf-8")
                if layer_path.is_file() else None)
        resolved = {}
        for role in AGENT_ROLES:
            try:
                res = models.resolve_role(role)
                resolved[role] = (res.model, res.provider)
            except models.ModelsError as exc:
                resolved[role] = ("отказ", str(exc))
        task_id = f"01PLANKA{self.rng.randrange(10**12):012d}"
        self.drives.append({"layer_text": text, "resolved": resolved,
                            "task_id": task_id})
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(json.dumps({
            "task_id": task_id,
            "head": self.report_head or self.sha,
            "escalated": False,
            "metrics": {
                "steps": self.drive_steps, "cost_usd": self.drive_cost,
                "review_iterations": 1, "escalations": [], "dev_retries": 0,
                "outcome": "killed", "kill_note": "штатно",
                "test_author_visited": True, "ceiling_exhausted": False,
                "ceiling_raise": None,
            },
            "steps": [],
        }, ensure_ascii=False), encoding="utf-8")

    # --- прогон и наблюдения ---------------------------------------------

    def run_canary(self, set_name: str = None) -> str:
        kwargs = {"k": 1, "sha": self.sha, "templates": [POOL_TITLE]}
        if set_name is not None:
            kwargs["set_name"] = set_name
        out, err = io.StringIO(), io.StringIO()
        self.exit = None
        with redirect_stdout(out), redirect_stderr(err):
            try:
                canary.cmd_canary(**kwargs)
            except SystemExit as exc:
                self.exit = exc
        self.stdout = out.getvalue()
        self.output = self.stdout + err.getvalue()
        if self.exit is not None and self.exit.code not in (None, 0):
            self.output += f"\n{self.exit.code}"
        return self.output

    def assert_ran(self, drives: int = 1) -> None:
        self.assertIsNone(self.exit, self.msg("прогон отказал"))
        self.assertEqual(len(self.drives), drives,
                         self.msg("процесс клона не запускался"))

    def first_line(self) -> str:
        lines = self.stdout.splitlines()
        self.assertTrue(lines, self.msg("прогон ничего не напечатал"))
        return lines[0]

    def summary_line(self, drive: int = -1) -> str:
        task_id = self.drives[drive]["task_id"]
        for line in self.output.splitlines():
            if line.startswith(f"  {task_id}:"):
                return line
        self.fail(self.msg(f"строки итога задачи {task_id} нет"))

    def clone_doc(self, drive: int = -1) -> dict:
        text = self.drives[drive]["layer_text"]
        self.assertIsNotNone(text, self.msg("слоя клона нет на диске"))
        return yamlmini.mapping(text)

    def clone_layer(self, drive: int = -1):
        """Слой клона, разобранный тем же `models.load_local`."""
        path = self.root / ".artel" / f"sloj-klona-{drive}.yaml"
        path.write_text(self.drives[drive]["layer_text"], encoding="utf-8")
        return models.load_local(path)

    def query(self, sql: str, *params) -> list:
        conn = sqlite3.connect(str(config.DB))
        conn.row_factory = sqlite3.Row
        try:
            return conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()

    def canary_rows(self) -> list:
        return self.query("SELECT * FROM canary_runs ORDER BY id")

    def assert_names_every_role_model(self, text: str, expected: dict,
                                      where: str) -> None:
        for role, model in expected.items():
            self.assertIn(f"{role} → {model}", text,
                          self.msg(f"{where} не называет «{role} → {model}»: "
                                   f"{text!r}"))

    def assert_refused_before_clone(self, *names: str) -> None:
        self.assertIsNotNone(self.exit, self.msg("отказа нет"))
        text = str(self.exit.code)
        for name in names:
            self.assertIn(name, text, self.msg(f"отказ не называет {name}"))
        self.assertEqual(self.clone_calls, [], self.msg("git clone вызван"))
        self.assertEqual(self.clone_dirs, [], self.msg("каталог клона заведён"))
        self.assertEqual(self.drives, [], self.msg("процесс клона запущен"))
        rows = self.query("SELECT task_id FROM tasks")
        self.assertEqual(rows, [], self.msg("строка в tasks заведена"))


class DefaultRunCloneLayerTest(CanaryCloneSandbox):
    """AC-1, AC-2: прогон без `--set`."""

    def test_ac1_default_run_clone_layer_is_the_pult_layer(self):
        """Прогон без `--set` на читаемом слое пульта со своими ярусами.

        Ярусы пульта — случайные модели каталога не из шаблона, модель
        яруса `strong` — `experimental` с разрешением и переопределением
        тарифа; у пульта есть `role_providers:`, `role_models:` (со своим
        тарифом) и `canary_sets:`. Слой клона, который видят шаги ролей
        клона: ярусы пульта, разрешение и тарифы перенесены, оба раздела
        ролей пульта перенесены, `canary_sets:` нет.

        Ловит мутацию: слой клона из шаблона — прогон без набора
        оставляет в клоне `models.LOCAL_TEMPLATE`, и ярусы клона
        указывают на модели шаблона, а не пульта; либо в клон уезжает
        слой пульта целиком вместе с `canary_sets:`; либо ярусы
        переносятся, а тарифы/разрешения/разделы ролей — нет.
        """
        tiers = self.random_tiers()
        tiers["strong"] = CLAUDE_EXPERIMENTAL
        rm_role = self.rng.choice(AGENT_ROLES)
        rm_model = self.rng.choice([m for m in CLAUDE_MODELS
                                    if m not in tiers.values()])
        rp_role = self.rng.choice(AGENT_ROLES)
        tariffs = {m: tuple(round(self.rng.uniform(0.1, 9.0), 2) for _ in range(4))
                   for m in (CLAUDE_EXPERIMENTAL, rm_model)}
        self.write_pult_layer(layer_text(
            tiers, allow=(CLAUDE_EXPERIMENTAL,), overrides=tariffs,
            role_providers={rp_role: "claude"}, role_models={rm_role: rm_model},
            canary_sets={"nabor-pulta": {rm_role: ("claude", rm_model)}}))

        self.run_canary()

        self.assert_ran()
        doc = self.clone_doc()
        self.assertEqual(doc.get("tiers"), tiers,
                         self.msg("ярусы слоя клона не равны ярусам пульта"))
        self.assertNotIn("canary_sets", doc, self.msg("canary_sets: в слое клона"))
        self.assertEqual((doc.get("role_providers") or {}).get(rp_role), "claude",
                         self.msg("role_providers: пульта не перенесён"))
        self.assertEqual((doc.get("role_models") or {}).get(rm_role), rm_model,
                         self.msg("role_models: пульта не перенесён"))
        clone = self.clone_layer()
        self.assertIn(CLAUDE_EXPERIMENTAL, clone.allow_experimental,
                      self.msg("разрешение experimental модели яруса не перенесено"))
        for model_id, prices in tariffs.items():
            self.assertIn(model_id, clone.overrides,
                          self.msg(f"тариф пульта модели {model_id} не перенесён"))
            self.assertEqual(tuple(clone.overrides[model_id].tariff), prices,
                             self.msg(f"тариф модели {model_id} не пультовый"))
        self.assertEqual(
            {r: m for r, (m, _p) in self.drives[0]["resolved"].items()},
            self.pult_models(tiers, {rm_role: rm_model}),
            self.msg("роли клона идут не на моделях слоя пульта"))

    def assert_template_clone_and_named_source(self) -> None:
        self.assert_ran()
        doc = self.clone_doc()
        self.assertEqual(doc.get("tiers"), TEMPLATE_TIERS,
                         self.msg("слой клона — не шаблон"))
        self.assertNotIn("role_models", doc, self.msg("role_models: в шаблоне"))
        line = self.first_line()
        self.assertIn("шаблон", line, self.msg(f"источник не назван: {line!r}"))
        self.assertIn("пульт", line, self.msg(f"слой пульта не назван: {line!r}"))
        self.assertTrue(
            any(word in line for word in ("не прочитан", "нет", "не разобран",
                                          "отсутств")),
            self.msg(f"первая строка не говорит, что слой пульта не прочитан: "
                     f"{line!r}"))

    def test_ac2_missing_pult_layer_gives_the_template_clone_layer(self):
        """Слоя пульта на диске нет.

        Прогон не отказывает, слой клона — ярусы шаблона, первая строка
        прогона называет источник «шаблон» и отсутствие слоя пульта.

        Ловит мутацию: отсутствующий слой пульта роняет прогон (`sys.exit`
        или исключение разбора до клона); либо слой клона собран, но
        первая строка молчит об источнике — Оператор принимает прогон на
        шаблоне за прогон на боевых моделях.
        """
        Path(config.MODELS_LOCAL).unlink(missing_ok=True)

        self.run_canary()

        self.assert_template_clone_and_named_source()

    def test_ac2_unparseable_pult_layer_gives_the_template_clone_layer(self):
        """Слой пульта есть, но не разбирается (случайно одно из двух
        повреждений: `tiers:` не отображение либо ярус вне перечня).

        Поведение то же, что без слоя: шаблон в клоне, источник «шаблон»
        и причина в первой строке.

        Ловит мутацию: нечитаемый слой пульта трактуется как отсутствие
        ярусов и даёт слой клона без `tiers:` (шаги ролей клона отказали
        бы), либо переносится в клон как есть; либо прогон отказывает
        ошибкой разбора слоя.
        """
        broken = self.rng.choice(("tiers: ne-otobrazhenie\n",
                                  "tiers:\n  sverhsilnyj: m-alfa-fikstury\n"))
        self.write_pult_layer(broken)

        self.run_canary()

        self.assert_template_clone_and_named_source()


class SetByRolesTest(CanaryCloneSandbox):
    """AC-6, AC-7: набор переводит только названные роли."""

    def test_ac6_set_moves_only_the_named_role(self):
        """Набор называет одну случайную роль на модели, отличной от её
        модели в слое пульта; у пульта есть запись `role_models:` другой
        роли.

        В слое клона названная роль идёт на модели и провайдере набора,
        каждая из трёх прочих — на той же модели, что по слою пульта;
        ярусы слоя клона — ярусы пульта.

        Ловит мутацию: набор применяется сдвигом яруса — соседи названной
        роли по ярусу получают модель набора; либо ярусы клона берутся из
        шаблона с подменой яруса набора, и роли, не названные набором,
        уходят на модель шаблона вместо пультовой; либо запись
        `role_models:` пульта теряется в клоне.
        """
        tiers = self.random_tiers()
        role = self.rng.choice(AGENT_ROLES)
        other = self.rng.choice([r for r in AGENT_ROLES if r != role])
        pult_role_models = {other: self.rng.choice(CLAUDE_MODELS)}
        expected = self.pult_models(tiers, pult_role_models)
        model = self.rng.choice([m for m in CLAUDE_MODELS if m != expected[role]])
        self.write_pult_layer(layer_text(
            tiers, role_models=pult_role_models,
            canary_sets={"odna-rol": {role: ("claude", model)}}))

        self.run_canary("odna-rol")

        self.assert_ran()
        resolved = self.drives[0]["resolved"]
        self.assertEqual(resolved[role], (model, "claude"),
                         self.msg(f"роль набора {role}"))
        for r in AGENT_ROLES:
            if r != role:
                self.assertEqual(resolved[r][0], expected[r],
                                 self.msg(f"роль {r} не названа набором "
                                          f"(набор: {role} -> {model})"))
        self.assertEqual(self.clone_doc().get("tiers"), tiers,
                         self.msg("ярусы слоя клона не равны ярусам пульта"))

    def test_ac7_two_roles_of_one_tier_with_different_models_are_accepted(self):
        """Набор называет две случайные роли одного яруса с разными
        моделями.

        Прогон не отказывает; в слое клона у каждой из двух ролей — своя
        модель набора.

        Ловит мутацию: остался отказ «набор даёт ярусу две разные модели»
        — прогон отказывает до клона; либо обе роли получают одну модель
        (последнюю записанную в ярус).
        """
        tiers = self.random_tiers()
        first, second = self.rng.sample(self.strong_roles, 2)
        m1, m2 = self.rng.sample(CLAUDE_MODELS, 2)
        self.write_pult_layer(layer_text(
            tiers, canary_sets={"dve-roli": {first: ("claude", m1),
                                             second: ("claude", m2)}}))

        self.run_canary("dve-roli")

        self.assert_ran()
        resolved = self.drives[0]["resolved"]
        self.assertEqual(resolved[first][0], m1, self.msg(f"роль {first}"))
        self.assertEqual(resolved[second][0], m2, self.msg(f"роль {second}"))


class SetRefusalsBeforeCloneTest(CanaryCloneSandbox):
    """AC-8: битый набор — отказ до эфемерного клона."""

    def run_broken_set(self, entries: dict) -> None:
        self.write_pult_layer(layer_text(self.random_tiers(),
                                         canary_sets={"bityj": entries}))
        self.run_canary("bityj")

    def test_ac8_role_outside_the_roles_map_is_refused_before_clone(self):
        """Набор называет роль, которой нет в карте исполнителей.

        Именованный отказ с именем роли; ни `git clone`, ни каталога
        клона, ни строки в `tasks`.

        Ловит мутацию: проверка ролей набора перенесена на момент сборки
        слоя клона внутри клона (или снята: роль вне карты просто ложится
        записью в `role_models:`) — прогон заводит клон и задачу.
        """
        role = f"rol-vne-karty-{self.rng.randrange(10**6):06d}"
        self.run_broken_set({role: ("claude", self.rng.choice(CLAUDE_MODELS))})

        self.assert_refused_before_clone(role)

    def test_ac8_model_outside_the_catalog_is_refused_before_clone(self):
        """Набор ведёт существующую роль на модель вне каталога.

        Именованный отказ с именем модели до клона.

        Ловит мутацию: модель набора не сверяется с каталогом (её отказ
        случился бы только на шаге роли в клоне) — прогон заводит клон и
        задачу.
        """
        model = f"m-net-v-kataloge-{self.rng.randrange(10**6):06d}"
        self.run_broken_set({self.rng.choice(AGENT_ROLES): ("claude", model)})

        self.assert_refused_before_clone(model)

    def test_ac8_provider_mismatch_is_refused_before_clone(self):
        """Запись набора называет провайдера, не совпадающего с
        провайдером её модели в каталоге.

        Именованный отказ с именем роли до клона.

        Ловит мутацию: провайдер записи набора кладётся в слой клона без
        сверки с каталогом — прогон заводит клон с ролью на чужом CLI.
        """
        role = self.rng.choice(AGENT_ROLES)
        if self.rng.random() < 0.5:
            entry = ("codex", self.rng.choice(CLAUDE_MODELS))
        else:
            entry = ("claude", CODEX_MODEL)
        self.run_broken_set({role: entry})

        self.assert_refused_before_clone(role)


class CodexRoleOfTheSetTest(CanaryCloneSandbox):
    """AC-9: Codex касается только роли набора."""

    def setUp(self):
        super().setUp()
        self.codex_role = self.rng.choice(self.strong_roles)
        self.neighbours = [r for r in self.strong_roles if r != self.codex_role]
        self.write_pult_layer(layer_text(
            self.random_tiers(),
            canary_sets={"kodeks-odna": {self.codex_role: ("codex", CODEX_MODEL)}}))

    def put_pointer(self) -> None:
        pointer = Path(config.ROLE_HOME) / KEYCHAIN_POINTER
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.write_bytes(b"ukazatel-svyazki-fikstury")

    def test_ac9_missing_pointer_refusal_names_only_the_codex_role(self):
        """Указателя связки ключей в доме роли пульта нет.

        Именованный отказ до клона называет роль набора на Codex и не
        называет ни одного её соседа по ярусу.

        Ловит мутацию: роли Codex прогона считаются по ярусу набора
        целиком — отказ перечисляет соседей по ярусу, идущих на `claude`.
        """
        self.run_canary("kodeks-odna")

        self.assert_refused_before_clone(self.codex_role)
        text = str(self.exit.code)
        for neighbour in self.neighbours:
            self.assertNotIn(neighbour, text,
                             self.msg(f"отказ Codex называет соседа {neighbour}"))

    def test_ac9_login_check_and_clone_layer_touch_only_the_codex_role(self):
        """Указатель есть, проверка входа Codex подменена подтверждённой.

        Проверку входа прогон зовёт только для роли набора; в слое клона
        провайдером Codex идёт только она, соседи по ярусу — `claude` на
        модели своего яруса.

        Ловит мутацию: перечень ролей Codex плана считается по ярусу —
        проверка входа зовётся для соседа по ярусу, а соседи в слое клона
        получают провайдера `codex` и модель набора.
        """
        self.put_pointer()
        checked = []

        def login(role):
            checked.append(role)
            return doctor.Check("codex-auth", "ok", "вход песочницы подтверждён")
        self.patch(doctor, "check_codex_chatgpt_auth", login)

        self.run_canary("kodeks-odna")

        self.assert_ran()
        self.assertTrue(checked, self.msg("проверка входа Codex не звалась"))
        self.assertEqual(set(checked), {self.codex_role},
                         self.msg(f"проверка входа звалась для {checked}"))
        resolved = self.drives[0]["resolved"]
        self.assertEqual(resolved[self.codex_role], (CODEX_MODEL, "codex"),
                         self.msg("роль набора"))
        for neighbour in self.neighbours:
            self.assertEqual(resolved[neighbour][1], "claude",
                             self.msg(f"сосед {neighbour} ушёл не на claude"))

    def test_ac9_unconfirmed_login_is_a_named_refusal(self):
        """Указатель есть, проверка входа Codex отвечает провалом.

        Прогон отказывает именованно (имя проверки в отказе), учебная
        задача не заводится, процесс клона не запускается.

        Ловит мутацию: недоказанный вход не останавливает прогон —
        процесс клона запускается и шаг роли Codex упал бы авторизацией
        за деньги.
        """
        self.put_pointer()
        self.patch(doctor, "check_codex_chatgpt_auth",
                   lambda role: doctor.Check("codex-vhod-fikstury", "fail",
                                             "вход не подтверждён"))

        self.run_canary("kodeks-odna")

        self.assertIsNotNone(self.exit, self.msg("отказа нет"))
        self.assertIn("codex-vhod-fikstury", str(self.exit.code),
                      self.msg("отказ не называет проверку входа"))
        self.assertEqual(self.drives, [], self.msg("процесс клона запущен"))
        self.assertEqual(self.query("SELECT task_id FROM tasks"), [],
                         self.msg("строка в tasks заведена"))


class RunSummaryModelsTest(CanaryCloneSandbox):
    """AC-10, AC-11: сводка моделей всех ролей и подпись кода клона."""

    def assert_summary_everywhere(self, expected: dict, source: str) -> None:
        self.assert_ran()
        first = self.first_line()
        summary = self.summary_line()
        rows = self.canary_rows()
        self.assertEqual(len(rows), 1, self.msg("строк canary_runs не одна"))
        stored = rows[0]["models_summary"] or ""
        for where, text in (("первая строка", first), ("строка итога", summary),
                            ("models_summary", stored)):
            self.assert_names_every_role_model(text, expected, where)
            self.assertIn(source, text,
                          self.msg(f"{where} не называет источник «{source}»: "
                                   f"{text!r}"))

    def test_ac10_default_run_names_every_role_model_and_the_pult_source(self):
        """Прогон без набора на слое пульта с записью `role_models:`.

        Первая строка, строка итога задачи и `models_summary` называют
        «роль → модель» каждой агентской роли по слою пульта и источник
        «слой пульта».

        Ловит мутацию: сводка моделей собирается только для набора, и у
        прогона без набора она пуста (как до задачи — `models_summary`
        `NULL`); либо сводка называет модели ярусов, упуская запись
        `role_models:`.
        """
        tiers = self.random_tiers()
        rm_role = self.rng.choice(AGENT_ROLES)
        role_models = {rm_role: self.rng.choice(CLAUDE_MODELS)}
        self.write_pult_layer(layer_text(tiers, role_models=role_models))

        self.run_canary()

        self.assert_summary_everywhere(self.pult_models(tiers, role_models),
                                       "слой пульта")

    def test_ac10_set_run_names_every_role_model_and_the_set_source(self):
        """Прогон с набором, называющим одну роль.

        Все три места называют модель набора у его роли, пультовые модели
        у остальных и источник «набор <имя>».

        Ловит мутацию: сводка называет только роли набора (как до задачи)
        — роли, идущие по слою пульта, в ней не названы; либо источник
        набора не назван.
        """
        tiers = self.random_tiers()
        role = self.rng.choice(AGENT_ROLES)
        expected = self.pult_models(tiers)
        model = self.rng.choice([m for m in CLAUDE_MODELS if m != expected[role]])
        expected[role] = model
        self.write_pult_layer(layer_text(
            tiers, canary_sets={"svodka": {role: ("claude", model)}}))

        self.run_canary("svodka")

        self.assert_summary_everywhere(expected, "набор svodka")

    def test_ac11_summary_carries_the_clone_code_label_even_on_the_pin(self):
        """Проверяемый sha совпадает с HEAD главной копии (пином), клон
        сообщает тот же коммит.

        Строка итога задачи несёт «код клона <sha>», подписи «код пина» в
        выводе прогона нет нигде.

        Ловит мутацию: подпись по-прежнему считается сравнением с HEAD
        главной копии (`код пина` при совпадении) — в выводе «код пина»,
        «код клона» нет.
        """
        self.write_pult_layer(layer_text(self.random_tiers()))

        self.run_canary()

        self.assert_ran()
        self.assertIn(f"код клона {self.sha}", self.summary_line(),
                      self.msg("нет подписи кода клона"))
        self.assertNotIn("код пина", self.output, self.msg("подпись «код пина»"))

    def test_ac11_label_names_the_commit_reported_by_the_clone(self):
        """Клон сообщает коммит, отличный от проверяемого (первый коммит
        песочницы).

        Строка итога называет «код клона» именно сообщённый коммит.

        Ловит мутацию: в подпись идёт проверяемый sha (`target_sha`), а не
        `head` результата процесса клона.
        """
        self.write_pult_layer(layer_text(self.random_tiers()))
        self.report_head = self.first_sha

        self.run_canary()

        self.assert_ran()
        self.assertIn(f"код клона {self.first_sha}", self.summary_line(),
                      self.msg("подпись не называет коммит клона"))
        self.assertNotIn("код пина", self.output, self.msg("подпись «код пина»"))


class BaselineModelsChangeTest(CanaryCloneSandbox):
    """AC-12, AC-13: базовая линия пары и смена моделей ролей."""

    def far_baseline(self) -> tuple:
        steps = self.drive_steps * self.rng.randint(5, 9)
        cost = round(self.drive_cost * self.rng.uniform(5.0, 9.0), 2)
        store.set_canary_baseline(store.db(), POOL_TITLE, steps, cost, 1,
                                  config.CANARY_DEFAULT_SET)
        return steps, cost

    def baseline(self) -> tuple:
        row = store.canary_baseline(store.db(), POOL_TITLE,
                                    config.CANARY_DEFAULT_SET)
        return row["steps"], round(row["cost_usd"], 2)

    def threshold_alerts(self) -> list:
        return store.open_alerts(store.db(), "threshold")

    def assert_incomparable(self) -> None:
        self.assert_ran(drives=len(self.drives))
        self.assertEqual(self.threshold_alerts(), [],
                         self.msg("алерт threshold при несравнимой линии"))
        self.assertEqual(self.baseline(), (self.drive_steps, self.drive_cost),
                         self.msg("базовая линия не перезаписана числами прогона"))
        line = self.summary_line()
        self.assertIn("модел", line, self.msg(f"причина не названа: {line!r}"))
        self.assertTrue(any(w in line for w in ("несравним", "не сравним",
                                                "несопоставим")),
                        self.msg(f"нет предупреждения о несравнимой линии: {line!r}"))
        self.assertEqual(self.canary_rows()[-1]["verdict"], "green",
                         self.msg("вердикт прогона не green"))

    def test_ac12_changed_role_models_make_the_baseline_incomparable(self):
        """Первый штатный прогон пары заводит строку и линию; линия затем
        отодвинута далеко от чисел прогона, а слой пульта переведён на
        другую модель яруса `strong`; второй штатный прогон.

        Алерта `threshold` нет, линия перезаписана числами второго
        прогона, примечание называет несравнимость из-за смены моделей,
        вердикт `green`.

        Ловит мутацию: сравнение с линией не смотрит на модели ролей —
        отклонение от чужой линии поднимает алерт (вход гейта сдвига пина)
        и линию не трогает; либо сверка идёт со строкой только что
        записанного прогона и всегда находит «те же модели».
        """
        tiers = self.random_tiers()
        self.write_pult_layer(layer_text(tiers))
        self.run_canary()
        self.assert_ran()
        self.far_baseline()
        tiers["strong"] = self.rng.choice(
            [m for m in CLAUDE_MODELS if m != tiers["strong"]])
        self.write_pult_layer(layer_text(tiers))
        self.drive_steps, self.drive_cost = 11, 1.25

        self.run_canary()

        self.assert_incomparable()

    def test_ac12_row_without_models_summary_makes_the_baseline_incomparable(self):
        """Последняя штатная строка пары записана до задачи — без сводки
        моделей (`models_summary` `NULL`), линия пары далеко от чисел.

        Штатный прогон: алерта нет, линия перезаписана, предупреждение о
        несравнимости, вердикт `green`.

        Ловит мутацию: строка без сводки моделей считается сравнимой
        («сравнивать нечего — значит, совпадает») — алерт поднимается и
        линия остаётся прежней.
        """
        self.write_pult_layer(layer_text(self.random_tiers()))
        store.insert_canary_run(
            store.db(), "20260101T000000Z", POOL_TITLE, "01PLANKASTARAYA",
            self.drive_steps, self.drive_cost, 1, 0, "killed", None, False,
            False, main_sha=self.sha, verdict="green",
            set_name=config.CANARY_DEFAULT_SET, models_summary=None)
        self.far_baseline()

        self.run_canary()

        self.assert_incomparable()

    def test_ac13_same_role_models_keep_the_old_comparison(self):
        """Два штатных прогона пары на одном и том же слое пульта; между
        ними линия отодвинута далеко от чисел прогона.

        Второй прогон поднимает алерт `threshold`, строка итога несёт
        прежнее примечание об отклонении, линия не перезаписана.

        Ловит мутацию: базовая линия объявляется несравнимой всегда
        (сводка сравнивается с меткой времени или с именем задачи, либо
        строка текущего прогона не отличается от прошлой) — алерта нет и
        линия перезаписана.
        """
        self.write_pult_layer(layer_text(self.random_tiers()))
        self.run_canary()
        self.assert_ran()
        far = self.far_baseline()

        self.run_canary()

        self.assert_ran(drives=2)
        self.assertTrue(self.threshold_alerts(),
                        self.msg("алерта threshold нет при сравнимой линии"))
        self.assertIn("отклонение от бейзлайна", self.summary_line(),
                      self.msg("прежнего примечания нет"))
        self.assertEqual(self.baseline(), far,
                         self.msg("сравнимая линия перезаписана"))
