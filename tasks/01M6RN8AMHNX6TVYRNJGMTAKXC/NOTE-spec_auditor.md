# Записка spec_auditor

## Выяснено
- Все 7 вызовов `pult_message` передают проект; snapshot.py:277 — всегда `config.DEFAULT_TARGET` (запись артели, только слой репозитория — merge_local отказывает ей, targets.py:492).
- `pult_message` читает плоскую запись `targets.target` (gitcmd.py:547-555); новое поле попадёт в неё, только если его добавят в `_flatten` (targets.py:855-859, обычно через DELIVERY_POLICY_FIELDS).
- yamlmini: `Harness-Actor: orchestrator` без кавычек -> строка; `""` -> ''; `\n` в кавычках НЕ экранирование (буквальный backslash); многострочное значение из файла не разбирается вовсе -> AC-4 «две строки» проверяем только вызовом `targets.merge_local` с dict.
- target-set: `_field_keys` берёт перечень из LOCAL_FIELDS (projects.py:780), `_argument_value` отказывает пустому (projects.py:819-821) — совпадает с SPEC.
- Существующие тесты (test_pult_commit_signature.py:68-98, rewrite_flow:76, entry_checks DELIVERY_REFUSALS, target_set LOCAL_FIELDS динамически) не ломаются от добавления поля.

## Не сработало
- grep/ls с `cd` или переменными в Bash отклоняются правами; работают абсолютные пути, `find` вместо `ls`.

## Где остановился
- Вердикт concerns, SPEC-AUDIT.md написан.

## Чего не хватило
- Нет.
