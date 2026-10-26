"""Внешние ссылки задач и эпиков: `new --ref`, `link` и `link --remove`,
поля проекта `policy.ref_required`/`policy.ref_systems`, отказы `new` до
побочных эффектов, наследование ссылок частями деления, ссылки в модели
доски.

Группа: долгоживущий
Красен до реализации: команды `link` в `artel.py` нет («Неизвестная команда link»), `new` не знает флага `--ref`, таблицы `external_refs` нет, у карточек и эпиков модели нет поля `refs`, поля `ref_required`/`ref_systems` раздела `policy` записи проекта `targets.py` отвергает; модуль `orchestrator/board.py` придёт в ветку только подтяжкой main с Э1.

Держит связку «команда CLI `artel.py` — БД — модель доски»: сценарий
идёт через `artel.main()` в лёгкой песочнице переходов
(`light_transition`). Ссылка документов задачи `refs/artifacts/<id>` в этой
песочнице пишется вызовом `update-ref` через подменённый `in_repo` — его
записывает хук `in_repo_handlers`. Проект с полями `policy` — запись
локального слоя (`targets.local_path()`) в трёх разделах; его клон —
заранее заведённый каталог `workspace.repo(<проект>)` с `.git`. Строки
`external_refs` и элементы `refs` сверяются по значениям (объект,
система, ключ, URL, `operator`, время записи): имена их полей SPEC не
задаёт. Системы, ключи, названия и проекты порождаются модулем `random`
при каждом запуске; зерно печатается и входит в текст провала.
"""
import contextlib
import importlib
import io
import random
import re
import sys
from unittest import mock

import pytest

from orchestrator import artel, catalog, config, idgen, store, targets, workspace
from tests.sandbox import capture_new_task_id, declare_target

OTHER_PROJECTS = ("vega", "orion", "lyra", "draco")
WORDS = ("Ольха", "Ясень", "Клён", "Вяз", "Липа", "Граб", "Осина", "Рябина",
         "Ива", "Бук", "Кедр", "Пихта")
SYSTEMS = ("kaiten", "jira", "youtrack", "gitlab-issue", "redmine", "trello")
ROLE_STATES = ("spec_writing", "tests_writing", "in_dev", "review")
TIME = re.compile(r"\d{4}-\d\d-\d\d")
FIRST = "первая, без зависимостей"


# --- окружение сценария ---

@pytest.fixture
def stand(light_transition):
    """Лёгкая песочница переходов: зерно, второй проект в `targets.yaml`,
    запись вызовов `update-ref` ссылок документов."""
    light_transition.seed = random.randrange(1 << 30)
    print(f"зерно: {light_transition.seed}")
    light_transition.rng = random.Random(light_transition.seed)
    light_transition.other = light_transition.rng.choice(OTHER_PROJECTS)
    declare_target(light_transition.other)
    make_clone(light_transition.other)
    light_transition.artifact_refs = []
    light_transition.in_repo_handlers.append(
        artifact_ref_recorder(light_transition.artifact_refs))
    return light_transition


def artifact_ref_recorder(log: list):
    """Хук `in_repo` песочницы: запоминает ссылки `refs/artifacts/…`, которые
    пишет `update-ref`, и отдаёт вызов дальше (`None`)."""
    def handler(repo, *args):
        if "update-ref" in args:
            log.extend(a for a in args if str(a).startswith("refs/artifacts/"))
        return None
    return handler


def board():
    """Модуль модели доски — импортом при вызове: модуль тестов обязан
    собираться и там, где модели ещё нет."""
    return importlib.import_module("orchestrator.board")


def note(stand, text: str) -> str:
    return f"зерно: {stand.seed}; {text}"


def cli(*args: str) -> tuple[str, int]:
    """`artel.py <args>`: (весь вывод вместе с текстом выхода, код выхода)."""
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


def words(stand, count: int = 2) -> str:
    return " ".join(stand.rng.sample(WORDS, count))


def ref_key(stand) -> str:
    return f"{stand.rng.choice(['', 'ABC-', 'T'])}{stand.rng.randrange(10, 10 ** 6)}"


def task_ids() -> set:
    return {r["id"] for r in store.all_tasks(store.db())}


def epics() -> dict:
    return {r["id"]: dict(r) for r in store.db().execute("SELECT * FROM epics")}


def epic_new(stand, project: str) -> str:
    before = set(epics())
    out, code = cli("epic", "new", project, f"Эпик {words(stand)}",
                    "--goal", f"Цель {words(stand, 3)}")
    added = set(epics()) - before
    assert len(added) == 1, note(stand, f"предпосылка: epic new ({code}):\n{out}")
    return added.pop()


def insert_task(stand, project: str, state: str | None = None) -> str:
    task_id = idgen.new_task_id()
    store.insert_task(store.db(), task_id, f"Задача {words(stand)}",
                      state or stand.rng.choice(ROLE_STATES),
                      f"task/{task_id.lower()}-x", project,
                      config.DEFAULT_BUDGET_USD)
    return task_id


def make_clone(project: str) -> None:
    """Каталог клона проекта с `.git`: `new` его не клонирует, ссылка
    документов пишется в него через подменённый `in_repo`."""
    (workspace.repo(project) / ".git").mkdir(parents=True, exist_ok=True)


def policy_project(stand, *, required: str | None = None,
                   systems: list | None = None) -> str:
    """Внешний проект локального слоя с полями `policy.ref_required` и/или
    `policy.ref_systems`; каталог его клона заведён заранее."""
    name = f"pol{stand.rng.randrange(10 ** 6)}"
    extra = ""
    if required is not None:
        extra += f"      ref_required: {required}\n"
    if systems is not None:
        extra += f"      ref_systems: [{', '.join(systems)}]\n"
    entry = (f"  {name}:\n"
             f"    description:\n      base: {config.MAIN_BRANCH}\n"
             f"      test_profile:\n        command: [python3, -m, pytest]\n"
             f"        long_lived_dir: tests\n"
             f"        long_lived_name: test_<id>_<name>.py\n"
             f"    policy:\n      no_paths: []\n      project_skills: []\n"
             f"      merge_gate: operator\n"
             f"      weakening_scope: [tests/**/*.py]\n"
             f"      mutation_claim_scope: [tests/test_*.py]\n{extra}"
             f"    machine:\n      forge: github\n"
             f"      url: https://localhost/team/{name}\n"
             f"      token_slot: {name}-token\n")
    local = targets.local_path()
    local.parent.mkdir(parents=True, exist_ok=True)
    text = local.read_text(encoding="utf-8") if local.exists() else "targets:\n"
    local.write_text(text + entry, encoding="utf-8")
    make_clone(name)
    return name


def ref_rows() -> list[tuple]:
    return [tuple(r) for r in store.db().execute(
        "SELECT * FROM external_refs ORDER BY rowid")]


def rows_of(obj: str, system: str, key: str) -> list[tuple]:
    return [r for r in ref_rows() if obj in r and system in r and key in r]


def new(stand, project: str, *flags: str) -> dict:
    """`new "<название>" --target <проект> <flags>`: вывод, код, заведённые
    задачи, новые ссылки документов, строки `external_refs` до и после."""
    before_ids, before_refs = task_ids(), len(stand.artifact_refs)
    before_rows = ref_rows()
    out, code = cli("new", f"Новая {words(stand)}", "--target", project, *flags)
    return {"out": out, "code": code, "created": task_ids() - before_ids,
            "artifacts": stand.artifact_refs[before_refs:],
            "rows_before": before_rows, "rows_after": ref_rows()}


def assert_new_refused_clean(stand, result: dict, what: str) -> None:
    """`new` отказал и ничего не оставил: ни строки задачи, ни ссылки
    документов, ни строки `external_refs`."""
    assert result["code"] != 0, note(stand, f"{what}: new не отказал:\n{result['out']}")
    assert result["created"] == set(), note(
        stand, f"{what}: заведены {result['created']}:\n{result['out']}")
    assert result["artifacts"] == [], note(
        stand, f"{what}: ссылки документов {result['artifacts']}")
    assert result["rows_after"] == result["rows_before"], note(
        stand, f"{what}: external_refs {result['rows_after']}")


def created_one(stand, result: dict, what: str) -> str:
    assert result["code"] == 0 and len(result["created"]) == 1, note(
        stand, f"{what}: new ({result['code']}):\n{result['out']}")
    return next(iter(result["created"]))


def model(project: str) -> dict:
    return board().build_model(store.db(), project)


def card_refs(stand, project: str, task_id: str) -> list:
    found = [c for c in model(project)["cards"] if c["task"] == task_id]
    assert len(found) == 1, note(stand, f"карточек {task_id}: {len(found)}")
    return found[0]["refs"]


def epic_refs(stand, project: str, epic_id: str) -> list:
    found = [e for e in model(project)["epics"] if e["id"] == epic_id]
    assert len(found) == 1, note(stand, f"эпиков {epic_id}: {len(found)}")
    return found[0]["refs"]


def matching(refs: list, system: str, key: str) -> list:
    return [r for r in refs if system in r.values() and key in r.values()]


def written_at(ref: dict) -> bool:
    return any(isinstance(v, str) and TIME.search(v) for v in ref.values())


def link(stand, kind: str, obj: str, system: str, key: str, *flags: str) -> None:
    out, code = cli("link", kind, obj, system, key, *flags)
    assert code == 0, note(stand, f"предпосылка: link {kind} {obj} {system} "
                                  f"{key} ({code}):\n{out}")


# --- AC-9 ---

def test_ac9_new_ref_is_stored_and_shown_with_author_and_time(stand):
    """`new … --ref <система>:<ключ>` заводит задачу и строку `external_refs`; в `cards[].refs` её карточки — ссылка с этими системой и ключом, пустым URL, автором `operator` и непустым временем записи.

    Ловит мутацию: `--ref` разбирается, но ссылка не записывается (или
    пишется без автора/времени); автор ссылки — `orchestrator`, а не
    `operator`.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.other])
    system, key = stand.rng.choice(SYSTEMS), ref_key(stand)
    task_id = created_one(stand, new(stand, project, "--ref", f"{system}:{key}"),
                          "new --ref")
    assert rows_of(task_id, system, key), note(stand, f"строк {ref_rows()}")
    found = matching(card_refs(stand, project, task_id), system, key)
    assert len(found) == 1, note(stand, f"refs {card_refs(stand, project, task_id)}")
    ref = found[0]
    assert "operator" in ref.values(), note(stand, f"автор: {ref}")
    assert written_at(ref), note(stand, f"время записи: {ref}")
    assert None in ref.values() or "" in ref.values(), note(stand, f"URL: {ref}")


def test_ac9_new_with_two_refs_stores_both(stand):
    """`new` с двумя `--ref` разных систем записывает обе ссылки — обе видны в `cards[].refs` задачи.

    Ловит мутацию: повторённый `--ref` перезаписывает прежнее значение
    (берётся последний флаг) — первая ссылка теряется.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.other])
    pairs = [(s, ref_key(stand)) for s in stand.rng.sample(SYSTEMS, 2)]
    flags = [x for s, k in pairs for x in ("--ref", f"{s}:{k}")]
    task_id = created_one(stand, new(stand, project, *flags), "new с двумя --ref")
    refs = card_refs(stand, project, task_id)
    for system, key in pairs:
        assert matching(refs, system, key), note(stand, f"нет {system}:{key}: {refs}")
        assert rows_of(task_id, system, key), note(stand, f"строк {ref_rows()}")


def test_ac9_ref_is_split_on_first_colon(stand):
    """`new --ref gitlab-issue:<группа>/<проект>:<номер>` записывает систему `gitlab-issue` и ключ `<группа>/<проект>:<номер>` целиком.

    Ловит мутацию: значение делится по последнему «:» (`rsplit`) —
    система `gitlab-issue:<группа>/<проект>`, ключ `<номер>`; или
    `split(":")` без предела — ключ обрезан до `<группа>/<проект>`.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.other])
    key = (f"{stand.rng.choice(['grp', 'team', 'core'])}/"
           f"{stand.rng.choice(['proj', 'api', 'web'])}:{stand.rng.randrange(1, 9999)}")
    task_id = created_one(stand, new(stand, project, "--ref", f"gitlab-issue:{key}"),
                          "new --ref gitlab-issue:…")
    refs = card_refs(stand, project, task_id)
    assert matching(refs, "gitlab-issue", key), note(stand, f"refs {refs}")
    assert rows_of(task_id, "gitlab-issue", key), note(stand, f"строк {ref_rows()}")


def test_ac9_ref_without_colon_refused_before_side_effects(stand):
    """`new --ref <система><ключ>` без «:» отказывает с причиной: нет ни строки задачи, ни строки `external_refs`, ни ссылки `refs/artifacts/<id>`.

    Ловит мутацию: значение без «:» принимается системой с пустым ключом
    (задача заводится); проверка `--ref` стоит после создания ссылки
    документов — `update-ref` уже записан.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.other])
    value = f"{stand.rng.choice(SYSTEMS)}{stand.rng.randrange(10, 10 ** 5)}"
    result = new(stand, project, "--ref", value)
    assert_new_refused_clean(stand, result, f"--ref {value}")
    assert result["out"].strip(), note(stand, "отказ без причины")


def test_ac9_ref_is_written_before_task_worktree(stand):
    """В момент вызова заведения ветки и рабочей копии задачи (`workspace.ensure`, его зовёт `catalog._ensure_task_worktree`) строка `external_refs` этой задачи уже есть в БД.

    Ловит мутацию: ссылки пишутся после `_ensure_task_worktree` (в конце
    `cmd_new`, рядом с `merge_after.record_declared`) — в момент создания
    ветки строки ещё нет.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.other])
    system, key = stand.rng.choice(SYSTEMS), ref_key(stand)
    seen = []
    real_ensure = workspace.ensure

    def ensure(task_id, branch):
        seen.append((task_id, rows_of(task_id, system, key)))
        return real_ensure(task_id, branch)

    with mock.patch.object(workspace, "ensure", ensure):
        task_id = created_one(stand, new(stand, project, "--ref", f"{system}:{key}"),
                              "new --ref")
    calls = [rows for tid, rows in seen if tid == task_id]
    assert calls, note(stand, f"workspace.ensure не вызван для {task_id}: {seen}")
    assert calls[0], note(stand, "на создании ветки ссылки в БД ещё нет")


# --- AC-10 ---

def test_ac10_link_task_with_url_in_write_order(stand):
    """Две `link task` одной задачи — первая с `--url`: обе видны в `cards[].refs` в порядке записи (не по алфавиту системы), у первой — этот URL, автор обеих — `operator`.

    Ловит мутацию: `refs` упорядочены по системе или ключу (`ORDER BY
    system`) — первая записанная ссылка с «большей» системой уходит
    второй; `--url` не сохраняется; автор `link` — не `operator`.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.other])
    task_id = insert_task(stand, project)
    late, early = sorted(stand.rng.sample(SYSTEMS, 2), reverse=True)
    first, second = (late, ref_key(stand)), (early, ref_key(stand))
    url = f"https://localhost/tracker/{first[1]}"
    link(stand, "task", task_id, *first, "--url", url)
    link(stand, "task", task_id, *second)
    refs = card_refs(stand, project, task_id)
    positions = [[i for i, r in enumerate(refs) if s in r.values() and k in r.values()]
                 for s, k in (first, second)]
    assert [len(p) for p in positions] == [1, 1], note(stand, f"refs {refs}")
    assert positions[0][0] < positions[1][0], note(stand, f"порядок refs {refs}")
    assert url in matching(refs, *first)[0].values(), note(stand, f"URL: {refs}")
    assert all("operator" in r.values() for r in refs), note(stand, f"автор: {refs}")


def test_ac10_link_epic_shows_in_epic_refs(stand):
    """`link epic <id> <система> <ключ>` добавляет ссылку эпику: она видна в `epics[].refs` модели его проекта.

    Ловит мутацию: `link epic` пишет ссылку видом `task` (или модель
    не читает ссылки эпиков) — в `epics[].refs` её нет.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.other])
    epic_id = epic_new(stand, project)
    system, key = stand.rng.choice(SYSTEMS), ref_key(stand)
    link(stand, "epic", epic_id, system, key)
    refs = epic_refs(stand, project, epic_id)
    assert matching(refs, system, key), note(stand, f"epics[].refs {refs}")


def test_ac10_repeated_link_adds_no_second_row(stand):
    """Повторный `link` той же системы и того же ключа тому же объекту не добавляет вторую строку `external_refs` и вторую ссылку в `refs`.

    Ловит мутацию: `link` вставляет строку без проверки дубля (нет
    `UNIQUE`/`INSERT OR IGNORE`) — строк и элементов `refs` становится две.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.other])
    task_id = insert_task(stand, project)
    system, key = stand.rng.choice(SYSTEMS), ref_key(stand)
    for _ in range(stand.rng.randint(2, 3)):
        cli("link", "task", task_id, system, key)
    assert len(rows_of(task_id, system, key)) == 1, note(stand, f"строк {ref_rows()}")
    assert len(matching(card_refs(stand, project, task_id), system, key)) == 1


def test_ac10_remove_link_and_refuse_missing(stand):
    """`link --remove task <id> <система> <ключ>` снимает ссылку — в модели и в `external_refs` её нет, соседняя остаётся; `--remove` несуществующей ссылки отказывает с причиной.

    Ловит мутацию: `--remove` снимает все ссылки задачи (без условия на
    систему и ключ); `--remove` несуществующей ссылки тихо завершается
    кодом 0.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.other])
    task_id = insert_task(stand, project)
    gone_sys, kept_sys = stand.rng.sample(SYSTEMS, 2)
    gone, kept = (gone_sys, ref_key(stand)), (kept_sys, ref_key(stand))
    link(stand, "task", task_id, *gone)
    link(stand, "task", task_id, *kept)
    out, code = cli("link", "--remove", "task", task_id, *gone)
    assert code == 0, note(stand, f"link --remove ({code}):\n{out}")
    refs = card_refs(stand, project, task_id)
    assert not matching(refs, *gone) and matching(refs, *kept), note(stand, f"refs {refs}")
    assert not rows_of(task_id, *gone) and rows_of(task_id, *kept), note(
        stand, f"строк {ref_rows()}")
    out, code = cli("link", "--remove", "task", task_id, *gone)
    assert code != 0 and out.strip(), note(stand, f"повторный --remove ({code}):\n{out}")


@pytest.mark.parametrize("kind", ["task", "epic"])
def test_ac10_link_to_unknown_object_refused(stand, kind):
    """`link task|epic <id> …` на id, которого нет в БД, отказывает ненулевым кодом, и `external_refs` не меняется.

    Ловит мутацию: `link` пишет строку без проверки существования
    объекта (внешний ключ не проверяется) — в `external_refs` появляется
    висячая ссылка.
    """
    ghost = idgen.new_task_id() if kind == "task" else f"E{idgen.new_task_id()}"
    before = ref_rows()
    out, code = cli("link", kind, ghost, stand.rng.choice(SYSTEMS), ref_key(stand))
    assert code != 0, note(stand, f"link {kind} {ghost} не отказал:\n{out}")
    assert ref_rows() == before, note(stand, f"строк {ref_rows()}")


# --- AC-11 ---

def test_ac11_ref_required_refuses_new_without_it(stand):
    """Проект с `policy.ref_required: <система>`: `new` без `--ref` этой системы (без `--ref` или со ссылкой другой системы) отказывает с причиной, называющей систему, — ни задачи, ни ссылки документов; с `--ref <система>:<ключ>` — заводится.

    Ловит мутацию: `ref_required` проверяется после создания ссылки
    документов (`update-ref` записан); любая ссылка любой системы
    засчитывается требуемой; отказ не называет систему.
    """
    required, other = stand.rng.sample(SYSTEMS, 2)
    project = policy_project(stand, required=required)
    flags = stand.rng.choice([[], ["--ref", f"{other}:{ref_key(stand)}"]])
    result = new(stand, project, *flags)
    assert_new_refused_clean(stand, result, f"без --ref {required} ({flags})")
    assert required in result["out"], note(stand, f"отказ без системы:\n{result['out']}")
    key = ref_key(stand)
    task_id = created_one(stand, new(stand, project, "--ref", f"{required}:{key}"),
                          f"--ref {required}")
    assert rows_of(task_id, required, key), note(stand, f"строк {ref_rows()}")


def test_ac11_canary_task_skips_ref_required(stand):
    """Учебная задача канарейки (`catalog.cmd_new(canary=True)`) в проект с `ref_required` заводится без ссылки.

    Ловит мутацию: проверка `ref_required` стоит в `cmd_new` без условия
    `not canary` — канареечная задача получает отказ.
    """
    project = policy_project(stand, required=stand.rng.choice(SYSTEMS))
    before = task_ids()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        task_id = catalog.cmd_new(f"Канарейка {words(stand)}", canary=True,
                                  target=project)
    assert task_ids() - before == {task_id}, note(stand, f"задачи:\n{buf.getvalue()}")
    assert store.get_task(store.db(), task_id)["target"] == project


def test_ac11_remove_of_last_required_ref_refused(stand):
    """У задачи проекта с `ref_required` одна ссылка требуемой системы: `link --remove` её отказывает с причиной, называющей систему, — ссылка остаётся в `external_refs` и `cards[].refs`; при второй ссылке той же системы `--remove` одной снимает её.

    Ловит мутацию: `--remove` не сверяется с `ref_required` (последняя
    требуемая ссылка снимается); проверка считает все ссылки задачи, а не
    ссылки требуемой системы, или запрещает снимать любую ссылку системы.
    """
    required = stand.rng.choice(SYSTEMS)
    project = policy_project(stand, required=required)
    first = ref_key(stand)
    task_id = created_one(stand, new(stand, project, "--ref", f"{required}:{first}"),
                          f"--ref {required}")
    out, code = cli("link", "--remove", "task", task_id, required, first)
    assert code != 0 and required in out, note(stand, f"--remove последней ({code}):\n{out}")
    assert rows_of(task_id, required, first), note(stand, f"строк {ref_rows()}")
    assert matching(card_refs(stand, project, task_id), required, first)

    second = ref_key(stand)
    link(stand, "task", task_id, required, second)
    gone = stand.rng.choice([first, second])
    out, code = cli("link", "--remove", "task", task_id, required, gone)
    assert code == 0, note(stand, f"--remove при двух ({code}):\n{out}")
    assert not rows_of(task_id, required, gone), note(stand, f"строк {ref_rows()}")
    assert not matching(card_refs(stand, project, task_id), required, gone)


# --- AC-12 ---

def test_ac12_ref_systems_limits_new_and_link(stand):
    """Проект с `policy.ref_systems`: `new --ref` и `link` системы вне списка отказывают и ничего не пишут (после отказа `new` нет ни задачи, ни ссылки документов); системы из списка — записываются.

    Ловит мутацию: список проверяется только у `new` (у `link` нет) или
    только у `link`; проверка `new` стоит после создания ссылки
    документов.
    """
    allowed = stand.rng.sample(SYSTEMS, 2)
    outsider = stand.rng.choice([s for s in SYSTEMS if s not in allowed])
    project = policy_project(stand, systems=allowed)
    result = new(stand, project, "--ref", f"{outsider}:{ref_key(stand)}")
    assert_new_refused_clean(stand, result, f"new --ref {outsider}")

    task_id = insert_task(stand, project)
    before = ref_rows()
    out, code = cli("link", "task", task_id, outsider, ref_key(stand))
    assert code != 0, note(stand, f"link {outsider} не отказал:\n{out}")
    assert ref_rows() == before, note(stand, f"строк {ref_rows()}")

    key = ref_key(stand)
    created = created_one(stand, new(stand, project, "--ref", f"{allowed[0]}:{key}"),
                          f"new --ref {allowed[0]}")
    assert rows_of(created, allowed[0], key), note(stand, f"строк {ref_rows()}")
    key = ref_key(stand)
    link(stand, "task", task_id, allowed[1], key)
    assert rows_of(task_id, allowed[1], key), note(stand, f"строк {ref_rows()}")


def test_ac12_any_nonempty_system_without_list(stand):
    """Проект без `policy.ref_systems`: `new --ref` и `link` принимают любую непустую систему, не известную пульту заранее.

    Ловит мутацию: системы сверяются со встроенным перечнем (например,
    только `kaiten`/`gitlab-issue`) даже без поля проекта.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.other])
    system = f"own-{stand.rng.randrange(10 ** 6)}"
    key = ref_key(stand)
    task_id = created_one(stand, new(stand, project, "--ref", f"{system}:{key}"),
                          f"new --ref {system}")
    assert rows_of(task_id, system, key), note(stand, f"строк {ref_rows()}")
    system, key = f"else-{stand.rng.randrange(10 ** 6)}", ref_key(stand)
    link(stand, "task", task_id, system, key)
    assert rows_of(task_id, system, key), note(stand, f"строк {ref_rows()}")


@pytest.mark.parametrize("command,empty", [("new", "system"), ("new", "key"),
                                           ("link", "system"), ("link", "key")])
def test_ac12_empty_system_or_key_refused(stand, command, empty):
    """Пустая система (`new --ref :<ключ>`, `link task <id> '' <ключ>`) и пустой ключ (`new --ref <система>:`, `link task <id> <система> ''`) отказывают с причиной и ничего не пишут; после отказа `new` нет ни задачи, ни ссылки документов.

    Ловит мутацию: пустая строка системы или ключа принимается
    (проверка «не None» вместо «не пусто») — строка `external_refs`
    с пустым полем записывается.
    """
    project = stand.rng.choice([config.DEFAULT_TARGET, stand.other])
    system = "" if empty == "system" else stand.rng.choice(SYSTEMS)
    key = "" if empty == "key" else ref_key(stand)
    if command == "new":
        result = new(stand, project, "--ref", f"{system}:{key}")
        assert_new_refused_clean(stand, result, f"new --ref {system}:{key}")
        assert result["out"].strip(), note(stand, "отказ без причины")
        return
    task_id = insert_task(stand, project)
    before = ref_rows()
    out, code = cli("link", "task", task_id, system, key)
    assert code != 0 and out.strip(), note(stand, f"link '{system}' '{key}' ({code}):\n{out}")
    assert ref_rows() == before, note(stand, f"строк {ref_rows()}")


# --- AC-13 ---

def spec_text(task_id: str, zone: str, parts: list) -> str:
    """SPEC родителя с секцией «## Деление» на части `parts`."""
    orders = [FIRST] + [f"после части {n}" for n in range(1, len(parts))]
    division = "".join(
        f"### {title}\n\nЗоны: {zone}\nПорядок: {order}\n\n"
        f"Текст ТЗ части «{title}».\n\n"
        for title, order in zip(parts, orders))
    return f"""---
task: {task_id}
type: spec
author_role: analyst
status: ready
schema_version: 5
budget_usd: 15
zones: {zone}
---

# SPEC: Родитель деления

## Контекст
Фикстура деления со ссылками.

## Требования
1. Фикстура.

## Критерии приёмки
AC-1. Фикстура.

## Оценка объёма и деление
Фикстура.

## Деление

{division}## Не входит
- Всё остальное.
"""


def test_ac13_division_parts_copy_parent_refs(stand):
    """Родитель на гейте SPEC с делением и ссылками (записаны в прошлом, остановленными часами): после `approve` каждая часть несёт в `cards[].refs` те же ссылки — система, ключ, URL, автор и время записи родителя.

    Ловит мутацию: части заводятся без ссылок родителя (`spawn_subtask`
    не копирует `external_refs`); копия пишется с новым временем
    (`store.now()` в момент деления) или автором `orchestrator`.
    """
    _, parent = capture_new_task_id(catalog.cmd_new, f"Родитель {words(stand, 3)}")
    parts = [f"Часть {w}" for w in stand.rng.sample(WORDS, stand.rng.randint(2, 3))]
    folder = stand.tdir.parent / parent
    folder.mkdir(parents=True, exist_ok=True)
    zone = f"orchestrator/t_refs_division_{stand.rng.randrange(10 ** 6)}.py"
    (folder / "SPEC.md").write_text(spec_text(parent, zone, parts), encoding="utf-8")
    conn = store.db()
    conn.execute("UPDATE tasks SET state='spec_gate' WHERE id=?", (parent,))
    conn.commit()

    pairs = [(s, ref_key(stand)) for s in stand.rng.sample(SYSTEMS, 2)]
    url = f"https://localhost/tracker/{pairs[0][1]}"
    past = f"20{stand.rng.randrange(10, 20)}-0{stand.rng.randrange(1, 9)}-11 10:00:00Z"
    with mock.patch.object(store, "now", lambda: past):
        link(stand, "task", parent, *pairs[0], "--url", url)
        link(stand, "task", parent, *pairs[1])

    out, code = cli("approve", parent)
    children = [r["id"] for r in store.all_tasks(store.db())
                if r["parent_task_id"] == parent]
    assert len(children) == len(parts), note(stand, f"части {children} ({code}):\n{out}")

    def own(refs: list, owner: str) -> list:
        return [{k: v for k, v in r.items() if v != owner} for r in refs]

    expected = own(card_refs(stand, config.DEFAULT_TARGET, parent), parent)
    assert len(expected) == 2, note(stand, f"предпосылка: refs родителя {expected}")
    for child in children:
        got = own(card_refs(stand, config.DEFAULT_TARGET, child), child)
        assert got == expected, note(stand, f"часть {child}: {got}\n!= {expected}")
