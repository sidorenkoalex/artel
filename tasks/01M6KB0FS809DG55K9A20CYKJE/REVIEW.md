---
task: 01M6KB0FS809DG55K9A20CYKJE
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Предел числа процессов шага роли

## Фаза A: план
- Таблица покрытия полна: требования 1–9 привязаны к шагам; шаги размера MR.
- Подход не конфликтует с архитектурой: расчёт в пульте, в ребёнке только `setrlimit`; отказ через `sys.exit` внутри `try/finally` `_cmd_run`; `auto.py` не тронут.
- «Влияние на систему» совпадает с diff: 7 файлов из зоны SPEC плюс карта, защищённые пути не тронуты, приложение `skills/test-authoring.md` — дифф в PLAN.
- Шаг 4 PLAN заявляет только тесты формулы, разбора вывода и `doctor`. Сторожа поведения шага (отказ, снятие группы, однократные записи, передача предела) план в `tests/` не закладывает — см. R1-F1.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `runner.py` `spawn_agent(nproc_limit=)`: `preexec_fn` только с `setrlimit`, функция и аргументы связаны заранее; `role_nproc_limit()` без аргументов, `resource` вызывается через модуль; предел считается один раз в `_run_developer_step` и передаётся по цепочке `_run_attempts` → `run_agent_once` → `_spawn_and_wait` → `spawn_agent`. |
| 2 | OK | `_read_maxprocperuid`: не darwin → `absent` без подпроцесса; на darwin `/usr/sbin/sysctl`, сбой, ненулевой код, пустой вывод или вывод без числа → `failed`. Запись-предупреждение одна на шаг (в `_step_nproc_limit`). |
| 3 | OK | При N ≥ M — запись журнала и `sys.exit` с текстом «запас процессов пользователя исчерпан: N из M». Вызов стоит внутри `try/finally` `_cmd_run`, захват зоны снимается. Сбой счёта → одна запись, шаг идёт. `ps` берётся через `liveness._ps_executable()`. |
| 4 | OK | Пульт не ограничивается: `setrlimit` выполняется только в ребёнке (долгоживущий AC-1/AC-2 зелёный). |
| 5 | OK | Ветка `else` у `proc.wait`, условие `isinstance(agent_pid, int)`, снятие до `close_pump`; запись в журнал только при `leftover > 0`. |
| 6 | OK | `orchestrator/doctor/role_nproc.py`: значения берутся только из трёх функций `runner`; статусы и обе пометки соответствуют SPEC; строка зарегистрирована в `cli.all_checks`. |
| 7 | OK | `docs/stack.md`: формула, константы, наследование, общий запас, расхождение на Linux. Карта свежа (регенерация не дала изменений, кроме `built_at_sha`). |
| 8 | OK | Приложение в PLAN под заданным заголовком, только добавление раздела. |
| 9 | OK | Тесты разработчика не порождают процессов; долгоживущий тест ставит опыт под пределом «счёт + 10» и снимает группу. |

## Замечания
- major — `tests/` (нет файла); код `orchestrator/runner.py` `_step_nproc_limit` (отказ при N ≥ M и однократные записи-предупреждения), `_run_developer_step` (`sys.exit(nproc_refusal)` внутри `try/finally` захвата зоны), `_run_attempts` и `_spawn_and_wait` (передача `nproc_limit` из шага в `spawn_agent`), ветка `else` у `proc.wait` в `_spawn_and_wait` (снятие оставшейся группы и запись `GROUP_LEFTOVER_ACTION`). Эти свойства требований 1, 2, 3 и 5 держит только планка, а все три её файла помечены `Группа: разовый` (`test_nproc_step.py`, `test_nproc_group.py`, `test_nproc_doctor.py`). Долгоживущий файл задачи покрывает только `spawn_agent` и `role_nproc_limit` (AC-1, AC-2). `tests/test_role_nproc_limit.py` покрывает формулу, разбор вывода и `doctor`. Проверено временной мутацией: снят отказ (`if count >= limit` → `if False`), снятие группы на обычном исходе (`leftover = 0`) и передача `nproc_limit` из `_run_attempts`. После этого `tests/test_role_nproc_limit.py`, долгоживущий файл задачи, `test_agent_log.py`, `test_liveness.py` и `test_auto_cycle.py` остались зелёными: 130 passed. Последствие: после мержа (ADR-0018 п. 3) любая регрессия молча вернёт инцидент 04.11 — шаг без предела, сироты в группе, старт при исчерпанном запасе — и ни CI, ни гейт её не поймают. Предложение: добавить в `tests/` (разработчик вправе использовать закрытые точки подмены и песочницу `_step.step_sandbox`, как в существующих тестах запуска шага) сторожа с заявками «Ловит мутацию». Нужны четыре: (а) `cmd_run` при подменённом `_user_process_count` ≥ предела выходит `SystemExit` с причиной, агент не порождён, захвата зоны нет; (б) `cmd_run` передаёт в `spawn_agent` `nproc_limit`, равный `role_nproc_limit()`; (в) при `(None, "failed")` и при сбое счёта ровно одна запись `NPROC_WARNING_ACTION` на шаг из двух попыток, при `absent` — ни одной; (г) `_spawn_and_wait` на обычном исходе снимает оставленный в группе процесс и пишет запись, а при пустой группе запись не пишет. Пункт (г) можно проверить и подменой `liveness.terminate_process_group`, без настоящего процесса. Повторять AC-1/AC-2 долгоживущего файла не нужно.
- minor — `orchestrator/runner.py` `_step_nproc_limit` и `orchestrator/doctor/role_nproc.py` `check_role_nproc`: `_read_maxprocperuid()` вызывается дважды — один раз напрямую ради исхода, второй раз внутри `role_nproc_limit()`. На macOS это два запуска `sysctl` на шаг. Если первый вызов упал, а второй прочитал значение, предупреждение «посчитан от значения по умолчанию 4000» расходится с фактическим пределом. Предложение: вынести формулу во внутреннего помощника от уже прочитанного значения. Публичную `role_nproc_limit()` (Р-2) можно оставить обёрткой над ним.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/ (нет файла); orchestrator/runner.py `_step_nproc_limit`, `_run_developer_step`, `_run_attempts`, `_spawn_and_wait` (ветка `else`) | Отказ при исчерпанном запасе, однократные предупреждения, передача `nproc_limit` из шага и снятие группы на обычном исходе сторожит только разовая планка; временная мутация всех трёх мест — tests/ зелёные | После мержа регрессия вернёт инцидент 04.11 незамеченной | Добавить в tests/ сторожа (а)–(г) с заявками «Ловит мутацию», без повтора долгоживущего AC-1/AC-2 |
| R1-F2 | open | orchestrator/runner.py `_step_nproc_limit`; orchestrator/doctor/role_nproc.py `check_role_nproc` | `_read_maxprocperuid` вызывается дважды | Лишний `sysctl`; возможное расхождение текста предупреждения с фактическим пределом | Считать предел от уже прочитанного значения (minor, на усмотрение) |

## Вердикт
changes_requested — закрыть R1-F1: добавить в `tests/` сторожа поведения шага по пунктам (а)–(г). R1-F2 — minor, на усмотрение разработчика, но в реестре его нужно разметить (`fixed` или `rejected`).

## Проверено исполнением
- `artel.py plank-run 01M6KB0FS809DG55K9A20CYKJE` — 27 passed, код выхода pytest 0.
- `python3 -m pytest tests/test_role_nproc_limit.py tests/test_01m6kb0fs809dg55k9a20cykje_role_nproc.py tests/test_doctor.py -p no:cacheprovider -q` — 124 passed, 3 subtests passed.
- `python3 scripts/codebase_map.py` и `git diff -- docs/codebase-map.md`: кроме строки `built_at_sha` изменений нет, карта свежа (файл возвращён `git checkout`).
- Временная мутация `orchestrator/runner.py` (снят отказ N≥M, снятие группы на обычном исходе, передача `nproc_limit` из `_run_attempts`), затем прогон `tests/test_role_nproc_limit.py`, долгоживущего файла задачи, `test_agent_log.py`, `test_liveness.py`, `test_auto_cycle.py` — 130 passed, 38 subtests passed: ни один сторож не покраснел. Код возвращён `git checkout -- orchestrator/runner.py`, рабочая копия чистая.
- `grep -rln "GROUP_LEFTOVER_ACTION|NPROC_REFUSAL_ACTION|NPROC_WARNING_ACTION|_step_nproc_limit|nproc_limit" tests/` — только два файла задачи, ни один из них не проверяет шаг.

## Предложения системе
- Планка, помеченная `разовый` «по песочнице» (запрет `gitcmd` и закрытых имён в долгоживущих файлах), оставляет свойства кода без сторожа после мержа. Шаблон PLAN или скил разработчика мог бы требовать, чтобы разработчик закрыл в `tests/` каждое свойство разовой планки, которое не держит долгоживущий файл (skills/test-authoring.md, ADR-0018 п. 3).
