"""AC-6, AC-7 — где признаки требования 3 НЕ отказывают: разовый файл с
теми же признаками и долгоживущий файл, законно пользующийся
`tests.sandbox`, `patch` публичного имени и `self._x`.

Каждый метод несёт контроль: тот же набор строк в долгоживущем файле
(AC-6) либо та же фикстура с одной закрытой строкой (AC-7) переход
отклоняет — иначе «отказа нет» доказывало бы лишь отсутствие проверки.

Группа: разовый
Красен до реализации: контроль каждого метода требует отказа по признаку требования 3, а статической проверки на выходе из `tests_writing` ещё нет — контрольный сценарий уходит в `in_dev`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402

# Девять признаков требования 3 — по одной строке каждого. Имя с
# идентификатором задачи дописывается в сценарии (он известен только
# после `setUp`).
ALL_SIGNS_HEAD = [
    'NOTE = "каталог tasks/ пульта"',
    "from orchestrator import gitcmd  # noqa: F401",
    'sys.path.insert(0, "/nonexistent")',
    "import _sandbox  # noqa: F401",
    "from orchestrator.fsm import _tests_writing_ac_state  # noqa: F401",
]
ALL_SIGNS_BODY = [
    'subprocess.run(["git", "status"], check=False)',
    'mock.patch("orchestrator.fsm._origin_main_sha")',
    'mock.patch.object(fsm, "_origin_main_sha")',
    "value = store._private_value",
]

# Законные обращения долгоживущего файла (AC-7).
SANDBOX_HEAD = [
    "from tests import sandbox as sandbox_mod  # noqa: F401",
    "from tests.sandbox import capture, _REPO_ROOT  # noqa: F401",
]
SANDBOX_BODY = [
    "self._value = 1",
    "root = sandbox_mod._REPO_ROOT",
    "helper = sandbox_mod.capture",
    'mock.patch("orchestrator.fsm.cmd_advance")',
    'mock.patch.object(fsm, "cmd_advance")',
]


class ExemptionsTest(_sandbox.GroupPlankSandbox):

    def test_ac6_once_file_with_all_signs_is_not_refused(self):
        """Разовый файл с литералом `tasks/`, импортом `gitcmd`, вызовом
        git через `subprocess`, идентификатором задачи, `sys.path.insert`,
        `import _sandbox`, закрытым именем из `orchestrator`, `patch`
        закрытого и `store._private_value` — переход проходит в `in_dev`;
        тот же набор в долгоживущем файле — отклонён (контроль).

        Ловит мутацию: проверку признаков применяют ко всем `test_*.py`,
        не глядя на строку группы, — разовый файл отклоняется, задача
        остаётся в `tests_writing`.
        """
        head = ALL_SIGNS_HEAD + [f'REF = "{self.TASK.lower()}"']
        self.assert_refused_naming(
            {"test_ac.py": _sandbox.plank_source(
                group=_sandbox.GROUP_LONG, head=head, body=ALL_SIGNS_BODY)},
            "test_ac.py", why="контроль: долгоживущий файл с признаками")
        self.assert_passes(
            {"test_ac.py": _sandbox.plank_source(
                group=_sandbox.GROUP_ONCE, head=head, body=ALL_SIGNS_BODY)},
            why="разовый файл с признаками требования 3")

    def test_ac7_tests_sandbox_public_patch_and_self_attr_pass(self):
        """Долгоживущий файл импортирует `tests.sandbox` (модулем и именем
        `_REPO_ROOT` с подчёркиванием), читает `sandbox_mod._REPO_ROOT`,
        патчит публичное `orchestrator.fsm.cmd_advance` (строкой и
        `patch.object`), пишет `self._value` — переход проходит в
        `in_dev`; та же фикстура плюс `store._private_value` — отклонена
        (контроль).

        Ловит мутацию: исключение пакета `tests` из признаков 7–9 забыли,
        и `sandbox_mod._REPO_ROOT` (или `from tests.sandbox import
        _REPO_ROOT`) засчитан как «закрытый атрибут»/«закрытое имя» —
        законный файл отклоняется, задача остаётся в `tests_writing`.
        """
        self.assert_refused_naming(
            {"test_ac.py": _sandbox.plank_source(
                head=SANDBOX_HEAD,
                body=SANDBOX_BODY + ["value = store._private_value"])},
            "test_ac.py", why="контроль: закрытый атрибут рядом с законными")
        self.assert_passes(
            {"test_ac.py": _sandbox.plank_source(
                head=SANDBOX_HEAD, body=SANDBOX_BODY)},
            why="tests.sandbox, patch публичного имени и self._x")


if __name__ == "__main__":
    unittest.main()
