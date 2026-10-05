"""Сценарий CI `scripts/plan_appendix_ci.py` на прогонах pull_request веток задач.

Группа: долгоживущий
Красен до реализации: сценарий отдаёт pull_request «не пуш ветки task/**» (код 0, приложения не накладываются), а сторож `--check-workflow` не смотрит условие `if:` шага — AC-1, AC-2 и AC-6 красные; AC-3, AC-4 и AC-5 держат уже существующее поведение (pull_request не task/** и из форка, пуши) и зелены с рождения.

Песочница воспроизводит прогон CI (`tests/sandbox.py::RealGitSandbox` +
bare `origin`):

- ветка задачи `task/<id в нижнем регистре>-<слаг>` правит свой файл и
  отправлена в `origin`; ссылка документов `refs/artifacts/<id>` с PLAN
  живёт только в `origin`;
- раннер pull_request выписан так, как его выписывает `actions/checkout`
  на pull_request: пустой репозиторий, `origin` → `file://`, подтяжка
  `refs/pull/<N>/merge` (merge-коммит ветки задачи с `main`) глубиной 1 и
  выписка этого коммита; раннер пуша — неглубокий клон ветки;
- сценарий запускается из корня раннера без аргументов (код сценария —
  этой рабочей копии), с переменными окружения Actions соответствующего
  события; унаследованные `GITHUB_*` процесса тестов убираются. Для
  pull_request — `GITHUB_EVENT_NAME=pull_request`,
  `GITHUB_REF=refs/pull/<N>/merge`, `GITHUB_HEAD_REF`, `GITHUB_BASE_REF`,
  `GITHUB_REPOSITORY` и файл события `GITHUB_EVENT_PATH`, в котором
  `pull_request.head.repo` — тот же репозиторий (`full_name` совпадает с
  `GITHUB_REPOSITORY`, `fork: false`) либо форк (иной `full_name`,
  `fork: true`) — так Actions различает ветку того же репозитория и
  ветку форка;
- «git не вызывается» — `git` в PATH сценария подменён обёрткой,
  журналирующей каждый вызов и передающей его настоящему git.
"""
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from orchestrator import checkpoint, config, idgen
from tests.sandbox import RealGitSandbox

CODE_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = CODE_ROOT / "scripts" / "plan_appendix_ci.py"

REPOSITORY = "artel-owner/artel"
FORK_REPOSITORY = "fork-owner/artel"

# Приложения PLAN правят только защищённые пути — от
# `config.PROTECTED_PATHS`, не литералом: перечень меняет Оператор.
# Markdown вне `tests/` и `.github/`: текст фикстуры в защищённом конфиге
# ломал бы сам прогон. Файл правки базы — любой, не защищённый.
PROTECTED_FILES = [p for p in config.PROTECTED_PATHS
                   if p.endswith(".md") and "*" not in p
                   and not p.startswith(("tests/", ".github"))]
BASE_FILES = ("base/alpha.txt", "base/beta.txt", "lib/gamma.cfg")
SLUG_WORDS = ("ci", "pr", "plan", "x", "2", "shag", "vetki", "merge")
HEADING_WORDS = ("правка", "шаг", "сторож", "настройка", "перечень")
# Ветки pull_request, не попадающие под `task/**`.
NON_TASK_HEADS = ("feature/x", "fix/{n}", "taskset/{n}-x", "task-{n}/x",
                  "main", "feature/task/{n}", "xtask/{n}-x", "task")

BASE_LINES = [f"строка базы {n:02d} из 40" for n in range(1, 41)]
BASE_TEXT = "".join(f"{line}\n" for line in BASE_LINES)
# Строки правок — через восемь: контекст хунка соседней правки их не задевает.
EDIT_LINES = BASE_LINES[::8]

GIT_SHIM = """#!/bin/sh
for a in "$@"; do printf '%s\\t' "$a" >> "{log}"; done
printf '\\n' >> "{log}"
exec "{real}" "$@"
"""


def names_number(text: str, number: int) -> bool:
    """Текст называет номер приложения рядом со словом «приложение»."""
    return re.search(rf"приложени\w*\s*(№\s*)?{number}\b", text,
                     re.IGNORECASE) is not None


class PlanAppendixPrSandbox(RealGitSandbox):
    """Автор, `origin` с веткой задачи и ссылкой документов, раннеры CI."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        tmp = Path(tempfile.mkdtemp(prefix="artel-plan-appendix-pr-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        self.tmp = tmp
        self.assertGreaterEqual(len(PROTECTED_FILES), 2, self.note(
            "в config.PROTECTED_PATHS нет двух защищённых файлов вне tests/"))
        # Два защищённых файла под приложения и третий — под правку базы.
        self.files = (self.rng.sample(PROTECTED_FILES, 2)
                      + [self.rng.choice(BASE_FILES)])
        for rel in self.files:
            self.write(rel, BASE_TEXT)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "база")
        self.origin = self.add_synced_origin()

        self.task = idgen.new_task_id()
        slug = "-".join(self.rng.sample(SLUG_WORDS, self.rng.randint(1, 3)))
        self.branch = f"task/{self.task.lower()}-{slug}"
        self.checkout(self.branch, create=True)
        self.write("feature.txt", f"код задачи {self.rng.randrange(10**6)}\n")
        self.git("add", "feature.txt")
        self.git("commit", "-q", "-m", "код задачи")
        self.git("push", "-q", "origin", self.branch)
        self.checkout(config.MAIN_BRANCH)
        self.pr_number = self.rng.randint(1, 9999)

    # ------------------------------------------------------------ обвязка

    def note(self, text: str) -> str:
        branch = getattr(self, "branch", "ещё не заведена")
        return f"{text} (зерно {self.seed}, ветка {branch})"

    def write(self, rel: str, text: str) -> None:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def read(self, root: Path, rel: str) -> str:
        return (root / rel).read_text(encoding="utf-8")

    def heading(self, number: int) -> str:
        word = self.rng.choice(HEADING_WORDS)
        return f"Приложение {number}: {word} {self.rng.randrange(10**6)}"

    def chain_diffs(self, rel: str, steps: list) -> list[str]:
        """Диффы последовательных правок `rel` ([(старое, новое), …]) от
        дерева ветки задачи: каждый следующий — от состояния после
        предыдущего (ложится только после него)."""
        self.checkout(self.branch)
        path = self.root / rel
        text = path.read_text(encoding="utf-8")
        diffs = []
        for old, new in steps:
            self.assertIn(old, text)
            path.write_text(text, encoding="utf-8")
            self.git("add", "--", rel)
            text = text.replace(old, new)
            path.write_text(text, encoding="utf-8")
            diff = self.git("diff", "--", rel)
            self.assertIn("diff --git a/", diff)
            diffs.append(diff)
        self.git("reset", "-q", "--", rel)
        self.git("checkout", "-q", "--", rel)
        self.checkout(config.MAIN_BRANCH)
        return diffs

    def edit_diff(self, rel: str, old: str, new: str) -> str:
        return self.chain_diffs(rel, [(old, new)])[0]

    def plan_text(self, appendices: list) -> str:
        sections = "".join(f"\n## {heading}\n\n```diff\n{diff}```\n"
                           for heading, diff in appendices)
        return (f"---\ntask: {self.task}\ntype: plan\n"
                f"author_role: developer\nstatus: ready\n"
                f"schema_version: 2\n---\n\n# PLAN\n\n## Подход\n\n"
                f"Фикстура.\n{sections}")

    def publish_plan(self, appendices: list) -> None:
        """PLAN с приложениями — в ссылку документов `origin`, мимо ветки."""
        docs = self.tmp / f"docs-{self.rng.randrange(10**9)}"
        self.git("init", "-q", str(docs))
        path = docs / checkpoint.task_dir_zone(self.task) / "PLAN.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.plan_text(appendices), encoding="utf-8")
        self.git("-C", str(docs), "add", "-A")
        self.git("-C", str(docs), "-c", "user.email=artel@example.invalid",
                 "-c", "user.name=artel tests", "commit", "-q", "-m",
                 "документы задачи")
        self.git("-C", str(docs), "push", "-q", "--force", str(self.origin),
                 f"HEAD:refs/artifacts/{self.task}")

    def advance_main(self, rel: str, old: str, new: str) -> None:
        """База уходит вперёд после отведения ветки: правка `rel` на main."""
        self.checkout(config.MAIN_BRANCH)
        text = self.read(self.root, rel)
        self.assertIn(old, text)
        self.write(rel, text.replace(old, new))
        self.git("commit", "-q", "-am", "база ушла вперёд")
        self.git("push", "-q", "origin", config.MAIN_BRANCH)

    def pr_runner(self) -> Path:
        """Раннер pull_request: merge-коммит ветки задачи с main, выписанный
        так, как его выписывает `actions/checkout`."""
        self.git("checkout", "-q", "--detach", config.MAIN_BRANCH)
        self.git("merge", "--no-ff", "-q", "-m",
                 f"Merge {self.branch} into {config.MAIN_BRANCH}", self.branch)
        merge = self.git("rev-parse", "HEAD").strip()
        self.checkout(config.MAIN_BRANCH)
        ref = f"refs/pull/{self.pr_number}/merge"
        self.git("push", "-q", "--force", "origin", f"{merge}:{ref}")
        runner = self.tmp / f"runner-pr-{self.rng.randrange(10**9)}"
        self.git("init", "-q", str(runner))
        self.rgit(runner, "remote", "add", "origin", f"file://{self.origin}")
        local = f"refs/remotes/pull/{self.pr_number}/merge"
        self.rgit(runner, "fetch", "-q", "--no-tags", "--depth=1", "origin",
                  f"+{ref}:{local}")
        self.rgit(runner, "checkout", "-q", "--force", local)
        self.assertEqual(self.rgit(runner, "rev-parse", "HEAD").strip(), merge)
        return runner

    def push_runner(self, branch: str) -> Path:
        runner = self.tmp / f"runner-push-{self.rng.randrange(10**9)}"
        self.git("clone", "-q", "--depth", "1", "--branch", branch,
                 f"file://{self.origin}", str(runner))
        return runner

    def rgit(self, runner: Path, *args: str) -> str:
        return self.git("-C", str(runner), *args)

    def git_shim(self) -> tuple[Path, Path]:
        """(каталог обёртки git для PATH, журнал её вызовов)."""
        shim_dir = self.tmp / f"shim-{self.rng.randrange(10**9)}"
        shim_dir.mkdir()
        log = shim_dir / "git-calls.log"
        real_git = shutil.which("git")
        self.assertTrue(real_git, "git не найден в PATH")
        shim = shim_dir / "git"
        shim.write_text(GIT_SHIM.format(log=log, real=real_git),
                        encoding="utf-8")
        shim.chmod(0o755)
        return shim_dir, log

    def git_calls(self, log: Path) -> list[str]:
        if not log.exists():
            return []
        return [line for line in log.read_text(encoding="utf-8").splitlines()
                if line.strip()]

    def event_file(self, payload: dict) -> Path:
        path = self.tmp / f"event-{self.rng.randrange(10**9)}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def base_env(self, runner: Path, path_prefix: str) -> dict:
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("GITHUB_")}
        env.update({
            "GITHUB_ACTIONS": "true",
            "GITHUB_REPOSITORY": REPOSITORY,
            "GITHUB_REPOSITORY_OWNER": REPOSITORY.split("/")[0],
            "GITHUB_WORKSPACE": str(runner),
            "GITHUB_SHA": self.rgit(runner, "rev-parse", "HEAD").strip(),
            "PYTHONDONTWRITEBYTECODE": "1",
        })
        if path_prefix:
            env["PATH"] = path_prefix + os.pathsep + env.get("PATH", "")
        return env

    def run_pr(self, runner: Path, head_ref: str, fork: bool = False,
               path_prefix: str = "") -> subprocess.CompletedProcess:
        env = self.base_env(runner, path_prefix)
        head_repo = FORK_REPOSITORY if fork else REPOSITORY
        repo = lambda name: {"full_name": name, "name": name.split("/")[1],
                             "owner": {"login": name.split("/")[0]},
                             "fork": name != REPOSITORY}
        payload = {
            "action": "synchronize",
            "number": self.pr_number,
            "pull_request": {
                "number": self.pr_number,
                "head": {"ref": head_ref, "label":
                         f"{head_repo.split('/')[0]}:{head_ref}",
                         "repo": repo(head_repo)},
                "base": {"ref": config.MAIN_BRANCH,
                         "label": f"{REPOSITORY.split('/')[0]}:"
                                  f"{config.MAIN_BRANCH}",
                         "repo": repo(REPOSITORY)},
            },
            "repository": repo(REPOSITORY),
        }
        env.update({
            "GITHUB_EVENT_NAME": "pull_request",
            "GITHUB_REF": f"refs/pull/{self.pr_number}/merge",
            "GITHUB_REF_NAME": f"{self.pr_number}/merge",
            "GITHUB_REF_TYPE": "branch",
            "GITHUB_HEAD_REF": head_ref,
            "GITHUB_BASE_REF": config.MAIN_BRANCH,
            "GITHUB_EVENT_PATH": str(self.event_file(payload)),
        })
        return self.run_script(runner, env)

    def run_push(self, runner: Path, branch: str,
                 path_prefix: str = "") -> subprocess.CompletedProcess:
        env = self.base_env(runner, path_prefix)
        payload = {"ref": f"refs/heads/{branch}",
                   "repository": {"full_name": REPOSITORY}}
        env.update({
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_REF": f"refs/heads/{branch}",
            "GITHUB_REF_NAME": branch,
            "GITHUB_REF_TYPE": "branch",
            "GITHUB_HEAD_REF": "",
            "GITHUB_BASE_REF": "",
            "GITHUB_EVENT_PATH": str(self.event_file(payload)),
        })
        return self.run_script(runner, env)

    def run_script(self, runner: Path, env: dict) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT)], cwd=runner,
                              env=env, capture_output=True, text=True,
                              timeout=120)

    def output(self, res: subprocess.CompletedProcess) -> str:
        return f"код {res.returncode}\n{res.stdout}\n{res.stderr}"

    def changed(self, runner: Path) -> set[str]:
        out = self.rgit(runner, "status", "--porcelain")
        return {line[3:] for line in out.splitlines() if line}


class PullRequestAppliesTest(PlanAppendixPrSandbox):

    def test_ac1_pull_request_applies_appendices_in_order_on_merge_tree(self):
        """pull_request ветки задачи: все приложения PLAN — по порядку, на merge-коммит, без коммита.

        Сценарий: после отведения ветки main правит третий файл (база ушла
        вперёд — merge-коммит PR отличается от головы ветки). PLAN несёт
        цепочку из 2-3 приложений к первому файлу, где каждое следующее
        правит строку, внесённую предыдущим (ложится только после него), и
        — в случайном месте цепочки — независимое приложение ко второму
        файлу. Раннер выписан на `refs/pull/<N>/merge`, событие —
        pull_request из ветки того же репозитория. Сценарий: код 0; первый
        файл — итог всей цепочки, во втором — правка его приложения; правка
        базы в третьем файле на месте и он не изменён (приложения легли на
        дерево чекаута, а не на перевыложенную голову ветки); HEAD раннера —
        прежний merge-коммит.

        Ловит мутацию: `task_branch` по-прежнему отдаёт None на
        pull_request (или шаг читает ветку из `GITHUB_REF`
        `refs/pull/<N>/merge`) — код 0 «не пуш ветки task/**», первый файл
        без правок; вторая — приложения накладываются не в порядке PLAN
        (обратно или сортировкой) — звено цепочки не ложится, код 1;
        третья — сценарий перевыкладывает голову ветки (`git checkout
        $GITHUB_HEAD_REF`) — правка базы в третьем файле пропадает, HEAD
        сдвинут; четвёртая — наложенное фиксируется коммитом — HEAD
        раннера сдвинут.
        """
        chain_rel, other_rel, base_rel = self.files
        line = self.rng.choice(EDIT_LINES)
        steps, current = [], line
        for i in range(self.rng.randint(2, 3)):
            new = f"звено {i + 1} ({self.rng.randrange(10**6)})"
            steps.append((current, new))
            current = new
        diffs = self.chain_diffs(chain_rel, steps)
        other_marker = f"правка второго файла ({self.rng.randrange(10**6)})"
        diffs.insert(self.rng.randint(0, len(diffs)), self.edit_diff(
            other_rel, self.rng.choice(EDIT_LINES), other_marker))
        self.publish_plan([(self.heading(i + 1), diff)
                           for i, diff in enumerate(diffs)])
        base_marker = f"правка базы ({self.rng.randrange(10**6)})"
        self.advance_main(base_rel, self.rng.choice(EDIT_LINES), base_marker)
        runner = self.pr_runner()
        head = self.rgit(runner, "rev-parse", "HEAD").strip()
        expected_chain = BASE_TEXT.replace(line, current)

        res = self.run_pr(runner, self.branch)

        out = self.output(res)
        self.assertEqual(res.returncode, 0, self.note(out))
        self.assertEqual(self.read(runner, chain_rel), expected_chain,
                         self.note(f"цепочка приложений к {chain_rel} не "
                                   f"наложена целиком\n{out}"))
        self.assertIn(other_marker, self.read(runner, other_rel),
                      self.note(f"приложение к {other_rel} не наложено\n{out}"))
        self.assertIn(base_marker, self.read(runner, base_rel), self.note(
            f"правки базы в {base_rel} нет — приложения легли не на дерево "
            f"чекаута pull_request\n{out}"))
        changed = self.changed(runner)
        self.assertIn(chain_rel, changed, self.note(out))
        self.assertNotIn(base_rel, changed, self.note(
            f"{base_rel} изменён относительно merge-коммита\n{out}"))
        self.assertEqual(self.rgit(runner, "rev-parse", "HEAD").strip(), head,
                         self.note(f"HEAD раннера сдвинут\n{out}"))


class PullRequestInapplicableTest(PlanAppendixPrSandbox):

    def test_ac2_appendix_not_applicable_on_merge_tree_fails_with_number_and_path(self):
        """Приложение легло бы на голову ветки, но не на merge-коммит: код 1, номер и путь в выводе.

        Сценарий: PLAN несёт 0-2 применимых приложения ко второму файлу и
        затем приложение к первому файлу, правящее строку, которую после
        отведения ветки поменяла база (main) — на голову ветки оно
        ложится (проверено `git apply --check` на ветке), на merge-коммит
        PR — нет. Событие — pull_request из ветки того же репозитория.
        Сценарий: код 1; вывод (stdout и stderr) называет номер этого
        приложения рядом со словом «приложение» и его путь.

        Ловит мутацию: pull_request ветки задачи не обрабатывается (код 0
        «не пуш ветки task/**»); вторая — сценарий накладывает приложения
        на перевыложенную голову ветки — приложение ложится, код 0;
        третья — отказ `git apply` проглочен или безымянный (без номера
        и пути) — код 0 либо вывод не называет приложение.
        """
        bad_rel, good_rel, _ = self.files
        before = self.rng.randint(0, 2)
        lines = self.rng.sample(EDIT_LINES, before + 1)
        appendices = [(self.heading(i + 1), self.edit_diff(
            good_rel, lines[i], f"правка {i + 1}")) for i in range(before)]
        number = before + 1
        target = lines[before]
        bad_diff = self.edit_diff(bad_rel, target,
                                  f"правка приложения {number}")
        appendices.append((self.heading(number), bad_diff))
        self.publish_plan(appendices)

        self.checkout(self.branch)
        patch = self.tmp / "bad.diff"
        patch.write_text(bad_diff, encoding="utf-8")
        self.git("apply", "--check", str(patch))
        self.checkout(config.MAIN_BRANCH)
        self.advance_main(bad_rel, target,
                          f"база поменяла строку ({self.rng.randrange(10**6)})")
        runner = self.pr_runner()

        res = self.run_pr(runner, self.branch)

        out = self.output(res)
        self.assertEqual(res.returncode, 1, self.note(out))
        text = res.stdout + res.stderr
        self.assertTrue(names_number(text, number), self.note(
            f"вывод не называет номер приложения {number}\n{out}"))
        self.assertIn(bad_rel, text, self.note(
            f"вывод не называет путь приложения {bad_rel}\n{out}"))


class PullRequestUntouchedTest(PlanAppendixPrSandbox):

    def assert_no_git(self, runner: Path, head_ref: str, fork: bool) -> None:
        shim_dir, log = self.git_shim()
        res = self.run_pr(runner, head_ref, fork=fork,
                          path_prefix=str(shim_dir))
        out = self.output(res)
        where = f"pull_request из {'форка' if fork else 'ветки'} {head_ref}"
        self.assertEqual(res.returncode, 0, self.note(f"{where}: {out}"))
        self.assertEqual(self.git_calls(log), [], self.note(
            f"{where}: сценарий звал git\n{out}"))
        self.assertEqual(self.changed(runner), set(), self.note(
            f"{where}: дерево раннера изменено\n{out}"))

    def publish_applicable_plan(self) -> None:
        self.publish_plan([(self.heading(1), self.edit_diff(
            self.files[0], self.rng.choice(EDIT_LINES), "правка приложения"))])

    def test_ac3_pull_request_from_non_task_branch_never_calls_git(self):
        """pull_request из ветки не `task/**`: код 0, ни одного вызова git.

        Сценарий: в `origin` есть ссылка документов задачи с применимым
        приложением, раннер выписан на merge-коммит PR. Для нескольких
        имён ветки источника, не попадающих под `task/**` (`feature/x`,
        `taskset/…`, `task-…/x`, `feature/task/…`, `xtask/…`, `main`, `task`
        — случайная выборка от зерна), сценарий завершается кодом 0, обёртка
        git в PATH не вызвана ни разу, дерево раннера не тронуто.

        Ловит мутацию: префикс ветки проверяется как `startswith("task")`
        без косой черты или подстрокой `"task/" in head_ref` — ветки
        `taskset/…`, `task-…/x`, `feature/task/…`, `xtask/…` идут в
        `git ls-remote`, и журнал обёртки непуст; вторая — сценарий
        читает ссылки `origin` до отбора ветки — git вызван для любой.
        """
        self.publish_applicable_plan()
        runner = self.pr_runner()
        heads = [h.format(n=self.task.lower()) for h in
                 self.rng.sample(NON_TASK_HEADS, 4)]
        if "feature/x" not in heads:
            heads.append("feature/x")
        for head_ref in heads:
            self.assert_no_git(runner, head_ref, fork=False)

    def test_ac4_pull_request_from_fork_task_branch_never_calls_git(self):
        """pull_request из форка с веткой `task/<id>-<слаг>`: код 0, ни одного вызова git.

        Сценарий: в `origin` есть ссылка документов задачи этой ветки с
        применимым приложением, раннер выписан на merge-коммит PR; файл
        события называет головой PR форк (`pull_request.head.repo`:
        иной `full_name`, `fork: true`), `GITHUB_HEAD_REF` — имя ветки
        задачи. Сценарий: код 0, обёртка git не вызвана ни разу, дерево
        раннера не тронуто.

        Ловит мутацию: сценарий отбирает pull_request только по
        `GITHUB_HEAD_REF` без проверки репозитория головы — ветка форка
        `task/**` идёт в `git ls-remote`/`fetch`, журнал обёртки непуст и
        приложение ложится в дерево раннера.
        """
        self.publish_applicable_plan()
        runner = self.pr_runner()
        self.assert_no_git(runner, self.branch, fork=True)


class PushUnchangedTest(PlanAppendixPrSandbox):

    def test_ac5_push_runs_unchanged(self):
        """Пуши: `task/**` накладывает приложения, `main` и `feature/x` — код 0 без git.

        Сценарий: PLAN в ссылке документов несёт 1-2 применимых
        приложения. Пуш ветки задачи (раннер — неглубокий клон ветки,
        `GITHUB_HEAD_REF` пуст, как у Actions на push): код 0, правки всех
        приложений в дереве раннера, HEAD прежний. Пуш `main` и пуш
        `feature/x` (раннеры — клоны этих веток, обёртка git в PATH): код
        0, обёртка не вызвана ни разу, дерево не тронуто.

        Ловит мутацию: ветка задачи берётся только из `GITHUB_HEAD_REF`
        (пустого на push) — пуш `task/**` больше не накладывает
        приложения, правок в дереве нет; вторая — пуш не `task/**` идёт в
        `git ls-remote` (снят отбор события/префикса) — журнал обёртки
        непуст.
        """
        markers = [f"правка пуша {i} ({self.rng.randrange(10**6)})"
                   for i in range(self.rng.randint(1, 2))]
        lines = self.rng.sample(EDIT_LINES, len(markers))
        self.publish_plan([(self.heading(i + 1), self.edit_diff(
            self.files[0], lines[i], marker))
            for i, marker in enumerate(markers)])
        runner = self.push_runner(self.branch)
        head = self.rgit(runner, "rev-parse", "HEAD").strip()

        res = self.run_push(runner, self.branch)

        out = self.output(res)
        self.assertEqual(res.returncode, 0, self.note(f"пуш ветки: {out}"))
        text = self.read(runner, self.files[0])
        for marker in markers:
            self.assertIn(marker, text, self.note(
                f"пуш ветки: приложение не наложено\n{out}"))
        self.assertEqual(self.rgit(runner, "rev-parse", "HEAD").strip(), head,
                         self.note(f"пуш ветки: HEAD сдвинут\n{out}"))

        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:refs/heads/feature/x")
        for branch in (config.MAIN_BRANCH, "feature/x"):
            runner = self.push_runner(branch)
            shim_dir, log = self.git_shim()
            res = self.run_push(runner, branch, path_prefix=str(shim_dir))
            out = self.output(res)
            self.assertEqual(res.returncode, 0, self.note(
                f"пуш {branch}: {out}"))
            self.assertEqual(self.git_calls(log), [], self.note(
                f"пуш {branch}: сценарий звал git\n{out}"))
            self.assertEqual(self.changed(runner), set(), self.note(
                f"пуш {branch}: дерево изменено\n{out}"))


OLD_CONDITION = ("github.event_name == 'push' && "
                 "startsWith(github.ref, 'refs/heads/task/')")
NEW_CONDITIONS = (
    "(github.event_name == 'push' && startsWith(github.ref, "
    "'refs/heads/task/')) || (github.event_name == 'pull_request' && "
    "startsWith(github.head_ref, 'task/'))",
    "${{ (github.event_name == 'push' && startsWith(github.ref, "
    "'refs/heads/task/')) || (github.event_name == 'pull_request' && "
    "startsWith(github.head_ref, 'task/') && "
    "github.event.pull_request.head.repo.full_name == github.repository) }}",
    "github.event_name == 'pull_request' && startsWith(github.head_ref, "
    "'task/') || github.event_name == 'push' && startsWith(github.ref, "
    "'refs/heads/task/')",
)

WORKFLOW_HEAD = """name: ci

on:
  push:
    branches: ['**']
  pull_request:

jobs:
  guard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: сторож шага приложений PLAN
        run: python3 scripts/plan_appendix_ci.py --check-workflow .github/workflows/ci.yml

  changes:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: пуш main
        if: github.event_name == 'push' && github.ref == 'refs/heads/main'
        run: echo main
"""

WORKFLOW_JOB = """
  {job}:
    needs: changes
    if: ${{{{ !cancelled() && needs.changes.outputs.code != 'false' }}}}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: приложения PLAN задачи на дереве ветки
        # Приложения PLAN задачи — до тестов.
        if: {condition}
        run: python3 scripts/plan_appendix_ci.py
      - name: тесты
        run: python3 -m pytest tests -p no:cacheprovider
"""


class CheckWorkflowConditionTest(unittest.TestCase):

    def setUp(self):
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        tmp = Path(tempfile.mkdtemp(prefix="artel-wf-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        self.path = tmp / "ci.yml"

    def check(self, conditions: dict) -> subprocess.CompletedProcess:
        text = WORKFLOW_HEAD + "".join(
            WORKFLOW_JOB.format(job=job, condition=conditions[job])
            for job in ("python", "python-min"))
        self.path.write_text(text, encoding="utf-8")
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("GITHUB_")}
        return subprocess.run([sys.executable, str(SCRIPT), "--check-workflow",
                               str(self.path)], env=env, capture_output=True,
                              text=True, timeout=120)

    def test_ac6_check_workflow_flags_push_only_condition_by_job(self):
        """Сторож: прежнее условие push-only шага — код 1 с именем job; условие с pull_request в обоих — код 0.

        Сценарий: синтетический workflow с jobs `guard`, `changes` (в нём
        постороннее push-only условие шага пуша main), `python` и
        `python-min`, шаг сценария стоит до pytest. (а) В случайном
        непустом подмножестве jobs `python`/`python-min` условие шага
        приложений — прежнее `github.event_name == 'push' &&
        startsWith(github.ref, 'refs/heads/task/')`, в остальных — условие,
        пропускающее и pull_request веток `task/**`: код 1, вывод называет
        каждый job с прежним условием. (б) В обоих jobs условие пропускает
        и pull_request (варианты формы — от зерна): код 0.

        Ловит мутацию: сторож по-прежнему не смотрит `if:` шага — на (а)
        код 0; вторая — нарушение без имени job — вывод не называет
        `python`/`python-min`; третья — сторож проверяет только job
        `python` — прежнее условие в одном `python-min` даёт код 0;
        четвёртая — нарушением считается любое упоминание `'push'` в
        условии — на (б) код 1.
        """
        jobs = ["python", "python-min"]
        bad = self.rng.sample(jobs, self.rng.randint(1, 2))
        conditions = {job: OLD_CONDITION if job in bad
                      else self.rng.choice(NEW_CONDITIONS) for job in jobs}

        res = self.check(conditions)

        out = (f"зерно {self.seed}, прежнее условие в {bad}: код "
               f"{res.returncode}\n{res.stdout}\n{res.stderr}")
        self.assertEqual(res.returncode, 1, out)
        text = res.stdout + res.stderr
        for job in bad:
            pattern = (r"python-min" if job == "python-min"
                       else r"\bpython\b(?!-min)")
            self.assertRegex(text, pattern, f"нарушение не называет job "
                                            f"{job}\n{out}")

        conditions = {job: self.rng.choice(NEW_CONDITIONS) for job in jobs}
        res = self.check(conditions)
        self.assertEqual(res.returncode, 0, (
            f"зерно {self.seed}, условия {conditions}: код {res.returncode}\n"
            f"{res.stdout}\n{res.stderr}"))


if __name__ == "__main__":
    unittest.main()
