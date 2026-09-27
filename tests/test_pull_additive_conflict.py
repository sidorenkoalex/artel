"""Юнит-тесты аддитивного слияния конфликта подтяжки main
(SPEC 01M3GKJ84XM5QPC6TK5EE307Q9, требования 4-9) — против НАСТОЯЩЕГО git
в песочнице `tests/sandbox.py::RealGitSandbox` (требование 11).

Заглушкой здесь нечего изображать: предмет — сами стадии индекса
(`:1:`/`:2:`/`:3:`), оставленные неудачным `git merge`, нули в колонке
удалений `git diff --no-index --numstat` и порядок добавок
`git merge-file --union`. Поддельный git мог бы «подтвердить» любую из
этих трёх вещей, ничего не проверив.

Регенерация карты кодовой базы (единственная часть, где `pull.py` зовёт
не git, а `scripts/codebase_map.py`) подменяется в наборе «карта +
документ» стабом ИМЕННО В ПРОСТРАНСТВЕ ИМЁН `pull` (`pull.subprocess`):
патчить `subprocess.run` глобально нельзя — этот же атрибут держит
`SpyRun` песочницы для `gitcmd`. Сама регенерация — предмет
`tests/test_fsm_map_conflict_autoresolve.py`, здесь проверяется, что
карта и документы разрешаются ОДНИМ коммитом.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, gitcmd, pull, store  # noqa: E402
from scripts import ci_push_class  # noqa: E402
from tests.sandbox import RealGitSandbox  # noqa: E402

MAP_REL = "docs/codebase-map.md"

SPEC_NO_AC_MARKUP = (
    "---\ntask: x\ntype: spec\nauthor_role: analyst\n"
    "status: ready\nschema_version: 1\n---\n\n# SPEC\n")

BASE_A = "a1\na2\na3\n"
BASE_B = "b1\nb2\n"

#: База документа-списка из замечания R1-F1 ревью итерации 1: два
#: растущих вниз списка, между которыми ВСЕГО две строки базы — меньше
#: контекста git, поэтому добавки сторон в разные списки склеиваются в
#: одну конфликтную область.
BASE_LISTS = "## Open\n- open: A\n## Closed\n- closed: B\n"

#: Те же два списка, разведённые шестью строками базы — хунки сторон
#: остаются раздельными, и union-слияние идёт штатно (парный случай к
#: `BASE_LISTS`).
BASE_FAR = "## Open\n- open: A\nx1\nx2\nx3\nx4\n## Closed\n- closed: B\n"

#: Карта кодовой базы — в базе слияния (ДО ветвления), чтобы её конфликт
#: в наборе «карта + документ» был содержательным (стадия базы есть), а
#: не `add/add` (R1-F4 ревью итерации 1).
MAP_BASE = "---\nbuilt_at_sha: seed\n---\n\n# Карта\n"


class AdditiveConflictSandbox(RealGitSandbox):
    """Ветка задачи и main, разошедшиеся правками одних и тех же файлов —
    общая обвязка сценариев файла, сама тестов не несёт."""

    TASK = "01PULLADDITIVECONFLICT"
    BRANCH = f"task/{TASK.lower()}-x"

    def setUp(self):
        super().setUp()
        self.write_files({"docs/a.md": BASE_A, "docs/b.md": BASE_B,
                          "docs/lists.md": BASE_LISTS, "docs/far.md": BASE_FAR,
                          MAP_REL: MAP_BASE})
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "seed: документы")

        store.insert_task(store.db(), self.TASK,
                          "Юнит-тест аддитивного конфликта", "in_dev",
                          self.BRANCH, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        self.checkout(self.BRANCH, create=True)

        from orchestrator import workspace
        ensure_patcher = mock.patch.object(
            workspace, "ensure", mock.Mock(return_value=(self.root, None)))
        ensure_patcher.start()
        self.addCleanup(ensure_patcher.stop)

        self.origin_main_source = mock.Mock(
            return_value=("origin", config.MAIN_BRANCH))
        self.read_branch_text_or_refuse = mock.Mock(
            return_value=SPEC_NO_AC_MARKUP)

    # ------------------------------------------------------------ утилиты

    def write_files(self, files: dict) -> None:
        for rel, text in files.items():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def commit_on_branch(self, files: dict) -> None:
        self.write_files(files)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "ветка задачи")

    def commit_on_main(self, files: dict) -> None:
        self.checkout(config.MAIN_BRANCH)
        self.write_files(files)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "main")
        self.checkout(self.BRANCH)

    def branch_head(self) -> str:
        return self.git("rev-parse", "HEAD").strip()

    def evaluate(self):
        conn = store.db()
        t = store.get_task(conn, self.TASK)
        main_sha = self.git("rev-parse", config.MAIN_BRANCH).strip()
        return pull.evaluate(
            conn, self.TASK, t, "in_dev",
            origin_main_source=self.origin_main_source,
            origin_main_sha=mock.Mock(return_value=main_sha),
            read_branch_text_or_refuse=self.read_branch_text_or_refuse)

    def state(self) -> str:
        return store.get_task(store.db(), self.TASK)["state"]

    def journal(self) -> list:
        return store.task_steps(store.db(), self.TASK)

    def actions(self) -> list:
        return [r["action"] for r in self.journal()]

    def read(self, rel: str) -> str:
        return (self.root / rel).read_text(encoding="utf-8")

    def unmerged(self) -> list:
        return self.git("diff", "--name-only", "--diff-filter=U").split()

    def first_parent_subjects(self, since: str) -> list:
        return self.git("log", "--first-parent", "--format=%s",
                        f"{since}..HEAD").splitlines()


class AdditiveDocsMergedTest(AdditiveConflictSandbox):

    def setUp(self):
        super().setUp()
        self.commit_on_branch({"docs/a.md": BASE_A + "BRANCH-A\n",
                               "docs/b.md": BASE_B + "BRANCH-B\n"})
        self.commit_on_main({"docs/a.md": BASE_A + "MAIN-A\n",
                             "docs/b.md": BASE_B + "MAIN-B\n"})
        self.before = self.branch_head()
        self.outcome = self.evaluate()

    def test_two_additive_documents_merge_without_escalation(self):
        """AC-6: конфликт по двум документам, где каждая сторона только
        дописала строки, завершает merge — `Pulled`, задача остаётся в
        `in_dev`, неразрешённых путей в индексе нет, и в каждом файле
        присутствуют ВСЕ строки базы и ВСЕ добавки обеих сторон.

        Ловит мутацию: аддитивное слияние не подключено (или подключено
        только для одного файла набора) — `evaluate` вернула бы `Conflict`
        и увела задачу в `escalated`; либо union заменён на выбор одной
        стороны — сравнение полного текста поймает потерянную добавку."""
        self.assertIsInstance(self.outcome, pull.Pulled)
        self.assertEqual(self.state(), "in_dev")
        self.assertEqual(self.unmerged(), [])
        self.assertEqual(self.read("docs/a.md"), BASE_A + "MAIN-A\nBRANCH-A\n")
        self.assertEqual(self.read("docs/b.md"), BASE_B + "MAIN-B\nBRANCH-B\n")

    def test_main_addition_stands_before_the_branch_addition(self):
        """AC-7: в слитом файле добавка main стоит ПЕРЕД добавкой ветки
        задачи.

        Ловит мутацию: порядок аргументов `git merge-file --union`
        перевёрнут (стадия ветки первой) — добавка ветки встала бы выше
        добавки main, и хронология растущего вниз списка сломалась бы для
        всей волны."""
        lines = self.read("docs/a.md").splitlines()
        self.assertLess(lines.index("MAIN-A"), lines.index("BRANCH-A"))

    def test_single_pull_commit_and_journal_record(self):
        """AC-8: слияние завершает ТОТ ЖЕ коммит подтяжки, отдельного
        коммита разрешения нет, в журнале — запись «аддитивный конфликт
        слит» с перечислением слитых файлов.

        Ловит мутацию: разрешение коммитится своим коммитом (или коммит
        подтяжки не завершается вовсе) — список subject'ов первого
        родителя перестал бы состоять из одного сообщения подтяжки; либо
        запись журнала потеряна — Оператор не узнал бы, что пульт правил
        его документы."""
        subjects = self.first_parent_subjects(self.before)
        self.assertEqual(subjects, [f"{self.TASK}: подтяжка {config.MAIN_BRANCH}"])

        rows = [r for r in self.journal()
                if r["action"] == pull.ADDITIVE_CONFLICT_ACTION]
        self.assertEqual(len(rows), 1, self.actions())
        self.assertIn("docs/a.md", rows[0]["detail"])
        self.assertIn("docs/b.md", rows[0]["detail"])

    def test_no_temporary_stage_files_are_left_in_the_working_tree(self):
        """Стадии выкладываются ВНЕ рабочего дерева: ни `.merge_file_*`,
        ни иных посторонних файлов после слияния в дереве нет.

        Ловит мутацию: стадии берутся `git checkout-index --stage=all
        --temp` (кладёт `.merge_file_*` в корень дерева) — следующий шаг
        задачи получил бы ложный отказ гейта зон по постороннему файлу,
        тот же класс, что регрессия волны 3 от 12.09."""
        self.assertEqual(self.git("status", "--porcelain").strip(), "")


class NonAdditiveConflictEscalatesTest(AdditiveConflictSandbox):

    def test_changed_base_line_keeps_the_previous_escalation(self):
        """AC-9: одна из сторон ИЗМЕНИЛА базовую строку — прежнее
        поведение: merge откачен, задача в `escalated`, note несёт текст
        `_merge_conflict_note`, журнал — метку
        `PULL_CONFLICT_ROLE_STEP_MARKER`.

        Ловит мутацию: аддитивным считается конфликт с изменением
        базовой строки (например, колонка удалений `numstat` не
        проверяется) — пульт молча склеил бы правку, которую обязан
        отдать разработчику, и потерянной строки никто бы не заметил."""
        self.commit_on_branch({"docs/a.md": "a1\nИЗМЕНЕНО\na3\nBRANCH-A\n"})
        self.commit_on_main({"docs/a.md": BASE_A + "MAIN-A\n"})

        outcome = self.evaluate()

        self.assertIsInstance(outcome, pull.Conflict)
        self.assertEqual(outcome.files, ["docs/a.md"])
        self.assertIn("конфликт подтяжки", outcome.note)
        self.assertEqual(self.state(), "escalated")
        self.assertEqual(self.unmerged(), [])
        self.assertIn("ИЗМЕНЕНО", self.read("docs/a.md"))
        self.assertNotIn("MAIN-A", self.read("docs/a.md"))
        self.assertIn(pull.PULL_CONFLICT_ROLE_STEP_MARKER, self.actions())

    def test_a_single_non_document_in_the_set_escalates_the_whole_set(self):
        """AC-10: набор включает не-документ (`.py`) — эскалация как
        прежде, даже если остальные файлы набора документные и
        аддитивные.

        Ловит мутацию: документность проверяется не у всех файлов набора
        (например, по первому или по любому одному) — конфликт кода
        завершился бы коммитом подтяжки с неразрешёнными маркерами `.py`
        в дереве."""
        self.commit_on_branch({"docs/a.md": BASE_A + "BRANCH-A\n",
                               "orchestrator/x.py": "# ветка\n"})
        self.commit_on_main({"docs/a.md": BASE_A + "MAIN-A\n",
                             "orchestrator/x.py": "# main\n"})

        outcome = self.evaluate()

        self.assertIsInstance(outcome, pull.Conflict)
        self.assertEqual(outcome.files, ["docs/a.md", "orchestrator/x.py"])
        self.assertEqual(self.state(), "escalated")
        self.assertEqual(self.unmerged(), [])
        self.assertEqual(self.read("docs/a.md"), BASE_A + "BRANCH-A\n")

    def test_document_added_by_both_sides_escalates(self):
        """AC-12: документ добавлен ОБЕИМИ сторонами — базовой стадии нет,
        «аддитивно относительно базы» не определено, исход тот же, что у
        AC-9.

        Ловит мутацию: отсутствие стадии базы трактуется как пустая база
        (например, ошибка `git show :1:` игнорируется) — пульт склеил бы
        два независимых документа в один без ведома автора."""
        self.commit_on_branch({"docs/new.md": "branch new\n"})
        self.commit_on_main({"docs/new.md": "main new\n"})

        outcome = self.evaluate()

        self.assertIsInstance(outcome, pull.Conflict)
        self.assertEqual(self.state(), "escalated")
        self.assertEqual(self.unmerged(), [])
        self.assertEqual(self.read("docs/new.md"), "branch new\n")

    def test_failed_union_merge_step_escalates_fail_closed(self):
        """AC-12: git не ответил успешно на шаг слияния (`merge-file`) —
        эскалация как прежде, ни одного изменённого файла в дереве.

        Ловит мутацию: неуспешный ответ git на слиянии игнорируется и
        путь автоматики продолжается — в файл попал бы пустой (или
        частичный) результат, и строки документа были бы потеряны
        молча."""
        self.commit_on_branch({"docs/a.md": BASE_A + "BRANCH-A\n"})
        self.commit_on_main({"docs/a.md": BASE_A + "MAIN-A\n"})
        real_in_repo = gitcmd.in_repo

        def failing_merge_file(repo, *args):
            if args[:1] == ("merge-file",):
                return subprocess.CompletedProcess(
                    ("git", *args), 1, "", "merge-file отказал (стаб)")
            return real_in_repo(repo, *args)

        with mock.patch.object(gitcmd, "in_repo", failing_merge_file):
            outcome = self.evaluate()

        self.assertIsInstance(outcome, pull.Conflict)
        self.assertEqual(self.state(), "escalated")
        self.assertEqual(self.read("docs/a.md"), BASE_A + "BRANCH-A\n")


class CloseHunksEscalateTest(AdditiveConflictSandbox):
    """Пост-проверка «итог == база + добавки обеих сторон» (решение
    Оператора ANSWER-1 п.1 по замечанию R1-F1 ревью итерации 1): обе
    стороны аддитивны, git отвечает нулём, но union-слияние близких
    хунков дублирует строки базы — такой конфликт обязан эскалировать, а
    не коммититься."""

    #: Обе стороны дописывают по пункту в КАЖДЫЙ из двух списков базы;
    #: между списками две строки базы — меньше контекста git.
    BRANCH_LISTS = ("## Open\n- open: A\n- open: BRANCH\n"
                    "## Closed\n- closed: B\n- closed: BRANCH-C\n")
    MAIN_LISTS = ("## Open\n- open: A\n- open: MAIN\n"
                  "## Closed\n- closed: B\n- closed: MAIN-C\n")

    def setUp(self):
        super().setUp()
        self.commit_on_branch({"docs/lists.md": self.BRANCH_LISTS})
        self.commit_on_main({"docs/lists.md": self.MAIN_LISTS})
        self.before = self.branch_head()
        self.outcome = self.evaluate()

    def test_close_additive_hunks_escalate_instead_of_being_committed(self):
        """Добавки сторон ближе четырёх строк базы друг к другу —
        прежняя эскалация: `Conflict`, `escalated`, `merge --abort`,
        метка «нужен шаг роли». Документ ветки остаётся нетронутым, и
        коммита подтяжки нет.

        Ловит мутацию: пост-проверка снята (итог union берётся как есть,
        раз обе стороны «+N, −0») — пульт закоммитил бы документ, в
        котором строки базы `## Closed`/`- closed: B` стоят ДВАЖДЫ, а
        `- open: BRANCH` уехал в чужой раздел, и унёс бы эту порчу в
        main как удачную подтяжку."""
        self.assertIsInstance(self.outcome, pull.Conflict)
        self.assertEqual(self.outcome.files, ["docs/lists.md"])
        self.assertEqual(self.state(), "escalated")
        self.assertEqual(self.unmerged(), [])
        self.assertEqual(self.read("docs/lists.md"), self.BRANCH_LISTS)
        self.assertEqual(self.first_parent_subjects(self.before), [])
        self.assertIn(pull.PULL_CONFLICT_ROLE_STEP_MARKER, self.actions())
        self.assertNotIn(pull.ADDITIVE_CONFLICT_ACTION, self.actions())

    def test_both_sides_are_additive_so_the_side_check_alone_would_pass(self):
        """Сверка аддитивности САМИХ СТОРОН этот случай пропускает: у
        каждой стороны «+2, −0» относительно базы — эскалацию даёт
        именно пост-проверка итога, а не отказ `_side_added_lines`.

        Ловит мутацию: эскалация приписана сверке сторон (например,
        `_side_added_lines` стал возвращать `None` на любом
        многохунковом диффе) — механизм закрыл бы заодно и штатные
        аддитивные слияния с двумя далёкими добавками, а тест выше
        остался бы зелёным и это скрыл."""
        base = self.root / "base.md"
        branch = self.root / "branch.md"
        main = self.root / "main.md"
        base.write_text(BASE_LISTS, encoding="utf-8")
        branch.write_text(self.BRANCH_LISTS, encoding="utf-8")
        main.write_text(self.MAIN_LISTS, encoding="utf-8")

        self.assertEqual(pull._side_added_lines(self.root, base, branch), 2)
        self.assertEqual(pull._side_added_lines(self.root, base, main), 2)


class DistantHunksStillMergeTest(AdditiveConflictSandbox):
    """Парная проверка к `CloseHunksEscalateTest`: те же два списка, но
    разведённые шестью строками базы — git держит хунки раздельно, итог
    сходится с арифметикой, и пост-проверка слиянию не мешает."""

    # Имена с суффиксом `_TEXT`: `BRANCH` у песочницы — ИМЯ ветки задачи,
    # перекрыть его текстом документа значит увести `checkout -b` в
    # многострочный «branch name». Сам `docs/far.md` лежит в базе
    # слияния (`AdditiveConflictSandbox.setUp`) — иначе конфликт был бы
    # `add/add`, а предмет теста — конфликт содержимого.
    BRANCH_TEXT = ("## Open\n- open: A\n- open: BRANCH\nx1\nx2\nx3\nx4\n"
                   "## Closed\n- closed: B\n- closed: BRANCH-C\n")
    MAIN_TEXT = ("## Open\n- open: A\n- open: MAIN\nx1\nx2\nx3\nx4\n"
                 "## Closed\n- closed: B\n- closed: MAIN-C\n")

    def setUp(self):
        super().setUp()
        self.commit_on_branch({"docs/far.md": self.BRANCH_TEXT})
        self.commit_on_main({"docs/far.md": self.MAIN_TEXT})

    def test_two_distant_additive_hunks_merge_in_order_main_then_branch(self):
        """Пост-проверка не закрывает штатный случай: документ с двумя
        далёкими добавками каждой стороны сливается, все строки базы — по
        одному разу, порядок в каждой области «main, затем ветка».

        Ловит мутацию: пост-проверка ужесточена до «один хунк на файл»
        (или сравнивает не те числа) — обычное аддитивное слияние
        растущего списка ушло бы в эскалацию, и механика задачи не
        срабатывала бы ровно там, ради чего заведена."""
        outcome = self.evaluate()

        self.assertIsInstance(outcome, pull.Pulled)
        self.assertEqual(self.state(), "in_dev")
        self.assertEqual(
            self.read("docs/far.md"),
            "## Open\n- open: A\n- open: MAIN\n- open: BRANCH\n"
            "x1\nx2\nx3\nx4\n"
            "## Closed\n- closed: B\n- closed: MAIN-C\n- closed: BRANCH-C\n")


class LineCountTest(unittest.TestCase):

    def test_last_line_without_a_trailing_newline_still_counts(self):
        """`_line_count` считает строки тем же счётом, что `git diff
        --numstat`: хвост без перевода строки — тоже строка, пустой
        текст — ноль.

        Ловит мутацию: счёт заменён на `text.count("\\n")` — файл без
        завершающего перевода строки давал бы итог на строку меньше
        суммы «база + добавки», и штатное аддитивное слияние такого
        документа уходило бы в ложную эскалацию."""
        self.assertEqual(pull._line_count(""), 0)
        self.assertEqual(pull._line_count("a\n"), 1)
        self.assertEqual(pull._line_count("a\nb"), 2)
        self.assertEqual(pull._line_count("a\nb\n"), 2)


class MapWithAdditiveDocumentTest(AdditiveConflictSandbox):
    """AC-11: набор «карта + аддитивный документ». Карта лежит в БАЗЕ
    слияния (`AdditiveConflictSandbox.setUp`, до ветвления) — её конфликт
    здесь содержательный, со всеми тремя стадиями индекса, а не `add/add`
    (R1-F4 ревью итерации 1: раньше карта коммитилась уже ПОСЛЕ
    переключения на ветку задачи, и в main её не было вовсе)."""

    MAP_BASE = MAP_BASE
    STUB_MAP = "---\nbuilt_at_sha: regen\n---\n\n# Карта (стаб регенерации)\n"

    def setUp(self):
        super().setUp()
        self.commit_on_branch({MAP_REL: self.MAP_BASE + "ветка\n",
                               "docs/a.md": BASE_A + "BRANCH-A\n"})
        self.commit_on_main({MAP_REL: self.MAP_BASE + "main\n",
                             "docs/a.md": BASE_A + "MAIN-A\n"})

    def test_the_map_conflict_of_this_set_has_a_merge_base(self):
        """Форма конфликта карты в этом наборе — содержательная, со
        стадией базы: карта лежит в КОММИТЕ БАЗЫ слияния, и обе стороны
        правят её относительно него (а не добавляют с нуля каждая
        своей). Иначе AC-11 проверялся бы на `add/add` — форме, которую
        требование 9 не имеет в виду.

        Ловит мутацию: карта снова коммитится только в ветке задачи (как
        было до R1-F4) — в базе слияния её не оказалось бы, конфликт стал
        бы `add/add`, и набор «карта + документ» закрывался бы
        отсутствием стадии базы, а не разбирался бы по требованию 9."""
        base = self.git("merge-base", "HEAD", config.MAIN_BRANCH).strip()

        self.assertEqual(self.git("show", f"{base}:{MAP_REL}"), self.MAP_BASE)
        self.assertEqual(self.git("show", f"HEAD:{MAP_REL}"),
                         self.MAP_BASE + "ветка\n")
        self.assertEqual(self.git("show", f"{config.MAIN_BRANCH}:{MAP_REL}"),
                         self.MAP_BASE + "main\n")

    def fake_regen(self, args, cwd=None, capture_output=None, text=None):
        """Стаб `python3 scripts/codebase_map.py`: пишет карту на слитом
        дереве и отвечает нулевым кодом, как настоящая регенерация."""
        (Path(cwd) / MAP_REL).write_text(self.STUB_MAP, encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, "", "")

    def test_map_and_additive_document_resolve_in_one_pull_commit(self):
        """AC-11: карта разрешена перегенерацией, документ — аддитивным
        слиянием, merge завершён ОДНИМ коммитом подтяжки, в журнале обе
        записи.

        Ловит мутацию: условие авторазрешения осталось «конфликтные файлы
        == [карта]» — набор из карты и документа эскалировал бы, ровно как
        26–27.09; либо карта и документы коммитятся двумя коммитами —
        список subject'ов первого родителя это поймает."""
        before = self.branch_head()

        with mock.patch.object(pull, "subprocess",
                              mock.Mock(run=self.fake_regen)):
            outcome = self.evaluate()

        self.assertIsInstance(outcome, pull.Pulled)
        self.assertEqual(self.state(), "in_dev")
        self.assertEqual(self.unmerged(), [])
        self.assertEqual(self.read(MAP_REL), self.STUB_MAP)
        self.assertEqual(self.read("docs/a.md"), BASE_A + "MAIN-A\nBRANCH-A\n")
        self.assertEqual(
            self.first_parent_subjects(before),
            [f"{self.TASK}: подтяжка {config.MAIN_BRANCH}"])

        actions = self.actions()
        self.assertIn(pull.ADDITIVE_CONFLICT_ACTION, actions)
        self.assertIn("конфликт подтяжки: карта авторазрешена регенерацией",
                      actions)

    def test_failed_map_regen_after_staged_documents_still_aborts_cleanly(self):
        """Регенерация карты отказала ПОСЛЕ того, как аддитивные документы
        уже записаны и добавлены в индекс: `git merge --abort` откатывает
        дерево целиком, задача эскалирует, документ возвращается к версии
        ветки.

        Ловит мутацию: слитые документы записываются на диск БЕЗ `git add`
        (или до того, как все union-тексты посчитаны) — незакоммиченная
        правка помешала бы `git merge --abort`, и задача осталась бы в
        полуслитом дереве с чужими строками в документе."""
        def failing_regen(args, cwd=None, capture_output=None, text=None):
            return subprocess.CompletedProcess(args, 1, "", "регенерация упала")

        with mock.patch.object(pull, "subprocess",
                              mock.Mock(run=failing_regen)):
            outcome = self.evaluate()

        self.assertIsInstance(outcome, pull.Conflict)
        self.assertEqual(self.state(), "escalated")
        self.assertEqual(self.unmerged(), [])
        self.assertEqual(self.git("status", "--porcelain").strip(), "")
        self.assertEqual(self.read("docs/a.md"), BASE_A + "BRANCH-A\n")
        self.assertEqual(self.read(MAP_REL), self.MAP_BASE + "ветка\n")

    def test_map_alone_keeps_todays_journal_detail(self):
        """Требование 9: набор из ОДНОЙ карты ведёт себя как сегодня —
        та же запись журнала с той же деталью «единственный конфликтующий
        файл».

        Ловит мутацию: деталь записи о карте переписана на общий текст
        для любого набора — сегодняшнее поведение набора из одной карты
        изменилось бы, хотя SPEC требует сохранить его дословно."""
        self.assertEqual(
            pull._map_journal_detail([MAP_REL]),
            f"{MAP_REL} — единственный конфликтующий файл, разрешён "
            f"checkout --theirs + регенерация scripts/codebase_map.py на "
            f"слитом дереве worktree задачи")
        self.assertNotIn("единственный",
                         pull._map_journal_detail([MAP_REL, "docs/a.md"]))


class DocPathDefinitionTest(unittest.TestCase):

    def test_definition_is_wider_than_the_ci_push_classifier(self):
        """Требование 4: документ здесь — `docs/**` либо любой `.md`; это
        НЕ `ci_push_class.is_doc_path` (у того `.md` — только в корне, а
        `tasks/**` — документы).

        Ловит мутацию: `pull._is_doc_path` заменён вызовом
        `ci_push_class.is_doc_path` — `skills/x.md` перестал бы быть
        документом для подтяжки, а `tasks/<id>/code.py` стал бы им, и
        конфликт кода задачи молча склеился бы union'ом."""
        self.assertTrue(pull._is_doc_path("docs/stack.md"))
        self.assertTrue(pull._is_doc_path("docs/adr/0001-x.md"))
        self.assertTrue(pull._is_doc_path("skills/x.md"))
        self.assertFalse(ci_push_class.is_doc_path("skills/x.md"))
        self.assertFalse(pull._is_doc_path("orchestrator/pull.py"))
        self.assertFalse(pull._is_doc_path("tasks/T001/code.py"))
        self.assertTrue(ci_push_class.is_doc_path("tasks/T001/code.py"))


if __name__ == "__main__":
    unittest.main()
