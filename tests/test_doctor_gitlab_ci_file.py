"""Строки `doctor` записи GitLab по уточнениям ANSWER-1 задачи 01M6EZXVFGH5Z2876XWMQG35FP: `include`, неподдержанное `if`, `changes`, переменные `$CI_PIPELINE_SOURCE`/`$CI_DEFAULT_BRANCH`, `retry: {max: N}`, ssh/чужой хост/относительный адрес подмодуля, 403 заданий при красном конвейере.

Свойства вне долгоживущих файлов задачи (`tests/test_01m6ezxvfgh5z2876xwmqg35fp_*`):
функции строк зовутся напрямую на клоне во временном каталоге; хостинг —
подмена `gitlab_adapter.transport`.
"""
import json
import subprocess
import tempfile
import urllib.parse
from pathlib import Path

import pytest

from orchestrator import config, doctor, forge, gitlab_adapter
from orchestrator.doctor import project_checks as pc
from tests.sandbox import TimeWithSleep, artel_target_entry


@pytest.fixture
def clone():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


def write_ci(clone: Path, text: str) -> None:
    (clone / pc.CI_FILE).write_text(text, encoding="utf-8")


def rules_line(clone: Path, entry: dict | None = None):
    return pc.check_workflow_rules("project-ci-pull-request-x", clone,
                                   entry or {"base": "develop"})


def test_include_without_workflow_rules_warns(clone):
    """`include:` без локального `workflow:rules` — `warn` «не разобран: include».

    Ловит мутацию: `include` не проверяется и файл без `workflow` даёт `ok`;
    `include` даёт `skip` вместо `warn` (ANSWER-1 п. 4).
    """
    write_ci(clone, "include:\n  - local: ci/base.yml\ntests:\n  script:\n    - pytest\n")
    line = rules_line(clone)
    assert line.status == "warn", line
    assert ".gitlab-ci.yml не разобран: include" in line.detail, line


def test_unsupported_if_and_changes_warn(clone):
    """Неподдержанное `if` и `changes` у сработавшего правила — `warn` «правило может сработать».

    Ловит мутацию: неподдержанное выражение считается ложным и решает
    следующее правило (`ok`); `changes` игнорируется и правило без `when`
    даёт `ok`; исход — `skip` вместо `warn`.
    """
    write_ci(clone, "workflow:\n  rules:\n    - if: $X > 1\n    - when: always\n")
    line = rules_line(clone)
    assert line.status == "warn" and "правило может сработать" in line.detail, line
    assert "правило workflow №1 (if: $X > 1)" in line.detail, line
    write_ci(clone, "workflow:\n  rules:\n    - if: $CI_COMMIT_BRANCH\n"
                    "      changes:\n        - src/**\n")
    line = rules_line(clone)
    assert line.status == "warn" and "changes" in line.detail, line


@pytest.mark.parametrize("cond,status", [
    ("'$CI_PIPELINE_SOURCE == \"push\"'", "ok"),
    ("'$CI_PIPELINE_SOURCE == \"merge_request_event\"'", "warn"),
    ("$CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH", "warn"),
    ("($CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH) || $CI_COMMIT_REF_NAME =~ /^TASK\\//i", "ok"),
    ("$CI_COMMIT_TAG && $CI_COMMIT_BRANCH", "warn"),
    ("$CI_COMMIT_BRANCH !~ /^task\\//", "warn"),
])
def test_rule_variables_and_operators(clone, cond, status):
    """Переменные конвейера отправки (`push`, база записи) и операторы `==`, `||`, `&&`, `!~`, флаг `i`, скобки.

    Ловит мутацию: `$CI_PIPELINE_SOURCE` не `push`; `$CI_DEFAULT_BRANCH`
    равна ветке задачи, а не `base`; `||`/`&&` перепутаны; неопределённая
    переменная истинна; флаг `i` не учитывается; `!~` не инвертирует.
    """
    write_ci(clone, f"workflow:\n  rules:\n    - if: {cond}\n")
    line = rules_line(clone)
    assert line.status == status, line


@pytest.mark.parametrize("text,line_no", [
    ("tests:\n  script: |\n    pytest\n", 2),
    ("a: 1\n---\nb: 2\n", 2),
    ("tests:\n  script:\n    - !reference [.x, script]\n", 3),
    ("tests:\n  script: pytest\n   retry: 1\n", 3),
])
def test_unparsed_forms_name_the_line(clone, text, line_no):
    """Многострочный скаляр, второй документ, тег, сбитый отступ — «не разобран: строка N».

    Ловит мутацию: форма вне подмножества молча пропущена (`ok`); номер
    строки отсчитан с нуля или не назван.
    """
    write_ci(clone, text)
    line = rules_line(clone)
    assert line.status == "warn", line
    assert f".gitlab-ci.yml не разобран: строка {line_no}:" in line.detail, line


def test_parser_reads_flow_quotes_and_comments(clone):
    """Потоковые формы, кавычки и комментарии разбираются; прочие ключи пропускаются.

    Ловит мутацию: комментарий ` #…` попадает в значение; потоковое
    отображение `{max: 2}` не разобрано; ключ `image`/`stages` даёт «не
    разобран».
    """
    write_ci(clone, "stages: [test, deploy]  # стадии\nimage: python:3.12\n"
                    "tests:\n  stage: test\n  retry: {max: 2, when: [script_failure]}\n"
                    "  script:\n    - 'pytest -q'  # прогон\n")
    doc, problem = pc.ci_document(clone)
    assert problem == "", problem
    assert doc["stages"] == ["test", "deploy"]
    assert doc["tests"]["retry"] == {"max": "2", "when": ["script_failure"]}
    assert doc["tests"]["script"] == ["pytest -q"]


@pytest.mark.parametrize("retry,status", [("{max: 2}", "warn"), ("{max: 0}", "ok")])
def test_retry_mapping_form(clone, retry, status):
    """`retry: {max: N}` при N > 0 — находка перезапуска, `{max: 0}` — нет (ANSWER-1 п. 2).

    Ловит мутацию: форма отображения не читается (`{max: 2}` — `ok`) или
    засчитывается всегда (`{max: 0}` — `warn`).
    """
    write_ci(clone, f"tests:\n  retry: {retry}\n  script:\n    - pytest\n")
    line = pc.check_ci_reruns("project-ci-reruns-x-app", clone, {"ci_job": "tests"})
    assert line.status == status, line


def test_reruns_include_without_finding_warns(clone):
    """`include:` без локальной находки — `warn` «не разобран: include», не `ok`.

    Ловит мутацию: `include` в строке перезапусков не учитывается — `ok`
    при том, что `retry` может прийти из подключённого файла.
    """
    write_ci(clone, "include: ci/base.yml\ntests:\n  script:\n    - pytest\n")
    line = pc.check_ci_reruns("project-ci-reruns-x-app", clone, {"ci_job": "tests"})
    assert line.status == "warn" and "include" in line.detail, line


def test_job_retry_zero_overrides_default(clone):
    """Своё `retry: 0` задания перекрывает `default: retry` — находки нет.

    Ловит мутацию: `default:` читается и при собственном `retry` задания.
    """
    write_ci(clone, "default:\n  retry: 2\ntests:\n  retry: 0\n  script:\n    - pytest\n")
    line = pc.check_ci_reruns("project-ci-reruns-x-app", clone, {"ci_job": "tests"})
    assert line.status == "ok", line


class Probe:
    def __init__(self):
        self.calls = []

    def in_repo(self, repo, *args, **kwargs):
        self.calls.append(args)
        return subprocess.CompletedProcess(list(args), 0, "", "")


@pytest.fixture
def probe(monkeypatch):
    fake = Probe()
    monkeypatch.setattr(doctor.gitcmd, "in_repo", fake.in_repo)
    return fake


def submodules(clone: Path, *urls: str):
    (clone / ".gitmodules").write_text("".join(
        f'[submodule "m{i}"]\n\tpath = libs/m{i}\n\turl = {url}\n'
        for i, url in enumerate(urls)), encoding="utf-8")
    entry = {"url": "https://git.example/team/proj", "token_slot": "slot"}
    return pc.check_submodules("project-submodules-x", clone, entry, False)


def test_relative_submodule_resolved_from_entry_url(clone, probe):
    """Относительный адрес `../lib.git` разрешается от `url` записи и пробуется.

    Ловит мутацию: относительный адрес не разрешается (проба по `../lib.git`
    либо подмодуль сочтён чужим и не проверен).
    """
    line = submodules(clone, "../lib.git")
    assert line.status == "ok", line
    assert probe.calls == [("ls-remote", "https://git.example/team/lib.git")], probe.calls


@pytest.mark.parametrize("url,marker", [
    ("git@git.example:team/lib.git", "ssh-адрес, токеном слота не проверяется"),
    ("ssh://git@git.example/team/lib.git", "ssh-адрес, токеном слота не проверяется"),
    ("https://other.example/team/lib.git", "не на хосте записи"),
])
def test_ssh_and_foreign_submodules_warn_without_probe(clone, probe, url, marker):
    """ssh-адрес на том же хосте и подмодуль чужого хоста — `warn` без пробы (ANSWER-1 пп. 1, 4).

    Ловит мутацию: ssh-адрес пробуется токеном слота; чужой хост
    пропускается молча (`ok`) или пробуется.
    """
    line = submodules(clone, url)
    assert line.status == "warn", line
    assert marker in line.detail, line
    assert probe.calls == [], probe.calls


def test_jobs_403_on_failed_pipeline_sets_http_status(initialized_tmp_root, monkeypatch):
    """Конвейер `failed`, задания — 403: `branch_pipeline` даёт `http_status` 403, строка `ci-token` — `fail` (ANSWER-1 п. 3).

    Ловит мутацию: код отказа чтения заданий теряется при красном
    конвейере; строка `ci-token` принимает такой исход за прочитанный итог.
    """
    name = "glproj"
    config.TARGETS.write_text("targets:\n" + artel_target_entry().rstrip("\n") + "\n" + (
        f"  {name}:\n    forge: gitlab\n    url: https://localhost/grp/{name}\n"
        f"    base: {config.MAIN_BRANCH}\n    token_slot: {name}-token\n"
        "    no_paths: []\n    project_skills: []\n    merge_gate: operator\n"),
        encoding="utf-8")

    def transport(method, url, headers=None, body=None, timeout=None):
        path = urllib.parse.urlsplit(url).path
        if path.endswith("/jobs"):
            return 403, {}, b'{"message": "403"}'
        items = [{"id": 7, "sha": "a" * 40, "status": "failed"}]
        return 200, {"X-Total": "1", "X-Next-Page": ""}, json.dumps(items).encode()

    monkeypatch.setattr(gitlab_adapter, "transport", transport)
    monkeypatch.setattr(gitlab_adapter, "time", TimeWithSleep(lambda seconds: None))
    result = forge.branch_pipeline(name, config.MAIN_BRANCH)
    assert result.http_status == 403, result
    monkeypatch.setattr(forge, "branch_pipeline", lambda t, b: forge.BranchPipeline(
        "a" * 40, forge.RED, "отказ", http_status=403))
    line = pc.check_forge_ci_token("project-ci-token-x", name, {"token_slot": "s"})
    assert line.status == "fail", line
