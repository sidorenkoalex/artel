"""Строка doctor `project-ci-token-<проект>`: читает ли токен внешнего проекта проверки коммита (check-runs) и запуски Actions.

Группа: долгоживущий

Красен до реализации: строки `project-ci-token-<проект>` среди строк проекта (`doctor.project_entry_checks`) ещё нет — поиск строки по имени падает в каждом сценарии AC-11 и AC-12.

Сценарий: песочница `TmpRootTest`, запись артели и учебного внешнего
проекта в `config.TARGETS`, клон проекта со своим bare-`origin`
(`make_project_repo`). Строки проекта — `doctor.project_entry_checks`,
тот же вход, которым их собирает вывод `doctor` (`doctor/cli.py`). Вызовы
`gh` перехватывает подмена `subprocess.run` (argv[0] — `gh`), git идёт
мимо неё (`network_guarded_real_run`). Поддельный GitHub отвечает как
`gh api` без `--jq`: на `…/commits/<ref>/check-runs` — ответом check-runs
сценария, на любой адрес `…/actions/…` и на `gh run list` — ответом
Actions сценария; голова базовой ветки (`commits/<ref>`,
`branches/<база>`, `git/ref…`) отдаётся всегда, защита ветки — пустым
объектом. HTTP-отказ — ненулевой код, тело ошибки в stdout и
`gh: <сообщение> (HTTP <код>)` в stderr; обрыв сети — ненулевой код без
HTTP-ответа либо `subprocess.TimeoutExpired`.

Токен слота проекта — подмена связки ключей песочницы
(`test-token-<слот>`); его значение ищется в выводе каждого сценария.
Имя проекта, тексты 403 и коды отказов — из `random`, зерно печатается и
входит в текст провала.
"""
import json
import os
import random
import re
import shutil
import subprocess
from unittest import mock

from orchestrator import config, doctor, keychain, targets
from orchestrator.doctor import project_checks
from tests.sandbox import (TmpRootTest, capture_new_task_id,
                           make_project_repo, network_guarded_real_run,
                           seed_artel_targets)

NOT_ACCESSIBLE = ("Resource not accessible by personal access token",
                  "Resource not accessible by integration")
WARN_TEXT = ("CI читается по Actions runs; для check-runs токену нужно право "
             "Checks: read")
PROJECT_NAMES = ("sled", "sani", "drovni", "rozvalni", "kibitka")
HEX = "0123456789abcdef"

NETWORK = (1, "", "error connecting to api.github.com\n"
                  "check your internet connection or "
                  "https://localhost/status\n")
TIMEOUT = "timeout"
MISSING = "missing"
UNPARSED = (0, "<html><body>502 прокси</body></html>", "")


def ok(payload) -> tuple:
    return 0, json.dumps(payload), ""


def http_error(code: int, message: str) -> tuple:
    body = json.dumps({"message": message, "status": str(code),
                       "documentation_url": "https://localhost/docs/rest"})
    return 1, body, f"gh: {message} (HTTP {code})\n"


class FakeGitHub:
    """Поддельный GitHub за подменой `subprocess.run`: ответ check-runs и
    ответ Actions задаёт сценарий; `everything` — один ответ на любой вызов
    `gh` (обрыв сети). `MISSING` — `gh` нет (`FileNotFoundError`)."""

    def __init__(self, sha: str, base: str):
        self.sha, self.base = sha, base
        self.calls: list[list[str]] = []
        self.check_runs = ok({"total_count": 1, "check_runs": [
            {"id": 1, "name": "тесты", "status": "completed",
             "conclusion": "success"}]})
        self.actions = ok({"total_count": 1, "workflow_runs": [
            {"id": 2, "name": "CI", "event": "push", "status": "completed",
             "conclusion": "success", "head_branch": base, "head_sha": sha}],
            "workflows": [{"id": 3, "name": "CI", "state": "active"}],
            "jobs": []})
        self.everything = None

    def __call__(self, cmd, *args, **kwargs):
        if not cmd or os.path.basename(str(cmd[0])) != "gh":
            return network_guarded_real_run(cmd, *args, **kwargs)
        argv = [str(a) for a in cmd]
        self.calls.append(argv)
        answer = self.everything if self.everything is not None \
            else self.answer(argv)
        if answer == MISSING:
            raise FileNotFoundError(2, "No such file or directory: 'gh'")
        if answer == TIMEOUT:
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout") or 1)
        code, out, err = answer
        return subprocess.CompletedProcess(cmd, code, out, err)

    def ci_calls(self) -> list:
        return [c for c in self.calls
                if "check-runs" in " ".join(c) or "actions" in " ".join(c)
                or c[1:3] == ["run", "list"]]

    def answer(self, argv: list):
        if argv[1:3] == ["run", "list"]:
            if self.actions[0] == 0:
                return ok([{"headBranch": self.base, "status": "completed",
                            "conclusion": "success", "databaseId": 2}])
            return self.actions
        if argv[1:3] == ["auth", "token"]:
            return 1, "", "no oauth token found\n"
        if argv[1:3] == ["repo", "view"]:
            return 0, f"{self.base}\n", ""
        joined = " ".join(argv)
        if "check-runs" in joined:
            return self.check_runs
        if re.search(r"/actions(/|\?|$)", joined) or "actions/" in joined:
            return self.actions
        if "protection" in joined:
            return ok({})
        if re.search(r"git/refs?/", joined):
            return ok({"ref": f"refs/heads/{self.base}",
                       "object": {"sha": self.sha, "type": "commit"}})
        if re.search(r"/branches/", joined):
            return ok({"name": self.base, "commit": {"sha": self.sha}})
        if re.search(r"/commits/[^/\s?]+", joined):
            return ok({"sha": self.sha, "commit": {"message": "init"}})
        return http_error(404, "Not Found")


class DoctorCiTokenSandbox(TmpRootTest):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(2 ** 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        seed_artel_targets()
        self.project = (self.rng.choice(PROJECT_NAMES)
                        + str(self.rng.randrange(10, 100)))
        make_project_repo(self.project)
        self.entries = targets.load()
        self.entry = self.entries[self.project]
        self.token = keychain.token(self.entry["token_slot"])
        self.sha = "".join(self.rng.choice(HEX) for _ in range(40))
        self.gh = FakeGitHub(self.sha, self.entry.get("base",
                                                      config.MAIN_BRANCH))
        patcher = mock.patch.object(subprocess, "run", self.fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        real_which = shutil.which
        self.gh_present = True
        patcher = mock.patch.object(
            shutil, "which",
            lambda name, *a, **k: (("/usr/local/bin/gh" if self.gh_present
                                    else None) if name == "gh"
                                   else real_which(name, *a, **k)))
        patcher.start()
        self.addCleanup(patcher.stop)

    def fake(self, cmd, *args, **kwargs):
        return self.gh(cmd, *args, **kwargs)

    def why(self, text: str) -> str:
        return (f"{text} (зерно {self.seed}, проект {self.project}, вызовы "
                f"gh: {self.gh.calls})")

    def ci_token_row(self, name: str | None = None, entry=None,
                     label: str = ""):
        """Строка `project-ci-token-<name>` среди строк проекта; значение
        токена проекта не встречается ни в строках, ни в печати."""
        name = name or self.project
        entry = entry if entry is not None else self.entry
        out, checks = capture_new_task_id(doctor.project_entry_checks,
                                          name, entry)
        rows = [c for c in checks if c.name == f"project-ci-token-{name}"]
        self.assertEqual(len(rows), 1, self.why(
            f"{label}: строк project-ci-token-{name} {len(rows)}; строки "
            f"проекта: {[c.name for c in checks]}"))
        self.assertNotIn(self.token, out + repr(checks), self.why(
            f"{label}: значение токена проекта в выводе doctor"))
        return rows[0]

    def assert_status(self, label: str, status: str, row) -> None:
        self.assertEqual(row.status, status, self.why(
            f"{label}: {row.status} вместо {status}: {row.detail}"))
        self.assertTrue((row.detail or "").strip(), self.why(
            f"{label}: {status} без причины"))


class AccessOutcomesTest(DoctorCiTokenSandbox):

    def test_ac11_ci_token_row_maps_check_runs_and_actions_access(self):
        """Строка `project-ci-token-<проект>` есть и сопоставляет доступ к check-runs и Actions исходам ok/warn/fail/skip.

        Сценарии (`subTest`): оба доступны — `ok`; check-runs 403
        «Resource not accessible …», Actions доступны — `warn` с текстом
        «CI читается по Actions runs; для check-runs токену нужно право
        Checks: read»; check-runs 401, 404, 5xx или неразобранный ответ при
        доступных Actions — `fail`; check-runs 403 «API rate limit
        exceeded» при доступных Actions — `skip` с причиной, без текста
        `warn`; Actions недоступны (403 «Resource not accessible …» или
        404) при доступных или запрещённых правами check-runs — `fail`.
        Значение токена проекта нигде в выводе не встречается.

        Ловит мутацию: строка не добавлена в строки проекта, любой 403
        check-runs (в том числе лимит запросов) даёт `warn`, отказ
        check-runs 401/404/5xx читается как `warn` или `ok`, либо
        недоступные Actions не дают `fail`.
        """
        forbidden = http_error(403, self.rng.choice(NOT_ACCESSIBLE))
        five = self.rng.choice((500, 502, 503))
        actions_down = self.rng.choice((
            http_error(403, self.rng.choice(NOT_ACCESSIBLE)),
            http_error(404, "Not Found")))
        cases = [
            ("оба доступны", None, None, "ok"),
            ("check-runs 403", forbidden, None, "warn"),
            ("check-runs 401", http_error(401, "Bad credentials"), None, "fail"),
            ("check-runs 404", http_error(404, "Not Found"), None, "fail"),
            (f"check-runs {five}", http_error(five, "Server Error"), None,
             "fail"),
            ("check-runs неразобран", UNPARSED, None, "fail"),
            ("check-runs 403 rate limit", http_error(
                403, "API rate limit exceeded for user ID "
                     f"{self.rng.randrange(10 ** 5, 10 ** 7)}."), None, "skip"),
            ("Actions недоступны", None, actions_down, "fail"),
            ("Actions недоступны, check-runs 403", forbidden, actions_down,
             "fail"),
        ]
        default_checks, default_actions = self.gh.check_runs, self.gh.actions
        for label, check_runs, actions, status in cases:
            with self.subTest(сценарий=label):
                self.gh.check_runs = check_runs or default_checks
                self.gh.actions = actions or default_actions
                row = self.ci_token_row(label=label)
                self.assert_status(label, status, row)
                if status == "warn":
                    self.assertIn(WARN_TEXT, row.detail, self.why(label))
                if label == "check-runs 403 rate limit":
                    self.assertNotIn(WARN_TEXT, row.detail, self.why(
                        f"{label}: временный отказ выдан за чтение по "
                        f"Actions"))


class SkipOutcomesTest(DoctorCiTokenSandbox):

    def test_ac12_ci_token_row_skips_without_network_gh_slot_role_artel(self):
        """Обрыв сети, нет `gh`, отказ `gh_env`, процесс роли и запись артели — `skip` с причиной; токен в вывод не попадает.

        Сценарии (`subTest`): любой вызов `gh` без HTTP-ответа (ошибка
        соединения либо таймаут) — `skip`, не `fail`; `gh` не найден
        (`shutil.which` — `None`, запуск — `FileNotFoundError`) — `skip`;
        слот токена пуст (`gh_env` возвращает отказ) — `skip`; в процессе
        роли (`ARTEL_ROLE`) — `skip` с `ROLE_SKIP`, и ни одного вызова `gh`
        к check-runs или Actions; запись артели — `skip` с
        `NOT_APPLICABLE`. Значение токена проекта нигде в выводе не
        встречается.

        Ловит мутацию: обрыв сети читается как `fail` («Actions
        недоступны»), отказ `gh_env` или отсутствие `gh` дают `fail`,
        проверка в процессе роли ходит в сеть (или не помечена
        `ROLE_SKIP`), либо артель получает собственную проверку вместо
        «неприменимо».
        """
        for label, answer in (("обрыв сети", NETWORK), ("таймаут", TIMEOUT)):
            with self.subTest(сценарий=label):
                self.gh.everything = answer
                self.assert_status(label, "skip",
                                   self.ci_token_row(label=label))
        self.gh.everything = None
        with self.subTest(сценарий="нет gh"):
            self.gh.everything, self.gh_present = MISSING, False
            self.assert_status("нет gh", "skip",
                               self.ci_token_row(label="нет gh"))
        self.gh.everything, self.gh_present = None, True
        with self.subTest(сценарий="отказ gh_env"):
            with mock.patch.object(keychain, "token", lambda slot: ""):
                self.assert_status("отказ gh_env", "skip",
                                   self.ci_token_row(label="отказ gh_env"))
        with self.subTest(сценарий="процесс роли"):
            self.gh.calls.clear()
            role = self.rng.choice(sorted(config.STATE_ROLE.values()))
            with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: role}):
                row = self.ci_token_row(label="процесс роли")
            self.assertEqual((row.status, row.detail),
                             ("skip", project_checks.ROLE_SKIP),
                             self.why("процесс роли"))
            self.assertEqual(self.gh.ci_calls(), [], self.why(
                "процесс роли: вызов gh к check-runs/Actions"))
        with self.subTest(сценарий="запись артели"):
            row = self.ci_token_row(config.DEFAULT_TARGET,
                                    self.entries[config.DEFAULT_TARGET],
                                    label="запись артели")
            self.assertEqual((row.status, row.detail),
                             ("skip", project_checks.NOT_APPLICABLE),
                             self.why("запись артели"))
