"""Артель идёт по общему потоку документов и свежести, как любой проект.

Группа: долгоживущий
Красен до реализации: переход задачи артели не пишет строку паспорта в её ссылку документов, запись «sha зафиксирован» артели без поля `артефакты=`, `show` артели читает статус SPEC с диска `config.TASKS`, `docs --fetch-all` не заводит клон внешнего проекта, `doctor` сверяет свежесть ветки артели с локальной `main` клона без `fetch`.

AC-5, AC-6, AC-8, AC-9, AC-12 SPEC задачи (строки 14, 15, 20, 22, 27
таблицы требования 1). Песочница — настоящий git:
`tests.sandbox.RealGitSandbox` (клон артели — сам репозиторий песочницы, у
него синхронный `origin`) и внешний проект `make_project_repo` (свой клон и
голый `origin`). Ссылки документов `refs/artifacts/<id>` пишутся сценарием
плотницки (`hash-object`/`update-index`/`write-tree`/`commit-tree` во
временный индекс) и фиксируются `store.record_fixation` — сдвиг сценарием
есть правка Оператора, не мимо пульта.

Имена проектов, состояния, статусы и тексты порождаются модулем `random`
при каждом запуске; зерно печатается и входит в текст провала.
"""
import io
import os
import random
import re
import shutil
import string
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import (catalog, config, docs_fetch, doctor, review, store,
                          workspace)
from tests.sandbox import (RealGitSandbox, capture, clone_artel_from_origin,
                           make_project_repo)

ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
PASSPORT = "PASSPORT.md"
FIXATION_ACTION = "sha зафиксирован"
VERDICT_ACTION = "state -> in_dev"
VERDICT_DETAIL = "замечания ревью, итерация {n}"
# Корень каталогов задач внутри ссылки документов (`<корень>/<id>/<файл>`).
DOCS_ROOT = "tasks"


def docs_rel(task_id: str, name: str) -> str:
    return "/".join((DOCS_ROOT, task_id, name))


def word(rng, k=6) -> str:
    return "".join(rng.choices(string.ascii_lowercase, k=k))


def run_cmd(fn, *args, **kwargs) -> tuple:
    """(вывод stdout+stderr, код SystemExit или None)."""
    buf = io.StringIO()
    code = None
    with redirect_stdout(buf), redirect_stderr(buf):
        try:
            fn(*args, **kwargs)
        except SystemExit as exc:
            code = exc.code
            if exc.code not in (None, 0):
                buf.write(f"\n{exc.code}")
    return buf.getvalue(), code


def fixation_fields(detail: str) -> list:
    """Имена полей записи «sha зафиксирован» по порядку."""
    return re.findall(r"(?:^|,\s*)([^=,\s]+)=", detail or "")


def fixation_value(detail: str, field: str) -> str:
    match = re.search(rf"(?:^|,\s*){field}=([^,\s]*)", detail or "")
    return match.group(1) if match else ""


class DocsRefSandbox(RealGitSandbox):
    """Пульт-песочница: клон артели — репозиторий песочницы с синхронным
    `origin`; внешний проект — свой клон и голый `origin`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.add_synced_origin()
        self.ext = "proekt" + word(self.rng, 5)
        self.ext_clone = make_project_repo(self.ext)
        self.conn = store.db()

    def msg(self, text: str) -> str:
        return f"зерно {self.seed}: {text}"

    def repo_of(self, target: str) -> Path:
        return self.root if target == config.DEFAULT_TARGET else self.ext_clone

    def git_in(self, repo, *args, env: dict = None) -> str:
        """git в репозитории `repo` песочницей (`RealGitSandbox.git`);
        `env` — добавка к окружению на время вызова."""
        with mock.patch.dict(os.environ, env or {}):
            return self.git("-C", str(repo), *args).strip()

    def hash_text(self, repo, text: str) -> str:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt",
                                         delete=False) as fh:
            fh.write(text)
        self.addCleanup(os.unlink, fh.name)
        return self.git_in(repo, "hash-object", "-w", fh.name)

    def new_task(self, target: str, state: str = "in_dev") -> str:
        task_id = "01" + "".join(self.rng.choices(ULID_ALPHABET, k=24))
        store.insert_task(self.conn, task_id, f"Фикстура {word(self.rng)}",
                          state, f"task/{task_id.lower()}-docs", target,
                          config.DEFAULT_BUDGET_USD)
        return task_id

    def commit_docs(self, target: str, task_id: str, files: dict) -> str:
        """Коммит `files` (имя в каталоге задачи -> текст) в
        `refs/artifacts/<id>` репозитория проекта поверх головы ссылки;
        ссылка фиксируется."""
        repo = self.repo_of(target)
        ref = f"refs/artifacts/{task_id}"
        parent = self.git_in(repo, "for-each-ref", "--format=%(objectname)", ref)
        with tempfile.TemporaryDirectory() as tmp:
            env = {"GIT_INDEX_FILE": str(Path(tmp) / "index")}
            if parent:
                self.git_in(repo, "read-tree", parent, env=env)
            else:
                self.git_in(repo, "read-tree", "--empty", env=env)
            for name, text in files.items():
                blob = self.hash_text(repo, text)
                self.git_in(repo, "update-index", "--add", "--cacheinfo",
                            f"100644,{blob},{docs_rel(task_id, name)}", env=env)
            tree = self.git_in(repo, "write-tree", env=env)
        args = ["commit-tree", tree, "-m", f"{task_id}: документы сценария"]
        if parent:
            args += ["-p", parent]
        sha = self.git_in(repo, *args)
        self.git_in(repo, "update-ref", ref, sha)
        store.record_fixation(self.conn, task_id)
        return sha

    def ref_head(self, target: str, task_id: str) -> str:
        return self.git_in(self.repo_of(target), "for-each-ref",
                           "--format=%(objectname)", f"refs/artifacts/{task_id}")

    def ref_file(self, target: str, task_id: str, name: str) -> str:
        repo, ref = self.repo_of(target), f"refs/artifacts/{task_id}"
        rel = docs_rel(task_id, name)
        if not self.git_in(repo, "for-each-ref", "--format=%(objectname)", ref):
            return ""
        names = self.git_in(repo, "ls-tree", "-r", "--name-only", ref).splitlines()
        if rel not in names:
            return ""
        return self.git("-C", str(repo), "show", f"{ref}:{rel}")

    def move(self, task_id: str, to: str, actor: str) -> None:
        frm = store.get_task(self.conn, task_id)["state"]
        capture(lambda: store.set_state(self.conn, task_id, to, actor,
                                        expected_state=frm,
                                        detail="переход сценария"))

    def code_commit(self, task_id: str) -> str:
        """Рабочая копия задачи и коммит кода в её ветке — голова кодовой
        ветки."""
        branch = store.get_task(self.conn, task_id)["branch"]
        wt, error = workspace.ensure(task_id, branch)
        self.assertIsNone(error, self.msg(f"рабочая копия: {error}"))
        rel = f"src_{word(self.rng)}.py"
        (Path(wt) / rel).write_text(f"X = {self.rng.randrange(1000)}\n",
                                    encoding="utf-8")
        self.git_in(wt, "add", rel)
        self.git_in(wt, "commit", "-q", "-m", f"{task_id}: код")
        return self.git_in(wt, "rev-parse", "HEAD")

    def fixation_details(self, task_id: str, since: int = 0) -> list:
        return [r["detail"] for r in store.task_steps(self.conn, task_id)
                if r["id"] > since and r["action"] == FIXATION_ACTION]


class PassportTest(DocsRefSandbox):

    def test_ac5_artel_transition_appends_passport_line_like_external(self):
        """Переход задачи артели дописывает строку паспорта в её `refs/artifacts/<id>` так же, как у задачи внешнего проекта.

        Сценарий: у задачи артели и у задачи внешнего проекта — ссылка
        документов с SPEC.md; обе проходят один и тот же случайный переход
        FSM (`store.set_state`) случайным актором. После перехода в каждой
        ссылке — файл паспорта `PASSPORT.md` каталога задачи со строкой `<состояние>
        actor=<актор>`, и голова ссылки сдвинулась.

        Ловит мутацию: у артели оставлена ветка «паспорта нет, ссылка
        только досылается» (`send_pending` вместо записи паспорта) — у
        задачи артели PASSPORT.md в ссылке нет, голова не сдвинулась.
        """
        to = self.rng.choice(["review", "verifying", "acceptance"])
        actor = self.rng.choice(["fsm", "operator"])
        for target in (config.DEFAULT_TARGET, self.ext):
            with self.subTest(target=target, seed=self.seed):
                task_id = self.new_task(target)
                before = self.commit_docs(target, task_id, {
                    "SPEC.md": f"---\nstatus: ready\n---\n# {word(self.rng)}\n"})
                self.move(task_id, to, actor)
                passport = self.ref_file(target, task_id, PASSPORT)
                self.assertRegex(passport, rf"\s{to}\s+actor={actor}\b",
                                 self.msg(f"{target}: нет строки паспорта "
                                          f"«{to} actor={actor}»:\n{passport!r}"))
                self.assertNotEqual(self.ref_head(target, task_id), before,
                                    self.msg(f"{target}: ссылка не сдвинута"))


class FixationRecordTest(DocsRefSandbox):

    def test_ac6_fixation_record_has_one_format_with_code_and_artifacts(self):
        """Запись «sha зафиксирован» у задачи артели и у задачи внешнего проекта одного формата и несёт `код=` и `артефакты=`.

        Сценарий: у задачи каждого проекта — ссылка документов и рабочая
        копия с коммитом кода; переход FSM пишет запись «sha
        зафиксирован». Набор и порядок полей записей двух задач совпадают
        и включают `target`, `sha`, `чисто`, `код`, `артефакты`; `код=` —
        голова кодовой ветки задачи, `артефакты=` — голова ссылки
        документов.

        Ловит мутацию: у артели оставлен прежний формат записи без
        `артефакты=` — наборы полей двух записей расходятся.
        """
        fields = {}
        for target in (config.DEFAULT_TARGET, self.ext):
            with self.subTest(target=target, seed=self.seed):
                task_id = self.new_task(target)
                self.commit_docs(target, task_id, {"SPEC.md": "---\n---\n"})
                code = self.code_commit(task_id)
                since = store.task_steps(self.conn, task_id)[-1]["id"]
                self.move(task_id, "review", "fsm")
                details = self.fixation_details(task_id, since)
                self.assertTrue(details, self.msg(f"{target}: записи нет"))
                detail = details[-1]
                fields[target] = fixation_fields(detail)
                for name in ("target", "sha", "чисто", "код", "артефакты"):
                    self.assertIn(name, fields[target], self.msg(
                        f"{target}: в записи нет поля {name}=: {detail}"))
                self.assertEqual(fixation_value(detail, "код"), code,
                                 self.msg(f"{target}: код= не голова ветки: "
                                          f"{detail}"))
                self.assertEqual(fixation_value(detail, "артефакты"),
                                 self.ref_head(target, task_id), self.msg(
                                     f"{target}: артефакты= не голова ссылки: "
                                     f"{detail}"))
        self.assertEqual(fields[config.DEFAULT_TARGET], fields[self.ext],
                         self.msg(f"форматы записей расходятся: {fields}"))

    def test_ac6_previous_verdict_sha_reads_code_field_for_both(self):
        """`review.previous_verdict_sha` находит базу по полю `код=` у задачи артели и у задачи внешнего проекта.

        Сценарий: у задачи каждого проекта — коммит кода в рабочей копии;
        журнал несёт переход-вердикт «замечания ревью, итерация N», после
        него переход FSM пишет запись «sha зафиксирован». База
        предыдущего вердикта — голова кодовой ветки задачи (значение
        `код=`), не голова ссылки документов.

        Ловит мутацию: в едином формате записи поле `код=` заменили или
        поставили после `артефакты=` с иным значением (голова ссылки
        документов) — база предыдущего вердикта перестаёт быть головой
        кода у одного из проектов.
        """
        for target in (config.DEFAULT_TARGET, self.ext):
            with self.subTest(target=target, seed=self.seed):
                task_id = self.new_task(target, state="review")
                self.commit_docs(target, task_id, {"SPEC.md": "---\n---\n"})
                code = self.code_commit(task_id)
                store.journal(self.conn, task_id, "fsm", VERDICT_ACTION,
                              VERDICT_DETAIL.format(n=self.rng.randint(1, 3)))
                self.move(task_id, "in_dev", "fsm")
                base = review.previous_verdict_sha(self.conn, task_id)
                self.assertEqual(base, code, self.msg(
                    f"{target}: база предыдущего вердикта {base!r} — не голова "
                    f"кода {code}; записи: {self.fixation_details(task_id)}"))


class ShowFromDocsRefTest(DocsRefSandbox):

    def test_ac8_show_of_artel_task_prints_status_from_docs_ref(self):
        """`show` задачи артели печатает статус SPEC из ссылки документов, а не с диска `config.TASKS`.

        Сценарий: у задачи артели SPEC.md в `refs/artifacts/<id>` несёт
        один статус, а файл `config.TASKS/<id>/SPEC.md` на диске — другой
        (оба — случайные). Вывод `show` несёт `SPEC.md: status=<статус
        ссылки>` и не несёт статуса диска.

        Ловит мутацию: у артели оставлено чтение frontmatter с диска
        `config.TASKS` — `show` печатает статус диска.
        """
        ref_status, disk_status = self.rng.sample(
            ["draft", "ready", "approved", "escalate", "changes_requested"], 2)
        task_id = self.new_task(config.DEFAULT_TARGET, state="spec_gate")
        self.commit_docs(config.DEFAULT_TARGET, task_id, {
            "SPEC.md": f"---\ntask: {task_id}\ntype: spec\nstatus: {ref_status}\n"
                       f"---\n\n# SPEC {word(self.rng)}\n"})
        disk = config.TASKS / task_id / "SPEC.md"
        disk.parent.mkdir(parents=True, exist_ok=True)
        disk.write_text(f"---\ntask: {task_id}\ntype: spec\n"
                        f"status: {disk_status}\n---\n\n# SPEC\n",
                        encoding="utf-8")
        out, _ = run_cmd(catalog.cmd_show, task_id)
        self.assertIn(f"SPEC.md: status={ref_status}", out, self.msg(
            f"show не печатает статус ссылки «{ref_status}»:\n{out}"))
        self.assertNotIn(f"SPEC.md: status={disk_status}", out, self.msg(
            f"show печатает статус диска «{disk_status}»:\n{out}"))


class FetchAllClonesTest(DocsRefSandbox):

    def test_ac9_fetch_all_clones_missing_project_and_brings_docs_refs(self):
        """`docs --fetch-all` заводит клон проекта из `targets.yaml`, у которого клона нет, и приносит его ссылки документов.

        Сценарий: в голом `origin` внешнего проекта — несколько ссылок
        `refs/artifacts/<id>`; клона проекта в его области нет, запись
        `targets.yaml` указывает на этот `origin`. После `docs
        --fetch-all` клон проекта есть, и каждая ссылка в нём равна ссылке
        `origin`.

        Ловит мутацию: клон по-прежнему заводится только для артели —
        проект без клона пропускается строкой «клона нет», клона и ссылок
        нет.
        """
        bare = config.PROJECTS / self.ext / "origin.git"
        placed = {}
        for _ in range(self.rng.randint(1, 3)):
            task_id = self.new_task(self.ext, state="done")
            placed[task_id] = self.commit_docs(self.ext, task_id, {
                "SPEC.md": f"---\nstatus: ready\n---\n# {word(self.rng)}\n"})
            self.git_in(self.ext_clone, "push", "-q", "origin",
                        f"refs/artifacts/{task_id}:refs/artifacts/{task_id}")
        shutil.rmtree(self.ext_clone)
        text = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(
            text.replace(f"file:///nonexistent/{self.ext}", str(bare)),
            encoding="utf-8")
        self.assertFalse(self.ext_clone.exists())
        out, code = run_cmd(docs_fetch.cmd_docs, ["--fetch-all"])
        self.assertTrue((self.ext_clone / ".git").exists(), self.msg(
            f"клон проекта {self.ext} не заведён:\n{out}"))
        for task_id, sha in placed.items():
            self.assertEqual(self.ref_head(self.ext, task_id), sha, self.msg(
                f"ссылка {task_id} не принесена в клон:\n{out}"))


class ArtelFreshnessSandbox(RealGitSandbox):
    """Клон артели — отдельный настоящий клон из голого `origin`; главная
    копия продвигает `origin/main`, локальная `main` клона стоит."""

    ARTEL_CLONE_IS_ROOT = False

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        origin = self.add_synced_origin()
        # HEAD голого `origin` — на `config.MAIN_BRANCH`, как у форджа: без
        # этого клон в git с веткой по умолчанию `master` (CI Linux) не
        # заводит локальную `main`.
        self.git("--git-dir", str(origin), "symbolic-ref", "HEAD",
                 f"refs/heads/{config.MAIN_BRANCH}")
        self.clone = clone_artel_from_origin(origin)
        self.conn = store.db()

    def msg(self, text: str) -> str:
        return f"зерно {self.seed}: {text}"

    def advance_origin_main(self, commits: int) -> None:
        for i in range(commits):
            (self.root / "marker.txt").write_text(f"main {i} {self.seed}\n",
                                                  encoding="utf-8")
            self.git("commit", "-q", "-am", f"main {i}")
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")

    def artel_task_with_branch(self) -> str:
        task_id = "01" + "".join(self.rng.choices(ULID_ALPHABET, k=24))
        branch = f"task/{task_id.lower()}-fresh"
        self.git("-C", str(self.clone), "branch", branch, config.MAIN_BRANCH)
        store.insert_task(self.conn, task_id, "Фикстура свежести", "in_dev",
                          branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        return task_id


class ArtelBranchFreshnessTest(ArtelFreshnessSandbox):

    def test_ac12_doctor_compares_artel_branch_with_origin_main_after_fetch(self):
        """`doctor` предупреждает о ветке артели, отставшей от `origin/main` клона, хотя локальная `main` клона не продвинута.

        Сценарий: ветка задачи артели заведена в клоне от его `main`; затем
        `origin/main` продвигается главной копией на случайное число
        коммитов больше `config.STALE_BRANCH_WARN_COMMITS`, а локальная
        `main` клона и его `origin/main` до `fetch` стоят. Проверка свежести
        `doctor` даёт `warn` с id задачи.

        Ловит мутацию: у артели оставлена сверка с локальной `main` клона
        без `fetch origin main` — отставание 0, проверка `ok`.
        """
        task_id = self.artel_task_with_branch()
        behind = config.STALE_BRANCH_WARN_COMMITS + self.rng.randint(1, 4)
        self.advance_origin_main(behind)
        checks = doctor.check_branch_freshness(self.conn)
        warns = [c for c in checks if c.status == "warn" and task_id in c.detail]
        self.assertTrue(warns, self.msg(
            f"ветка, отставшая от origin/main на {behind} коммитов, без "
            f"предупреждения: {[(c.status, c.detail) for c in checks]}"))

    def test_ac12_branch_within_threshold_of_origin_main_is_not_warned(self):
        """Ветка артели, отставшая от `origin/main` не больше `config.STALE_BRANCH_WARN_COMMITS`, предупреждения не получает.

        Сценарий: тот же, но `origin/main` продвинута на случайное число
        коммитов от 0 до порога включительно — `warn` с id задачи нет.

        Ловит мутацию: сверка после `fetch` считает отставание от
        `origin/main` с ошибкой порога (`>=` вместо `>`) или против чужой
        базы — ветка у самого порога получает предупреждение.
        """
        task_id = self.artel_task_with_branch()
        self.advance_origin_main(
            self.rng.randint(0, config.STALE_BRANCH_WARN_COMMITS))
        checks = doctor.check_branch_freshness(self.conn)
        self.assertFalse(
            [c for c in checks if c.status == "warn" and task_id in c.detail],
            self.msg(f"{[(c.status, c.detail) for c in checks]}"))


if __name__ == "__main__":
    import unittest
    unittest.main()
