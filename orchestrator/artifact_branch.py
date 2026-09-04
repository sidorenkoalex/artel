"""Артефактная ветка пульта: `tasks/<id>/` target'а при жизни задачи
(SPEC T094, требования 7-11; AC-8, AC-9, AC-10, AC-12).

С A7 (требование 2, требование 3, AC-5/AC-6/AC-7) — ЛЮБОЙ target,
включая артель: до A7 self/догфуд (`config.DEFAULT_TARGET`) оставался
на однобраншевом флоу (`tasks/<id>/` жило прямо в ветке `task/*`) —
убран целиком вместе с `catalog._new_dogfood`; новые задачи артели
заводят эту ветку тем же кодом, что и любой другой target.

Запись — веткой-плотником (`hash-object`/`update-index`/`write-tree`/
`commit-tree`/`update-ref`), не рабочим деревом `config.ROOT`: главная
копия пульта в этот момент может стоять на любой ветке (main, ручной
чекаут Оператора) — плотницкая запись её чекаут не трогает вовсе.
Временный `GIT_INDEX_FILE` (тот же приём, каким `tasks/T094/
acceptance_tests/test_ac16_retro_corpus_local_rebuild.py` кладёт тестовый
`refs/artifacts/*`) держит операции независимыми от индекса основной
рабочей копии.
"""
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import config, fixation, gitcmd

PASSPORT_REL_TMPL = "tasks/{task_id}/PASSPORT.md"


def branch_name(task_id: str) -> str:
    """Имя артефактной ветки пульта задачи (реестр PLAN.md, требование 1:
    имя решает разработчик — SPEC схему не называет)."""
    return f"artifact/{task_id.lower()}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def write_commit(repo: Path, files: dict, message: str, author_name: str,
                 author_email: str, parent: str | None = None,
                 remove: list | None = None) -> str:
    """Коммитит `files` ({путь: текст ИЛИ bytes}) в объектную базу `repo`
    плотницки (используется и `snapshot.publish_and_cleanup` — коммит в
    клоне целевого, не только в `config.ROOT`); `parent`, если задан, —
    дерево-родитель загружается в индекс первым (`read-tree`), так что
    новый коммит несёт и старое содержимое, не только правку `files`
    (дописывание, не перезапись — AC-12). Возвращает sha нового коммита;
    пустая строка — git не ответил на любом шаге.

    Значение `files[rel]` — `str` (обычный артефакт-текст) или `bytes`
    (нетекстовое содержимое, например бинарный файл роли, REVIEW.md T094
    итерация 2, замечание 1: раньше такие файлы терялись при попытке
    прочитать их как UTF-8) — `hash-object` получает байты напрямую в
    обоих случаях, `str` кодируется UTF-8 без потерь для текста.

    `remove` — пути, которые обязаны пропасть из дерева результата, а не
    просто отсутствовать в `files` (SPEC 01M1KT0792125J9ZNJNZJ86E9Q,
    требование 4/AC-6): `update-index --force-remove` поверх дерева,
    загруженного `read-tree parent`, — без него запись, отсутствующая в
    `files`, остаётся в результирующем дереве навсегда (дописывание,
    никогда не удаление). Применяется ПОСЛЕ `files` — вызывающий код не
    имеет права пересекать `files` и `remove` одним и тем же путём.
    """
    index_file = repo / f".artel-carpentry-index-{os.getpid()}-{abs(id(files))}"
    env = {**os.environ, "GIT_INDEX_FILE": str(index_file)}
    try:
        if parent:
            read_tree = subprocess.run(
                ["git", "read-tree", parent], cwd=repo, env=env,
                capture_output=True, text=True)
            if read_tree.returncode != 0:
                return ""
        for rel, content in files.items():
            data = content if isinstance(content, bytes) else content.encode("utf-8")
            blob = subprocess.run(
                ["git", "hash-object", "-w", "--stdin"], cwd=repo, env=env,
                input=data, capture_output=True)
            if blob.returncode != 0:
                return ""
            blob_sha = blob.stdout.decode().strip()
            upd = subprocess.run(
                ["git", "update-index", "--add", "--cacheinfo",
                 f"100644,{blob_sha},{rel}"],
                cwd=repo, env=env, capture_output=True, text=True)
            if upd.returncode != 0:
                return ""
        for rel in (remove or []):
            rm = subprocess.run(
                ["git", "update-index", "--force-remove", "--", rel],
                cwd=repo, env=env, capture_output=True, text=True)
            if rm.returncode != 0:
                return ""
        tree = subprocess.run(["git", "write-tree"], cwd=repo, env=env,
                              capture_output=True, text=True)
        if tree.returncode != 0:
            return ""
        tree_sha = tree.stdout.strip()
        commit_args = ["git", "commit-tree", tree_sha, "-m", message]
        if parent:
            commit_args += ["-p", parent]
        commit_env = {**env, "GIT_AUTHOR_NAME": author_name,
                      "GIT_AUTHOR_EMAIL": author_email,
                      "GIT_COMMITTER_NAME": author_name,
                      "GIT_COMMITTER_EMAIL": author_email}
        commit = subprocess.run(commit_args, cwd=repo, env=commit_env,
                                capture_output=True, text=True)
        if commit.returncode != 0:
            return ""
        return commit.stdout.strip()
    finally:
        try:
            index_file.unlink(missing_ok=True)
        except OSError:
            pass


def commit_files(task_id: str, files: dict, message: str,
                 author_name: str = fixation.FIXATION_AUTHOR_NAME,
                 author_email: str = fixation.FIXATION_AUTHOR_EMAIL,
                 remove: list | None = None) -> str:
    """Коммитит `files` в артефактную ветку задачи (создаёт её, если ещё
    нет — от головы `config.MAIN_BRANCH`, тем же принципом, что кодовая
    ветка `task/*`). Возвращает sha нового коммита; пустая строка — git
    не ответил. `remove` — см. `write_commit`."""
    branch = branch_name(task_id)
    parent = gitcmd.branch_head_sha(branch) or gitcmd.branch_head_sha(
        config.MAIN_BRANCH) or None
    commit_sha = write_commit(config.ROOT, files, message, author_name,
                              author_email, parent=parent, remove=remove)
    if not commit_sha:
        return ""
    upd_ref = subprocess.run(
        ["git", "update-ref", f"refs/heads/{branch}", commit_sha],
        cwd=config.ROOT, capture_output=True, text=True)
    if upd_ref.returncode != 0:
        return ""
    return commit_sha


def push(task_id: str) -> bool:
    """Push best-effort артефактной ветки в origin пульта (SPEC требование
    7, AC-8): отказ (нет origin, сеть недоступна) — `False`, не исключение
    — вызывающий код (`catalog.cmd_new`) не имеет права из-за этого
    отказать в заведении задачи."""
    branch = branch_name(task_id)
    res = gitcmd.git("push", "-q", "origin", f"refs/heads/{branch}:refs/heads/{branch}")
    return res is not None and res.returncode == 0


def read_tree(task_id: str) -> dict:
    """{путь: текст} всех файлов `tasks/<id>/` артефактной ветки задачи;
    пустой словарь — ветки нет или каталог в ней пуст."""
    branch = branch_name(task_id)
    paths = gitcmd.ls_tree_files(branch, f"tasks/{task_id}") or []
    files = {}
    for rel in paths:
        text, _ = gitcmd.show(branch, rel)
        if text is not None:
            files[rel] = text
    return files


def materialize_task_dir(task_id: str, dest_root: Path) -> str:
    """Материализует `tasks/<id>/` каталога `dest_root` из ГОЛОВЫ
    артефактной ветки (SPEC 01M1NKTF173WV5CPDZ1C3WW69K, AC-1): файлы
    ветки перезаписываются на диск как есть, файл на диске, отсутствующий
    в ветке (в том числе осевший от прерванного предыдущего шага),
    убирается. Тот же приём, что `acceptance.materialize_from_branch`
    (git-чтение через `gitcmd.ls_tree_files`/`show`), но пишет НА МЕСТЕ,
    не во временный каталог, и удаляет лишнее — здесь диск обязан стать
    зеркалом ветки, а не просто получить недостающее.

    Ветки нет, или git не ответил на любой из шагов — тихая деградация
    (AC-2): диск не трогается вовсе, возвращается пустая строка. Голова
    ветки читается ОДИН раз в начале (`gitcmd.branch_head_sha`) и дальше
    используется как ревизия для `ls_tree_files`/`show` — атомарный
    снимок, не гоняющаяся за движущимся именем ветки между вызовами.

    Возвращает sha использованной головы — конфликт-гвард автокоммита
    (`checkpoint._commit_external_step_artifacts`, AC-6/AC-7) хранит его
    как baseline, с которым потом сверяет диск и текущую голову ветки.
    """
    branch = branch_name(task_id)
    head = gitcmd.branch_head_sha(branch)
    if not head:
        return ""
    prefix = f"tasks/{task_id}/"
    paths = gitcmd.ls_tree_files(head, prefix.rstrip("/"))
    if paths is None:
        return ""
    wanted = {}
    for rel in paths:
        if not rel.startswith(prefix):
            continue
        text, _ = gitcmd.show(head, rel)
        if text is not None:
            wanted[rel] = text
    task_dir = dest_root / "tasks" / task_id
    if task_dir.is_dir():
        for path in sorted(task_dir.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(dest_root).as_posix()
            if rel not in wanted:
                path.unlink()
    for rel, text in wanted.items():
        dest = dest_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text, encoding="utf-8")
    return head


def append_passport_line(task_id: str, state: str, actor: str) -> None:
    """Дописывает строку паспорта живой задачи (SPEC требование 11,
    AC-12) в артефактную ветку — состояние, момент перехода
    (`_now()`, тот же формат, что `store.now()`), актор. Читает текущее
    содержимое файла ветко-корректно (`gitcmd.show`) и коммитит
    НАКОПЛЕННЫЙ текст — предыдущие строки не теряются (дописывание, не
    перезапись)."""
    rel = PASSPORT_REL_TMPL.format(task_id=task_id)
    branch = branch_name(task_id)
    existing, _ = gitcmd.show(branch, rel)
    prior = existing if existing is not None else "# Паспорт живой задачи\n\n"
    line = f"{_now()}  {state}  actor={actor}\n"
    commit_files(task_id, {rel: prior + line},
                f"{task_id}: паспорт — {state}")


def snapshot_pending(task_id: str) -> bool:
    """True — артефактная ветка задачи ещё существует локально: снапшот
    закрытия (SPEC требования 12-13) ещё не подтверждён в origin
    целевого (AC-15) — уборка ветки ждёт."""
    return gitcmd.branch_exists(branch_name(task_id))


def drop(task_id: str) -> str:
    """Удаляет артефактную ветку задачи ПОСЛЕ подтверждённого снапшота
    (AC-13, AC-15); строка — что вышло."""
    branch = branch_name(task_id)
    if not gitcmd.branch_exists(branch):
        return f"артефактной ветки {branch} нет"
    res = gitcmd.git("branch", "-D", branch)
    if res is None or res.returncode != 0:
        reason = res.stderr.strip()[:200] if res is not None else "git не ответил"
        return f"артефактная ветка {branch} не удалена: {reason}"
    return f"удалена артефактная ветка {branch}"
