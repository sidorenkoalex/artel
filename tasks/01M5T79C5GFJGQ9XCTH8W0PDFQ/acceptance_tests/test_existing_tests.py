"""Существующие тесты семи мест и `tests/test_invariants.py` не тронуты
задачей, а названные в SPEC тесты зелёные на её коде.

Группа: разовый
Зелёный с рождения: до реализации названные тесты зелёные на базе, а файлы не изменены задачей; тест держит, что перенос мест в `gitcmd` не меняет их исхода и не правит их текст.

Пути задачи — `changed_paths()` помощника пульта (`_pult.py`): закоммиченный
дифф от базы плюс неотслеживаемые файлы. Тесты запускаются отдельным
процессом `pytest` в рабочей копии (`CODE_ROOT`) с теми же флагами, что
прогон планки.
"""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, changed_paths  # noqa: E402

TARGETS = [
    "tests/test_01m4s24963r9h18an2xdp6r15b_cache.py",
    "tests/test_01m4tvbt9zcrqdy669qv3s95ma_reference.py",
    "tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py",
    "tests/test_01m5r45m0fqb2wvrhybrf81jm6_batched_reads.py"
    "::test_ac5_suite_tree_hash_runs_one_rev_parse",
    "tests/test_outcome_gate_module.py::test_unexpected_header_is_prepare_refusal",
    "tests/test_01m42pencs26d0656x8fr7dfa7_gitcmd_explicit_repo.py"
    "::GitcmdWithoutRepoOnlyFromAllowListTest"
    "::test_ac8_every_call_without_repo_is_in_the_allow_list",
]

# Тесты у строк, названных AC-3, внутри файлов, прогоняемых целиком.
NAMED = [
    "tests/test_01m4s24963r9h18an2xdp6r15b_cache.py::SourceReadingTest"
    "::test_ac10_two_git_launches_whatever_the_number_of_files",
    "tests/test_01m4s24963r9h18an2xdp6r15b_cache.py::SourceReadingTest"
    "::test_ac10_no_cat_file_without_suitable_blobs",
    "tests/test_01m4s24963r9h18an2xdp6r15b_cache.py::SourceReadingTest"
    "::test_ac10_malformed_sha_is_refused_before_any_git_launch",
    "tests/test_01m4s24963r9h18an2xdp6r15b_cache.py::SourceReadingTest"
    "::test_ac10_shared_deadline_stops_the_build",
    "tests/test_01m4s24963r9h18an2xdp6r15b_cache.py::StatesTest"
    "::test_ac12_never_raises_on_git_write_or_parse_failure",
    "tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py::UnreadConventionsTest"
    "::test_ac9_unreadable_base_marked_unread_and_journaled",
    "tests/test_01m5634e094qf7jx8hd3ksg4kn_external_brief.py::UnreadConventionsTest"
    "::test_ac10_failed_file_read_marked_unread_not_absent",
]


def pytest_run(*targets: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", *targets, "-q", "-p", "no:cacheprovider",
         "-p", "timeout", "-o", "timeout=120"],
        cwd=CODE_ROOT, capture_output=True, text=True, timeout=600)


def test_ac2_invariants_file_unchanged():
    """Задача не меняет `tests/test_invariants.py`: сторож — отдельный файл.

    Ловит мутацию: сторож дописан классом в `tests/test_invariants.py`
    рядом с `CarpentryGitCallsGoThroughGitcmdTest` — путь среди путей задачи.
    """
    assert "tests/test_invariants.py" not in changed_paths()


@pytest.mark.parametrize("target", TARGETS)
def test_ac3_existing_place_tests_green_without_edit(target):
    """Существующий тест мест не правлен задачей и зелёный на её коде.

    Файл теста не входит в пути задачи; тест (файл целиком или узел у
    названной строки) проходит отдельным прогоном `pytest`.

    Ловит мутацию: место 4 перенесено на функцию `gitcmd` поверх
    `subprocess.run` — шпион `subprocess.Popen` теста
    `test_ac10_two_git_launches_whatever_the_number_of_files` видит иное
    число процессов, файл `…_cache.py` красный.
    """
    path = target.split("::")[0]
    assert path not in changed_paths()
    res = pytest_run(target)
    assert res.returncode == 0, res.stdout[-4000:] + res.stderr[-2000:]


def test_ac3_named_tests_still_exist_and_pass():
    """Тесты у строк, названных AC-3 внутри файлов, существуют и зелёные.

    Узлы прогоняются явно: пропавший или переименованный тест даёт
    ошибку сбора.

    Ловит мутацию: тест `test_ac9_unreadable_base_marked_unread_and_journaled`
    переименован при «подгонке» под новый путь git места 2 — узел не
    найден, прогон красный.
    """
    res = pytest_run(*NAMED)
    assert res.returncode == 0, res.stdout[-4000:] + res.stderr[-2000:]
    assert f"{len(NAMED)} passed" in res.stdout
