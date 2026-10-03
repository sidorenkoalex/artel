---
task: 01M41W15BK20WBTD9TMBTSXNZA
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: plank-run работает в шаге роли — путь планки, который признаёт сторож роли

## Фаза A — план
- Таблица покрытия полна: требования 1–4 → шаги 1–2; AC-4 (правки существующих тестов) явно закрыто записью «правок нет».
- Шаги размера MR: одна правка формирования аргумента + зафиксированный долгоживущий сторож test_author; своих тестов разработчик не добавлял — повтора долгоживущего нет (ADR-0020 п.4).
- «Влияние на систему» совпадает с diff: в диапазоне `411d8e37...HEAD` кроме артефактов/карты/лок-теста изменён только `orchestrator/plank_run.py` (5+/2−). `conftest.py`, гейты, `acceptance.run` не тронуты. Откат — revert.
- Риск `relative_to` → `ValueError` разобран верно: `plank_in_code_copy` отдаёт `materialize_from_branch`/`materialize_files`, оба возвращают `code_dir / "tasks" / task_id` (`orchestrator/acceptance.py:393-395`, докстринг `:345`), т. е. `tdir` строится от того же объекта `code_dir` — `relative_to` не может упасть ни на симлинке, ни на `resolve()`-расхождении.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/plank_run.py:142-143`: `tasks/<id>/acceptance_tests` либо `…/<selected>` (с `::узлом` — `selected` уже несёт его из `_selected`); подтверждено AC-3 сторожа по всем 4 формам (регистратор `sys.argv` pytest) |
| 2 | OK | `cwd=code_dir` в `run_plank` — относительный путь эквивалентен абсолютному; `test_ac4_without_role_…` (состав, «код выхода pytest», код выхода команды) зелёный |
| 3 | OK | `tests/test_01m41w15bk20wbtd9tmbtsxnza_plank_run_role.py`: настоящий `conftest.py`+`pyproject.toml`, без подмены `subprocess.run`, вся планка и файл; мутация «абсолютный путь» проверена мной — красный |
| 4 | OK | `tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py`, `tests/test_plank_run_edges.py` не изменены (нет в diff --stat), зелёные |

## Замечания
Нет blocker/major/minor.

Сверка тестов: в диапазоне ветки изменённых методов существующих `tests/` нет — ослабления нет. Лок-тест задачи: заявки «Ловит мутацию» у AC-1…AC-4 называют наблюдаемое расхождение (отказ «Сторож роли», абсолютный позиционный путь в argv, иной итог/код выхода); первая заявка AC-1/AC-3 подтверждена временной мутацией. Планка (`test_ac4_existing_tests_and_plan.py`) помечена «Группа: разовый» — верно, это факт задачи (diff с базой + PLAN.md); долгоживущее свойство закрыто `tests/`, как требует ADR-0018 п.3. Ветвления под литералы фикстуры в коде нет — правило общее.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m41w15bk20wbtd9tmbtsxnza_plank_run_role.py tests/test_01m41r4yam4ngeqxw1fwh7t22m_plank_run.py tests/test_plank_run_edges.py tests/test_conftest_role_guard.py` — `21 passed, 26 subtests passed in 26.95s`.
- Временная мутация `orchestrator/plank_run.py:142` → `tests_rel = str(tdir / "acceptance_tests")`, прогон `tests/test_01m41w15bk20wbtd9tmbtsxnza_plank_run_role.py` — `8 failed, 3 passed` (AC-1, все подслучаи AC-2 и AC-3 красные; AC-4 зелёный, как и заявлено). Код возвращён, `git status --short` чист.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` — расхождение только в строке `built_at_sha`, карта свежа по содержимому; регенерированный файл возвращён `git checkout`.
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M41W15BK20WBTD9TMBTSXNZA` — отказ «Сторож роли…», код pytest 2: пульт исполняет код пина с абсолютным путём (ровно чинимый дефект, как и описано в PLAN). Свойство планки (два существующих файла не правлены и зелёные) подтверждено вручную: их нет в `git diff --stat 411d8e37...HEAD`, прогон выше зелёный.
- CI коммита 89a3b869 — зелёный (16 проверок, по пакету).

## Предложения системе
- Задачи, чинящие сам `plank-run`, не могут прогнать свою планку командой пульта до мержа (пульт на пине); ревьювер подтверждает AC планки косвенно. Стоит в миссии таких шагов явно разрешать альтернативу (например, `plank-run` кодом ветки) или помечать это ожидаемым — согласен с предложением PLAN.
- Однострочная мутация через `python3 - <<EOF` в Bash требует подтверждения прав; скилу review-checklist стоит прямо рекомендовать «временную мутацию» через Edit/Edit-обратно.
