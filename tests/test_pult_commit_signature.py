"""Подпись коммита пульта и запись «ветка отправлена» (SPEC 01M5WDB7JY0VJGHVKCABA2QC5T, требования 3-5, 15).

Свойства вне долгоживущих файлов задачи: запись «ветка отправлена»
прежнего вида (без двоеточия, до задачи) по-прежнему читается как последняя
отправка; трейлер пульта — последним абзацем при любой записи проекта, а
запись «коммит пульта» без `commit_author` не пишется.
"""
import pytest

from orchestrator import config, gitcmd, idgen, store, targets

ENTRY = """targets:
  {name}:
    description:
      base: {base}
      test_profile:
        command: [python3, -m, pytest]
        long_lived_dir: tests
        long_lived_name: test_<id>_<name>.py
    policy:
      no_paths: []
      project_skills: []
      merge_gate: operator
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
{policy}    machine:
      forge: github
      url: https://localhost/team/{name}
      token_slot: {name}-token
{machine}"""


@pytest.fixture
def task(initialized_tmp_root):
    task_id = idgen.new_task_id()
    store.insert_task(store.db(), task_id, "Задача", "in_dev", "task/x",
                      "qsign", config.DEFAULT_BUDGET_USD)
    return task_id


def write_project(policy: str = "", machine: str = "") -> None:
    local = targets.local_path()
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text(ENTRY.format(name="qsign", base=config.MAIN_BRANCH,
                                  policy=policy, machine=machine),
                     encoding="utf-8")
    assert targets.target("qsign")["forge"] == "github"


def test_legacy_sent_record_is_last_sent(task):
    """Запись «ветка отправлена» прежнего вида (до задачи) — по-прежнему последняя отправка.

    Ловит мутацию: `_last_sent_sha` читает только новое действие
    «ветка отправлена:» — у ветки, отправленной до задачи, записи
    отправки «нет», и перезапись своей ветки уходит в эскалацию «ветка на
    сервере без записи отправки».
    """
    sha = "a" * 40
    store.journal(store.db(), task, "orchestrator",
                  gitcmd.PUSH_SENT_LEGACY_ACTION, f"{sha} task/x")
    assert gitcmd.last_sent_sha(task) == sha
    newer = "b" * 40
    store.journal(store.db(), task, "orchestrator", gitcmd.PUSH_SENT_ACTION,
                  f"{newer} task/x")
    assert gitcmd.last_sent_sha(task) == newer


def test_trailer_without_commit_author_and_no_journal(task):
    """Без `commit_author`: трейлер — последним абзацем, автор прежний, записи «коммит пульта» нет.

    Ловит мутацию: трейлер ставится только при `commit_author` (у записи
    без поля его нет) либо запись «коммит пульта» пишется безусловно —
    журнал проекта без `commit_author` меняется.
    """
    write_project()
    message = gitcmd.pult_message("T: сообщение\n", "qsign")
    assert message.splitlines()[-1] == gitcmd.PULT_ACTOR_TRAILER
    assert message.startswith("T: сообщение\n\n")
    assert gitcmd.pult_identity_args("qsign") == []
    assert gitcmd.pult_identity("qsign", "N", "e@x") == ("N", "e@x")
    gitcmd.journal_pult_commit(store.db(), task, "qsign", "c" * 40, "чекпоинт")
    assert not [r for r in store.task_steps(store.db(), task)
                if r["action"] == gitcmd.PULT_COMMIT_ACTION]


def test_co_author_before_trailer_with_commit_author(task):
    """С `commit_author` и `co_author`: соавтор и трейлер — последний абзац, запись «коммит пульта» с sha.

    Ловит мутацию: строка соавтора не дописана (или дописана после
    трейлера вне последнего абзаца) либо запись «коммит пульта» не несёт
    sha коммита.
    """
    write_project('      co_author: "Co-authored-by: Соавтор <co@x.example>"\n',
                  "      commit_author:\n        name: pult\n"
                  "        email: pult@x.example\n")
    message = gitcmd.pult_message("T: сообщение", "qsign")
    assert message.split("\n\n")[-1].splitlines() == [
        "Co-authored-by: Соавтор <co@x.example>", gitcmd.PULT_ACTOR_TRAILER]
    assert gitcmd.pult_identity_args("qsign") == [
        "-c", "user.name=pult", "-c", "user.email=pult@x.example"]
    gitcmd.journal_pult_commit(store.db(), task, "qsign", "d" * 40, "сжатие")
    rows = [f"{r['action']} {r['detail']}" for r in store.task_steps(store.db(), task)
            if r["actor"] == "orchestrator"]
    assert f"коммит пульта: {'d' * 40} (сжатие)" in rows
