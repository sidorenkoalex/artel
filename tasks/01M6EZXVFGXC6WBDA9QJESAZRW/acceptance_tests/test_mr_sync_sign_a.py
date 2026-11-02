"""Правило признака (а) `mr-sync`: у открытого MR `sha`, уже лежащий в `origin/<base>`, вливанием этого MR не считается (AC-14).

Группа: разовый
Зелёный с рождения: правило ANSWER-1 п. 3 Б2.2 уже держит `orchestrator/mr_sync.py:356` (`if mr.state == "merged"`), код `mr_sync.py` задача не меняет (требование 9) — метод сторожит правило и краснеет на мутации `state == "merged"` → `True`.

Почему разовый: стенд — `Stand` долгоживущего файла `mr-sync`
(`tests/test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_sync.py`), а долгоживущему
файлу помощники разрешены только из `tests/sandbox.py`. Долгоживущий тест
правила требование 9 поручает разработчику (`tests/`).

Сценарий: задача доведена до `awaiting_human` настоящим `approve` гейта
мержа (MR открыла подделка хостинга), `base` на сервере ушёл вперёд чужим
коммитом. Подделка отвечает на `mr_status` открытым MR, чей `sha` — коммит,
уже лежащий в `origin/<base>`; поля `merge_commit_sha`/`squash_commit_sha`
не заданы. Правки задачи в `base` нет. `artel.py mr-sync <id> --confirm`
без `--by-content` отказывает.

Провалидировано мутацией (внесена вручную в рабочую копию и откачена, не
закоммичена): `if mr.state == "merged":` → `if True:` на
`orchestrator/mr_sync.py:356` — `--confirm` закрывает задачу, метод красен.
"""
import pytest

from orchestrator import mr_sync, store
from tests import test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_sync as sync


@pytest.fixture
def stand(real_git):
    return sync.Stand(real_git)


@pytest.mark.parametrize("sha_at", ["точка ответвления", "голова base"])
def test_ac14_opened_mr_sha_in_base_is_not_sign_a(stand, sha_at):
    """Открытый MR с `sha` — предком `origin/<base>`: `mr-sync <id> --confirm` без `--by-content` отказывает, задача ждёт людей.

    Сценарий: задача в `awaiting_human`, `base` на сервере сдвинут чужим
    коммитом; ответ `mr_status` — `state: opened`, `sha` — точка
    ответвления задачи либо текущая голова `base` (обе в `origin/<base>`).
    `mr-sync <id> --confirm`: задача в `awaiting_human`, `closed_as` пуст,
    RETRO нет; в журнале — запись отказа `--confirm`.

    Ловит мутацию: `state == "merged"` → `True` в `orchestrator/mr_sync.py`
    — `sha` открытого MR засчитан признаком (а), итог «влит этим MR»,
    `--confirm` закрывает задачу `done`.
    """
    task = stand.to_awaiting()
    fork = stand.fork_at[task]
    head = stand.foreign_main()
    sha = fork if sha_at == "точка ответвления" else head
    stand.reply(task, state="opened", sha=sha)
    out = stand.mr_sync(task, "--confirm")
    where = stand.context(task, out) + f"\n--- sha MR {sha} ({sha_at})"
    sync.confirm_refused(stand, task, out)
    assert stand.state(task) == sync.STATE, where
    refused = [r for r in stand.rows(task)[stand.marks.get(task, 0):]
               if r["action"] == mr_sync.CONFIRM_REFUSED_ACTION]
    assert refused, where
    assert store.get_task(stand.conn, task)["closed_as"] in (None, ""), where
