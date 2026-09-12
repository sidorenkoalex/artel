"""Приёмочные тесты SPEC 01M2A22CG2P0E69H00RDHFF3K4: `canary.
_spec_gate_next_state`/`_pass_spec_gate` обязаны определять источник
SPEC через `artifact_source.resolve(conn, task_id)`, не через
`gitcmd.on_foreign_branch(t["branch"])` — иначе AC-разметка SPEC на
артефактной ветке теряется, и канареечная задача уходит в `in_dev`,
минуя `tests_writing`/test_author (SPEC, Контекст).

Красен до реализации: на момент написания `_spec_gate_next_state`
(orchestrator/canary.py:513-523) всё ещё читает SPEC через `gitcmd.
on_foreign_branch(t["branch"])` и диск `config.TASKS/<id>/SPEC.md` —
для задачи, чей SPEC лежит только на артефактной ветке (как в AC-1/
AC-2), она получает пустой словарь frontmatter и ошибочно возвращает
`"in_dev"`; `test_ac4_...` падает на `on_foreign_branch.assert_not_
called()`, так как функция всё ещё её вызывает. `_pass_spec_gate`
(строки 526-533) пока не отличает «SPEC не найден» от «SPEC без
AC-разметки» и не зовёт `_kill_inconclusive` — `test_ac3_...` падает на
сравнении вызова мока.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from orchestrator import artifact_source, canary, config, store  # noqa: E402

# `canary.py` на момент написания тестов ещё НЕ импортирует `artifact_
# source` (требование 1 этой задачи добавляет `from . import artifact_
# source` в его секцию импортов — приём из fsm.py/fsm_advance.py,
# `artifact_source.resolve(...)`, см. SPEC «Материалы»). Патчим
# разделяемый объект модуля `orchestrator.artifact_source` напрямую —
# так подмена видна и до, и после того, как `canary.py` заведёт своё
# `from . import artifact_source` (тот же объект модуля, не копия).


AC_MARKED_SPEC = """---
task: T-AC1
type: spec
schema_version: 2
---

## Критерии приёмки

AC-1. Пример критерия приёмки.
"""

SKIP_TESTS_SPEC = """---
task: T-AC2
type: spec
schema_version: 2
skip_tests: причина пропуска тестов
---

## Критерии приёмки

AC-1. Пример критерия приёмки.
"""


class SpecGateNextStateReadsArtifactSourceTest(unittest.TestCase):
    """`canary._spec_gate_next_state` — источник SPEC для чтения foreign
    SPEC (SPEC, требование 1, AC-1/AC-2/AC-4)."""

    TASK = "T-AC1"
    ARTIFACT_BRANCH = "artifact/T-AC1"
    CODE_BRANCH = "task/t-ac1-x"

    def _t(self):
        return {"branch": self.CODE_BRANCH}

    def test_ac1_spec_only_on_artifact_branch_goes_to_tests_writing(self):
        """Задача, чей AC-размеченный SPEC (`schema_version: 2`, раздел
        «Критерии приёмки» с AC-n) лежит ТОЛЬКО на артефактной ветке —
        не на кодовой ветке задачи и не на диске
        `config.TASKS/<id>/SPEC.md` — уходит в `"tests_writing"`.

        Ловит мутацию: `_spec_gate_next_state` продолжает определять
        источник через `gitcmd.on_foreign_branch(t["branch"])` вместо
        `artifact_source.resolve(conn, task_id)` — тогда для кодовой
        ветки читается несуществующий диск (`artifacts.frontmatter`
        пустой словарь), и результат ошибочно — `"in_dev"`.
        """
        def fake_resolve(conn, task_id):
            self.assertEqual(task_id, self.TASK)
            return self.ARTIFACT_BRANCH, True

        def fake_show(branch, rel):
            # Кодовая ветка (ADR-0016) SPEC не несёт вовсе — только
            # артефактная ветка отдаёт AC-размеченный текст.
            if branch == self.ARTIFACT_BRANCH:
                self.assertEqual(rel, f"tasks/{self.TASK}/SPEC.md")
                return AC_MARKED_SPEC, ""
            return None, "SPEC.md отсутствует на этой ветке"

        with mock.patch.object(artifact_source, "resolve",
                              side_effect=fake_resolve), \
             mock.patch.object(canary.gitcmd, "show", side_effect=fake_show), \
             mock.patch.object(canary.artifacts, "frontmatter",
                               return_value={}):
            result = canary._spec_gate_next_state(None, self.TASK, self._t())

        self.assertEqual(result, "tests_writing")

    def test_ac2_skip_tests_on_artifact_branch_goes_to_in_dev(self):
        """SPEC на артефактной ветке несёт `skip_tests: <причина>` —
        `_spec_gate_next_state` возвращает `"in_dev"`, tests_writing
        осознанно пропущен по явному указанию SPEC.

        Ловит мутацию: реализация перестаёт передавать поле
        `skip_tests` дальше в `guard.requires_ac_markup` (например,
        собирает `meta` только из `schema_version`, теряя остальные
        поля frontmatter) — задача со `skip_tests` ошибочно ушла бы в
        `"tests_writing"`. Диск и «чужая» ветка намеренно замоканы на
        AC-размеченный SPEC БЕЗ `skip_tests`: если реализация всё ещё
        игнорирует `artifact_source.resolve` (старый путь через
        `gitcmd.on_foreign_branch(t["branch"])`), она попадёт на один
        из этих двух источников и ошибочно даст `"tests_writing"` —
        без этого старый код случайно совпал бы с ожидаемым `"in_dev"`
        по не найденному на диске файлу, не проверяя вообще ничего.
        """
        def fake_resolve(conn, task_id):
            return self.ARTIFACT_BRANCH, True

        def fake_show(branch, rel):
            if branch == self.ARTIFACT_BRANCH:
                return SKIP_TESTS_SPEC, ""
            return AC_MARKED_SPEC, ""

        with mock.patch.object(artifact_source, "resolve",
                              side_effect=fake_resolve), \
             mock.patch.object(canary.gitcmd, "show", side_effect=fake_show), \
             mock.patch.object(canary.artifacts, "frontmatter",
                               return_value={"schema_version": 2}):
            result = canary._spec_gate_next_state(None, self.TASK, self._t())

        self.assertEqual(result, "in_dev")

    def test_ac4_does_not_call_on_foreign_branch(self):
        """Источник SPEC для чтения foreign-ветки определяется
        исключительно через `artifact_source.resolve(conn, task_id)` —
        `gitcmd.on_foreign_branch(t["branch"])` в `_spec_gate_next_state`
        не вызывается вовсе, даже если его результат не влияет на исход.

        Ловит мутацию: реализация оставляет старую проверку
        `gitcmd.on_foreign_branch(branch)` рядом с новой логикой (как
        «дополнительную подстраховку», не влияющую на возвращаемое
        значение) — вызов зафиксирован, `assert_not_called` падает.
        """
        with mock.patch.object(artifact_source, "resolve",
                              return_value=(self.ARTIFACT_BRANCH, True)), \
             mock.patch.object(canary.gitcmd, "show",
                               return_value=(AC_MARKED_SPEC, "")), \
             mock.patch.object(canary.gitcmd, "on_foreign_branch") as on_foreign:
            canary._spec_gate_next_state(None, self.TASK, self._t())

        on_foreign.assert_not_called()


class PassSpecGateNotFoundKillsInconclusiveTest(unittest.TestCase):
    """`canary._pass_spec_gate` — SPEC не найден ни в одном источнике
    (SPEC, требование 2, AC-3)."""

    TASK = "T-AC3"
    ARTIFACT_BRANCH = "artifact/T-AC3"
    CODE_BRANCH = "task/t-ac3-x"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for attr, value in (("ROOT", root),
                            ("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        store.create_schema(store.db())
        self.conn = store.db()
        store.insert_task(self.conn, self.TASK, "Канареечная задача",
                          "spec_gate", self.CODE_BRANCH,
                          config.DEFAULT_TARGET, 50.0, is_canary=True)

        patcher = mock.patch.object(artifact_source, "resolve",
                                    return_value=(self.ARTIFACT_BRANCH, True))
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(canary.gitcmd, "show",
                                    return_value=(None, "путь не найден на ветке"))
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(canary.artifacts, "frontmatter",
                                    return_value={})
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(canary, "_kill_inconclusive")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_ac3_spec_not_found_kills_inconclusive_not_in_dev(self):
        """SPEC недоступен ни на артефактной ветке (`gitcmd.show` не
        нашёл файл), ни на диске (`artifacts.frontmatter` — пустой
        словарь, файла нет) — `_pass_spec_gate` НЕ переводит задачу в
        `in_dev`: вызывает `_kill_inconclusive` с именованной причиной
        «canary: SPEC не найден в источнике артефактов (<ветка>)».

        Ловит мутацию: `_pass_spec_gate` продолжает трактовать «SPEC не
        найден» как «SPEC без AC-разметки» (поведение до этой задачи) —
        задача уходит в `in_dev` через `store.set_state`, `_kill_
        inconclusive` не вызывается вовсе.
        """
        canary._pass_spec_gate(self.conn, self.TASK)

        canary._kill_inconclusive.assert_called_once_with(
            self.conn, self.TASK,
            f"canary: SPEC не найден в источнике артефактов "
            f"({self.ARTIFACT_BRANCH})")
        t = store.get_task(self.conn, self.TASK)
        self.assertEqual(t["state"], "spec_gate")


# AC-7: manual — «tests/test_canary.py содержит тесты на AC-2, AC-3 и
# AC-5» описывает СОДЕРЖИМОЕ будущего коммита разработчика в файле вне
# зоны test_author (`tests/`, зона задачи из фронтматтера — зона
# разработчика). Поведение AC-2/AC-3/AC-5 уже проверено выше и в
# test_canary_report_and_regression.py напрямую против
# `orchestrator/canary.py` — по-настоящему красными тестами сейчас и
# зелёными после реализации. Смоделировать содержательную (не
# тавтологичную) проверку «эти же тесты добавлены ИМЕННО в tests/
# test_canary.py» детерминированным тестом здесь означало бы либо
# угадывать ещё не написанную структуру кода разработчика (текстовый
# грep по несуществующим именам методов — тавтология, ловится любым
# именем), либо мутационно тестировать целиком tests/test_canary.py по
# трём независимым сценариям сразу — что для AC-2/AC-3 требует той же
# догадки о ещё не выбранной форме реализации. Факт размещения тестов
# именно в tests/test_canary.py — предметная проверка ревьювером диффа
# на приёмке (аналогично AC-8 ниже).
# AC-8: manual — «тесты tests/test_canary.py, существовавшие до этой
# задачи, проходят без правок в сторону смягчения» — сравнение СИЛЫ
# утверждений старого и нового текста теста (не удалён ли assert, не
# заменён ли строгий на слабый) — человеческий вердикт по существу
# диффа, не решается прогоном (прогон видит только «упал/прошёл», не
# «стал слабее»). Полный прогон `tests/test_canary.py` без правок в
# сторону смягчения при этом гоняет CI на каждый коммит — эта планка
# ловит УДАЛЕНИЕ/ПОЛОМКУ существующего теста как красноту, но не
# «смягчение» формулировки внутри живого теста; вторую половину
# проверяет ревьювер на диффе.
