"""Клон проекта получает ссылки документов задач при заведении; сверка
`artifact-ref-sync` не шумит на закрытых задачах, чья ссылка есть только в
`origin` и совпадает там с коммитом закрытия.

Группа: долгоживущий

Песочница — настоящий git (`tests.sandbox.RealGitSandbox`). Для
`workspace.ensure_clone` (AC-1…AC-3): главная копия пульта, bare `origin`
рядом с ней и запись артели в `targets.yaml`, чей `url` — этот `origin`;
клона артели до вызова нет (`ARTEL_CLONE_IS_ROOT = False`). Ссылки
документов `refs/artifacts/<id>` в `origin` — коммиты, которых нет в
истории `main`. Неудачу fetch ссылок изображает подставной `git` в начале
`PATH`: он отказывает только `fetch`, называющему `refs/artifacts`, прочие
команды передаёт настоящему git.

Для `doctor.check_artifact_ref_sync` (AC-4, AC-5): клон артели — сам
репозиторий песочницы, `origin` — bare рядом; задачи закрываются настоящим
`snapshot.commit_closing` (коммит закрытия отправляется в `origin`), затем
сценарий снимает локальную ссылку или сдвигает ссылку в `origin`.

Идентификаторы задач, число задач каждого вида и вид расхождения берутся
случайно; зерно печатается и входит в текст провала.

Красен до реализации: `ensure_clone` заводит клон голым `git clone`,
который `refs/artifacts/*` не приносит (AC-1), и неудачи fetch не
печатает — его нет (AC-3); `check_artifact_ref_sync` выдаёт `warn` «голова
(нет локально)» на каждую закрытую задачу без локальной ссылки и строки со
сводкой и подсказкой `docs --fetch-all` не несёт (AC-4, AC-5). AC-2 зелен
с рождения: существующий каталог клона `ensure_clone` не трогает.
"""
import io
import os
import random
import re
import shutil
import stat
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import config, doctor, snapshot, store, workspace
from tests.sandbox import (_PROJECT_TARGET_ENTRY, OriginRealGitSandbox,
                           RealGitSandbox, capture)

ID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
FETCH_ALL_HINT = "docs --fetch-all"


def random_task_id(rng: random.Random) -> str:
    return "01" + "".join(rng.choice(ID_ALPHABET) for _ in range(24))


def docs_ref(task_id: str) -> str:
    return f"refs/artifacts/{task_id}"


class SeededMixin:
    """Зерно случайных входов: печатается и входит в текст провала."""

    def seed_rng(self) -> None:
        self.seed = random.randrange(2 ** 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def msg(self, text: str) -> str:
        return f"{text} (зерно: {self.seed})"


class CloneRefsSandbox(SeededMixin, RealGitSandbox):
    """Главная копия, bare `origin` с её `main`, запись артели в
    `targets.yaml` на этот `origin`; клона артели ещё нет."""

    ARTEL_CLONE_IS_ROOT = False

    def setUp(self):
        super().setUp()
        self.seed_rng()
        self.origin = self.root.parent / f"{self.root.name}-origin.git"
        self.git("clone", "-q", "--bare", str(self.root), str(self.origin))
        self.addCleanup(shutil.rmtree, self.origin, True)
        config.TARGETS.write_text(
            "targets:\n" + _PROJECT_TARGET_ENTRY.format(
                name=config.DEFAULT_TARGET, base=config.MAIN_BRANCH).replace(
                f"file:///nonexistent/{config.DEFAULT_TARGET}",
                str(self.origin)),
            encoding="utf-8")
        self.clone = workspace.repo(config.DEFAULT_TARGET)
        self.assertFalse(self.clone.exists(), "предусловие: клона ещё нет")

    def new_commit(self, parent: str = "HEAD", repo: Path | None = None) -> str:
        """Коммит вне истории `main` (ссылкой ветки не удерживается)."""
        where = ("-C", str(repo or self.root), "-c", "user.name=t",
                 "-c", "user.email=t@example.invalid")
        tree = self.git(*where, "rev-parse", f"{parent}^{{tree}}").strip()
        note = f"документы {self.rng.randrange(10 ** 9)}"
        return self.git(*where, "commit-tree", tree, "-p", parent,
                        "-m", note).strip()

    def push_origin_ref(self, task_id: str, sha: str) -> None:
        self.git("push", "-q", "--force", str(self.origin),
                 f"{sha}:{docs_ref(task_id)}")

    def refs(self, repo: Path) -> dict:
        out = self.git("-C", str(repo), "for-each-ref",
                       "--format=%(refname) %(objectname)", "refs/artifacts/")
        return dict(line.split(" ", 1) for line in out.splitlines() if line)

    def seed_origin_refs(self, count: int) -> list:
        ids = [random_task_id(self.rng) for _ in range(count)]
        for task_id in ids:
            self.push_origin_ref(task_id, self.new_commit())
        return ids


class EnsureCloneFetchesDocsRefsTest(CloneRefsSandbox):

    def test_ac1_new_clone_carries_origin_docs_refs(self):
        """Свежезаведённый клон несёт все `refs/artifacts/<id>` origin с теми же sha.

        Сценарий: в `origin` от двух до пяти ссылок документов задач со
        случайными id, каждая — на свой коммит вне `main`; каталога клона
        нет. `ensure_clone` возвращается без причины отказа, и набор
        локальных `refs/artifacts/*` клона совпадает с набором в `origin`
        по именам и sha.

        Ловит мутацию: заведение клона остаётся голым `git clone` без
        fetch `refs/artifacts/*` (или fetch идёт до `git clone`, в
        несуществующий каталог) — в клоне ссылок документов нет; fetch
        приносит только одну ссылку вместо всех — набор короче, чем в
        origin.
        """
        ids = self.seed_origin_refs(self.rng.randint(2, 5))
        expected = self.refs(self.origin)
        self.assertEqual(len(expected), len(ids), self.msg("предусловие"))

        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            clone, error = workspace.ensure_clone(config.DEFAULT_TARGET)

        self.assertIsNone(error, self.msg(f"ensure_clone отказал: {error}"))
        self.assertEqual(clone, self.clone)
        self.assertEqual(self.refs(clone), expected, self.msg(
            "локальные refs/artifacts/* клона не совпали с origin"))


class EnsureCloneKeepsExistingCloneTest(CloneRefsSandbox):

    def test_ac2_existing_clone_refs_untouched(self):
        """Повторный `ensure_clone` при существующем клоне не трогает его `refs/artifacts/*`.

        Сценарий: клон уже заведён (`git clone` сценария). В нём три вида
        ссылок документов: ушедшая вперёд origin (локальный коммит поверх
        головы origin), отставшая от origin (origin сдвинут вперёд после
        клонирования) и совпадающая с origin; ещё одна ссылка есть только
        в origin. `ensure_clone` возвращается без причины отказа, а
        локальные `refs/artifacts/*` клона те же, что до вызова: ушедшая
        вперёд не перезаписана, отставшая не продвинута, новая не
        появилась.

        Ловит мутацию: fetch ссылок документов вынесен до проверки
        «каталог клона уже есть» (выполняется при каждом вызове) —
        отставшая ссылка продвигается до origin и в клоне появляется
        ссылка, которой там не было; fetch с принудительной перезаписью —
        вдобавок теряется ушедшая вперёд ссылка.
        """
        ahead, behind, same, only_origin = (random_task_id(self.rng)
                                            for _ in range(4))
        for task_id in (ahead, behind, same):
            self.push_origin_ref(task_id, self.new_commit())
        self.clone.parent.mkdir(parents=True, exist_ok=True)
        self.git("clone", "-q", str(self.origin), str(self.clone))
        for task_id in (ahead, behind, same):
            self.git("-C", str(self.clone), "fetch", "-q", "origin",
                     f"{docs_ref(task_id)}:{docs_ref(task_id)}")
        origin_ahead = self.refs(self.clone)[docs_ref(ahead)]
        local_ahead = self.new_commit(origin_ahead, repo=self.clone)
        self.git("-C", str(self.clone), "update-ref", docs_ref(ahead),
                 local_ahead)
        old_behind = self.refs(self.origin)[docs_ref(behind)]
        self.push_origin_ref(behind, self.new_commit(old_behind))
        self.push_origin_ref(only_origin, self.new_commit())
        before = self.refs(self.clone)
        self.assertEqual(before[docs_ref(ahead)], local_ahead)
        self.assertNotEqual(before[docs_ref(behind)],
                            self.refs(self.origin)[docs_ref(behind)])
        self.assertNotIn(docs_ref(only_origin), before)

        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            clone, error = workspace.ensure_clone(config.DEFAULT_TARGET)

        self.assertIsNone(error, self.msg(f"ensure_clone отказал: {error}"))
        self.assertEqual(clone, self.clone)
        self.assertEqual(self.refs(self.clone), before, self.msg(
            "ensure_clone изменил ссылки документов существующего клона"))


FAILING_GIT = """#!/bin/sh
fetch=""
docs=""
for arg in "$@"; do
  case "$arg" in
    fetch) fetch=1 ;;
    *refs/artifacts*) docs=1 ;;
  esac
done
if [ -n "$fetch" ] && [ -n "$docs" ]; then
  echo "fatal: {token}" >&2
  exit 128
fi
exec "{real_git}" "$@"
"""


class EnsureCloneSurvivesFetchFailureTest(CloneRefsSandbox):

    def failing_fetch_path(self, token: str) -> str:
        """`PATH` с подставным `git` впереди: отказ только у fetch ссылок
        документов, с текстом `token` в stderr."""
        real_git = shutil.which("git")
        self.assertTrue(real_git, "предусловие: git в PATH")
        bindir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, bindir, True)
        script = bindir / "git"
        script.write_text(FAILING_GIT.replace("{token}", token).replace(
            "{real_git}", real_git), encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP
                     | stat.S_IXOTH)
        return f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}"

    def test_ac3_fetch_failure_keeps_clone_and_prints_reason(self):
        """Неудача fetch ссылок документов не отменяет заведение клона и печатается с причиной.

        Сценарий: в `origin` есть ссылки документов; подставной `git`
        отказывает любому `fetch`, называющему `refs/artifacts`, со
        случайной меткой в stderr, остальное (сам `git clone`, хуки,
        идентичность) идёт настоящим git. `ensure_clone` возвращает путь
        клона без причины отказа, каталог клона на месте и остаётся
        git-репозиторием, а в вывод (stdout или stderr) попала строка с
        меткой из stderr неудавшегося fetch.

        Ловит мутацию: неудача fetch превращается в причину отказа
        `ensure_clone` (или каталог клона убирается, как при неудаче
        `git clone`) — возврат несёт причину / каталога нет; причина
        неудачи fetch глотается молча — метки нет в выводе.
        """
        self.seed_origin_refs(self.rng.randint(1, 3))
        token = f"подставной отказ fetch {self.rng.randrange(16 ** 8):08x}"

        out = io.StringIO()
        with mock.patch.dict(os.environ,
                             {"PATH": self.failing_fetch_path(token)}), \
                redirect_stdout(out), redirect_stderr(out):
            clone, error = workspace.ensure_clone(config.DEFAULT_TARGET)

        self.assertIsNone(error, self.msg(
            f"неудача fetch стала отказом ensure_clone: {error}"))
        self.assertEqual(clone, self.clone)
        self.assertTrue((clone / ".git").exists(), self.msg(
            "каталог клона не остался git-репозиторием"))
        self.assertIn(token, out.getvalue(), self.msg(
            "причина неудачи fetch не попала в вывод"))


class ClosedRefSyncSandbox(SeededMixin, OriginRealGitSandbox):
    """Клон артели — сам репозиторий песочницы, `origin` — bare рядом;
    задачи артели закрываются настоящим коммитом закрытия."""

    def setUp(self):
        super().setUp()
        self.seed_rng()
        self.add_origin()
        self.git("push", "-q", "origin",
                 f"{config.MAIN_BRANCH}:{config.MAIN_BRANCH}")
        self.conn = store.db()

    def local_head(self, ref: str) -> str:
        out = self.git("for-each-ref", "--format=%(objectname)", ref)
        return out.strip()

    def origin_head(self, ref: str) -> str:
        out = self.git("-C", self.bare, "for-each-ref",
                       "--format=%(objectname)", ref)
        return out.strip()

    def closed_task(self) -> tuple[str, str, str]:
        """(id, коммит закрытия, первый коммит ссылки) — закрытая задача
        артели, у которой локальная ссылка и ссылка в origin равны коммиту
        закрытия."""
        task_id = random_task_id(self.rng)
        state = self.rng.choice(("done", "killed"))
        store.insert_task(self.conn, task_id, "Задача", "in_dev",
                          f"task/{task_id.lower()}-x", config.DEFAULT_TARGET,
                          25.0)
        tree = self.git("rev-parse", "HEAD^{tree}").strip()
        first = self.git("commit-tree", tree, "-p", "HEAD", "-m",
                         f"{task_id}: документы").strip()
        self.git("update-ref", docs_ref(task_id), first)
        store.update_task(self.conn, task_id, state=state)
        capture(snapshot.commit_closing, self.conn, task_id, state)
        closing = snapshot.closing_sha(self.conn, task_id)
        self.assertTrue(closing, self.msg("предусловие: коммит закрытия"))
        self.git("push", "-q", "--force", "origin",
                 f"{closing}:{docs_ref(task_id)}")
        self.assertEqual(self.local_head(docs_ref(task_id)), closing)
        self.assertEqual(self.origin_head(docs_ref(task_id)), closing)
        return task_id, closing, first

    def only_in_origin(self) -> str:
        """Закрытая задача без локальной ссылки; в origin — коммит закрытия."""
        task_id, _closing, _first = self.closed_task()
        self.git("update-ref", "-d", docs_ref(task_id))
        return task_id

    def mismatched(self) -> str:
        """Закрытая задача, у которой ссылка в origin ≠ коммиту закрытия:
        сдвинута на первый коммит или снята; локальная ссылка — коммит
        закрытия или снята (вид — случайно)."""
        task_id, _closing, first = self.closed_task()
        ref = docs_ref(task_id)
        if self.rng.random() < 0.5:
            self.git("push", "-q", "--force", "origin", f"{first}:{ref}")
        else:
            self.git("push", "-q", "origin", f":{ref}")
        if self.rng.random() < 0.5:
            self.git("update-ref", "-d", ref)
        return task_id

    def seed_closed(self, fetchable: int, mismatched: int) -> tuple[list, list]:
        kinds = (["fetchable"] * fetchable + ["mismatched"] * mismatched
                 + ["synced"] * self.rng.randint(0, 2))
        self.rng.shuffle(kinds)
        groups = {"fetchable": [], "mismatched": [], "synced": []}
        for kind in kinds:
            if kind == "fetchable":
                groups[kind].append(self.only_in_origin())
            elif kind == "mismatched":
                groups[kind].append(self.mismatched())
            else:
                groups[kind].append(self.closed_task()[0])
        return groups["fetchable"], groups["mismatched"]

    def summary_rows(self, checks: list) -> list:
        return [c for c in checks if FETCH_ALL_HINT in c.detail]

    def assert_summary(self, checks: list, count: int) -> None:
        rows = self.summary_rows(checks)
        self.assertEqual(len(rows), 1, self.msg(
            f"строк с подсказкой {FETCH_ALL_HINT} не одна: {checks}"))
        self.assertNotEqual(rows[0].status, "warn", self.msg(
            f"сводка со статусом warn: {rows[0]}"))
        self.assertRegex(rows[0].detail, rf"(?<!\d){count}(?!\d)", self.msg(
            f"сводка не называет число задач ({count}): {rows[0]}"))


class ClosedRefOnlyInOriginTest(ClosedRefSyncSandbox):

    def test_ac4_closed_ref_only_in_origin_is_not_a_warning(self):
        """Закрытая задача без локальной ссылки, совпадающая в origin с коммитом закрытия, — не `warn`, а число в одной сводке.

        Сценарий: от одной до четырёх закрытых задач без локальной ссылки,
        у которых ссылка в origin равна коммиту закрытия, вперемешку с
        закрытыми задачами, полностью совпадающими с коммитом закрытия.
        Ни одна `warn`-строка `check_artifact_ref_sync` не называет id
        такой задачи; ровно одна строка результата несёт подсказку
        `docs --fetch-all`, её статус не `warn`, и она называет число
        таких задач.

        Ловит мутацию: прежняя ветка «локальная голова ≠ коммиту закрытия
        — предупреждение» срабатывает и при отсутствии локальной ссылки —
        `warn` с id задачи («голова (нет локально)»); сводка выводится
        строкой `warn` или по строке на задачу — статус `warn` / строк с
        подсказкой больше одной; в сводке общее число закрытых задач
        вместо числа задач без локальной ссылки — нужного числа в строке
        нет.
        """
        fetchable, _ = self.seed_closed(self.rng.randint(1, 4), 0)

        checks = doctor.check_artifact_ref_sync(self.conn)

        noisy = [c for c in checks if c.status == "warn"
                 and any(task_id in c.detail for task_id in fetchable)]
        self.assertEqual(noisy, [], self.msg(
            "warn по задаче, чья ссылка есть только в origin"))
        self.assert_summary(checks, len(fetchable))


class ClosedRefSummaryNextToWarningTest(ClosedRefSyncSandbox):

    def test_ac5_one_warning_for_mismatch_and_one_summary(self):
        """Рядом с настоящим расхождением — ровно одна `warn`-строка по нему и одна сводка.

        Сценарий: от двух до четырёх закрытых задач без локальной ссылки
        (в origin — коммит закрытия), одна закрытая задача, у которой
        ссылка в origin ≠ коммиту закрытия (сдвинута на ранний коммит или
        снята; локальная ссылка есть или нет — случайно), и случайное
        число полностью совпадающих закрытых задач. `check_artifact_ref_sync`
        выдаёт ровно одну `warn`-строку, она называет задачу с
        расхождением, и ровно одну строку-сводку с подсказкой
        `docs --fetch-all` не со статусом `warn`, называющую число задач
        без локальной ссылки.

        Ловит мутацию: при наличии настоящих предупреждений сводка
        отбрасывается (возвращаются только `warn`-строки) — строки с
        подсказкой нет; сводка встраивается в `warn`-строку — её статус
        `warn`; отсутствие локальной ссылки освобождает от предупреждения
        и задачу, у которой origin ≠ коммиту закрытия, — `warn`-строк нет.
        """
        fetchable, mismatched = self.seed_closed(self.rng.randint(2, 4), 1)

        checks = doctor.check_artifact_ref_sync(self.conn)

        warns = [c for c in checks if c.status == "warn"]
        self.assertEqual(len(warns), 1, self.msg(f"warn-строки: {warns}"))
        self.assertIn(mismatched[0], warns[0].detail, self.msg(
            "warn-строка не называет задачу с расхождением"))
        self.assert_summary(checks, len(fetchable))


if __name__ == "__main__":
    unittest.main()
