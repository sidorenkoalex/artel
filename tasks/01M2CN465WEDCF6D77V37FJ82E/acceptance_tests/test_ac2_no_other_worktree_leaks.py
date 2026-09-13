"""AC-2 — 01M2CN465WEDCF6D77V37FJ82E: прочие классы `tests/` с
собственным `PATCHED_ATTRS` не оставляют `config.WORKTREES` незапатченным
там, где их код реально дотягивается до настоящей записи.

Источник — SPEC.md, «Критерии приёмки»:

AC-2. Ни один класс в `tests/`, задающий собственный `PATCHED_ATTRS`
(кроме `_GitFixationTmpRootTest`, покрытого AC-1), не оставляет
`config.WORKTREES`/`config.BACKUP_MARKER` незапатченными в ситуации, где
код этого класса реально пишет по этим путям на настоящий корень (класс,
где сам механизм записи подменён отдельно — например, `workspace.ensure`
целиком заменён моком, как в `tests/test_multitarget.py:104` — утечкой
не считается).

Аудит на момент написания планки (см. `docs/audits/code-revision-
2026-09-13.md`, повторная проверка вручную по каждому классу с
собственным `PATCHED_ATTRS`): единственный класс, реально дотягивающийся
до записи по `config.WORKTREES` без патча, — `_GitFixationTmpRootTest`
(AC-1). Два класса из этого же списка отсутствие `"WORKTREES"` не
превращает в утечку по документированной причине:

- `tests.test_multitarget._MultitargetTmpRootTest` — `runner.workspace.
  ensure` целиком заменён `mock.patch.object` в `setUp` (строка ~134),
  поэтому `workspace.path`/`config.WORKTREES` не участвуют в вызове
  вовсе — ровно пример из формулировки AC-2 выше.
- `tests.test_doctor._RoleHomeReferenceTmpRootTest` — сужает `TmpRootTest`
  до `ROLE_HOME`/`ROLE_CONFIG_DIR`; все тесты-потомки вызывают только
  `doctor.check_role_home_reference()`, который не читает и не пишет
  `config.WORKTREES` ни прямо, ни через `workspace`/`auto`/`catalog`.

Ни один из прочих классов с собственным `PATCHED_ATTRS` не пишет
`config.BACKUP_MARKER` в обход патча: единственное место, реально
делающее `config.BACKUP_MARKER.write_text(...)` в `tests/`
(`tests/test_doctor.py::_DoctorTmpRootTest.touch_backup`), объявлено на
классе, наследующем ПОЛНЫЙ набор `tests.sandbox.ALL_CONFIG_ATTRS` по
умолчанию (не сужает `PATCHED_ATTRS`), поэтому `BACKUP_MARKER` уже
патчится.

Тест ниже пин(ует) этот вывод аудита машиной: он не может обойти всё
пространство будущих правок (как и любой тест), но ловит ИМЕННО класс
регрессии из SPEC «Контекст» — новый или существующий класс `tests/`
получает собственный `PATCHED_ATTRS` без `WORKTREES`, не входя в
документированный список исключений выше.

Зелёный с рождения: AC-2 говорит о ПРОЧИХ классах `tests/` (кроме
`_GitFixationTmpRootTest`, покрытого отдельно AC-1) — по аудиту
`docs/audits/code-revision-2026-09-13.md`, зафиксированному в докстринге
выше, ни один из них сегодня не оставляет `WORKTREES`/`BACKUP_MARKER`
незапатченным без документированного обоснования (мок `workspace.ensure`
у `_MultitargetTmpRootTest`, отсутствие записи по этим путям у
`_RoleHomeReferenceTmpRootTest`). Правка AC-1 меняет только
`_GitFixationTmpRootTest`, который эти тесты явно исключают через
`_COVERED_BY_AC1` — фикс разработчика не может ни покрасить, ни
починить их: они проверяют инвариант, который уже держится сегодня, и
останутся зелёными до и после реализации задачи.
"""
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402

# Документированные исключения (см. докстринг модуля) — класс не должен
# появляться здесь без обоснования того же уровня, что и два примера выше.
_WORKTREES_EXEMPT = {
    ("tests.test_multitarget", "_MultitargetTmpRootTest"),
    ("tests.test_doctor", "_RoleHomeReferenceTmpRootTest"),
}

# `_GitFixationTmpRootTest` — территория AC-1, отдельная планка.
_COVERED_BY_AC1 = {
    ("tests.test_git_fixation", "_GitFixationTmpRootTest"),
}

_BACKUP_MARKER_WRITE_RE = re.compile(
    r"BACKUP_MARKER[^\n]{0,40}\.(write_text|write_bytes|mkdir|touch)\(")


class NoOtherPatchedAttrsLeakTest(unittest.TestCase):

    def test_ac2_custom_patched_attrs_classes_cover_worktrees_or_are_exempt(self):
        """Каждый класс `tests/` с собственным (не унаследованным)
        `PATCHED_ATTRS`, кроме `_GitFixationTmpRootTest` (AC-1), либо
        включает `"WORKTREES"`, либо входит в документированный список
        исключений выше.

        Ловит мутацию: кто-то заводит новый (или правит существующий,
        кроме двух исключений) класс с сужённым `PATCHED_ATTRS`, не
        включающим `"WORKTREES"`, и не мокает `workspace.ensure`/не
        обосновывает отсутствие пути к записи — ровно тот класс
        регрессии, что коммит d692f2a6 внёс для
        `_GitFixationTmpRootTest` (SPEC «Контекст»).
        """
        offenders = []
        for modname, clsname, cls in _util.discover_custom_patched_attrs_classes():
            key = (modname, clsname)
            if key in _COVERED_BY_AC1 or key in _WORKTREES_EXEMPT:
                continue
            if "WORKTREES" not in cls.PATCHED_ATTRS:
                offenders.append(f"{modname}.{clsname}: {cls.PATCHED_ATTRS!r}")
        self.assertEqual(
            [], offenders,
            "класс(ы) с собственным PATCHED_ATTRS не патчат WORKTREES и "
            "не занесены в документированный список исключений: "
            + "; ".join(offenders))

    def test_ac2_custom_patched_attrs_classes_patch_backup_marker_if_they_write_it(self):
        """Любой класс `tests/` с собственным `PATCHED_ATTRS`, чьё СОБСТВЕННОЕ
        тело (свои методы, не тела других классов того же модуля) реально
        делает `config.BACKUP_MARKER.write_text(...)`/`.mkdir(...)`, обязан
        включать `"BACKUP_MARKER"` в `PATCHED_ATTRS`.

        Ловит мутацию: в класс с сужённым `PATCHED_ATTRS` добавляют
        реальную запись `config.BACKUP_MARKER` внутри его СОБСТВЕННОГО
        метода (по образцу `tests/test_doctor.py::_DoctorTmpRootTest.
        touch_backup`, который сам патчит `BACKUP_MARKER` через дефолтный
        полный `PATCHED_ATTRS` и потому не офендер), не добавив
        `"BACKUP_MARKER"` в кортеж, — тест обязан покраснеть. Проверка
        нарочно ограничена ТЕЛОМ САМОГО КЛАССА (`inspect.getsource(cls)`),
        а не всем модулем: `test_doctor.py` несёт `touch_backup` на
        СОСЕДНЕМ классе `_DoctorTmpRootTest` (не предке
        `_RoleHomeReferenceTmpRootTest`) — поиск по всему модулю ложно
        обвинил бы класс, который этот метод не наследует и не вызывает.
        """
        import inspect

        offenders = []
        for modname, clsname, cls in _util.discover_custom_patched_attrs_classes():
            key = (modname, clsname)
            if key in _COVERED_BY_AC1:
                continue
            if "BACKUP_MARKER" in cls.PATCHED_ATTRS:
                continue
            try:
                class_source = inspect.getsource(cls)
            except (OSError, TypeError):
                class_source = ""
            if _BACKUP_MARKER_WRITE_RE.search(class_source):
                offenders.append(f"{modname}.{clsname}")
        self.assertEqual(
            [], offenders,
            "класс(ы) с собственным PATCHED_ATTRS без BACKUP_MARKER живут "
            "в модуле, реально пишущем config.BACKUP_MARKER: "
            + "; ".join(offenders))


class MultitargetWorkspaceEnsureExceptionStillHoldsTest(unittest.TestCase):
    """Функциональная проверка ОДНОГО из двух документированных исключений
    выше: `_MultitargetTmpRootTest` не нуждается в `WORKTREES`, ПОТОМУ ЧТО
    `runner.workspace.ensure` у него замокан целиком — если это условие
    перестанет выполняться, исключение из списка выше становится ложным, и
    класс должен либо получить `WORKTREES`, либо тест ниже должен
    покраснеть первым."""

    def test_ac2_multitarget_sandbox_still_mocks_workspace_ensure(self):
        """`_MultitargetTmpRootTest.setUp()` подменяет `runner.workspace.
        ensure` целиком.

        Ловит мутацию: кто-то убирает `mock.patch.object(runner.workspace,
        "ensure", ...)` из `setUp` этого класса (например, при рефакторинге
        песочницы) — `runner.workspace.ensure` после `setUp()` останется
        оригинальной функцией, и `assertIsNot` покраснеет, сигналя, что
        исключение AC-2 для этого класса больше не обосновано.
        """
        from orchestrator import runner
        from tests.test_multitarget import _MultitargetTmpRootTest

        original_ensure = runner.workspace.ensure
        # `_MultitargetTmpRootTest` — базовый класс песочницы, без
        # собственных test-методов (их несут только его подклассы) —
        # `unittest.TestCase.__init__` требует ИМЯ СУЩЕСТВУЮЩЕГО метода,
        # не обязательно тестового; `"setUp"` подходит и не запускается
        # сам по себе конструктором.
        instance = _MultitargetTmpRootTest("setUp")
        instance.setUp()
        try:
            self.assertIsNot(
                runner.workspace.ensure, original_ensure,
                "workspace.ensure должен быть замокан в setUp — иначе "
                "класс без WORKTREES в PATCHED_ATTRS реально пишет в "
                "настоящий config.WORKTREES")
        finally:
            instance.doCleanups()


if __name__ == "__main__":
    unittest.main()
