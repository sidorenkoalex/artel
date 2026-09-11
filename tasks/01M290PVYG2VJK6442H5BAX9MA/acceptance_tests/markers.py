# AC-8: skip — критерий о непорче ЧУЖИХ уже существующих тестов
# (tests/test_timeout_checkpoint.py, tests/test_step_autocommit.py,
# tests/test_checkpoint_external_step_artifacts.py, tests/
# test_checkpoint_stray_acceptance_files.py, tests/test_zones_gate.py,
# tests/test_guard_task_root_subdirectory.py, tests/
# test_guard_extraneous_acceptance_files.py) остающихся зелёными без
# ослабления — это прогон уже названного поимённо набора (`python3 -m
# unittest tests.<файл>` по каждому), не новое наблюдаемое поведение
# продукта. Новый тест здесь дублировал бы тот же прогон без
# независимого сигнала; фактическая проверка — на developer/reviewer
# шаге этой задачи (прогон перечисленных файлов) и штатным discover CI.
