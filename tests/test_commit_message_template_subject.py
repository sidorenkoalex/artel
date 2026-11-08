"""Шаблон `policy.commit_message_template` и тема коммита, как её видит git (замечание ревью R1-F1).

Git при `commit -m` срезает пробелы в конце строк, а `log --format=%s`
склеивает строки первого абзаца через пробел. Рубеж «замечания ревью не
отработаны» сравнивает тему подтяжки по шаблону с темой из `git log`, поэтому
обязан нормализовать ожидаемую тему тем же правилом; шаблон с переводом
строки отвергается загрузкой — он описывает первую строку сообщения.
Все проверки — на вымышленной записи проекта и временном git-репозитории.
"""
import subprocess
from unittest import mock

import pytest

from orchestrator import artel  # noqa: F401 — порядок импорта пакета без цикла
from orchestrator import checkpoint, targets, workspace
from orchestrator.advance_gates import review

TASK = "01AAAAAAAAAAAAAAAAAAAAAAAA"


def git(repo, *args) -> str:
    res = subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t",
         "-c", "commit.gpgsign=false", *args],
        capture_output=True, text=True, check=True)
    return res.stdout


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    return path


def commit(repo, message: str) -> None:
    git(repo, "commit", "-q", "--allow-empty", "-m", message)


@pytest.mark.parametrize("template", ["{ref}: {text}\n",
                                      "{text}\n\nRefs: {ref}",
                                      "{text}\r({ref})"])
def test_multiline_template_refused_by_field_name(template):
    """Шаблон с переводом строки — отказ проверки записи полем `policy.commit_message_template`; тот же шаблон одной строкой (с пробелом в конце) проходит.

    `target-set` многострочное значение не пишет, а локальный слой не
    раскрывает `\\n` в кавычках — проверка загрузчика держит свойство для
    любого источника записи. Ловит мутацию: удалена проверка перевода
    строки в `_check_delivery` — многострочный шаблон принят, тест красный.
    """
    policy = {"ref_required": "tracker", "commit_message_template": template}
    with pytest.raises(targets.TargetsError) as exc:
        targets._check_delivery("demo", policy, {})
    assert "поле 'policy.commit_message_template' — " in str(exc.value)
    policy["commit_message_template"] = "{ref}: {text} "
    targets._check_delivery("demo", policy, {})


@pytest.mark.parametrize("message", [
    "ABC-1: подтяжка main ",
    "подтяжка main\n(ABC-1)",
    "\nподтяжка main  \nABC-1\t\n\nтело\nещё",
    "подтяжка main (Название \nзадачи )",
])
def test_git_subject_matches_git_log(repo, message):
    """`_git_subject` даёт ровно ту тему, которую `git log --format=%s` показывает после `commit -m`.

    Ловит мутацию: `_git_subject` возвращает сообщение как есть (без среза
    пробелов в конце и склейки строк первого абзаца) — тема расходится с
    `%s`, тест красный.
    """
    commit(repo, message)
    assert review._git_subject(message) == git(repo, "log", "-1",
                                                "--format=%s").rstrip("\n")


@pytest.mark.parametrize("raw", ["ABC-1: подтяжка main ",
                                 "ABC-1: подтяжка main (Название\nзадачи)"])
def test_templated_pull_with_trailing_space_not_counted(repo, raw):
    """Подтяжка с темой по шаблону, которую git нормализовал, не засчитывается шагом developer; коммит кода по шаблону — засчитывается.

    Ловит мутацию: сравнение темы `git log` с сырым результатом
    `pult_subject` (без `_git_subject`) — подтяжка засчитана, дата
    последнего коммита developer не `None`, тест красный.
    """
    commit(repo, raw)
    entry = {"base": "main", "commit_message_template": "{ref}: {text} "}
    with mock.patch.object(workspace, "task_repo", return_value=repo), \
            mock.patch.object(checkpoint, "task_project_entry",
                              return_value=entry), \
            mock.patch.object(checkpoint, "pult_subject", return_value=raw):
        assert review._latest_developer_commit_iso_date(
            "main", TASK, conn=object()) is None
        commit(repo, "ABC-1: код закоммичен пультом за роль developer ")
        assert review._latest_developer_commit_iso_date(
            "main", TASK, conn=object()) is not None
