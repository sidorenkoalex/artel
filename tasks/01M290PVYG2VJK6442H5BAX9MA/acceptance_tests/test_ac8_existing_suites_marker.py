"""AC-8 (tasks/01M290PVYG2VJK6442H5BAX9MA/SPEC.md): существующие тесты
`checkpoint` (`tests/test_timeout_checkpoint.py`,
`tests/test_step_autocommit.py`,
`tests/test_checkpoint_external_step_artifacts.py`,
`tests/test_checkpoint_stray_acceptance_files.py`), `fsm_advance`/гейт
зон (`tests/test_zones_gate.py`) и `guard`
(`tests/test_guard_task_root_subdirectory.py`,
`tests/test_guard_extraneous_acceptance_files.py`) остаются зелёными
без ослабления существующих проверок.

Зелёный с рождения: этот файл не содержит тестового кода — критерий о
непорче уже существующего, поимённо перечисленного набора тестов
проверяется прогоном тех самых файлов (`python3 -m unittest
tests.<файл>` по каждому из перечисленных), а не новым наблюдаемым
поведением продукта; здесь только пометка трассируемости AC-8, см.
комментарий ниже.
"""

# AC-8: skip — критерий о непорче ЧУЖИХ уже существующих тестов
# (перечислены в докстринге выше) остающихся зелёными без ослабления —
# это прогон уже названного поимённо набора, не новое наблюдаемое
# поведение продукта. Новый тест здесь дублировал бы тот же прогон без
# независимого сигнала; фактическая проверка — на developer/reviewer
# шаге этой задачи (прогон перечисленных файлов) и штатным discover CI.
