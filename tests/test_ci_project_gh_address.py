"""Адресация `gh` функций `orchestrator/ci.py` репозиторию внешнего проекта:
разбор адреса, отказы и признак артели (SPEC 01M55V7WB94C9BZXTXTTH83YWV,
ANSWER-1, пункты Н-1..Н-4).

Свойства, не покрытые долгоживущим файлом задачи
`tests/test_01m55v7wb94c9bzxtxtth83ywv_project_gh.py`. Запуски `gh`
перехватываются подменой `subprocess.run`: настоящий `gh` не нужен, сети нет.
"""
import json
import subprocess
from unittest import mock

from orchestrator import ci, config, repo_context
from tests.sandbox import TmpRootTest, artel_target_entry

SHA = "f" * 40
OWNER = "ownerx"
NAME = "projy"


class ProjectGhAddressTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        self.project = "uchebproj"
        self.write_url(f"https://localhost/{OWNER}/{NAME}.git")
        self.clone = repo_context.clone_path(self.project)
        self.clone.mkdir(parents=True)
        self.calls = []

    def write_url(self, url: str) -> None:
        self.url = url
        config.TARGETS.write_text(
            "targets:\n" + artel_target_entry()
            + f"  {self.project}:\n    forge: github\n    url: {url}\n"
              f"    base: trunk\n    token_slot: {self.project}-slot\n"
              f"    no_paths: []\n    project_skills: []\n"
              f"    merge_gate: operator\n", encoding="utf-8")

    def fake_run(self, cmd, *args, **kwargs):
        self.calls.append((list(cmd), kwargs.get("env")))
        payload = {"total_count": 1, "check_runs": [
            {"name": "py", "status": "completed", "conclusion": "success"}]}
        return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")

    def recording(self):
        return mock.patch.object(subprocess, "run", side_effect=self.fake_run)

    def test_clone_treated_as_artel_by_predicate_calls_gh_like_artel(self):
        """Клон проекта, который признак `repo_context.is_artel` зовёт артелью,
        — вызов артели: без `GH_REPO`, `--repo` и своего окружения (Н-1).

        Без подмены тот же вызов несёт `GH_REPO=<владелец>/<имя>`.

        Ловит мутацию: внешний проект узнаётся не признаком `is_artel`, а
        своей сверкой пути или имени — под подменой признака `gh` всё равно
        получает `GH_REPO` проекта.
        """
        with self.recording():
            runs, why = ci.check_runs(SHA, repo=self.clone)
        self.assertIsNotNone(runs, why)
        self.assertEqual(self.calls[-1][1]["GH_REPO"], f"{OWNER}/{NAME}")
        self.calls.clear()
        clone = self.clone
        with mock.patch.object(repo_context, "is_artel",
                               lambda s=None: s == clone
                               or s == config.DEFAULT_TARGET), \
                self.recording():
            runs, why = ci.check_runs(SHA, repo=self.clone)
        self.assertIsNotNone(runs, why)
        self.assertEqual(len(self.calls), 1, self.calls)
        argv, env = self.calls[0]
        self.assertIsNone(env, f"у вызова артели своё окружение: {env}")
        self.assertNotIn("--repo", argv)

    def test_owner_and_name_from_bare_https_and_scp_without_git(self):
        """`GH_REPO` из голого https-адреса и scp без `.git` (Н-2).

        Ловит мутацию: разбор требует `.git` в конце либо не знает scp-вид
        — `gh api` получает отказ «вид адреса не разобран» или не тот
        `GH_REPO`.
        """
        for url in (f"https://localhost/{OWNER}/{NAME}",
                    f"git@localhost:{OWNER}/{NAME}"):
            with self.subTest(url=url):
                self.calls.clear()
                with self.recording():
                    res = ci.gh("api", "repos/{owner}/{repo}", repo=url)
                self.assertEqual(res.returncode, 0, res.stderr)
                argv, env = self.calls[0]
                self.assertEqual(env["GH_REPO"], f"{OWNER}/{NAME}")
                self.assertNotIn("--repo", argv)

    def test_unparsed_url_refuses_only_gh_api(self):
        """Неразобранный адрес отказывает только `gh api`; `gh run`/`gh pr` —
        с `--repo <url>`, как прежде; отказ называет адрес и причину (Н-3).

        Ловит мутацию: отказ разбора ставится всем видам вызова (`gh run`
        не запущен) либо его текст не называет адрес или причину.
        """
        url = f"ssh://git@localhost/{OWNER}/{NAME}.git"
        with self.recording():
            res = ci.gh("api", "repos/{owner}/{repo}", repo=url)
        self.assertNotEqual(res.returncode, 0)
        self.assertEqual(self.calls, [])
        self.assertIn(url, res.stderr)
        self.assertIn("вид адреса не разобран", res.stderr)
        for args in (("run", "list"), ("pr", "view", "task/x")):
            with self.subTest(args=args):
                self.calls.clear()
                with self.recording():
                    res = ci.gh(*args, repo=url)
                self.assertEqual(res.returncode, 0, res.stderr)
                argv = self.calls[0][0]
                self.assertEqual(argv[-2:], ["--repo", url])

    def test_project_area_without_record_refuses(self):
        """Путь в области проекта без записи `targets.yaml` — именованный
        отказ, `gh` не запущен (Н-4).

        Ловит мутацию: неразрешённый проект молча считается артелью — `gh`
        запускается без `GH_REPO` и спрашивает репозиторий артели.
        """
        ghost = "bezzapisi"
        path = repo_context.clone_path(ghost)
        path.mkdir(parents=True)
        for what, call in (
                ("check_runs", lambda: ci.check_runs(SHA, repo=path)[1]),
                ("check_run_workflow_run",
                 lambda: ci.check_run_workflow_run("1", repo=path)[1]),
                ("trigger_rerun",
                 lambda: ci.trigger_rerun("task/x", "1", repo=path))):
            with self.subTest(функция=what):
                self.calls.clear()
                with self.recording():
                    why = call()
                self.assertEqual(self.calls, [], what)
                self.assertIn(ghost, why)
                self.assertIn("не запущен", why)
