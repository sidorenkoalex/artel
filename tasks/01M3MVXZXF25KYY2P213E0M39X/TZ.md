---
task: 01M3MVXZXF25KYY2P213E0M39X
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Защищённые пути: настройки сбора тестов (conftest.py, pyproject.toml и родственные)

# ТЗ: Защищённые пути — настройки сбора тестов (conftest.py, pyproject.toml и родственные)

Источник: решение Оператора 28.09.2026 по итогам ревью схемы записи
приёмочных тестов в `tests/` (строка бэклога 28.09, приоритет 2); ревью
лучших практик: подмена окружения pytest (conftest, настройки, плагины) —
известный способ обойти фиксацию тестов, описанный в исследованиях
агентных бенчмарков (SWE-bench, ImpossibleBench).

Факты (origin/main a588e172):
- `orchestrator/config.py::PROTECTED_PATHS` — 12 записей: `gates.yaml`,
  `roles.yaml`, `.github/`, `templates/`, `skills/`, `docs/invariants.md`,
  `tests/test_invariants.py`, `docs/adr/`, `CLAUDE.md`, `AGENTS.md`,
  `targets.yaml`, `models.yaml`. Корневых `conftest.py` и `pyproject.toml`
  среди них нет.
- Корневой `conftest.py` — сам гейт: отказывает роли конвейера в сборе
  всего дерева тестов (признак роли `ARTEL_ROLE`, SPEC
  01M2B6K3EM7F2J72RC2F520Y2K). Правка этого файла ролью снимает гейт без
  следа в гейте защищённых путей.
- `pyproject.toml` несёт настройки pytest (проверить раздел
  `[tool.pytest.ini_options]` и прочие; SPEC называет, что там есть);
  `pytest.ini`, `setup.cfg`, `tox.ini`, `tests/conftest.py` в репозитории
  на 28.09 отсутствуют.
- Правка защищённого пути ролью возможна только приложением к PLAN,
  которое пульт применяет на мерже (`orchestrator/fsm_merge_gate.py`,
  перечень префиксов полного прогона `_FULL_SUITE_APPENDIX_PREFIXES`).
- Проверки защищённых путей: гейт диффа (`orchestrator/gates.py`,
  `fsm_merge_gate._protected_path_diff_gate`), CI
  (`tests/test_ci_protected_paths.py`), гейт зон
  (`tests/test_zones_gate.py`, `tests/test_protected_paths_gate.py`).

Требуется:
1. Защищёнными становятся: корневой `conftest.py`, файл `conftest.py` в
   любом каталоге репозитория, корневые `pyproject.toml`, `pytest.ini`,
   `setup.cfg`, `tox.ini`. SPEC решает и обосновывает, как перечень
   выражает «`conftest.py` в любом каталоге» (сегодня записи — префиксы
   пути) и нужно ли для этого расширить сравнение пути, не меняя смысла
   существующих записей.
2. Гейт диффа защищённых путей, гейт зон и проверка CI отказывают правке
   этих файлов ролью так же, как правке остальных защищённых путей; правка
   приложением к PLAN применяется на мерже; приложения к этим файлам
   требуют полного прогона `tests/` в цикле мержа (как приложения к
   `tests/` и `.github/`) — SPEC называет, где это задаётся.
3. Существующее поведение для остальных 12 записей не меняется.
4. `docs/stack.md` (раздел о защищённых путях или правках Оператора, SPEC
   находит) — одна строка: настройки сбора тестов защищены, и почему.
5. Тесты (`tests/`): правка каждого нового пути в диффе ветки — отказ
   гейта защищённых путей; вложенный `tests/sub/conftest.py` — тоже отказ;
   файл с похожим именем, не являющийся настройкой (`tests/test_conftest_x.py`,
   `docs/pyproject.md`), — не отказ; приложение к `conftest.py`
   запускает полный прогон на мерже. Корень и пути — через помощники
   `tests/sandbox.py`.

Зоны: orchestrator/config.py, orchestrator/gates.py, orchestrator/fsm_merge_gate.py, docs/stack.md, tests/.

Приложением: tests/test_invariants.py (только если инвариант перечня защищённых путей сверяет состав перечня литералом — SPEC проверяет и называет).

Только чтение (не менять): conftest.py, pyproject.toml, .github/,
orchestrator/advance_gates/, scripts/guard.py, docs/invariants.md,
docs/adr/, skills/, templates/, docs/backlog.md.

Не входит: правка содержимого `conftest.py` и `pyproject.toml`; защита
настроек других инструментов (линтеры, форматеры); запись приёмочных
тестов в `tests/` (отдельные задачи по ADR-0020).

Рамка: $30.
