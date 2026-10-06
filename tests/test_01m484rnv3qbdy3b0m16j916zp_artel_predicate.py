"""Оставленные развилки артели узнают её одной функцией-признаком `repo_context`.

Группа: долгоживущий
Красен до реализации: ни одна из восьми оставленных развилок не зовёт `repo_context.is_artel` — каждая сравнивает имя проекта (или путь клона) с `config.DEFAULT_TARGET` напрямую, и подмена признака ветку поведения внешнего проекта не меняет.

AC-13 SPEC задачи (требования 1-2, строки 16, 18, 19,
21, 24, 25, 28, 29 таблицы): признак артели — `repo_context.is_artel`
(SPEC называет её; преемник с ДРУГИМ именем потребует правки этой планки
через `amend-tests`). Подмена признака отвечает «артель» для внешнего
проекта и для самой артели — независимо от того, что ей передают:
контекст (`RepoContext`), имя проекта, строку задачи или путь в области
проекта (`config.PROJECTS/<имя>/…`). Каждый сценарий сначала сверяет
ветку внешнего проекта без подмены (так развилка ведёт себя сегодня), затем
— ветку артели под подменой.

Имена проектов, номера задач и тексты порождаются модулем `random` при
каждом запуске; зерно печатается и входит в текст провала.
"""
import io
import os
import random
import string
import subprocess
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import (ci, coldstart, config, docs_fetch, doctor, fsm,
                          github_adapter, repo_context, snapshot, store)
from tests.sandbox import (LightTransitionSandbox, RealGitSandbox,
                           SchemaTmpRootTest, capture, declare_target,
                           make_project_repo)


# Корень каталогов задач внутри ссылки документов (`<корень>/<id>/<файл>`).
DOCS_ROOT = "tasks"


def subject_target(arg):
    """Имя проекта, о котором спрашивают признак: из контекста, имени,
    строки задачи или пути в области проектов; `None` — не определить."""
    if arg is None:
        return None
    if isinstance(arg, str):
        return arg
    target = getattr(arg, "target", None)
    if isinstance(target, str):
        return target
    if isinstance(arg, os.PathLike):
        path = Path(arg).resolve()
        if path == Path(config.ROOT).resolve():
            return config.DEFAULT_TARGET
        try:
            return path.relative_to(Path(config.PROJECTS).resolve()).parts[0]
        except (ValueError, IndexError):
            return None
    try:
        return arg["target"]
    except (KeyError, IndexError, TypeError):
        return None


def artel_also_for(ext: str):
    """Подмена признака: «артель» — для артели и для проекта `ext`."""
    def fake(arg=None, *args, **kwargs):
        return subject_target(arg) in (config.DEFAULT_TARGET, ext)
    return fake


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


def word(rng, k=6) -> str:
    return "".join(rng.choices(string.ascii_lowercase, k=k))


# Номерные задачи пульта для сценариев строк 24-25 (литералы, см. линт
# формата id в CI).
LEGACY_TASK_DIRS = ("T007", "T042", "T118", "T256", "T391", "T804")

class _SeedMixin:
    def seed_rng(self):
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.ext = "proekt" + word(self.rng, 5)

    def msg(self, text: str) -> str:
        return f"зерно {self.seed}: {text}"

    def as_artel(self):
        return mock.patch.object(repo_context, "is_artel",
                                 artel_also_for(self.ext))


class PredicateLightTest(_SeedMixin, SchemaTmpRootTest):
    """Развилки, наблюдаемые без настоящего git: 16, 18, 19, 24, 25."""

    def setUp(self):
        super().setUp()
        self.seed_rng()

    def write_ext_entry(self, url: str, base: str) -> None:
        text = config.TARGETS.read_text(encoding="utf-8")
        config.TARGETS.write_text(
            text.rstrip("\n") + "\n" + (
                f"  {self.ext}:\n"
                f"    forge: github\n"
                f"    url: {url}\n"
                f"    base: {base}\n"
                f"    token_slot: {self.ext}-token\n"
                f"    no_paths: []\n"
                f"    project_skills: []\n"
                f"    merge_gate: operator\n"), encoding="utf-8")

    def test_ac13_resolve_row16_uses_predicate(self):
        """Строка 16: контекст проекта, признанного артелью, собирается без записи `targets.yaml` — remote `origin`, база `config.MAIN_BRANCH`.

        Сценарий: запись внешнего проекта несёт свой адрес форджа и свою
        базовую ветку. Без подмены `resolve` отдаёт их; под подменой
        признака — `remote="origin"` и `base=config.MAIN_BRANCH`, как у
        артели. Проект без записи в `targets.yaml` без подмены не
        разрешается (`None`), под подменой — разрешается так же.

        Ловит мутацию: `resolve` по-прежнему сравнивает имя с
        `config.DEFAULT_TARGET` вместо признака — под подменой внешний
        проект получает адрес и базу из своей записи, а проект без записи
        остаётся `None`.
        """
        url = f"http://localhost/{word(self.rng)}.git"
        base = "trunk-" + word(self.rng, 4)
        self.write_ext_entry(url, base)
        ctx = repo_context.resolve(self.ext)
        self.assertEqual((ctx.remote, ctx.base), (url, base),
                         self.msg("без подмены — запись проекта"))
        ghost = "bezzapisi" + word(self.rng, 4)
        self.assertIsNone(repo_context.resolve(ghost), self.msg("без записи"))
        with mock.patch.object(repo_context, "is_artel",
                               lambda arg=None, *a, **k: subject_target(arg)
                               in (config.DEFAULT_TARGET, self.ext, ghost)):
            ctx = repo_context.resolve(self.ext)
            lost = repo_context.resolve(ghost)
        self.assertIsNotNone(ctx, self.msg("под подменой контекст не разрешён"))
        self.assertEqual((ctx.remote, ctx.base),
                         ("origin", config.MAIN_BRANCH), self.msg(
                             f"под подменой признака resolve({self.ext}) "
                             f"читает targets.yaml: {ctx}"))
        self.assertIsNotNone(lost, self.msg(
            "проект без записи, признанный артелью, не разрешён"))
        self.assertEqual((lost.remote, lost.base),
                         ("origin", config.MAIN_BRANCH), self.msg(str(lost)))

    def test_ac13_gh_repo_row18_uses_predicate(self):
        """Строка 18: `gh` для проекта, признанного артелью, зовётся без `--repo`.

        Сценарий: снятие Draft MR (`github_adapter.undraft_mr`) задачи
        внешнего проекта с форджем github; `ci.gh` подменён шпионом.
        Без подмены вызов несёт `repo=<адрес форджа проекта>`; под подменой
        признака — ни `repo`, как у артели.

        Ловит мутацию: `_gh_repo_kwargs` по-прежнему сравнивает имя с
        `config.DEFAULT_TARGET` — под подменой `gh pr ready` получает
        `repo=` (адрес из записи либо `origin` из контекста артели).
        """
        declare_target(self.ext)
        calls = []

        def spy(*args, **kwargs):
            calls.append(kwargs)
            return subprocess.CompletedProcess(["gh", *args], 0, "ok", "")

        row = {"target": self.ext, "branch": f"task/{word(self.rng)}",
               "draft_mr_created": 1, "is_canary": 0, "title": "фикстура"}
        task_id = "01" + "".join(self.rng.choices("0123456789ABCDEF", k=24))
        store.insert_task(store.db(), task_id, "Фикстура", "merge_gate",
                          row["branch"], self.ext, config.DEFAULT_BUDGET_USD)
        with mock.patch.object(ci, "gh", spy):
            capture(github_adapter.undraft_mr, store.db(), task_id, row)
        self.assertTrue(calls and "repo" in calls[-1], self.msg(
            f"без подмены gh зовётся без --repo: {calls}"))
        calls.clear()
        with mock.patch.object(ci, "gh", spy), self.as_artel():
            capture(github_adapter.undraft_mr, store.db(), task_id, row)
        self.assertTrue(calls, self.msg("gh не позван под подменой"))
        self.assertNotIn("repo", calls[-1], self.msg(
            f"под подменой признака gh получил --repo: {calls[-1]}"))

    def test_ac13_ci_repo_row19_uses_predicate(self):
        """Строка 19: внутренние вызовы `ci` для клона проекта, признанного артелью, идут без `repo=`.

        Сценарий: `ci.branch_status` ветки задачи с `repo=` клона внешнего
        проекта; `ci.head_sha` подменён шпионом. Без подмены голова
        читается с `repo=<клон проекта>`; под подменой признака — прежней
        формой без `repo=`, как для клона артели.

        Ловит мутацию: `_repo_kwargs` по-прежнему сравнивает путь с клоном
        артели (`workspace.repo(config.DEFAULT_TARGET)`) — под подменой
        `head_sha` получает `repo=<клон проекта>`.
        """
        declare_target(self.ext)
        clone = repo_context.clone_path(self.ext)
        calls = []

        def spy(branch, **kwargs):
            calls.append(kwargs)
            return "", "голова не прочитана (тест)"

        branch = f"task/{word(self.rng)}"
        with mock.patch.object(ci, "head_sha", spy):
            ci.branch_status(branch, repo=clone)
        self.assertEqual(calls, [{"repo": clone}], self.msg(
            "без подмены head_sha получает клон проекта"))
        calls.clear()
        with mock.patch.object(ci, "head_sha", spy), self.as_artel():
            ci.branch_status(branch, repo=clone)
        self.assertEqual(calls, [{}], self.msg(
            f"под подменой признака head_sha получил repo=: {calls}"))

    def test_ac13_coldstart_tasks_dir_row25_uses_predicate(self):
        """Строка 25: каталог номерных задач проекта, признанного артелью, — `config.TASKS` главной копии.

        Сценарий: в `config.TASKS` лежит каталог `T<a>`, в каталоге задач
        области внешнего проекта — `T<b>` (a ≠ b). Без подмены
        `observed_max_task_number(<проект>)` — b; под подменой признака — a.

        Ловит мутацию: `_tasks_dir` по-прежнему сравнивает имя с
        `config.DEFAULT_TARGET` — под подменой счётчик сеется из каталога
        области проекта (b), а не из `config.TASKS`.
        """
        # Имена — литералы `Tnnn` (линт CI запрещает форматировать id задачи
        # вне orchestrator/idgen.py), число — из имени.
        name_a, name_b = self.rng.sample(LEGACY_TASK_DIRS, 2)
        a, b = int(name_a[1:]), int(name_b[1:])
        (config.TASKS / name_a).mkdir(parents=True)
        (config.PROJECTS / self.ext / "tasks" / name_b).mkdir(parents=True)
        self.assertEqual(coldstart.observed_max_task_number(self.ext), b,
                         self.msg("без подмены — каталог проекта"))
        with self.as_artel():
            got = coldstart.observed_max_task_number(self.ext)
        self.assertEqual(got, a, self.msg(
            f"под подменой признака каталог задач не config.TASKS: {got}"))

    def test_ac13_coldstart_history_row24_uses_predicate(self):
        """Строка 24: следы номерных задач пульта (RETRO в `docs/retro/`) сканируются для проекта, признанного артелью.

        Сценарий: в `docs/retro/` главной копии лежит `T<n>.md`, каталогов
        задач нет. Без подмены для внешнего проекта счётчик — 0; под
        подменой признака — n.

        Ловит мутацию: `observed_max_task_number` по-прежнему решает
        «сканировать ли ветки/RETRO/историю main» сравнением имени с
        `config.DEFAULT_TARGET` — под подменой RETRO не учтён, счётчик 0.
        """
        name = self.rng.choice(LEGACY_TASK_DIRS)
        n = int(name[1:])
        retro = config.ROOT / "docs" / "retro"
        retro.mkdir(parents=True)
        (retro / f"{name}.md").write_text("# RETRO\n", encoding="utf-8")
        self.assertEqual(coldstart.observed_max_task_number(self.ext), 0,
                         self.msg("без подмены RETRO пульта не сканируется"))
        with self.as_artel():
            got = coldstart.observed_max_task_number(self.ext)
        self.assertEqual(got, n, self.msg(
            f"под подменой признака RETRO пульта не учтён: {got}"))


class PredicateSpecGateTest(_SeedMixin, LightTransitionSandbox):
    """Строка 29: сверка раздела «Меняемое поведение» на approve SPEC."""

    def setUp(self):
        super().setUp()
        self.seed_rng()
        # Клон проекта нужен чтению SPEC из ссылки документов
        # (`artifact_branch.show` без клона отказывает до сверки раздела).
        make_project_repo(self.ext)

    SPEC ="""---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: tests/, app.py
budget_usd: 30
---

# SPEC: фикстура признака артели

## Контекст

Фикстура песочницы.

## Требования

1. Требование фикстуры.

## Критерии приёмки

AC-1. Фикстурный критерий.

## Меняемое поведение

Смена ожидания фикстуры.

- `tests/test_fx_{word}.py::Fx{cls}Test::test_missing_{word}`: `1` → `2` (требование 1)

## Не входит

Ничего.
"""

    def section_refusals(self, task_id: str) -> list:
        from scripts import guard
        return [r["detail"] for r in store.task_steps(store.db(), task_id)
                if r["action"] == "approve отклонён"
                and guard.BEHAVIOR_CHANGE_SECTION in (r["detail"] or "")]

    def spec_gate_task(self) -> str:
        task_id = "01" + "".join(self.rng.choices("0123456789ABCDEFGHJKMNPQRSTVWXYZ", k=24))
        store.insert_task(store.db(), task_id, "Фикстура признака", "spec_gate",
                          f"task/{task_id.lower()}-x", self.ext,
                          config.DEFAULT_BUDGET_USD)
        tdir = config.TASKS / task_id
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "SPEC.md").write_text(self.SPEC.format(
            task=task_id, word=word(self.rng), cls=word(self.rng).capitalize()),
            encoding="utf-8")
        return task_id

    def test_ac13_behavior_change_row29_uses_predicate(self):
        """Строка 29: раздел «Меняемое поведение» сверяется на approve SPEC у задачи проекта, признанного артелью.

        Сценарий: задача внешнего проекта на `spec_gate`, её SPEC называет
        в разделе «Меняемое поведение» метод, которого нет в main. Без
        подмены approve раздел не сверяет — записи «approve отклонён» о
        разделе нет; под подменой признака (вторая задача — тот же
        сценарий) approve мягко отказывает записью, называющей раздел.

        Ловит мутацию: `_behavior_change_declaration` по-прежнему
        сравнивает `t["target"]` с `config.DEFAULT_TARGET` — под подменой
        раздел не сверяется, отказа о разделе нет.
        """
        plain = self.spec_gate_task()
        out, _ = run_cmd(fsm.cmd_approve, plain)
        self.assertEqual(self.section_refusals(plain), [], self.msg(
            f"без подмены раздел сверён у внешнего проекта:\n{out}"))
        patched = self.spec_gate_task()
        with self.as_artel():
            out, _ = run_cmd(fsm.cmd_approve, patched)
        self.assertTrue(self.section_refusals(patched), self.msg(
            f"под подменой признака раздел «Меняемое поведение» не сверён:\n"
            f"{out}"))
        self.assertEqual(store.get_task(store.db(), patched)["state"],
                         "spec_gate", self.msg("задача ушла со spec_gate"))


class PredicateGitTest(_SeedMixin, RealGitSandbox):
    """Развилки, наблюдаемые на настоящем git: 21 и 28. Клон артели —
    сам репозиторий песочницы (главная копия)."""

    def setUp(self):
        super().setUp()
        self.seed_rng()
        self.ext_clone = make_project_repo(self.ext)
        self.ext_origin = config.PROJECTS / self.ext / "origin.git"

    def new_task(self, state: str) -> str:
        task_id = "01" + "".join(self.rng.choices("0123456789ABCDEFGHJKMNPQRSTVWXYZ", k=24))
        store.insert_task(store.db(), task_id, "Фикстура признака", state,
                          f"task/{task_id.lower()}-x", self.ext,
                          config.DEFAULT_BUDGET_USD)
        return task_id

    def git_in(self, repo, *args, env: dict = None) -> str:
        """git в репозитории `repo` песочницей (`RealGitSandbox.git`);
        `env` — добавка к окружению на время вызова."""
        with mock.patch.dict(os.environ, env or {}):
            return self.git("-C", str(repo), *args).strip()

    def main_copy_docs_ref(self, task_id: str, text: str) -> str:
        """`refs/artifacts/<id>` с SPEC.md каталога задачи — только в git
        главной копии пульта (плотницкая запись во временный индекс)."""
        with tempfile.TemporaryDirectory() as tmp:
            spec = Path(tmp) / "SPEC.md"
            spec.write_text(text, encoding="utf-8")
            blob = self.git_in(self.root, "hash-object", "-w", str(spec))
            env = {"GIT_INDEX_FILE": str(Path(tmp) / "index")}
            self.git_in(self.root, "read-tree", "--empty", env=env)
            rel = "/".join((DOCS_ROOT, task_id, "SPEC.md"))
            self.git_in(self.root, "update-index", "--add", "--cacheinfo",
                        f"100644,{blob},{rel}", env=env)
            tree = self.git_in(self.root, "write-tree", env=env)
        sha = self.git_in(self.root, "commit-tree", tree, "-m", "документы")
        self.git_in(self.root, "update-ref", f"refs/artifacts/{task_id}", sha)
        return sha

    def test_ac13_docs_main_copy_reader_row21_uses_predicate(self):
        """Строка 21: ссылка документов, которая есть только в git главной копии, читается для задачи проекта, признанного артелью.

        Сценарий: задача внешнего проекта; её `refs/artifacts/<id>` с
        SPEC.md лежит только в git главной копии пульта — ни в клоне
        проекта, ни в его origin. Без подмены `docs <id> SPEC.md` отказывает
        «ссылки … нет»; под подменой признака печатает текст SPEC из
        главной копии.

        Ловит мутацию: `_main_copy_reader` по-прежнему сравнивает проект
        задачи с `config.DEFAULT_TARGET` — под подменой команда отказывает,
        текста SPEC в выводе нет.
        """
        task_id = self.new_task("done")
        text = f"---\nstatus: ready\n---\n\n# SPEC {word(self.rng)}\n"
        self.main_copy_docs_ref(task_id, text)
        out, code = run_cmd(docs_fetch.cmd_docs, [task_id, "SPEC.md"])
        self.assertNotIn(text.strip(), out, self.msg(
            f"без подмены задача проекта читается из главной копии:\n{out}"))
        self.assertNotIn(code, (None, 0), self.msg(out))
        with self.as_artel():
            out, code = run_cmd(docs_fetch.cmd_docs, [task_id, "SPEC.md"])
        self.assertIn(code, (None, 0), self.msg(
            f"под подменой признака docs отказал:\n{out}"))
        self.assertIn(text.strip(), out, self.msg(
            f"под подменой признака SPEC не прочитан из главной копии:\n{out}"))

    def test_ac13_doctor_closing_commit_row28_uses_predicate(self):
        """Строка 28: коммит закрытия задачи проекта, признанного артелью, ищется и в git главной копии.

        Сценарий: закрытая задача внешнего проекта; её коммит закрытия
        записан в журнал, но объект есть только в git главной копии —
        не в клоне проекта; в origin проекта ссылки нет. Без подмены
        `doctor --fix` пишет «не найден ни в клоне, ни в главной копии», и
        ссылка в origin проекта не появляется; под подменой признака
        (вторая задача) коммит досылается в origin проекта из главной
        копии — ссылка там равна коммиту закрытия.

        Ловит мутацию: `_fix_unsent_closed_ref` по-прежнему сравнивает
        проект с `config.DEFAULT_TARGET` — под подменой коммит из главной
        копии не досылается, ссылки в origin проекта нет.
        """
        def closed_task() -> tuple:
            task_id = self.new_task("done")
            closing = self.git_in(self.root, "commit-tree", "HEAD^{tree}",
                                  "-p", "HEAD", "-m",
                                  f"закрытие {word(self.rng)}")
            store.journal(store.db(), task_id, "orchestrator",
                          snapshot.CLOSING_ACTION,
                          f"refs/artifacts/{task_id} <- {closing} (done)")
            self.assertEqual(snapshot.closing_sha(store.db(), task_id),
                             closing, self.msg("запись закрытия не читается"))
            return task_id, closing

        def origin_ref(task_id: str) -> str:
            return self.git_in(self.ext_origin, "for-each-ref",
                               "--format=%(objectname)",
                               f"refs/artifacts/{task_id}")

        plain, plain_closing = closed_task()
        out, _ = run_cmd(doctor.cmd_doctor, fix=True)
        self.assertEqual(origin_ref(plain), "", self.msg(
            f"без подмены коммит закрытия задачи проекта дослан из главной "
            f"копии:\n{out}"))
        patched, closing = closed_task()
        with self.as_artel():
            out, _ = run_cmd(doctor.cmd_doctor, fix=True)
        self.assertEqual(origin_ref(patched), closing, self.msg(
            f"под подменой признака коммит закрытия не дослан из главной "
            f"копии:\n{out}"))


if __name__ == "__main__":
    import unittest
    unittest.main()
