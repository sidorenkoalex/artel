"""Записка роли `NOTE-<роль>.md` в guard: перечень ролей записки, белый
список корня каталога задачи, освобождение записки от структурной проверки
в `guard --all` и в проверке одного файла.

Группа: долгоживущий

Красен до реализации: в `scripts/guard.py` нет ни кортежа `STEP_NOTE_ROLES`, ни функции `is_step_note`, белый список корня каталога задачи не знает имён `NOTE-<роль>.md` — `guard --all` называет записку посторонним файлом, а проверка одного файла требует у неё frontmatter.

Планка провалидирована временным стабом реализации (все методы зелёные, стаб удалён, не закоммичен).

Свойства чистых функций guard проверяются прямым вызовом; `guard --all` и
проверка одного файла — запуском `scripts/guard.py` этого дерева во
временном каталоге с деревом документов задачи (guard читает каталог задач
относительно рабочего каталога запуска). Номер задачи, текст записки и
выбор роли порождаются при каждом запуске от зерна; зерно печатается и
входит в текст провала.
"""
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from orchestrator import config, roles
from scripts import guard

REPO = Path(__file__).resolve().parent.parent
GUARD_SCRIPT = REPO / "scripts" / "guard.py"
TASKS = config.TASKS.name
EXPECTED_ROLES = ("analyst", "spec_auditor", "test_author", "developer",
                  "reviewer")
ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
STRAY_REASON = "посторонний файл в каталоге задачи"


def task_id(rng: random.Random) -> str:
    return "01T" + "".join(rng.choice(ULID_ALPHABET) for _ in range(23))


def free_text(rng: random.Random) -> str:
    """Свободный текст записки: без frontmatter, с разделами и мусором,
    который структурная проверка артефакта сочла бы нарушением."""
    token = rng.randrange(10 ** 9)
    return (f"# Записка {token}\n\nВыяснено: что-то {token}.\n"
            f"Не сработало: --- не frontmatter ---\n"
            f"Где остановился: шаг {rng.randrange(100)}.\n"
            f"Чего не хватило: правила {token}.\n")


def non_role_note_names(rng: random.Random) -> list:
    word = "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(7))
    return ["NOTE.md", "NOTE-operator.md", f"NOTE-{word}.md"]


BROKEN_PLAN = "план без заголовочного блока\n\n## Подход\n\nтекст\n"


class StepNoteRolesTest(unittest.TestCase):
    """AC-1: перечень ролей записки."""

    def test_ac1_step_note_roles_are_the_five_agent_roles(self):
        """Кортеж `guard.STEP_NOTE_ROLES` сверяется с пятью ролями критерия и
        с ролями `roles.yaml`, у которых `executor: agent`.

        Наблюдение: это кортеж, его набор ровно `analyst`, `spec_auditor`,
        `test_author`, `developer`, `reviewer` без повторов, и тот же набор
        дают агентские роли карты исполнителей.

        Ловит мутацию: в кортеж забыли `spec_auditor` (или вписали
        `operator`/`verifier`), либо в `roles.yaml` появилась агентская роль,
        которой записка не знает — наборы разойдутся.
        """
        got = guard.STEP_NOTE_ROLES
        self.assertIsInstance(got, tuple)
        self.assertEqual(len(got), len(set(got)), f"повторы в {got}")
        self.assertEqual(set(got), set(EXPECTED_ROLES))
        entries = roles.load()
        agents = {name for name, entry in entries.items()
                  if isinstance(entry, dict) and entry.get("executor") == "agent"}
        self.assertEqual(set(got), agents,
                         "STEP_NOTE_ROLES разошёлся с агентскими ролями roles.yaml")


class TaskRootWhitelistTest(unittest.TestCase):
    """AC-2: белый список корня каталога задачи."""

    def test_ac2_role_notes_are_not_extraneous_other_note_names_are(self):
        """Пять имён `NOTE-<роль>.md` первого уровня и посторонние имена
        записки (`NOTE.md`, `NOTE-operator.md`, `NOTE-<случайное слово>.md`).

        Наблюдение: `is_extraneous_task_root_file` для пяти имён ролей —
        `False`, для прочих — `True`.

        Ловит мутацию: белый список расширен маской `NOTE-.*\\.md` (или
        `NOTE.*`) вместо точных имён — `NOTE-operator.md` и `NOTE.md`
        перестают быть посторонними; либо одно из пяти имён забыто.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        for role in EXPECTED_ROLES:
            with self.subTest(роль=role, зерно=seed):
                self.assertFalse(guard.is_extraneous_task_root_file(f"NOTE-{role}.md"))
        for name in non_role_note_names(rng):
            with self.subTest(имя=name, зерно=seed):
                self.assertTrue(guard.is_extraneous_task_root_file(name),
                                f"зерно: {seed}; {name} стал допустимым")


class IsStepNoteTest(unittest.TestCase):
    """AC-3: `guard.is_step_note`."""

    def test_ac3_is_step_note_only_for_role_note_on_task_first_level(self):
        """Пути записки на первом уровне каталога задачи (относительные и
        абсолютные) и пути-обманки: та же записка в подкаталоге и в
        `acceptance_tests/`, `PLAN.md`, `PASSPORT.md`, `NOTE.md`,
        `NOTE-operator.md` первого уровня.

        Наблюдение: `True` — только у пяти имён ролей на первом уровне.

        Ловит мутацию: проверяется только имя файла без уровня (записка в
        `acceptance_tests/` или `wip/` освобождается), либо функция
        возвращает `True` для любого корневого `.md` белого списка.
        """
        seed = random.randrange(1 << 30)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        tid = task_id(rng)
        base = Path(TASKS) / tid
        abs_base = Path(tempfile.gettempdir()) / f"r{rng.randrange(10 ** 6)}" / TASKS / tid
        for role in EXPECTED_ROLES:
            name = f"NOTE-{role}.md"
            for root in (base, abs_base):
                with self.subTest(путь=str(root / name), зерно=seed):
                    self.assertTrue(guard.is_step_note(root / name))
            sub = rng.choice(("wip", "tmp", "chernovik"))
            for path in (base / sub / name, base / "acceptance_tests" / name,
                         abs_base / "acceptance_tests" / name):
                with self.subTest(путь=str(path), зерно=seed):
                    self.assertFalse(guard.is_step_note(path))
        for name in ["PLAN.md", "SPEC.md", "PASSPORT.md"] + non_role_note_names(rng):
            with self.subTest(путь=str(base / name), зерно=seed):
                self.assertFalse(guard.is_step_note(base / name))


class GuardRunsOnNotesTest(unittest.TestCase):
    """AC-4: `guard --all` и проверка одного файла на дереве с запиской."""

    def setUp(self):
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.tid = task_id(self.rng)
        self.task_dir = self.root / TASKS / self.tid
        self.task_dir.mkdir(parents=True)

    def put(self, rel: str, text: str) -> str:
        path = self.task_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return f"{TASKS}/{self.tid}/{rel}"

    def guard(self, *args: str) -> tuple:
        res = subprocess.run([sys.executable, str(GUARD_SCRIPT), *args],
                             cwd=self.root, capture_output=True, text=True,
                             timeout=120)
        return res.returncode, res.stdout + res.stderr

    def violations(self, out: str) -> list:
        return [ln.strip()[2:] for ln in out.splitlines()
                if ln.strip().startswith("- ")]

    def msg(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def test_ac4_guard_all_passes_first_level_notes_with_free_text(self):
        """Каталог задачи несёт пять записок первого уровня со свободным
        текстом без frontmatter (и одну случайную из них отдельно).

        Наблюдение: `guard --all` завершается кодом 0 без нарушений.

        Ловит мутацию: имена записок добавлены в белый список корня, но
        `guard --all` по-прежнему гонит их через структурную проверку
        артефакта — «нет frontmatter» по каждой записке.
        """
        for role in EXPECTED_ROLES:
            self.put(f"NOTE-{role}.md", free_text(self.rng))
        rc, out = self.guard("--all")
        self.assertEqual(rc, 0, self.msg(out))
        self.assertEqual(self.violations(out), [], self.msg(out))

    def test_ac4_guard_all_still_refuses_broken_plan_beside_notes(self):
        """Рядом с записками первого уровня лежит `PLAN.md` без
        заголовочного блока.

        Наблюдение: `guard --all` отказывает (код не 0), нарушение называет
        `PLAN.md`, ни одно нарушение не называет записку.

        Ловит мутацию: освобождение записки сделано через пропуск всех `.md`
        первого уровня (или всех имён белого списка) — битый `PLAN.md`
        проходит.
        """
        role = self.rng.choice(EXPECTED_ROLES)
        self.put(f"NOTE-{role}.md", free_text(self.rng))
        self.put("PLAN.md", BROKEN_PLAN)
        rc, out = self.guard("--all")
        self.assertNotEqual(rc, 0, self.msg(out))
        found = self.violations(out)
        self.assertTrue([v for v in found if "PLAN.md" in v], self.msg(out))
        self.assertEqual([v for v in found if f"NOTE-{role}.md" in v], [],
                         self.msg(out))

    def test_ac4_guard_all_checks_note_in_plank_and_subdir_as_before(self):
        """Записка со свободным текстом лежит не на первом уровне: в
        `acceptance_tests/` и в подкаталоге каталога задачи.

        Наблюдение: `guard --all` отказывает, и нарушение называет каждую
        из этих записок — так же, как он называет файл `zametki.md` со
        свободным текстом на тех же местах.

        Ловит мутацию: освобождение дано по имени файла без проверки уровня
        — записка в `acceptance_tests/` или в `wip/` проходит без нарушения.
        """
        role = self.rng.choice(EXPECTED_ROLES)
        sub = self.rng.choice(("wip", "tmp", "chernovik"))
        for place in ("acceptance_tests", sub):
            with self.subTest(место=place, зерно=self.seed):
                for name in (f"NOTE-{role}.md", "zametki.md"):
                    for path in self.task_dir.rglob("*"):
                        if path.is_file():
                            path.unlink()
                    rel = self.put(f"{place}/{name}", free_text(self.rng))
                    rc, out = self.guard("--all")
                    self.assertNotEqual(rc, 0, self.msg(f"{rel}: {out}"))
                    self.assertTrue([v for v in self.violations(out) if rel in v],
                                    self.msg(f"нарушение не называет {rel}: {out}"))

    def test_ac4_single_file_check_skips_note_but_not_broken_plan(self):
        """Проверка одного файла (`guard.py <путь>`, без `--all`): записка
        первого уровня каждой из пяти ролей и битый `PLAN.md` того же
        каталога.

        Наблюдение: на записке — код 0 и ни одного нарушения; на `PLAN.md`
        — код не 0 с нарушением, называющим `PLAN.md`.

        Ловит мутацию: освобождение записки добавлено только в обход
        `--all`, а в ветке одного файла записку по-прежнему проверяет
        `check` — «нет frontmatter» и код 1.
        """
        for role in EXPECTED_ROLES:
            rel = self.put(f"NOTE-{role}.md", free_text(self.rng))
            with self.subTest(записка=rel, зерно=self.seed):
                rc, out = self.guard(rel)
                self.assertEqual(rc, 0, self.msg(out))
                self.assertEqual(self.violations(out), [], self.msg(out))
        plan = self.put("PLAN.md", BROKEN_PLAN)
        rc, out = self.guard(plan)
        self.assertNotEqual(rc, 0, self.msg(out))
        self.assertTrue([v for v in self.violations(out) if "PLAN.md" in v],
                        self.msg(out))


if __name__ == "__main__":
    unittest.main()
