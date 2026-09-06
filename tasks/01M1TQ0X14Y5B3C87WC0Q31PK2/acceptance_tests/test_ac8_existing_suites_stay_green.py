"""AC-8 задачи 01M1TQ0X14Y5B3C87WC0Q31PK2 — пометка, без тестового кода.

Зелёный с рождения: файл не несёт ни одного тестового метода — служит
только носителем пометки `# AC-8: ci` ниже, выполнять и красить здесь
нечему.

# AC-8: ci — критерий буквально про существующие `tests/` («Существующие
tests/test_artifact_branch*.py, tests/test_checkpoint*.py, tests/
test_doctor.py остаются зелёными без правки существующих ассертов»,
формулировка содержит ключевые слова «существующ», `tests/`, «зелён» —
`scripts/guard.py::ci_marker_wording_ok`). CI кодовой ветки
(`.github/workflows/ci.yml`, шаг «unit-тесты», `python3 -m unittest
discover -s tests -v`) уже гоняет ВЕСЬ набор `tests/` на каждый пуш,
включая три названных файла/маски, — автогейт приёмки
(`orchestrator/fsm_autogate.py`, SPEC 01M1SHJTT0V516BWHYXWS50F3G)
засчитывает такой критерий исполненным по зелёному CI головы кодовой
ветки задачи, без повторного прогона `tests/` самим пультом.

Дублирующий вызов `unittest discover` подпроцессом внутри
`acceptance_tests/` того же смысла не добавляет и рискует ложным красным
из-за окружения этой машины (тот же довод, что у `tasks/T041/
acceptance_tests/test_checkpoint_after_timeout.py`, AC-5, и у
`tasks/01M1NBWTSXEJB24PXR417YF1VA/acceptance_tests/
test_ac8_developer_timeout_end_to_end.py`, AC-9) — а сама планка этой
задачи прогонять `tests/test_doctor.py`/`tests/test_checkpoint*.py`
изнутри процесса, который их же и правит, не имеет смысла: `guard`
запрещает планке трогать зону `tests/` (это код разработчика, не
`acceptance_tests/`), а результат такого прогона был бы неотличим от
того, что и так покажет обычный CI-джоб этой же ветки.

Число тестов «до этой задачи» (`python3 -c "import unittest;
print(unittest.TestLoader().discover('tests', pattern=X).countTestCases())"`,
ветка task/01m1tq0x14y5b3c87wc0q31pk2-otkaz-push-artefaktnoy-vetki-v от
свежего main, 06.09.2026) — планка для сверки Оператором/ревьювером, что
набор не уменьшился и не покраснел:
  test_artifact_branch*.py — 0 (маска пока ничего не matчит; SPEC явно
    называет её на будущее — новый файл этой же задачи может попасть под
    неё)
  test_checkpoint*.py — 21
  test_doctor.py — 120
"""
