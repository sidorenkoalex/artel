"""Команда `artel.py forge-probe <проект> --ref <ветка> | --sha <sha>`: строка конвейера — по `forge.branch_pipeline` указанной ветки либо по `forge.pipeline_status` коммита; оба флага вместе — отказ с подсказкой; без флагов — прежний вывод по базе.

Группа: долгоживущий
Красен до реализации: `forge-probe` не знает флагов `--ref`/`--sha` — выходит с ненулевым кодом «неизвестный флаг» и не печатает конвейер; вариант без флагов и отказ на двух флагах сразу зелены с рождения — первый держит прежний вывод, второй сегодня отказывает «неизвестный флаг» с той же подсказкой использования.

Связка, которую держит файл: «запись `forge: gitlab` в `targets.yaml`
песочницы — `artel.main` — `forge`». Песочница — `initialized_tmp_root`;
функции `forge.token_user`, `project_info`, `token_expiry`, `protections`,
`branch_pipeline`, `pipeline_status`, `job_test_report` подменены
поддельным хостингом, записывающим каждый вызов: конвейер каждой ветки и
каждого sha — свои случайные sha, итог и имена заданий.

Имена проекта, веток, заданий и sha порождаются модулем `random` при
каждом запуске; зерно печатается и входит в текст провала.
"""
import contextlib
import io
import random
import sys
from unittest import mock

import pytest

from orchestrator import artel, config, forge
from tests.sandbox import artel_target_entry

LETTERS = "abcdefghijkmnopqrstuvwxyz"
VERDICTS = (forge.GREEN, forge.RED, forge.RUNNING)


def word(rng: random.Random, prefix: str, size: int = 7) -> str:
    return prefix + "".join(rng.choice(LETTERS) for _ in range(size))


@pytest.fixture
def seed():
    value = random.randrange(1 << 30)
    print(f"зерно: {value}")
    return value


class Hosting:
    """Поддельный `forge`: конвейер ветки и коммита строится по имени."""

    def __init__(self, rng: random.Random):
        self.rng = rng
        self.calls: list = []
        self.branches: dict = {}
        self.shas: dict = {}

    def jobs(self, prefix: str) -> list:
        return [forge.Job(word(self.rng, prefix, 5), "success", "test", i)
                for i in range(1, self.rng.randint(2, 4))]

    def branch_pipeline(self, target, branch):
        self.calls.append(("branch_pipeline", branch))
        if branch not in self.branches:
            self.branches[branch] = forge.BranchPipeline(
                "%040x" % self.rng.getrandbits(160), self.rng.choice(VERDICTS), "",
                self.jobs("bj-"))
        return self.branches[branch]

    def pipeline_status(self, target, sha):
        self.calls.append(("pipeline_status", sha))
        if sha not in self.shas:
            self.shas[sha] = forge.PipelineStatus(self.rng.choice(VERDICTS), "",
                                                  self.jobs("sj-"))
        return self.shas[sha]


@pytest.fixture
def scene(initialized_tmp_root, monkeypatch, seed):
    rng = random.Random(seed)
    name = word(rng, "gl")
    text = "targets:\n" + artel_target_entry()
    config.TARGETS.write_text(text.rstrip("\n") + "\n" + (
        f"  {name}:\n    forge: gitlab\n    url: https://localhost/team/{name}\n"
        f"    base: {config.MAIN_BRANCH}\n    token_slot: {name}-token\n"
        "    no_paths: []\n    project_skills: []\n    merge_gate: operator\n"),
        encoding="utf-8")
    fake = Hosting(rng)
    monkeypatch.setattr(forge, "token_user", lambda t: forge.TokenUser("probe-user"))
    monkeypatch.setattr(forge, "project_info", lambda t: forge.ProjectInfo(config.MAIN_BRANCH, 40))
    monkeypatch.setattr(forge, "token_expiry", lambda t: forge.TokenExpiry(note="без срока"))
    monkeypatch.setattr(forge, "protections", lambda t: forge.Protections(["main"], []))
    monkeypatch.setattr(forge, "branch_pipeline", fake.branch_pipeline)
    monkeypatch.setattr(forge, "pipeline_status", fake.pipeline_status)
    monkeypatch.setattr(forge, "job_test_report",
                        lambda t, sha, job: forge.TestReport(None, "отчёта нет"))
    return {"name": name, "rng": rng, "seed": seed, "fake": fake}


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


def test_ac14_ref_prints_branch_pipeline_of_that_branch(scene):
    """`forge-probe <проект> --ref <ветка>` печатает sha, итог и задания конвейера этой ветки, а не базы.

    Сценарий: у поддельного хостинга конвейер базы и конвейер случайной
    ветки `feat…` — разные sha, итоги, задания. Команда выходит с кодом 0;
    в выводе — sha, итог и имена заданий `branch_pipeline(<проект>,
    <ветка>)`; sha и задания конвейера базы в выводе нет.

    Ловит мутацию: флаг `--ref` разобран, но строка конвейера по-прежнему
    печатается по `base` (в выводе sha базы); `--ref` не передаётся в
    `branch_pipeline` (вызова с веткой нет); флаг не знаком команде (код
    выхода не 0).
    """
    s = scene
    fake = s["fake"]
    branch = word(s["rng"], "feat-", 5)
    base = fake.branch_pipeline(s["name"], config.MAIN_BRANCH)
    wanted = fake.branch_pipeline(s["name"], branch)
    fake.calls.clear()
    out, code = cli("forge-probe", s["name"], "--ref", branch)
    note = f"зерно: {s['seed']}; ветка {branch}; код {code}; вызовы {fake.calls}\n{out}"
    assert code == 0, note
    assert ("branch_pipeline", branch) in fake.calls, note
    assert wanted.sha in out, note
    assert wanted.verdict in out, note
    for job in wanted.jobs:
        assert job.name in out, note
    assert base.sha not in out, note
    for job in base.jobs:
        assert job.name not in out, note


def test_ac14_sha_prints_pipeline_status_of_that_commit(scene):
    """`forge-probe <проект> --sha <sha>` печатает sha, итог и задания `pipeline_status` этого коммита.

    Сценарий: случайный sha; поддельный `pipeline_status` отдаёт для него
    свой итог и задания. Команда выходит с кодом 0; `pipeline_status`
    вызван с этим sha; в выводе — sha, итог и имена заданий.

    Ловит мутацию: `--sha` печатает конвейер базы (`branch_pipeline`), а
    `pipeline_status` не зовётся; задания коммита не печатаются; флаг не
    знаком команде.
    """
    s = scene
    fake = s["fake"]
    sha = "%040x" % s["rng"].getrandbits(160)
    wanted = fake.pipeline_status(s["name"], sha)
    fake.calls.clear()
    out, code = cli("forge-probe", s["name"], "--sha", sha)
    note = f"зерно: {s['seed']}; sha {sha}; код {code}; вызовы {fake.calls}\n{out}"
    assert code == 0, note
    assert ("pipeline_status", sha) in fake.calls, note
    assert sha[:8] in out, note
    assert wanted.verdict in out, note
    for job in wanted.jobs:
        assert job.name in out, note


def test_ac14_ref_and_sha_together_refused(scene):
    """`--ref` и `--sha` вместе — ненулевой код и подсказка использования.

    Сценарий: `forge-probe <проект> --ref <ветка> --sha <sha>`. Код выхода
    не 0, в выводе — подсказка использования `forge-probe <проект>`;
    поддельный хостинг конвейеров не опрошен.

    Ловит мутацию: побеждает один из флагов молча (код 0, печать
    конвейера); отказ без подсказки использования.
    """
    s = scene
    sha = "%040x" % s["rng"].getrandbits(160)
    out, code = cli("forge-probe", s["name"], "--ref", "feat", "--sha", sha)
    note = f"зерно: {s['seed']}; код {code}; вызовы {s['fake'].calls}\n{out}"
    assert code != 0, note
    assert "forge-probe <проект>" in out, note
    assert s["fake"].calls == [], note


def test_ac14_without_flags_prints_base_pipeline(scene):
    """Без флагов — прежний вывод: конвейер базы по `branch_pipeline(<проект>, base)`.

    Сценарий: `forge-probe <проект>`. Код выхода 0; `branch_pipeline`
    вызван с базой записи, `pipeline_status` не вызван; в выводе строка
    «последний конвейер <база>: sha <sha>, итог <итог>» и задания.

    Ловит мутацию: новый разбор флагов ломает вызов без флагов (код не 0);
    без флагов зовётся `pipeline_status` или ветка по умолчанию иная,
    чем база записи.
    """
    s = scene
    fake = s["fake"]
    out, code = cli("forge-probe", s["name"])
    base = fake.branches.get(config.MAIN_BRANCH)
    note = f"зерно: {s['seed']}; код {code}; вызовы {fake.calls}\n{out}"
    assert code == 0, note
    assert ("branch_pipeline", config.MAIN_BRANCH) in fake.calls, note
    assert not [c for c in fake.calls if c[0] == "pipeline_status"], note
    assert (f"последний конвейер {config.MAIN_BRANCH}: sha {base.sha}, итог "
            f"{base.verdict}") in out, note
    for job in base.jobs:
        assert job.name in out, note
