"""Копия эпика в ссылке `refs/artifacts/epic-<id>` репозитория проекта
эпика: запись и одна отправка на команду `epic …`, отказ и восстановление
отправки, неудача записи без клона, `epic export`, `epic restore`, отказ
`promote` по проверке ТЗ пути `new`.

Группа: долгоживущий
Красен до реализации: (на ветке до подтяжки main с шагом Э1 — таблицы `epics` нет) команды `epic …` ссылку `refs/artifacts/epic-<id>` не пишут и не отправляют (чтение её дерева падает), подкоманд `epic draft`, `epic decision`, `epic export`, `epic restore` нет, а таблиц `epic_drafts` и `epic_decisions` в схеме нет.

Держит связку «команда CLI `artel.py` — БД — git проекта — его origin»:
песочница — настоящий git (`real_git`, `tests/fixtures.py`): пульт и клон
артели — репозиторий песочницы с синхронным origin, проект эпика — не
`artel`, свой клон с голым origin (`make_project_repo`). Шпион стоит на
`subprocess.run`, которым пульт запускает git; отправка ссылки эпика —
`git push` с аргументом `refs/artifacts/epic-…`. Дерево ссылки читается
`git ls-tree`/`git show` помощником песочницы. Форма Markdown файлов
ссылки SPEC не задаёт — сверяется, что в файле есть значения состояния
БД. Имена колонок таблиц черновиков и решений SPEC не называет — строки
находятся по значениям. Проекты, названия, тексты и рамки порождаются
модулем `random` при каждом запуске; зерно печатается и входит в текст
провала.
"""
import contextlib
import io
import os
import random
import sqlite3
import subprocess
import sys
from unittest import mock

import pytest

from orchestrator import artel, config, idgen, store
from tests.sandbox import declare_target, make_project_repo, strip_dash_c

LETTERS = "abcdefghijklmnopqrstuvwxyz"
WORDS = ("Ольха", "Ясень", "Клён", "Вяз", "Липа", "Граб", "Осина", "Рябина",
         "Ива", "Бук", "Кедр", "Пихта")
EPIC_REF_PREFIX = "refs/artifacts/epic-"
# Действие записи журнала об отказе отправки ссылки документов задачи —
# требование 12 называет тот же текст и для ссылки эпика.
PUSH_FAILED = "push артефактной ветки FAILED"
TABLES = ("tasks", "epics", "epic_drafts", "epic_decisions", "steps", "leases")


# --- окружение сценария ---

@pytest.fixture
def stand(real_git):
    """Пульт с синхронным origin артели и проект эпика (не `artel`) с
    клоном и голым origin; зерно сценария."""
    sb = real_git
    sb.seed = random.randrange(1 << 30)
    print(f"зерно: {sb.seed}")
    sb.rng = random.Random(sb.seed)
    env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
    env.start()
    sb.addCleanup(env.stop)
    sb.artel_origin = sb.add_synced_origin()
    sb.project = "p" + "".join(sb.rng.choice(LETTERS) for _ in range(7))
    sb.clone = make_project_repo(sb.project)
    sb.bare = config.PROJECTS / sb.project / "origin.git"
    return sb


def note(stand, text: str) -> str:
    return f"зерно: {stand.seed}; {text}"


def words(stand, count: int = 2) -> str:
    return " ".join(stand.rng.sample(WORDS, count))


def marker(stand) -> str:
    return f"{stand.rng.randrange(1 << 40):x}"


@contextlib.contextmanager
def git_calls():
    """Подкоманды git (без пар `-C <путь>`) всех запусков внутри блока."""
    calls = []
    real = subprocess.run

    def spy(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and cmd and cmd[0] == "git":
            calls.append(tuple(str(c) for c in strip_dash_c(cmd[1:])))
        return real(cmd, *args, **kwargs)

    with mock.patch.object(subprocess, "run", side_effect=spy):
        yield calls


def epic_pushes(calls) -> list:
    return [c for c in calls if c and c[0] == "push"
            and any(EPIC_REF_PREFIX in a for a in c[1:])]


def cli(*args: str) -> tuple[str, int, int]:
    """`artel.py <args>`: (весь вывод с текстом выхода, код выхода, число
    отправок ссылки эпика)."""
    buf = io.StringIO()
    code = 0
    with git_calls() as calls, \
            mock.patch.object(sys, "argv", ["artel.py", *args]), \
            contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            artel.main()
        except SystemExit as exc:
            code = exc.code or 0
            if isinstance(code, str):
                buf.write(f"\n{code}")
                code = 1
    return buf.getvalue(), code, len(epic_pushes(calls))


def epic_ref(epic_id: str) -> str:
    return f"{EPIC_REF_PREFIX}{epic_id}"


def local_head(stand, ref: str, repo=None) -> str:
    return stand.git("-C", str(repo or stand.clone), "for-each-ref",
                     "--format=%(objectname)", ref).strip()


def origin_head(stand, ref: str, bare=None) -> str:
    out = stand.git("ls-remote", str(bare or stand.bare), ref).split()
    return out[0] if out else ""


def ref_paths(stand, ref: str, repo=None) -> list[str]:
    return stand.git("-C", str(repo or stand.clone), "ls-tree", "-r",
                     "--name-only", ref).splitlines()


def ref_file(stand, ref: str, path: str, repo=None) -> str:
    return stand.git("-C", str(repo or stand.clone), "show", f"{ref}:{path}")


def rows(table: str) -> list[dict]:
    return [dict(r) for r in store.db().execute(f"SELECT * FROM {table}")]


def epic_rows() -> dict:
    return {r["id"]: r for r in rows("epics")}


def rows_of(table: str, epic_id: str) -> list[dict]:
    return [r for r in rows(table) if epic_id in r.values()]


def snapshot() -> dict:
    conn = store.db()
    return {t: [tuple(r) for r in conn.execute(f"SELECT * FROM {t} ORDER BY rowid")]
            for t in TABLES}


def task_ids() -> set:
    return {r["id"] for r in store.all_tasks(store.db())}


def set_state(task_id: str, state: str) -> None:
    conn = store.db()
    conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
    conn.commit()


def insert_task(stand, project: str | None = None) -> str:
    task_id = idgen.new_task_id()
    store.insert_task(store.db(), task_id, f"Задача {words(stand)}", "in_dev",
                      f"task/{task_id.lower()}-x", project or stand.project,
                      config.DEFAULT_BUDGET_USD)
    return task_id


def epic_new(stand, project: str | None = None, *flags: str) -> tuple[str, dict]:
    """`epic new`: (id эпика, {"title", "goal", "out", "pushes"})."""
    before = set(epic_rows())
    title, goal = f"Эпик {words(stand, 3)} {marker(stand)}", f"Цель {words(stand, 3)}"
    out, code, pushes = cli("epic", "new", project or stand.project, title,
                            "--goal", goal, *flags)
    added = set(epic_rows()) - before
    assert len(added) == 1, note(stand, f"предпосылка: epic new ({code}):\n{out}")
    return added.pop(), {"title": title, "goal": goal, "out": out,
                         "pushes": pushes, "code": code}


def tz_file(stand, *, body: str | None = None,
            trailing_newline: bool = True) -> tuple[str, str, str]:
    """Файл ТЗ: (путь, название — первый заголовок `# `, полный текст)."""
    title = f"Черновик {words(stand)} {marker(stand)}"
    text = body if body is not None else (
        f"Источник: фикстура {stand.seed}.\n\nТребуется:\n"
        f"1. Поправить {words(stand, 3)} {marker(stand)}.\n")
    text = f"# {title}\n\n{text}"
    if not trailing_newline:
        text = text.rstrip("\n")
    path = stand.root / ".artel" / f"tz-{marker(stand)}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path), title, text


def draft_add(stand, epic_id: str, *flags: str, **tz) -> dict:
    path, title, text = tz_file(stand, **tz)
    out, code, pushes = cli("epic", "draft", "add", epic_id, "--tz", path, *flags)
    assert [r for r in rows_of("epic_drafts", epic_id) if title in r.values()], \
        note(stand, f"предпосылка: epic draft add ({code}):\n{out}")
    return {"title": title, "text": text, "out": out, "pushes": pushes}


def promote(stand, address: str) -> str:
    before = task_ids()
    out, code, _ = cli("epic", "draft", "promote", address)
    created = task_ids() - before
    assert len(created) == 1, note(
        stand, f"предпосылка: promote {address} ({code}):\n{out}")
    return created.pop()


def lines_in(text: str, content: str) -> bool:
    """Каждая непустая строка `text` есть в `content`."""
    return all(line.strip() in content for line in text.splitlines()
               if line.strip())


def epic_artel_refs(stand) -> list[str]:
    """Ссылки эпиков в клоне артели и в его origin."""
    local = stand.git("for-each-ref", "--format=%(refname)",
                      "refs/artifacts/").splitlines()
    remote = [line.split()[-1] for line in stand.git(
        "ls-remote", str(stand.artel_origin)).splitlines() if line.strip()]
    return [r for r in local + remote if r.startswith(EPIC_REF_PREFIX)]


# --- AC-7 ---

def test_ac7_every_changing_command_writes_and_sends_ref_once(stand):
    """Каждая команда требования 11 на эпике проекта не `artel`: ровно одна отправка ссылки эпика, голова в origin равна новой локальной, дерево несёт `EPIC.md`, `DECISIONS.md` и `drafts/<n>.md` каждого черновика со значениями БД после команды; в клоне и origin артели ссылок эпика нет.

    Ловит мутацию: одна из команд (`epic remove`, `epic envelope`,
    `epic draft drop`, `epic decision`) не пишет ссылку — голова не
    сдвинулась; команда внутри lease задачи (`epic add`) отправляет
    ссылку на каждом коммите — две отправки; ссылка пишется до
    изменения БД и несёт прежнее состояние; ссылка эпика уходит в
    клон артели, а не в репозиторий проекта эпика.
    """
    epic_id, info = epic_new(stand)
    ref = epic_ref(epic_id)
    member = insert_task(stand)
    drafts: dict = {}
    state = {"head": ""}
    envelope = str(stand.rng.randint(300, 899))
    first_frame, second_frame = "12.25", f"{stand.rng.randint(13, 89)}.75"
    decision = f"Решение {words(stand, 3)} {marker(stand)}"
    outcome = f"Итог {words(stand, 3)} {marker(stand)}"

    def check(label: str, pushes: int, out: str) -> str:
        """Одна отправка, новая голова равна origin, файлы на месте, поля
        строки `epics` в `EPIC.md`; возвращает текст `EPIC.md`."""
        detail = f"{label}:\n{out}"
        assert pushes == 1, note(stand, f"отправок ссылки эпика {pushes}; {detail}")
        head = local_head(stand, ref)
        assert head and head != state["head"], note(
            stand, f"голова не сдвинулась; {detail}")
        assert origin_head(stand, ref) == head, note(stand, f"origin ≠ локальной; {detail}")
        state["head"] = head
        paths = set(ref_paths(stand, ref))
        base = f"epics/{epic_id}"
        needed = {f"{base}/EPIC.md", f"{base}/DECISIONS.md"} | {
            f"{base}/drafts/{n}.md" for n in drafts}
        assert needed <= paths, note(stand, f"нет {needed - paths}; {detail}")
        epic_md = ref_file(stand, ref, f"{base}/EPIC.md")
        epic_row = epic_rows()[epic_id]
        for field in ("id", "project", "title", "goal", "state", "created_at",
                      "outcome", "closed_at"):
            if epic_row[field] is not None:
                assert str(epic_row[field]) in epic_md, note(
                    stand, f"EPIC.md без {field}={epic_row[field]!r}; {detail}\n{epic_md}")
        return epic_md

    check("epic new", info["pushes"], info["out"])

    new_title = f"Новое {words(stand, 3)} {marker(stand)}"
    steps = [("edit", ("epic", "edit", epic_id, "--title", new_title),
              lambda epic_md: new_title in epic_md),
             ("envelope", ("epic", "envelope", epic_id, envelope),
              lambda epic_md: envelope in epic_md),
             ("add", ("epic", "add", epic_id, member),
              lambda epic_md: member in epic_md),
             ("remove", ("epic", "remove", epic_id, member),
              lambda epic_md: member not in epic_md),
             ("add again", ("epic", "add", epic_id, member),
              lambda epic_md: member in epic_md)]
    for label, args, reflects in steps:
        out, code, pushes = cli(*args)
        epic_md = check(label, pushes, out)
        assert reflects(epic_md), note(
            stand, f"{label}: EPIC.md не отражает БД ({code}):\n{out}\n{epic_md}")

    path, title, text = tz_file(stand)
    out, code, pushes = cli("epic", "draft", "add", epic_id, "--tz", path,
                            "--budget", first_frame)
    drafts[1] = title
    check("draft add", pushes, out)
    content = ref_file(stand, ref, f"epics/{epic_id}/drafts/1.md")
    assert title in content and lines_in(text, content) and "draft" in content, \
        note(stand, f"drafts/1.md:\n{content}")

    out, code, pushes = cli("epic", "draft", "edit", f"{epic_id}/1", "--budget",
                            second_frame)
    check("draft edit", pushes, out)
    content = ref_file(stand, ref, f"epics/{epic_id}/drafts/1.md")
    assert second_frame in content and first_frame not in content, note(
        stand, f"drafts/1.md после edit:\n{content}")

    path, title, text = tz_file(stand)
    out, code, pushes = cli("epic", "draft", "add", epic_id, "--tz", path)
    drafts[2] = title
    check("draft add 2", pushes, out)
    out, code, pushes = cli("epic", "draft", "drop", f"{epic_id}/2")
    check("draft drop", pushes, out)
    content = ref_file(stand, ref, f"epics/{epic_id}/drafts/2.md")
    assert "dropped" in content, note(stand, f"drafts/2.md после drop:\n{content}")

    before = task_ids()
    out, code, pushes = cli("epic", "draft", "promote", f"{epic_id}/1")
    created = task_ids() - before
    assert len(created) == 1, note(stand, f"promote ({code}):\n{out}")
    result = created.pop()
    check("draft promote", pushes, out)
    content = ref_file(stand, ref, f"epics/{epic_id}/drafts/1.md")
    assert "promoted" in content and result in content, note(
        stand, f"drafts/1.md после promote:\n{content}")
    assert result in ref_file(stand, ref, f"epics/{epic_id}/EPIC.md"), note(
        stand, "EPIC.md без задачи из promote")

    out, code, pushes = cli("epic", "decision", epic_id, decision, "--for",
                            f"{epic_id}/1")
    check("decision", pushes, out)
    assert decision in ref_file(stand, ref, f"epics/{epic_id}/DECISIONS.md"), \
        note(stand, "DECISIONS.md без решения")

    set_state(member, "done")
    set_state(result, "done")
    out, code, pushes = cli("epic", "close", epic_id, outcome)
    assert epic_rows()[epic_id]["state"] == "closed", note(stand, f"close:\n{out}")
    check("close", pushes, out)
    assert outcome in ref_file(stand, ref, f"epics/{epic_id}/EPIC.md")

    assert epic_artel_refs(stand) == [], note(
        stand, f"ссылки эпика у артели: {epic_artel_refs(stand)}")


# --- AC-8 ---

def test_ac8_refused_and_read_only_commands_keep_ref_head(stand):
    """Отказавшие `epic close` (задача не окончательна), `epic draft edit` отброшенного черновика, `epic decision --for` без черновика, `epic draft add` с несуществующей задачей в перечне, а также `epic show` и `epic export` не меняют голову ссылки эпика ни локально, ни в origin.

    Ловит мутацию: ссылка пишется до проверки, которая затем отказывает
    (голова сдвинута при отказе); `epic show`/`epic export` пишут или
    отправляют ссылку.
    """
    epic_id, _ = epic_new(stand)
    ref = epic_ref(epic_id)
    member = insert_task(stand)
    cli("epic", "add", epic_id, member)
    draft_add(stand, epic_id)
    draft_add(stand, epic_id)
    cli("epic", "draft", "drop", f"{epic_id}/2")
    cli("epic", "decision", epic_id, f"Решение {marker(stand)}")
    heads = (local_head(stand, ref), origin_head(stand, ref))
    assert heads[0] and heads[0] == heads[1], note(stand, f"предпосылка: {heads}")
    path, _, _ = tz_file(stand)

    refused = [("epic", "close", epic_id, f"Итог {words(stand)}"),
               ("epic", "draft", "edit", f"{epic_id}/2", "--budget", "7.5"),
               ("epic", "decision", epic_id, f"Решение {marker(stand)}", "--for",
                f"{epic_id}/{stand.rng.randint(5, 99)}"),
               ("epic", "draft", "add", epic_id, "--tz", path, "--start-after",
                idgen.new_task_id())]
    stand.rng.shuffle(refused)
    for args in refused:
        out, code, _ = cli(*args)
        assert code != 0, note(stand, f"предпосылка: {args} не отказал:\n{out}")
        assert (local_head(stand, ref), origin_head(stand, ref)) == heads, note(
            stand, f"{args} сдвинул голову:\n{out}")
    for args in (("epic", "show", epic_id), ("epic", "export", epic_id)):
        out, code, pushes = cli(*args)
        assert (local_head(stand, ref), origin_head(stand, ref)) == heads, note(
            stand, f"{args} сдвинул голову:\n{out}")
        assert pushes == 0, note(stand, f"{args} отправил ссылку")


# --- AC-9, AC-21: отказ отправки ---

def failed_pushes(epic_id: str) -> list[dict]:
    return [dict(r) for r in store.task_steps(store.db(), epic_id)
            if r["action"] == PUSH_FAILED]


def changing_command(stand, epic_id: str):
    """Случайная команда, меняющая эпик, и проверка её изменения в БД."""
    title = f"Название {marker(stand)}"
    decision = f"Решение {marker(stand)}"
    choices = [
        (("epic", "edit", epic_id, "--title", title),
         lambda: epic_rows()[epic_id]["title"] == title),
        (("epic", "decision", epic_id, decision),
         lambda: any(decision in r.values()
                     for r in rows_of("epic_decisions", epic_id))),
    ]
    return stand.rng.choice(choices)


def test_ac9_unavailable_origin_then_next_command_sends(stand):
    """origin проекта недоступен: команда, меняющая эпик, завершается кодом 0, изменение в БД, отказ отправки в журнале эпика; после восстановления origin следующая такая команда отправляет ссылку, и голова в origin равна локальной.

    Ловит мутацию: отказ отправки откатывает команду или роняет её
    ненулевым кодом; отказ не пишется в журнал; после отказа ссылка
    помечена отправленной, и следующая команда её не отправляет
    (origin отстаёт от локальной).
    """
    epic_id, _ = epic_new(stand)
    ref = epic_ref(epic_id)
    hidden = stand.bare.with_name("origin-offline.git")
    stand.bare.rename(hidden)
    failed_before = len(failed_pushes(epic_id))
    args, changed = changing_command(stand, epic_id)

    out, code, _ = cli(*args)

    assert code == 0, note(stand, f"команда при недоступном origin ({code}):\n{out}")
    assert changed(), note(stand, f"изменение БД потеряно:\n{out}")
    assert len(failed_pushes(epic_id)) > failed_before, note(
        stand, f"отказ отправки не в журнале: "
               f"{[dict(r) for r in store.task_steps(store.db(), epic_id)]}")

    hidden.rename(stand.bare)
    args, changed = changing_command(stand, epic_id)
    out, code, pushes = cli(*args)
    assert changed(), note(stand, f"вторая команда ({code}):\n{out}")
    assert pushes >= 1, note(stand, "после восстановления origin отправки нет")
    head = local_head(stand, ref)
    assert head and origin_head(stand, ref) == head, note(
        stand, "ссылка в origin не равна локальной")


def reject_epic_refs(stand) -> None:
    hook = stand.bare / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\nwhile read o n r; do case \"$r\" in "
                    f"{EPIC_REF_PREFIX}*) exit 1;; esac; done\nexit 0\n",
                    encoding="utf-8")
    hook.chmod(0o755)


def test_ac21_push_failure_journal_has_epic_id_and_project(stand):
    """origin отвергает ссылку эпика: запись отказа отправки в журнале с `task_id` — id эпика, `target` — проект эпика (не `artel`).

    Ловит мутацию: отказ пишется журналом под `epic-<id>` (имя ссылки)
    или без `target` — запись несёт проект по умолчанию; отказ не
    пишется вовсе.
    """
    epic_id, _ = epic_new(stand)
    reject_epic_refs(stand)
    args, changed = changing_command(stand, epic_id)

    out, code, _ = cli(*args)

    assert changed(), note(stand, f"команда ({code}):\n{out}")
    failed = failed_pushes(epic_id)
    assert failed, note(stand, f"отказ отправки не записан под {epic_id}:\n{out}")
    assert {r["target"] for r in failed} == {stand.project}, note(
        stand, f"target записей отказа: {[r['target'] for r in failed]}")
    assert not failed_pushes(f"epic-{epic_id}")


def test_ac21_each_listed_command_sends_ref_once(stand):
    """`epic new`, `epic edit`, `epic close`, `epic add`, `epic remove`, `epic draft add`, `epic decision` — каждая ровно одна отправка ссылки эпика в origin, в том числе без lease задачи; lease по id эпика нет.

    Ловит мутацию: команды без lease задачи не открывают область
    отложенной отправки — отправка на каждом коммите ссылки (две и
    больше на команду); `epic add`/`epic remove` отправляют ссылку и
    внутри, и после области — две отправки.
    """
    epic_id, info = epic_new(stand)
    counts = {"new": info["pushes"]}
    member = insert_task(stand)
    runs = [("edit", ("epic", "edit", epic_id, "--goal", f"Цель {marker(stand)}")),
            ("add", ("epic", "add", epic_id, member)),
            ("remove", ("epic", "remove", epic_id, member)),
            ("add", ("epic", "add", epic_id, member))]
    for label, args in runs:
        out, code, counts[label] = cli(*args)
    counts["draft add"] = draft_add(stand, epic_id)["pushes"]
    cli("epic", "draft", "drop", f"{epic_id}/1")
    out, code, counts["decision"] = cli("epic", "decision", epic_id,
                                        f"Решение {marker(stand)}")
    set_state(member, "done")
    out, code, counts["close"] = cli("epic", "close", epic_id, f"Итог {marker(stand)}")
    assert epic_rows()[epic_id]["state"] == "closed", note(stand, f"close:\n{out}")

    assert all(n == 1 for n in counts.values()), note(stand, f"отправки: {counts}")
    assert store.lease_row(store.db(), epic_id) is None
    ref = epic_ref(epic_id)
    assert origin_head(stand, ref) == local_head(stand, ref) != ""


# --- AC-22 ---

def normalized(out: str, *pairs) -> set:
    for value, placeholder in pairs:
        out = out.replace(value, placeholder)
    return {line.strip() for line in out.splitlines() if line.strip()}


def test_ac22_write_failure_without_clone_keeps_db_and_next_command_writes(stand):
    """Проект эпика объявлен без клона: `epic new` заводит эпик, печатает строку, которой нет в выводе той же команды при клоне, и пишет запись журнала эпика с действием, которого нет у той же команды при клоне; после появления клона следующая `epic edit` пишет ссылку с состоянием БД после неё.

    Ловит мутацию: неудача записи ссылки роняет команду с откатом БД
    (эпика нет); неудача проглочена молча — ни предупреждения, ни
    записи журнала; следующая команда пишет ссылку, только если её не
    было (не догоняет), или пишет состояние до правки.
    """
    with_clone, info = epic_new(stand)
    clone_actions = {r["action"] for r in store.task_steps(store.db(), with_clone)}
    lonely = "q" + "".join(stand.rng.choice(LETTERS) for _ in range(7))
    declare_target(lonely)

    epic_id, lone = epic_new(stand, lonely)

    assert epic_rows()[epic_id]["title"] == lone["title"], note(stand, "эпика нет")
    base = normalized(info["out"], (with_clone, "<E>"), (stand.project, "<P>"),
                      (info["title"], "<T>"), (info["goal"], "<G>"))
    lines = normalized(lone["out"], (epic_id, "<E>"), (lonely, "<P>"),
                       (lone["title"], "<T>"), (lone["goal"], "<G>"))
    assert lines - base, note(stand, f"нет предупреждения:\n{lone['out']}")
    actions = {r["action"] for r in store.task_steps(store.db(), epic_id)}
    assert actions - clone_actions, note(
        stand, f"нет записи журнала о неудаче записи: {actions} ⊆ {clone_actions}")

    clone = make_project_repo(lonely)
    title = f"После клона {marker(stand)}"
    out, code, _ = cli("epic", "edit", epic_id, "--title", title)
    ref = epic_ref(epic_id)
    assert local_head(stand, ref, clone), note(stand, f"ссылки нет ({code}):\n{out}")
    epic_md = ref_file(stand, ref, f"epics/{epic_id}/EPIC.md", clone)
    assert title in epic_md and lone["goal"] in epic_md, note(
        stand, f"EPIC.md не несёт состояние после edit:\n{epic_md}")


# --- AC-10 ---

def test_ac10_export_prints_every_ref_file_verbatim_in_order(stand):
    """Эпик с 10–12 черновиками и решениями: вывод `epic export` содержит дословно `EPIC.md`, затем `drafts/<n>.md` по возрастанию `<n>` (10 после 9), затем `DECISIONS.md` — тексты файлов ссылки.

    Ловит мутацию: черновики идут лексикографически (`10.md` раньше
    `2.md`); `export` собирает Markdown своим кодом, отличным от записи
    ссылки (текст расходится с файлом); `DECISIONS.md` не печатается.
    """
    epic_id, _ = epic_new(stand)
    count = stand.rng.randint(10, 12)
    for n in range(count):
        flags = ("--budget", f"{stand.rng.randint(5, 50)}.5") if n % 2 else ()
        draft_add(stand, epic_id, *flags)
    cli("epic", "draft", "drop", f"{epic_id}/{stand.rng.randint(1, count)}")
    for _ in range(2):
        cli("epic", "decision", epic_id, f"Решение {words(stand)} {marker(stand)}")

    out, code, _ = cli("epic", "export", epic_id)

    ref, base = epic_ref(epic_id), f"epics/{epic_id}"
    order = ([f"{base}/EPIC.md"] + [f"{base}/drafts/{n}.md"
                                    for n in range(1, count + 1)]
             + [f"{base}/DECISIONS.md"])
    position = 0
    for path in order:
        text = ref_file(stand, ref, path)
        found = out.find(text, position)
        assert found >= 0, note(stand, f"{path} нет дословно после позиции "
                                       f"{position} ({code}):\n{text}\n---\n{out}")
        position = found + len(text)


# --- AC-12, AC-13, AC-14: epic restore ---

def build_restore_source(stand) -> dict:
    """Два эпика проекта: открытый без конверта (черновик без рамки с ТЗ,
    кончающимся переводом строки; черновик с рамкой и перечнями, ТЗ без
    хвостового перевода строки; решение с пробелами и переводом строки) и
    закрытый с конвертом (черновики `promoted` и `dropped` с рамками,
    решения по конверту и по задаче)."""
    body = (f"Источник: фикстура {stand.seed}.\n\nТребуется:\n1. Пункт.\n\n"
            f"## Раздел {marker(stand)}\n\n---\n\n# Ещё заголовок\n\nХвост.\n")
    first, _ = epic_new(stand)
    draft_add(stand, first, body=body)
    x, y = insert_task(stand), insert_task(stand)
    second_body = body.replace("Хвост.", f"Хвост {marker(stand)}.")
    draft_add(stand, first, "--budget", "23.75", "--start-after", x, "--after", y,
              body=second_body, trailing_newline=False)
    spaced = f"  Решение с пробелами {marker(stand)} \n  и второй строкой  "
    cli("epic", "decision", first, spaced)
    cli("epic", "decision", first, f"По черновику {marker(stand)}", "--for",
        f"{first}/1")

    second, _ = epic_new(stand, None, "--envelope", "55")
    member = insert_task(stand)
    cli("epic", "add", second, member)
    draft_add(stand, second, "--budget", "9.5")
    result = promote(stand, f"{second}/1")
    draft_add(stand, second, "--budget", "4.25")
    cli("epic", "draft", "drop", f"{second}/2")
    cli("epic", "decision", second, f"По конверту {marker(stand)}", "--for",
        "envelope")
    cli("epic", "decision", second, f"По задаче {marker(stand)}", "--for", member)
    set_state(member, "done")
    set_state(result, "done")
    out, code, _ = cli("epic", "close", second, f"Итог {marker(stand)}")
    assert epic_rows()[second]["state"] == "closed", note(stand, f"close:\n{out}")
    return {"open": first, "closed": second, "spaced": spaced}


def epic_state(epic_id: str) -> dict:
    return {"epics": [epic_rows().get(epic_id)],
            "epic_drafts": sorted(map(repr, rows_of("epic_drafts", epic_id))),
            "epic_decisions": sorted(map(repr, rows_of("epic_decisions", epic_id)))}


@contextlib.contextmanager
def empty_db(stand):
    """`config.DB` на время блока — новая БД со свежей схемой без строк."""
    path = stand.root / ".artel" / f"restore-{marker(stand)}.db"
    conn = sqlite3.connect(path)
    store.create_schema(conn)
    conn.commit()
    conn.close()
    with mock.patch.object(config, "DB", path):
        yield


def test_ac12_restore_recreates_rows_equal_to_source(stand):
    """`epic restore <проект> <id>` на БД без строк эпика воссоздаёт `epics`, `epic_drafts`, `epic_decisions` обоих эпиков равными исходным по всем полям: ТЗ с `# `, `## `, `---` с хвостовым переводом строки и без него, решение с пробелами и переводом строки, `NULL` и заданные рамка, конверт, итог, `closed_at`.

    Ловит мутацию: разбор ссылки режет ТЗ по строке `---` или `## `
    (текст короче); хвостовой перевод строки теряется или добавляется;
    `NULL` рамки или конверта воссоздаётся `0` либо пустой строкой;
    время решения или `created_at` эпика берутся текущими, а не из
    ссылки; поле (`merge_after`, задача-результат) не попадает в
    ссылку и воссоздаётся пустым.
    """
    made = build_restore_source(stand)
    source = {key: epic_state(made[key]) for key in ("open", "closed")}
    assert source["open"]["epics"][0]["envelope_usd"] is None
    assert source["closed"]["epics"][0]["closed_at"] is not None

    with empty_db(stand):
        assert epic_rows() == {}, note(stand, "предпосылка: БД не пуста")
        for key in ("open", "closed"):
            out, code, _ = cli("epic", "restore", stand.project, made[key])
            assert epic_state(made[key]) == source[key], note(
                stand, f"restore {key} ({code}):\n{out}\n"
                       f"{epic_state(made[key])}\n≠\n{source[key]}")


def test_ac13_second_restore_changes_nothing(stand):
    """Повторный `epic restore` той же ссылки на БД, уже воссозданной первым, не меняет ни одной таблицы БД.

    Ловит мутацию: повторный `restore` вставляет решения второй раз
    (решения без естественного ключа дублируются) или перезаписывает
    строки с новым временем.
    """
    made = build_restore_source(stand)
    epic_id = stand.rng.choice([made["open"], made["closed"]])
    with empty_db(stand):
        out, code, _ = cli("epic", "restore", stand.project, epic_id)
        assert epic_rows(), note(stand, f"предпосылка: первый restore ({code}):\n{out}")
        before = snapshot()
        out, code, _ = cli("epic", "restore", stand.project, epic_id)
        assert snapshot() == before, note(stand, f"повторный restore ({code}):\n{out}")


def column_holding(table: str, epic_id: str, value) -> tuple[int, str]:
    """(rowid, имя колонки) строки `table` эпика, где лежит `value`."""
    for r in store.db().execute(f"SELECT rowid AS fixture_rowid, * FROM {table}"):
        row = dict(r)
        if epic_id in row.values():
            for name, item in row.items():
                if name != "fixture_rowid" and item == value:
                    return row["fixture_rowid"], name
    raise LookupError(f"{value!r} нет в {table}")


@pytest.mark.parametrize("table", ["epics", "epic_drafts", "epic_decisions"])
def test_ac14_restore_refuses_on_divergence_and_keeps_db(stand, table):
    """Строка эпика (черновика, решения) в БД расходится со ссылкой: `epic restore` отказывает, называя таблицу и поле расхождения; БД не меняется.

    Ловит мутацию: `restore` перезаписывает расходящуюся строку
    значением из ссылки; сверяет только наличие строк, а не поля
    (расхождение не замечено); отказ без перечня (таблица и поле не
    названы).
    """
    made = build_restore_source(stand)
    epic_id = made["open"]
    conn = store.db()
    if table == "epics":
        rowid, column = column_holding("epics", epic_id, epic_rows()[epic_id]["goal"])
    elif table == "epic_drafts":
        draft = rows_of("epic_drafts", epic_id)[0]
        text = next(v for v in draft.values() if isinstance(v, str)
                    and v.startswith("# "))
        rowid, column = column_holding(table, epic_id, text)
    else:
        rowid, column = column_holding(table, epic_id, made["spaced"])
    conn.execute(f"UPDATE {table} SET {column}=? WHERE rowid=?",
                 (f"Правка мимо ссылки {marker(stand)}", rowid))
    conn.commit()
    before = snapshot()

    out, code, _ = cli("epic", "restore", stand.project, epic_id)

    assert code != 0, note(stand, f"restore при расхождении не отказал:\n{out}")
    assert table in out and column in out, note(
        stand, f"отказ не называет {table}.{column}:\n{out}")
    assert snapshot() == before, note(stand, f"restore изменил БД:\n{out}")


# --- AC-4 ---

def test_ac4_promote_refused_by_new_tz_check(stand):
    """ТЗ черновика ссылается на файл, которого нет в дереве проекта: `promote` отказывает теми же строками отказа `tz_check`, что `new` с этим ТЗ; задача не заводится, черновик — `draft`.

    Ловит мутацию: `promote` заводит задачу мимо пути `new` (без
    `tz_check`) — задача с битой ссылкой ТЗ заведена; черновик
    переводится в `promoted` до проверки и остаётся таким после отказа.
    """
    missing = f"src/absent_{marker(stand)}.py:{stand.rng.randint(2, 40)}"
    body = (f"Источник: фикстура {stand.seed}.\n\nТребуется:\n"
            f"1. Поправить функцию в `{missing}`.\n")
    path, title, _ = tz_file(stand, body=body)
    before = task_ids()
    out, code, _ = cli("new", f"Проверка {marker(stand)}", "--tz", path,
                       "--target", stand.project)
    refusals = [line.strip() for line in out.splitlines() if "отказ:" in line]
    assert task_ids() == before and refusals, note(
        stand, f"предпосылка: new с битой ссылкой ТЗ не отказал ({code}):\n{out}")

    epic_id, _ = epic_new(stand)
    out, code, _ = cli("epic", "draft", "add", epic_id, "--tz", path)
    draft = [r for r in rows_of("epic_drafts", epic_id) if title in r.values()]
    assert draft, note(stand, f"предпосылка: draft add ({code}):\n{out}")

    out, code, _ = cli("epic", "draft", "promote", f"{epic_id}/1")

    assert code != 0, note(stand, f"promote не отказал:\n{out}")
    for line in refusals:
        assert line in out, note(stand, f"нет причины «{line}»:\n{out}")
    assert task_ids() == before, note(stand, "задача заведена")
    row = [r for r in rows_of("epic_drafts", epic_id) if title in r.values()][0]
    assert "draft" in row.values(), note(stand, f"черновик после отказа: {row}")
