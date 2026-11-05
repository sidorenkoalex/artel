## Выяснено
- Четвёртый аудит (spec fb05dac1). Решения гейта №3.1/№3.2 закрыли оба прежних замечания (сигнатура `_drop_key_mismatches`, связь `--drop-key` со сверкой).
- Опыт (tempfile + подмена config.TARGETS): `_target_set_mismatches` для `--key` со значением 123 / [a, b] отдаёт текст `_submodule_tokens_error` — требование 3 выполнимо через сверку.
- `machine` не опустеет после снятия последнего ключа: forge/url/token_slot обязательны (targets.py:378).
- Прежние тесты target-set не сверяют TARGET_SET_USAGE и не передают `--key` — не краснеют.
- Вердикт concerns: у `--key` нет критерия, что ветка зовёт `_target_set_mismatches` (симметрично решению №3.2).

## Не сработало
- Опытная фикстура: `profile` → нужно `test_profile` (отображение), `merge_gate` — operator | target-human.

## Где остановился
- SPEC-AUDIT.md сдан status: ready, verdict: concerns; guard ок.

## Чего не хватило
- Готовой минимальной валидной записи локального слоя для опыта (искал поля merge_local).
