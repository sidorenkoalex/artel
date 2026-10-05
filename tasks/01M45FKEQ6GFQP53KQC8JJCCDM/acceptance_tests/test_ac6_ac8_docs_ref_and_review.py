"""AC-6 и AC-8 SPEC 01M45FKEQ6GFQP53KQC8JJCCDM: ссылка документов как
источник `show`, клон внешнего проекта в `docs --fetch-all`, гейт отработки
замечаний ревью для задачи внешнего проекта.

AC-6: `show` задачи внешнего проекта и задачи артели печатает статусы
SPEC/PLAN/REVIEW из ссылки документов `refs/artifacts/<id>` в клоне проекта
задачи, а не с диска `config.TASKS` (на диске лежит приманка с другим
статусом). `docs --fetch-all` заводит клон внешнего проекта по `url` записи
`targets.yaml` (локальный голый репозиторий), если клона ещё нет, и делает
в нём fetch ссылок документов.

AC-8: `_review_rework_gate` отказывает задаче внешнего проекта с REVIEW.md
`status: changes_requested` в ссылке документов, если последний коммит
разработчика в кодовой ветке старше вердикта ревьювера, — так же, как
задаче артели.

Сценарии на настоящем git (`RealGitSandbox`, клон артели — сам репозиторий
песочницы; клон внешнего проекта — `make_project_repo`), коммиты ссылок
собираются плотницки во временном индексе с заданным временем коммиттера.
Сети нет: `origin` — локальные голые репозитории.

Группа: разовый
Обоснование группы: сценарии ставят настоящие ссылки `refs/artifacts/<id>` в
клонах проектов и зовут внутренние функции гейта (`advance_gates.review.
_review_rework_gate`) и команды (`docs_fetch.cmd_docs`, `catalog.cmd_show`)
напрямую — долгоживущей группе это запрещено.
Красен до реализации: `_artifact_frontmatter` читает frontmatter задачи артели с диска config.TASKS (печатается приманка status=draft), `docs_fetch._fetch_all` заводит клон только артели (внешний проект «пропущен», клона нет), `_review_rework_gate` возвращает None для не-артели — методы test_ac6_show_artel_task_reads_docs_ref, test_ac6_fetch_all_creates_external_clone и test_ac8_external_task_refused красные; test_ac6_show_external_task_reads_docs_ref и test_ac8_artel_task_refused держат существующее поведение и зелёные с рождения.
"""
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from orchestrator import catalog, config, docs_fetch, store
from orchestrator.advance_gates import review
from tests.sandbox import RealGitSandbox, capture, make_project_repo

ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
PROJECT_NAMES = ("sled", "sani", "drovni", "rozvalni")

# Вердикт ревьювера позже последнего коммита разработчика: переделка не
# отработана.
DEVELOPER_TS = "2026-08-01T10:00:00+00:00"
VERDICT_TS = "2026-08-02T10:00:00+00:00"

ENV_IDENTITY = {
    "GIT_AUTHOR_NAME": "artel tests", "GIT_AUTHOR_EMAIL": "artel@example.invalid",
    "GIT_COMMITTER_NAME": "artel tests",
    "GIT_COMMITTER_EMAIL": "artel@example.invalid",
}


def _git(repo, *args, env=None, stdin=None) -> str:
    res = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                         text=True, env=env, input=stdin)
    if res.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} в {repo}: {res.stderr}")
    return res.stdout.strip()


def commit_files(repo, files: dict, message: str, when: str,
                 parent: str | None = None) -> str:
    """Коммит в `repo`, дерево — ровно `files` ({путь: текст}), время
    автора и коммиттера `when`; рабочее дерево и индекс репозитория не
    трогаются (временный индекс). Возвращает sha."""
    index_dir = tempfile.mkdtemp()
    try:
        env = dict(os.environ, **ENV_IDENTITY,
                   GIT_INDEX_FILE=str(Path(index_dir) / "index"),
                   GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
        for rel, text in files.items():
            blob = _git(repo, "hash-object", "-w", "--stdin", env=env,
                        stdin=text)
            _git(repo, "update-index", "--add", "--cacheinfo",
                 f"100644,{blob},{rel}", env=env)
        tree = _git(repo, "write-tree", env=env)
        args = ["commit-tree", tree, "-m", message]
        if parent:
            args += ["-p", parent]
        return _git(repo, *args, env=env)
    finally:
        shutil.rmtree(index_dir, ignore_errors=True)


def frontmatter_doc(task_id: str, kind: str, status: str, extra: str = "") -> str:
    return (f"---\ntask: {task_id}\ntype: {kind}\nauthor_role: x\n"
            f"status: {status}\n{extra}schema_version: 1\n---\n\n# {kind}\n")


def targets_yaml(entries: dict) -> str:
    """Записи `targets.yaml`: {имя: url}."""
    text = "targets:\n"
    for name, url in entries.items():
        text += (f"  {name}:\n    forge: github\n    url: {url}\n"
                 f"    base: {config.MAIN_BRANCH}\n    token_slot: {name}-token\n"
                 "    no_paths: []\n    project_skills: []\n"
                 "    merge_gate: operator\n")
    return text


class _Sandbox(RealGitSandbox):
    """Пульт на настоящем git; генераторы id и имени проекта из `random`."""

    def setUp(self):
        super().setUp()
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def why(self, text: str) -> str:
        return f"{text} (зерно {self.seed})"

    def new_id(self) -> str:
        return "01M" + "".join(self.rng.choice(ULID_ALPHABET) for _ in range(23))

    def project_name(self) -> str:
        return self.rng.choice(PROJECT_NAMES) + str(self.rng.randrange(10, 100))

    def add_task(self, task_id: str, target: str) -> str:
        branch = f"task/{task_id.lower()}-x"
        store.insert_task(store.db(), task_id, "Задача", "in_dev", branch,
                          target, 25.0)
        return branch

    def clone_of(self, target: str) -> Path:
        return config.PROJECTS / target / "repo"


class ShowReadsDocsRefTest(_Sandbox):
    """AC-6: `show` читает статусы документов из ссылки документов."""

    NAMES = ("SPEC.md", "PLAN.md", "REVIEW.md")

    def _seed(self, target: str) -> tuple[str, dict]:
        """Задача `target`: в ссылке документов клона — SPEC/PLAN/REVIEW со
        статусами из `random`, на диске `config.TASKS/<id>/` — те же файлы
        со статусом-приманкой `draft`. Возвращает (id, {имя: статус})."""
        tid = self.new_id()
        self.add_task(tid, target)
        pool = ["ready", "approved", "changes_requested", "escalate"]
        statuses = {name: self.rng.choice(pool) for name in self.NAMES}
        files = {f"tasks/{tid}/{name}": frontmatter_doc(tid, name[:-3].lower(),
                                                        status)
                 for name, status in statuses.items()}
        repo = self.clone_of(target)
        sha = commit_files(repo, files, f"{tid}: документы", VERDICT_TS)
        _git(repo, "update-ref", f"refs/artifacts/{tid}", sha)
        disk = config.TASKS / tid
        disk.mkdir(parents=True, exist_ok=True)
        for name in self.NAMES:
            (disk / name).write_text(
                frontmatter_doc(tid, name[:-3].lower(), "draft"),
                encoding="utf-8")
        return tid, statuses

    def _assert_show(self, tid: str, statuses: dict) -> None:
        out = capture(catalog.cmd_show, tid)
        for name, status in statuses.items():
            self.assertIn(f"{name}: status={status}", out,
                          self.why(f"{name}: статус не из ссылки документов: "
                                   f"{out!r}"))
        self.assertNotIn("status=draft", out,
                         self.why(f"напечатан статус с диска config.TASKS: "
                                  f"{out!r}"))

    def test_ac6_show_artel_task_reads_docs_ref(self):
        """`show` задачи артели печатает статусы из её ссылки документов.

        Клон артели несёт `refs/artifacts/<id>` с SPEC/PLAN/REVIEW, статусы —
        из `random`; на диске `config.TASKS/<id>/` лежат те же файлы со
        `status: draft`. Вывод `show` несёт `<файл>: status=<статус ссылки>`
        для каждого и не несёт `status=draft`.

        Ловит мутацию: в `_artifact_frontmatter` оставлена развилка «артель —
        с диска `config.TASKS`» — в выводе `status=draft` вместо статусов
        ссылки.
        """
        tid, statuses = self._seed(config.DEFAULT_TARGET)
        self._assert_show(tid, statuses)

    def test_ac6_show_external_task_reads_docs_ref(self):
        """`show` задачи внешнего проекта печатает статусы из ссылки в клоне проекта.

        Клон проекта (`make_project_repo`) несёт `refs/artifacts/<id>` с
        SPEC/PLAN/REVIEW, статусы — из `random`; на диске `config.TASKS/<id>/`
        — приманка `status: draft`. Вывод `show` несёт статусы ссылки и не
        несёт `status=draft`.

        Ловит мутацию: общая ветка `_artifact_frontmatter` после удаления
        развилки читает диск `config.TASKS` для любого проекта (выбрана не та
        ветка) — в выводе `status=draft` вместо статусов ссылки.
        """
        target = self.project_name()
        make_project_repo(target)
        tid, statuses = self._seed(target)
        self._assert_show(tid, statuses)


class FetchAllCreatesCloneTest(_Sandbox):
    """AC-6: `docs --fetch-all` заводит клон внешнего проекта."""

    def test_ac6_fetch_all_creates_external_clone(self):
        """Клона внешнего проекта нет: `--fetch-all` заводит его из `targets.yaml` и подтягивает ссылки.

        `targets.yaml` несёт артель и внешний проект, `url` которого — локальный
        голый репозиторий с веткой базы и несколькими (число из `random`)
        ссылками `refs/artifacts/<id>`. Каталога клона
        `config.PROJECTS/<проект>/repo` до команды нет. После `docs
        --fetch-all` клон есть (`.git`), каждая ссылка в нём равна ссылке
        голого репозитория, а вывод несёт строку исхода fetch этого проекта
        (`<проект>: принесено …`), а не «пропущен».

        Ловит мутацию: в `_fetch_all` оставлено `ensure_clone` только для
        артели — проект «пропущен — репозиторий проекта задачи не найден»,
        каталога клона нет, ссылок локально нет.
        """
        target = self.project_name()
        bare = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, bare, ignore_errors=True)
        _git(bare, "init", "-q", "--bare")
        base = commit_files(bare, {"README": "проект\n"}, "init", DEVELOPER_TS)
        _git(bare, "update-ref", f"refs/heads/{config.MAIN_BRANCH}", base)
        _git(bare, "symbolic-ref", "HEAD", f"refs/heads/{config.MAIN_BRANCH}")
        placed = {}
        for _ in range(self.rng.randrange(1, 4)):
            tid = self.new_id()
            self.add_task(tid, target)
            sha = commit_files(bare, {f"tasks/{tid}/SPEC.md":
                                      frontmatter_doc(tid, "spec", "ready")},
                               f"{tid}: документы", VERDICT_TS)
            _git(bare, "update-ref", f"refs/artifacts/{tid}", sha)
            placed[tid] = sha
        config.TARGETS.write_text(
            targets_yaml({config.DEFAULT_TARGET: "file:///nonexistent/artel",
                          target: str(bare)}), encoding="utf-8")
        clone = self.clone_of(target)
        self.assertFalse(clone.exists(), self.why("предусловие: клона нет"))

        code = 0
        try:
            out = capture(docs_fetch.cmd_docs, ["--fetch-all"])
        except SystemExit as exc:
            code, out = exc.code, ""

        self.assertTrue((clone / ".git").exists(),
                        self.why(f"клон {clone} не заведён (код {code}): {out!r}"))
        for tid, sha in placed.items():
            got = subprocess.run(
                ["git", "-C", str(clone), "for-each-ref",
                 "--format=%(objectname)", f"refs/artifacts/{tid}"],
                capture_output=True, text=True).stdout.strip()
            self.assertEqual(got, sha,
                             self.why(f"{tid}: ссылка не подтянута в клон"))
        lines = [ln for ln in out.splitlines() if ln.startswith(f"{target}:")]
        self.assertTrue(lines, self.why(f"нет строки проекта {target}: {out!r}"))
        self.assertTrue(all("пропущен" not in ln and "отказ" not in ln
                            for ln in lines),
                        self.why(f"проект не прошёл fetch: {lines!r}"))
        self.assertIn("принесено", " ".join(lines),
                      self.why(f"нет исхода fetch проекта: {lines!r}"))


class ReviewReworkGateTest(_Sandbox):
    """AC-8: гейт отработки замечаний ревью — для задачи любого проекта."""

    def _seed(self, target: str) -> tuple[str, object]:
        """В клоне проекта `target`: кодовая ветка задачи с коммитом
        разработчика (`DEVELOPER_TS`) поверх базы и ссылка документов, где
        REVIEW.md `changes_requested` закоммичен автокоммитом шага
        reviewer позже (`VERDICT_TS`). Журнала задачи нет."""
        tid = self.new_id()
        branch = self.add_task(tid, target)
        repo = self.clone_of(target)
        base = _git(repo, "rev-parse", config.MAIN_BRANCH)
        code = commit_files(repo, {"src.py": f"x = {self.rng.randrange(99)}\n"},
                            f"{tid}: код фикса", DEVELOPER_TS, parent=base)
        _git(repo, "update-ref", f"refs/heads/{branch}", code)
        iteration = self.rng.randrange(1, 4)
        docs = commit_files(
            repo, {f"tasks/{tid}/REVIEW.md": frontmatter_doc(
                tid, "review", "changes_requested",
                extra=f"iteration: {iteration}\n")},
            f"{tid}: артефакты шага reviewer (автокоммит оркестратора)",
            VERDICT_TS)
        _git(repo, "update-ref", f"refs/artifacts/{tid}", docs)
        return tid, store.get_task(store.db(), tid)

    def _assert_refused(self, tid: str, t) -> None:
        refusal = review._review_rework_gate(store.db(), tid, t,
                                             f"refs/artifacts/{tid}")
        self.assertIsNotNone(refusal,
                             self.why("гейт пропустил неотработанное ревью"))
        self.assertEqual(refusal.action, review._REWORK_REFUSAL_ACTION,
                         self.why(f"отказ не того гейта: {refusal!r}"))
        self.assertIn(DEVELOPER_TS[:10], refusal.detail,
                      self.why(f"отказ не называет коммит разработчика из "
                               f"клона проекта: {refusal.detail!r}"))

    def test_ac8_external_task_refused(self):
        """Задача внешнего проекта без нового коммита разработчика после вердикта получает отказ.

        Клон проекта (`make_project_repo`): кодовая ветка задачи с коммитом
        разработчика 01.08, ссылка документов с REVIEW.md
        `status: changes_requested`, закоммиченным автокоммитом reviewer
        02.08. `_review_rework_gate` возвращает отказ «замечания ревью не
        отработаны», и его пояснение называет дату коммита разработчика из
        клона проекта.

        Ловит мутацию: в `_review_rework_gate` оставлен ранний выход для
        не-артели (`task_target != DEFAULT_TARGET -> None`) — гейт
        возвращает `None`, задача уходит дальше без отработки замечаний.
        """
        target = self.project_name()
        make_project_repo(target)
        tid, t = self._seed(target)
        self._assert_refused(tid, t)

    def test_ac8_artel_task_refused(self):
        """Задача артели в том же положении получает тот же отказ.

        Клон артели (репозиторий песочницы): кодовая ветка с коммитом
        разработчика 01.08, ссылка документов с REVIEW.md
        `changes_requested` от 02.08. `_review_rework_gate` отказывает с тем
        же действием и датой коммита разработчика в пояснении.

        Ловит мутацию: при удалении развилки общая ветка гейта читает
        REVIEW.md или коммиты не из клона проекта задачи (например, из
        `config.ROOT` или кодовой ветки вместо ссылки документов) — REVIEW.md
        не найден, гейт пропускает задачу.
        """
        tid, t = self._seed(config.DEFAULT_TARGET)
        self._assert_refused(tid, t)


if __name__ == "__main__":
    unittest.main(argv=sys.argv)
