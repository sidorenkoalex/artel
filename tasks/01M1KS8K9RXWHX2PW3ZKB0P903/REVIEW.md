---
task: 01M1KS8K9RXWHX2PW3ZKB0P903
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 3
---

# REVIEW: Оценка объёма задачи и решение о делении на этапе SPEC

## Фаза A — гейт плана

Инкрементальный diff пакета от заявленного sha (`00e32aaf...`) не
собрался («Invalid symmetric difference expression») — этого sha нет
в репозитории ни как объекта (`git cat-file -t` — «could not get
object info»), ни в истории `REVIEW.md` задачи. Восстановил диапазон
вручную: последний коммит, где `REVIEW.md` реально получил
`changes_requested` итерации 1, — `034e7820`; сверял diff `034e7820..
HEAD` по файлам зоны задачи (`git diff --stat`/`git diff` с явным
списком путей) — пустой диапазон не был бы поводом считать ветку
неизменной (review-checklist, «Инкрементальный diff пакета»), но в
данном случае диапазон оказался непустым и содержательным (см.
«Проверено исполнением»).

Рабочее дерево `tasks/01M1KS8K9RXWHX2PW3ZKB0P903/` в момент старта
ревью было удалено (`git status` — все файлы `D`) — известный
восстановимый класс, не признак дефекта; восстановлено `git checkout
--`, не переписыванием.

1. Таблица «Покрытие требований» PLAN.md по-прежнему полна (шаг 10
   добавлен к требованиям 1/3/6).
2. Изменения итерации 2 (шаг 10) — точечная правка двух замечаний
   major, не расширяет объём: `scripts/guard.py` (регэксп/докстринги),
   28 докстрингов тестов, разметка реестра. Размер MR разумный.
3. Подход не конфликтует с конвенциями: `git apply --check
   protected-paths.patch` по-прежнему проходит чисто, защищённые пути
   не тронуты правкой итерации 2. Полный diff ветки (`main...HEAD`,
   зона `orchestrator/`, `scripts/`, `docs/`, `tests/`) — ровно
   заявленные 9 файлов, побочных изменений нет.

Замечаний к плану как таковому нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Все шесть сигналов проверены заново после R1-F1: `_zone_paths` теперь ищет `ZONE_PATH` по ВСЕМУ тексту SPEC (не по несуществующему разделу «## Зоны»). Прогнал `guard.split_signal_names` на реальном `tasks/01M1KS8K9RXWHX2PW3ZKB0P903/SPEC.md` — находит `orchestrator/config.py`, `scripts/guard.py` (2 пути; сигнал «модулей/файлов» не срабатывает, т.к. < 5, что корректно) — сигнал больше не мёртвый код, реально читает практический текст SPEC. |
| 2 | OK | Без изменений с итерации 1 — `templates/SPEC.md` (патч) несёт секцию «Оценка объёма и деление» (AC-4). |
| 3 | OK | `split_assessment_errors` отказывает и называет сигналы (AC-5/AC-6/AC-7); юнит- и приёмочные тесты зелёные. |
| 4 | OK | `docs/operator-gates.md`, пункт 6 — без изменений (AC-8/AC-9). |
| 5 | OK | `skills/spec-authoring.md` (патч) — без изменений (AC-10/AC-11). |
| 6 | OK | `orchestrator/report.py` — без изменений (AC-12). |
| 7 | OK | Константы `orchestrator/config.py` — без изменений (AC-1). |

## Замечания

Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | scripts/guard.py:614-621,665-670,705,720-724 | AC-1/AC-3 читали несуществующий на практике раздел `## Зоны` SPEC | 2 из 6 сигналов требования 1 не срабатывали ни для одного реального SPEC | Проверил суть исправления, не только диф: `ZONES_SECTION` и `_zone_text` действительно удалены (grep обоих имён по scripts/guard.py, tests/, orchestrator/ — 0 совпадений), `_zone_paths` вызывает `ZONE_PATH.findall(text)` по всему аргументу без предварительной вырезки раздела. Прогнал на реальном SPEC этой задачи (см. «Соответствие SPEC», требование 1) — сигнал теперь находит пути практически, не только в фикстуре `_sandbox.py`. `test_ac1_*`/`test_ac3_*` (залоченная планка) и `tests/test_guard_split_signals.py::ZoneFilesSignalTest`/`InvariantMechanismSignalUnitTest` зелёные. Замечание закрыто по сути, перевожу в `accepted`. |
| R1-F2 | accepted | tests/test_guard_split_signals.py, tests/test_split_assessment_merge_gate.py | 28 юнит-тестов без докстринг-заявки `Ловит мутацию: …` | ревьювер не мог свериться с заявленной мутацией; будущее ослабление сигнала некому было ловить по контракту | Прочитал файл `tests/test_guard_split_signals.py` целиком: все 23 тестовых метода покрыты заявкой — где сценарий одинаков внутри класса (`ZoneFilesSignalTest`, `AcCountSignalTest`, `BudgetSignalTest` — по 2 метода «ниже/на пороге»), докстринг на уровне класса корректно описывает границу и сравнение `>=`; там, где сценарий различается («DiffForecastSignalTest», «RequiresSplitAssessmentTest», «SplitAssessmentErrorsTest», «ClosedTaskExceptionTest» — 15 методов), докстринг на уровне метода, каждый называет конкретную мутацию (сдвиг границы, инверсия сравнения, выпавшая проводка, безусловное срабатывание) и наблюдаемое следствие — не пересказ имени метода. То же для `SnapshotSplitAssessmentTest` (5 методов, все с заявкой). Сверил заявленные границы (`>=`) с фактическим кодом (`grep -n "SPLIT_SIGNAL_.*>="  scripts/guard.py`) — совпадает. `grep -c "Ловит мутацию" tests/test_guard_split_signals.py tests/test_split_assessment_merge_gate.py` — 20 и 5 (класс-докстринги считаются по одному на класс, покрывают 23+5=28 методов без пропусков). Замечание закрыто по сути, перевожу в `accepted`. |

## Вердикт

`approved` — 0 blocker/major/minor. Оба замечания итерации 1
(R1-F1, R1-F2) исправлены по сути и переведены в `accepted`; реестр
замечаний закрыт целиком.

## Проверено исполнением

- `git checkout -- tasks/01M1KS8K9RXWHX2PW3ZKB0P903/` — рабочее дерево
  задачи было пустым на старте ревью (известный класс — восстановлено
  чтением, не переписыванием).
- `git diff 034e7820..HEAD -- scripts/guard.py tests/test_guard_split_signals.py
  tests/test_split_assessment_merge_gate.py orchestrator/config.py
  orchestrator/store.py orchestrator/fsm.py orchestrator/report.py
  docs/operator-gates.md tasks/01M1KS8K9RXWHX2PW3ZKB0P903/` — реконструировал
  инкрементальный diff вручную (заявленный в пакете sha `00e32aaf...`
  не существует в репозитории); 419 строк, ровно правка шага 10
  (guard.py + 28 докстрингов + PLAN/REVIEW), побочных файлов нет.
- `git diff --stat main...HEAD -- orchestrator/ scripts/ docs/ tests/
  templates/ skills/` — весь diff задачи от main: 9 файлов, совпадает
  с зоной, заявленной в PLAN.md.
- `python3 scripts/guard.py --all` — «GUARD: ок (425 файлов)».
- `python3 -m unittest discover -s tests` (полный прогон) — 1415
  тестов, `OK` (рост против 1380 итерации 1 — параллельные задачи в
  проекте, не регрессия этой ветки).
- `python3 -m unittest tests.test_guard_split_signals
  tests.test_split_assessment_merge_gate -v` — 28 тестов, все `ok`,
  докстринги «Ловит мутацию» видны в выводе `-v` для каждого метода.
- `python3 -m unittest discover -s
  tasks/01M1KS8K9RXWHX2PW3ZKB0P903/acceptance_tests -p "test_*.py" -v`
  — 16 тестов, все `ok` (залоченная приёмочная планка зелёная).
- `git apply --check tasks/01M1KS8K9RXWHX2PW3ZKB0P903/protected-paths.patch`
  — применяется чисто на текущем дереве.
- `python3 scripts/codebase_map.py --check` — карта свежая
  (расхождений по содержимому нет; случайно тронутую `built_at_sha`
  откатил `git checkout -- docs/codebase-map.md`).
- `grep -n "ZONES_SECTION\|_zone_text" scripts/guard.py tests/
  orchestrator/` — 0 совпадений (мёртвый код действительно удалён,
  основание закрытия R1-F1).
- `python3 -c "..."` (guard.split_signal_names/_zone_paths на реальном
  `tasks/01M1KS8K9RXWHX2PW3ZKB0P903/SPEC.md`) — находит пути
  `orchestrator/config.py`, `scripts/guard.py` по всему тексту SPEC
  (без раздела «## Зоны») — сигнал требования 1 подтверждённо
  достижим на практике, не только в фикстуре планки.
- `grep -c "Ловит мутацию" tests/test_guard_split_signals.py
  tests/test_split_assessment_merge_gate.py` — 20 и 5; прочитал
  `tests/test_guard_split_signals.py` целиком, сверил, что все 23
  метода покрыты (класс- или метод-уровня докстрингом) — основание
  закрытия R1-F2.

## Предложения системе

- Пакет ревью этой итерации нёс sha предыдущего вердикта
  (`00e32aaf2c15059ffb72260275b29b9d2b53e8fe`), которого нет в
  репозитории — `git cat-file -t` вернул «could not get object info»,
  а `git diff <sha>...HEAD` — «Invalid symmetric difference
  expression». Класс уже описан в скиле («Инкрементальный diff пакета
  — пустой не значит без изменений»), но это конкретный случай хуже
  пустого diff: сборка diff падает с ошибкой, а не молча возвращает
  пусто, и для пустого «не собрался» сообщения в пакете (что здесь и
  произошло) скил не даёт явной инструкции отличить «diff пуст» от
  «diff не собрался вовсе» — стоит уточнить формулировку, чтобы
  ревьювер не тратил цикл на диагностику несуществующего sha.
