"""`amend-tests` отправляет голову кодовой ветки в origin; `verifying` сам
отправляет голову, которой GitHub не нашёл (HTTP 422), вместо ожидания до
потолка.

Группа: долгоживущий

Красен до реализации: `amend-tests` коммитит правку долгоживущего файла в кодовую ветку, но в origin её не отправляет, а `verifying` на исходе 422 только ждёт, и подсказка исхода — ручной `git push -u origin` — красны AC-1, AC-2, AC-4 (обе стороны), AC-6, AC-7, AC-9; AC-3, AC-5 и AC-8 держат то, что код уже делает (нет обращения к origin) и зелёны.

Песочница — настоящий git: пульт и клон артели — `self.root`, голый
репозиторий в роли origin (`add_synced_origin`). Задача артели заводится
`catalog.cmd_new`; её кодовая ветка несёт долгоживущий файл фикстуры
(`tests/test_<id>_alpha.py` — имя считается от id задачи песочницы) и
опубликована в origin; ссылка документов `refs/artifacts/<id>` несёт SPEC
с одним критерием, зелёную планку и перечень сумм долгоживущих файлов,
`tests_locked_sha` стоит на её голове, фиксация заведена. Черновик запроса
на слияние помечен заведённым — фордж не трогается.

Отказ отправки — хук `pre-receive` голого origin, который отвергает
обновление ветки задачи (ссылки документов и main он пропускает) и пишет в
stderr случайную метку: метка в тексте отказа команды доказывает, что
причина пришла от узла отправки. Ответ GitHub подменяется на `ci.gh`:
`ci.verifying_status` разбирает его сама, так что исход 422 и прочие
исходы получаются настоящим кодом разбора. Узел
`github_adapter.ensure_head_in_origin` там, где важен факт обращения,
обёрнут шпионом поверх настоящей функции.

Содержимое правок, метка отказа, порядок исходов CI и имена веток — из
`random`; зерно печатается и входит в текст каждого провала.
"""
import contextlib
import hashlib
import io
import json
import os
import random
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from orchestrator import (amend, catalog, ci, config, fsm, github_adapter,
                          projects, store, workspace)
from scripts import guard
from tests.sandbox import GitignoreCommittedRealGitSandbox, RealGitSandbox

DOCS_REF_PREFIX = "refs/artifacts/"
PLANK_NAME = "test_plank.py"
NOTE_PATH = "docs/note.md"

SPEC_TEMPLATE = """---
task: TASK_ID
type: spec
author_role: analyst
status: ready
schema_version: 5
---

# SPEC: <название задачи>

## Контекст

## Требования

## Критерии приёмки

AC-1. Фикстурный критерий песочницы.

## Не входит
"""

PLANK_TEXT = '''"""Фикстура планки песочницы.

Группа: разовый
Зелёный с рождения: фикстура песочницы.
"""
import unittest


class FixturePlankTest(unittest.TestCase):

    def test_ac1_fixture_criterion(self):
        """Фикстурный метод."""
        self.assertEqual(1 + 1, 2)
'''

LONG_LIVED_TEXT = '''"""Фикстура долгоживущего файла песочницы.

Группа: долгоживущий
"""
import random
import unittest


class FixtureLongLivedTest(unittest.TestCase):

    def test_ac1_long_fixture(self):
        """Фикстурный метод.

        Ловит мутацию: фикстура песочницы — сумма перестаёт совпадать.
        """
        seed = random.randrange(1 << 30)
        self.assertEqual(1 + 1, 2, f"зерно: {seed}")
'''

ARTEL_TARGETS = f"""targets:
  {config.DEFAULT_TARGET}:
    forge: github
    url: file:///nonexistent/{config.DEFAULT_TARGET}
    base: {config.MAIN_BRANCH}
    token_slot: {config.DEFAULT_TARGET}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
      report: junit-xml
      install: []
"""

TITLES = ("Отправка головы", "Правка долгоживущих", "Опрос CI")

PUSH_OK_ACTION = "push (голова не в origin)"
PUSH_FAILED_ACTION = "push FAILED (голова не в origin)"
AMEND_ABORTED_ACTION = "amend-tests прерван"

REJECT_HOOK = """#!/bin/sh
while read old new ref; do
  if [ "$ref" = "refs/heads/BRANCH" ]; then
    echo "TOKEN" >&2
    exit 1
  fi
done
exit 0
"""


def completed(args, returncode: int, stdout: str = "", stderr: str = ""):
    return subprocess.CompletedProcess(list(args), returncode, stdout, stderr)


def fake_gh_for(kind: str):
    """Подмена `ci.gh`: ответ GitHub для исхода `kind` — «422», «green»,
    «running», «none», «red». Прочие вызовы `gh` (черновик и т.п.) —
    ненулевой код, как у отсутствующего CLI."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    runs = {
        "green": [{"name": "tests", "status": "completed",
                   "conclusion": "success"}],
        "running": [{"name": "tests", "status": "in_progress",
                     "conclusion": None, "started_at": now}],
        "none": [],
        "red": [{"name": "tests", "status": "completed",
                 "conclusion": "failure"}],
    }

    def fake(*args, timeout=None, repo=None):
        if args and args[0] == "api":
            if kind == "422":
                return completed(args, 1, "", "gh: No commit found for SHA: "
                                 "deadbeef (HTTP 422)")
            payload = runs[kind]
            return completed(args, 0, json.dumps(
                {"total_count": len(payload), "check_runs": payload}))
        if args[:2] == ("run", "list"):
            return completed(args, 0, "[]")
        return completed(args, 1, "", "gh в песочнице не заведён")

    return fake


class OriginPushSandbox(GitignoreCommittedRealGitSandbox):
    """Задача артели с залоченной планкой, кодовой веткой в рабочей копии и
    голым origin; `WITH_MANIFEST = False` — лок без перечня долгоживущих
    файлов (режим `amend-tests` только для планки)."""

    WITH_MANIFEST = True

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.origin = self.add_synced_origin()

        config.TARGETS.write_text(ARTEL_TARGETS, encoding="utf-8")
        self.run_cmd(projects.cmd_target_init, config.DEFAULT_TARGET)
        self.run_cmd(catalog.cmd_init)
        self.use_role_map()
        templates = self.root / ".artel" / "templates-fixture"
        templates.mkdir(parents=True, exist_ok=True)
        (templates / "SPEC.md").write_text(SPEC_TEMPLATE, encoding="utf-8")
        for patcher in (
                mock.patch.object(config, "TEMPLATES", templates),
                mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""}),
                mock.patch("orchestrator.doctor.preflight_checks",
                           lambda *args, **kwargs: [])):
            patcher.start()
            self.addCleanup(patcher.stop)

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.task_id = catalog.cmd_new(self.rng.choice(TITLES),
                                           target=config.DEFAULT_TARGET)
        self.branch = store.get_task(store.db(), self.task_id)["branch"]
        if not self.git("branch", "--list", self.branch).strip():
            self.git("branch", self.branch, config.MAIN_BRANCH)
        self.wt, error = workspace.ensure(self.task_id, self.branch)
        self.assertIsNone(error, self.note(f"рабочая копия не заведена: {error}"))
        self.own = f"{guard.long_lived_path_prefix(self.task_id)}alpha.py"
        self.wt_commit({self.own: LONG_LIVED_TEXT}, "долгоживущий файл")
        self.git("push", "-q", "origin", f"{self.branch}:{self.branch}")

        docs = {"SPEC.md": SPEC_TEMPLATE.replace("TASK_ID", self.task_id),
                "acceptance_tests/" + PLANK_NAME: PLANK_TEXT}
        if self.WITH_MANIFEST:
            digest = hashlib.sha256((self.wt / self.own).read_bytes()).hexdigest()
            docs["acceptance_tests/" + guard.LONG_LIVED_MANIFEST_NAME] = (
                guard.render_long_lived_manifest({self.own: digest}))
        self.commit_docs(docs, "планка")
        store.update_task(store.db(), self.task_id, tests_locked_sha=self.docs_head(),
                          state="in_dev", draft_mr_created=1)
        store.record_fixation(store.db(), self.task_id)

    # --- обвязка -------------------------------------------------------

    def note(self, text: str) -> str:
        return f"{text} (зерно {self.seed})"

    def run_cmd(self, fn, *args, **kwargs) -> tuple[str, bool]:
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

    def locked(self) -> str:
        return self.row()["tests_locked_sha"]

    def docs_head(self) -> str:
        return self.git("for-each-ref", "--format=%(objectname)",
                        DOCS_REF_PREFIX + self.task_id).strip()

    def local_head(self) -> str:
        return self.git("rev-parse", f"refs/heads/{self.branch}").strip()

    def origin_head(self) -> str:
        out = self.git("ls-remote", str(self.origin), f"refs/heads/{self.branch}")
        return out.split()[0] if out.strip() else ""

    def actions(self) -> list[str]:
        return [s["action"] for s in store.task_steps(store.db(), self.task_id)]

    def wt_commit(self, files: dict, message: str) -> None:
        for rel, text in files.items():
            path = self.wt / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.git("-C", str(self.wt), "add", "--", *files)
        self.git("-C", str(self.wt), "commit", "-q", "-m", message)

    def commit_docs(self, files: dict, message: str) -> None:
        """Коммит `files` (путь внутри каталога задачи -> текст) в ссылку
        документов: отдельная рабочая копия на её голове и `update-ref`."""
        old = self.docs_head()
        self.assertTrue(old, self.note("ссылки документов нет"))
        scratch = Path(self.root / ".artel" / f"docs-copy-{self.rng.randrange(1 << 30)}")
        self.git("worktree", "add", "-q", "--detach", str(scratch), old)
        try:
            for rel, text in files.items():
                path = scratch / "tasks" / self.task_id / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            self.git("-C", str(scratch), "add", "-A")
            self.git("-C", str(scratch), "commit", "-q", "-m", message)
            new = self.git("-C", str(scratch), "rev-parse", "HEAD").strip()
        finally:
            self.git("worktree", "remove", "--force", str(scratch))
        self.git("update-ref", DOCS_REF_PREFIX + self.task_id, new, old)

    def edit_long_lived(self) -> None:
        """Правка Оператора долгоживущего файла в рабочей копии."""
        (self.wt / self.own).write_text(
            LONG_LIVED_TEXT + f"# правка Оператора {self.rng.randrange(1 << 30)}\n",
            encoding="utf-8")

    def edit_plank(self) -> None:
        """Правка Оператора планки в каталоге задачи рабочей копии."""
        plank = self.wt / "tasks" / self.task_id / "acceptance_tests" / PLANK_NAME
        plank.parent.mkdir(parents=True, exist_ok=True)
        plank.write_text(PLANK_TEXT + f"\n# правка планки {self.rng.randrange(1 << 30)}\n",
                         encoding="utf-8")

    def reject_branch_push(self) -> str:
        """Origin отвергает обновление ветки задачи; возвращает метку,
        которую хук пишет в stderr."""
        token = f"origin-отказ-{self.rng.randrange(1 << 30)}"
        hook = self.origin / "hooks" / "pre-receive"
        hook.write_text(REJECT_HOOK.replace("BRANCH", self.branch)
                        .replace("TOKEN", token), encoding="utf-8")
        hook.chmod(0o755)
        return token

    def allow_branch_push(self) -> None:
        (self.origin / "hooks" / "pre-receive").unlink()

    def amend(self, **kwargs) -> tuple[str, bool]:
        return self.run_cmd(amend.cmd_amend_tests, self.task_id,
                            f"правка {self.seed}", **kwargs)

    @contextlib.contextmanager
    def push_spy(self):
        with mock.patch.object(github_adapter, "ensure_head_in_origin",
                               wraps=github_adapter.ensure_head_in_origin) as spy:
            yield spy

    def advance(self, kind: str) -> str:
        with mock.patch.object(ci, "gh", fake_gh_for(kind)):
            out, _refused = self.run_cmd(fsm.cmd_advance, self.task_id)
        return out


class AmendLongLivedPushTest(OriginPushSandbox):

    def test_ac1_amend_long_lived_pushes_code_head_in_dev_and_verifying(self):
        """Правка долгоживущего файла в `in_dev`, затем в `verifying` — после каждой голова ветки в origin равна локальной.

        Сценарий: задача в `in_dev`; Оператор правит долгоживущий файл в
        рабочей копии, `amend-tests` завершается без отказа, лок сдвинут, а
        sha ветки задачи в origin равен её локальной голове (новый коммит
        правки). Затем задача переводится в `verifying`, Оператор правит
        файл ещё раз, и снова: успех, новая локальная голова и она же в
        origin.

        Ловит мутацию: отправка в origin не добавлена (или стоит только в
        одной ветке состояния) — после команды origin остаётся на прежнем
        коммите, локальная голова впереди; отправка идёт до коммита правки
        — в origin уезжает голова без коммита правки.
        """
        for state in ("in_dev", "verifying"):
            with self.subTest(state=state):
                store.update_task(store.db(), self.task_id, state=state)
                lock_before, head_before = self.locked(), self.local_head()
                self.edit_long_lived()

                out, refused = self.amend()

                self.assertFalse(refused, self.note(f"[{state}] отказ:\n{out}"))
                self.assertNotEqual(self.locked(), lock_before, self.note(
                    f"[{state}] предпосылка: лок не сдвинут:\n{out}"))
                self.assertNotEqual(self.local_head(), head_before, self.note(
                    f"[{state}] предпосылка: правка не закоммичена в кодовую ветку"))
                self.assertEqual(self.origin_head(), self.local_head(), self.note(
                    f"[{state}] голова ветки задачи в origin не равна локальной "
                    f"после amend-tests:\n{out}"))

    def test_ac2_failed_push_is_named_refusal_without_relock(self):
        """Origin отверг отправку — ненулевой код, лок и ссылка документов прежние, журнал «amend-tests прерван», сообщение с причиной и путём восстановления.

        Сценарий: хук origin отвергает обновление ветки задачи со
        случайной меткой в stderr. Оператор правит долгоживущий файл,
        `amend-tests` завершается ненулевым кодом; `tests_locked_sha` и
        голова ссылки документов прежние; в журнале задачи появилась
        запись «amend-tests прерван»; текст отказа несёт метку хука
        (причину, которую вернул узел отправки) и
        `amend-tests <id> --from-branch`.

        Ловит мутацию: отказ узла отправки проглочен — команда идёт дальше,
        пишет перечень в ссылку документов и сдвигает лок; отправка стоит
        после записи (б) — ссылка документов сдвинута при отказе; причина
        отказа узла не передана в текст сообщения; отказ без записи
        «amend-tests прерван» в журнале.
        """
        token = self.reject_branch_push()
        lock_before, docs_before = self.locked(), self.docs_head()
        aborted_before = self.actions().count(AMEND_ABORTED_ACTION)
        self.edit_long_lived()

        out, refused = self.amend()

        self.assertTrue(refused, self.note(f"отказ отправки не остановил команду:\n{out}"))
        self.assertEqual(self.locked(), lock_before, self.note(
            f"tests_locked_sha сдвинут при отказе отправки:\n{out}"))
        self.assertEqual(self.docs_head(), docs_before, self.note(
            f"голова ссылки документов сдвинута при отказе отправки:\n{out}"))
        self.assertEqual(self.actions().count(AMEND_ABORTED_ACTION),
                         aborted_before + 1, self.note(
            f"нет записи «{AMEND_ABORTED_ACTION}» в журнале: {self.actions()}"))
        self.assertIn(token, out, self.note(
            f"причина отказа узла отправки не названа:\n{out}"))
        self.assertIn(f"amend-tests {self.task_id} --from-branch", out, self.note(
            f"путь восстановления не назван:\n{out}"))

    def test_ac3_canary_amend_does_not_touch_origin(self):
        """Канареечная задача: правка долгоживущего файла проходит без обращения к origin.

        Сценарий: задача помечена канареечной; Оператор правит
        долгоживущий файл, `amend-tests` завершается без отказа, лок
        сдвинут, правка закоммичена в локальную ветку. Узел
        `ensure_head_in_origin` не вызывался ни разу, ветка в origin — на
        прежнем коммите.

        Ловит мутацию: исключение канарейки не добавлено (или проверяет не
        тот признак) — узел отправки вызывается, и ветка в origin
        сдвигается на голову с правкой.
        """
        store.update_task(store.db(), self.task_id, is_canary=1)
        origin_before, lock_before = self.origin_head(), self.locked()
        self.edit_long_lived()

        with self.push_spy() as spy:
            out, refused = self.amend()

        self.assertFalse(refused, self.note(f"отказ канареечной задаче:\n{out}"))
        self.assertNotEqual(self.locked(), lock_before, self.note(
            f"предпосылка: лок не сдвинут:\n{out}"))
        self.assertEqual(spy.call_count, 0, self.note(
            f"узел отправки вызван для канарейки: {spy.call_args_list}"))
        self.assertEqual(self.origin_head(), origin_before, self.note(
            "ветка канареечной задачи в origin изменилась"))

    def test_ac4_from_branch_pushes_unpushed_long_lived_divergence(self):
        """`--from-branch` с незапушенным коммитом правки долгоживущего файла — голова в origin равна локальной, лок сдвинут.

        Сценарий: в кодовую ветку закоммичена (не отправлена) правка
        долгоживущего файла; `amend-tests --from-branch` завершается без
        отказа, `tests_locked_sha` сдвинут, sha ветки в origin равен
        локальной голове.

        Ловит мутацию: `--from-branch` при расхождении долгоживущих файлов
        не проверяет голову в origin — лок сдвинут, а origin остаётся на
        коммите без правки.
        """
        self.wt_commit({self.own: LONG_LIVED_TEXT
                        + f"# закоммиченная правка {self.seed}\n"}, "правка")
        self.assertNotEqual(self.origin_head(), self.local_head(),
                            self.note("предпосылка: голова уже в origin"))
        lock_before = self.locked()

        out, refused = self.amend(from_branch=True)

        self.assertFalse(refused, self.note(f"отказ --from-branch:\n{out}"))
        self.assertNotEqual(self.locked(), lock_before, self.note(
            f"tests_locked_sha не сдвинут:\n{out}"))
        self.assertEqual(self.origin_head(), self.local_head(), self.note(
            f"голова ветки в origin не равна локальной после --from-branch:\n{out}"))

    def test_ac4_from_branch_failed_push_keeps_lock_and_docs(self):
        """`--from-branch`, отправка отвергнута — ненулевой код, лок и ссылка документов прежние, причина и путь восстановления в сообщении.

        Сценарий: в кодовую ветку закоммичена (не отправлена) правка
        долгоживущего файла, хук origin отвергает обновление ветки со
        случайной меткой; `amend-tests --from-branch` завершается
        ненулевым кодом, `tests_locked_sha` и голова ссылки документов
        прежние, текст отказа несёт метку хука и
        `amend-tests <id> --from-branch`.

        Ловит мутацию: отказ отправки в `--from-branch` проглочен — лок
        сдвинут на коммит с пересчитанным перечнем; отправка идёт после
        коммита перечня в ссылку документов — ссылка сдвинута при отказе;
        причина узла не попала в сообщение.
        """
        self.wt_commit({self.own: LONG_LIVED_TEXT
                        + f"# закоммиченная правка {self.seed}\n"}, "правка")
        token = self.reject_branch_push()
        lock_before, docs_before = self.locked(), self.docs_head()

        out, refused = self.amend(from_branch=True)

        self.assertTrue(refused, self.note(f"отказ отправки не остановил команду:\n{out}"))
        self.assertEqual(self.locked(), lock_before, self.note(
            f"tests_locked_sha сдвинут при отказе отправки:\n{out}"))
        self.assertEqual(self.docs_head(), docs_before, self.note(
            f"голова ссылки документов сдвинута при отказе отправки:\n{out}"))
        self.assertIn(token, out, self.note(
            f"причина отказа узла отправки не названа:\n{out}"))
        self.assertIn(f"amend-tests {self.task_id} --from-branch", out, self.note(
            f"путь восстановления не назван:\n{out}"))

    def test_ac5_from_branch_plank_only_does_not_touch_origin(self):
        """`--from-branch` без расхождения долгоживущих файлов (правка только планки) не обращается к origin.

        Сценарий: кодовая ветка несёт незапушенный коммит вне долгоживущих
        файлов (локальная голова впереди origin), в ссылку документов
        закоммичена правка планки; `amend-tests --from-branch` завершается
        без отказа и сдвигает лок, узел `ensure_head_in_origin` не
        вызывался, ветка в origin — на прежнем коммите.

        Ловит мутацию: проверка головы в origin в `--from-branch` стоит без
        условия «есть расхождение долгоживущих файлов» — узел вызывается и
        отправляет незапушенный коммит в origin.
        """
        self.wt_commit({NOTE_PATH: f"заметка {self.seed}\n"}, "заметка")
        self.commit_docs({"acceptance_tests/" + PLANK_NAME:
                          PLANK_TEXT + f"\n# правка планки {self.seed}\n"},
                         "правка планки ролью")
        store.record_fixation(store.db(), self.task_id)
        origin_before, lock_before = self.origin_head(), self.locked()

        with self.push_spy() as spy:
            out, refused = self.amend(from_branch=True)

        self.assertFalse(refused, self.note(f"отказ --from-branch:\n{out}"))
        self.assertNotEqual(self.locked(), lock_before, self.note(
            f"предпосылка: лок не сдвинут:\n{out}"))
        self.assertEqual(spy.call_count, 0, self.note(
            f"узел отправки вызван без расхождения долгоживущих: "
            f"{spy.call_args_list}"))
        self.assertEqual(self.origin_head(), origin_before, self.note(
            "ветка в origin изменилась при правке только планки"))


class AmendWithoutManifestTest(OriginPushSandbox):

    WITH_MANIFEST = False

    def test_ac5_plank_only_mode_does_not_touch_origin_or_code_branch(self):
        """Режим без перечня лока: правка планки не обращается к origin и не коммитит в кодовую ветку.

        Сценарий: лок задачи без перечня долгоживущих файлов; кодовая ветка
        несёт незапушенный коммит (голова впереди origin); Оператор правит
        планку в каталоге задачи рабочей копии. `amend-tests` завершается
        без отказа и сдвигает лок; узел `ensure_head_in_origin` не
        вызывался, ветка в origin прежняя, локальная голова кодовой ветки
        прежняя.

        Ловит мутацию: отправка головы в origin добавлена в общий путь
        `amend-tests`, а не только в режим с перечнем — узел вызывается и
        отправляет незапушенный коммит; режим без перечня коммитит в
        кодовую ветку — её голова сдвигается.
        """
        self.wt_commit({NOTE_PATH: f"заметка {self.seed}\n"}, "заметка")
        origin_before, head_before = self.origin_head(), self.local_head()
        lock_before = self.locked()
        self.edit_plank()

        with self.push_spy() as spy:
            out, refused = self.amend()

        self.assertFalse(refused, self.note(f"отказ правке планки:\n{out}"))
        self.assertNotEqual(self.locked(), lock_before, self.note(
            f"предпосылка: лок не сдвинут:\n{out}"))
        self.assertEqual(spy.call_count, 0, self.note(
            f"узел отправки вызван в режиме без перечня: {spy.call_args_list}"))
        self.assertEqual(self.origin_head(), origin_before, self.note(
            "ветка в origin изменилась в режиме без перечня"))
        self.assertEqual(self.local_head(), head_before, self.note(
            "режим без перечня создал коммит в кодовой ветке"))


class VerifyingPushTest(OriginPushSandbox):
    """Задача в `verifying`; кодовая ветка несёт незапушенный коммит вне
    долгоживущих файлов — голова не в origin, перечень лока совпадает."""

    def setUp(self):
        super().setUp()
        self.wt_commit({NOTE_PATH: f"заметка {self.seed}\n"}, "заметка")
        self.enter_verifying()
        self.assertNotEqual(self.origin_head(), self.local_head(),
                            self.note("предпосылка: голова уже в origin"))

    def enter_verifying(self) -> None:
        """Вход в `verifying` переходом: отсчёт потолка — с этого момента."""
        store.set_state(store.db(), self.task_id, "verifying", "fsm",
                        expected_state=self.row()["state"], detail="песочница")

    def test_ac6_verifying_422_pushes_head_and_stays(self):
        """Исход 422 в `verifying`: один опрос отправляет голову, журнал «push (голова не в origin)», задача остаётся в `verifying`.

        Сценарий: GitHub отвечает на check-runs головы HTTP 422; один
        `advance` — после него sha ветки в origin равен локальной голове,
        в журнале задачи появилась запись «push (голова не в origin)»,
        состояние — `verifying` (не `escalated`).

        Ловит мутацию: обработчик `verifying` не реагирует на исход 422 —
        голова остаётся вне origin, записи об отправке нет; после
        отправки задача переводится в другое состояние вместо ожидания CI.
        """
        out = self.advance("422")

        self.assertEqual(self.origin_head(), self.local_head(), self.note(
            f"голова не отправлена в origin опросом verifying:\n{out}"))
        self.assertIn(PUSH_OK_ACTION, self.actions(), self.note(
            f"нет записи «{PUSH_OK_ACTION}»: {self.actions()}\n{out}"))
        self.assertEqual(self.row()["state"], "verifying", self.note(
            f"задача ушла из verifying:\n{out}"))

    def test_ac7_verifying_422_failed_push_stays_and_journals(self):
        """Исход 422, отправка отвергнута: каждый опрос пишет «push FAILED (голова не в origin)», задача остаётся в `verifying`.

        Сценарий: хук origin отвергает обновление ветки задачи; GitHub
        отвечает 422. Два опроса `advance` подряд: после каждого в журнале
        прибавляется запись «push FAILED (голова не в origin)», состояние —
        `verifying`, ветка в origin на прежнем коммите.

        Ловит мутацию: обработчик не зовёт узел отправки на исходе 422 —
        записи «push FAILED» нет; отказ отправки эскалирует задачу или
        переводит её из `verifying` до потолка.
        """
        self.reject_branch_push()
        origin_before = self.origin_head()
        for poll in (1, 2):
            failed_before = self.actions().count(PUSH_FAILED_ACTION)

            out = self.advance("422")

            self.assertEqual(self.actions().count(PUSH_FAILED_ACTION),
                             failed_before + 1, self.note(
                f"опрос {poll}: нет новой записи «{PUSH_FAILED_ACTION}»: "
                f"{self.actions()}\n{out}"))
            self.assertEqual(self.row()["state"], "verifying", self.note(
                f"опрос {poll}: задача ушла из verifying:\n{out}"))
            self.assertEqual(self.origin_head(), origin_before, self.note(
                f"опрос {poll}: ветка в origin изменилась при отказе"))

    def test_ac8_other_outcomes_do_not_call_push_node(self):
        """Исходы «зелёный», «проверки идут», «проверок нет» без 422 и «красный» — узел отправки не вызывается, переходы и журнал прежние.

        Сценарий: для каждого исхода (порядок — случайный) задача заново в
        `verifying` с головой вне origin, GitHub отвечает соответствующим
        набором check-runs; один `advance`. Узел `ensure_head_in_origin` не
        вызывался, ветка в origin прежняя, записей об отправке нет; в
        журнале — запись статуса CI с текстом исхода; зелёный переводит в
        `review`, остальные оставляют в `verifying`.

        Ловит мутацию: обработчик зовёт узел отправки на любом исходе (или
        на всём «проверок нет», не только на 422) — узел вызван, голова
        уезжает в origin, в журнале запись «push (голова не в origin)».
        """
        expected = {"green": ("review", "зелёный"),
                    "running": ("verifying", "ещё идёт"),
                    "none": ("verifying", "проверок нет вовсе"),
                    "red": ("verifying", "не зелёный")}
        kinds = list(expected)
        self.rng.shuffle(kinds)
        origin_before = self.origin_head()
        for kind in kinds:
            with self.subTest(outcome=kind):
                self.enter_verifying()
                steps_before = len(store.task_steps(store.db(), self.task_id))

                with self.push_spy() as spy:
                    out = self.advance(kind)

                state, needle = expected[kind]
                new = store.task_steps(store.db(), self.task_id)[steps_before:]
                self.assertEqual(spy.call_count, 0, self.note(
                    f"[{kind}] узел отправки вызван: {spy.call_args_list}"))
                self.assertEqual(self.origin_head(), origin_before, self.note(
                    f"[{kind}] ветка в origin изменилась"))
                self.assertFalse(
                    [s["action"] for s in new if "push" in s["action"]],
                    self.note(f"[{kind}] запись об отправке в журнале: "
                              f"{[s['action'] for s in new]}"))
                self.assertTrue(
                    [s for s in new if s["action"] == fsm.VERIFYING_STATUS_ACTION
                     and needle in (s["detail"] or "")],
                    self.note(f"[{kind}] нет записи статуса CI с «{needle}»: "
                              f"{[(s['action'], s['detail']) for s in new]}\n{out}"))
                self.assertEqual(self.row()["state"], state, self.note(
                    f"[{kind}] переход не прежний:\n{out}"))


class VerifyingNoteTest(RealGitSandbox):

    def test_ac9_422_note_describes_pult_push_without_manual_hint(self):
        """Текст исхода «голова ветки не в origin» описывает отправку пультом при опросе `verifying`, без «git push -u origin».

        Сценарий: в репозитории заводятся ветки со случайными именами,
        GitHub отвечает на check-runs их головы HTTP 422;
        `ci.verifying_status` для каждой — текст исхода не содержит
        «git push -u origin», содержит «голова», «origin», «push», имя
        ветки, «пульт» и «verifying».

        Ловит мутацию: подсказка ручного `git push -u origin <ветка>`
        оставлена в тексте; новый текст потерял имя ветки или слово
        «push»; текст не говорит, что голову отправит пульт при опросе
        `verifying`.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        for n in range(3):
            branch = f"task/{rng.randrange(1 << 40):x}-vetka-{n}"
            self.git("branch", branch, config.MAIN_BRANCH)

            with mock.patch.object(ci, "gh", fake_gh_for("422")):
                _outcome, note = ci.verifying_status(branch, repo=self.root)

            hint = f"{note!r} (ветка {branch}, зерно {seed})"
            self.assertIn("голова", note, hint)
            self.assertIn("origin", note, hint)
            self.assertNotIn("git push -u origin", note, hint)
            self.assertIn("push", note, hint)
            self.assertIn(branch, note, hint)
            self.assertIn("пульт", note.lower(), hint)
            self.assertIn("verifying", note, hint)
