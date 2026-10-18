---
task: 01M583RM59DHDRDH877AERAVMD
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

## Ответ Оператора: мандат на правку общих помощников CanaryLifecycleTest

Решение Оператора 18.10: методы test_ac1–test_ac3 `CanaryLifecycleTest` — только правка общих помощников `_CHILD` (:23-57) и `launch_signalled` (:112-137), а также проверка AC-12 в общем пути `assert_signal_cleanup` (:139-149), по требованиям 6 и 9 SPEC. Точка сигнала существующих методов (после файла наблюдения, во время ожидания), предел 20 с, долгоживущие подменённые suite (:36) и ведение (:44), все утверждения — прежние.

Ослабление тестов разрешено: tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py::CanaryLifecycleTest::test_ac1_sigterm_cleans_clone_origin_and_both_process_groups
Ослабление тестов разрешено: tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py::CanaryLifecycleTest::test_ac2_sighup_cleans_clone_origin_and_both_process_groups
Ослабление тестов разрешено: tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py::CanaryLifecycleTest::test_ac3_signal_records_non_green_existing_verdict

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py::CanaryLifecycleTest::test_ac1_sigterm_cleans_clone_origin_and_both_process_groups` — через общие `_CHILD`/`launch_signalled`/`assert_signal_cleanup` | SIGTERM во время ожидания: клон и origin удалены, suite и ведение не живы — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`:139-156 | остаётся; плюс AC-12: до сигнала оба процесса живы | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`:139-156 после правки (те же четыре `assertFalse`, та же точка сигнала) | ок |
| `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py::CanaryLifecycleTest::test_ac2_sighup_cleans_clone_origin_and_both_process_groups` — через те же помощники | то же для SIGHUP — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`:158-163 | остаётся; плюс AC-12 | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`:158-163 после правки | ок |
| `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py::CanaryLifecycleTest::test_ac3_signal_records_non_green_existing_verdict` — через `launch_signalled` | строка прогона «оборвана сигналом <имя>», вердикт не green и из прежнего множества — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`:165-183 | остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`:165-183 без правки утверждений | ок |
| `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py::CanaryLifecycleTest::launch_signalled` (:112-137) — общий с тестами раннего окна | предел 20 с ожидания наблюдения и `communicate` — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`:126, :136 | остаётся: тот же предел, сигнал из процесса теста после файла наблюдения | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`:112-137 после правки (SPEC требование 6, AC-6) | ок |
| `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py::_CHILD` (:23-57) — общий с тестами раннего окна | подменённые suite (:36) и ведение (:44) долгоживущи (`time.sleep(90)`), поэтому «не живы» после сигнала не пусто — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`:36, :44 | остаётся; короткое ведение — только отдельной подменой в новом тесте AC-11 | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`:36, :44 + AC-12 (оба pid живы до сигнала) | ок |
| `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py::CanaryLifecycleTest::test_ac4_suite_run_stops_on_normal_timeout_and_exception`, `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py::test_ac5_live_clone_contains_owner_pid_marker` — не меняются | свои подмены `launch` — `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`:195, :247 | остаётся | `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`:185-260 без правки | ок |

Независимая проверка: подтверждаю — независимый агент 18.10 сверил SPEC (требования 6 и 9, AC-6, AC-7, AC-12, матрица) с файлом теста: правка `_CHILD` и `launch_signalled` допускается только как общих с тестами раннего окна, точка сигнала, предел 20 с, долгоживущие подмены и все утверждения сохраняются; повторы, пропуски, `xfail`, рост пределов и заглушки запрещены; AC-12 добавляет утверждение и ничего не снимает; test_ac4, test_ac5 и тесты `tests/test_canary_drive.py`, `tests/test_01m4beg0003ch0qa1gy0pxat03_clone_marker.py` не правятся.
