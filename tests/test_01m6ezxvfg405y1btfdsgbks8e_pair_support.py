"""Поддержка проекта решается парой (`forge`, `merge_gate`): `gitlab` + `target-human` поддержан, `github` + `target-human` и `gitlab` + `operator` — нет, с причиной, называющей гейт, хостинг и перечень поддержанных пар.

Группа: долгоживущий
Красен до реализации: в `orchestrator/targets.py` нет `SUPPORTED_PAIRS`, `SUPPORTED_FORGES`/`SUPPORTED_MERGE_GATES` — `("github",)`/`("operator",)`, `unsupported_reason` для `gitlab` + `target-human` возвращает «хостинг gitlab не поддержан: адаптера нет», а для неподдержанных пар — прежние тексты без перечня пар.

Связка, которую держит файл: «запись проекта в `targets.yaml` песочницы —
`targets.target`/`targets.unsupported_reason` — команда CLI `artel.py`
(`new`, `run`, `auto`, `approve`) — БД задач». Песочницы: `tmp_root`
(разбор записи), `initialized_tmp_root` (отказы команд; агент
`runner.spawn_agent` и переход `fsm.cmd_advance` подменены и при вызове
поднимают `Halt`), `light_transition` (позитивный `new` целиком без
настоящего git). Константы поддержки проверяются без песочницы.

Имена проектов порождаются модулем `random` при каждом запуске; зерно
печатается и входит в текст провала.
"""
import contextlib
import io
import random
import sys
from unittest import mock

import pytest

from orchestrator import artel, config, fsm, idgen, repo_context, runner, store, targets
from tests.sandbox import artel_target_entry

LETTERS = "abcdefghijkmnopqrstuvwxyz"


class Halt(Exception):
    """Подменённая зависимость вызвана: команда обрывается здесь."""


def project_name(rng: random.Random) -> str:
    return "q" + "".join(rng.choice(LETTERS) for _ in range(8))


def declare(name: str, forge: str, gate: str) -> None:
    """Дописывает плоскую запись проекта в `targets.yaml` песочницы."""
    text = (config.TARGETS.read_text(encoding="utf-8")
            if config.TARGETS.exists() else "targets:\n" + artel_target_entry())
    entry = (f"  {name}:\n    forge: {forge}\n"
             f"    url: https://localhost/team/{name}\n"
             f"    base: {config.MAIN_BRANCH}\n"
             f"    token_slot: {name}-token\n    no_paths: []\n"
             f"    project_skills: []\n    merge_gate: {gate}\n")
    config.TARGETS.write_text(text.rstrip("\n") + "\n" + entry, encoding="utf-8")


def declare_many(rng: random.Random, forge: str, gate: str, count: int) -> list:
    names = []
    while len(names) < count:
        name = project_name(rng)
        if name not in names:
            names.append(name)
            declare(name, forge, gate)
    return names


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


@pytest.fixture
def halted():
    """Агент и переход FSM подменены: вызов поднимает `Halt`."""
    with mock.patch.object(runner, "spawn_agent", side_effect=Halt("spawn_agent")) as spawn, \
            mock.patch.object(fsm, "cmd_advance", side_effect=Halt("cmd_advance")) as advance:
        yield {"spawn": spawn, "advance": advance}


def cli(*args: str) -> tuple:
    """`artel.py <args>`: (весь вывод вместе с текстом выхода, код выхода).
    Оборванная на подменённой зависимости команда — код `"Halt"`."""
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
        except Halt as exc:
            buf.write(f"\nHalt: {exc}")
            code = "Halt"
    return buf.getvalue(), code


def insert_task(name: str, state: str) -> str:
    task_id = idgen.new_task_id()
    store.insert_task(store.db(), task_id, "Задача проекта", state,
                      f"task/{task_id.lower()}-x", name, config.DEFAULT_BUDGET_USD)
    return task_id


def action_args(action: str, name: str) -> list:
    """Аргументы команды `action` для проекта `name`; задача — в БД."""
    if action == "new":
        return ["new", "Задача проекта", "--target", name]
    if action == "run":
        return ["run", insert_task(name, "in_dev"), "--attach"]
    if action == "auto":
        return ["auto", insert_task(name, "in_dev"), "--attach"]
    return ["approve", insert_task(name, "merge_gate")]


GHTH_REASON = ("гейт мержа target-human не поддержан для хостинга github "
               "(поддержаны: github + operator, gitlab + target-human)")
GLOP_REASON = ("гейт мержа operator не поддержан для хостинга gitlab "
               "(поддержаны: github + operator, gitlab + target-human)")


def refusal_note(seed, name, action, code, out, halted) -> str:
    return (f"зерно: {seed}; проект {name}; {action}; код {code}; "
            f"spawn {halted['spawn'].call_count}, advance {halted['advance'].call_count}\n{out}")


def check_refusal(seed, halted, forge, gate, reason, action) -> None:
    """Общий сценарий AC-2/AC-3: команда `action` проекта пары отказывает."""
    name = project_name(random.Random(seed))
    declare(name, forge, gate)
    out, code = cli(*action_args(action, name))
    note = refusal_note(seed, name, action, code, out, halted)
    assert code not in (0, "Halt"), note
    assert f"проект {name}: {reason}" in out, note
    assert f"проект {name}: проект {name}: " not in out, note
    assert halted["spawn"].call_count == 0, note
    assert halted["advance"].call_count == 0, note


# --- AC-1 ---

def test_ac1_gitlab_target_human_entry_supported(tmp_root, seed):
    """Запись `gitlab` + `target-human` загружается, причины неподдержки нет.

    Сценарий: в `targets.yaml` песочницы — три записи `gitlab` +
    `target-human` со случайными именами. Для каждой `targets.target`
    отдаёт запись с теми же `forge`/`merge_gate` без исключения, а
    `targets.unsupported_reason` возвращает `None`.

    Ловит мутацию: `SUPPORTED_PAIRS` без пары `("gitlab", "target-human")`
    или по-прежнему отдельная сверка `forge` с `("github",)` —
    `unsupported_reason` вернёт текст причины вместо `None`; отказ поставлен
    в проверку записи (`targets.check`) — `targets.target` поднимет
    `TargetsError`.
    """
    for name in declare_many(random.Random(seed), "gitlab", "target-human", 3):
        entry = targets.target(name)
        assert (entry["forge"], entry["merge_gate"]) == ("gitlab", "target-human"), \
            f"зерно: {seed}; {name}: {entry}"
        assert targets.unsupported_reason(name) is None, f"зерно: {seed}; {name}"


def test_ac1_gitlab_target_human_new_not_refused(light_transition, seed):
    """`new --target` проекта `gitlab` + `target-human` заводит задачу.

    Сценарий: в лёгкой песочнице переходов — запись `gitlab` +
    `target-human` со случайным именем и заранее заведённым каталогом
    клона. `artel.py new "<название>" --target <проект>` выходит с кодом 0,
    заводит ровно одну строку `tasks` этого проекта, в выводе нет текста
    отказа по поддержке («не поддержан»).

    Ловит мутацию: `unsupported_reason` для `gitlab` по-прежнему отвечает
    «адаптера нет» — `new` выйдет с «new: проект <имя>: … — задача не
    заведена», строки `tasks` не будет.
    """
    name = project_name(random.Random(seed))
    declare(name, "gitlab", "target-human")
    (repo_context.clone_path(name) / ".git").mkdir(parents=True, exist_ok=True)
    before = {r["id"] for r in store.all_tasks(store.db())}
    out, code = cli("new", "Задача проекта gitlab", "--target", name)
    created = [r for r in store.all_tasks(store.db()) if r["id"] not in before]
    note = f"зерно: {seed}; проект {name}; код {code}\n{out}"
    assert code == 0, note
    assert len(created) == 1 and created[0]["target"] == name, note
    assert "не поддержан" not in out, note


# --- AC-2 ---

def test_ac2_github_target_human_reason_exact(tmp_root, seed):
    """Запись `github` + `target-human` загружается, причина — ровно текст п. 3.

    Сценарий: три записи `github` + `target-human` со случайными именами;
    `targets.target` отдаёт каждую без исключения, `unsupported_reason`
    возвращает точный текст «гейт мержа target-human не поддержан для
    хостинга github (поддержаны: …)».

    Ловит мутацию: пара `github` + `target-human` попала в поддержанные
    (`unsupported_reason` решает по отдельным кортежам, где теперь есть
    `target-human`) — вернётся `None`; причина с префиксом «проект <имя>: »
    или прежний текст «не исполняется (ADR-0029)» — равенство не сойдётся.
    """
    for name in declare_many(random.Random(seed), "github", "target-human", 3):
        entry = targets.target(name)
        assert (entry["forge"], entry["merge_gate"]) == ("github", "target-human"), \
            f"зерно: {seed}; {name}: {entry}"
        assert targets.unsupported_reason(name) == GHTH_REASON, f"зерно: {seed}; {name}"


@pytest.mark.parametrize("action", ["new", "run", "auto", "approve"])
def test_ac2_github_target_human_actions_refuse(initialized_tmp_root, halted, seed, action):
    """Команды задачи проекта `github` + `target-human` отказывают причиной с одним префиксом.

    Сценарий: запись `github` + `target-human` со случайным именем; для
    `run`/`auto` задача заведена в БД в `in_dev`, для `approve` — в
    `merge_gate`. Команда выходит отказом (не кодом 0 и не дойдя до
    подменённых агента и `fsm.cmd_advance`), в выводе — `проект <имя>: `
    и следом полный текст причины п. 3, без удвоенного «проект <имя>:
    проект <имя>: ».

    Ловит мутацию: причина `unsupported_reason` сама начинается с «проект
    <имя>: » — вывод вызывающего удвоит префикс; пара открыта — команда
    дойдёт до агента/перехода (`Halt`) или `new` заведёт задачу с кодом 0.
    """
    check_refusal(seed, halted, "github", "target-human", GHTH_REASON, action)


# --- AC-3 ---

def test_ac3_gitlab_operator_reason_exact(tmp_root, seed):
    """Запись `gitlab` + `operator` загружается, причина — ровно текст п. 3.

    Сценарий: три записи `gitlab` + `operator` со случайными именами;
    `targets.target` отдаёт каждую без исключения, `unsupported_reason`
    возвращает точный текст «гейт мержа operator не поддержан для хостинга
    gitlab (поддержаны: …)».

    Ловит мутацию: решение по отдельным кортежам (`gitlab` в
    `SUPPORTED_FORGES`, `operator` в `SUPPORTED_MERGE_GATES`) — пара
    сочтётся поддержанной, вернётся `None`; остался текст «хостинг gitlab не
    поддержан: адаптера нет (ADR-0029)» — равенство не сойдётся.
    """
    for name in declare_many(random.Random(seed), "gitlab", "operator", 3):
        entry = targets.target(name)
        assert (entry["forge"], entry["merge_gate"]) == ("gitlab", "operator"), \
            f"зерно: {seed}; {name}: {entry}"
        assert targets.unsupported_reason(name) == GLOP_REASON, f"зерно: {seed}; {name}"


@pytest.mark.parametrize("action", ["new", "run", "auto", "approve"])
def test_ac3_gitlab_operator_actions_refuse(initialized_tmp_root, halted, seed, action):
    """Команды задачи проекта `gitlab` + `operator` отказывают причиной с одним префиксом.

    Сценарий: как у AC-2, для записи `gitlab` + `operator`: команда выходит
    отказом до агента и перехода, в выводе — `проект <имя>: ` и полный
    текст причины п. 3 для этой пары, без удвоения префикса.

    Ловит мутацию: пара `gitlab` + `operator` сочтена поддержанной
    (сверка по отдельным кортежам) — `new` заведёт задачу, `run`/`auto`/
    `approve` дойдут до агента/перехода; причина с собственным префиксом
    «проект <имя>: » — префикс в выводе удвоится.
    """
    check_refusal(seed, halted, "gitlab", "operator", GLOP_REASON, action)


# --- AC-4 ---

def test_ac4_support_constants_exact():
    """Константы поддержки — ровно значения требования 2.

    Сценарий: без песочницы читаются `targets.SUPPORTED_FORGES`,
    `targets.SUPPORTED_MERGE_GATES` и `targets.SUPPORTED_PAIRS` и
    сравниваются точным равенством с кортежами и множеством пар SPEC.

    Ловит мутацию: `SUPPORTED_FORGES` остался `("github",)` или
    `SUPPORTED_MERGE_GATES` — `("operator",)`; в `SUPPORTED_PAIRS` попала
    лишняя пара (`("gitlab", "operator")`) или константы нет вовсе —
    `AttributeError`.
    """
    assert targets.SUPPORTED_FORGES == ("github", "gitlab")
    assert targets.SUPPORTED_MERGE_GATES == ("operator", "target-human")
    assert targets.SUPPORTED_PAIRS == {("github", "operator"), ("gitlab", "target-human")}


@pytest.mark.parametrize("forge,gate,expected", [
    ("github", "target-human",
     "гейт мержа target-human не поддержан для хостинга github "
     "(поддержаны: github + operator, gitlab + target-human)"),
    ("gitlab", "operator",
     "гейт мержа operator не поддержан для хостинга gitlab "
     "(поддержаны: github + operator, gitlab + target-human)"),
], ids=["github-target-human", "gitlab-operator"])
def test_ac4_reason_text_names_pair_and_supported_list(tmp_root, seed, forge, gate, expected):
    """Текст причины неподдержанной пары называет её значения и перечень пар, без префикса.

    Сценарий: запись пары со случайным именем; текст `unsupported_reason`
    содержит значение `forge`, значение `merge_gate` и перечень
    «github + operator, gitlab + target-human», не начинается с «проект »,
    не содержит «адаптера нет» и точно равен тексту п. 3.

    Ловит мутацию: перечень собран не в порядке `sorted(SUPPORTED_PAIRS)`
    (обход множества) — порядок пар в тексте поплывёт; в шаблоне
    перепутаны `forge` и `merge_gate`; оставлена ветка «хостинг … не
    поддержан: адаптера нет».
    """
    name = project_name(random.Random(seed))
    declare(name, forge, gate)
    reason = targets.unsupported_reason(name)
    note = f"зерно: {seed}; {name}: {reason!r}"
    assert reason is not None, note
    assert forge in reason and gate in reason, note
    assert "github + operator, gitlab + target-human" in reason, note
    assert not reason.startswith("проект "), note
    assert "адаптера нет" not in reason, note
    assert reason == expected, note


# --- AC-7 ---

def test_ac7_artel_and_github_operator_supported(tmp_root, seed):
    """Артель и проекты `github` + `operator` по-прежнему поддержаны.

    Сценарий: в `targets.yaml` песочницы — артель и три записи `github` +
    `operator` со случайными именами; `unsupported_reason` для артели и
    для каждой записи возвращает `None`.

    Ловит мутацию: в `SUPPORTED_PAIRS` вместо `("github", "operator")`
    записана перевёрнутая пара `("operator", "github")` или сверка идёт по
    `(merge_gate, forge)` — проекты GitHub и сама артель получат причину
    отказа.
    """
    names = declare_many(random.Random(seed), "github", "operator", 3)
    for name in [config.DEFAULT_TARGET, *names]:
        assert targets.unsupported_reason(name) is None, f"зерно: {seed}; {name}"
