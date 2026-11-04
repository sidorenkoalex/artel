"""AC-10 — AC-13: команда пульта `task-rm` — удаление файлов в пределах своей задачи.

Группа: разовый
Сценарии держат связку «диспетчер `artel.main()` — БД задачи — рабочая копия
и ссылка документов в git дублёра» и читают закрытое имя
`artel._ROLE_ALLOWED_COMMANDS` (AC-13), а правило долгоживущих файлов
`tests/` запрещает и закрытые имена, и вызов git через `subprocess`
(`scripts/guard.py::long_lived_sign_hits`); поэтому файл — в планке.

Команда зовётся в процессе теста (`artel.main()` с подменённым `sys.argv`)
над дублёром ROOT (`_doubler.Doubler`): задачи `OWN`/`OTHER` в БД
дублёра, их рабочие копии в клоне, каталог документов `OWN` и ссылка
документов `refs/artifacts/OWN` с `tasks/OWN/SPEC.md`.

Красен до реализации: команды `task-rm` в диспетчере `orchestrator/artel.py` ещё нет — под признаком роли она отказывает «команда недоступна процессу роли», без признака — неизвестная команда; файлы не удаляются, миссии ролей её не называют.
"""
import os
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _doubler import OTHER, OWN, Doubler  # noqa: E402

from orchestrator import artel, brief, config, review, role_prompt, store  # noqa: E402


@pytest.fixture
def pult(tmp_path, monkeypatch):
    return Doubler(tmp_path, monkeypatch)


def _task_rm(monkeypatch, task_id: str, *paths) -> int:
    """`artel.py task-rm <id> <путь>…` в процессе теста; код выхода."""
    monkeypatch.setattr(sys, "argv", ["artel.py", "task-rm", task_id,
                                      *[str(p) for p in paths]])
    try:
        artel.main()
    except SystemExit as exc:
        if exc.code is None or exc.code == 0:
            return 0
        return exc.code if isinstance(exc.code, int) else 1
    return 0


def _as_role(monkeypatch, sign: str, task: str | None) -> None:
    """Признак роли: "role" — `ARTEL_ROLE`; "home" — `HOME`, равный дому роли, без `ARTEL_ROLE`."""
    if sign == "role":
        monkeypatch.setenv(config.ARTEL_ROLE_ENV, "test_author")
    else:
        monkeypatch.delenv(config.ARTEL_ROLE_ENV, raising=False)
        monkeypatch.setenv("HOME", str(config.ROLE_HOME))
    if task is None:
        monkeypatch.delenv(config.ARTEL_TASK_ENV, raising=False)
    else:
        monkeypatch.setenv(config.ARTEL_TASK_ENV, task)


def _write(path: Path, text: str = "файл\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_ac10_task_rm_removes_own_untracked_new_doc_and_symlink(pult, monkeypatch):
    """Свой неотслеживаемый файл копии, новый файл каталога документов и ссылка внутри копии.

    Под признаком роли (`ARTEL_ROLE`, `ARTEL_TASK=OWN`) `task-rm OWN` с тремя
    путями: неотслеживаемый файл своей рабочей копии, файл каталога
    документов, которого нет в ссылке документов, и символическая ссылка
    копии на файл той же копии. Наблюдается: код 0, все три пути исчезли,
    цель ссылки на месте.

    Ловит мутацию: команда идёт по символической ссылке и удаляет цель
    (`unlink` разрешённого пути) — цель ссылки пропадает; новый файл каталога
    документов считается лежащим в ссылке документов — отказ, код ненулевой.
    """
    untracked = _write(pult.own / "scratch" / "stub.py")
    new_doc = _write(pult.docs / "draft-note.md")
    target = _write(pult.own / "link-target.txt")
    link = pult.own / "link-inside"
    link.symlink_to(target)
    _as_role(monkeypatch, "role", OWN)

    code = _task_rm(monkeypatch, OWN, untracked, new_doc, link)

    assert code == 0
    assert not untracked.exists()
    assert not new_doc.exists()
    assert not os.path.lexists(link)
    assert target.exists()


def _refused_item(pult, kind: str) -> Path:
    """Недопустимый путь набора AC-11 (созданный на диске, где это файл или ссылка)."""
    own = pult.own
    if kind == "doc-in-artifacts":
        return pult.docs / "SPEC.md"
    if kind == "outside":
        return _write(pult.outside / "foreign.txt")
    if kind == "dotdot":
        _write(pult.area / "stray.txt")
        return Path(f"{own}/../../stray.txt")
    if kind == "symlink-out":
        link = own / "link-out"
        link.symlink_to(_write(pult.outside / "link-target.txt"))
        return link
    if kind == "through-dir-link":
        _write(pult.outside / "dir" / "inner.txt")
        (own / "dir-link").symlink_to(pult.outside / "dir", target_is_directory=True)
        return own / "dir-link" / "inner.txt"
    if kind == "directory":
        _write(own / "newdir" / "inside.txt")
        return own / "newdir"
    if kind == "own-dot-git":
        return own / ".git"
    if kind == "nested-dot-git-file":
        return _write(own / "nested" / ".git", "gitdir: /nowhere\n")
    if kind == "nested-dot-git-dir":
        _write(own / "nested2" / ".git" / "HEAD", "ref: refs/heads/main\n")
        return own / "nested2" / ".git"
    if kind == "inside-dot-git":
        return _write(own / "nested3" / ".git" / "config", "[core]\n")
    raise AssertionError(kind)


@pytest.mark.parametrize("kind", [
    "doc-in-artifacts", "outside", "dotdot", "symlink-out", "through-dir-link",
    "directory", "own-dot-git", "nested-dot-git-file", "nested-dot-git-dir",
    "inside-dot-git"])
def test_ac11_task_rm_refuses_whole_set(pult, monkeypatch, kind):
    """Набор с одним недопустимым путём — отказ всей команды без частичного удаления.

    В набор входят два допустимых файла (неотслеживаемый файл своей копии и
    новый файл каталога документов) и один недопустимый: файл каталога
    документов из ссылки документов, путь вне двух корней, `../` за корни,
    ссылка наружу, путь через ссылку на каталог вне корней, каталог, файл
    `.git` своей копии, `.git` вложенного уровня (файл и каталог), путь
    внутри `.git`. Наблюдается: ненулевой код, все пути набора на месте,
    `git rev-parse --show-toplevel` в рабочей копии называет её саму.

    Ловит мутацию: файлы удаляются по одному до проверки всего набора —
    допустимые файлы, стоящие в наборе раньше недопустимого, пропадают;
    проверка `.git` только по имени верхнего уровня — вложенный `.git`
    удаляется; проверка корней до `realpath` — путь через ссылку на каталог
    вне корней удаляет `inner.txt`.
    """
    good_own = _write(pult.own / "scratch.txt")
    good_doc = _write(pult.docs / "new-draft.md")
    bad = _refused_item(pult, kind)
    _as_role(monkeypatch, "role", OWN)

    code = _task_rm(monkeypatch, OWN, good_own, good_doc, bad)

    assert code != 0, kind
    assert good_own.exists(), kind
    assert good_doc.exists(), kind
    assert os.path.lexists(bad), kind
    toplevel = pult.git_seed("rev-parse", "--show-toplevel", cwd=pult.own)
    assert Path(toplevel).resolve() == pult.own.resolve(), kind


@pytest.mark.parametrize("sign", ["role", "home"])
@pytest.mark.parametrize("env_task", [OTHER, None])
def test_ac12_task_rm_refuses_foreign_or_missing_task_under_role(pult, monkeypatch,
                                                                sign, env_task):
    """Под признаком роли `<id>`, отличный от `ARTEL_TASK`, и признак без `ARTEL_TASK` — отказ.

    Признак роли — в обеих формах: `ARTEL_ROLE` и `HOME`, равный дому роли,
    без `ARTEL_ROLE`. `task-rm OWN` своего неотслеживаемого файла рабочей
    копии `OWN` при `ARTEL_TASK=OTHER` либо без `ARTEL_TASK`. Наблюдается:
    ненулевой код, файл на месте.

    Ловит мутацию: признак роли распознаётся только по `ARTEL_ROLE` (форма
    «home» удаляет файл); без `ARTEL_TASK` задача берётся из аргумента —
    файл удалён с кодом 0.
    """
    victim = _write(pult.own / "scratch.txt")
    _as_role(monkeypatch, sign, env_task)

    code = _task_rm(monkeypatch, OWN, victim)

    assert code != 0
    assert victim.exists()


def test_ac12_operator_task_rm_any_task(pult, monkeypatch):
    """Вызов Оператора без признака роли с явным id любой задачи — успех.

    Без `ARTEL_ROLE`, `ARTEL_TASK`, с `HOME` Оператора: `task-rm OTHER`
    неотслеживаемого файла рабочей копии `OTHER`. Наблюдается: код 0, файл
    удалён.

    Ловит мутацию: команда требует `ARTEL_TASK` всегда, а не только под
    признаком роли — у Оператора отказ, файл на месте.
    """
    victim = _write(pult.other / "scratch.txt")

    code = _task_rm(monkeypatch, OTHER, victim)

    assert code == 0
    assert not victim.exists()


def test_ac13_task_rm_in_role_allowed_commands():
    """`task-rm` входит в белый список команд процесса роли диспетчера.

    Ловит мутацию: команда добавлена в таблицу диспетчера, но не в
    `_ROLE_ALLOWED_COMMANDS` — под признаком роли она отказывает «команда
    недоступна процессу роли».
    """
    assert "task-rm" in artel._ROLE_ALLOWED_COMMANDS


@pytest.mark.parametrize("role", ["test_author", "developer"])
def test_ac13_mission_docs_paragraph_names_task_rm(pult, role):
    """Миссия роли с каталогом документов называет `task-rm` в абзаце о каталоге документов.

    Миссия собирается штатным `role_prompt.mission_brief_package` с каталогом
    документов (компоненты брифа подменены пустыми); абзац — тот, что
    называет путь каталога документов (`role_prompt.docs_dir_note`).

    Ловит мутацию: команда упомянута в миссии одной роли (например, только
    test_author), а не в общем абзаце о каталоге документов — у второй роли
    `task-rm` в абзаце нет.
    """
    t = {"branch": f"task/{OWN.lower()}", "title": "Задача дублёра",
         "reviewed_iter": 0}
    conn = store.db()
    with mock.patch.object(brief, "analyst_map_component", return_value=""), \
            mock.patch.object(brief, "test_author_answer_component", return_value=None), \
            mock.patch.object(brief, "developer_brief", return_value=""), \
            mock.patch.object(brief, "spec_auditor_brief", return_value=""), \
            mock.patch.object(review, "review_package", return_value=""), \
            mock.patch.object(review, "previous_verdict_sha", return_value=""):
        mission, _brief, _package = role_prompt.mission_brief_package(
            conn, OWN, t, role, pult.own, pult.docs)
    conn.close()
    paragraphs = [p for p in mission.split("\n\n")
                  if f"Каталог документов задачи — {pult.docs}" in p]

    assert paragraphs, mission
    assert any("task-rm" in p for p in paragraphs), paragraphs
