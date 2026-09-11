"""Приёмочные тесты 01M28NWK5X10J139Z8TD69HFAC: класс пуша (ADR-0016) не
маскирует красный main.

Красен до реализации: `scripts/ci_push_class.py` ещё не существует — любой
подпроцесс-вызов ниже падает (FileNotFoundError у subprocess.run либо
ненулевой код), поэтому все тесты `ClassifierTests` красные до появления
скрипта. Тесты `DevTestSuiteCoverageTests` (AC-8/AC-9) красные по той же
причине для второго файла — `tests/test_ci_push_class.py` тоже ещё не
существует (его создаёт разработчик вместе со скриптом).

Контракт вызова, который лочат эти тесты (SPEC, требования 1 и 6): скрипт
запускается БЕЗ аргументов командной строки — все входы приходят через
переменные окружения GITHUB_EVENT_NAME, GITHUB_REF, GITHUB_SHA (HEAD),
BEFORE (родитель, тем же именем, что несёт текущий bash в ci.yml), плюс
GITHUB_TOKEN/GITHUB_REPOSITORY для запроса `gh api ...` (AC-3). Список
изменённых файлов скрипт вычисляет сам через `git diff --name-only
$BEFORE $HEAD` в текущем каталоге (requirement 1, альтернатива «либо сам
скрипт вызывает git diff --name-only») — под это тесты заводят настоящий
временный git-репозиторий с нужными коммитами, а не передают список
файлов явным входом.

Запрос к GitHub API (`gh api repos/{owner}/{repo}/actions/runs?...`,
AC-3) перехватывается через подставной исполняемый файл `gh` на PATH
(`_install_fake_gh`) — так тест управляет ответом (`FAKE_GH_MODE`:
green/red/empty/error) без обращения к реальной сети и реальному GitHub.
"""
import ast
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "ci_push_class.py"
DEV_TEST_PATH = REPO_ROOT / "tests" / "test_ci_push_class.py"

ZERO_SHA = "0" * 40

FAKE_GH_SOURCE = '''#!/usr/bin/env python3
import json
import os
import sys

mode = os.environ.get("FAKE_GH_MODE", "green")
sha = os.environ.get("FAKE_GH_SHA", "0" * 40)
log = os.environ.get("FAKE_GH_ARGS_LOG")
if log:
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(" ".join(sys.argv[1:]) + "\\n")

if mode == "error":
    sys.stderr.write("fake gh: имитация сетевой ошибки\\n")
    sys.exit(1)
if mode == "empty":
    print(json.dumps({"total_count": 0, "workflow_runs": []}))
    sys.exit(0)

conclusion = "success" if mode == "green" else "failure"
print(json.dumps({
    "total_count": 1,
    "workflow_runs": [
        {"name": "ci", "status": "completed", "conclusion": conclusion,
         "head_sha": sha},
    ],
}))
sys.exit(0)
'''


def _clean_env(extra=None, path_prefix=None):
    """Окружение подпроцесса без унаследованных GIT_*/GITHUB_*/GH_*
    переменных родительского процесса (тесты сами живут в git-репозитории
    и в песочнице роли — их GIT_DIR/GITHUB_* не должны протекать в
    классифицируемый под-git и под-gh)."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("GIT_", "GITHUB_")) and k not in ("GH_TOKEN",)}
    if path_prefix:
        env["PATH"] = f"{path_prefix}{os.pathsep}{env.get('PATH', '')}"
    if extra:
        env.update(extra)
    return env


def _git(repo, *args):
    return subprocess.run(["git", *args], cwd=str(repo), env=_clean_env(),
                          capture_output=True, text=True, timeout=15)


def _init_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "test@example.com")
    _git(path, "config", "user.name", "Test Author")
    return path


def _commit_files(repo, files, message):
    for rel, content in files.items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    commit = _git(repo, "commit", "-q", "-m", message)
    assert commit.returncode == 0, commit.stderr
    sha = _git(repo, "rev-parse", "HEAD")
    return sha.stdout.strip()


def _doc_only_repo(path):
    """before — код и документ, head — меняет только docs/tasks/*.md
    в корне (requirement 3: «все изменённые файлы под docs/, tasks/ или
    *.md в корне»)."""
    repo = _init_repo(path)
    before = _commit_files(
        repo, {"scripts/app.py": "print(1)\n", "README.md": "старое\n"},
        "before — код и документ")
    head = _commit_files(
        repo, {
            "docs/adr/9999-example.md": "adr текст\n",
            "tasks/DEMO0000000000000000000001/SPEC.md": "spec текст\n",
            "CHANGELOG.md": "запись в корне\n",
        }, "head — только документы")
    return repo, before, head


def _install_fake_gh(bindir):
    bindir.mkdir(parents=True, exist_ok=True)
    gh_path = bindir / "gh"
    gh_path.write_text(FAKE_GH_SOURCE, encoding="utf-8")
    gh_path.chmod(0o755)
    return gh_path


def _run_classifier(cwd, env, timeout=30):
    return subprocess.run([sys.executable, str(SCRIPT_PATH)], cwd=str(cwd),
                          env=env, capture_output=True, text=True,
                          timeout=timeout)


class ClassifierTests(unittest.TestCase):

    def test_ac1_stdlib_only_and_stdout_contract(self):
        """`scripts/ci_push_class.py` существует, верхнеуровневые импорты —
        только stdlib (плюс локальные пакеты репозитория), и на валидном
        входе (push в ветку task/**) печатает на stdout строку вида
        `code=true`/`code=false` и непустую строку причины.

        Ловит мутацию: если реализация уберёт строку `code=...` со stdout
        (например станет писать код класса только в $GITHUB_OUTPUT, как
        делала bash-версия) — регэксп по строкам stdout не найдёт
        совпадения и тест покраснеет; импорт стороннего pip-пакета
        (например `requests` вместо `subprocess`+`urllib`/`gh`) завалит
        проверку AST-импортов.
        """
        self.assertTrue(SCRIPT_PATH.is_file(), f"{SCRIPT_PATH} не найден")
        tree = ast.parse(SCRIPT_PATH.read_text(encoding="utf-8"),
                         filename=str(SCRIPT_PATH))
        stdlib = sys.stdlib_module_names
        local_allow = {"orchestrator", "scripts"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    self.assertIn(
                        top, stdlib | local_allow,
                        f"импорт стороннего пакета {alias.name!r} — "
                        f"запрещено требованием 1 (только stdlib)")
            elif isinstance(node, ast.ImportFrom) and not node.level:
                top = (node.module or "").split(".")[0]
                self.assertIn(
                    top, stdlib | local_allow,
                    f"импорт стороннего пакета {node.module!r} — "
                    f"запрещено требованием 1 (только stdlib)")

        with tempfile.TemporaryDirectory() as tmp:
            repo = _init_repo(Path(tmp) / "repo")
            before = _commit_files(repo, {"a.txt": "1\n"}, "before")
            head = _commit_files(repo, {"a.txt": "2\n"}, "head")
            env = _clean_env({
                "GITHUB_EVENT_NAME": "push",
                "GITHUB_REF": "refs/heads/task/01M28NWK5X10J139Z8TD69HFAC",
                "GITHUB_SHA": head,
                "BEFORE": before,
            })
            proc = _run_classifier(repo, env)

        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = [l for l in proc.stdout.splitlines() if l.strip()]
        code_lines = [l for l in lines if re.match(r"^code=(true|false)$", l)]
        self.assertEqual(
            len(code_lines), 1,
            f"ожидалась ровно одна строка code=true|code=false, stdout:\n{proc.stdout}")
        reason_lines = [l for l in lines if l not in code_lines]
        self.assertTrue(reason_lines, "строка причины на stdout не найдена")

    def test_ac2_adr0016_branches_reproduce_bash_dословно(self):
        """Классификация повторяет ADR-0016 дословно: `artifact/**` даёт
        `code=false` независимо от содержимого диффа (даже если дифф
        похож на код, «без диффа» из requirement 2 — ветка не должна
        вообще смотреть на файлы), `task/**` и `pull_request` — всегда
        `code=true`, а push в main без валидной базы диффа (пустой
        BEFORE, нулевой sha, несуществующий в репозитории sha —
        «принудительный пуш»/«ошибка диффа») fail-closed остаётся на
        `code=true`; push в main с кодовым файлом в диффе — тоже `true`.

        Ловит мутацию: если реализация перепутает ветвление (например
        станет вычислять `code=false` для main при пустом BEFORE вместо
        fail-closed true, или начнёт смотреть на дифф для `artifact/**`),
        конкретная subTest вернёт противоположный код.
        """
        with tempfile.TemporaryDirectory() as tmp:
            repo, before, head = _doc_only_repo(Path(tmp) / "repo")
            # head реально меняет только документы; для main-с-кодом ниже
            # используем head2, где затронут и код — не только docs/tasks/*.md.
            head_with_code = _commit_files(
                repo, {"scripts/other.py": "print(2)\n"},
                "head2 — код после документного коммита")

            cases = [
                ("artifact/**, дифф выглядит как код",
                 "push", "refs/heads/artifact/01M28NWK5X10J139Z8TD69HFAC",
                 before, head_with_code, "false"),
                ("task/**, дифф только докcументы",
                 "push", "refs/heads/task/01M28NWK5X10J139Z8TD69HFAC-slug",
                 before, head, "true"),
                ("task/**, дифф код",
                 "push", "refs/heads/task/01M28NWK5X10J139Z8TD69HFAC-slug",
                 before, head_with_code, "true"),
                ("pull_request",
                 "pull_request", "refs/pull/42/merge",
                 before, head, "true"),
                ("main, BEFORE пуст — нет базы диффа",
                 "push", "refs/heads/main", "", head, "true"),
                ("main, BEFORE — нулевой sha (новая ветка)",
                 "push", "refs/heads/main", ZERO_SHA, head, "true"),
                ("main, BEFORE не существует в репозитории (force push)",
                 "push", "refs/heads/main", "f" * 40, head, "true"),
                ("main, дифф содержит код (не только docs/tasks/*.md)",
                 "push", "refs/heads/main", before, head_with_code, "true"),
            ]
            for label, event, ref, before_sha, head_sha, expected in cases:
                with self.subTest(label):
                    env = _clean_env({
                        "GITHUB_EVENT_NAME": event,
                        "GITHUB_REF": ref,
                        "GITHUB_SHA": head_sha,
                        "BEFORE": before_sha,
                    })
                    proc = _run_classifier(repo, env)
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertIn(
                        f"code={expected}", proc.stdout,
                        f"{label}: ожидали code={expected}, stdout:\n{proc.stdout}")

    def test_ac3_doc_push_green_parent_skips_tests(self):
        """Документный пуш в main (все изменённые файлы под docs/, tasks/
        или *.md в корне), для которого GitHub API отдаёт последний
        завершённый прогон workflow `ci` родителя с `conclusion ==
        success`, даёт `code=false`.

        Ловит мутацию: если реализация перепутает условие (например
        станет требовать `status != completed` или проигнорирует
        `conclusion`), для зелёного родителя код останется `true`.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, before, head = _doc_only_repo(root / "repo")
            fakebin = root / "fakebin"
            _install_fake_gh(fakebin)
            env = _clean_env({
                "GITHUB_EVENT_NAME": "push",
                "GITHUB_REF": "refs/heads/main",
                "GITHUB_SHA": head,
                "BEFORE": before,
                "GITHUB_TOKEN": "test-token",
                "GITHUB_REPOSITORY": "example/repo",
                "FAKE_GH_MODE": "green",
                "FAKE_GH_SHA": before,
            }, path_prefix=str(fakebin))
            proc = _run_classifier(repo, env)

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("code=false", proc.stdout, proc.stdout)

    def test_ac4_doc_push_non_success_parent_forces_tests(self):
        """Документный пуш в main даёт `code=true`, если ответ GitHub API
        о родителе — красный прогон (`conclusion == failure`), не
        содержит прогона вовсе (пустой `workflow_runs`), либо запрос к
        API завершился ошибкой (ненулевой код `gh`).

        Ловит мутацию: если реализация трактует отсутствие прогона или
        ошибку API как «пропускаем тесты» (code=false по умолчанию вместо
        fail-closed true) — соответствующая subTest покраснеет.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fakebin = root / "fakebin"
            _install_fake_gh(fakebin)
            for mode in ("red", "empty", "error"):
                with self.subTest(mode):
                    repo, before, head = _doc_only_repo(root / f"repo-{mode}")
                    env = _clean_env({
                        "GITHUB_EVENT_NAME": "push",
                        "GITHUB_REF": "refs/heads/main",
                        "GITHUB_SHA": head,
                        "BEFORE": before,
                        "GITHUB_TOKEN": "test-token",
                        "GITHUB_REPOSITORY": "example/repo",
                        "FAKE_GH_MODE": mode,
                        "FAKE_GH_SHA": before,
                    }, path_prefix=str(fakebin))
                    proc = _run_classifier(repo, env)
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertIn(
                        "code=true", proc.stdout,
                        f"{mode}: ожидали code=true, stdout:\n{proc.stdout}")

    def test_ac5_reason_lines_match_exact_wording_with_parent_sha(self):
        """Причина на stdout для документного пуша воспроизводит одну из
        трёх строк требования 5 дословно, подставляя фактический sha
        родителя в первых двух случаях.

        Ловит мутацию: если разработчик перефразирует текст причины
        (сменит тире на дефис, «тесты идут» на «тесты запущены» и т.п.)
        или забудет подставить настоящий sha — точное сравнение строки
        упадёт.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fakebin = root / "fakebin"
            _install_fake_gh(fakebin)
            cases = [
                ("green", lambda sha: f"документный пуш, родитель {sha} "
                                      f"зелёный — тесты пропущены"),
                ("red", lambda sha: f"родитель {sha} красный — тесты идут"),
                ("empty", lambda sha: "нет данных о родителе — тесты идут"),
            ]
            for mode, expected_fn in cases:
                with self.subTest(mode):
                    repo, before, head = _doc_only_repo(root / f"repo-{mode}")
                    env = _clean_env({
                        "GITHUB_EVENT_NAME": "push",
                        "GITHUB_REF": "refs/heads/main",
                        "GITHUB_SHA": head,
                        "BEFORE": before,
                        "GITHUB_TOKEN": "test-token",
                        "GITHUB_REPOSITORY": "example/repo",
                        "FAKE_GH_MODE": mode,
                        "FAKE_GH_SHA": before,
                    }, path_prefix=str(fakebin))
                    proc = _run_classifier(repo, env)
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    expected = expected_fn(before)
                    self.assertIn(
                        expected, proc.stdout,
                        f"{mode}: не нашли {expected!r} в stdout:\n{proc.stdout}")


# AC-6: manual — правка защищённого .github/workflows/ci.yml сдаётся
# unified-диффом приложением к PLAN.md (требование 8), а не изменением
# файла в кодовой ветке задачи; факт «job changes вызывает python3
# scripts/ci_push_class.py и передаёт GITHUB_TOKEN» и факт «дифф
# проходит git apply --check на чистом дереве» — свойства ТЕКСТА диффа
# в PLAN.md, а не рантайм-поведения кода этой ветки. Детерминированный
# unittest здесь бессмыслен: ci.yml в этой ветке не меняется вовсе
# (правит только Оператор отдельным MR), а стабильного адреса файла с
# диффом-приложением SPEC не называет. Оператор/ревьювер проверяют
# `git apply --check` и содержимое диффа на приёмке.

# AC-7: manual — по тем же причинам, что и AC-6: абзац «наследование
# итога родителя» в docs/adr/0016-ci-jobs-by-push-class.md (защищённый
# путь) сдаётся unified-диффом приложением к PLAN.md, файл ADR в этой
# ветке не меняется. Содержательность формулировки абзаца — предмет
# ревью текста Оператором, не автоматической проверки.


class DevTestSuiteCoverageTests(unittest.TestCase):

    def test_ac8_dev_suite_covers_adr0016_branches_and_is_green(self):
        """`tests/test_ci_push_class.py` (разрабатывается вместе со
        скриптом) существует, синтаксически валиден и покрывает ветки
        `artifact/**`, `task/**` и `pull_request`; прогон этого файла
        через `python3 -m unittest` зелёный.

        Ловит мутацию: если разработчик не заведёт тест на одну из веток
        ADR-0016 (например забудет `task/**`), соответствующий маркер не
        найдётся в исходнике файла и assertIn упадёт; красный прогон
        файла — assertEqual(returncode, 0) падает.
        """
        self.assertTrue(DEV_TEST_PATH.is_file(), f"{DEV_TEST_PATH} не найден")
        source = DEV_TEST_PATH.read_text(encoding="utf-8")
        for marker in ("artifact/", "task/", "pull_request"):
            self.assertIn(
                marker, source,
                f"tests/test_ci_push_class.py не упоминает ветку "
                f"{marker!r} классификации ADR-0016 (требование 9)")

        proc = subprocess.run(
            [sys.executable, "-m", "unittest",
             "tests.test_ci_push_class", "-v"],
            cwd=str(REPO_ROOT), env=_clean_env(),
            capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_ac9_dev_suite_covers_doc_push_parent_status_and_sha_reason(self):
        """`tests/test_ci_push_class.py` покрывает документный пуш при
        красном/зелёном родителе, ошибку запроса к API и упоминание sha
        родителя в причине на stdout (требование 9).

        Ловит мутацию: если разработчик не заведёт сценарий с ошибкой
        API или с проверкой родительского `conclusion`, соответствующий
        текстовый маркер не найдётся в исходнике файла.
        """
        self.assertTrue(DEV_TEST_PATH.is_file(), f"{DEV_TEST_PATH} не найден")
        source = DEV_TEST_PATH.read_text(encoding="utf-8")
        for marker in ("conclusion", "success", "failure", "родител"):
            self.assertIn(
                marker, source,
                f"tests/test_ci_push_class.py не упоминает {marker!r} "
                f"(статус/причина родителя, требование 9)")


if __name__ == "__main__":
    unittest.main()
