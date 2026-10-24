---
task: 01M5QR5BSEX9T95YC11KEERMT6
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Скорость набора — уборка `full_suite_lock` без ожидания предела, замер записью в `doctor_duration` ac8

## Подход

Две независимые правки в двух тестовых файлах по мандату Оператора 24.10
(ANSWER-1).

1. `tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py:357`,
   `LockSandbox.stop_everything`: `self.release(path.name)` →
   `self.release(path.name.removeprefix("tree-"))`. Каталог дерева —
   `tree-<метка>` (`tree`, :274), пробник ждёт `release-<метка>`
   (`release_path`, :249–250). Прочие строки уборки (сигнал `linger`,
   ожидание до 10 с, `SIGKILL` групп, сверка записей pid) не тронуты.
2. `tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py`,
   `test_ac8_ack_restarts_calibration_after_signal`: из 17 `measured_run`
   остаётся один — первый вызов калибровки `measured_run(0.01)`; дальше
   7× `journal_measurement(1.12)` (0,28 с на тест, образец :168–246),
   сигнал `journal_measurement(1.92)` (0,48 с на тест — образец
   `test_duration_delayed_ninth_triggers`), после `ack_alert` —
   8× `journal_measurement(1.12)`. Утверждения, докстринг и «Ловит
   мутацию» прежние; остаток файла не тронут.

**Значения и позиция настоящего прогона.** Порог сигнала
(`orchestrator/doctor/suite_duration.py:58–62`) — медиана
`seconds_per_test` первых k=8 записей окна × (1 + 0,6). В окне 8 записей:
настоящий прогон и 7 записей 0,28 с на тест. Медиана восьми чисел, из
которых семь равны 0,28, равна 0,28 при любом значении настоящего
прогона (4-е и 5-е по порядку значения — оба 0,28), поэтому порог —
0,448 с на тест, а сигнал 0,48 > 0,448 открывается. Настоящий прогон
калибровку не сдвигает, разброс его длительности (pytest-старт на 4
теста — доли секунды на тест) на порог не влияет; позиция первым —
по решению гейта SPEC (ANSWER-1, п. 4). Замер: тест ac8 зелёный после
правки (`pytest …doctor_duration.py` — 6 passed), планка AC-3 зелёная.
После ack окно пересчитывается от `ack_ts` (`_reference`, :12–17):
8 записей ≤ k → «калибровка», сигнала нет.

**ac9.** SPEC (Контекст) относит потерю 10 с и к `test_ac9_…`, но ac9
(`MergeGateOutcomesTest`, :962) не порождает пробников `tree-*`: его
набор лежит в `tests/` репозитория песочницы (`prepare`, :885), дочерних
процессов `spawn` нет, цикл ожидания уборки сразу пуст. Правка его не
касается; время ac9 определяется пределом `FULL_SUITE_TIMEOUT_SEC`
от зерна (3–6 с, :976). Сравнение на одном зерне — ниже (≈ равно,
разница — шум). Планка AC-6 для ac9 зелёная: к снятию групп живых
процессов нет.

## Шаги

1. Правка `stop_everything` (одна строка) + замер времени ac6/ac9/ac11
   до и после.
2. Правка ac8 + замер времени до и после.
3. Патчи `mutation-001.diff`, `mutation-002.diff` в каталоге документов;
   `mutation-run --ref base` и `--ref worktree` с `--wait-lock 4`.
4. Карта `python3 scripts/codebase_map.py` (сменился только
   `built_at_sha`), планка `plank-run`, guard.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2 |
| 3 | 3 |
| 4 | 1, 2 |
| 5 | 1–4 |

## Время до и после (требование 4, AC-6)

Прогоны адресные, `-p no:xdist`, по одному разу; длительность — фаза
`call` из `--durations=0`.

Без фиксации зерна (одна сессия pytest, 4 узла):

| Тест | До | После |
|---|---|---|
| `test_ac6_wait_over_limit_is_not_started_without_pytest` | 16,67 с | 5,74 с |
| `test_ac9_timeout_is_refused_as_timeout_not_as_broken_appendix` | 4,19 с | 6,24 с (предел от другого зерна) |
| `test_ac11_not_started_is_refused_with_holder` | 16,78 с | 6,66 с |
| `test_ac8_ack_restarts_calibration_after_signal` | 19,93 с | 7,31 с |

На одном зерне песочницы 12345 (запускатель `seeded_timing.py` в
каталоге документов подменяет `random.randrange(1 << 30)` — зерно
`LockSandbox.setUp`, :193; «до» — та же правка временно откачена в
рабочей копии):

| Тест | До | После |
|---|---|---|
| `test_ac6_wait_over_limit_is_not_started_without_pytest` | 15,26 с | 5,60 с |
| `test_ac9_timeout_is_refused_as_timeout_not_as_broken_appendix` | 8,86 с | 8,77 с |
| `test_ac11_not_started_is_refused_with_holder` | 17,25 с | 7,25 с |

После правки уборка `full_suite_lock` не ждёт предел: планка
`test_ac6_cleanup_does_not_wait_out_limit` (все три параметра) зелёная —
к первому `kill_group` ни один дочерний процесс не работает, сверка pid
не находит живых для `SIGKILL`. Все тесты обоих файлов: `python3 -m
pytest tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py
tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py` — 23 passed
in 142.30s.

## Мутации (требование 3, AC-5)

- `mutation-001.diff` — заявка ac8: `_series` берёт `reference = None`
  вместо `_reference(conn, target)`, т. е. после ack перечитывает старую
  калибровку и сразу повторно открывает тот же `suite.duration`.
- `mutation-002.diff` — выбор записей окна: `_series` возвращает
  `values[start + 1:]` вместо `values[start:]` (сдвиг на одну запись при
  отсечении окна по числу процессов xdist) — окно короче на одну, на
  девятой записи калибровка ещё не закрыта, сигнал не открывается.

Оба патча проверены `git apply --check` на рабочем дереве.

Команда «до» (база ветки):
`python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py mutation-run 01M5QR5BSEX9T95YC11KEERMT6 --ref base --tests tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py --wait-lock 4 --wait 5`
(первые три вызова отказали: замок машины держал suite-run задачи
01M5QAEPC6RF097YQ43T3Y56D9, ожидание 4 мин истекало; четвёртый
дождался замка). Вывод дословно:

```
[01M5QR5BSEX9T95YC11KEERMT6] mutation-run: замок машины держит прогон suite-run задачи 01M5QAEPC6RF097YQ43T3Y56D9 (pid 12046) — жду его освобождения не дольше 4 мин, проверка раз в 10 с
[01M5QR5BSEX9T95YC11KEERMT6] mutation-run: прогон №1 (патчи 1-2, ref base) запущен фоном, pid 20808; лог: /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5QR5BSEX9T95YC11KEERMT6/01M5QR5BSEX9T95YC11KEERMT6-mutation-run-1.log; таблица: /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5QR5BSEX9T95YC11KEERMT6/01M5QR5BSEX9T95YC11KEERMT6-mutation-run-1.mutations.tsv
--- таблица /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5QR5BSEX9T95YC11KEERMT6/01M5QR5BSEX9T95YC11KEERMT6-mutation-run-1.mutations.tsv ---
# mutation-run №1 задачи 01M5QR5BSEX9T95YC11KEERMT6
# источник патчей: каталог на диске
# ревизия прогона: base 9c0e8b8c74393d4c456fa114b8c125e3348919b8
# тесты: tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py
# рабочих процессов: auto
# патч 1 mutation-001.diff sha256 bce34b4d00fd9f34d3b3d34520c9782cb6e0b0e572e27aaa45c32e2e292e7569
# патч 2 mutation-002.diff sha256 f49af29cf56720379458cc4ecaa8b0097d41b8baebba4923b26f048dde3577f4
номер	исход	узлы
1	убита	tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py::DoctorDurationTest::test_ac8_ack_restarts_calibration_after_signal
2	убита	tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py::DoctorDurationTest::test_duration_delayed_ninth_triggers,tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py::DoctorDurationTest::test_ac7_duration_calibrates_and_ignores_worker_changes,tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py::DoctorDurationTest::test_ac8_ack_restarts_calibration_after_signal
[01M5QR5BSEX9T95YC11KEERMT6] mutation-run №1: прогнано патчей 2 (убита: 2); таблица: /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5QR5BSEX9T95YC11KEERMT6/01M5QR5BSEX9T95YC11KEERMT6-mutation-run-1.mutations.tsv; лог: /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5QR5BSEX9T95YC11KEERMT6/01M5QR5BSEX9T95YC11KEERMT6-mutation-run-1.log
```

Команда «после» (рабочая копия с правкой):
`python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py mutation-run 01M5QR5BSEX9T95YC11KEERMT6 --ref worktree --tests tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py --wait-lock 4 --wait 5`.
Вывод дословно:

```
[01M5QR5BSEX9T95YC11KEERMT6] mutation-run: прогон №2 (патчи 1-2, ref worktree) запущен фоном, pid 22880; лог: /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5QR5BSEX9T95YC11KEERMT6/01M5QR5BSEX9T95YC11KEERMT6-mutation-run-2.log; таблица: /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5QR5BSEX9T95YC11KEERMT6/01M5QR5BSEX9T95YC11KEERMT6-mutation-run-2.mutations.tsv
--- таблица /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5QR5BSEX9T95YC11KEERMT6/01M5QR5BSEX9T95YC11KEERMT6-mutation-run-2.mutations.tsv ---
# mutation-run №2 задачи 01M5QR5BSEX9T95YC11KEERMT6
# источник патчей: каталог на диске
# ревизия прогона: worktree 9c0e8b8c74393d4c456fa114b8c125e3348919b8
# тесты: tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py
# рабочих процессов: auto
# патч 1 mutation-001.diff sha256 bce34b4d00fd9f34d3b3d34520c9782cb6e0b0e572e27aaa45c32e2e292e7569
# патч 2 mutation-002.diff sha256 f49af29cf56720379458cc4ecaa8b0097d41b8baebba4923b26f048dde3577f4
номер	исход	узлы
1	убита	tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py::DoctorDurationTest::test_ac8_ack_restarts_calibration_after_signal
2	убита	tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py::DoctorDurationTest::test_duration_delayed_ninth_triggers,tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py::DoctorDurationTest::test_ac7_duration_calibrates_and_ignores_worker_changes,tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py::DoctorDurationTest::test_ac8_ack_restarts_calibration_after_signal
[01M5QR5BSEX9T95YC11KEERMT6] mutation-run №2: прогнано патчей 2 (убита: 2); таблица: /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5QR5BSEX9T95YC11KEERMT6/01M5QR5BSEX9T95YC11KEERMT6-mutation-run-2.mutations.tsv; лог: /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5QR5BSEX9T95YC11KEERMT6/01M5QR5BSEX9T95YC11KEERMT6-mutation-run-2.log
```

Контрольные прогоны без патча зелёные на обоих ref (`6 passed`).
Строки падения ac8 из логов патчей:

- №1 (base), p001: `FAILED tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py::DoctorDurationTest::test_ac8_ack_restarts_calibration_after_signal - AssertionError: [<sqlite3.Row object at 0x10af0aec0>] is not false` — `:268`, `assertFalse(self.triggers())` после `ack_alert`.
- №1 (base), p002: `FAILED tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py::DoctorDurationTest::test_ac8_ack_restarts_calibration_after_signal - AssertionError: 0 != 1` — `:265`, `assertEqual(len(found), 1)`.
- №2 (worktree), p001: `FAILED tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py::DoctorDurationTest::test_ac8_ack_restarts_calibration_after_signal - AssertionError: [<sqlite3.Row object at 0x10b3a47f0>] is not false` — `:271`, то же утверждение после ack (строка сдвинута на 3 комментарием и разбивкой калибровки).
- №2 (worktree), p002: `FAILED tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py::DoctorDurationTest::test_ac8_ack_restarts_calibration_after_signal - AssertionError: 0 != 1` — `:268`, `assertEqual(len(found), 1)`.

Каждая мутация убита одним и тем же утверждением ac8 до и после правки.
Дерево `orchestrator/` прогонов одно: обе ревизии —
9c0e8b8c74393d4c456fa114b8c125e3348919b8,
`git rev-parse 9c0e8b8c…:orchestrator` = ee653f0db27be636e0dca19fb20380546c46bc83,
`git diff --stat HEAD -- orchestrator` в рабочей копии пуст. sha256
патчей в шапках обоих прогонов совпадают.

## Влияние на систему

Меняются только два тестовых файла (зона задачи) и карта (вывод
генератора). Код пульта `orchestrator/` не тронут. Утверждения тестов не
меняются; свойство «настоящий полный прогон пишет замер» держит первый
`measured_run(0.01)` ac8; «запись → сигнал» держат записи замера ac8 и
соседние тесты :168–246 (матрица ANSWER-1, строка 3). Мандат на
`doctor_duration` — ANSWER-1. Откат — revert merge-коммита. Временные
файлы шага — только в каталоге документов (`seeded_timing.py`); замок
ждали только `--wait-lock`.

## Риски

- Время ac9 зависит от зерна; правка его не ускоряет (см. «Подход»).

## Предложения системе

- SPEC «Контекст» отнёс ожидание предела уборки к ac9, хотя ac9 не
  порождает пробников `tree-*` — шпион процессов полезно сверять с
  наличием `spawn` в тесте.
- Время тестов `full_suite_lock` зависит от случайного зерна; сравнение
  «до/после» без фиксации зерна шумит на секунды — команды пульта для
  адресного замера с заданным зерном нет (обход — `seeded_timing.py`).
