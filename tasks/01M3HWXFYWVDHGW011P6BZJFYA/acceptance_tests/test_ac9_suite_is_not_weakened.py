"""AC-9 (tasks/01M3HWXFYWVDHGW011P6BZJFYA/SPEC.md): существующий
`tests/test_test_integrity_gate.py` и остальной набор не ослаблены — ни
одного удалённого, переименованного или пропущенного теста;
`tests/test_invariants.py` проходит без правок.

Полный набор `tests/` здесь НЕ прогоняется целиком: его гоняют CI и
автогейт приёмки (`orchestrator/acceptance.py::run_full_suite` — условие
того же гейта, что исполняет эту планку), а копия всего набора внутри
планки — не проверка, а второй CI (`skills/test-authoring.md`).
Прогоняется `tests/test_test_integrity_gate.py` — набор самого узла
(0.4 с). `tests/test_invariants.py` здесь НЕ прогоняется по машинной
причине: он один идёт ~118 с, а раннер планки отводит отдельному тесту
`timeout=120` (`acceptance._pytest_command`/`stack.PER_TEST_TIMEOUT_SEC`)
— прогон упирался бы в таймаут вместо проверки. Его зелёность держат тот
же `run_full_suite` и CI; половину критерия «без правок» планка
проверяет здесь побайтно.

«Обеззубленный» тест (ожидание переписано ВНУТРИ метода, имя и маркеры
на месте) статическим сравнением не ловится — это предмет ревью по
диффу; планка держит то, что проверяемо механически: состав тестовых
методов и число выключателей по ВСЕМУ набору `tests/`, плюс неизменность
`tests/test_invariants.py` целиком.

База сравнения берётся ДИНАМИЧЕСКИ — `git merge-base` головы рабочей
копии с `origin/<main>` либо локальным `<main>` (`config.MAIN_BRANCH`,
не литерал «main»): тот же приём и тот же источник базы, что у самого
узла (`gitcmd.diff_base`), поэтому подтяжка main в ветку задачи планку
не ломает.

Зелёный с рождения: набор сегодня цел и зелен — тест сохранения
существующего поведения. Он краснеет, когда мешающий новому правилу тест
`tests/test_test_integrity_gate.py` (например ожидание «маркер пропуска в
новом файле — находка») удалён, переименован или выключен вместо
приведения кода к нему, либо когда правка задевает
`tests/test_invariants.py`, который SPEC называет файлом только для
чтения.
"""
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts import guard  # noqa: E402

from _sandbox import REPO_ROOT  # noqa: E402
from orchestrator import config  # noqa: E402

#: Набор самого узла, названный критерием поимённо, — прогоняется здесь.
INTEGRITY_SUITE = "tests/test_test_integrity_gate.py"

#: Файл, который критерий требует оставить вовсе без правок.
READ_ONLY_SUITE = "tests/test_invariants.py"


def _git(*args) -> tuple:
    result = subprocess.run(["git", *args], cwd=REPO_ROOT,
                            capture_output=True, text=True, timeout=60)
    return result.returncode, result.stdout


def base_ref() -> str:
    """merge-base головы рабочей копии с main — та же база, что у узла
    (`gitcmd.diff_base`): сначала `origin/<main>`, затем локальный
    `<main>`."""
    for candidate in (f"origin/{config.MAIN_BRANCH}", config.MAIN_BRANCH):
        code, out = _git("merge-base", candidate, "HEAD")
        if code == 0 and out.strip():
            return out.strip()
    raise AssertionError(
        f"база сравнения не определена: ни origin/{config.MAIN_BRANCH}, "
        f"ни {config.MAIN_BRANCH} не дают merge-base с HEAD")


def base_files(ref: str) -> list:
    code, out = _git("ls-tree", "-r", "--name-only", ref, "tests/")
    if code != 0:
        raise AssertionError(f"состав {ref}:tests/ не прочитан")
    return [line for line in out.splitlines() if line.endswith(".py")]


def base_source(ref: str, rel_path: str) -> str:
    code, out = _git("show", f"{ref}:{rel_path}")
    if code != 0:
        raise AssertionError(f"{ref}:{rel_path} не прочитан")
    return out


def head_source(rel_path: str) -> str | None:
    path = REPO_ROOT / rel_path
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def disabler_count(source: str) -> int:
    """Число выключателей теста — ровно те маркеры, которые считает
    ослаблением сам узел (`guard.test_skip_markers`), а не самодельный
    перечень строк."""
    return sum(len(markers)
               for markers in guard.test_skip_markers(source).values())


class SuiteIsNotWeakenedTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.base = base_ref()

    def test_ac9_integrity_gate_suite_passes_on_the_branch(self):
        """`tests/test_test_integrity_gate.py` — набор самого узла —
        прогоняется целиком и проходит без единого провала.

        Ловит мутацию: новое правило вписано в узел так, что существующие
        ожидания гейта ломаются (например маркер пропуска перестаёт
        попадать в находки вовсе, а не только условный с причиной), и
        вместо приведения правила к набору красноту чинят подгонкой —
        прогон назовёт провалившийся метод.
        """
        self.assertTrue((REPO_ROOT / INTEGRITY_SUITE).is_file(),
                        f"{INTEGRITY_SUITE} исчез из ветки (AC-9)")

        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
             INTEGRITY_SUITE],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=90)

        self.assertEqual(
            0, result.returncode,
            f"{INTEGRITY_SUITE} не зелёный:\n"
            + result.stdout[-4000:] + result.stderr[-2000:])

    def test_ac9_no_test_method_of_the_suite_disappeared(self):
        """Каждый тестовый метод, существовавший в `tests/` базы
        сравнения, существует в ветке под тем же квалифицированным именем
        и в том же файле.

        Ловит мутацию: тест, мешающий новому правилу, удалён или
        переименован вместо приведения кода к нему — `assertEqual`
        назовёт исчезнувшее имя вместе с файлом.
        """
        gone = []
        for rel_path in base_files(self.base):
            head = head_source(rel_path)
            if head is None:
                gone.append(f"{rel_path}: файла нет")
                continue
            before = set(guard.qualified_test_methods(base_source(self.base,
                                                                  rel_path)))
            after = set(guard.qualified_test_methods(head))
            gone.extend(f"{rel_path}{guard.TEST_NAME_SEP}{name}"
                        for name in sorted(before - after))

        self.assertEqual(
            [], gone,
            "тестовый метод(ы) базы сравнения исчезли из ветки — удаление "
            "или переименование теста это ослабление проверки (AC-9): "
            + ", ".join(gone))

    def test_ac9_no_disabler_was_added_to_the_suite(self):
        """Число выключателей теста (`@skip`/`@expectedFailure`/
        `self.skipTest(` и родня) ни в одном файле `tests/` не выросло
        против базы сравнения.

        Ловит мутацию: мешающий тест формально оставлен на месте (имя не
        исчезло, предыдущий метод его не поймает), но выключен
        декоратором или вызовом пропуска — набор снова зелёный, а
        проверка не делается; ровно тот способ, который эта задача
        описывает как ослабление.
        """
        grown = []
        for rel_path in base_files(self.base):
            head = head_source(rel_path)
            if head is None:
                continue
            before = disabler_count(base_source(self.base, rel_path))
            after = disabler_count(head)
            if after > before:
                grown.append(f"{rel_path}: было {before}, стало {after}")

        self.assertEqual([], grown,
                         "в наборе tests/ появились выключатели тестов "
                         "(AC-9): " + ", ".join(grown))

    def test_ac9_invariants_suite_is_untouched(self):
        """`tests/test_invariants.py` в ветке байт-в-байт совпадает с
        базой сравнения — критерий требует, чтобы он проходил БЕЗ правок,
        и SPEC («Не входит») называет его файлом только для чтения.

        Ловит мутацию: запись инварианта 38 или его проверка подогнаны
        под новое правило вместо того, чтобы новое правило уложилось в
        существующий инвариант — самый дешёвый способ «позеленить» и
        ровно тот, который принцип целостности запрещает роли.
        """
        head = head_source(READ_ONLY_SUITE)

        self.assertIsNotNone(head, f"{READ_ONLY_SUITE} исчез из ветки (AC-9)")
        self.assertEqual(
            base_source(self.base, READ_ONLY_SUITE), head,
            f"{READ_ONLY_SUITE} правлен на ветке — критерий требует, чтобы "
            f"он проходил БЕЗ правок (AC-9)")


if __name__ == "__main__":
    unittest.main()
