---
task: 01M1SG9T962WJJ31S282GWM0EN
type: plan
author_role: developer
status: ready
schema_version: 4
---

# PLAN: гейты зон и ёмкости сравнивают ветку с точкой расхождения от origin/main

## Подход

Одна точка правды для базы сравнения — `orchestrator/gitcmd.py::diff_base(branch)`:
merge-base ветки задачи с `refs/remotes/origin/<MAIN_BRANCH>`, если такой
ref заведён в репозитории (проверка через `git rev-parse --verify --quiet`
— чтение уже существующего локального ref, без `fetch`/`ls-remote`, тесты
не выходят в сеть), иначе — merge-base с локальным `config.MAIN_BRANCH`.
`None` — git не ответил ни на проверку ref, ни на саму команду
`merge-base`. Рядом — `diff_base_source(branch)`, независимо повторяющая
тот же критерий наличия ref ради текстового источника для журнала
(«origin/main» / локальный «main»): `diff_base` возвращает по AC-1 только
`str | None`, второе значение (источник) несёт отдельная функция, а не
кортеж — иначе сигнатура разошлась бы с буквальным текстом AC-1.

Три потребителя переключены на эту базу:
- `fsm_advance._zones_gate_refuses` — вместо двухточечного
  `gitcmd.diff_names(config.MAIN_BRANCH, branch)` берёт
  `gitcmd.diff_names(gitcmd.diff_base(branch), branch)`;
- `fsm_advance._capacity_gate_refuses` — оба `git diff` (снимок кода и
  снимок артефактов) идут от той же базы;
- `review.review_package` при `iteration == 1` — база `gitcmd.diff_base(branch)`
  с откатом на `config.MAIN_BRANCH`, если git не ответил (пакет не гейт,
  отказать переходу вместо ревьювера некому — то же вырожденное решение,
  что уже применяет `previous_verdict_sha` при нераспознанном sha).
  Инкрементальный diff (`iteration > 1` с непустым `prev_sha`) и
  вырожденный откат `iteration > 1` без `prev_sha` (`base = config.MAIN_BRANCH`,
  legacy-поведение) этой задачей не тронуты — оба ветвятся раньше вызова
  `diff_base` и не видят его вовсе (AC-4, требование «не входит»/2).

`diff_base` вернула `None` — оба гейта (`_zones_gate_refuses`,
`_capacity_gate_refuses`) отказывают fail-closed тем же приёмом
(`store.journal` + `print`), что уже применяется на сбое
`diff_names`/`git diff` сегодня (ADR-0002, «неизвестный статус — это
нельзя»). Журнальная запись финального отказа обеих гейтов (не
промежуточного «git не ответил на определение базы») называет sha
merge-base и источник (`gitcmd.diff_base_source`) — Оператор видит, с чем
реально сравнивали.

## Шаги

1. `orchestrator/gitcmd.py`: `_origin_main_ref_exists()` (приватный общий
   критерий), `diff_base(branch)`, `diff_base_source(branch)`.
2. `orchestrator/fsm_advance.py`: `_zones_gate_refuses` и
   `_capacity_gate_refuses` — база через `gitcmd.diff_base`, fail-closed на
   `None`, sha+источник в финальном журнальном сообщении отказа.
3. `orchestrator/review.py`: `review_package` — база `iteration == 1` через
   `gitcmd.diff_base` с откатом на `config.MAIN_BRANCH`; инкрементальная и
   «нет prev_sha» ветки не меняются.
4. `tests/test_review_package.py`: общий `FakeGit` этого файла не моделирует
   `refs/remotes/origin/<MAIN_BRANCH>`/`merge-base` — без правки все
   существующие тесты, зовущие `review_package` при `iteration == 1`
   (например `test_stat_and_diff_are_taken_against_main`), заработали бы
   через настоящий вызов `gitcmd.diff_base` внутри общего диспетчера
   `FakeGit.__call__` и получили бы мусорную «базу» вместо литерала
   `config.MAIN_BRANCH`, на который завязаны их ассерты. Добавлены две
   ветки диспетчера: `rev-parse --verify --quiet refs/remotes/origin/...`
   отвечает «ref отсутствует» (эта песочница не моделирует remote —
   корректная симуляция вырожденного случая, тот же приём, что уже несёт
   ветка для `refs/heads/` чуть выше), `merge-base` отвечает вторым
   аргументом как есть (запрошенная база), что при отсутствии origin-ref
   даёт байт-в-байт `config.MAIN_BRANCH` — существующие ассерты остаются
   верны без ослабления.
5. `python3 scripts/codebase_map.py` — `diff_base`/`diff_base_source`
   публичные, карта регенерирована тем же коммитом (conventions-core).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (diff_base — одна точка правды) | 1 |
| 2 (гейт зон/ёмкости/полный diff пакета — новая база) | 2, 3 |
| 3 (fail-closed на None) | 2 |
| 4 (журнал называет базу) | 2 |
| 5 (внешний target вне объёма) | 2, 3 (не тронуто — оба гейта и так пропускают внешний target раньше вызова `diff_base`) |

## Влияние на систему

Затронуты три существующих потребителя, все — в зоне задачи
(`orchestrator/fsm_advance.py`, `orchestrator/review.py`). Инкрементальный
diff ревью-пакета и вырожденный откат `iteration > 1` без `prev_sha`
намеренно не тронуты (AC-4, требование «не входит»/2) — база остаётся
`prev_sha`/`config.MAIN_BRANCH` соответственно, `diff_base` в этих ветках
не вызывается вовсе (проверено `acceptance_tests/test_ac4_...py`, мок
`gitcmd.diff_base` роняет `AssertionError` при вызове — тест зелёный).

Инвариант «тесты не выходят в сеть» (01M1QHQ277…) не ослаблен: `diff_base`
не зовёт `fetch`/`ls-remote`/`clone`/`push` — только чтение уже
существующего локального ref (`rev-parse --verify --quiet`) и
`merge-base`, обе команды чисто локальные; отдельный acceptance-тест
(`test_ac1_diff_base.py::test_ac1_never_invokes_network_git_subcommands`)
перехватывает `subprocess.run` и проверяет отсутствие сетевых подкоманд.

Fail-closed на gitcmd.diff_base -> None сохраняет прежний класс отказа
(ADR-0002) — оба гейта уже отказывали так же на сбое своих прежних
git-вызовов, здесь добавлена ровно одна новая точка сбоя перед ними, с
тем же журнальным приёмом.

Правка `tests/test_review_package.py::FakeGit` (шаг 4) — минимальная
достройка существующего диспетчера под два новых вызова
(`rev-parse .../refs/remotes/origin/...`, `merge-base`), без ослабления
ни одного существующего ассерта: полный прогон файла (117 тестов, вместе
с `tests/test_zones_gate.py` и `tests/test_capacity_gate.py`) зелёный.

Откат: правки локальны к трём файлам + regen карты + один тестовый мок;
`git revert` коммита задачи возвращает прежнее (двух-/трёхточечное с
`config.MAIN_BRANCH`) поведение без затрагивания соседних задач.

## Риски

- Реальный git-репозиторий с `refs/remotes/origin/main`, где эта ветка
  РЕАЛЬНО разошлась с origin (Оператор не подтянул) — `diff_base` возьмёт
  происхождение от origin, гейты станут строже локального `config.MAIN_BRANCH`
  для diff, посчитанного ДО подтяжки. Ожидаемо: подтяжка перед `verifying`
  и так гарантирует слияние origin в ветку задачи раньше входа в гейты
  (SPEC «Контекст»), сценарий out-of-scope здесь не возникает при штатном
  цикле FSM.

## Предложения системе

- `tests/test_review_package.py::FakeGit` — уже третий по счёту частный
  диспетчер `gitcmd.git`-заглушки в кодовой базе (`tests/sandbox.py::fake_git`,
  `fake_git_for`, этот) с похожей, но не общей структурой веток
  rev-parse/show/ls-tree. Общий параметризуемый фейк git с расширяемым
  набором подкоманд снял бы необходимость трогать чужой тестовый файл при
  каждой новой git-примитиве в `gitcmd.py` — класс «добавил примитив в
  gitcmd.py, чиню три независимых мока» уже повторился минимум дважды
  (эта задача, T029 упомянутый в докстринге `previous_verdict_sha`).
