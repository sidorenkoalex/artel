---
task: T037
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 2
---

# REVIEW: Общая тестовая песочница и ревизия мокинга subprocess

## Фаза A — гейт плана

Покрытие: все 6 требований SPEC отражены в таблице «Покрытие требований»
PLAN.md и разнесены по трём шагам зависимого, но единого MR. Шаги —
проверяемые единицы (каждый гоняет свой приёмочный тест + полный
`unittest discover`), не микрооперации и не «сделать всё». Подход не
конфликтует с конвенциями: `spawn_agent` сделан ровно по образцу
`gitcmd.git`/`keychain.token`, как и требует SPEC. Два отклонения от
«только импорты и пути патчей» (переименование `TmpRootTest`-наследника,
переименование локального `fake_git` в `test_brief.py`) явно
задокументированы в PLAN с обоснованием — вынуждены буквальной AST-логикой
залоченного приёмочного теста AC-1, не дедупликацией. План принят без
замечаний.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `tests/sandbox.py` определяет `TmpRootTest`/`capture`/`fake_git`; приёмочный тест AC-1 (`NoLeftoverCopiesOutsideSandboxTest`) зелёный — прогнан лично, подтверждает отсутствие копий по всем файлам `tests/*.py`. |
| 2 | OK | `orchestrator/runner.py:20-28` — `spawn_agent` заведён по образцу `gitcmd.git`; `run_agent_once` переведён (runner.py:432). Прямого мокинга `runner.subprocess.Popen` в `tests/*.py` не осталось (проверено grep + приёмочным AST-тестом AC-3, зелёный). |
| 3 | OK | `orchestrator/doctor.py:206` — `check_cli_version()` добавлен в `preflight_checks()` после раннего `return` по блокирующим проверкам, как и `check_git_identity()`. `check_cli_version()` возвращает только `ok`/`warn` (doctor.py:96-105) — блокировки шага не вносит. Приёмочные тесты AC-4 зелёные. |
| 4 | OK | Просмотрен полный diff тестовых файлов: правки — импорты, цель `mock.patch(.object)`, `PATCHED_ATTRS`, и два документированных переименования (класс-наследник `TmpRootTest`, `fake_git`→`fake_git_with_calls` в `test_brief.py:177`). Логика/ассерты не тронуты нигде. |
| 5 | OK (с оговоркой) | Полный прогон `python3 -m unittest discover -s tests` — лично прогнан на ветке: 599 тестов, 3 падения в `test_multitarget.py::RoleEnvTest` (`test_absent_identity_is_journalled_before_the_step`, `test_env_carries_the_git_identity`, `test_identity_already_in_the_environment_is_not_overridden`). Проверено отдельно во временном worktree main (до T037, коммит `eea60cc`) — те же 3 теста падают той же ошибкой (ambient git identity машины ревьювера расходится с `PROBE_NAME`/`PROBE_EMAIL`), то есть предсуществующий экологический флейк, не внесённый этой веткой; заявлен в `test_manual_criteria.py` со ссылкой на прецеденты T035/T036 и не воспроизводится на чистом CI-раннере (`.github/workflows/ci.yml`, ubuntu-latest). Число тестов — 599, совпадает с базой на main (599) — не уменьшилось. |
| 6 | OK | Таблица переносов в PLAN.md полная и по каждому файлу называет расхождение `PATCHED_ATTRS` и остаточную логику `setUp`, сверено построчно с diff — расхождений не нашёл. Диф не трогает `gates.yaml`/`roles.yaml`/`.github/`/`templates/`/`skills/` — откат одним `git revert` merge-коммита технически чист (продуктовых миграций нет, единственное поведенческое изменение — warn-проверка в preflight, откатывается тем же ревертом). |

## Замечания

- minor — `tests/test_doctor.py:19` (`import tempfile`), `tests/test_multitarget.py` (`import tempfile`), `tests/test_agent_failure.py:17`, `tests/test_agent_log.py:19`, `tests/test_step_cost.py:17` — во всех пяти файлах `tempfile.TemporaryDirectory()` был единственным использованием импорта `tempfile` в `TmpRootTest.setUp()`; после переноса этой логики в `tests/sandbox.py` импорт остался, но нигде в файле больше не используется (проверено `grep -c "tempfile\." <файл>` → `0` для всех пяти). Правка импортов — часть заявленного объёма правок тестов (требование 4), так что предлагаю почистить: убрать неиспользуемый `import tempfile` в этих пяти файлах в этом же MR или следующей итерацией. Не блокирует: поведения не меняет, тесты проходят.

## Вердикт

approved. 0 blocker/major. Единственное замечание — minor (мёртвые импорты `tempfile` в 5 файлах), не мешает мержу; можно поправить попутно или оставить как техдолг без ADR (это не тест/гейт/лимит/guard, принцип целостности не задет).
