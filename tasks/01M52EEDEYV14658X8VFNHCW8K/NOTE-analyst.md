# Записка analyst

## Выяснено
- Возврат из spec_gate 16.10: шесть замечаний аудита внесены в SPEC (status: ready, guard ок).
  - Треб. 7/AC-7: пути команды разведены — оба у run/collect/run_repeat; через `run_full_suite` (acceptance.py:1115) у `_run_full_suite_now`/`_to_log`; единственный путь у `run_plank` (:923) и `two_sided._run_side` (:222). argv/cwd — точное равенство, env — разница с os.environ (acceptance.py:86, :1372; two_sided.py:230-232).
  - AC-1: перечень секретов — из реестра `providers.PROVIDERS` (как `runner.foreign_secret_env_names`, runner.py:914), случай с подменённым набором имён.
  - Треб. 4/AC-6: env не-отображение и значение не-строка (yamlmini.py:57-62) — отказ с `test_profile` и `env`.
  - Треб. 6/AC-5: умолчания workdir="", env пустое, runner="pult-pytest"; kwargs-построения Profile в tests/test_project_profile_gates.py:210, tests/test_network_address_gate.py:178 без правки.
  - Новое треб. 8 / AC-8: текст отказа по образцу targets.py:281; раздел «## Матрица неослабления» (форма — mandate.py:253 MATRIX_HEADERS) со строкой про tests/test_01m45fjvgqt1k0p8hdexzx6hs7_test_profile.py:103,151-152.
- AC теперь 8, бюджет 25 (рамка ТЗ) не менялся.

## Не сработало
- Ничего.

## Где остановился
- SPEC сдан, QUESTIONS.md нет.

## Чего не хватило
- Что такое «строка матрицы неослабления» в SPEC — нашёл форму в docs/operator-gates.md:61 и mandate.py:238-255.
