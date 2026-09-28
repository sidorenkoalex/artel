"""Источник байтов ретроспективы — АРТЕФАКТНАЯ ветка задачи, читаемая
через git (SPEC 01M3KE80RNBCY9G48E75Z14TA7, требования 5-7; AC-5, AC-6,
AC-7, AC-10, AC-11).

Настоящий git, а не заглушка (`sandbox.RealGitSandbox`): предмет проверки
— именно то, что `orchestrator/retro.py` читает `tasks/<id>/` ИЗ ВЕТКИ, а
не с диска главной копии, и подменённый `read_tree` этого показать не
может. Каталог задачи в главной копии в этих тестах либо отсутствует
вовсе (обычное состояние на момент записи ретроспективы закрытия), либо
несёт ДРУГОЕ содержимое — приманку, по которой видно, какой из двух
источников победил.

Строка «Адрес артефактов» ретроспективы снимка (требование 3) проверяется
здесь же на уровне вёрстки: имя ссылки передаёт `orchestrator/snapshot.py`
параметром `address`, сквозной путь публикации — в
`tests/test_snapshot_closing_outcome.py`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artifact_branch, config, retro, store  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

TASK = "01M3RETROBRANCHREADS01"

BRANCH_SPEC = """---
task: 01M3RETROBRANCHREADS01
type: spec
author_role: analyst
status: ready
schema_version: 5
---

# SPEC: задача из артефактной ветки

## Контекст

Ретроспектива читает SPEC из артефактной ветки задачи. Второе предложение
в «Суть» попасть не должно.

## Требования

1. Требование.

## Критерии приёмки

AC-1. Критерий.

## Не входит

- Ничего.
"""

DISK_DECOY_SPEC = """---
task: 01M3RETROBRANCHREADS01
type: spec
author_role: analyst
status: ready
schema_version: 5
---

# SPEC: приманка главной копии

## Контекст

Приманка с диска главной копии.

## Требования

1. Требование.

## Критерии приёмки

AC-1. Критерий.

## Не входит

- Ничего.
"""

#: Планка ветки: два тестовых метода, один критерий помечен `manual`,
#: другой — `skip`. Числа попарно различны (2/1/1 против 0/0/0 деградации
#: и против любого «посчитали не то»), `@ac` склеивается в `ac` при сборке
#: строки — иначе литерал читался бы сканерами самого пульта как настоящий
#: тестовый метод ЭТОГО файла (тот же приём, что в `tests/test_retro.py`).
BRANCH_ACCEPTANCE = ('''"""Планка приёмки из артефактной ветки."""
# @AC-3: manual — проверяется руками.
# @AC-4: skip — не проверяется.
import unittest


class T(unittest.TestCase):
    def test_@ac1_one(self):
        pass

    def test_@ac2_two(self):
        pass
''').replace("@ac", "ac").replace("@AC", "AC")

#: Приманка на диске главной копии — ПЯТЬ методов и ни одной пометки:
#: любое число из неё отличимо от числа ветки.
DISK_DECOY_ACCEPTANCE = ('''"""Приманка главной копии."""
import unittest


class T(unittest.TestCase):
    def test_@ac1_a(self):
        pass

    def test_@ac1_b(self):
        pass

    def test_@ac1_c(self):
        pass

    def test_@ac1_d(self):
        pass

    def test_@ac1_e(self):
        pass
''').replace("@ac", "ac").replace("@AC", "AC")

BRANCH_COUNTS_LINE = "Приёмочные тесты: 2 тест(ов), 1 manual, 1 skip"
EMPTY_COUNTS_LINE = "Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip"
BRANCH_GIST_SENTENCE = ("Ретроспектива читает SPEC из артефактной ветки "
                        "задачи.")


class RetroBranchReadTest(RealGitSandbox):
    """Задача с живой артефактной веткой и без каталога в главной копии —
    ровно то состояние, в котором пульт пишет ретроспективу закрытия."""

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        store.insert_task(self.conn, TASK, "Задача с веткой", "merge_gate",
                          f"task/{TASK.lower()}-x", config.DEFAULT_TARGET,
                          50.0)

    def commit_branch_artifacts(self) -> None:
        artifact_branch.commit_files(
            TASK,
            {f"tasks/{TASK}/SPEC.md": BRANCH_SPEC,
             f"tasks/{TASK}/acceptance_tests/test_branch.py": BRANCH_ACCEPTANCE},
            f"{TASK}: SPEC и планка приёмки")

    def write_disk_decoy(self) -> None:
        adir = config.TASKS / TASK / "acceptance_tests"
        adir.mkdir(parents=True, exist_ok=True)
        (config.TASKS / TASK / "SPEC.md").write_text(DISK_DECOY_SPEC,
                                                     encoding="utf-8")
        (adir / "test_decoy.py").write_text(DISK_DECOY_ACCEPTANCE,
                                            encoding="utf-8")

    def test_done_counts_come_from_the_branch_without_a_task_dir(self):
        """AC-5/AC-6: каталога задачи в главной копии нет, ветка несёт
        планку из двух тестов с пометками manual/skip — ретроспектива
        несёт эти же числа, а не нули.

        Ловит мутацию: счётчики снова считаются по `config.TASKS/<id>`
        (каталога нет — `guard` вернёт нули) или чтение ветки потеряно —
        в тексте окажется «0 тест(ов), 0 manual, 0 skip», и `assertIn`
        ниже покраснеет.
        """
        self.commit_branch_artifacts()
        self.assertFalse((config.TASKS / TASK).exists())

        text = retro.build_done(self.conn, TASK, "abcd" * 10)

        self.assertIn(BRANCH_COUNTS_LINE, text)
        self.assertNotIn(EMPTY_COUNTS_LINE, text)

    def test_done_gist_takes_the_first_context_sentence_of_the_branch_spec(self):
        """AC-10/AC-11: «Суть» — название задачи плюс первое предложение
        «Контекста» SPEC.md ВЕТКИ, а не одно название.

        Ловит мутацию: `SPEC.md` снова читается с диска главной копии
        (файла нет — «Суть» вырождается в одно название задачи) — строка
        «Суть: Задача с веткой — Ретроспектива читает SPEC…» не соберётся,
        и `assertIn` ниже покраснеет.
        """
        self.commit_branch_artifacts()
        self.assertFalse((config.TASKS / TASK).exists())

        text = retro.build_done(self.conn, TASK, "abcd" * 10)

        self.assertIn(f"Суть: Задача с веткой — {BRANCH_GIST_SENTENCE}", text)
        self.assertNotIn("Второе предложение", text)

    def test_branch_wins_over_the_main_copy_task_dir(self):
        """Требования 5-6: источник — ветка, даже когда каталог задачи в
        главной копии существует и несёт ДРУГОЕ содержимое.

        Ловит мутацию: чтение вернулось к `config.TASKS/<id>` — в тексте
        появятся числа приманки («5 тест(ов), 0 manual, 0 skip») и её
        первое предложение, и `assertNotIn` ниже покраснеет.
        """
        self.commit_branch_artifacts()
        self.write_disk_decoy()

        text = retro.build_done(self.conn, TASK, "abcd" * 10)

        self.assertIn(BRANCH_COUNTS_LINE, text)
        self.assertIn(BRANCH_GIST_SENTENCE, text)
        self.assertNotIn("5 тест(ов)", text)
        self.assertNotIn("Приманка с диска", text)

    def test_killed_counts_come_from_the_branch_too(self):
        """Требование 5 — ОБЕ ретроспективы: killed-ретроспектива снимка
        (ветка ещё жива, публикация идёт до её удаления) несёт те же числа
        ветки.

        Ловит мутацию: `build_killed` оставлен на чтении главной копии,
        пока переведён только `build_done` — в тексте окажется «0
        тест(ов), 0 manual, 0 skip», и `assertIn` ниже покраснеет.
        """
        self.commit_branch_artifacts()
        store.journal(self.conn, TASK, "operator", "state -> killed",
                      "kill switch")

        text = retro.build_killed(self.conn, TASK)

        self.assertIn(BRANCH_COUNTS_LINE, text)
        self.assertIn("Итог: killed — причина: kill switch", text)

    def test_done_address_names_the_snapshot_ref_when_asked(self):
        """Требование 3/AC-2: вызыватель (ретроспектива снимка) вправе
        назвать вечный адрес `refs/artifacts/<id>`; по умолчанию строка
        остаётся контент-адресной (`docs/retro/<id>.md`, SPEC «Не входит»).

        Ловит мутацию: параметр `address` игнорируется (адрес всегда
        собирается из sha мержа) — «Адрес артефактов: refs/artifacts/<id>»
        в тексте не появится; обратная мутация (`address` подставляется
        всегда) уронит второй `assertIn`.
        """
        self.commit_branch_artifacts()

        by_ref = retro.build_done(self.conn, TASK, "abcd" * 10,
                                  address=f"refs/artifacts/{TASK}")
        default = retro.build_done(self.conn, TASK, "abcd" * 10)

        self.assertIn(f"Адрес артефактов: refs/artifacts/{TASK}", by_ref)
        self.assertNotIn("артефакты не сохранены", by_ref)
        self.assertIn(f"Адрес артефактов: {'abcd' * 10}:tasks/{TASK}/",
                      default)


class RetroWithoutBranchTest(RealGitSandbox):
    """Артефактной ветки нет вовсе — долговая генерация killed-ретроспективы
    на следующем мерже (`orchestrator/fsm_postmerge.py`), AC-7."""

    def setUp(self):
        super().setUp()
        self.conn = store.db()
        store.insert_task(self.conn, TASK, "Задача без ветки", "merge_gate",
                          f"task/{TASK.lower()}-x", config.DEFAULT_TARGET,
                          50.0)

    def test_generation_degrades_to_zeros_and_bare_title(self):
        """AC-7: генерация проходит без исключения, счётчики нули, «Суть» —
        одно название задачи без второй части.

        Ловит мутацию: чтение ветки перестало деградировать (исключение на
        отсутствующей ветке, обращение к `None`) — тест упадёт на самом
        вызове `build_done`; мутация «нули подменены чем-то ещё» уронит
        `assertIn` строки счётчиков.
        """
        self.assertFalse(
            artifact_branch.snapshot_pending(TASK),
            "предпосылка теста: артефактной ветки задачи нет")

        text = retro.build_done(self.conn, TASK, "abcd" * 10)

        self.assertIn(EMPTY_COUNTS_LINE, text)
        self.assertIn("Суть: Задача без ветки\n", text)

    def test_killed_generation_degrades_the_same_way(self):
        """AC-7 на второй ретроспективе: `build_killed` без ветки тоже
        проходит и даёт нули.

        Ловит мутацию: деградация чтения ветки закрыта только в
        `build_done` — `build_killed` упадёт исключением либо потеряет
        строку счётчиков.
        """
        text = retro.build_killed(self.conn, TASK)

        self.assertIn(EMPTY_COUNTS_LINE, text)
        self.assertIn("Суть: Задача без ветки\n", text)


if __name__ == "__main__":
    unittest.main()
