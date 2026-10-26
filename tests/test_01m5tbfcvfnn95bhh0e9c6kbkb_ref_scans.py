"""Ссылка эпика `refs/artifacts/epic-<id>` рядом со ссылкой документов
задачи `refs/artifacts/<id задачи>` в origin: забор приносит обе, места
перебора ссылок документов не принимают ссылку эпика за задачу.

Группа: долгоживущий
Красен до реализации: пересборка кэша ретро-корпуса выводит id задачи из имени любой ссылки `refs/artifacts/*` и даёт строку `task_id = epic-<id>` по дереву эпика, несущему заголовочный блок ретро; `plan_appendix_ci.remote_docs_refs` отдаёт `epic-<id>` среди ссылок документов задач.

Держит связку «git origin — команда или функция пульта — её вывод»:
песочница — настоящий git (`real_git`, `tests/fixtures.py`), пульт — клон
артели с синхронным origin. Коммиты ссылок собираются в черновом
репозитории и отправляются в origin помощником песочницы `git`; ссылка
эпика несёт `epics/<id>/EPIC.md` с заголовочным блоком, тем же, что у
ретро задачи. Каждое место сверяется дважды — со ссылкой эпика и после
её удаления: вывод по ссылке задачи обязан совпасть. Id, тексты и
порядок порождаются модулем `random` при каждом запуске; зерно
печатается и входит в текст провала.
"""
import contextlib
import io
import os
import random
import shutil
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from orchestrator import (artel, config, doctor, idgen, retro_corpus, store,
                          workspace)
from scripts import plan_appendix_ci
from tests.sandbox import make_project_repo

ARTIFACTS = "refs/artifacts/"
FRONTMATTER = "---\noperator: o-{seed}\nmodel: m-{seed}\nartel_sha: {sha}\n---\n\n"


# --- окружение сценария ---

@pytest.fixture
def stand(real_git):
    """Клон артели с синхронным origin; в origin — ссылка документов задачи
    (в БД — задача `in_dev`) и ссылка эпика."""
    sb = real_git
    sb.seed = random.randrange(1 << 30)
    print(f"зерно: {sb.seed}")
    sb.rng = random.Random(sb.seed)
    env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
    env.start()
    sb.addCleanup(env.stop)
    sb.origin = sb.add_synced_origin()
    scratch = Path(tempfile.mkdtemp())
    sb.addCleanup(shutil.rmtree, scratch, ignore_errors=True)
    sb.scratch = scratch
    sb.git("init", "-q", str(scratch))
    sb.task = idgen.new_task_id()
    # Id эпика — приставка `E` и id пульта (SPEC шага Э1).
    sb.epic = "E" + idgen.new_task_id()
    sb.epic_ref = f"epic-{sb.epic}"
    store.insert_task(store.db(), sb.task, "Задача песочницы", "in_dev",
                      f"task/{sb.task.lower()}-x", config.DEFAULT_TARGET,
                      config.DEFAULT_BUDGET_USD)
    head = sb.git("rev-parse", "HEAD").strip()
    task_dir = f"{config.TASKS.name}/{sb.task}"
    sb.task_sha = commit_tree(sb, {
        f"{task_dir}/SPEC.md": f"SPEC {sb.seed}\n",
        f"{task_dir}/RETRO.md": FRONTMATTER.format(seed=sb.seed, sha=head)
        + "ретро\n"})
    sb.epic_sha = commit_tree(sb, {
        f"epics/{sb.epic}/EPIC.md": FRONTMATTER.format(seed=sb.seed, sha=head)
        + f"# Эпик {sb.seed}\n",
        f"epics/{sb.epic}/DECISIONS.md": "решений нет\n"})
    return sb


def note(stand, text: str) -> str:
    return f"зерно: {stand.seed}; {text}"


def commit_tree(stand, files: dict) -> str:
    """Коммит без родителя в черновом репозитории с деревом ровно `files`."""
    sgit = ("-C", str(stand.scratch))
    stand.git(*sgit, "checkout", "-q", "--orphan",
              f"o-{stand.rng.randrange(1 << 30)}")
    stand.git(*sgit, "rm", "-rqf", "--ignore-unmatch", "--", ".")
    for rel, text in files.items():
        path = stand.scratch / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    stand.git(*sgit, "add", "-A")
    stand.git(*sgit, "-c", "user.name=t", "-c", "user.email=t@example.invalid",
              "commit", "-qm", f"фикстура {stand.seed}")
    return stand.git(*sgit, "rev-parse", "HEAD").strip()


def place(stand, repo, name: str, sha: str) -> None:
    stand.git("-C", str(stand.scratch), "push", "-q", "-f", str(repo),
              f"{sha}:{ARTIFACTS}{name}")


def drop(stand, repo, name: str) -> None:
    stand.git("-C", str(stand.scratch), "push", "-q", str(repo),
              f":{ARTIFACTS}{name}")


def local_ref(stand, name: str, repo=None) -> str:
    return stand.git("-C", str(repo or stand.root), "for-each-ref",
                     "--format=%(objectname)", f"{ARTIFACTS}{name}").strip()


def both_in_origin(stand) -> None:
    pairs = [(stand.task, stand.task_sha), (stand.epic_ref, stand.epic_sha)]
    stand.rng.shuffle(pairs)
    for name, sha in pairs:
        place(stand, stand.origin, name, sha)


def both_local(stand) -> None:
    for name, sha in ((stand.task, stand.task_sha), (stand.epic_ref, stand.epic_sha)):
        place(stand, stand.root, name, sha)


def without_epic(stand) -> None:
    """Ссылки эпика больше нет ни в origin, ни в клоне артели."""
    drop(stand, stand.origin, stand.epic_ref)
    stand.git("update-ref", "-d", f"{ARTIFACTS}{stand.epic_ref}")


def cli(*args: str) -> tuple[str, int]:
    buf = io.StringIO()
    code = 0
    with mock.patch.object(sys, "argv", ["artel.py", *args]), \
            contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            artel.main()
        except SystemExit as exc:
            code = exc.code or 0
            if isinstance(code, str):
                buf.write(f"\n{code}")
                code = 1
    return buf.getvalue(), code


def db_rows() -> dict:
    conn = store.db()
    return {t: [tuple(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY rowid")]
            for t in ("tasks", "steps")}


# --- AC-11 ---

def test_ac11_docs_fetch_all_brings_both_refs_without_epic_line(stand):
    """`docs --fetch-all`: обе ссылки из origin приходят в клон артели с головами origin, id эпика нет в выводе, строк задач и журнала не прибавилось, код 0.

    Ловит мутацию: забор отсеивает `epic-…` вместе с не-задачами —
    ссылка эпика не принесена; по ссылке эпика печатается строка или
    ищется задача с id `epic-<id>` (запись журнала, отказ).
    """
    both_in_origin(stand)
    before = db_rows()

    out, code = cli("docs", "--fetch-all")

    assert code == 0, note(stand, f"docs --fetch-all ({code}):\n{out}")
    assert local_ref(stand, stand.task) == stand.task_sha, note(stand, out)
    assert local_ref(stand, stand.epic_ref) == stand.epic_sha, note(
        stand, f"ссылка эпика не принесена:\n{out}")
    assert stand.epic not in out, note(stand, f"строка по ссылке эпика:\n{out}")
    assert db_rows() == before, note(stand, "забор изменил строки задач или журнала")


def test_ac11_new_clone_brings_both_refs_silently(stand):
    """Заведение клона проекта (`workspace.ensure_clone`) по origin с обеими ссылками: в клоне обе ссылки с головами origin, ошибки нет, id эпика в выводе нет.

    Ловит мутацию: `_fetch_docs_refs` берёт шаблон `refs/artifacts/<ULID>`
    — ссылка эпика в новый клон не приходит; по ссылке эпика печатается
    строка отказа.
    """
    project = "p" + "".join(stand.rng.choice("abcdefghij") for _ in range(7))
    make_project_repo(project)
    remote = stand.root.parent / f"remote-{stand.seed}-{project}"
    shutil.move(str(config.PROJECTS / project), str(remote))
    stand.addCleanup(shutil.rmtree, remote, ignore_errors=True)
    bare = remote / "origin.git"
    for name, sha in ((stand.task, stand.task_sha), (stand.epic_ref, stand.epic_sha)):
        place(stand, bare, name, sha)
    text = config.TARGETS.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.strip().startswith("url:") and project in line:
            text = text.replace(line, f"    url: {bare}")
    config.TARGETS.write_text(text, encoding="utf-8")

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        clone, error = workspace.ensure_clone(project)

    assert error is None, note(stand, f"клон не заведён: {error}\n{buf.getvalue()}")
    assert local_ref(stand, stand.task, clone) == stand.task_sha
    assert local_ref(stand, stand.epic_ref, clone) == stand.epic_sha, note(
        stand, f"ссылка эпика не в новом клоне:\n{buf.getvalue()}")
    assert stand.epic not in buf.getvalue(), note(stand, buf.getvalue())


def test_ac11_cleanup_inventory_ignores_epic_ref(stand):
    """`artifact-branches-cleanup` (предпросмотр) с веткой `artifact/<задача>` в origin: код 0, id эпика нет в выводе, вывод со ссылкой эпика равен выводу без неё.

    Ловит мутацию: опись строит перечень задач из `refs/artifacts/*` —
    `epic-<id>` попадает в «задачи без refs/artifacts» или в ветки к
    удалению; разбор имени падает на `epic-`.
    """
    both_in_origin(stand)
    stand.git("push", "-q", str(stand.origin),
              f"HEAD:refs/heads/artifact/{stand.task.lower()}")

    with_epic, code = cli("artifact-branches-cleanup")
    assert code == 0, note(stand, f"cleanup ({code}):\n{with_epic}")
    assert stand.epic not in with_epic and stand.epic.lower() not in with_epic
    without_epic(stand)
    plain, _ = cli("artifact-branches-cleanup")
    assert with_epic == plain, note(stand, f"{with_epic}\n≠\n{plain}")


def test_ac11_doctor_ref_sync_has_no_epic_finding(stand):
    """Сверка ссылок документов `doctor` при обеих ссылках в origin и в клоне: ни одна находка не называет эпик, находки равны находкам без ссылки эпика.

    Ловит мутацию: сверка перебирает ссылки origin и выводит из имени
    id задачи — по `epic-<id>` находка «задачи нет в БД» или
    «расходится»; разбор падает на имени без формы id.
    """
    both_in_origin(stand)
    both_local(stand)

    with_epic = doctor.check_artifact_ref_sync(store.db())

    assert not [c for c in with_epic if stand.epic in str(c)], note(
        stand, f"находка по эпику: {with_epic}")
    without_epic(stand)
    plain = doctor.check_artifact_ref_sync(store.db())
    assert [tuple(c) for c in with_epic] == [tuple(c) for c in plain], note(
        stand, f"{with_epic}\n≠\n{plain}")


def test_ac11_retro_cache_has_no_epic_row(stand):
    """Пересборка кэша ретро-корпуса при обеих ссылках в клоне артели (у дерева эпика — тот же заголовочный блок, что у ретро задачи): строка задачи есть, строки с id эпика нет, строки равны строкам без ссылки эпика.

    Ловит мутацию: `_retro_entry` берёт `task_id` последним сегментом
    имени любой ссылки — строка `task_id = epic-<id>` в корпусе.
    """
    both_local(stand)
    cache = stand.root / ".artel" / f"retro-{stand.seed}.json"

    with mock.patch.object(retro_corpus, "CACHE_PATH", cache):
        with_epic = retro_corpus.rebuild_cache()
        assert any(r.get("task_id") == stand.task for r in with_epic), note(
            stand, f"предпосылка: нет строки задачи: {with_epic}")
        assert not [r for r in with_epic if stand.epic in repr(r)], note(
            stand, f"строка по ссылке эпика: {with_epic}")
        without_epic(stand)
        plain = retro_corpus.rebuild_cache()
    assert with_epic == plain, note(stand, f"{with_epic}\n≠\n{plain}")


def test_ac11_history_snapshots_dry_run_ignores_epic_ref(stand):
    """`artifact-history-snapshots --dry-run` при каталоге задачи на main origin и обеих ссылках в origin: код 0, id эпика нет в выводе, вывод равен выводу без ссылки эпика.

    Ловит мутацию: проход строит перечень из принесённых
    `refs/artifacts/*`, а не из каталогов main — эпик попадает в
    «со ссылкой»/«были бы созданы»; разбор падает на `epic-`.
    """
    rel = Path(config.TASKS.name) / stand.task / "SPEC.md"
    (stand.root / rel).parent.mkdir(parents=True, exist_ok=True)
    (stand.root / rel).write_text(f"SPEC {stand.seed}\n", encoding="utf-8")
    stand.git("add", str(rel))
    stand.git("-c", "user.name=t", "-c", "user.email=t@example.invalid",
              "commit", "-qm", f"каталог задачи {stand.seed}")
    stand.git("push", "-q", "origin", f"HEAD:{config.MAIN_BRANCH}")
    both_in_origin(stand)

    with_epic, code = cli("artifact-history-snapshots", "--dry-run")
    assert code == 0, note(stand, f"dry-run ({code}):\n{with_epic}")
    assert stand.epic not in with_epic, note(stand, with_epic)
    without_epic(stand)
    plain, _ = cli("artifact-history-snapshots", "--dry-run")
    assert with_epic == plain, note(stand, f"{with_epic}\n≠\n{plain}")


def test_ac11_plan_appendix_ci_refs_skip_epic(stand, monkeypatch):
    """Разбор ссылок документов CI в клоне с origin: `remote_docs_refs` отдаёт задачу с её головой и не отдаёт эпик; `docs_ref_for_branch` для ветки задачи находит её ссылку.

    Ловит мутацию: `remote_docs_refs` отдаёт любое имя под
    `refs/artifacts/` — `epic-<id>` среди ссылок документов задач;
    сопоставление ветки берёт не самое длинное совпадение.
    """
    both_in_origin(stand)
    monkeypatch.chdir(stand.root)

    refs = plan_appendix_ci.remote_docs_refs()

    assert refs.get(stand.task) == stand.task_sha, note(stand, f"{refs}")
    assert not [k for k in refs if stand.epic in k], note(
        stand, f"эпик среди ссылок документов задач: {refs}")
    branch_rest = f"{stand.task.lower()}-slug-{stand.seed}"
    assert plan_appendix_ci.docs_ref_for_branch(branch_rest, refs) == (
        stand.task, stand.task_sha), note(stand, f"{refs}")
