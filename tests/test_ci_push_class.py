"""Юнит-тесты scripts/ci_push_class.py (01M28NWK5X10J139Z8TD69HFAC):
классификатор класса пуша CI (ADR-0016) плюс наследование итога родителя
для документного пуша в main (требования 1–9).
"""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts import ci_push_class  # noqa: E402

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "ci_push_class.py"

PARENT_SHA = "a" * 40
HEAD_SHA = "b" * 40


def _completed(returncode=0, stdout="", stderr=""):
    return subprocess.CompletedProcess(["gh"], returncode, stdout, stderr)


class AdrClassificationTest(unittest.TestCase):
    """AC-2/AC-8: логика классификации ADR-0016 сохранена дословно —
    те же ответы, что давала bash-версия job `changes`."""

    def test_artifact_branch_is_code_false_without_touching_git_or_gh(self):
        """Ловит мутацию: код на artifact/** ошибочно идёт диффом/API —
        правило AC-2 не должно трогать git/gh вовсе."""
        with mock.patch("subprocess.run") as run:
            code, reason = ci_push_class.classify(
                "push", "refs/heads/artifact/01m1abc", PARENT_SHA, HEAD_SHA)
        run.assert_not_called()
        self.assertFalse(code)

    def test_artifact_branch_code_is_false(self):
        """Ловит мутацию: правило artifact/** перестаёт выставлять
        code=false, или причина теряет слово "артефактная"."""
        code, reason = ci_push_class.classify(
            "push", "refs/heads/artifact/01m1abc", PARENT_SHA, HEAD_SHA)
        self.assertFalse(code)
        self.assertIn("артефактная", reason)

    def test_task_branch_is_always_code_true(self):
        """Ловит мутацию: ветка task/** с исключительно документным диффом
        ошибочно получает code=false — правило «task/** всегда true»
        должно игнорировать содержимое диффа."""
        code, reason = ci_push_class.classify(
            "push", "refs/heads/task/01m1abc-slug", PARENT_SHA, HEAD_SHA,
            changed_files=["docs/backlog.md"])
        self.assertTrue(code)

    def test_pull_request_is_always_code_true(self):
        """Ловит мутацию: событие pull_request ошибочно классифицируется
        как документный пуш и получает code=false вместо безусловного
        code=true."""
        code, reason = ci_push_class.classify(
            "pull_request", "refs/heads/task/01m1abc-slug", PARENT_SHA, HEAD_SHA,
            changed_files=["docs/backlog.md"])
        self.assertTrue(code)

    def test_main_code_change_is_code_true(self):
        """Ловит мутацию: пуш в main с изменением кода (файл вне docs/
        tasks/*.md) ошибочно признаётся документным и получает
        code=false."""
        code, reason = ci_push_class.classify(
            "push", "refs/heads/main", PARENT_SHA, HEAD_SHA,
            changed_files=["orchestrator/config.py"])
        self.assertTrue(code)

    def test_main_mixed_doc_and_code_is_code_true(self):
        """Ловит мутацию: смешанный дифф (документный файл + кодовый файл)
        ошибочно признаётся полностью документным — единственный файл вне
        docs/tasks/*.md должен ломать весь документный класс, та же
        логика, что `grep -Ev` в исходном bash."""
        code, reason = ci_push_class.classify(
            "push", "refs/heads/main", PARENT_SHA, HEAD_SHA,
            changed_files=["docs/backlog.md", "orchestrator/config.py"])
        self.assertTrue(code)

    def test_main_no_diff_base_is_code_true(self):
        """Ловит мутацию: пустая база диффа (before="") трактуется как
        повод разрешить code=false вместо fail-closed code=true."""
        code, reason = ci_push_class.classify(
            "push", "refs/heads/main", "", HEAD_SHA)
        self.assertTrue(code)

    def test_main_forced_push_null_before_is_code_true(self):
        """Ловит мутацию: нулевой sha родителя (принудительный пуш) не
        распознаётся как «нет базы диффа» и получает code=false вместо
        fail-closed code=true."""
        code, reason = ci_push_class.classify(
            "push", "refs/heads/main", "0" * 40, HEAD_SHA)
        self.assertTrue(code)

    def test_main_diff_error_is_code_true(self):
        """Ловит мутацию: ненулевой код возврата `git diff --name-only`
        трактуется как пустой (документный) дифф вместо fail-closed
        code=true."""
        with mock.patch("subprocess.run") as run:
            run.side_effect = [
                _completed(returncode=0),   # git cat-file -e before
                _completed(returncode=1),   # git diff --name-only упал
            ]
            code, reason = ci_push_class.classify(
                "push", "refs/heads/main", PARENT_SHA, HEAD_SHA)
        self.assertTrue(code)


class DocPushParentInheritanceTest(unittest.TestCase):
    """AC-3/AC-4/AC-5/AC-9: документный пуш main наследует итог родителя."""

    def _gh_response(self, conclusion, name="ci", status="completed"):
        payload = {"workflow_runs": [
            {"name": name, "status": status, "conclusion": conclusion},
        ]}
        return _completed(returncode=0, stdout=json.dumps(payload))

    def test_green_parent_gives_code_false(self):
        """Ловит мутацию: зелёный родитель (conclusion=success) не даёт
        документному пушу code=false, либо строка причины не называет sha
        родителя дословно."""
        with mock.patch("subprocess.run", return_value=self._gh_response("success")):
            code, reason = ci_push_class.classify(
                "push", "refs/heads/main", PARENT_SHA, HEAD_SHA,
                changed_files=["docs/backlog.md", "tasks/T1/SPEC.md"])
        self.assertFalse(code)
        self.assertEqual(
            f"документный пуш, родитель {PARENT_SHA} зелёный — тесты пропущены",
            reason)

    def test_red_parent_gives_code_true(self):
        """Ловит мутацию: красный родитель (conclusion=failure) ошибочно
        даёт code=false вместо fail-closed code=true, либо причина не
        называет sha родителя."""
        with mock.patch("subprocess.run", return_value=self._gh_response("failure")):
            code, reason = ci_push_class.classify(
                "push", "refs/heads/main", PARENT_SHA, HEAD_SHA,
                changed_files=["docs/backlog.md"])
        self.assertTrue(code)
        self.assertEqual(f"родитель {PARENT_SHA} красный — тесты идут", reason)

    def test_no_run_for_parent_gives_code_true(self):
        """Ловит мутацию: пустой список прогонов (нет данных о родителе)
        ошибочно трактуется как зелёный родитель и даёт code=false."""
        with mock.patch("subprocess.run",
                        return_value=_completed(returncode=0,
                                                stdout=json.dumps({"workflow_runs": []}))):
            code, reason = ci_push_class.classify(
                "push", "refs/heads/main", PARENT_SHA, HEAD_SHA,
                changed_files=["docs/backlog.md"])
        self.assertTrue(code)
        self.assertEqual("нет данных о родителе — тесты идут", reason)

    def test_api_error_gives_code_true(self):
        """Ловит мутацию: ненулевой код возврата `gh api` (ошибка запроса)
        не переводит классификатор в fail-closed code=true."""
        with mock.patch("subprocess.run",
                        return_value=_completed(returncode=1, stderr="rate limited")):
            code, reason = ci_push_class.classify(
                "push", "refs/heads/main", PARENT_SHA, HEAD_SHA,
                changed_files=["docs/backlog.md"])
        self.assertTrue(code)
        self.assertEqual("нет данных о родителе — тесты идут", reason)

    def test_api_bad_json_gives_code_true(self):
        """Ловит мутацию: битый JSON в stdout `gh api` не перехватывается
        и валит классификатор исключением вместо fail-closed code=true."""
        with mock.patch("subprocess.run",
                        return_value=_completed(returncode=0, stdout="не json")):
            code, reason = ci_push_class.classify(
                "push", "refs/heads/main", PARENT_SHA, HEAD_SHA,
                changed_files=["docs/backlog.md"])
        self.assertTrue(code)
        self.assertEqual("нет данных о родителе — тесты идут", reason)

    def test_gh_not_found_gives_code_true(self):
        """Ловит мутацию: OSError при вызове `gh` (бинарь не найден) не
        перехватывается и не сводится к fail-closed code=true, как у
        `orchestrator/ci.py::gh`."""
        with mock.patch("subprocess.run", side_effect=OSError("no such file")):
            code, reason = ci_push_class.classify(
                "push", "refs/heads/main", PARENT_SHA, HEAD_SHA,
                changed_files=["docs/backlog.md"])
        self.assertTrue(code)
        self.assertEqual("нет данных о родителе — тесты идут", reason)

    def test_ignores_run_of_other_workflow(self):
        """Ловит мутацию: фильтр по name == "ci" пропадает, и зелёный
        прогон СТОРОННЕГО workflow на том же head_sha ошибочно даёт
        code=false вместо учёта красного прогона `ci`."""
        payload = {"workflow_runs": [
            {"name": "other", "status": "completed", "conclusion": "success"},
            {"name": "ci", "status": "completed", "conclusion": "failure"},
        ]}
        with mock.patch("subprocess.run",
                        return_value=_completed(returncode=0, stdout=json.dumps(payload))):
            code, reason = ci_push_class.classify(
                "push", "refs/heads/main", PARENT_SHA, HEAD_SHA,
                changed_files=["docs/backlog.md"])
        self.assertTrue(code)
        self.assertIn("красный", reason)


class OutputFormatTest(unittest.TestCase):
    """AC-1/AC-5: печать двух строк на stdout — code=true|false и причина,
    называющая sha родителя. Контракт вызова (requirement 1/6, залочен
    tasks/01M28NWK5X10J139Z8TD69HFAC/acceptance_tests/test_ci_push_class.py)
    — БЕЗ аргументов командной строки, входы через переменные окружения
    GITHUB_EVENT_NAME/GITHUB_REF/GITHUB_SHA/BEFORE."""

    def _env(self, **extra):
        env = dict(os.environ)
        env.update(extra)
        return env

    def test_script_prints_code_and_reason_lines(self):
        """Ловит мутацию: точка входа `main()` печатает не ровно две
        строки, строка `code=` не идёт первой, либо причина не содержит
        слово "артефактная" — контракт вызова из ci.yml/приёмочных тестов
        расходится."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            env=self._env(GITHUB_EVENT_NAME="push",
                          GITHUB_REF="refs/heads/artifact/01m1abc",
                          BEFORE=PARENT_SHA, GITHUB_SHA=HEAD_SHA),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(0, result.returncode)
        lines = result.stdout.splitlines()
        self.assertEqual(2, len(lines))
        self.assertEqual("code=false", lines[0])
        self.assertIn("артефактная", lines[1])

    def test_script_reads_before_and_head_from_env_on_task_branch(self):
        """Ловит мутацию: `main()` не читает BEFORE/GITHUB_SHA из
        окружения (например, падает на None) — ветка task/** не даёт
        code=true, ломая контракт входа без CLI-аргументов."""
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            env=self._env(GITHUB_EVENT_NAME="push",
                          GITHUB_REF="refs/heads/task/01m1abc-slug",
                          BEFORE=PARENT_SHA, GITHUB_SHA=HEAD_SHA),
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(0, result.returncode)
        self.assertEqual("code=true", result.stdout.splitlines()[0])


if __name__ == "__main__":
    unittest.main()
