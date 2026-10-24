---
task: 01M5NHXJA3X7C66XTJN4J3E25W
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: ADR-0027, часть Б — правила стиля pytest в скилах, инвариант общих фикстур, устойчивое подключение фикстур

## Фаза A: план
- Покрытие: таблица PLAN закрывает требования 1–6; шаги проверяемые (перенос приложений + `git apply --check`, прогон на дереве «ветка + приложения», guard).
- Подход согласован с конвенциями: защищённые пути (`conftest.py`, `skills/*`, `tests/test_invariants.py`, `docs/invariants.md`) меняются только приложениями, ветка их не трогает.
- «Влияние на систему» совпадает с фактом: `git diff --stat 16f9ab43...HEAD` — один файл, залоченный долгоживущий тест `tests/test_01m5nhxja3x7c66xtjn4j3e25w_shared_fixtures.py` (+254); кода, карты, существующих тестов ветка не меняет. Откат — revert мерж-коммита, описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Блоки ```diff PLAN 1–5 побайтно равны блокам 1–3 `TZ.md` и 1–2 SPEC «Приложения Оператора» (сравнение строк программой); 4-й блок ТЗ (заменённое Приложение 4) в PLAN не перенесён — верно. `git apply --check` каждого на 8417c85b — код 0. |
| 2 | OK | Новый файл `tests/test_01m5nhxja3x7c66xtjn4j3e25w_shared_fixtures.py`: функции модуля, `assert`, `parametrize` литералами, у каждой функции «Ловит мутацию:»; классов `TestCase` нет (`unittest` используется только как раннер инварианта). |
| 3 | OK | `test_ac2_…`: зеркало с копией `conftest.py` и `orchestrator` по симлинку, без `tests/`, `PYTHONPATH` только на каталог, без `ARTEL_ROLE`, `--collect-only` явного файла — код 0 и число собранных. |
| 4 | OK | `test_ac3_…`: файл под `tasks/<id>/acceptance_tests/` просит `tmp_root` без импорта, проверяет тип `TmpRootTest` и каталог `root`. |
| 5 | OK | `test_ac4_invariant_red_on_each_mutation` — шесть мутаций (0)–(5) AC-4 + `test_ac4_invariant_green_on_unmutated_copy`; запуск методов инварианта с подменой `PATH`. |
| 6 | OK | В `tests/` только новый файл; защищённых путей в diff ветки нет. |

## Замечания
Нет замечаний уровня blocker/major/minor.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved — приложения перенесены дословно и применяются на текущей базе; на дереве «ветка + Приложения 1–5» тесты задачи и инвариант 42 зелёные, сторожа проверены временными мутациями.

## Проверено исполнением
- Программная сверка: извлечены блоки ```diff из `TZ.md`, `SPEC.md`, `PLAN.md`; PLAN[1..5] == TZ[1..3] + SPEC[1..2] — True для всех пяти; `git apply --check -` каждого блока на чистом дереве (HEAD 8417c85b) — код 0.
- На дереве с наложенными Приложениями 1–5: `python3 -m pytest -p no:cacheprovider -q tests/test_01m5nhxja3x7c66xtjn4j3e25w_shared_fixtures.py tests/test_invariants.py::SharedFixturesWrapSandboxClassesInvariantTest` — 12 passed, 98 subtests passed.
- Временная мутация: откат только Приложения 1 (`conftest.py` с голым `find_spec`) — `test_ac2_collect_without_tests_package_exits_zero` красный (AssertionError на коде возврата).
- Временная мутация инварианта: `issubclass(...)` → `True` — красный ровно `test_ac4_invariant_red_on_each_mutation[foreign_class]`; проверка алиаса `set(node.name.split(".")) | {node.asname}` → `{node.name}` — красный ровно `[sandbox_imports_config_alias]`. Заявки «Ловит мутацию» подтверждены.
- После каждого прогона приложения сняты `git apply -R`, `git status --short` — чисто.
- `python3 …/artel.py plank-run 01M5NHXJA3X7C66XTJN4J3E25W` — `test_task_facts.py`: 3 passed, код выхода 0.
- CI головы 8417c85b — зелёный (16 проверок, по пакету).

## Предложения системе
- Планка задачи (`acceptance_tests/test_task_facts.py`) написана в стиле unittest-импортов, хотя задача вводит обязательный стиль pytest — до мержа это законно, но после мержа такой файл планки нарушал бы новое правило `skills/test-authoring.md`; стоит, чтобы guard начал требовать стиль pytest с момента мержа этой части.
