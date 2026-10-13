"""Гейт мержа и записка роли: записка `NOTE-<роль>.md` первого уровня
документов задачи со свободным текстом мерж не отказывает, битый `PLAN.md`
рядом с ней и записка в `acceptance_tests/` — отказывают, как прежде.

Группа: долгоживущий

Красен до реализации: белый список корня каталога задачи не знает имён `NOTE-<роль>.md` — проверка документов задачи на ссылке называет записку посторонним файлом, и мерж задачи с запиской отказан.

Планка провалидирована временным стабом реализации (все методы зелёные, стаб удалён, не закоммичен).

Связка, которую держит файл: «`approve` на `merge_gate` — проверка
документов задачи на голове ссылки `refs/artifacts/<id>` — журнал «merge
FAILED» — main origin». Песочница — настоящий git
(`tests.sandbox.RealGitSandbox`): главная копия пульта, она же клон
артели, и bare `origin` рядом. Первый коммит несёт копию `orchestrator/` и
`scripts/` этого дерева (гейт мержа зовёт `scripts/guard.py` и
`scripts/codebase_map.py` дерева мержа и применяет правила `guard --all` к
документам задачи артели), заглушку карты кодовой базы и исторический
каталог закрытой задачи с её RETRO. Задача заводится прямо на
`merge_gate`: кодовая ветка от origin/main (опубликована), ссылка
документов — коммит вспомогательного репозитория, отправленный и в
репозиторий задачи, и в его `origin`, затем фиксация
(`store.record_fixation`). Команда — диспетчером `artel.main()` тем же
argv, что набирает Оператор (`approve`). GitHub изображает подставной `gh`
в начале `PATH` (все проверки зелёные), часы подставные.

Номер задачи, роль записки и её текст порождаются при каждом запуске от
зерна; зерно печатается и входит в текст провала.
"""
import contextlib
import io
import os
import random
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import artel, catalog, config, store
from tests.sandbox import RealGitSandbox, capture, patch_pult_sleep

REPO = Path(__file__).resolve().parent.parent
TASKS_DIR = config.TASKS.name
ROLES = ("analyst", "spec_auditor", "test_author", "developer", "reviewer")
ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
MAP_REL = "docs/codebase-map.md"
MAP_PLACEHOLDER = ("---\nbuilt_at_sha: " + "0" * 40 + "\n---\n\n"
                   "# Карта кодовой базы (заглушка песочницы)\n")

# Подставной `gh`: зелёные проверки на любой коммит, пустые списки прогонов
# и запросов на слияние; прочие вызовы — отказ.
FAKE_GH = r'''
import json, re, sys
args = sys.argv[1:]
joined = " ".join(args)
if args[:1] == ["api"] and "/check-runs" in joined:
    page = re.search(r"[?&]page=(\d+)", joined)
    runs = [{"name": "тесты кода", "status": "completed",
             "conclusion": "success"}]
    shown = runs if page is None or page.group(1) == "1" else []
    print(json.dumps({"total_count": len(runs), "check_runs": shown},
                     ensure_ascii=False))
    sys.exit(0)
if args[:2] in (["run", "list"], ["pr", "list"], ["pr", "view"]):
    print("[]")
    sys.exit(0)
sys.stderr.write("gh песочницы: вызов не поддержан: " + joined + "\n")
sys.exit(1)
'''


def plank_text() -> str:
    """Планка задачи песочницы из одного метода; метка собирается заменой,
    чтобы сканер планки пульта не принял литерал за тест этого файла."""
    return ('"""Планка задачи песочницы."""\nimport unittest\n\n\n'
            'class Fixture(unittest.TestCase):\n'
            '    def test_@ac1_fixture(self):\n        pass\n').replace("@ac", "ac")


def spec_text(task: str) -> str:
    return (f"---\ntask: {task}\ntype: spec\nauthor_role: analyst\n"
            f"status: ready\nschema_version: 5\nzones: kod/\nbudget_usd: 10\n---\n\n"
            f"# SPEC: задача {task}\n\n"
            f"## Контекст\n\nЗадача песочницы мержа.\n\n## Требования\n\n"
            f"1. Требование.\n\n## Критерии приёмки\n\n@AC-1. Критерий.\n\n"
            f"## Не входит\n\n- Ничего.\n").replace("@AC", "AC")


def plan_text(task: str) -> str:
    return (f"---\ntask: {task}\ntype: plan\nauthor_role: developer\n"
            f"status: ready\nschema_version: 1\n---\n\n# PLAN: задача {task}\n\n"
            f"## Подход\n\nФикстура.\n\n## Шаги\n\n## Покрытие требований\n\n"
            f"## Влияние на систему\n")


BROKEN_PLAN = "план без заголовочного блока\n\n## Подход\n\nтекст\n"


class NoteMergeGateTest(RealGitSandbox):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        role = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        role.start()
        self.addCleanup(role.stop)
        os.environ.pop(config.ARTEL_ROLE_ENV, None)
        self.prepare_main()
        self.origin = self.add_synced_origin()
        src = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, src, ignore_errors=True)
        self.docs_src = Path(src) / "docs-src"
        self.git("init", "-q", "-b", "docs-src", str(self.docs_src))
        capture(catalog.cmd_init)
        self.conn = store.db()

        bindir = self.root / ".artel" / "fake-bin"
        bindir.mkdir(parents=True, exist_ok=True)
        gh = bindir / "gh"
        gh.write_text(f"#!{sys.executable}\n{FAKE_GH}", encoding="utf-8")
        gh.chmod(0o755)
        env = mock.patch.dict(os.environ, {
            "PATH": f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"})
        env.start()
        self.addCleanup(env.stop)

        self.clock = 0.0
        base_mono, base_wall = time.monotonic(), time.time()
        for target, fake in (("time.monotonic", lambda: base_mono + self.clock),
                             ("time.time", lambda: base_wall + self.clock)):
            patcher = mock.patch(target, side_effect=fake)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(patch_pult_sleep(self.fake_sleep).close)

    def fake_sleep(self, seconds) -> None:
        self.clock += float(seconds)
        if self.clock > 10 * 24 * 3600:
            raise AssertionError(self.msg("ожидание не кончается"))

    def prepare_main(self) -> None:
        for name in ("orchestrator", "scripts"):
            shutil.copytree(REPO / name, self.root / name,
                            ignore=shutil.ignore_patterns("__pycache__"))
        (self.root / "docs").mkdir(exist_ok=True)
        (self.root / MAP_REL).write_text(MAP_PLACEHOLDER, encoding="utf-8")
        old = "01H" + "".join(self.rng.choice(ULID_ALPHABET) for _ in range(23))
        plank = self.root / TASKS_DIR / old / "acceptance_tests" / "test_old.py"
        plank.parent.mkdir(parents=True)
        plank.write_text(plank_text(), encoding="utf-8")
        retro_path = self.root / "docs" / "retro" / f"{old}.md"
        retro_path.parent.mkdir(parents=True)
        retro_path.write_text(f"# RETRO: {old}\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "код пульта")

    # ----------------------------------------------------------------- git

    def in_repo(self, repo: Path, *args: str) -> str:
        return self.git("-C", str(repo), *args)

    def task_id(self) -> str:
        return "01T" + "".join(self.rng.choice(ULID_ALPHABET) for _ in range(23))

    def put_docs(self, task: str, files: dict) -> None:
        src = self.docs_src
        self.in_repo(src, "checkout", "-q", "--orphan", f"d-{task}")
        self.in_repo(src, "rm", "-rfq", "--ignore-unmatch", ".")
        for rel, text in files.items():
            path = src / TASKS_DIR / task / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.in_repo(src, "add", "-A")
        self.in_repo(src, "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                     "commit", "-q", "-m", f"{task}: документы")
        sha = self.in_repo(src, "rev-parse", "HEAD").strip()
        for dest in (self.root, self.origin):
            self.in_repo(src, "push", "-q", str(dest), f"{sha}:refs/artifacts/{task}")

    def commit_to_main(self, files: dict) -> None:
        self.git("fetch", "-q", "origin")
        self.git("merge", "-q", "--ff-only", f"origin/{config.MAIN_BRANCH}")
        for rel, text in files.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            self.git("add", rel)
        self.git("commit", "-q", "-m", "правка main до задачи")
        self.git("push", "-q", "origin", f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    def make_task(self, extra_docs: dict, plan: str | None = None) -> dict:
        """Задача на `merge_gate`: кодовая ветка от origin/main опубликована,
        ссылка документов в репозитории и его origin, фиксация."""
        self.commit_to_main({
            MAP_REL: f"{MAP_PLACEHOLDER}\n{self.rng.randrange(10 ** 9)}\n"})
        task = self.task_id()
        branch = f"task/{task.lower()}-x"
        self.git("fetch", "-q", "origin")
        self.git("checkout", "-q", "-b", branch, f"origin/{config.MAIN_BRANCH}")
        code = f"zadacha_{task.lower()}.py"
        (self.root / code).write_text(f"VALUE = {self.rng.randrange(10 ** 6)}\n",
                                      encoding="utf-8")
        self.git("add", code)
        self.git("commit", "-q", "-m", f"{task}: код")
        self.git("push", "-q", "-u", "origin", branch)
        self.git("checkout", "-q", config.MAIN_BRANCH)
        store.insert_task(self.conn, task, f"Задача {task}", "merge_gate", branch,
                          config.DEFAULT_TARGET, config.DEFAULT_BUDGET_USD)
        files = {"SPEC.md": spec_text(task),
                 "PLAN.md": plan if plan is not None else plan_text(task),
                 "acceptance_tests/test_ac1_fixture.py": plank_text()}
        files.update(extra_docs)
        self.put_docs(task, files)
        store.record_fixation(self.conn, task)
        return {"id": task, "branch": branch}

    # ------------------------------------------------------------ команды

    def cli(self, *argv: str) -> tuple:
        out = io.StringIO()
        ok, tail = True, ""
        with mock.patch.object(sys, "argv", ["artel.py", *argv]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                artel.main()
            except SystemExit as exc:
                if exc.code not in (0, None):
                    ok, tail = False, f"\n{exc.code}"
            except Exception as exc:  # noqa: BLE001 — исход сценария, не сбой теста
                ok, tail = False, f"\nисключение: {exc!r}"
        return ok, out.getvalue() + tail

    def approve(self, task: dict) -> str:
        outputs = []
        for _ in range(3):
            ok, out = self.cli("approve", task["id"])
            outputs.append(out)
            if not ok or self.state_of(task) != "merge_gate":
                break
        journal = [f"{r['action']} | {r['detail'] or ''}"
                   for r in store.task_steps(store.db(), task["id"])]
        return "\n".join(outputs) + "\n" + "\n".join(journal)

    def state_of(self, task: dict) -> str:
        return store.get_task(store.db(), task["id"])["state"]

    def origin_main(self) -> str:
        return self.in_repo(self.origin, "rev-parse",
                            f"refs/heads/{config.MAIN_BRANCH}").strip()

    def failed_details(self, task: dict) -> list:
        return [row["detail"] or "" for row in store.task_steps(store.db(), task["id"])
                if row["action"] == "merge FAILED"]

    def note(self) -> tuple:
        role = self.rng.choice(ROLES)
        token = self.rng.randrange(10 ** 9)
        text = (f"Выяснено: {token}\nНе сработало: --- не frontmatter ---\n"
                f"Где остановился: здесь\nЧего не хватило: правила {token}\n")
        return f"NOTE-{role}.md", text

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    # -------------------------------------------------------------- AC-4

    def test_ac4_merge_gate_passes_first_level_note_with_free_text(self):
        """Документы задачи артели на голове ссылки несут записку роли
        первого уровня со свободным текстом без frontmatter.

        Наблюдение: `approve` доводит задачу до `done`; ни одна запись
        «merge FAILED» не называет записку.

        Ловит мутацию: имя записки добавлено в белый список корня, но
        проверка документов задачи на ссылке (правила `guard --all`) гонит её
        через структурную проверку артефакта — «нет frontmatter», мерж
        отказан.
        """
        name, text = self.note()
        task = self.make_task({name: text})

        out = self.approve(task)

        self.assertEqual(self.state_of(task), "done", self.msg(out))
        self.assertEqual([d for d in self.failed_details(task) if name in d], [],
                         self.msg(out))

    def test_ac4_merge_gate_refuses_broken_plan_and_note_in_plank(self):
        """Две задачи артели: (а) рядом с запиской первого уровня — `PLAN.md`
        без заголовочного блока; (б) записка со свободным текстом лежит в
        `acceptance_tests/`.

        Наблюдение: мерж отказан — задача на `merge_gate`, main origin не
        сдвинулся, запись «merge FAILED» называет `PLAN.md` (а) или записку
        планки (б); в (а) ни одна запись не называет записку первого уровня.

        Ловит мутацию: освобождение записки дано пропуском всех корневых
        `.md` либо по имени файла без уровня — битый `PLAN.md` или записка в
        `acceptance_tests/` проходят проверку документов задачи.
        """
        name, text = self.note()
        cases = [("битый PLAN.md", {name: text}, BROKEN_PLAN, "PLAN.md"),
                 ("записка в планке", {f"acceptance_tests/{name}": text}, None,
                  f"acceptance_tests/{name}")]
        for case, extra, plan, culprit in cases:
            with self.subTest(случай=case, зерно=self.seed):
                task = self.make_task(extra, plan=plan)
                before = self.origin_main()

                out = self.approve(task)

                self.assertEqual(self.state_of(task), "merge_gate", self.msg(out))
                self.assertEqual(self.origin_main(), before, self.msg(out))
                details = self.failed_details(task)
                self.assertTrue([d for d in details if culprit in d],
                                self.msg(f"«merge FAILED» не называет {culprit}: {out}"))
                if plan is not None:
                    self.assertEqual(
                        [d for d in details
                         if f"{TASKS_DIR}/{task['id']}/{name}" in d], [],
                        self.msg(out))


if __name__ == "__main__":
    unittest.main()
