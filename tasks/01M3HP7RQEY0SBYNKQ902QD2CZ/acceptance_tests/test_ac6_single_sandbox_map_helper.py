"""AC-6: карту исполнителей и локальный слой моделей тесты из AC-3 берут из
ЕДИНСТВЕННОГО помощника песочницы; второго помощника того же назначения в
`tests/` нет.

«Помощник того же назначения» разбирается так: файл `tests/`, который сам
ЧИТАЕТ содержимое боевой карты (`<адрес карты>.read_text()`/`open(<адрес
карты>)`) и при этом импортируется другим файлом `tests/`, — то есть
раздаёт карту не только себе. Чтение карты ради собственного сценария
помощником не делает: `tests/test_yaml_parsing.py::test_the_real_roles_
file_parses` разбирает боевой файл потому, что боевой файл и есть его
предмет, и AC-2 оставляет такие тесты на месте.

Локальный слой моделей: фикстура выдаётся ПРИСВАИВАНИЕМ `config.
MODELS_LOCAL` — им слой уводится из рабочей конфигурации Оператора во
временный каталог процесса. Запись содержимого в уже выданный слой
(`config.MODELS_LOCAL.write_text(...)`) — сценарий отдельного теста, а не
второй помощник, и под правило не подпадает.

Первый метод от PLAN.md не зависит вовсе; второй сверяет с PLAN.md
перечень тестов AC-3.

Красен до реализации: `tests/test_runner_role_model.py` читает боевой
`roles.yaml` сам (строка 33, `_REAL_ROLES_TEXT`) и раздаёт производные от
него карты четырём файлам `tests/` (`test_providers.py`,
`test_runner_model_preflight.py`, `test_stack_optional_tools.py`,
`test_stack_roles_tier_spread.py`) — это и есть второй помощник того же
назначения.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402


class SingleMapHelperTest(unittest.TestCase):
    """Кто в `tests/` раздаёт карту исполнителей и локальный слой."""

    def sources(self) -> dict:
        return {rel: (_util.text_on_disk(rel) or "")
                for rel in _util.tests_py_files()}

    def test_ac6_no_second_map_helper_lives_in_tests(self):
        """Ни один файл `tests/`, кроме `tests/sandbox.py`, не читает
        боевую карту и не раздаёт её другим файлам `tests/`; локальный слой
        моделей выдаётся присваиванием `config.MODELS_LOCAL` ровно в одном
        файле — той же песочнице.

        Ловит мутацию: общий помощник заведён в `tests/sandbox.py`, но
        прежний источник карты в `tests/test_runner_role_model.py` оставлен
        на месте «для совместимости» и по-прежнему импортируется соседями —
        источников снова два, и на следующей правке они разойдутся ровно
        так, как разошлась собственная карта `tests/test_models_doctor.py`
        (раздел «Контекст» SPEC: о ней не знает ни один помощник).
        """
        sources = self.sources()
        importers = {}
        for rel, source in sources.items():
            for module in _util.tests_module_imports(source):
                importers.setdefault(module, set()).add(rel)

        second = {}
        for rel, source in sources.items():
            if rel == _util.SANDBOX or not _util.map_read_sites(source):
                continue
            users = sorted(importers.get(_util.module_name(rel), set()) - {rel})
            if users:
                second[rel] = users
        self.assertEqual(
            second, {},
            f"боевую карту читает и раздаёт соседям не только "
            f"{_util.SANDBOX}: {second} — AC-6 требует ОДНОГО помощника")

        layer_owners = sorted(
            rel for rel, source in sources.items()
            if _util.models_local_assignments(source))
        self.assertEqual(
            layer_owners, [_util.SANDBOX],
            f"локальный слой моделей как фикстуру процесса выдаёт не только "
            f"{_util.SANDBOX}: {layer_owners}")

    def test_ac6_ac3_tests_do_not_read_the_real_map_themselves(self):
        """Ни один файл из перечня AC-3 (тесты, чей предмет не карта ролей)
        не читает боевую карту сам — карту он получает от песочницы.

        Ловит мутацию: класс закрыт по одному файлу — песочница отдаёт
        фикстуру, но файл, чей предмет не карта, продолжает строить свою
        карту из боевого текста (`(REPO_ROOT / "roles.yaml").read_text()`).
        Такой файл остаётся чувствительным к составу ролей и к ярусам, и
        SPEC (обоснование требования 3) называет это прямо: правка по
        одному файлу оставляет класс открытым и заставляет платить за него
        четвёртый раз.
        """
        sources = self.sources()
        guilty = {}
        for rel in _util.ac3_targets():
            lines = _util.map_read_sites(sources.get(rel, ""))
            if lines:
                guilty[rel] = lines
        self.assertEqual(
            guilty, {},
            f"эти тесты из перечня AC-3 читают боевую карту сами (файл: "
            f"строки): {guilty} — карту им обязана выдавать песочница "
            f"{_util.SANDBOX}")


if __name__ == "__main__":
    unittest.main()
