"""AC-2 (tasks/T069/SPEC.md): `isolation-smoke` красный при утечке
MCP-вектора и зелёный на текущей конфигурации; существующие проверки
смоука не ослаблены.

SPEC, требование 2, называет расширяемую функцию по имени
(`orchestrator/doctor.py: isolation_smoke`) и её уровень: «офлайн-сборка
cmd/env шага, без реального запуска claude (тот же приём, что уже
применён к --setting-sources)» — а этот приём (см. текущий код
`isolation_smoke`, ветка `--setting-sources`) не строит `cmd` заново, а
читает готовую константу (`config.AGENT_SETTING_SOURCES`), которая и
формирует реальный флаг в `runner.run_agent_once`. Какую константу/
механизм заведёт разработчик для MCP-вектора — решение PLAN (SPEC не
называет имя), поэтому этот тест, как и его T058-прецедент
(`tasks/T058/acceptance_tests/test_ac3_isolation_smoke_marker.py`,
докстринг «не переоткрывает внутреннее устройство новой проверки»), не
мокает и не угадывает внутренний атрибут — он утверждает то единственное,
что гарантирует сам контракт `Check` независимо от механизма: раз новый
маркер существует и реально проверяет MCP-вектор (а не просто ничего не
делает), его подтверждение обязано попасть в текст `detail` итогового
`ok` — по тому же образцу, что уже несут существующие маркеры
(«project-/local-хуки исключены из resolve-сурсов шага» — сегодняшний
текст `isolation_smoke`, `orchestrator/doctor.py`). Сегодня (до
реализации T069) в этом тексте нет ни слова про MCP — тест закономерно
красный по этой причине (marker ещё не существует), не по случайной.

Дискриминирующую половину критерия («красный при утечке») в T058-прецеденте
несёт ОТДЕЛЬНАЯ пара живых тестов (`test_ac1_ac2_role_hook_isolation.py`),
а не `isolation_smoke()` сама по себе — здесь она устроена иначе: T069
AC-2 явно требует красноты/зелени от самой `isolation_smoke()`, но белый-
ящик мутационный тест на конкретный, ещё не выбранный атрибут (по
прецеденту `tests/test_doctor.py::
test_project_hook_setting_source_leak_is_caught`, мокающему
`doctor.config.AGENT_SETTING_SOURCES`) риск ложной красноты «по
неправильной причине» (`AttributeError` на угаданное developer'ом имя,
skills/test-authoring.md, «Краснота — объяснённая, не по умолчанию»,
прецеденты T051/T041/T059/T060) — такой мутационный тест на выбранный
разработчиком механизм пишет сам разработчик в `tests/test_doctor.py`
(тот же приём, что T058: `test_project_hook_setting_source_leak_is_caught`
появился там, а не в приёмочных тестах). Полный набор `tests/`, включая
эту мутацию, зелёный проверяет AC-4.

Красен до реализации:
`test_ac2_isolation_smoke_ok_detail_names_the_mcp_marker` — сегодняшний
`detail` `isolation_smoke()` не содержит подстроки "mcp" (проверено
прогоном перед написанием этого докстринга); маркер MCP-вектора ещё не
добавлен.
"""
import shutil
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import doctor  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402


class IsolationSmokeMcpMarkerTest(TmpRootTest):
    """`isolation_smoke()` читает промпт роли из `config.ROOT / "skills"`
    — без копии `skills/` в песочницу проверка падает ещё до маркера MCP
    (тот же минимум, что и в T058-прецеденте и в
    `tests/test_doctor.py::_DoctorTmpRootTest.setUp`)."""

    def setUp(self):
        super().setUp()
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills")

    def test_ac2_isolation_smoke_ok_detail_names_the_mcp_marker(self):
        check = doctor.isolation_smoke()

        self.assertEqual(
            check.status, "ok",
            f"isolation_smoke сообщил не-ok в заведомо здоровой "
            f"конфигурации после ожидаемого расширения маркером "
            f"MCP-вектора (SPEC T069 AC-2): {check.detail}")
        self.assertIn(
            "mcp", check.detail.lower(),
            "isolation_smoke() не подтверждает проверку MCP-вектора в "
            "своём итоговом detail — маркер MCP-вектора (SPEC T069, "
            "требование 2, «по аналогии с уже реализованными... "
            "маркерами») ещё не добавлен в isolation_smoke "
            f"(SPEC T069 AC-2); текущий detail: {check.detail!r}")


if __name__ == "__main__":
    unittest.main()
