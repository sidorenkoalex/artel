---
task: 01M5NHXJA3X7C66XTJN4J3E25W
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: ADR-0027, часть Б — правила стиля pytest в скилах, инвариант общих фикстур, устойчивое подключение фикстур

## Фаза A: план
- Покрытие: таблица PLAN закрывает требования 1–6; шаги проверяемые (перенос приложений + `git apply --check`, прогон на дереве «ветка + приложения», guard).
- Подход согласован с конвенциями: защищённые пути (`conftest.py`, `skills/*`, `tests/test_invariants.py`, `docs/invariants.md`) меняются только приложениями, ветка их не трогает.
- «Влияние на систему» совпадает с фактом. Diff пакета (`main...ветка`) показывает `orchestrator/pull.py` и `tests/test_01m5npvrrk9r6s6sd40cbjzypt_pull_plank_appendix.py`, но это ложный хвост: локальный `main` (80dc5169) отстаёт от `origin/main` (44bf2cdb, мерж задачи 01M5NPVRRK9R6S6SD40CBJZYPT), а подтяжка fd00b3e0 принесла этот мерж в ветку. `git diff --stat origin/main...HEAD` — один файл, залоченный долгоживущий тест задачи (+254). Своего кода, карты и существующих тестов ветка не меняет. Откат — revert мерж-коммита, описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Блоки ```diff PLAN 1–5 побайтно равны блокам 1–3 `TZ.md` и 1–2 SPEC «Приложения Оператора» (программная сверка). Заменённое 4-е Приложение ТЗ в PLAN не перенесено — так и должно быть. `git apply --check` каждого блока на HEAD fd00b3e0 (после подтяжки) — код 0. |
| 2 | OK | `tests/test_01m5nhxja3x7c66xtjn4j3e25w_shared_fixtures.py`: функции модуля, `assert`, `parametrize` литералами, у каждой функции есть «Ловит мутацию:»; классов `TestCase` нет (`unittest` — только раннер инварианта). |
| 3 | OK | `test_ac2_…`: зеркало с копией `conftest.py` и `orchestrator` по симлинку, без `tests/`; `PYTHONPATH` только на каталог, без `ARTEL_ROLE`; `--collect-only` явного файла — код 0 и собраны все тесты. |
| 4 | OK | `test_ac3_…`: тест-функция под `tasks/<id>/acceptance_tests/` просит `tmp_root` без импорта. |
| 5 | OK | `test_ac4_invariant_red_on_each_mutation` покрывает мутации (0)–(5); есть `test_ac4_invariant_green_on_unmutated_copy`. |
| 6 | OK | В `tests/` только новый файл; защищённых путей в собственном diff ветки (против `origin/main`) нет. |

## Замечания
Нет замечаний уровня blocker/major/minor.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved. Приложения перенесены дословно и применяются на базе после подтяжки main (fd00b3e0). На дереве «ветка + Приложения 1–5» тесты задачи и инвариант 42 зелёные. Сторож Приложения 1 проверен временной мутацией. Реестр замечаний пуст: в iteration 1 записей не было.

## Проверено исполнением
- `git diff --stat origin/main...HEAD` — один файл, тест задачи (+254). Хвост `pull.py` в пакете объясняется устаревшим локальным `main`.
- Программная сверка: PLAN[1..5] == TZ[1..3] + SPEC[1..2] — True для всех пяти блоков. `git apply --check -` каждого блока на чистом дереве HEAD fd00b3e0 — код 0.
- Дерево с наложенными Приложениями 1–5: `python3 -m pytest -p no:cacheprovider -q tests/test_01m5nhxja3x7c66xtjn4j3e25w_shared_fixtures.py tests/test_invariants.py::SharedFixturesWrapSandboxClassesInvariantTest` — 12 passed, 98 subtests passed.
- Временная мутация: наложены только Приложения 2–5 (`conftest.py` с голым `find_spec`). `test_ac2_collect_without_tests_package_exits_zero` красный (`ModuleNotFoundError: No module named 'tests'`), итог 1 failed, 8 passed.
- После каждого прогона приложения сняты `git apply -R`; `git status --short` — чисто.
- `python3 …/artel.py plank-run 01M5NHXJA3X7C66XTJN4J3E25W` — `test_task_facts.py`: 3 passed, код выхода 0.
- CI головы fd00b3e0 зелёный (16 проверок, по пакету).

## Предложения системе
- Пакет ревью строит diff как `git diff main...ветка` от локального `main` клона. Если этот `main` отстаёт от `origin/main`, после подтяжки в diff попадает чужой смерженный код (здесь `orchestrator/pull.py` задачи 01M5NPVRRK9R6S6SD40CBJZYPT). Сборщику пакета стоит брать базу от `origin/main` либо подтягивать локальный `main` перед сборкой.
