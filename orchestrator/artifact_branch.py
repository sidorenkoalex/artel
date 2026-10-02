"""Ссылка документов задачи `refs/artifacts/<id>` в репозитории пульта —
`tasks/<id>/` от `new` до конца жизни задачи (ADR-0021 п.3; до него —
ветка `artifact/<id>`, SPEC T094, требования 7-11). Для ЛЮБОГО target,
включая артель.

Дерево ссылки — только `tasks/<id>/…`, первый коммит — без родителя;
закрытие задачи — последний коммит RETRO в ту же ссылку
(`orchestrator/snapshot.py`), история документов остаётся достижимой из
головы. Исторические снимки закрытия (коммит без родителя, ADR-0018 п.1)
лежат под тем же именем и читаются тем же `gitcmd.show`.

Запись — плотницкая (`hash-object`/`update-index`/`write-tree`/
`commit-tree`/`update-ref`), не рабочим деревом `config.ROOT`: главная
копия пульта в этот момент может стоять на любой ветке — плотницкая
запись её чекаут не трогает. Временный `GIT_INDEX_FILE` держит операции
независимыми от индекса основной рабочей копии. `update-ref` идёт со
сверкой прежнего значения: две записи одной задачи, начатые от одной
головы, не теряют ни одной правки — проигравшая перечитывает ссылку и
пересобирает коммит поверх новой головы.

Каждый коммит ссылки сразу отправляется в `origin` пульта; отказ —
запись журнала, повтор — на следующем переходе (`send_pending` из
`store.set_state`). Гейт мержа и закрытие сверяют ссылку с `origin`
(`origin_sync_refusal`).
"""
import os
from datetime import datetime, timezone
from pathlib import Path

from . import config, fixation, gitcmd, store

PASSPORT_REL_TMPL = "tasks/{task_id}/PASSPORT.md"

# Пустое прежнее значение `update-ref`: ссылки ещё нет, и заводит её только
# тот, кто увидел её отсутствие (сверка прежнего значения и для первой
# записи).
_ABSENT_OID = "0" * 40

# Попыток записи со сверкой: проигрыш гонки перечитывает голову и
# пересобирает коммит; отказ, не уходящий за эти попытки, — не гонка,
# а сбой git (вызывающий код получает пустую строку, как и раньше).
_CAS_ATTEMPTS = 5

# Классификация отказа push (SPEC 01M1TQ0X14Y5B3C87WC0Q31PK2, требование 1):
# три причины, которые Оператору нужно различать — «заведение без origin»
# не то же самое действие, что «сеть моргнула», не то же самое, что
# «кто-то коммитил в origin мимо пульта» (инцидент 06.09, SPEC «Контекст»).
PUSH_REASON_NO_ORIGIN = "нет origin"
PUSH_REASON_NETWORK = "сеть"
PUSH_REASON_NON_FAST_FORWARD = "non-fast-forward"


def branch_name(task_id: str) -> str:
    """Полное имя ссылки документов задачи `refs/artifacts/<id>` (ADR-0021
    п.3). Имя функции прежнее: читатели передают его в `gitcmd.show`/
    `ls_tree_files`/`branch_head_sha` как ревизию, и полное имя ссылки
    там принимается так же, как имя ветки."""
    return f"refs/artifacts/{task_id}"


def ref_head(task_id: str) -> str:
    """sha головы ссылки документов; пустая строка — ссылки нет или git
    не ответил."""
    return gitcmd.branch_head_sha(branch_name(task_id))


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
            read_tree = gitcmd.carpentry(repo, ["read-tree", parent], env)
            if read_tree.returncode != 0:
                return ""
        for rel, content in files.items():
            data = content if isinstance(content, bytes) else content.encode("utf-8")
            blob = gitcmd.carpentry(repo, ["hash-object", "-w", "--stdin"], env,
                                    input=data, text=False)
            if blob.returncode != 0:
                return ""
            blob_sha = blob.stdout.decode().strip()
            upd = gitcmd.carpentry(
                repo, ["update-index", "--add", "--cacheinfo",
                      f"100644,{blob_sha},{rel}"], env)
            if upd.returncode != 0:
                return ""
        for rel in (remove or []):
            rm = gitcmd.carpentry(
                repo, ["update-index", "--force-remove", "--", rel], env)
            if rm.returncode != 0:
                return ""
        tree = gitcmd.carpentry(repo, ["write-tree"], env)
        if tree.returncode != 0:
            return ""
        tree_sha = tree.stdout.strip()
        commit_args = ["commit-tree", tree_sha, "-m", message]
        if parent:
            commit_args += ["-p", parent]
        commit_env = {**env, "GIT_AUTHOR_NAME": author_name,
                      "GIT_AUTHOR_EMAIL": author_email,
                      "GIT_COMMITTER_NAME": author_name,
                      "GIT_COMMITTER_EMAIL": author_email}
        commit = gitcmd.carpentry(repo, commit_args, commit_env)
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
    """Единый узел записи документов задачи (ADR-0021 п.3): коммит `files`
    поверх головы `refs/artifacts/<id>` (ссылки нет — первый коммит без
    родителя), `update-ref` со сверкой прежнего значения, затем отправка
    в `origin` (`_send`). Ссылка физически живёт в `config.ROOT` для
    ЛЮБОГО target. Возвращает sha нового коммита; пустая строка — git не
    ответил. `remove` — см. `write_commit`.

    Сверка проиграна (ссылку между чтением головы и `update-ref` сдвинула
    другая запись) — голова перечитывается, коммит пересобирается поверх
    неё: обе правки остаются в истории, история линейна. Отказ отправки
    коммит не отменяет — он журналируется и досылается на следующем
    переходе (`send_pending`)."""
    sha, _outcome = _write(task_id, files, message, author_name, author_email,
                           remove, require_change=False)
    return sha


# Исходы `commit_change`, кроме записанного коммита.
UNCHANGED = "unchanged"
TREE_UNKNOWN = "tree-unknown"


def commit_change(task_id: str, files: dict, message: str,
                  remove: list | None = None) -> tuple[str, str]:
    """`commit_files`, которому коммит без изменений не нужен: (sha, "") —
    записан и меняет дерево; ("", `UNCHANGED`) — дерево совпало с деревом
    головы, ссылка не тронута; ("", `TREE_UNKNOWN`) — деревья не сверены
    (git не ответил), ссылка не тронута; ("", "") — коммит не записан.
    Сверка идёт ДО `update-ref`: отправленный в `origin` пустой коммит
    назад уже не забрать."""
    return _write(task_id, files, message, fixation.FIXATION_AUTHOR_NAME,
                  fixation.FIXATION_AUTHOR_EMAIL, remove, require_change=True)


def _same_tree(commit_sha: str, parent: str) -> bool | None:
    res = gitcmd.git("rev-parse", f"{commit_sha}^{{tree}}", f"{parent}^{{tree}}")
    trees = res.stdout.split() if res is not None and res.returncode == 0 else []
    if len(trees) != 2:
        return None
    return trees[0] == trees[1]


def _write(task_id: str, files: dict, message: str, author_name: str,
           author_email: str, remove: list | None,
           require_change: bool) -> tuple[str, str]:
    ref = branch_name(task_id)
    for _ in range(_CAS_ATTEMPTS):
        parent = gitcmd.branch_head_sha(ref)
        commit_sha = write_commit(config.ROOT, files, message, author_name,
                                  author_email, parent=parent or None,
                                  remove=remove)
        if not commit_sha:
            return "", ""
        if require_change and parent:
            same = _same_tree(commit_sha, parent)
            if same is None:
                return "", TREE_UNKNOWN
            if same:
                return "", UNCHANGED
        upd_ref = gitcmd.git("update-ref", ref, commit_sha,
                             parent or _ABSENT_OID)
        if upd_ref is None:
            return "", ""
        if upd_ref.returncode == 0:
            _send(task_id, journal_success=False)
            return commit_sha, ""
    return "", ""


def _classify_push_failure(stderr: str) -> str:
    """Три причины отказа push, различаемые по подстроке `stderr` git
    (SPEC требование 1). Non-fast-forward различён вживую (бэйр-репозиторий,
    два клона, второй push после первого) — реальный git не несёт литерала
    «non-fast-forward» в этой версии, а несёт `[rejected] ... (fetch
    first)` — обе подстроки и проверяются. «Нет origin» здесь не нужен
    (перехватывается раньше `_attempt_push`, до попытки реального push) —
    остаток, не подошедший под non-fast-forward, классифицируется как
    «сеть» (единственная оставшаяся причина требования 1)."""
    lowered = stderr.lower()
    if ("rejected" in lowered or "fetch first" in lowered
            or "non-fast-forward" in lowered):
        return PUSH_REASON_NON_FAST_FORWARD
    return PUSH_REASON_NETWORK


def _attempt_push(branch: str) -> tuple[bool, str, str]:
    """(успех, причина отказа, stderr git) — причина/stderr пустые при
    успехе. Отсутствие origin проверяется ДО попытки реального push
    (`gitcmd.has_no_remote`) — не по тексту stderr: `git push` без
    настроенного origin отвечает по-разному в зависимости от версии git,
    а отсутствие remote проверяется напрямую и надёжно."""
    if gitcmd.has_no_remote(config.ROOT):
        return False, PUSH_REASON_NO_ORIGIN, ""
    ref = gitcmd.qualified_ref(branch)
    res = gitcmd.git("push", "-q", "origin", f"{ref}:{ref}")
    if res is not None and res.returncode == 0:
        return True, "", ""
    stderr = (res.stderr or "").strip() if res is not None else "git не ответил"
    return False, _classify_push_failure(stderr), stderr


def _journal_push_outcome(task_id: str, branch: str, ok: bool, reason: str,
                          stderr: str) -> None:
    """Запись журнала задачи об исходе push — успех и отказ ОБА (AC-3:
    повторная попытка на следующем автокоммите обязана оставить СВОЮ
    запись про исход, успешный или нет, не молчать так же, как молчал бы
    код до этой задачи). Свежее `store.db()`-соединение — та же цена,
    что уже платят `answer.py`/`amend.py`/`catalog.py` в похожих местах,
    не имеющих под рукой чужого `conn`; циклического импорта не образует
    — `store.py` тянет `artifact_branch` только отложенным импортом
    внутри функции (`store.record_fixation`), не на уровне модуля."""
    conn = store.db()
    if ok:
        store.journal(conn, task_id, "orchestrator", "push артефактной ветки",
                      f"push артефактной ветки {branch} — успех")
        return
    detail = reason + (f": {stderr[:300]}" if stderr else "")
    if reason == PUSH_REASON_NON_FAST_FORWARD:
        local_sha = gitcmd.branch_head_sha(branch)
        origin_sha = gitcmd.remote_branch_sha(branch)
        detail += (f"; локальный sha {local_sha}, origin sha {origin_sha} "
                  f"— свести merge-коммитом")
    store.journal(conn, task_id, "orchestrator",
                  "push артефактной ветки FAILED", detail)


def push(task_id: str) -> bool:
    """Push артефактной ветки в origin пульта — best-effort в смысле
    возврата (SPEC требование 7, AC-8: `False`, не исключение — вызывающий
    код, включая `catalog.cmd_new`, не имеет права из-за отказа push
    отказать в заведении задачи или прервать шаг), но НЕ молчаливый:
    каждый исход, успех и отказ, классифицируется и журналируется (SPEC
    01M1TQ0X14Y5B3C87WC0Q31PK2, требования 1-2). `--force`/`-f`/
    `--force-with-lease` здесь не появляется НИКОГДА, включая
    non-fast-forward (AC-4) — единственный аргумент ветки после `origin`
    в команде push буквальный, без условных путей."""
    branch = branch_name(task_id)
    ok, reason, stderr = _attempt_push(branch)
    _journal_push_outcome(task_id, branch, ok, reason, stderr)
    return ok


def _origin_configured() -> bool:
    """У репозитория пульта есть `origin` с адресом. Нет — отправлять
    некуда (лёгкая песочница без git, пульт без remote): автоматическая
    отправка после коммита молчит, а о пустом remote говорит `doctor`.
    Адрес есть, но недоступен — это отказ отправки, он журналируется."""
    res = gitcmd.git("remote", "get-url", "origin")
    return res is not None and res.returncode == 0 and bool(res.stdout.strip())


def _send(task_id: str, journal_success: bool) -> bool:
    """Отправка ссылки документов в `origin` после коммита и на переходе.
    Отказ журналируется всегда (классифицированной причиной, тем же
    `_journal_push_outcome`, что у `push`); успех — только по просьбе
    вызывающего: автоматическая отправка идёт после каждого коммита, и
    запись об успехе на каждой строке паспорта засорила бы журнал."""
    if not _origin_configured():
        return False
    ref = branch_name(task_id)
    ok, reason, stderr = _attempt_push(ref)
    if not ok or journal_success:
        _journal_push_outcome(task_id, ref, ok, reason, stderr)
    return ok


def send_pending(task_id: str) -> None:
    """Повторная отправка ссылки на переходе FSM (`store.set_state`):
    коммит, чья отправка раньше отказала, досылается здесь. Ссылки нет
    локально — отправлять нечего. Совпадающую с `origin` ссылку `git push`
    не меняет."""
    if ref_head(task_id):
        _send(task_id, journal_success=False)


def origin_sync_refusal(task_id: str) -> str | None:
    """None — локальная `refs/artifacts/<id>` совпадает с ней же в
    `origin` (гейт мержа и закрытие могут идти дальше); иначе — текст
    отказа, называющий `origin` и оба sha.

    Перед сверкой — попытка отправки: коммит, чья отправка раньше
    отказала, здесь же и доезжает. Отказ сверки — и расхождение, и
    отсутствие ссылки в `origin` при локальной, и недоступный `origin`:
    история документов, которая есть только локально, закрытой не
    считается. `origin` у пульта не настроен вовсе — сверять не с чем
    (лёгкая песочница), об этом говорит `doctor`."""
    if not _origin_configured():
        return None
    local = ref_head(task_id)
    if local:
        _send(task_id, journal_success=False)
    remote, reason = gitcmd.remote_ref_state(branch_name(task_id))
    if reason:
        return (f"отказ: origin не ответил на сверку {branch_name(task_id)} "
                f"— {reason}")
    if local == remote:
        return None
    if not remote:
        return (f"отказ: {branch_name(task_id)} нет в origin (локально "
                f"{local}) — документы задачи не отправлены")
    return (f"отказ: {branch_name(task_id)} расходится с origin — локально "
            f"{local or '(нет)'}, в origin {remote}")


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
