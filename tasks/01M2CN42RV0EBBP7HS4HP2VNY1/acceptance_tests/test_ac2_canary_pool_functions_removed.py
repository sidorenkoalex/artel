"""AC-2 задачи 01M2CN42RV0EBBP7HS4HP2VNY1: в `orchestrator/canary.py`
тринадцати перенесённых имён (требование 1) больше нет; модуль
импортирует из `pool_seal` только то, что использует (минимум
`_pool_dir`, нужную `cmd_canary`); импорты `hashlib`, `hmac`, `struct`,
`uuid`, `keychain` остаются в `canary.py` только если хотя бы одно
использование каждого из них сохранилось вне перенесённого диапазона.

На коммите-базе задачи (`_helpers.BASE_COMMIT`) все обращения к
`hashlib`/`hmac`/`struct`/`uuid`/`keychain` в `canary.py` лежат внутри
диапазона :181-462 (перенесённого целиком) — ни одного использования
вне этого диапазона нет (проверено вручную при написании планки), то
есть в ЭТОЙ задаче условное «если использование сохранилось» не
выполняется ни для одного из пяти имён: все пять обязаны исчезнуть из
`canary.py` целиком.

Красен до реализации: `canary.py` всё ещё определяет все 13 функций и
несёт все пять импортов — `assertFalse(leftover)` из первых двух тестов
упадёт на непустом множестве.
"""
import ast
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _helpers import POOL_SEAL_NAMES, REPO_ROOT  # noqa: E402

sys.path.insert(0, str(REPO_ROOT))
from orchestrator import canary  # noqa: E402

CANARY_PATH = REPO_ROOT / "orchestrator" / "canary.py"
REMOVED_PLAIN_IMPORTS = ("hashlib", "hmac", "struct", "uuid")


class PoolFunctionsRemovedFromCanaryTest(unittest.TestCase):

    def test_ac2_thirteen_pool_names_no_longer_defined_in_canary(self):
        """Сценарий: разбираем `canary.py` через `ast`, собираем имена
        функций верхнего уровня, сверяем с множеством 13 перенесённых
        имён.

        Ловит мутацию: перенос скопировал функции в `pool_seal.py`, но
        забыл удалить оригиналы из `canary.py` («перенос» на деле стал
        дублированием) — пересечение множеств не пустое.
        """
        source = CANARY_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        defined = {n.name for n in tree.body
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        leftover = defined & set(POOL_SEAL_NAMES)
        self.assertFalse(leftover, f"canary.py всё ещё определяет {leftover}")

    def test_ac2_unused_stdlib_imports_are_dropped(self):
        """Сценарий: разбираем `canary.py`, собираем имена простых
        `import X` верхнего уровня, сверяем с четырьмя именами
        (`hashlib`, `hmac`, `struct`, `uuid`), использования которых на
        коммите-базе задачи целиком лежат в перенесённом диапазоне.

        Ловит мутацию: перенос убрал использования этих модулей из
        `canary.py`, но забыл убрать сами `import` — линтер бы это
        поймал, но AC-2 фиксирует это явно как приёмочное требование.
        """
        source = CANARY_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_names.update(a.asname or a.name for a in node.names)
        leftover = imported_names & set(REMOVED_PLAIN_IMPORTS)
        self.assertFalse(leftover, f"неиспользуемые импорты остались: {leftover}")

    def test_ac2_keychain_no_longer_imported_in_canary(self):
        """Сценарий: `keychain` попадал в `canary.py` через `from .
        import (..., keychain, ...)` — проверяем, что после переноса
        среди имён любого `from . import (...)` этого модуля
        `keychain` больше нет.

        Ловит мутацию: перенос убрал прямые вызовы `keychain.token(...)`
        из `canary.py`, но забыл убрать `keychain` из общего кортежа
        импорта пакета.
        """
        source = CANARY_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_from_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported_from_names.update(a.asname or a.name
                                           for a in node.names)
        self.assertNotIn("keychain", imported_from_names,
                         "keychain больше не используется в canary.py вне "
                         "перенесённого кода — импорт обязан исчезнуть")


class CanaryPoolDirIsLiveImportFromPoolSealTest(unittest.TestCase):

    def test_ac2_canary_pool_dir_is_the_same_object_as_pool_seal(self):
        """Сценарий: `_pool_dir` живёт в `pool_seal.py` (требование 1);
        `canary.py` обязана иметь то же самое имя в своём пространстве
        имён (используется в `cmd_canary`) как ИМПОРТ, не как
        независимую копию.

        Ловит мутацию: `canary.py` держит собственное определение
        `_pool_dir` (тело скопировано, а не импортировано через `from
        .pool_seal import _pool_dir`) — `assertIs` разойдётся, даже
        если обе функции по отдельности возвращают одинаковый путь.
        """
        from orchestrator import pool_seal
        self.assertTrue(
            hasattr(canary, "_pool_dir"),
            "orchestrator.canary._pool_dir отсутствует — cmd_canary не "
            "сможет найти каталог пула")
        self.assertIs(
            canary._pool_dir, pool_seal._pool_dir,
            "canary._pool_dir — не тот же объект, что pool_seal._pool_dir "
            "(похоже на скопированное, а не импортированное определение)")

    def test_ac2_cmd_canary_resolves_pool_dir_through_canary_local_name(self):
        """Сценарий: подменяем `canary._pool_dir` (имя, которым
        реально пользуется тело `cmd_canary`, читая свой собственный
        модульный глобал — `from .pool_seal import _pool_dir` даёт
        именно такую связку: патч на `pool_seal._pool_dir` НЕ долетел
        бы до уже импортированного в `canary` имени) на функцию,
        возвращающую заведомо несуществующий путь, и зовём `canary.
        cmd_canary` — она обязана взять именно этот путь.

        Ловит мутацию: `cmd_canary` перестаёт читать `_pool_dir` через
        имя модуля (например, кто-то захардкодил `Path.home() / config.
        CANARY_POOL_DIRNAME` прямо в `cmd_canary` вместо вызова
        функции) — патч не долетит, путь в сообщении об ошибке
        останется прежним (реальным `~/.artel-canary`), не фиктивным.
        """
        fake_dir = Path(tempfile.gettempdir()) / \
            "artel-canary-does-not-exist-ac2-01M2CN42RV0EBBP7HS4HP2VNY1"
        with mock.patch.object(canary, "_pool_dir", return_value=fake_dir):
            with self.assertRaises(SystemExit) as ctx:
                canary.cmd_canary(k=1)
        self.assertIn(str(fake_dir), str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
