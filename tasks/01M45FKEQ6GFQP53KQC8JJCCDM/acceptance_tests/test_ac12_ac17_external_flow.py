"""Сквозной поток внешнего проекта в песочнице: гейты `in_dev` и гейт мержа.

Группа: разовый
Обоснование группы: сценарий ведёт настоящий git клона проекта, его голого
`origin` и рабочей копии задачи и подменяет `gitcmd.subprocess.run`
настоящим запуском — долгоживущей группе это запрещено; долгоживущий
сквозной тест в `tests/` по требованию 5 SPEC пишет разработчик.

Красен до реализации: гейт зон, неослабление тестов и заявка мутации на `in_dev` и сверка защищённых путей на гейте мержа сегодня не исполняются для проекта, отличного от `config.DEFAULT_TARGET` (развилки `zones.py`, `review.py`, `test_integrity.py`, `fsm_merge_gate.py`), поле `no_paths` код не читает, записи журнала о невключённых языковых проверках нет; AC-12..AC-16 и журнальная часть AC-17 красны.

Песочница — `tests.sandbox.TmpRootTest` (пути `config` во временном
каталоге), поверх неё настоящий git (`network_guarded_real_run`).
Внешний проект заводит `tests.sandbox.make_project_repo`: клон
`config.PROJECTS/<проект>/repo` и голый `origin.git` рядом — локальный
«фордж». Запись проекта в `config.TARGETS` пишет сценарий до
`make_project_repo` (та её не перезаписывает): зоны задачи — `src/` и
`tests/`, `no_paths` — `infra/` (путь, которого нет в
`config.PROTECTED_PATHS`: отказ по нему доказывает чтение `no_paths`, а не
перечня пульта). База проекта несёт `src/app.py`, `infra/deploy.cfg`,
`lib/base.py` и существующий тест `tests/test_existing.py` с заявками.
Задача заводится `catalog.cmd_new(..., target=<проект>)`, рабочая копия —
`workspace.ensure`, PLAN `ready` — коммитом в ссылку документов
(`artifact_branch.commit_files`). Правка задачи — коммит в рабочей копии и
отправка ветки в `origin`; переход — `fsm.cmd_advance` из `in_dev`, мерж —
`fsm.cmd_approve` из `merge_gate` с подменённым ответом GitHub (`ci.gh`:
все проверки зелёные — иначе гейт мержа ждал бы CI до потолка).

Профиль тестов. Формат поля задаёт часть 1 этапа
(01M45FJVGQT1K0P8HDEXZX6HS7, SPEC требование 1: поле `test_profile`). Чтобы
не повторять его литералом, профиль внешнего проекта берётся из записи
`artel` настоящего `targets.yaml` репозитория: поля этой записи вне
`orchestrator.targets.FIELDS` копируются в запись внешнего проекта «с
профилем» (часть 1 добавляет профиль артели приложением к `targets.yaml`,
её значения — pytest и `tests/test_<id>_<имя>.py`). Пока таких полей в
записи артели нет, берётся запасной литерал — значения артели из таблицы
требования 1 SPEC части 1. Запись «без профиля» — та же запись без этих
полей.

Опознание гейтов — по устойчивым словам действия журнала, которые гейты
пишут для артели сегодня: «гейт зон», «защищённый путь», «неослабления
тестов», «заявки мутации»; сам путь или файл ищется в тексте отказа.
"""
import contextlib
import io
import json
import random
import subprocess
from pathlib import Path
from unittest import mock

import orchestrator
from orchestrator import (artifact_branch, catalog, ci, config, fixation, fsm,
                          gitcmd, store, targets, workspace, yamlmini)
from tests.sandbox import (TmpRootTest, make_project_repo,
                           network_guarded_real_run)

REPO_TARGETS = Path(orchestrator.__file__).resolve().parent.parent / "targets.yaml"

# Значения профиля артели из таблицы требования 1 SPEC части 1 — запасной
# путь, пока запись артели настоящего `targets.yaml` профиля не несёт.
FALLBACK_PROFILE = {
    "test_profile": {
        "command": ["python3", "-m", "pytest"],
        "long_lived_dir": "tests",
        "long_lived_name": "test_<id>_<name>.py",
        "weakening_scope": ["tests/**/*.py"],
        "mutation_claim_scope": ["tests/test_*.py"],
        "report": "junit-xml",
        "install": [],
    },
}

REFUSED_PREFIX = "переход отклонён"
ZONES_WORD = "гейт зон"
PROTECTED_WORD = "защищённый путь"
WEAKENING_WORD = "неослабления тестов"
MUTATION_WORD = "заявки мутации"

PLAN_READY = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: сквозной поток внешнего проекта

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""

EXISTING_TEST = '''"""Существующий тест проекта."""
import unittest


class ExistingTest(unittest.TestCase):

    def test_one(self):
        """Первый.

        Ловит мутацию: фикстура — сумма перестаёт совпадать.
        """
        self.assertEqual(1 + 1, 2)

    def test_two(self):
        """Второй.

        Ловит мутацию: фикстура — разность перестаёт совпадать.
        """
        self.assertEqual(3 - 1, 2)
'''

NEW_TEST_WITHOUT_CLAIM = '''"""Новый тест задачи."""
import unittest


class FreshTest(unittest.TestCase):

    def test_fresh_{n}(self):
        """Новый метод без заявки."""
        self.assertEqual({n}, {n})
'''


def _repo_profile_fields() -> dict:
    """Поля записи `artel` настоящего `targets.yaml` вне `targets.FIELDS`;
    пусто — запасной литерал `FALLBACK_PROFILE`."""
    try:
        data = yamlmini.mapping(REPO_TARGETS.read_text(encoding="utf-8"))
        entry = data["targets"][config.DEFAULT_TARGET]
    except (OSError, KeyError, TypeError, yamlmini.YamlError):
        entry = {}
    extra = {k: v for k, v in entry.items() if k not in targets.FIELDS}
    return extra or dict(FALLBACK_PROFILE)


PROFILE_FIELDS = _repo_profile_fields()


def _yaml_field(key: str, value, indent: int) -> str:
    pad = " " * indent
    if isinstance(value, dict):
        return f"{pad}{key}:\n" + "".join(
            _yaml_field(k, v, indent + 2) for k, v in value.items())
    if isinstance(value, list):
        return f"{pad}{key}: [{', '.join(str(v) for v in value)}]\n"
    return f"{pad}{key}: {value}\n"


def _fake_gh(*args, timeout=None, repo=None):
    """GitHub песочницы: все проверки зелёные, прочие вызовы `gh` — отказ."""
    if args and args[0] == "api":
        runs = [{"name": "tests", "status": "completed",
                 "conclusion": "success"}]
        return subprocess.CompletedProcess(
            list(args), 0, json.dumps({"total_count": 1, "check_runs": runs}),
            "")
    if args[:2] == ("run", "list"):
        return subprocess.CompletedProcess(list(args), 0, "[]", "")
    return subprocess.CompletedProcess(list(args), 1, "",
                                       "gh в песочнице не заведён")


class _ExternalFlowSandbox(TmpRootTest):
    """Внешний проект с голым `origin`, задача в `in_dev` с зонами
    `src/, tests/`; `WITH_PROFILE` — несёт ли запись проекта профиль."""

    WITH_PROFILE = True
    TARGET = "vneshniy"
    ZONES = "src/, tests/"
    NO_PATH = "infra/"
    NO_PATH_FILE = "infra/deploy.cfg"
    OUTSIDE_FILE = "lib/base.py"
    EXISTING_TEST_FILE = "tests/test_existing.py"

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        real_git = mock.patch.object(gitcmd.subprocess, "run",
                                     network_guarded_real_run)
        real_git.start()
        self.addCleanup(real_git.stop)

        self.run_cmd(catalog.cmd_init)
        config.TARGETS.write_text(self.targets_text(), encoding="utf-8")
        self.clone = make_project_repo(self.TARGET)
        self.origin = config.PROJECTS / self.TARGET / "origin.git"
        self.seed_base()

        out, _ = self.run_cmd(catalog.cmd_new, "Сквозной поток проекта",
                              target=self.TARGET)
        rows = store.db().execute(
            "SELECT id FROM tasks WHERE target=?", (self.TARGET,)).fetchall()
        self.assertEqual(len(rows), 1, self.note(f"задача не заведена:\n{out}"))
        self.task_id = rows[0]["id"]
        store.update_task(store.db(), self.task_id, zones=self.ZONES)
        self.branch = self.row()["branch"]
        self.wt, error = workspace.ensure(self.task_id, self.branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        sha = artifact_branch.commit_files(
            self.task_id,
            {f"tasks/{self.task_id}/PLAN.md": PLAN_READY.format(task=self.task_id)},
            "PLAN ready")
        self.assertTrue(sha, self.note("PLAN не записан в ссылку документов"))
        store.update_task(store.db(), self.task_id, state="in_dev")

    # --- запись проекта и база -----------------------------------------

    def targets_text(self) -> str:
        text = ("targets:\n"
                f"  {self.TARGET}:\n"
                "    forge: github\n"
                f"    url: file://{config.PROJECTS / self.TARGET / 'origin.git'}\n"
                f"    base: {config.MAIN_BRANCH}\n"
                f"    token_slot: {self.TARGET}-token\n"
                f"    no_paths: [{self.NO_PATH}]\n"
                "    project_skills: []\n"
                "    merge_gate: operator\n")
        if self.WITH_PROFILE:
            text += "".join(_yaml_field(k, v, 4)
                            for k, v in PROFILE_FIELDS.items())
        return text

    def git(self, repo: Path, *args: str) -> str:
        res = subprocess.run(["git", "-C", str(repo), *args],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, self.note(
            f"git {' '.join(args)}: {res.stderr}"))
        return res.stdout

    def seed_base(self) -> None:
        files = {"src/app.py": "VALUE = 1\n",
                 self.NO_PATH_FILE: "replicas = 1\n",
                 self.OUTSIDE_FILE: "BASE = 1\n",
                 self.EXISTING_TEST_FILE: EXISTING_TEST}
        for rel, text in files.items():
            path = self.clone / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git(self.clone, "add", "-A")
        self.git(self.clone, "commit", "-q", "-m", "база проекта")
        self.git(self.clone, "push", "-q", "origin", config.MAIN_BRANCH)

    # --- обвязка -------------------------------------------------------

    def note(self, text: str) -> str:
        return f"{text} (зерно {getattr(self, 'seed', '—')})"

    def run_cmd(self, fn, *args, **kwargs) -> tuple:
        """(вывод вместе с текстом отказа, был ли ненулевой `SystemExit`)."""
        buf = io.StringIO()
        refused = False
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fn(*args, **kwargs)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    refused = True
                    buf.write(f"\n{exc.code}")
        return buf.getvalue(), refused

    def row(self):
        return store.get_task(store.db(), self.task_id)

    def steps(self) -> list:
        return [(s["action"] or "", s["detail"] or "")
                for s in store.task_steps(store.db(), self.task_id)]

    def refusals(self) -> list:
        return [(a, d) for a, d in self.steps() if a.startswith(REFUSED_PREFIX)]

    def commit_task_change(self, write: dict = None, remove=()) -> None:
        """Правка задачи коммитом в рабочей копии и отправка ветки в
        `origin` — как её оставляет шаг разработчика."""
        for rel, text in (write or {}).items():
            path = self.wt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        for rel in remove:
            self.git(self.wt, "rm", "-q", "--", rel)
        self.git(self.wt, "add", "-A")
        self.git(self.wt, "commit", "-q", "-m",
                 f"правка задачи {self.rng.randrange(1 << 30)}")
        self.git(self.wt, "push", "-q", "origin",
                 f"HEAD:refs/heads/{self.branch}")

    def advance(self) -> str:
        with mock.patch.object(ci, "gh", _fake_gh):
            out, _ = self.run_cmd(fsm.cmd_advance, self.task_id)
        return out

    def in_zone_edit(self) -> dict:
        return {"src/app.py": f"VALUE = {self.rng.randrange(2, 1 << 20)}\n"}

    def refusal_with(self, word: str, needle: str, out: str):
        """Первая запись отказа, чьё действие несёт `word`, а действие или
        detail — `needle`; провал называет все отказы и вывод."""
        for action, detail in self.refusals():
            if word in action and needle in f"{action} {detail}":
                return action, detail
        self.fail(self.note(
            f"нет отказа «{word}», называющего {needle}; отказы: "
            f"{self.refusals()}\nвывод:\n{out}"))

    def origin_base_head(self) -> str:
        return self.git(self.origin, "rev-parse",
                        f"refs/heads/{config.MAIN_BRANCH}").strip()


class WithProfileFlowTest(_ExternalFlowSandbox):

    def test_ac12_out_of_zone_file_is_refused_by_zones_gate(self):
        """Правка файла вне зон задачи внешнего проекта — отказ гейта зон с именем файла.

        Сценарий: проект с профилем тестов; задача с зонами `src/, tests/`
        коммитит правку `src/app.py` (в зоне) и `lib/base.py` (вне зон),
        ветка отправлена в голый `origin`. `advance` из `in_dev` — в
        журнале задачи запись отказа, действие которой несёт «гейт зон», а
        текст называет `lib/base.py`; задача осталась в `in_dev`.

        Ловит мутацию: развилка `config.DEFAULT_TARGET` в гейте зон
        оставлена — внешний проект гейт пропускает, отказа нет; перечень
        файлов диффа берётся не из клона проекта (рабочая копия пульта) —
        `lib/base.py` в отказе не назван.
        """
        write = self.in_zone_edit()
        write[self.OUTSIDE_FILE] = f"BASE = {self.rng.randrange(2, 1 << 20)}\n"
        self.commit_task_change(write)

        out = self.advance()

        self.refusal_with(ZONES_WORD, self.OUTSIDE_FILE, out)
        self.assertEqual(self.row()["state"], "in_dev", self.note(out))

    def test_ac13_no_paths_edit_is_refused_naming_the_path(self):
        """Правка пути из `no_paths` записи проекта — отказ «защищённый путь» с этим путём.

        Сценарий: проект с профилем, `no_paths: [infra/]` (пути нет в
        `config.PROTECTED_PATHS`); задача коммитит `infra/deploy.cfg`
        вместе с правкой в зоне. `advance` из `in_dev` — запись отказа с
        «защищённый путь» в действии, текст называет `infra/deploy.cfg`;
        задача в `in_dev`.

        Ловит мутацию: сверка защищённых путей берёт перечень пульта
        `config.PROTECTED_PATHS` вместо `no_paths` проекта — `infra/` не
        защищён, отказа «защищённый путь» нет (будет разве что «вне зон»);
        гейт зон пропускает внешний проект — отказа нет вовсе.
        """
        write = self.in_zone_edit()
        write[self.NO_PATH_FILE] = f"replicas = {self.rng.randrange(2, 99)}\n"
        self.commit_task_change(write)

        out = self.advance()

        self.refusal_with(PROTECTED_WORD, self.NO_PATH_FILE, out)
        self.assertEqual(self.row()["state"], "in_dev", self.note(out))

    def test_ac14_deleting_existing_test_is_refused_by_weakening_gate(self):
        """Удаление существующего теста без мандата — отказ гейта неослабления тестов.

        Сценарий: проект с профилем; задача удаляет `tests/test_existing.py`
        (в зонах, в области неослабления профиля) и правит `src/app.py`,
        мандата Оператора нет. `advance` из `in_dev` — запись отказа с
        «неослабления тестов» в действии, текст называет удалённый файл;
        задача в `in_dev`.

        Ловит мутацию: развилка `config.DEFAULT_TARGET` в гейте
        неослабления оставлена (или проект с профилем трактуется как
        проект без профиля) — удаление проходит без отказа; дифф читается
        не в клоне проекта — удаления не видно.
        """
        self.commit_task_change(self.in_zone_edit(),
                                remove=(self.EXISTING_TEST_FILE,))

        out = self.advance()

        self.refusal_with(WEAKENING_WORD, self.EXISTING_TEST_FILE, out)
        self.assertEqual(self.row()["state"], "in_dev", self.note(out))

    def test_ac15_new_test_without_claim_is_refused_by_mutation_gate(self):
        """Новый тест без «Ловит мутацию» — отказ гейта заявки мутации с именем файла.

        Сценарий: проект с профилем; задача добавляет
        `tests/test_fresh_<n>.py` с методом без заявки и правит
        `src/app.py`. `advance` из `in_dev` — запись отказа с «заявки
        мутации» в действии, текст называет новый файл; задача в `in_dev`.

        Ловит мутацию: развилка `config.DEFAULT_TARGET` в гейте заявки
        мутации оставлена — новый тест без заявки проходит; область заявки
        не берётся из профиля проекта и не покрывает `tests/test_*.py` —
        отказа нет.
        """
        n = self.rng.randrange(1, 1 << 20)
        fresh = f"tests/test_fresh_{n}.py"
        write = self.in_zone_edit()
        write[fresh] = NEW_TEST_WITHOUT_CLAIM.format(n=n)
        self.commit_task_change(write)

        out = self.advance()

        self.refusal_with(MUTATION_WORD, fresh, out)
        self.assertEqual(self.row()["state"], "in_dev", self.note(out))

    def test_ac16_merge_gate_escalates_no_paths_edit_without_merge(self):
        """Гейт мержа: правка пути из `no_paths` не мержится, задача эскалирована с этим путём.

        Сценарий: проект с профилем; ветка задачи несёт правку
        `infra/deploy.cfg` и отправлена в `origin`; задача поставлена на
        `merge_gate`, GitHub отвечает «все проверки зелёные». `approve` —
        голова базовой ветки голого `origin` прежняя, задача в
        `escalated`, запись журнала эскалации называет «защищённый путь» и
        `infra/deploy.cfg`.

        Ловит мутацию: сверка защищённых путей на гейте мержа включена
        только для артели (`repo_context.is_artel`) или берёт
        `config.PROTECTED_PATHS` вместо `no_paths` — задача мержится, база
        `origin` сдвигается, эскалации нет.
        """
        write = self.in_zone_edit()
        write[self.NO_PATH_FILE] = f"replicas = {self.rng.randrange(2, 99)}\n"
        self.commit_task_change(write)
        store.set_state(store.db(), self.task_id, "merge_gate", "operator",
                        expected_state="in_dev", detail="песочница")
        live_sha, _clean = fixation.read(self.task_id, self.TARGET)
        self.assertTrue(live_sha, self.note("предпосылка: фиксация не прочитана"))
        base_before = self.origin_base_head()

        with mock.patch.object(ci, "gh", _fake_gh):
            out, _ = self.run_cmd(fsm.cmd_approve, self.task_id, live_sha)

        self.assertEqual(self.origin_base_head(), base_before, self.note(
            f"задача с правкой {self.NO_PATH_FILE} смержена в "
            f"{config.MAIN_BRANCH} origin:\n{out}"))
        self.assertEqual(self.row()["state"], "escalated", self.note(
            f"задача не эскалирована:\n{out}"))
        escalations = [d for a, d in self.steps() if a == "state -> escalated"]
        self.assertTrue(
            any(PROTECTED_WORD in d and self.NO_PATH_FILE in d
                for d in escalations),
            self.note(f"эскалация не называет защищённый путь "
                      f"{self.NO_PATH_FILE}: {escalations}\n{out}"))


class WithoutProfileFlowTest(_ExternalFlowSandbox):

    WITH_PROFILE = False

    def test_ac17_language_checks_off_with_journal_record(self):
        """Проект без профиля: языковые проверки не отказывают, журнал называет их невключёнными.

        Сценарий: та же запись проекта без профиля тестов; задача удаляет
        `tests/test_existing.py`, добавляет тест без заявки и правит
        `src/app.py` (всё в зонах). `advance` из `in_dev` — нет отказа
        гейта неослабления и гейта заявки мутации; в журнале задачи есть
        запись, называющая поле профиля (`test_profile`), и среди таких
        записей названы обе проверки (неослабление и заявка мутации).
        Отсутствие отказов зелено и сегодня (у внешнего проекта гейты
        пропущены развилкой); красна журнальная часть.

        Ловит мутацию: проверки у проекта без профиля отключаются молча —
        записи журнала нет; проект без профиля получает проверки со
        значениями артели — отказ неослабления или заявки мутации.
        """
        n = self.rng.randrange(1, 1 << 20)
        write = self.in_zone_edit()
        write[f"tests/test_fresh_{n}.py"] = NEW_TEST_WITHOUT_CLAIM.format(n=n)
        self.commit_task_change(write, remove=(self.EXISTING_TEST_FILE,))

        out = self.advance()

        language = [(a, d) for a, d in self.refusals()
                    if WEAKENING_WORD in a or MUTATION_WORD in a]
        self.assertEqual(language, [], self.note(
            f"языковая проверка отказала проекту без профиля:\n{out}"))
        skipped = " ".join(f"{a} {d}" for a, d in self.steps()
                           if any(name in f"{a} {d}" for name in PROFILE_FIELDS))
        self.assertTrue(skipped, self.note(
            f"нет записи журнала о невключённых проверках (поле профиля "
            f"{', '.join(PROFILE_FIELDS)}): {self.steps()}\n{out}"))
        self.assertIn("неослаб", skipped, self.note(
            f"запись не называет проверку неослабления: {skipped}"))
        self.assertIn("мутац", skipped, self.note(
            f"запись не называет проверку заявки мутации: {skipped}"))

    def test_ac17_zones_gate_still_refuses_out_of_zone_file(self):
        """Проект без профиля: файл вне зон по-прежнему получает отказ гейта зон с его именем.

        Сценарий: запись без профиля; задача коммитит `lib/base.py` (вне
        зон) и правку в зоне. `advance` из `in_dev` — отказ с «гейт зон»,
        текст называет `lib/base.py`; задача в `in_dev`.

        Ловит мутацию: гейт зон завязан на наличие профиля (или на
        развилку проекта) — проект без профиля проходит его без отказа.
        """
        write = self.in_zone_edit()
        write[self.OUTSIDE_FILE] = f"BASE = {self.rng.randrange(2, 1 << 20)}\n"
        self.commit_task_change(write)

        out = self.advance()

        self.refusal_with(ZONES_WORD, self.OUTSIDE_FILE, out)
        self.assertEqual(self.row()["state"], "in_dev", self.note(out))

    def test_ac17_no_paths_edit_still_refused(self):
        """Проект без профиля: правка пути из `no_paths` по-прежнему получает отказ «защищённый путь».

        Сценарий: запись без профиля, `no_paths: [infra/]`; задача коммитит
        `infra/deploy.cfg` и правку в зоне. `advance` из `in_dev` — отказ
        с «защищённый путь», текст называет `infra/deploy.cfg`; задача в
        `in_dev`.

        Ловит мутацию: сверка `no_paths` выполняется только при профиле —
        проект без профиля правит защищённый путь без отказа.
        """
        write = self.in_zone_edit()
        write[self.NO_PATH_FILE] = f"replicas = {self.rng.randrange(2, 99)}\n"
        self.commit_task_change(write)

        out = self.advance()

        self.refusal_with(PROTECTED_WORD, self.NO_PATH_FILE, out)
        self.assertEqual(self.row()["state"], "in_dev", self.note(out))
