---
task: 01M59Z0FW1699SJQ2FA5Y76CZ3
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: G2а-2: выкладка планки компонента по `plank_layout` и `plank-run` по правилу планки

# G2а-2: выкладка планки компонента по `plank_layout` и `plank-run` по правилу планки

## Факты

Вторая половина G2а волны G по ADR-0026 (`docs/adr/0026-project-components-and-outcome-gates.md`, принят 19.10.2026; «Решение» п. 5 — «на базе прогоняются файлы планки из ветки (выкладка `plank_layout`)», «Порядок исполнения» — строка G2а). **Зависит от G2а-1:** правило планки уже построено функцией `project_profile.plank_rule(target)` (возвращает `guard.PlankRule`; принадлежность файла компоненту — `PlankRule.component_of(name)`, признак тестового файла — `PlankRule.is_test(name)`, маски `tests` компонента — `PlankRule.masks(component)`), а `Profile` несёт поля `tests` и `plank_layout`. Эта задача правило вызывает и не меняет.

- Выкладка сегодня — только у `pytest-own` под `long_lived_dir`: `orchestrator/acceptance.py:1172` (`PLANK_LAYOUT_DIR`), `orchestrator/acceptance.py:1176` (`PLANK_LAYOUT_EXCLUDE`), `orchestrator/acceptance.py:1187` (`_layout_mode`), `orchestrator/acceptance.py:1196` (`_layout_root`), `orchestrator/acceptance.py:1253` (`_plank_layout`); файлы кладутся в подкаталог `acceptance_tests` — `orchestrator/acceptance.py:1258` (`acceptance_tests`), `orchestrator/acceptance.py:1275` (`layout`). Профиль без `runner: pytest-own` (компонент `pult-vitest`) выкладки не получает, и планка гонится из `tasks/<id>/acceptance_tests` рабочей копии — вне `workdir` компонента.
- Места выкладки: `orchestrator/acceptance.py:1283` (`run`), `orchestrator/acceptance.py:1460` (`collect`), `orchestrator/acceptance.py:1951` (`run_plank`), уборка — `orchestrator/acceptance.py:1907` (`drop_from_code_copy`), при записи с несколькими компонентами уборка молча пропускается — `orchestrator/acceptance.py:1923` (`ComponentsPending`).
- Исключение остатка выкладки из полного набора pytest — `--ignore=<long_lived_dir>/.artel-plank`: прогон по отчёту — `_report_argv` (`orchestrator/acceptance.py:719`, флаг — в строках 752–754 того же файла), полный набор `pytest-own` — `orchestrator/acceptance.py:2307-2311` (`PLANK_LAYOUT_DIR`).
- Подмножество тестов `pult-vitest` передаётся раннеру через `select`: `orchestrator/acceptance.py:688` (`_subset_args`).
- Шаблон `plank_layout` запись проверяет лишь на `<id>` в любом сегменте: `orchestrator/targets.py:493-510` (`_template_path_error`); `plank_layout: frontend/src/<id>` с шаблоном исключения `frontend/src/` спрятал бы от чекпоинта новые файлы кода.
- `plank-run`: наличие тестов — `orchestrator/plank_run.py:61` (`_has_tests`, `test_*.py`), отказ «нет файлов test_*.py» — `orchestrator/plank_run.py:186` (`_has_tests`), выбор `[файл]` с `::узлом` — `orchestrator/plank_run.py:66-77` (`_selected`).

Требуется:

1. **Выкладка по `plank_layout`.** Правило с непустой причиной отказа построения (поле refusal объекта правила; например компонент `pult-vitest` без `tests`) — отказ подготовки прогона и `plank-run` с этим текстом, прогон не запускается, исход не зелёный. У профиля с полем `plank_layout` файлы планки его компонента (у правила по умолчанию — `rule.owns(name)`, иначе `rule.component_of(name) == profile.component`; общие файлы — `guard.SHARED_PLANK_FILE`, `.md`/`.txt` — в выкладку не кладутся; у компонента с командой pytest сверх них — помощник `_pult.py`, у прочих — нет) на время прогона копируются прямо в `<plank_layout>` рабочей копии кода (без подкаталога `acceptance_tests`); `<id>` — `task_id` как есть, как в `_layout_root`. Подготовка отказывает с текстом, прогон не запускается, исход не зелёный, если: `<id>` — не последний сегмент `plank_layout`; путь вне `workdir` компонента (пустой `workdir` — корень репозитория); в родителе `<id>` есть отслеживаемые git файлы (`git ls-files` не пуст). Шаблон в `info/exclude` клона — `/<родитель <id>>/` от корня, до записи файлов, тем же замком, что `_exclude_pattern`. Уборка — в `finally` и в `drop_from_code_copy`.
2. **Без `plank_layout`.** Компонент, чья команда не pytest (`acceptance.is_pytest_command`), с отчётом и без `plank_layout` — отказ подготовки «у компонента <имя> нет plank_layout — планку выложить некуда». `pytest-own` без `plank_layout` — прежняя выкладка под `long_lived_dir`, прежний `LAYOUT_OUTSIDE_NOTE`.
3. **Цели прогона.** Цели `run`, `collect`, `run_plank` — выложенные файлы компонента; у `pult-vitest` — через `select` (`_subset_args`). Файлов компонента в планке нет (только `.md`/`.txt`) — тот же исход, что «планка не заведена» у `run`/`collect`; у `plank-run` — прежний отказ с маской компонента.
4. **Исключение остатка выкладки.** У компонента с `plank_layout` и командой pytest — `--ignore=<plank_layout до <id>>` вместо `--ignore=<long_lived_dir>/.artel-plank` в `_report_argv` и в полном наборе `pytest-own`; у `pult-vitest` флага нет, остаток убирает `drop_from_code_copy`.
5. **`plank-run` по правилу.** Наличие тестов и выбор `[файл]` — по `plank_rule` проекта задачи (отказ «нет файлов test_*.py» у артели прежний; у компонента — с маской `tests` компонента); `[файл]::узел` у не-pytest компонента — отказ «узел :: у компонента <имя> не поддерживается; передай файл». Сводка итога («итог pytest: …») не меняется — сводки прогонов роли — G5.
6. **У артели (`pult-pytest`) и у записей `test_profile` (sled сегодня) выкладка, аргументы прогонов, тексты и вывод `plank-run` — прежние.** Аналитик перечисляет в SPEC тексты, закрепляемые тестами до правки: `LAYOUT_OUTSIDE_NOTE`, отказы `_exclude_pattern`, отказы `plank-run` («нет файлов test_*.py», «файла … нет в планке»), argv полного набора `pytest-own` с `--ignore`.
7. Тесты детерминированы, без сети и без Node: учебный проект с двумя компонентами (`junit-xml` на pytest и `pult-vitest` с подменённым раннером, пишущим заранее заданный отчёт) — выкладка каждого компонента, отказы п. 1–2, argv п. 4; сквозные `run`, `collect`, `plank-run` — на записи `components:` из одного компонента каждого вида.

Критерии приёмки:
- прогон планки `pult-vitest` идёт из `<plank_layout>` внутри `workdir`, выкладка не видна `git status` и убрана после красного, зелёного исхода и исключения;
- `plank_layout` вне `workdir`, с `<id>` не последним сегментом, с отслеживаемыми файлами в родителе и его отсутствие у не-pytest компонента — отказ с текстом, не зелёный;
- у компонента `junit-xml` на pytest с `plank_layout` полный набор получает `--ignore=<родитель <id>>`;
- `plank-run` у `pult-vitest` видит `*.test.jsx`, отказывает на `::узле`;
- у артели перечисленные в SPEC тексты, argv и исходы прежние.

Решения по умолчанию (аналитику не спрашивать): помощник `_pult.py` в выкладку не-pytest компонента не кладётся; настоящий сбор Vitest из каталога с точкой (`src/.artel-plank`) — проба этапа 2 плана, здесь не проверяется; `targets.py` не меняется — форма `plank_layout` проверяется при подготовке прогона; прогон планки из нескольких компонентов одним гейтом — не эта задача (запись с несколькими компонентами по-прежнему отказывает в `decide`).

Зоны: orchestrator/acceptance.py, orchestrator/plank_run.py, tests/

Только чтение: `targets.yaml`, `orchestrator/suite_run.py`, `orchestrator/suite_lock.py`, `orchestrator/advance_gates/test_integrity.py`, `orchestrator/targets.py`, `orchestrator/project_profile.py`, `scripts/guard.py`, `orchestrator/repo_context.py`, `orchestrator/fsm_advance.py`, `orchestrator/advance_gates/acceptance.py`, `orchestrator/advance_gates/tests_writing.py`, `orchestrator/amend.py`, `orchestrator/checkpoint.py`, `orchestrator/pull.py`, `orchestrator/pull_main.py`, `orchestrator/runner.py`, `orchestrator/fsm.py`, `orchestrator/notes.py`, `orchestrator/stack.py`, `orchestrator/artel.py`, `orchestrator/reporters/`, `docs/adr/0026-project-components-and-outcome-gates.md`, `docs/backlog.md`. Правка вне зон — эскалация до SPEC.

Не входит: запрет автогейта приёмки для правила не по умолчанию (`fsm_autogate._plank_rule_refusal`, G2а-1) сохраняется до G2б — честного `FAIL_TO_PASS`; его текст со ссылкой на G2а-2 правит G2б; правило планки, трассируемость, чекпоинт, `preflight`, `amend-tests`, сухой прогон приёмки, автогейт, документы перед мержем (G2а-1); снятие отказа задачам записи с несколькими компонентами (`MULTI_COMPONENT_PENDING`); долгоживущие файлы по компоненту, честный `FAIL_TO_PASS`, импорты относительно выкладки в задании test_author (G2б); сводки прогонов (G5).

Рамка: $35. Набор моделей — по умолчанию.
