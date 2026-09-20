"""Юнит-тесты приложений PLAN к защищённым путям (SPEC
01M2YSHDKWFJN3XSJ618Z74FNF): разбор `scripts/guard.py::plan_appendices`,
гейт применимости `orchestrator/advance_gates/plan_appendix.py`,
классификация путей полного прогона и строка RETRO.

Углы, которые приёмочная планка задачи намеренно не бьёт: там git всегда
настоящий и всегда отвечает, а PLAN.md фикстур написан по форме — здесь
проверяются перекошенные разделы, сбой git и опт-ин соседних узлов
(внешний target, PLAN без приложений).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, fsm_postmerge, gitcmd, store  # noqa: E402
from orchestrator.advance_gates import plan_appendix  # noqa: E402
from scripts import guard  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

# Защищённый путь-файл и защищённый каталог — от `config.PROTECTED_PATHS`,
# не литералом: список меняет Оператор, и тест обязан пережить его
# крутилку.
PROTECTED_FILE = next(p for p in config.PROTECTED_PATHS if not p.endswith("/"))
# Каталог ВНЕ `tests/`/`.github/`: правка под ним не требует полного
# прогона (требование 5) — на нём же проверяется префиксная формула
# защищённости.
PROTECTED_DIR = next(p for p in config.PROTECTED_PATHS
                     if p.endswith("/") and not p.startswith("tests")
                     and not p.startswith(".github"))


def diff_block(path: str, body: str | None = None) -> str:
    """Блок ```diff одного приложения — минимальный, но с настоящим
    заголовком `diff --git`."""
    inner = body if body is not None else f"diff --git a/{path} b/{path}"
    return f"```diff\n{inner}\n--- a/{path}\n+++ b/{path}\n```\n"


class PlanAppendicesParsingTest(unittest.TestCase):

    def test_section_prefix_matches_a_heading_with_a_tail(self):
        """Заголовок раздела узнаётся по префиксу «## Приложение», а не по
        точному имени: практика пишет его с хвостом.

        Ловит мутацию: разбор зовёт `guard.section_body(text,
        "Приложение")` (сверка имени раздела ЦЕЛИКОМ) — раздел «##
        Приложение: правка skills/x.md» не нашёлся бы вовсе, и все восемь
        сегодняшних разделов `tasks/` остались бы невидимыми."""
        text = (f"# PLAN\n\n## Приложение: правка {PROTECTED_FILE}\n\n"
                f"{diff_block(PROTECTED_FILE)}")

        appendices, errors = guard.plan_appendices(text)

        self.assertEqual([a.path for a in appendices], [PROTECTED_FILE])
        self.assertEqual(errors, [])

    def test_diff_block_outside_an_appendix_section_is_ignored(self):
        """Блок ```diff в обычном разделе PLAN (например в «## Подход»)
        приложением не является.

        Ловит мутацию: блоки ищутся по ВСЕМУ тексту PLAN, а не в телах
        разделов приложений — любой дифф, приведённый разработчиком для
        иллюстрации, пульт применил бы коммитом в main."""
        text = (f"# PLAN\n\n## Подход\n\nВот как выглядит дифф:\n\n"
                f"{diff_block(PROTECTED_FILE)}\n## Шаги\n\n1. Шаг.\n")

        self.assertEqual(guard.plan_appendices(text), ([], []))

    def test_appendix_section_ends_at_the_next_heading(self):
        """Тело раздела приложения кончается на следующем `## ` заголовке:
        блок соседнего раздела в приложение не затягивается.

        Ловит мутацию: тело раздела берётся до конца файла — дифф из
        любого последующего раздела PLAN уехал бы в main как приложение."""
        text = (f"# PLAN\n\n## Приложение\n\n{diff_block(PROTECTED_FILE)}\n"
                f"## Риски\n\n{diff_block(PROTECTED_DIR + 'x.md')}")

        appendices, errors = guard.plan_appendices(text)

        self.assertEqual([a.path for a in appendices], [PROTECTED_FILE])
        self.assertEqual(errors, [])

    def test_appendix_section_without_diff_blocks_gives_nothing(self):
        """Раздел «## Приложение» с одним обоснованием и без блоков
        ```diff — ни приложений, ни ошибок.

        Ловит мутацию: пустой раздел трактуется как ошибка «нет заголовка
        diff --git» — PLAN, где Оператор сам вырезал приложение, но
        оставил заголовок раздела, застрял бы на гейте `in_dev`
        навсегда."""
        text = "# PLAN\n\n## Приложение\n\nПравка отложена до следующей задачи.\n"

        self.assertEqual(guard.plan_appendices(text), ([], []))

    def test_file_under_a_protected_directory_is_accepted(self):
        """Путь под защищённым КАТАЛОГОМ списка — защищённый (та же
        формула префикса, что у гейта зон и гейта мержа).

        Ловит мутацию: защищённость сверяется точным равенством пути с
        элементом `config.PROTECTED_PATHS` — приложение к `skills/<файл>`
        (ровно тот случай, из-за которого задача и заведена) объявлялось
        бы «не защищённым»."""
        path = PROTECTED_DIR + "some-file.md"

        appendices, errors = guard.plan_appendices(
            f"## Приложение\n\n{diff_block(path)}")

        self.assertEqual([a.path for a in appendices], [path])
        self.assertEqual(errors, [])

    def test_rename_header_with_two_different_paths_is_refused(self):
        """`diff --git a/<старый> b/<новый>` (переименование) корректным
        заголовком не считается.

        Ловит мутацию: путь берётся только из группы `a/` без сверки со
        второй — приложение-переименование прошло бы проверку
        защищённости по СТАРОМУ пути и создало бы файл по НОВОМУ,
        сколь угодно постороннему."""
        block = diff_block(
            PROTECTED_FILE,
            body=f"diff --git a/{PROTECTED_FILE} b/docs/somewhere-else.md")

        appendices, errors = guard.plan_appendices(f"## Приложение\n\n{block}")

        self.assertEqual(appendices, [])
        self.assertEqual(errors, [guard.APPENDIX_NO_HEADER_ERROR])

    def test_appendix_carries_the_whole_diff_text(self):
        """Текст приложения — всё содержимое блока без строк-оград: его
        отдают `git apply`, и потеря хоть одной строки делает патч
        неприменимым.

        Ловит мутацию: в `diff` кладётся только строка заголовка `diff
        --git` (или блок сохраняется ВМЕСТЕ с оградой ```diff) — `git
        apply` отказал бы на каждом приложении, и механика не работала бы
        ни разу."""
        text = f"## Приложение\n\n{diff_block(PROTECTED_FILE)}"

        appendices, _errors = guard.plan_appendices(text)

        diff = appendices[0].diff
        self.assertNotIn("```", diff)
        self.assertIn(f"diff --git a/{PROTECTED_FILE} b/{PROTECTED_FILE}", diff)
        self.assertIn(f"--- a/{PROTECTED_FILE}", diff)
        self.assertIn(f"+++ b/{PROTECTED_FILE}", diff)


class PlanAppendixGateTest(TmpRootTest):
    """Углы гейта применимости, которых нет в приёмочной планке: PLAN без
    приложений (ни одного вызова git), ошибки разбора, сбой git и внешний
    target."""

    TASK = "T001"
    BRANCH = "task/t001-x"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK, "Тест приложений", "in_dev",
                          self.BRANCH, config.DEFAULT_TARGET, 10.0)
        self.t = {"branch": self.BRANCH}

    def details(self) -> list[str]:
        return [r["detail"] for r in self.conn.execute(
            "SELECT detail FROM steps WHERE task_id=?", (self.TASK,))]

    def actions(self) -> list[str]:
        return [r["action"] for r in self.conn.execute(
            "SELECT action FROM steps WHERE task_id=?", (self.TASK,))]

    def test_plan_without_appendices_touches_no_git(self):
        """PLAN без разделов «## Приложение» проходит гейт, не спросив git
        ни о чём.

        Ловит мутацию: база сравнения (`diff_base`) или worktree базы
        заводятся ДО проверки «приложения вообще есть» — каждая задача
        артели платила бы вычекиванием целого дерева за механику, которой
        не пользуется, а песочница без настоящего git ложно отказывала бы
        переходу."""
        def boom(*args, **kwargs):
            raise AssertionError("гейт приложений не обязан звать git для "
                                 "PLAN без приложений")

        with mock.patch.object(gitcmd, "diff_base", boom):
            refuses = plan_appendix._plan_appendix_gate_refuses(
                self.conn, self.TASK, self.t, "# PLAN\n\n## Подход\n\nтекст\n")

        self.assertFalse(refuses)
        self.assertEqual(self.actions(), [])

    def test_parse_errors_refuse_the_transition(self):
        """Блок ```diff с путём вне `config.PROTECTED_PATHS` отказывает
        переходу тем же именованным действием, что и неприменимое
        приложение.

        Ловит мутацию: ошибки разбора (требование 1) гейт игнорирует и
        смотрит только на `git apply --check` — блок с посторонним путём
        (или без заголовка `diff --git`) молча выпал бы из списка, и
        Оператор узнал бы о потерянной правке только когда её не оказалось
        бы в main."""
        text = f"## Приложение\n\n{diff_block('docs/not-protected.md')}"

        refuses = plan_appendix._plan_appendix_gate_refuses(
            self.conn, self.TASK, self.t, text)

        self.assertTrue(refuses)
        self.assertIn(plan_appendix.PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION,
                      self.actions())
        self.assertTrue(any("docs/not-protected.md" in d
                            for d in self.details()))

    def test_git_not_answering_the_diff_base_refuses(self):
        """`diff_base`, не ответивший базой сравнения, — отказ
        (fail-closed, ADR-0002), не молчаливый пропуск.

        Ловит мутацию: ветка `base is None` заменена на `return None`
        («git молчит — считаем применимым») — приложение уехало бы в main
        ни разу не проверенным, ровно как до этой задачи."""
        text = f"## Приложение\n\n{diff_block(PROTECTED_FILE)}"

        with mock.patch.object(gitcmd, "diff_base", return_value=None):
            refuses = plan_appendix._plan_appendix_gate_refuses(
                self.conn, self.TASK, self.t, text)

        self.assertTrue(refuses)
        self.assertIn(plan_appendix.PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION,
                      self.actions())

    def test_external_target_skips_the_gate(self):
        """Внешний (не self) target — гейт не проверяется: защищённые пути
        списка это файлы ПУЛЬТА, а git здесь ходит в `config.ROOT`.

        Ловит мутацию: проверка target'а убрана — задача внешнего проекта
        отказывала бы на приложении к своему `tests/…`, сверяя его с
        деревом пульта, где такого файла нет вовсе."""
        store.update_task(self.conn, self.TASK, target="other")
        text = f"## Приложение\n\n{diff_block(PROTECTED_FILE)}"

        def boom(*args, **kwargs):
            raise AssertionError("гейт приложений не обязан звать git для "
                                 "внешнего target")

        with mock.patch.object(gitcmd, "diff_base", boom):
            refuses = plan_appendix._plan_appendix_gate_refuses(
                self.conn, self.TASK, self.t, text)

        self.assertFalse(refuses)

    def test_refusal_action_reaches_the_refusal_history(self):
        """Действие отказа начинается с `store.REFUSAL_ACTION_PREFIX` —
        только по этому признаку отказ доезжает до истории отказов брифа
        роли.

        Ловит мутацию: действие переименовано во что-то без префикса
        «переход отклонён» — отказ остался бы в журнале, но роль
        запускалась бы вслепую, не узнав, какое приложение неприменимо."""
        self.assertTrue(
            plan_appendix.PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION.startswith(
                store.REFUSAL_ACTION_PREFIX))


class FullSuiteScopeTest(unittest.TestCase):

    def test_tests_and_github_paths_need_the_full_suite(self):
        """Приложение к `tests/…` или `.github/…` требует полного прогона.

        Ловит мутацию: условие сведено к одному из двух префиксов —
        правка правил CI (или самого набора тестов) уехала бы в main без
        единой проверки, потому что проверять её было бы уже нечем."""
        from orchestrator import fsm_merge_gate

        self.assertTrue(fsm_merge_gate._appendix_needs_full_suite(
            ["tests/test_invariants.py"]))
        self.assertTrue(fsm_merge_gate._appendix_needs_full_suite(
            [".github/workflows/ci.yml"]))

    def test_other_protected_paths_do_not_need_the_full_suite(self):
        """Приложение к `skills/`/`templates/`/`docs/` полного прогона не
        требует — его проверит CI main.

        Ловит мутацию: прогон запускается для ЛЮБОГО приложения — каждый
        мерж с правкой скила платил бы полным набором под удерживаемым
        мьютексом merge-окна."""
        from orchestrator import fsm_merge_gate

        self.assertFalse(fsm_merge_gate._appendix_needs_full_suite(
            [PROTECTED_DIR + "x.md", "docs/invariants.md"]))
        self.assertFalse(fsm_merge_gate._appendix_needs_full_suite([]))


class RetroAppendicesLineTest(unittest.TestCase):

    def test_no_appendices_leaves_the_text_byte_identical(self):
        """RETRO задачи без приложений не отличается от сегодняшнего ни
        одним символом.

        Ловит мутацию: строка дописывается безусловно (пустой перечень
        даёт хвост «Приложения Оператора применены: ») — RETRO КАЖДОЙ
        задачи артели понесло бы пустую строку о механике, которой она не
        пользовалась."""
        text = "# RETRO: T001\n\nИтог: done\n"

        self.assertEqual(fsm_postmerge._with_appendices_line(text, None), text)
        self.assertEqual(fsm_postmerge._with_appendices_line(text, []), text)

    def test_applied_paths_are_listed_in_a_single_line(self):
        """Перечень применённых путей ложится в RETRO одной строкой.

        Ловит мутацию: в строку кладётся не перечень путей, а их число
        (или сам объект списка) — RETRO перестало бы отвечать на вопрос
        «что именно этот мерж поменял в защищённых путях», ради которого
        строка и заведена."""
        out = fsm_postmerge._with_appendices_line(
            "# RETRO\n", ["gates.yaml", "skills/x.md"])

        line = [ln for ln in out.splitlines()
                if ln.startswith(fsm_postmerge.APPENDICES_RETRO_PREFIX)]
        self.assertEqual(len(line), 1)
        self.assertIn("gates.yaml", line[0])
        self.assertIn("skills/x.md", line[0])


if __name__ == "__main__":
    unittest.main()
