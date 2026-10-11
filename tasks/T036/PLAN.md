---
task: T036
type: plan
author_role: developer
status: ready        # draft | ready | approved
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# PLAN: Merge-последовательность merge_gate через gitcmd.git

## Подход

Чистый перевод вызова: тело цикла `merge_gate` в `orchestrator/fsm.py`
сейчас гоняет голый `subprocess.run(["git", ...], cwd=config.ROOT,
capture_output=True, text=True)` — ровно то же самое, что уже делает
`gitcmd.git(*args)` (`orchestrator/gitcmd.py:9-18`). Замена — вызвать
`gitcmd.git(*cmd[1:])` вместо `subprocess.run(cmd, cwd=config.ROOT,
capture_output=True, text=True)`, где `cmd` — тот же кортеж, что и
сейчас (без первого элемента `"git"`, который `gitcmd.git` подставляет
сам). Список из четырёх кортежей команд (checkout/pull/merge/push) не
меняется ни по составу, ни по порядку, ни по аргументам — меняется
только то, чем каждая команда исполняется. `res.returncode` и
`res.stderr` читаются так же, как раньше (`gitcmd.git` возвращает тот
же `subprocess.CompletedProcess`), поэтому проверка отказа и текст
журнала «merge FAILED» с обрезкой `stderr` до 500 символов остаются
байт-в-байт.

Модуль `subprocess` в `fsm.py` после правки: пробежка `grep -n
"subprocess" orchestrator/fsm.py` перед коммитом покажет только
`import subprocess`, если он больше нигде не используется — тогда
импорт удаляется, иначе (используется где-то ещё в файле) остаётся.
Это единственная развилка в реализации, разрешается по факту в момент
правки, не меняет требований SPEC.

Тесты приёмки (`tasks/T036/acceptance_tests/test_merge_gitcmd.py`) уже
залочены (T023) и патчат `gitcmd.subprocess.run`, а не
`fsm.subprocess.run` — значит рабочий код обязан звать `gitcmd.git`, а
не собственный `subprocess.run`: тесты и являются проверкой требования 1
(AC-1 вдобавок ловит это статическим AST-разбором `fsm.py`).

## Шаги

1. В `orchestrator/fsm.py` (`merge_gate`) перевести четыре вызова
   `subprocess.run(["git", ...])` на `gitcmd.git(*args)`; убрать
   неиспользуемый `import subprocess`, если он более нигде в файле не
   нужен. Прогнать приёмочные тесты T036 и весь `unittest discover -s
   tests`. Один MR.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 |
| 6 | 1 |

## Влияние на систему

Правка ограничена веткой `merge_gate` в `orchestrator/fsm.py` — самой
опасной последовательности системы (реальный merge в `main`).
Поведение не меняется (те же команды, тот же `cwd`, та же обработка
`returncode`/`stderr`), поэтому риск для инвариантов минимален: это
смена механизма вызова git на уже существующую и протестированную
обёртку (`gitcmd.git` используется `ci.py`, `cleanup.py`, `doctor.py`,
`fixation.py`, `projects.py`, `review.py`, `runner.py` — прецедентов
достаточно, чтобы не считать её экспериментальной). Тесты, гейты,
лимиты и guard-проверки не трогаются и не ослабляются: правки тестов —
только замена пути патча (`gitcmd.subprocess.run` вместо
`fsm.subprocess.run`) в тех тестах, что явно мокали git-вызов внутри
`merge_gate` (`tests/test_invariants.py` — сценарии и ассерты те же).
Соседние ветки `cmd_approve` (`ci.branch_status`, прочие состояния) не
затрагиваются. Откат — вернуть четыре строки к прежнему
`subprocess.run(...)`, `git diff` локализован в одном методе.

## Риски

Единственный практический риск — пропустить тест, который до сих пор
патчит `fsm.subprocess.run` для этой ветки, и получить неверяемый
зелёный прогон (тест перестаёт что-либо проверять, а не падает).
Закрывается тем же способом, что и приёмочные тесты: `grep -rn
"fsm.subprocess" tests/` после правки должен быть пуст для сценариев
`merge_gate`.
