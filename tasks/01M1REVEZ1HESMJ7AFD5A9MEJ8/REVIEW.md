---
task: 01M1REVEZ1HESMJ7AFD5A9MEJ8
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 4
---

# REVIEW: зависимости стека (P0) — файл закреплённых версий, venv пульта, установка в CI и у роли

Примечание: ревью-пакет этой итерации нёс diff и опись СОВЕРШЕННО ДРУГОЙ
задачи (01M1RR1PZC926T13NB1JSZ7F8T, `zone_lock.py`/`fsm.py`) и сообщал,
что `SPEC.md`/`PLAN.md` этой задачи «не существуют ни в ветке, ни в
дереве». Оба факта — артефакт сборщика пакета, не состояние задачи: диф
между `sha предыдущего вердикта` (022239772515b5a26de8bcf67ba757705c716e0e,
= коммит R1-F1/R1-F2 этой задачи) и HEAD ветки (`49567169`) — это
СЛИЯНИЕ main внутрь ветки задачи (коммит-мерж `49567169`), которое
попутно принесло чужой смерженный в main материал (`01M1RR1PZC926T13
NB1JSZ7F8T`); собственный диф задачи лежит РАНЬШЕ этой точки. Разобрал
вручную (`git merge-base main <ветка задачи>` = `7224f9c9`, диф
`7224f9c9..HEAD` по зонам задачи) — см. «Проверено исполнением». Тот же
класс, что уже в памяти («T087: подтяжка main снова не регенерировала
карту … пустой/короткий инкрементальный diff — повод перепроверить
вручную»), и то же, что предыдущий ревьювер отмечал про SPEC/PLAN
резолвинг. `SPEC.md`/`PLAN.md` реально существуют в рабочем каталоге
задачи и в артефактной ветке `artifact/01m1revez1hesmj7afd5a9mej8` —
прочитаны точечно. См. «Предложения системе».

## Фаза A: гейт плана

PLAN.md не менялся с итерации 1 по существу (только раздел «Подход»
дополнен абзацем про закрытие R1-F1/R1-F2) — гейт плана пройден на
итерации 1 и остаётся в силе: guard ок, таблица покрытия требований
полна, шаги — проверяемые единицы, подход не конфликтует с архитектурой
S1/S3. Перепроверил `python3 scripts/guard.py` — ок.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (файл закреплённых версий + исключения манифеста) | OK | `requirements.lock` — 8 записей, версии сверены с реальным PyPI (`pip index versions` на каждый пакет — совпадают дословно, включая `pytest==9.1.1`); транзитивные зависимости `pytest`/`pytest-timeout`/`pytest-xdist` для Python ≥3.11 полны (`requires_dist` каждого пакета с PyPI — `exceptiongroup`/`tomli` условны на `python_version < "3.11"`, `colorama` только `win32` — ничего не пропущено). `THIRD_PARTY_EXCEPTIONS` — 3 записи с причиной, AC-1..3/AC-14 тестами зелёные. |
| 2 (venv пульта, идемпотентно, сверка версий) | OK | `orchestrator/venv.py::sync` — реальный `python -m venv` + `pip install -r`; идемпотентность и интерпретатор проверены тестами (AC-4..6). `check_stack()` — WARN на расхождении/отсутствии venv (AC-7/8), тесты зелёные. |
| 3 (CI ставит зависимости из файла) | OK | Диф `ci.yml` в PLAN.md применён `git apply --check` на ТЕКУЩЕМ `main` (не только на историческом `72a755a3`, как на итерации 1) — прошёл чисто. `.github/workflows/` не тронут кодом ветки (сверено `git diff main HEAD -- .github/`, пусто). |
| 4 (role_env берёт интерпретатор venv) | OK | `_venv_interpreter_bin()`/`role_env()` — venv `bin/` первым в PATH, `OSError` без отката; все три существующих вызывающих места `role_env()` в `doctor.py` (`check_git_identity`, `isolation_smoke`, `_live_smoke_run`) уже ловят `OSError` — прочитал код всех трёх, ни одно не изменено этой задачей и не упадёт необработанным исключением. `run_agent_once` (`orchestrator/runner.py:661-668`) тоже ловит и журналирует `agent run SKIPPED` — AC-13 закрыт существующим контрактом, не новым кодом. |
| 5 (P1 — раннер pytest — вне объёма) | OK | `grep -rn pytest orchestrator/*.py .github/workflows/ci.yml` — только установка/упоминания, раннер не добавлен. |
| 6 (тесты) | OK | R1-F1 закрыт (см. Реестр) — тесты зелёные и несут заявку «Ловит мутацию» каждый. |

## Замечания

Новых замечаний нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_multitarget.py:847-885 | 3 новых теста без докстринга «Ловит мутацию» | — | Проверил `tests/test_multitarget.py::RoleEnvVenvInterpreterTest` — все три метода (`test_consistent_venv_puts_its_bin_first_on_path`, `test_inconsistent_venv_raises_instead_of_falling_back`, `test_missing_venv_also_raises_rather_than_falling_back`) теперь несут собственный докстринг с формулировкой «Ловит мутацию: …», описывающей конкретный сценарий поломки, не пересказ имени метода. Суть замечания устранена. |
| R1-F2 | accepted | orchestrator/runner.py:448-457 | `_venv_interpreter_bin` зовёт весь `check_stack()` (3 лишних subprocess) ради venv-статуса | — | Обоснование отказа проверено буквально: прочитал `tasks/01M1REVEZ1HESMJ7AFD5A9MEJ8/acceptance_tests/test_ac12_ac13_role_env_venv_interpreter.py:67-68,96-97,122-123` — все три залоченных метода мокают именно `runner.stack.check_stack` целиком (`mock.patch.object(runner.stack, "check_stack", ...)`), не отдельную venv-функцию. Сужение вызова внутри `_venv_interpreter_bin` на не-`check_stack` функцию оставило бы эти моки без эффекта — реальный `check_stack()` спавнил бы живые `git`/`gh`/`claude` и не нашёл бы согласованный venv по временному пути теста, планка бы покраснела. Отказ обоснован реальным ограничением локнутой планки (T023), риск явно описан в PLAN.md «Риски», код действительно не менялся (`orchestrator/runner.py:448-457` идентичен итерации 1). |

## Вердикт

approved

## Проверено исполнением

- Восстановил реальный диф задачи вручную: `git merge-base main task/01m1revez1hesmj7afd5a9mej8-zavisimosti-steka-p0-fayl-zakr` → `7224f9c9`; `git diff --stat 7224f9c9 49567169 -- orchestrator/ tests/ requirements.lock scripts/` — 14 файлов (`orchestrator/{artel,config,runner,stack,venv}.py`, `requirements.lock`, `tests/{sandbox,test_agent_prompt,test_invariants,test_multitarget,test_review_freshness,test_review_package,test_stack,test_venv}.py`) — тот же набор, что PLAN.md заявляет по шагам 1-5.
- `python3 -m unittest tests.test_stack tests.test_venv tests.test_multitarget -v` — 63 теста, все зелёные.
- `python3 -m unittest tests.test_agent_prompt tests.test_review_freshness tests.test_review_package tests.test_invariants -v` — 159 тестов, все зелёные.
- `python3 -m unittest tests.test_doctor tests.test_sandbox -v` — 125 тестов, все зелёные (сверка, что общий патч `stack.check_stack` в `tests/sandbox.py::TmpRootTest` не задел смежные песочницы).
- `python3 -m unittest discover -s tasks/01M1REVEZ1HESMJ7AFD5A9MEJ8/acceptance_tests -v` — 15 тестов, все зелёные (AC-9/10/11 — `manual`, обоснование — защищённый путь `.github/workflows/`, содержимое финального `ci.yml` недоступно код-ветке; AC-16 — `skip`, регрессия покрыта прогоном выше).
- `python3 scripts/guard.py tasks/01M1REVEZ1HESMJ7AFD5A9MEJ8/SPEC.md tasks/01M1REVEZ1HESMJ7AFD5A9MEJ8/PLAN.md` — «GUARD: ок (2 файлов)».
- Дословно скопировал диф `.github/workflows/ci.yml` из PLAN.md в файл и прогнал `git apply --check` в рабочем дереве текущей ветки (её `.github/workflows/ci.yml` идентичен `main` — `git diff main HEAD -- .github/workflows/ci.yml` пуст) — «применяется без ошибок» подтверждено на ТЕКУЩЕМ `main` (275116b9), не только историческом.
- `python3 scripts/codebase_map.py` (пробный прогон, отменён `git checkout -- docs/codebase-map.md`) — диф с версией в ветке только в строке `built_at_sha`, содержимое идентично.
- Версии `requirements.lock` сверены с реальным PyPI: `python3 -m pip index versions <pkg>` для всех 8 записей — совпадают дословно; `requires_dist` каждого пакета верхнего уровня (`pytest`/`pytest-timeout`/`pytest-xdist`, PyPI JSON API) — транзитивные зависимости для Python ≥3.11 (`REQUIRED_PYTHON`) полны, ничего не упущено (условные `exceptiongroup`/`tomli`/`colorama` не нужны на целевой платформе).
- Ручное чтение `orchestrator/doctor.py:137-158,344-361,439-444` — все три вызывающих места `role_env()` ловят `OSError` общим образом, ни одно не изменено этой задачей.
- Полный набор `tests/` не прогонялся (решение Оператора 05.09, ANSWER-1 п.1) — только затронутые модули выше плюс смежные песочницы (`test_doctor`, `test_sandbox`).

## Предложения системе

- Сборщик ревью-пакета итерации 2 сообщил инкрементальный диф от sha
  предыдущего вердикта до HEAD, но этот диапазон (`022239772515b5a26de
  8bcf67ba757705c716e0e..49567169`) на деле не диф ветки — оба конца
  разделены МЕРЖЕМ main внутрь ветки задачи, и `git diff a...b`
  (сборщик явно использовал форму с тремя точками — см. заголовок диффа
  в пакете) для этой пары считается от `merge-base(a,b)`, который здесь
  СОВПАДАЕТ с `a` (022239772515b5a26de8bcf67ba757705c716e0e — предок
  49567169), поэтому диф показал ровно содержимое коммита-мержа
  (чужую задачу 01M1RR1PZC926T13NB1JSZ7F8T, попавшую в main и
  подтянутую в ветку), а не диф этой задачи между итерациями. Класс тот
  же, что уже в памяти (T087), но конкретный механизм здесь — это
  трёхточечный `git diff` через коммит-мерж, не расхождение из-за
  автокоммита. Тот же прогон сборщика заодно не нашёл `SPEC.md`/
  `PLAN.md` (тот же класс, что REVIEW.md итерации 1 уже отметил про
  резолвинг «дерева») — оба факта совпали в одной итерации и делают
  пакет непригодным для ревью без ручной перепроверки диапазона диффа;
  стоит: (а) для инкрементального диффа считать `git diff a..b` (две
  точки) там, где нужен ИМЕННО диф ветки между вердиктами, не диф от
  точки расхождения; (б) чинить резолвинг пути «дерева» на worktree
  задачи, как уже предложено итерацией 1.
