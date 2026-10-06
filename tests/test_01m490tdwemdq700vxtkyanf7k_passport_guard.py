"""Паспорт задачи без frontmatter и `scripts/guard.py` — режим `--all` и
одиночный файл.

Группа: долгоживущий
Красен до реализации: guard ещё отдаёт PASSPORT.md первого уровня в проверку артефакта — AC-1/AC-3 получают «нет frontmatter» по паспорту, AC-6 — код 1 без строки пропуска; AC-4 красен, потому что белый список acceptance_tests сегодня пускает любой .md и PASSPORT.md там получает «нет frontmatter» вместо «посторонний файл в каталоге планки»; AC-2/AC-5/AC-7 держат прежнее поведение и зелёные уже сейчас.

Каждый сценарий строит во временном каталоге дерево `tasks` с каталогом
живой задачи (номер задачи случаен, `docs/retro/<id>.md` для него нет) и
запускает настоящий `scripts/guard.py` подпроцессом из корня этого дерева
— ровно так, как его зовёт гейт мержа. Номер задачи и строки паспорта
порождаются модулем `random` при каждом запуске; зерно печатается и входит
в текст провала.
"""
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parent.parent / "scripts" / "guard.py"
TASKS_DIR = "tasks"
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
STATES = ["new", "analysis", "spec_review", "tests_writing", "in_dev",
          "in_review", "acceptance", "merge_gate", "done"]
ACTORS = ["pult", "operator", "analyst", "developer", "reviewer"]
ROUNDS = 3

EXTRANEOUS_TASK_ROOT = "посторонний файл в каталоге задачи"
EXTRANEOUS_PLANK = "посторонний файл в каталоге планки"
NO_FRONTMATTER = "нет frontmatter"
PASSPORT_SKIPPED = "паспорт задачи, не артефакт роли — пропущен"


def random_task_id(rng: random.Random) -> str:
    return "01ZZ" + "".join(rng.choice(CROCKFORD) for _ in range(22))


def passport_text(rng: random.Random) -> str:
    """Паспорт в формате пульта: заголовок и строки «<время> <состояние>
    actor=<кто>», без frontmatter."""
    lines = ["# Паспорт живой задачи", ""]
    for _ in range(rng.randint(1, 6)):
        stamp = (f"2026-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}T"
                 f"{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}:"
                 f"{rng.randint(0, 59):02d}Z")
        lines.append(f"{stamp} {rng.choice(STATES)} actor={rng.choice(ACTORS)}")
    return "\n".join(lines) + "\n"


def valid_tz_text(task_id: str) -> str:
    """Артефакт, корректный по guard: ТЗ Оператора — тело свободное,
    обязательных разделов нет."""
    return ("---\n"
            f"task: {task_id}\n"
            "type: tz\n"
            "author_role: operator\n"
            "status: ready\n"
            "---\n\n"
            "# ТЗ\n\nСвободный текст задачи.\n")


class PassportGuardTest(unittest.TestCase):
    def setUp(self):
        self.seed = random.randrange(2 ** 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def make_tree(self, root: Path, task_id: str) -> Path:
        task_dir = root / TASKS_DIR / task_id
        task_dir.mkdir(parents=True)
        (task_dir / "TZ.md").write_text(valid_tz_text(task_id),
                                        encoding="utf-8")
        return task_dir

    def run_guard(self, root: Path, *args: str) -> tuple:
        proc = subprocess.run([sys.executable, str(GUARD), *args], cwd=root,
                              capture_output=True, text=True, timeout=110)
        return proc.returncode, proc.stdout + proc.stderr

    def rel(self, *parts: str) -> str:
        return str(Path(TASKS_DIR, *parts))

    def context(self, out: str) -> str:
        return f"зерно: {self.seed}\n{out}"

    def assert_no_passport_violation(self, out: str, rel_passport: str):
        offending = [line for line in out.splitlines()
                     if rel_passport in line and PASSPORT_SKIPPED not in line]
        self.assertEqual(offending, [], self.context(out))

    def test_ac1_all_accepts_passport_without_frontmatter(self):
        """Живая задача: корректный артефакт и паспорт без frontmatter.

        `guard --all` из корня дерева обязан завершиться кодом 0 и не
        назвать `PASSPORT.md` ни одной строкой нарушения; проверяется на
        нескольких случайных номерах задач и содержимом паспорта.
        Ловит мутацию: исключение паспорта добавили только в одиночный
        режим, а обход `--all` по-прежнему отдаёт `PASSPORT.md` в
        `check` — код 1 и строка «PASSPORT.md: нет frontmatter».
        """
        for _ in range(ROUNDS):
            task_id = random_task_id(self.rng)
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                task_dir = self.make_tree(root, task_id)
                (task_dir / "PASSPORT.md").write_text(
                    passport_text(self.rng), encoding="utf-8")
                rc, out = self.run_guard(root, "--all")
            self.assertEqual(rc, 0, self.context(out))
            self.assert_no_passport_violation(
                out, self.rel(task_id, "PASSPORT.md"))

    def test_ac2_passport_content_under_other_name_is_extraneous(self):
        """Содержимое паспорта под чужим именем `.md` первого уровня.

        Имя вне белого списка (`JOURNAL.md` и подобные) — посторонний
        файл: `guard --all` код 1 и строка «<путь>: посторонний файл в
        каталоге задачи» именно для этого файла.
        Ловит мутацию: признак паспорта сделан по содержимому (заголовок
        «# Паспорт живой задачи») либо пропуск распространён на любой
        `.md` первого уровня — `JOURNAL.md` проходит молча, код 0.
        """
        for name in ("JOURNAL.md", "PASSPORT_COPY.md",
                     f"NOTES_{self.rng.randint(1, 999)}.md"):
            task_id = random_task_id(self.rng)
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                task_dir = self.make_tree(root, task_id)
                (task_dir / name).write_text(passport_text(self.rng),
                                             encoding="utf-8")
                rc, out = self.run_guard(root, "--all")
            self.assertEqual(rc, 1, self.context(out))
            self.assertIn(f"{self.rel(task_id, name)}: {EXTRANEOUS_TASK_ROOT}",
                          out, self.context(out))

    def test_ac3_spec_without_frontmatter_beside_passport_still_refused(self):
        """`SPEC.md` без frontmatter рядом с паспортом.

        `guard --all` код 1, нарушение «нет frontmatter» названо для
        `SPEC.md`, а по `PASSPORT.md` нарушения нет.
        Ловит мутацию: каталог задачи с паспортом пропускается целиком
        (или пропуск по признаку «первый уровень» без проверки имени) —
        `SPEC.md` без frontmatter проходит, код 0.
        """
        for _ in range(ROUNDS):
            task_id = random_task_id(self.rng)
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                task_dir = self.make_tree(root, task_id)
                (task_dir / "PASSPORT.md").write_text(
                    passport_text(self.rng), encoding="utf-8")
                (task_dir / "SPEC.md").write_text(
                    "# SPEC: без заголовочного блока\n\n## Контекст\nтекст\n",
                    encoding="utf-8")
                rc, out = self.run_guard(root, "--all")
            self.assertEqual(rc, 1, self.context(out))
            spec_rel = self.rel(task_id, "SPEC.md")
            self.assertTrue(
                any(spec_rel in line and NO_FRONTMATTER in line
                    for line in out.splitlines()), self.context(out))
            self.assert_no_passport_violation(
                out, self.rel(task_id, "PASSPORT.md"))

    def test_ac4_passport_in_acceptance_tests_is_extraneous(self):
        """`PASSPORT.md` без frontmatter в `acceptance_tests/` живой задачи.

        `guard --all` код 1 и строка «<путь>: посторонний файл в каталоге
        планки» для этого файла.
        Ловит мутацию: `PASSPORT.md` в `acceptance_tests/` остаётся
        допустимым `.md` планки (правило посторонних его не называет) —
        вместо строки «посторонний файл в каталоге планки» выводится
        «нет frontmatter»; либо паспорт узнаётся по одному имени без
        проверки уровня — файл пропущен, код 0.
        """
        for _ in range(ROUNDS):
            task_id = random_task_id(self.rng)
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                task_dir = self.make_tree(root, task_id)
                (task_dir / "acceptance_tests").mkdir()
                (task_dir / "acceptance_tests" / "PASSPORT.md").write_text(
                    passport_text(self.rng), encoding="utf-8")
                rc, out = self.run_guard(root, "--all")
            self.assertEqual(rc, 1, self.context(out))
            rel = self.rel(task_id, "acceptance_tests", "PASSPORT.md")
            self.assertIn(f"{rel}: {EXTRANEOUS_PLANK}", out, self.context(out))

    def test_ac5_passport_in_nested_directory_is_extraneous(self):
        """`PASSPORT.md` без frontmatter во вложенном каталоге первого уровня.

        `<каталог задачи>/<каталог>/PASSPORT.md` — посторонний: `guard --all`
        код 1 и строка «<путь>: посторонний файл в каталоге задачи».
        Ловит мутацию: в белый список посторонних добавлено имя
        `PASSPORT.md` на любой глубине (или пропуск по имени в обходе) —
        `wip/PASSPORT.md` проходит молча, код 0.
        """
        for sub in ("wip", "tmp", f"draft{self.rng.randint(1, 99)}"):
            task_id = random_task_id(self.rng)
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                task_dir = self.make_tree(root, task_id)
                (task_dir / sub).mkdir()
                (task_dir / sub / "PASSPORT.md").write_text(
                    passport_text(self.rng), encoding="utf-8")
                rc, out = self.run_guard(root, "--all")
            self.assertEqual(rc, 1, self.context(out))
            rel = self.rel(task_id, sub, "PASSPORT.md")
            self.assertIn(f"{rel}: {EXTRANEOUS_TASK_ROOT}", out,
                          self.context(out))

    def test_ac6_single_file_passport_skipped_with_note(self):
        """Одиночный режим на паспорте первого уровня без frontmatter.

        guard с путём `<каталог задачи>/PASSPORT.md` из корня дерева: код 0, в выводе
        строка «<путь>: паспорт задачи, не артефакт роли — пропущен»,
        отказа «нет frontmatter» нет.
        Ловит мутацию: исключение паспорта сделано только в обходе
        `--all`, одиночный режим по-прежнему зовёт `check` — код 1 и
        «нет frontmatter»; либо пропуск молчаливый — строки пропуска нет.
        """
        for _ in range(ROUNDS):
            task_id = random_task_id(self.rng)
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                task_dir = self.make_tree(root, task_id)
                (task_dir / "PASSPORT.md").write_text(
                    passport_text(self.rng), encoding="utf-8")
                rel = self.rel(task_id, "PASSPORT.md")
                rc, out = self.run_guard(root, rel)
            self.assertEqual(rc, 0, self.context(out))
            self.assertIn(f"{rel}: {PASSPORT_SKIPPED}", out, self.context(out))
            self.assertNotIn(NO_FRONTMATTER, out, self.context(out))

    def test_ac7_single_file_passport_not_first_level_still_checked(self):
        """Одиночный режим на `acceptance_tests/PASSPORT.md` без frontmatter.

        Файл не первого уровня каталога задачи проверяется как артефакт:
        код 1 и нарушение «нет frontmatter», строки пропуска нет.
        Ловит мутацию: в одиночном режиме паспорт узнаётся по одному имени
        файла (`path.name == "PASSPORT.md"`) без проверки, что его каталог
        лежит прямо в каталоге задач — файл пропущен, код 0.
        """
        for _ in range(ROUNDS):
            task_id = random_task_id(self.rng)
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                task_dir = self.make_tree(root, task_id)
                (task_dir / "acceptance_tests").mkdir()
                (task_dir / "acceptance_tests" / "PASSPORT.md").write_text(
                    passport_text(self.rng), encoding="utf-8")
                rel = self.rel(task_id, "acceptance_tests", "PASSPORT.md")
                rc, out = self.run_guard(root, rel)
            self.assertEqual(rc, 1, self.context(out))
            self.assertTrue(
                any(rel in line and NO_FRONTMATTER in line
                    for line in out.splitlines()), self.context(out))
            self.assertNotIn(PASSPORT_SKIPPED, out, self.context(out))


if __name__ == "__main__":
    unittest.main()
