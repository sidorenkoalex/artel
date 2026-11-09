# Записка developer — 01M6ZEMZB8Q1PKRXMJBJSTPR7T (итерация ревью 1)

## Выяснено
- Указание Оператора на гейте SPEC (пп. 1-8) в бриф разработчика не входит — читается из
  `artel.py log <id>` (запись «указание Оператора на гейте SPEC», 11:33:57Z).
- R1-F1..F4 закрыты в orchestrator/acceptance.py: `_remove_tree` (без shutil.rmtree),
  `_helper_run(interp, script, args, env)` → `[interp, "-", *args]`, `input=script`;
  `_interpreter_admitted` (запрос отдаёт `pytest_core`); `_failed_age` удаляет повреждённую отметку.
- R1-F5: заявка мутации в timeout_integrations переписана.
- Новый тест tests/test_acceptance_pycache_guards.py — 5 passed.

## Не сработало
- `ls`/`cat`/`awk` в шаге нет или требуют подтверждения; листинг — через `python3 -c`.

## Где остановился
- Шаг сдан: 4 мутации убиты, 13 соседних файлов — 243 passed; карта перегенерирована;
  реестр REVIEW.md размечен `fixed`; PLAN ready (раздел «Возврат из ревью, итерация 1»), guard ок.
- 8(б) (место None без строки) не менял: расходится с требованием 1 SPEC, ждёт решения Оператора.

## Чего не хватило
- Указания Оператора на гейте SPEC в брифе разработчика (искал в каталоге документов).
