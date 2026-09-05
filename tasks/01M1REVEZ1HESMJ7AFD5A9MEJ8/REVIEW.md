---
task: 01M1REVEZ1HESMJ7AFD5A9MEJ8
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 4
---

# REVIEW: зависимости стека (P0) — файл закреплённых версий, venv пульта, установка в CI и у роли

Примечание: ревью-пакет ошибочно сообщил, что `SPEC.md`/`PLAN.md` не
показаны («не существует ни в ветке, ни в дереве») — оба файла реально
существуют в рабочем каталоге задачи (`tasks/01M1REVEZ1HESMJ7AFD5A9MEJ8/
{SPEC,PLAN}.md`) и прочитаны точечно инструментом чтения. См.
«Предложения системе».

## Фаза A: гейт плана

PLAN.md проходит `scripts/guard.py` (структурно ок). Таблица покрытия
требований полна (все 6 требований SPEC покрыты шагами 1-5), шаги —
проверяемые единицы (по файлу/паре файлов на шаг), подход не
конфликтует с существующей архитектурой `check_stack()`/`role_env()`
(S1/S3). Зоны диффа сверены с `zones:` SPEC + `COMMON_ZONES`
(`orchestrator/config.py:438`) + расширением зон PLAN
(`orchestrator/artel.py`, мандат ANSWER-2.md, маркер «Расширение зон
разрешено:» совпадает буквально с тем, что ищет
`fsm_advance._answer_zones_mandate`) — все 15 изменённых файлов
покрыты, нарушений нет. Диф `.github/workflows/ci.yml` в разделе
«Приложение» PLAN.md сверен вручную построчно с текущим `main`
(контекстные строки диффа совпадают с `git show main:.github/
workflows/ci.yml` byte-for-byte в районе строк 158-166) — патч
применился бы чисто (AC-11).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (файл закреплённых версий + исключения манифеста) | OK | `requirements.lock` (root), `THIRD_PARTY_EXCEPTIONS` — 3 записи с причиной, инвариант stdlib-only пропускает их и по-прежнему падает на прочих (AC-1..3, AC-14 — тесты зелёные) |
| 2 (venv пульта, идемпотентно, сверка версий) | OK | `orchestrator/venv.py::sync` создаёт venv `sys.executable`'ом, идемпотентно; `check_stack()` даёт WARN на расхождении/отсутствии (AC-4..8 — тесты зелёные) |
| 3 (CI ставит зависимости из файла) | OK (проверено вручную, не автотестом) | Диф `ci.yml` — приложение в PLAN.md, `.github/workflows/` не тронут кодом; AC-9/10/11 помечены `manual` с обоснованием (протокол доступен только Оператору при мерже) — обоснование состоятельно |
| 4 (role_env берёт интерпретатор venv) | OK | `_venv_interpreter_bin()` + `role_env()` — venv `bin/` первым в PATH, `OSError` без тихого отката (AC-12/13 — тесты зелёные) |
| 5 (P1 — раннер pytest — вне объёма) | OK | Проверено `grep -rn pytest orchestrator/*.py` — упоминания только описательные/существующие (doctor.py сторож, комментарии), раннер не добавлен |
| 6 (тесты) | Changes requested | Тесты есть и зелёные, но см. R1-F1 — часть новых тестов не несёт обязательной заявки «Ловит мутацию» |

## Замечания

- major — `tests/test_multitarget.py:847-885` (класс
  `RoleEnvVenvInterpreterTest`, методы
  `test_consistent_venv_puts_its_bin_first_on_path` (847),
  `test_inconsistent_venv_raises_instead_of_falling_back` (861),
  `test_missing_venv_also_raises_rather_than_falling_back` (874)) — ни
  один из трёх новых тестовых методов не несёт собственного докстринга
  с заявкой «Ловит мутацию: …» (skills/test-authoring.md,
  review-checklist п.3): есть только докстринг КЛАССА с общим описанием
  требования, но не по каждому тесту отдельно. Показательно, что
  разработчик писал их как копию (permanent-regression) локнутых
  приёмочных тестов `tasks/01M1REVEZ1HESMJ7AFD5A9MEJ8/acceptance_tests/
  test_ac12_ac13_role_env_venv_interpreter.py`, где ровно те же три
  метода (`test_ac12_consistent_venv_puts_its_bin_first_on_path`,
  `test_ac13_inconsistent_venv_raises_instead_of_silently_using_the_
  system_python`, `test_ac13_missing_venv_also_raises_rather_than_
  falling_back`) несут полноценные докстринги с «Ловит мутацию» — и они
  просто не были перенесены при копировании в постоянный набор.
  Предложение: скопировать докстринги трёх методов из
  acceptance_tests-версии (с поправкой на то, что там `unittest.
  TestCase`, а здесь `TmpRootTest`/иные фикстуры venv_dir — сама
  формулировка «Ловит мутацию» переносится дословно).

- minor — `orchestrator/runner.py:448-457` (`_venv_interpreter_bin`) —
  функция зовёт ПОЛНЫЙ `stack.check_stack()` (питон + `git`/`gh`/
  `claude` — три живых subprocess с таймаутом 10 c каждый — плюс venv/
  venv-packages) только чтобы получить статус двух venv-проверок;
  `role_env()` зовётся минимум дважды за шаг роли (`doctor.
  check_git_identity` в preflight и сам `run_agent_once` — из PLAN
  «Влияние на систему»), то есть каждый шаг ЛЮБОЙ роли теперь тянет
  до 6 лишних subprocess-вызовов инструментов, не относящихся к вопросу
  «venv согласован». В обычном случае это доли секунды, но при
  зависании/деградации `git`/`gh`/`claude` (маловероятно, но не
  исключено) это новый источник задержки шага, не описанный в
  «Риски» PLAN.md (там отмечен только повторный `pip freeze`).
  Не блокирует — узкая функция, вычисляющая только venv/venv-packages
  без остальных проверок манифеста, была бы избавлена от этой связки;
  оставляю на усмотрение разработчика/Оператора.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/test_multitarget.py:847,861,874 | 3 новых теста без докстринга «Ловит мутацию» | ревьювер не может сверить тест с заявленной мутацией — конвенция test-authoring нарушена | скопировать докстринги из tasks/.../acceptance_tests/test_ac12_ac13_role_env_venv_interpreter.py (те же 3 сценария) |
| R1-F2 | open | orchestrator/runner.py:448-457 | `_venv_interpreter_bin` зовёт весь `check_stack()` (3 лишних subprocess) ради venv-статуса | лишняя задержка/поверхность отказа на каждом шаге любой роли, не описанная в Рисках PLAN | сузить проверку до venv/venv-packages, либо явно принять риск и дописать его в «Риски» PLAN.md |

## Вердикт

changes_requested — единственный блокирующий класс: докстринги трёх
тестов в `tests/test_multitarget.py` (R1-F1). R1-F2 — необязательное
улучшение, не требует отдельной итерации, но стоит решить тем же
проходом.

## Проверено исполнением

- `python3 -m unittest tests.test_stack tests.test_venv tests.test_multitarget tests.test_invariants -v` — 108 тестов, все зелёные.
- `python3 -m unittest tests.test_agent_prompt tests.test_review_freshness tests.test_review_package -v` — 114 тестов, все зелёные.
- `python3 -m unittest discover -s tasks/01M1REVEZ1HESMJ7AFD5A9MEJ8/acceptance_tests -v` — 15 тестов, все зелёные (AC-9/10/11 и AC-16 — обоснованно `manual`/`skip`, см. докстринги файлов).
- `python3 scripts/guard.py tasks/01M1REVEZ1HESMJ7AFD5A9MEJ8/SPEC.md tasks/01M1REVEZ1HESMJ7AFD5A9MEJ8/PLAN.md` — «GUARD: ок (2 файлов)».
- `python3 scripts/codebase_map.py` (прогон вхолостую для сверки, изменение отменено `git checkout -- docs/codebase-map.md`) — диф с версией в ветке только в строке `built_at_sha`, содержимое совпадает (карта не отстала).
- Ручная сверка контекстных строк диффа `.github/workflows/ci.yml` (раздел «Приложение» PLAN.md) с `git show main:.github/workflows/ci.yml` — совпадают дословно, патч применился бы (AC-11).
- `grep -rn pytest orchestrator/*.py scripts/*.py .github/workflows/ci.yml` — раннер pytest не добавлен, только упоминания/установка пакета (требование 5).
- Полный набор `tests/` не прогонялся (решение Оператора 05.09, ANSWER-1 п.1) — только затронутые модули выше.

## Предложения системе

- Сборщик ревью-пакета не нашёл `SPEC.md`/`PLAN.md` этой задачи ни в
  кодовой ветке (ожидаемо — артефакты туда не коммитятся, skills/
  conventions-core.md), ни «в дереве» — но путь, по которому он искал
  «дерево», судя по сообщению об ошибке, был корень пульта
  (`/Users/.../artel/tasks/...`), а не рабочий каталог задачи
  (`.artel/worktrees/<id>/tasks/...`), где файлы реально лежат и откуда
  ревьювер их прочитал напрямую. Тот же класс, что уже отмечен в
  памяти («tasks/<id>/ отсутствует во всей истории task-ветки» —
  проверяй артефактную/рабочую копию, не строку ошибки буквально) —
  здесь ошиблась не роль, а сам сборщик пакета; стоит поправить его
  резолвинг пути «дерева» на актуальный worktree задачи, иначе
  следующий ревьювер, доверившийся пакету буквально, вынесет вердикт
  без SPEC/PLAN вовсе.
