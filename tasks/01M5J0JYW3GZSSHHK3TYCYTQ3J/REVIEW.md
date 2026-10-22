---
task: 01M5J0JYW3GZSSHHK3TYCYTQ3J
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: G3б-2 — гейт неослабления по исходам: прежние версии, строгий режим, исключения в коде, заменяемые тесты; автогейт по правилу планки

## Фаза A: план
- Таблица покрытия PLAN полна (требования 1–11 → шаги 1–4); шаги размера MR, по файлам зоны; подход (всё новое — в ядре `_judge`, вне `_bounds` ядро не зовётся) не конфликтует с архитектурой.
- «Влияние на систему» сверено с diff: затронуты ровно `mandate._weakening_scope_refusal`, поля `Profile`/`_with_component_fields`/`layers_of`, `targets._check_component_rules`, `fsm_autogate._plank_rule_refusal`/`_autogate_conditions`, `outcome_integrity` и новый `tests/test_outcome_integrity_added_lines.py`. Существующие тесты `tests/` не правились (в diff `tests/` — только новый файл). Откат — revert. Замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | поля вне сравнения, `paths` через `_regexes`, `layers_of` с отложенным импортом; тексты отказов `targets` совпадают с SPEC |
| 2 | OK | `_Files.is_test`: маски `tests`, без них — пути отчёта базы (включая file-level) |
| 3 | OK | C, третья выписка `scratch/prior` в `trees` (уборка тем же `finally`), `checkout <база> -- :(literal)…`, удаление `A`, прогон, перепрогон `(PRIOR, BASE)`, одна находка на id |
| 4 | OK | `_replacement_findings`, `_cover`: мандат, затем замена только для «исчез»/«прежняя версия красная» |
| 5 | OK | `_strict_findings`, `_path_covering` |
| 6 | OK | в границе: маски `tests`/`test_support`, `paths` (без них — любой путь); вне — прежний текст |
| 7 | реализовано не так | новый путь переименования исключён из проверки по тестовому СТАРОМУ пути (R1-F2); при `diff.noprefix=true` в конфиге git Оператора проверка молча даёт ноль находок (R1-F1) |
| 8 | OK | `_name_status` / `_added_lines` → `_Prepare` |
| 9 | OK | `_KINDS`, `_RANK` 4–10, `_runs_marker`, отпечаток с `замена:…`, `_proven` по виду, порядок строк записи |
| 10 | OK по коду, сторожа в `tests/` нет | R1-F3 |
| 11 | OK | детерминированные песочницы без сети/Node |

## Замечания

- major — orchestrator/advance_gates/outcome_integrity.py `_added_lines` (argv `git … diff --no-color --no-ext-diff -M -U0`, разбор `+++ b/…`) — вывод зависит от пользовательского конфига git: `gitcmd.pult_env()` наследует окружение и `~/.gitconfig` процесса пульта, а при `diff.noprefix=true` строка заголовка — `+++ a.js` без `b/`, разбор ставит `path = None` и пропускает все добавленные строки. Проверено исполнением: на одном и том же репозитории с добавленной строкой `process.env.NODE_ENV` `_added_lines` даёт `{'a.js': [(2, …)]}` по умолчанию и `{}` при `GIT_CONFIG_KEY_0=diff.noprefix, VALUE=true`. Итог — находок «исключение в коде» ноль без отказа: fail-open гейта, прямо против требования 8 (сбой диффа не должен давать «ноль находок»). Предложение: зафиксировать префиксы в argv (`--src-prefix=a/ --dst-prefix=b/` или `-c diff.noprefix=false -c diff.mnemonicPrefix=false`) и/или считать заголовок `+++ ` без ожидаемого префикса (кроме `/dev/null`) отказом подготовки; добавить тест в `tests/test_outcome_integrity_added_lines.py` с подменённым `diff.noprefix=true` через `GIT_CONFIG_COUNT`.
- major — orchestrator/advance_gates/outcome_integrity.py `_code_exception_findings`, условие `if any(files.is_test(p) or files.is_support(p) for p in (path, old))` — файл, переименованный ИЗ тестового пути в путь кода, выпадает из проверки по своему старому пути. SPEC, требование 7: проверяются файлы компонента вне тестовых файлов и `test_support`; новый путь `lib/util.py` — файл кода. Проверено исполнением: `_code_exception_findings` с записью `('R090', 'tests/test_util.py', 'lib/util.py')` и добавленной строкой `NODE_ENV` в `lib/util.py` даёт `[]`, тот же файл со статусом `M` — находку. Сценарий: ветка `git mv tests/test_util.py lib/util.py` (>50% сходства) и дописывает `os.environ["NODE_ENV"]`-ветвление — у `python-ast` ни строгого режима, ни находки исключения; прежняя версия старого пути на третьей выписке зелёная. Предложение: решать тестовость/`test_support` по пути головы (`path`), старый путь не учитывать; тест на переименование тест→код с подстрокой.
- major — tasks/01M5J0JYW3GZSSHHK3TYCYTQ3J/acceptance_tests/test_autogate_plank_rule.py (единственное покрытие AC-28/AC-29), orchestrator/fsm_autogate.py `_plank_rule_refusal` — свойство кода «при правиле не по умолчанию отказ снят только в границе `_bounds`; у канарейки и вне границы — прежний отказ» держит только планка с `Группа: разовый`; в `tests/` его нет (поиск `_plank_rule_refusal`/«G3б) не исполняется» по `tests/` — только старые файлы без этого сценария; долгоживущие файлы задачи AC-28/29 не содержат). После мержа планку не гоняет ни CI, ни автогейт (ADR-0018 п. 3): регрессия, снимающая отказ у канарейки или вне границы, пройдёт молча — это снятие fail-closed. Предложение: тест в `tests/` (например `tests/test_fsm_autogate_plank_rule.py`) на `_plank_rule_refusal(rule, t)`: правило не по умолчанию + профиль в границе → `None`; то же с `is_canary=1` и с профилем вне границы → текст «до гейта неослабления по исходам (G3б) не исполняется»; отказ построения → «автогейт: <причина>»; с заявками «Ловит мутацию: …». Эталон пина AC-30 — факт задачи, ему место в планке, в `tests/` не нужен.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/advance_gates/outcome_integrity.py `_added_lines` (argv и разбор `+++ `) | разбор зависит от `diff.noprefix` конфига git пульта | при `diff.noprefix=true` ноль находок «исключение в коде» без отказа — fail-open | зафиксировать префиксы в argv; неожиданный заголовок — `_Prepare`; тест с `GIT_CONFIG_*` |
| R1-F2 | open | orchestrator/advance_gates/outcome_integrity.py `_code_exception_findings` (`for p in (path, old)`) | переименование тест→код исключает новый файл кода из проверки | подстрока исключения в переименованном в код файле не даёт находки (обход требования 7) | тестовость — только по пути головы; тест на переименование |
| R1-F3 | open | orchestrator/fsm_autogate.py `_plank_rule_refusal`; покрытие только в разовой планке | AC-28/29 без сторожа в `tests/` | регрессия снятия отказа у канарейки/вне границы пройдёт после мержа незамеченной | тест `_plank_rule_refusal` в `tests/` с заявками мутаций |

## Вердикт
changes_requested — исправить R1-F1, R1-F2, R1-F3 (список выше). Прочее (требования 1–6, 8–11, план) замечаний не имеет.

## Проверено исполнением
- `python3 …/orchestrator/artel.py plank-run 01M5J0JYW3GZSSHHK3TYCYTQ3J` — 4 passed, код выхода 0.
- `python3 -m pytest -q -p no:xdist tests/test_01m5j0jyw3gzsshhk3tycytq3j_profile_layers.py tests/test_outcome_integrity_added_lines.py tests/test_fsm_autogate.py tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py` — 33 passed, 25 subtests passed.
- `python3 -m pytest -q -p no:xdist -o timeout=600 tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py` — 44 passed, 26 subtests, 254.95 с.
- R1-F1: `_added_lines` на временном репозитории — по умолчанию `{'a.js': [(2, 'const m=process.env.NODE_ENV')]}`, при `GIT_CONFIG_KEY_0=diff.noprefix=true` — `{}`; при `diff.mnemonicPrefix=true` — корректно.
- R1-F2: `_code_exception_findings` с `_Files` компонента без `tests` (база: `tests/test_util.py`) — запись `R090 tests/test_util.py → lib/util.py` с `NODE_ENV` даёт `[]`, запись `M lib/util.py` — находку.
- Сверка неослабления: diff `tests/` против базы 075806f2 — только новый файл `tests/test_outcome_integrity_added_lines.py`, существующие тесты не тронуты.

## Предложения системе
- Долгоживущий `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py` идёт ~254 с при пороге 60 с (предупреждение пакета) — каждый метод заводит настоящие git-выписки; skills/test-authoring.md мог бы требовать общий `setUpClass`-стенд для песочниц гейта исходов.
- Вызовы git, вывод которых разбирается построчно (`diff`, `log` с форматами), наследуют `~/.gitconfig` через `gitcmd.pult_env` — класс «вывод зависит от конфига пользователя»; стоит дать `gitcmd` изолированный вариант (`GIT_CONFIG_GLOBAL=/dev/null` или фиксированные `-c`).
