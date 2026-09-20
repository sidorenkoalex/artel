"""Юнит-тесты приложений PLAN к защищённым путям (SPEC
01M2YSHDKWFJN3XSJ618Z74FNF): разбор `scripts/guard.py::plan_appendices`,
гейт применимости `orchestrator/advance_gates/plan_appendix.py`,
применение приложений на мерже, классификация путей полного прогона,
класс отказа в `orchestrator/auto.py` и строка RETRO.

Углы, которые приёмочная планка задачи намеренно не бьёт: там git всегда
настоящий и всегда отвечает, а PLAN.md фикстур написан по форме — здесь
проверяются перекошенные разделы, сбой git и опт-ин соседних узлов
(внешний target, PLAN без приложений).

Узел применения на мерже живёт и здесь, в `tests/` (REVIEW итерация 1,
R1-F3): планку задачи CI не гоняет (`.github/workflows/ci.yml` запускает
`tests/`), и снятая будущей задачей строка вызова `_apply_plan_appendices`
иначе не покраснила бы ни один тест — механика умерла бы молча.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (acceptance, artifact_branch, auto,  # noqa: E402
                          catalog, ci, config, fsm_merge_gate, fsm_postmerge,
                          gitcmd, store)
from orchestrator.advance_gates import plan_appendix  # noqa: E402
from scripts import guard  # noqa: E402
from tests.sandbox import RealGitSandbox, TmpRootTest, capture  # noqa: E402

# Защищённый путь-файл и защищённый каталог — от `config.PROTECTED_PATHS`,
# не литералом: список меняет Оператор, и тест обязан пережить его
# крутилку.
PROTECTED_FILE = next(p for p in config.PROTECTED_PATHS if not p.endswith("/"))
# Второй защищённый файл — для многофайлового блока ```diff.
PROTECTED_FILE_2 = next(p for p in config.PROTECTED_PATHS
                        if not p.endswith("/") and p != PROTECTED_FILE
                        and not p.startswith("tests/")
                        and not p.startswith(".github"))
# Защищённый файл под `tests/` — триггер полного прогона (требование 5).
PROTECTED_TESTS_FILE = next(p for p in config.PROTECTED_PATHS
                            if p.startswith("tests/"))
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

        self.assertEqual([a.paths for a in appendices], [(PROTECTED_FILE,)])
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

        self.assertEqual([a.paths for a in appendices], [(PROTECTED_FILE,)])
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

        self.assertEqual([a.paths for a in appendices], [(path,)])
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
        self.assertEqual(errors, [guard.appendix_rename_header_error(
            PROTECTED_FILE, "docs/somewhere-else.md")])

    def test_rename_header_error_names_the_rename_not_a_missing_header(self):
        """Ошибка переименования — СВОЯ, и она называет оба пути (R2-F2,
        REVIEW итерация 2).

        Ловит мутацию: заголовок-переименование отвергается общей ошибкой
        `APPENDIX_NO_HEADER_ERROR` — роль читает в брифе «нет заголовка
        diff --git», видит заголовок на месте, чинит наугад, и каждая
        попытка стоит гарантированного шага developer (класс AC-6)."""
        block = diff_block(
            PROTECTED_FILE,
            body=f"diff --git a/{PROTECTED_FILE} b/docs/somewhere-else.md")

        _appendices, errors = guard.plan_appendices(
            f"## Приложение\n\n{block}")

        self.assertNotIn(guard.APPENDIX_NO_HEADER_ERROR, errors)
        self.assertIn(PROTECTED_FILE, errors[0])
        self.assertIn("docs/somewhere-else.md", errors[0])
        # Ошибка «нет заголовка» осталась за своим — настоящим —
        # сценарием AC-2, а не разошлась на два повода.
        headerless = "```diff\n--- a/x\n+++ b/x\n```\n"
        self.assertEqual(
            guard.plan_appendices(f"## Приложение\n\n{headerless}")[1],
            [guard.APPENDIX_NO_HEADER_ERROR])

    def test_context_line_with_a_code_fence_does_not_close_the_block(self):
        """Контекстная строка диффа ` ``` ` (пробел + ограда — так
        выглядит неизменённая строка markdown-файла) блок ```diff НЕ
        закрывает: приложение к защищённому md-файлу с примером кода
        обязано доехать до `git apply` целиком (R2-F1, REVIEW итерация 2).

        Ловит мутацию: ограда распознаётся с допуском ведущих пробелов
        (`^\\s*```\\s*$`) — дифф режется на первой же контекстной ограде,
        `git apply` отвечает «corrupt patch», и гейт `in_dev` отказывает
        переходу действием «приложение PLAN неприменимо»: роль жжёт шаг
        на дифф, в котором нечего чинить, а задача встаёт `Stop`'ом."""
        path = PROTECTED_DIR + "adr-like.md"
        block = ("```diff\n"
                 f"diff --git a/{path} b/{path}\n"
                 f"--- a/{path}\n+++ b/{path}\n"
                 "@@ -1,5 +1,5 @@\n"
                 "-старый абзац\n"
                 "+новый абзац\n"
                 " ```\n"
                 " artel.py status\n"
                 " ```\n"
                 "```\n")

        appendices, errors = guard.plan_appendices(f"## Приложение\n\n{block}")

        self.assertEqual(errors, [])
        self.assertEqual([a.paths for a in appendices], [(path,)])
        self.assertIn(" artel.py status", appendices[0].diff)
        self.assertEqual(appendices[0].diff.count("\n"), 9)

    def test_indented_fence_does_not_open_a_block(self):
        """Ограда, сдвинутая от колонки 0, блоком ```diff не считается —
        парная половина R2-F1.

        Ловит мутацию: открывающая ограда снова допускает ведущие
        пробелы — контекстная строка ` ```diff ` внутри приложения к
        md-файлу открыла бы ВТОРОЙ блок посреди первого, и разбор
        разъехался бы с тем, что видит `git apply`."""
        text = ("## Приложение\n\n  ```diff\n"
                f"diff --git a/{PROTECTED_FILE} b/{PROTECTED_FILE}\n"
                "  ```\n")

        appendices, errors = guard.plan_appendices(text)

        self.assertEqual(appendices, [])
        # Дифф не растворился молча: он остался ВНЕ блоков ```diff, и про
        # него есть именованная ошибка (R1-F1).
        self.assertEqual(errors, [guard.APPENDIX_DIFF_OUTSIDE_BLOCK_ERROR])

    def test_block_with_two_headers_gives_both_paths(self):
        """Блок ```diff с заголовками `diff --git` двух файлов даёт ОДНО
        приложение, несущее оба пути: ровно так выглядит вывод `git diff`
        по двум путям, и именно так написан реальный раздел
        `tasks/01M1THKTJ7YT1K410G1KS17MK6/PLAN.md` (пять заголовков в
        одном блоке).

        Ловит мутацию: из блока берётся только ПЕРВЫЙ заголовок
        (`search` вместо `findall`) — `git apply` на мерже правит оба
        файла, а `git add` уносит в main один: вторая правка Оператора
        исчезает вместе со scratch-деревом, и ни журнал, ни RETRO о ней
        не знают."""
        second = PROTECTED_DIR + "second.md"
        block = ("```diff\n"
                 f"diff --git a/{PROTECTED_FILE} b/{PROTECTED_FILE}\n"
                 f"--- a/{PROTECTED_FILE}\n+++ b/{PROTECTED_FILE}\n"
                 f"diff --git a/{second} b/{second}\n"
                 f"--- a/{second}\n+++ b/{second}\n```\n")

        appendices, errors = guard.plan_appendices(f"## Приложение\n\n{block}")

        self.assertEqual([a.paths for a in appendices],
                         [(PROTECTED_FILE, second)])
        self.assertEqual(errors, [])

    def test_unprotected_path_among_the_headers_refuses_the_whole_block(self):
        """Незащищённый путь во ВТОРОМ заголовке блока отказывает всему
        блоку именованной ошибкой.

        Ловит мутацию: защищённость проверяется только у первого пути
        блока — правка обычного файла репозитория, приписанная вторым
        заголовком, уехала бы в main коммитом пульта мимо ветки задачи,
        ревью и CI ветки."""
        block = ("```diff\n"
                 f"diff --git a/{PROTECTED_FILE} b/{PROTECTED_FILE}\n"
                 "diff --git a/docs/not-protected.md b/docs/not-protected.md\n"
                 "```\n")

        appendices, errors = guard.plan_appendices(f"## Приложение\n\n{block}")

        self.assertEqual(appendices, [])
        self.assertEqual(
            errors,
            [guard.appendix_unprotected_path_error("docs/not-protected.md")])

    def test_diff_under_a_bare_fence_gives_the_named_error(self):
        """Дифф раздела приложения, огороженный голым ``` вместо ```diff,
        даёт именованную ошибку, а не молчание.

        Ловит мутацию: блоки распознаются только по ограде ```diff, а
        остаток тела раздела никто не смотрит — приложение с голой
        оградой не даёт ни приложения, ни ошибки, и правка Оператора
        теряется бесследно ещё до гейта."""
        text = ("## Приложение\n\n```\n"
                f"diff --git a/{PROTECTED_FILE} b/{PROTECTED_FILE}\n"
                f"--- a/{PROTECTED_FILE}\n+++ b/{PROTECTED_FILE}\n```\n")

        appendices, errors = guard.plan_appendices(text)

        self.assertEqual(appendices, [])
        self.assertEqual(errors, [guard.APPENDIX_DIFF_OUTSIDE_BLOCK_ERROR])

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
        (fail-closed, ADR-0002), не молчаливый пропуск, и отказ ЭТОТ —
        отдельным действием: причина у него не в PLAN.md роли.

        Ловит мутацию: ветка `base is None` заменена на `return None`
        («git молчит — считаем применимым») — приложение уехало бы в main
        ни разу не проверенным, ровно как до этой задачи; вторая мутация
        — сбой git журналируется действием «приложение PLAN неприменимо»,
        и `auto` жжёт на нём гарантированный шаг developer с подсказкой
        «почини дифф», которую роли нечем исполнить."""
        text = f"## Приложение\n\n{diff_block(PROTECTED_FILE)}"

        with mock.patch.object(gitcmd, "diff_base", return_value=None):
            refuses = plan_appendix._plan_appendix_gate_refuses(
                self.conn, self.TASK, self.t, text)

        self.assertTrue(refuses)
        self.assertEqual(self.actions(),
                         [plan_appendix.PLAN_APPENDIX_GATE_FAILURE_ACTION])

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


class SequentialApplyGateTest(RealGitSandbox):
    """Гейт применимости на НАСТОЯЩЕМ git: два приложения к одному файлу,
    второе из которых опирается на строку первого."""

    TASK = "01PLANAPPENDIXSEQ00000001"

    def setUp(self):
        super().setUp()
        self.branch = f"task/{self.TASK.lower()}-x"
        (self.root / PROTECTED_FILE).write_text("alpha\nbeta\ngamma\n",
                                                encoding="utf-8")
        self.git("add", PROTECTED_FILE)
        self.git("commit", "-q", "-m", "защищённый файл базы")
        self.checkout(self.branch, create=True)
        (self.root / "feature.txt").write_text("код задачи\n", encoding="utf-8")
        self.git("add", "feature.txt")
        self.git("commit", "-q", "-m", f"{self.TASK}: код")
        self.checkout(config.MAIN_BRANCH)
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK, "Приложения PLAN", "in_dev",
                          self.branch, config.DEFAULT_TARGET, 10.0)

    def test_second_appendix_may_rely_on_the_first(self):
        """Два приложения к одному файлу, где второе опирается на строку,
        добавленную первым, гейт пропускает: он кладёт их ПОДРЯД на одно
        дерево — ровно так, как их положит цикл мержа.

        Ловит мутацию: гейт проверяет каждое приложение порознь против
        ЧИСТОЙ базы (`git apply --check`) — второе приложение отвергается
        с «error: patch failed», роль читает в брифе ложный отказ и
        починить его может только склейкой блоков в один, хотя на мерже
        оба легли бы."""
        first = ("```diff\n"
                 f"diff --git a/{PROTECTED_FILE} b/{PROTECTED_FILE}\n"
                 f"--- a/{PROTECTED_FILE}\n+++ b/{PROTECTED_FILE}\n"
                 "@@ -1,3 +1,3 @@\n alpha\n-beta\n+beta-Оператора\n gamma\n"
                 "```\n")
        second = ("```diff\n"
                  f"diff --git a/{PROTECTED_FILE} b/{PROTECTED_FILE}\n"
                  f"--- a/{PROTECTED_FILE}\n+++ b/{PROTECTED_FILE}\n"
                  "@@ -1,3 +1,4 @@\n alpha\n beta-Оператора\n gamma\n"
                  "+delta-Оператора\n```\n")

        refuses = plan_appendix._plan_appendix_gate_refuses(
            self.conn, self.TASK, {"branch": self.branch},
            f"## Приложение\n\n{first}\n{second}")

        journal = [r["action"] for r in store.task_steps(self.conn, self.TASK)]
        self.assertFalse(refuses, f"журнал отказов: {journal}")
        self.assertEqual(journal, [])

    def test_base_worktree_is_removed_after_the_gate(self):
        """Дерево базы сравнения убирается — и после пропуска, и после
        отказа: `git worktree list` пульта остаётся с одной записью.

        Ловит мутацию: уборка стоит не в `finally`, а после цикла (или
        снята вовсе) — каждая задача с приложением оставляла бы пульту
        временный worktree и запись `.git/worktrees/`, а отказавшая —
        ещё и дерево с половиной применённых хунков."""
        bad = ("```diff\n"
               f"diff --git a/{PROTECTED_FILE} b/{PROTECTED_FILE}\n"
               f"--- a/{PROTECTED_FILE}\n+++ b/{PROTECTED_FILE}\n"
               "@@ -1,3 +1,3 @@\n нет такой строки\n-и такой нет\n+новая\n"
               " и этой нет\n```\n")

        refuses = plan_appendix._plan_appendix_gate_refuses(
            self.conn, self.TASK, {"branch": self.branch},
            f"## Приложение\n\n{bad}")

        self.assertTrue(refuses)
        worktrees = [line for line in self.git("worktree", "list").splitlines()
                     if line.strip()]
        self.assertEqual(len(worktrees), 1, f"остались деревья: {worktrees}")


class RefusalClassTest(unittest.TestCase):
    """Класс отказа гейта применимости в `orchestrator/auto.py` (AC-6) —
    угол, который до REVIEW итерации 1 жила только планка задачи."""

    def test_inapplicable_refusal_is_role_fixable(self):
        """Отказ «приложение PLAN неприменимо» входит в перечень отказов
        `in_dev`, на которых `auto` запускает шаг developer.

        Ловит мутацию: действие убрано из
        `auto._IN_DEV_ROLE_FIXABLE_REFUSAL_ACTIONS` — отказ попадает в
        класс «нужны руки Оператора», второй вызов даёт `Stop`, и роль не
        получает ни одного шага на починку приложения (тупик задачи
        01M2XJKKPH 20.09)."""
        self.assertIn(plan_appendix.PLAN_APPENDIX_INAPPLICABLE_REFUSAL_ACTION,
                      auto._IN_DEV_ROLE_FIXABLE_REFUSAL_ACTIONS)

    def test_gate_failure_is_not_role_fixable(self):
        """Инфраструктурный отказ того же гейта в перечень НЕ входит.

        Ловит мутацию: в перечень внесено оба действия разом — `auto`
        жёг бы гарантированный шаг developer на сбое git с подсказкой
        «почини unified-дифф», которую роли нечем исполнить."""
        self.assertNotIn(plan_appendix.PLAN_APPENDIX_GATE_FAILURE_ACTION,
                         auto._IN_DEV_ROLE_FIXABLE_REFUSAL_ACTIONS)


TARGETS_YAML = """targets:
  artel:
    forge: github
    url: http://localhost/artel
    base: {base}
    token_slot: artel-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

BASE_TEXT = "первая строка базы\nвторая строка базы\nтретья строка базы\n"


class MergeAppendixTest(RealGitSandbox):
    """Применение приложений в цикле мержа (AC-8..AC-13) — тело гейта
    зовётся напрямую, тем же приёмом, что
    `tests/test_fsm_merge_gate_done_snapshot.py`.

    Песочница самостоятельная (а не импорт планки задачи): планка живёт в
    `tasks/<id>/acceptance_tests/`, уезжает снапшотом вместе с задачей и
    из `tests/` не импортируется."""

    TASK = "01PLANAPPENDIXMERGE000001"
    CODE_FILE = "feature.txt"
    FIXTURES = (PROTECTED_FILE, PROTECTED_FILE_2, PROTECTED_TESTS_FILE)

    def setUp(self):
        super().setUp()
        config.TARGETS.write_text(TARGETS_YAML.format(base=config.MAIN_BRANCH),
                                  encoding="utf-8")
        # Защищённые файлы-фикстуры коммитятся ДО origin: main origin —
        # база плотницкого merge, и файл, появившийся позже, в scratch не
        # попал бы вовсе.
        for rel in self.FIXTURES:
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(BASE_TEXT, encoding="utf-8")
            self.git("add", rel)
        self.git("commit", "-q", "-m", "защищённые файлы-фикстуры")
        self.origin = self.add_synced_origin()
        capture(catalog.cmd_init)

        self.branch = f"task/{self.TASK.lower()}-x"
        self.checkout(self.branch, create=True)
        (self.root / self.CODE_FILE).write_text("код задачи\n",
                                                encoding="utf-8")
        self.git("add", self.CODE_FILE)
        self.git("commit", "-q", "-m", f"{self.TASK}: код задачи")
        self.checkout(config.MAIN_BRANCH)

        store.insert_task(store.db(), self.TASK, f"Задача {self.TASK}",
                          "merge_gate", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        self.conn = store.db()
        self.full_suite_calls = []
        self.full_suite_result = (True, "42 passed (тест)")
        self.patch(acceptance, "run_full_suite", self.fake_full_suite)
        self.patch(ci, "branch_status", lambda branch: (True, "зелёный (тест)"))

    # ------------------------------------------------------------ фикстуры

    def patch(self, target, attr: str, replacement) -> None:
        patcher = mock.patch.object(target, attr, replacement)
        patcher.start()
        self.addCleanup(patcher.stop)

    def fake_full_suite(self, root):
        self.full_suite_calls.append(Path(root))
        return self.full_suite_result

    def applicable_block(self, rels: list[str], marker: str) -> str:
        """Блок ```diff из НАСТОЯЩЕГО `git diff` по перечисленным файлам:
        применимость обеспечена git'ом, а не глазомером автора теста.
        Несколько файлов в одном блоке — ровно то, что даёт `git diff` по
        двум путям (R1-F1)."""
        before = {rel: (self.root / rel).read_text(encoding="utf-8")
                  for rel in rels}
        for rel, text in before.items():
            (self.root / rel).write_text(
                text.replace("вторая строка базы", f"{marker} ({rel})"),
                encoding="utf-8")
        diff = self.git("diff", "--", *rels)
        for rel, text in before.items():
            (self.root / rel).write_text(text, encoding="utf-8")
        self.assertIn(f"diff --git a/{rels[0]} b/{rels[0]}", diff)
        return f"```diff\n{diff}```\n"

    def commit_plan(self, blocks: list[str] | None = None) -> None:
        section = ("\n## Приложение: правка защищённых путей\n\n"
                   + "\n".join(blocks) if blocks else "")
        text = (f"---\ntask: {self.TASK}\ntype: plan\nauthor_role: developer\n"
                f"status: ready\nschema_version: 2\n---\n\n# PLAN\n\n"
                f"## Подход\n\nФикстура.\n{section}")
        sha = artifact_branch.commit_files(
            self.TASK, {f"tasks/{self.TASK}/PLAN.md": text},
            f"{self.TASK}: PLAN.md")
        self.assertTrue(sha, "PLAN.md не закоммичен в артефактную ветку")

    # -------------------------------------------------------------- чтение

    def approve(self):
        t = store.get_task(store.db(), self.TASK)
        return fsm_merge_gate._cmd_approve_merge_gate(
            store.db(), self.TASK, "merge_gate", t,
            confirmed_ci_note="зелёный (тест)")

    def origin_git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(self.origin), *args],
                              capture_output=True, text=True)

    def origin_main_sha(self) -> str:
        res = self.origin_git("rev-parse", "refs/heads/" + config.MAIN_BRANCH)
        return res.stdout.strip() if res.returncode == 0 else ""

    def origin_subjects(self) -> list[str]:
        res = self.origin_git("log", "--format=%s", "--reverse",
                              "refs/heads/" + config.MAIN_BRANCH)
        return [s for s in res.stdout.splitlines() if s]

    def origin_files_changed_by(self, mark: str) -> list[str]:
        res = self.origin_git("log", "--format=%H %s",
                              "refs/heads/" + config.MAIN_BRANCH)
        for line in res.stdout.splitlines():
            sha, _, subject = line.partition(" ")
            if mark in subject:
                show = self.origin_git("show", "--name-only", "--format=", sha)
                return [p for p in show.stdout.splitlines() if p]
        return []

    def journal_blob(self) -> str:
        return "\n".join(f"{r['action']} | {r['detail'] or ''}"
                         for r in store.task_steps(store.db(), self.TASK))

    def state(self) -> str:
        return store.db().execute("SELECT state FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()["state"]

    # --------------------------------------------------------------- тесты

    def test_appendix_commit_precedes_the_artifact_snapshot(self):
        """Приложение к двум защищённым файлам одним блоком уезжает в main
        отдельным коммитом «<id>: приложения Оператора — <пути>», ДО
        коммита снимка артефактов, и коммит несёт ОБА файла.

        Ловит мутацию: вызов `_apply_plan_appendices` снят из
        `_cmd_approve_merge_gate` (или переставлен после публикации
        артефактов) — коммита приложений в main не окажется вовсе либо он
        встанет после снимка; вторая мутация — из блока берётся только
        первый заголовок `diff --git`, и второй файл в коммит не
        попадает."""
        self.commit_plan([self.applicable_block(
            [PROTECTED_FILE, PROTECTED_FILE_2], "правка Оператора")])

        result = self.approve()

        self.assertEqual(result, ("done",), self.journal_blob())
        subjects = self.origin_subjects()
        applied = [i for i, s in enumerate(subjects)
                   if "приложения Оператора" in s]
        snapshot = [i for i, s in enumerate(subjects)
                    if "снимок артефактной ветки" in s]
        self.assertTrue(applied, f"нет коммита приложений: {subjects}")
        self.assertTrue(snapshot, f"нет коммита снимка: {subjects}")
        self.assertLess(applied[0], snapshot[0], subjects)
        self.assertEqual(
            sorted(self.origin_files_changed_by("приложения Оператора")),
            sorted([PROTECTED_FILE, PROTECTED_FILE_2]))
        self.assertIn("приложения применены:", self.journal_blob())

    def test_inapplicable_appendix_returns_the_task_to_in_dev(self):
        """Приложение, не применимое к подтянутому main, возвращает задачу
        в `in_dev` — без `sys.exit`, без продвижения main, без оставленного
        scratch-дерева.

        Ловит мутацию: неприменимое на мерже приложение завершает процесс
        отказом (или, хуже, проезжает молча) — задача застревает на
        `merge_gate` без роли, способной починить дифф, а main уезжает с
        половиной хунков."""
        self.commit_plan([("```diff\n"
                           f"diff --git a/{PROTECTED_FILE} b/{PROTECTED_FILE}\n"
                           f"--- a/{PROTECTED_FILE}\n+++ b/{PROTECTED_FILE}\n"
                           "@@ -1,3 +1,3 @@\n строки, которой нет\n"
                           "-и этой нет\n+правка\n и этой нет\n```\n")])
        before = self.origin_main_sha()

        result = self.approve()

        self.assertEqual(result, ("stopped",))
        self.assertEqual(self.state(), "in_dev", self.journal_blob())
        self.assertIn("приложение PLAN неприменимо после подтяжки:",
                      self.journal_blob())
        self.assertEqual(self.origin_main_sha(), before)
        self.assertEqual(
            [line for line in self.git("worktree", "list").splitlines()
             if line.strip()][1:], [],
            "scratch-дерево мержа не убрано")

    def test_red_full_suite_keeps_the_task_on_merge_gate(self):
        """Красный полный прогон приложения к `tests/` — именованный отказ
        мержа: задача остаётся на `merge_gate`, main не продвинут.

        Ловит мутацию: исход прогона не смотрят (или красный понижен до
        предупреждения) — приложение, ломающее набор тестов, уехало бы в
        main, и чинить его было бы уже нечем: сам набор и есть то, чем
        main проверяется."""
        self.commit_plan([self.applicable_block([PROTECTED_TESTS_FILE],
                                                "правка набора")])
        self.full_suite_result = (False, "1 failed (тест)")
        before = self.origin_main_sha()

        with self.assertRaises(SystemExit) as caught:
            self.approve()

        self.assertIn("приложения ломают тесты:", str(caught.exception.code))
        self.assertEqual(self.state(), "merge_gate")
        self.assertEqual(self.origin_main_sha(), before)
        self.assertEqual(len(self.full_suite_calls), 1)

    def test_plan_without_appendices_merges_as_before(self):
        """PLAN без разделов «## Приложение»: мерж идёт прежним путём — ни
        коммита приложений, ни полного прогона, ни записи журнала о них
        (AC-13).

        Ловит мутацию: узел приложений зовёт `git apply`/полный прогон
        безусловно — КАЖДЫЙ мерж артели платил бы полным набором под
        удерживаемым мьютексом merge-окна и получал бы лишний пустой
        коммит в main."""
        self.commit_plan()

        result = self.approve()

        self.assertEqual(result, ("done",), self.journal_blob())
        self.assertEqual([s for s in self.origin_subjects()
                          if "приложения Оператора" in s], [])
        self.assertEqual(self.full_suite_calls, [])
        self.assertNotIn("приложения применены:", self.journal_blob())


if __name__ == "__main__":
    unittest.main()
