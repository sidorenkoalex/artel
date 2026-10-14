---
task: 01M4VBTTH9TT5R74W2ZGKKYZK2
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: DoctorDurationTest: точная граница калибровки и устойчивость к нагрузке

## Соответствие SPEC

Фаза A: план покрывает все шесть требований тремя проверяемыми шагами; подход использует публичный журнал и настоящий doctor, не меняя продуктовый код, лимиты либо гейты. Фактический diff соответствует заявленному влиянию: два тестовых модуля; карта кода сгенерирована отдельно.

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Исправлен счёт новой серии (`k - 1` после первой записи workers=2); три независимых сценария проверяют высокую восьмую, задержанную девятую и задержанную десятую записи. |
| 2 | OK | Алгоритмическая часть пишет полный контролируемый набор метрик через `acceptance.journal_suite_metrics` и пять раз фильтрует результат настоящего `self.doctor_checks()` по точному target. |
| 3 | OK | Неизменённый workers=1-сценарий сохранён; отдельный workers=2-сценарий проверяет результат, запись, поля и точную нормализацию. |
| 4 | OK | Все 15 форм сохранены: десять прямых утверждений и пять `assertTrue(checks)` после этапов серии; `checks` относятся к `suite-duration:<target>`. |
| 5 | OK | Константы, AC6 и AC8 не менялись; новые детерминированные сценарии покрывают границу, нормализацию, смену workers и сигнал после калибровки. |
| 6 | OK | Дифф соответствует матрице неослабления SPEC: прежние свойства перенесены без ослабления, исторический перечень прошлой задачи не затронут. |

## Замечания

Нет.

## Реестр замечаний

Замечаний этой и предыдущих итераций нет.

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved

## Проверено исполнением

- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4VBTTH9TT5R74W2ZGKKYZK2` — 6 passed за 7.52 с.
- `python3 -m unittest tests.test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.DoctorDurationTest.test_ac7_duration_calibrates_and_ignores_worker_changes tests.test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.DoctorDurationTest.test_duration_high_eighth_has_no_signal tests.test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.DoctorDurationTest.test_duration_delayed_ninth_triggers tests.test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.DoctorDurationTest.test_duration_normal_ninth_then_delayed_tenth_triggers tests.test_01m4araxf7vss5xz8c99bx8de2_suite_observation.SuiteObservationTest.test_gate_writes_workers_2_metrics` — 5 tests зелёные за 7.291 с.
- `python3 -m unittest tests.test_01m4araxf7vss5xz8c99bx8de2_doctor_duration tests.test_01m4araxf7vss5xz8c99bx8de2_suite_observation` — 11 tests зелёные за 42.317 с. Интеграционные предупреждения о близости к лимиту 4/5 с не были отказами.

## Предложения системе

Нет.
