---
task: 01M4P9PHCTT7TXWF422E3Y9GXN
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py, tests/test_liveness.py, orchestrator/liveness.py, docs/codebase-map.md, tests/
budget_usd: 25
---

# SPEC: Стабилизация двух тестов, краснящих CI под нагрузкой (full_suite_limit_runs, test_liveness)

## Контекст
Два теста стабильно зелёные по отдельности (локально 3 из 3 за ~5 с), но
краснят CI в полном наборе (~5000 тестов, xdist) на раннере GitHub —
11.10.2026 четыре случая (CI ветки 01M4MQAGRWMWR0GFDM9086P3TD, прогон
38123982463; CI main 513ec5da, прогон 38168246062, обе попытки; CI ветки
01M4M67SGNEYMN9F1C7XVX24XE, 38139177114; CI main c47f3c9a, 38139914132),
10.10 — `test_ac3` того же файла на CI мержа 01M4KAYMW2YRFB7G0442WFVSHA.

- `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py::ConfigLimitCutsGateRunTest::test_ac4_gate_run_without_subfield_is_cut_at_patched_config`
  (~381–405): предел C = `randint(3, 6)` с, пробник держится
  `randint(60, 80)` с; `self.assertTrue(self.events("start"))` падает
  «[] is not true» — прогон обрезан по пределу раньше, чем пробник
  записал старт (старт python и сбор pytest под нагрузкой дольше C). Тот
  же приём — у `ProfileLimitCutsGateRunTest::test_ac3_gate_run_is_cut_at_profile_limit_not_config`
  (~341–349, предел профиля `randint(3, 6)`), а также, по коду main, у
  `TimeoutSourceTextTest::test_ac6_*` и `TimeoutTextStartsTest::test_ac7_*`
  (предел 3–6 с) и `SuiteRunProfileLimitTest::test_ac5_*` (4–7 с);
  `test_ac3_profile_limit_above_config_lets_gate_run_finish` берёт C 2–3 с
  с иным ожиданием (пробник должен закончиться сам).
- `tests/test_liveness.py::GroupMemberCountPathTest::test_counts_members_exactly_when_ps_is_not_on_path`
  (~165–183): «1 != 2». `_spawn_group_with_child(sleep_sec=5.0)` (~51–69)
  — лидер и потомок спят 5 с; под нагрузкой подсчёт может прийти после
  выхода потомка либо `ps` не уложиться в `timeout=5`
  (`orchestrator/liveness.py::_group_member_count` ~94–111, запасной путь
  даёт нижнюю оценку 1).

## Требования
1. Причина каждого падения установлена по коду и, где можно, замером под
   нагрузкой (например, прогон файла параллельно с нагрузочным
   процессом) и записана в PLAN — не догадкой.
2. Данные и условия методов `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`,
   где прогон обрезается по пределу из config/профиля, — `test_ac4_gate_run_without_subfield_is_cut_at_patched_config`,
   `test_ac3_gate_run_is_cut_at_profile_limit_not_config` и иных методов
   файла с тем же приёмом (какие из них чувствительны — устанавливает
   требование 1) — изменены так, что проверка не зависит от скорости
   старта процессов под нагрузкой. Допустимо поднять нижнюю границу
   предела до уровня, где старт пробника гарантирован (с соразмерным
   `hold`), либо отсчитывать проверку старта иначе. Утверждения «пробник
   стартовал» и «отказ называет предел» сохраняются без ослабления.
3. Данные и условия `tests/test_liveness.py::GroupMemberCountPathTest::test_counts_members_exactly_when_ps_is_not_on_path`
   изменены так, что подсчёт делается, пока группа гарантированно из
   двух процессов (например, потомок живёт до явного завершения тестом,
   а не 5 с); утверждение «ровно 2» сохраняется.
4. Утверждения (`assert*`) существующих методов не удаляются и не
   ослабляются; вид утверждения не меняется. Смена литерала в
   утверждении допустима только перечнем раздела «Меняемое поведение»
   с дословными литералами — в этом SPEC такой смены нет (раздел
   отсутствует); понадобится — эскалация Оператору.
5. Если причина падения `test_liveness` — в коде пульта (например,
   `timeout=5` у `ps` в `orchestrator/liveness.py::_group_member_count`
   неоправданно мал), правка вносится в `orchestrator/liveness.py` с
   тестом; свойство «сбой `ps` не выдаётся за пустую группу» (живая
   группа при сбое `ps` даёт не 0) не ослабляется.
6. Время прогона каждого изменённого тестового файла растёт не больше
   чем на 30 с по сравнению с main.

## Критерии приёмки
AC-1. Изменённые методы `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`
(не меньше `test_ac4_gate_run_without_subfield_is_cut_at_patched_config` и
`test_ac3_gate_run_is_cut_at_profile_limit_not_config`) зелёные при
прогоне файла параллельно с нагрузочным процессом (N процессов
`python -c 'while 1: pass'` по числу ядер) не менее 5 раз подряд; в них
по-прежнему утверждается, что пробник стартовал и что отказ называет
предел C (или N).

AC-2. `tests/test_liveness.py::GroupMemberCountPathTest::test_counts_members_exactly_when_ps_is_not_on_path`
зелёный при прогоне файла параллельно с тем же нагрузочным процессом не
менее 5 раз подряд, с утверждением, что подсчёт равен ровно 2.

AC-3. Мутация «предел без подполя взят при импорте» (умолчание параметра
`timeout=config.FULL_SUITE_TIMEOUT_SEC` или константа модуля) после правки
по-прежнему краснит `test_ac4_gate_run_without_subfield_is_cut_at_patched_config`,
а мутация «гейт мержа берёт `config.FULL_SUITE_TIMEOUT_SEC`, а не предел
профиля» — `test_ac3_gate_run_is_cut_at_profile_limit_not_config`.

AC-4. Мутация «`ps` ищется только по PATH вызывающего» (без запасных
`/bin`, `/usr/bin`) после правки по-прежнему краснит
`test_counts_members_exactly_when_ps_is_not_on_path`; при правке
`orchestrator/liveness.py` подсчёт для живой группы при сбое `ps` (не
запустился, не ответил в срок, ненулевой код) не равен 0.

AC-5. Время прогона каждого изменённого тестового файла на ветке больше
времени его прогона на main не более чем на 30 с.

## Оценка объёма и деление
Сработали сигналы guard: «число затрагиваемых модулей/файлов» и, как
следствие, «прогноз диффа не дан». Первый сигнал — от упоминаний модулей
`orchestrator/*.py` по всему тексту SPEC, и пять из них — пути ТОЛЬКО ДЛЯ
ЧТЕНИЯ из раздела «Не входит» (`acceptance.py`, `fsm_merge_gate.py`,
`config.py`, `suite_run.py`) плюс `liveness.py`. Меняются не больше трёх
файлов: два тестовых файла и, условно (требование 5),
`orchestrator/liveness.py`; плюс регенерация `docs/codebase-map.md` при
правке `liveness.py`.

Прогноз диффа: 6 КиБ

Обоснование монолита (материал для решения Оператора): части по двум
файлам технически независимы и мержимы порознь, но каждая — правка
данных нескольких методов одного файла; деление удвоило бы число шагов
(SPEC, тесты, ревью) при планке бюджета $25 на задачу, а рамка ТЗ —
$25 на всё. Общий для обеих частей — один сценарий приёмки (прогон под
нагрузкой 5 раз подряд), задаваемый одной планкой.

## Не входит
- Команда повтора прогона CI main (отдельная строка копилки).
- Общий поиск нестабильных тестов по набору.
- Правка путей только для чтения: `orchestrator/acceptance.py`,
  `orchestrator/fsm_merge_gate.py`, `orchestrator/config.py`,
  `orchestrator/suite_run.py`, `tests/sandbox.py`,
  `tests/test_invariants.py`, `docs/invariants.md`, `docs/adr/`,
  `docs/operator-gates.md`, `docs/backlog.md`, `skills/`, `templates/`,
  `CLAUDE.md`, `roles.yaml`, `.github/`, `.artel/`.
- Смена вида утверждений, их удаление или ослабление — только вопросом
  Оператору с матрицей.
- Зелёный полный набор `tests/` и зелёный CI ветки — её держит пульт.

## Материалы
- ТЗ: `tasks/01M4P9PHCTT7TXWF422E3Y9GXN/TZ.md` (копилка 10.10 и 11.10,
  решение Оператора 11.10.2026).
- Код: `orchestrator/liveness.py::_ps_executable` (~85–91),
  `_group_member_count` (~94–111).
