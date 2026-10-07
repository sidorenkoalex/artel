---
task: 01M4ARAXF7VSS5XZ8C99BX8DE2
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Нагрузка машины в записи полного прогона и сигнал роста времени

## Подход

Измерение полного прогона собирается в `acceptance.run_full_suite`: монотонное время, load average до и после pytest, число xdist из вывода или команды, снимок `ps` на конце. Журналирование делает только вызывающий узел гейта, только для реально запущенного полного набора. По решению Оператора 07.10 (вариант В, возврат из verifying после CI 8baf5a00) требование 1 в части `suite-run` и AC-2 отменены: команда не меняет журнал шагов задачи. Она использует собранный снимок нагрузки только для строки отчёта о таймауте (требование 2, AC-5). Общий формат JSON используется сигналом `doctor` и текстом таймаута. Сигнал читает записи гейта по target, после последнего ack и только в непрерывном суффиксе с одинаковым числом процессов.

По [ANSWER-1.md](ANSWER-1.md) Оператор через `amend-tests` снял AC-2 и исправил AC-5 (лок `78865507`): отчёт `suite-run` сверяется с заданным снимком `os.getloadavg` без обращения к журналу. Исправленный тест уже в HEAD ветки (`d03109ad`); запись `suite-run` в журнал остаётся запрещённой решением Оператора.

## Шаги

1. Добавить сбор измерения и запись «прогон: время» на исходах гейта; добавить строку нагрузки при таймауте гейта и `suite-run`, не меняя журнал задачи из команды.
2. Добавить предупреждение нагрузки машины и сигнал `suite.duration` в `doctor`, константы порогов и юнит-тесты на углы разбора.
3. Прогнать планку, затронутые тесты, полный набор штатной командой пульта; обновить карту кодовой базы.

## Покрытие требований

| Требование SPEC | Шаг |
|---|---|
| 1–2 | 1; запись `suite-run` отменена решением Оператора 07.10, вариант В |
| 3–4 | 2 |
| 5 | Приложение ниже |
| 6 | Ряд ниже |

## Ряд полного прогона 02.10–07.10

Время — локальное время mtime файла лога; длительность и число тестов взяты из итоговой строки pytest. `xdist` — число из заголовка `workers [`; при его отсутствии стоит «нет в логе». Логи без итоговой строки не дают время на тест и в таблицу не включены.

| Дата и время | Секунды | Тестов | Секунд на тест | xdist процессов | Лог `.artel/logs/` |
|---|---:|---:|---:|---:|---|
| 02.10 11:02 | 140.82 | 3628 | 0.0388 | 14 | `01M3XR84299TD6V6E16D2PNXH4-fullsuite-1.log` |
| 02.10 11:13 | 179.60 | 3642 | 0.0493 | 14 | `01M3V4ZPB6HFDJ36MTDAQG5VNT-fullsuite-1.log` |
| 02.10 11:32 | 140.45 | 3635 | 0.0386 | 14 | `01M3XTF1CEBXT4J7P0EKG5J342-fullsuite-1.log` |
| 02.10 11:40 | 146.25 | 3648 | 0.0401 | 14 | `01M3SA3ANYZ7036AAGXZG753E3-fullsuite-1.log` |
| 02.10 11:56 | 156.73 | 3646 | 0.0430 | 14 | `01M3XVW94Z8E8R71XN7QWYMSP4-fullsuite-1.log` |
| 02.10 12:24 | 171.59 | 3651 | 0.0470 | 14 | `01M3XTF1CEBXT4J7P0EKG5J342-fullsuite-2.log` |
| 02.10 12:30 | 146.09 | 3654 | 0.0400 | 14 | `01M3XWR7140Q8C1XAFPZ9E854M-fullsuite-1.log` |
| 02.10 13:06 | 131.96 | 3655 | 0.0361 | 14 | `01M3XTFJCC5TG63FHW907GQM4D-fullsuite-1.log` |
| 02.10 13:30 | 141.02 | 3690 | 0.0382 | 14 | `01M3XTF5506GF43HD51ECE230T-fullsuite-1.log` |
| 02.10 14:27 | 134.57 | 3702 | 0.0364 | 14 | `01M3VFYP4RXBY0BG8D3A0B18HD-fullsuite-1.log` |
| 02.10 15:18 | 150.95 | 3711 | 0.0407 | 14 | `01M3Y7G6T3MK7A899521VF9N7B-fullsuite-1.log` |
| 02.10 15:28 | 152.34 | 3711 | 0.0411 | 14 | `01M3Y8570H9Y57YTP3M7E1AMHG-fullsuite-1.log` |
| 02.10 15:42 | 144.30 | 3737 | 0.0386 | 14 | `01M3Y753QNG6TS5C7MTJS1MEV6-fullsuite-1.log` |
| 02.10 16:06 | 156.08 | 3778 | 0.0413 | 14 | `01M3SF7DPFGEZ7VYEGGXGTX49E-fullsuite-1.log` |
| 02.10 16:43 | 152.79 | 3795 | 0.0403 | 14 | `01M3Y75X6K2ZMD85971TCWV41E-fullsuite-1.log` |
| 02.10 17:04 | 172.37 | 3795 | 0.0454 | 14 | `01M3Y75C9TY76083CG1PK00EM4-fullsuite-1.log` |
| 02.10 17:53 | 162.82 | 3824 | 0.0426 | 14 | `01M3Y75GCRESC2KDS9VPRJK4PS-fullsuite-1.log` |
| 02.10 18:11 | 207.05 | 3848 | 0.0538 | 14 | `01M3YCHP14179R32SFJVKQB32G-fullsuite-1.log` |
| 02.10 18:35 | 150.97 | 3862 | 0.0391 | 14 | `01M3YDHTY1Y67KB98FVSHREC4N-fullsuite-1.log` |
| 02.10 18:41 | 179.71 | 3849 | 0.0467 | 14 | `01M3YJ7VQ7CSBBPC8X84Z0YG3R-fullsuite-1.log` |
| 02.10 20:19 | 150.62 | 3876 | 0.0389 | 14 | `01M3YQB4KMADY0BET5N8279N6B-fullsuite-1.log` |
| 02.10 20:52 | 164.40 | 3878 | 0.0424 | 14 | `01M3YS928033B1QF89VN2N5KC3-fullsuite-1.log` |
| 02.10 21:03 | 163.73 | 3899 | 0.0420 | 14 | `01M3YCHS4F08VTV6XX10VF92H3-fullsuite-1.log` |
| 02.10 21:15 | 163.59 | 3901 | 0.0419 | 14 | `01M3YCHS4F08VTV6XX10VF92H3-fullsuite-2.log` |
| 02.10 22:38 | 166.54 | 3921 | 0.0425 | 14 | `01M3YCHVVEK14SK8GT4R0H7M2C-fullsuite-1.log` |
| 02.10 23:06 | 168.94 | 3932 | 0.0430 | 14 | `01M3YXYAX5PW9BM67MB4GK85D1-fullsuite-1.log` |
| 03.10 00:17 | 166.54 | 3938 | 0.0423 | 14 | `01M3Z5S8TQXPNH133XQ8K1978X-fullsuite-1.log` |
| 03.10 09:32 | 163.63 | 3918 | 0.0418 | 14 | `01M3Z2DMQRD0BD7AARFVTCVVG8-fullsuite-1.log` |
| 03.10 16:55 | 167.79 | 3940 | 0.0426 | 14 | `01M409YKM3QE5KVRGV0G94F5ZC-fullsuite-1.log` |
| 03.10 17:00 | 193.56 | 3940 | 0.0491 | 14 | `01M409YKM3QE5KVRGV0G94F5ZC-fullsuite-2.log` |
| 03.10 19:21 | 171.03 | 3951 | 0.0433 | 14 | `01M409YNSWACNFKNJE2X263ZSD-fullsuite-1.log` |
| 03.10 22:04 | 178.63 | 3973 | 0.0450 | 14 | `01M41AB597B330P2RCXCMVRZPE-fullsuite-1.log` |
| 03.10 23:10 | 158.99 | 3973 | 0.0400 | 14 | `01M41M6KGWA9PJ6G1KPDC6XY70-fullsuite-1.log` |
| 03.10 23:25 | 156.65 | 3974 | 0.0394 | 14 | `01M41M6KGWA9PJ6G1KPDC6XY70-fullsuite-2.log` |
| 04.10 00:33 | 149.47 | 3988 | 0.0375 | 14 | `01M41R4YAM4NGEQXW1FWH7T22M-fullsuite-1.log` |
| 04.10 01:02 | 152.59 | 3988 | 0.0383 | 14 | `01M41VH0Z3CQ0WY039SV1ERGMB-fullsuite-1.log` |
| 04.10 01:19 | 173.24 | 3992 | 0.0434 | 14 | `01M41W15BK20WBTD9TMBTSXNZA-fullsuite-1.log` |
| 04.10 01:27 | 167.63 | 3976 | 0.0422 | 14 | `01M41VTQJ9DSX64NFMFAF9W53B-fullsuite-1.log` |
| 04.10 01:35 | 179.16 | 3984 | 0.0450 | 14 | `01M41VTQJ9DSX64NFMFAF9W53B-fullsuite-2.log` |
| 04.10 02:26 | 181.98 | 4003 | 0.0455 | 14 | `01M41VTSE5N15P5P2WZF4GF2BQ-fullsuite-1.log` |
| 04.10 08:38 | 181.43 | 4012 | 0.0452 | 14 | `01M42NB9GKXNP74HAYEJ7C7CA8-fullsuite-1.log` |
| 04.10 09:01 | 170.21 | 4023 | 0.0423 | 14 | `01M42NBCADGSGTCBZB8NKBVDVH-fullsuite-1.log` |
| 04.10 20:51 | 284.13 | 4061 | 0.0700 | 14 | `01M42PENCS26D0656X8FR7DFA7-fullsuite-1.log` |
| 04.10 20:58 | 347.89 | 4062 | 0.0856 | 14 | `01M42PENCS26D0656X8FR7DFA7-fullsuite-2.log` |
| 04.10 22:22 | 203.01 | 4068 | 0.0499 | 14 | `01M443HPZBMJGCHVGV4JQN88RS-fullsuite-1.log` |
| 04.10 22:29 | 391.22 | 4069 | 0.0961 | 14 | `01M443HPZBMJGCHVGV4JQN88RS-fullsuite-2.log` |
| 04.10 22:42 | 207.48 | 4085 | 0.0508 | 14 | `01M443BPQEA9ZMJ3R50THNB1MF-fullsuite-1.log` |
| 04.10 23:10 | 189.27 | 4097 | 0.0462 | 14 | `01M443HV9SJYVYQTHJSQ87QV68-fullsuite-1.log` |
| 04.10 23:15 | 258.50 | 4097 | 0.0631 | 14 | `01M443HV9SJYVYQTHJSQ87QV68-fullsuite-2.log` |
| 04.10 23:44 | 339.79 | 4112 | 0.0826 | 14 | `01M446WN0V7JW4NSYQFKTBJ05C-fullsuite-1.log` |
| 05.10 00:36 | 359.01 | 4134 | 0.0868 | 14 | `01M446X1B7FB8JDMYFP5APWTVE-fullsuite-1.log` |
| 05.10 02:13 | 215.56 | 4147 | 0.0520 | 14 | `01M446WEVJXARR5CDED8RE9CCR-fullsuite-1.log` |
| 05.10 02:42 | 206.70 | 4185 | 0.0494 | 14 | `01M44EP0D47F498TEE08MNGBYT-fullsuite-1.log` |
| 05.10 03:26 | 210.20 | 4196 | 0.0501 | 14 | `01M446WV7S94FTZGJCGMPJ667F-fullsuite-1.log` |
| 05.10 03:45 | 216.81 | 4209 | 0.0515 | 14 | `01M44ENQCRK02T2MWZB9HC3XHH-fullsuite-1.log` |
| 05.10 04:34 | 220.43 | 4226 | 0.0522 | 14 | `01M44ENW1B73Z80PR73HP1C9CG-fullsuite-1.log` |
| 05.10 09:35 | 222.46 | 4238 | 0.0525 | 14 | `01M44EP4Q927DJXVX9YMMZ0B7V-fullsuite-1.log` |
| 05.10 10:24 | 250.32 | 4259 | 0.0588 | 14 | `01M45D29BQJE8FJYJA4JQWSYFZ-fullsuite-1.log` |
| 05.10 13:23 | 698.42 | 4326 | 0.1614 | 14 | `01M45FJD46BX45VHC36S4VS9QN-fullsuite-1.log` |
| 05.10 13:31 | 450.21 | 4327 | 0.1040 | 14 | `01M45FJD46BX45VHC36S4VS9QN-fullsuite-2.log` |
| 05.10 13:51 | 653.85 | 4326 | 0.1511 | 14 | `01M45FJD46BX45VHC36S4VS9QN-fullsuite-3.log` |
| 05.10 13:58 | 346.51 | 4327 | 0.0801 | 14 | `01M45FJD46BX45VHC36S4VS9QN-fullsuite-4.log` |
| 05.10 17:59 | 501.14 | 4340 | 0.1155 | 14 | `01M466ZERXQKXTR5RQCDYVDZJQ-fullsuite-1.log` |
| 05.10 18:15 | 839.22 | 4360 | 0.1925 | 14 | `01M45FJVGQT1K0P8HDEXZX6HS7-fullsuite-1.log` |
| 05.10 18:24 | 450.05 | 4340 | 0.1037 | 14 | `01M466ZERXQKXTR5RQCDYVDZJQ-fullsuite-3.log` |
| 05.10 18:48 | 437.45 | 4373 | 0.1000 | 14 | `01M45FJVGQT1K0P8HDEXZX6HS7-fullsuite-2.log` |
| 05.10 19:04 | 533.06 | 4371 | 0.1220 | 14 | `01M45FJVGQT1K0P8HDEXZX6HS7-fullsuite-3.log` |
| 05.10 20:13 | 286.20 | 4411 | 0.0649 | 14 | `01M462QACEH29RPRD2RZHGHQFM-fullsuite-1.log` |
| 05.10 21:32 | 621.09 | 4423 | 0.1404 | 14 | `01M46D5ZZQY7GBEW5TBVQ0P3ZV-fullsuite-1.log` |
| 06.10 00:36 | 411.80 | 4448 | 0.0926 | 14 | `01M46C776SZEMYPBQGPNJN1TXY-fullsuite-1.log` |
| 06.10 01:50 | 811.35 | 4471 | 0.1815 | 14 | `01M46D5T8SZ9D6S34TZFX8S46V-fullsuite-1.log` |
| 06.10 10:58 | 558.86 | 4494 | 0.1244 | 14 | `01M45FK56DWMNBRKA1VWM12H19-fullsuite-1.log` |
| 06.10 15:01 | 614.09 | 4537 | 0.1354 | 14 | `01M484RNV3QBDY3B0M16J916ZP-fullsuite-1.log` |
| 06.10 19:27 | 617.34 | 4547 | 0.1358 | 14 | `01M48FRD9RJDBBVT2SN0FY5G2A-fullsuite-1.log` |
| 06.10 19:43 | 630.42 | 4544 | 0.1387 | 14 | `01M48WR0HKZW8KJCBWDZTFC4ZY-fullsuite-1.log` |
| 06.10 20:03 | 588.84 | 4544 | 0.1296 | 14 | `01M490TDWEMDQ700VXTKYANF7K-fullsuite-1.log` |
| 06.10 20:59 | 617.31 | 4561 | 0.1353 | 14 | `01M48WR0HKZW8KJCBWDZTFC4ZY-fullsuite-2.log` |
| 06.10 23:53 | 638.00 | 4577 | 0.1394 | 14 | `01M48WRE8BHFDY011Q0HQGQ91B-fullsuite-1.log` |
| 07.10 01:09 | 822.41 | 4589 | 0.1792 | 14 | `01M49B90T16AR81ETFEYY164H1-fullsuite-1.log` |
| 07.10 01:23 | 806.16 | 4589 | 0.1757 | 14 | `01M49B90T16AR81ETFEYY164H1-fullsuite-2.log` |
| 07.10 03:31 | 678.31 | 4612 | 0.1471 | 14 | `01M48WT5X7ZC7332DRH85VY19D-fullsuite-1.log` |
| 07.10 06:00 | 600.09 | 4618 | 0.1299 | 14 | `01M48WTP12VC8MY2BNE5JSVXKA-fullsuite-2.log` |
| 07.10 11:39 | 619.91 | 4625 | 0.1340 | 14 | `01M4AG4D90B3ZYZGH2EC1B48R0-fullsuite-2.log` |
| 07.10 13:13 | 648.65 | 4636 | 0.1399 | 14 | `01M4AG3QYV3E7MN7FAVA10VDJG-fullsuite-2.log` |

Сверка внутри группы прогонов с одинаковым числом процессов xdist: у всех 84 завершённых прогонов таблицы в логе указано 14 workers. Первые 8 записей дают медиану 0,04004 с/тест, порог `1 + SUITE_DURATION_RATIO` = 1,6 составляет 0,06406 с/тест после `SUITE_DURATION_CALIBRATION_RUNS` = 8. На прогонах 02.10 – 04.10 утром максимум 0,05381 с/тест, сигнал не срабатывает. На 04.10 вечером сигнал срабатывает в 20:51 (0,0700), 20:58 (0,0856), 22:29 (0,0961) и 23:44 (0,0826); другие вечерние прогоны ниже порога. Группа с иным числом xdist в этих логах отсутствует, поэтому эмпирическую проверку смены числа процессов обеспечивают тесты AC-7.

## Влияние на систему

Добавляются записи гейта в журнал и строки `doctor`; `suite-run` сохраняет свой инвариант неизменности журнала шагов задачи. Предел времени, замок полного прогона, исходы гейтов и существующие проверки не меняются. Чтение `ps` ограничено снимком на конце прогона и проверкой doctor. Откат — revert коммитов задачи; удаление новых журнальных записей не требуется: неизвестные действия прежний код игнорирует.

## Риски

Снимок процессов берётся перед убийством дерева по таймауту и после завершения pytest на остальных исходах; PID раннера и его потомки исключаются. Когда песочница запрещает `/bin/ps`, macOS `libproc` даёт снимок с вычислением процента CPU по короткому интервалу. Логи с неполной сводкой не калибруют сигнал.

## Проверка

- Зафиксированные тесты `tests/test_01m4araxf7vss5xz8c99bx8de2_suite_observation.py`, `tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py` и новый `tests/test_suite_duration.py`: 10 passed. Два новых сторожа покраснели на своих временных мутациях и после восстановления зелёные.
- `tests/test_doctor.py` и `tests/test_report.py`: 180 проверок зелёные в совместном прогоне с тестом doctor задачи (итого 183 passed). Проверки гейта `tests/test_approve_acceptance_full_suite.py`, `tests/test_suite_lock.py::ApproveNotStartedTest`, `tests/test_full_suite_profile_timeout.py`: 19 passed и 7 subtests passed после сохранения сигнатуры раннера.
- В затронутом наборе `tests/test_acceptance.py`, `tests/test_suite_run.py`, `tests/test_full_suite_profile_timeout.py`, зафиксированном тесте записи и новом тесте сигнала: 45 passed, один отказ `tests/test_acceptance.py::MaterializeFromBranchGitFailureTest::test_none_from_ls_tree_files_leaves_existing_plank_untouched` — обращение к несуществующей таблице `tasks` при разрешении вымышленной задачи; изменённые места кода не участвуют в трассировке.
- После отказа перехода исправлено чтение короткого, но корректного снимка `ps` в `orchestrator/acceptance.py::_process_snapshot`: один процесс больше не отбрасывается из-за ограничения списка тремя элементами. AC-6 (`test_ac6_machine_load_is_ok_or_warn_never_fail`) проходит. Совместный прогон `tests/test_acceptance.py`, `tests/test_suite_run.py`, `tests/test_doctor.py`, `tests/test_suite_duration.py` и двух зафиксированных файлов задачи: 157 passed, тот же один отказ теста материализации планки с `sqlite3.OperationalError: no such table: tasks`; трассировка не проходит через изменённую функцию.
- `python3 scripts/guard.py <каталог документов>/PLAN.md`: GUARD: ок; `git diff --check` и `py_compile` проходят. Карта обновлена `python3 scripts/codebase_map.py`.
- После исправления `plank-run` проходит: 1 passed. `suite-run` повторно не стартовал из песочницы роли из-за `PermissionError` при создании `.artel/logs/suite-run/lock.json`; ограничение записано ниже.
- После решения Оператора 07.10 `orchestrator/suite_run.py::_run` больше не зовёт `journal_suite_metrics`; эта правка сохранена чекпоинтом c0558cc2. `tests/test_suite_run.py::SuiteRunJournalTest::test_suite_run_preserves_task_steps_on_every_outcome` проверяет неизменность журнала на зелёном, красном и таймаутном исходах и сохранение строки нагрузки при таймауте: `tests/test_suite_run.py` — 15 passed, 4 subtests passed. Временное возвращение вызова `journal_suite_metrics` делает сторожа красным (4 subtests failed); после восстановления кода `git status --short` чист. Долгоживущий `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py::FootprintTest::test_ac23_task_state_untouched_and_no_files_outside_state` — 1 passed.
- После `amend-tests` Оператора и коммита `d03109ad` повторный прогон затронутых модулей (`tests/test_acceptance.py`, `tests/test_suite_run.py`, `tests/test_doctor.py`, `tests/test_report.py`, `tests/test_full_suite_profile_timeout.py`, `tests/test_approve_acceptance_full_suite.py`, `tests/test_suite_duration.py` и два зафиксированных файла задачи): 240 passed, 1 failed за 101,01 с. Исправленный AC-5 проходит. Единственный отказ — прежний `MaterializeFromBranchGitFailureTest::test_none_from_ls_tree_files_leaves_existing_plank_untouched`: `sqlite3.OperationalError: no such table: tasks` при разрешении вымышленного task id; трассировка не проходит через изменённые функции задачи.
- После правки теста Оператором `python3 scripts/codebase_map.py` обновил карту; `git diff --check` — без ошибок. `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4ARAXF7VSS5XZ8C99BX8DE2`: 1 passed. Полный набор запрошен штатным `suite-run`, но команда завершилась до запуска pytest с `PermissionError` при создании `.artel/logs/suite-run/lock.json` вне разрешённых корней песочницы роли.

## Приложение: строка `docs/triggers.md`

Точный текст новой строки после №27:

| 32 | Рост времени полного прогона `suite.duration` | время на тест последней записи выше медианы окна из `SUITE_DURATION_CALIBRATION_RUNS` записей более чем в `1 + SUITE_DURATION_RATIO` раз; при смене числа процессов xdist окно начинается заново; ack переносит точку отсчёта | ряд записей журнала «прогон: время» target после ack, с одинаковым числом процессов xdist | решение Оператора при ack: устранить нагрузку машины или пересмотреть состав полного набора | doctor, alerts kind=trigger |

## Предложения системе

- Для анализа исторического ряда `.artel/logs/*-fullsuite-*.log` нет команды пульта; понадобился разовый сценарий разбора итоговых строк. Нужна команда экспорта метрик полного прогона.
- `suite-run` из шага роли падает `PermissionError` при создании `.artel/logs/suite-run/lock.json`: каталог вне разрешённых корней записи роли. Нужна совместимая с песочницей точка записи замка и отчёта либо штатное посредничество пульта.
- `tests/test_acceptance.py::MaterializeFromBranchGitFailureTest::test_none_from_ls_tree_files_leaves_existing_plank_untouched` падает вне изменённого пути: `artifact_branch.task_repo` ищет target вымышленной задачи в БД без таблицы `tasks`. Нужна изоляция теста от БД пульта либо подготовка схемы в фикстуре.
- Противоречие AC-5 с решением Оператора устранено через `amend-tests` по ANSWER-1; этот тест теперь проверяет отчёт без записи журнала.
