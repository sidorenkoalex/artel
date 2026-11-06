# Записка spec_auditor

## Выяснено
- SPEC e54f64d0: факты о строках gitcmd.py/targets.py верны; snapshot.py:281 передаёт config.DEFAULT_TARGET (не проект задачи) — снимки истории всегда с Artel-Actor.
- yamlmini: значение из двух строк из файла недостижимо (`|` -> YamlError, кавычки через перевод строки -> два ключа, `\n` буквальный) — AC-4 «две строки» только через targets.merge_local(dict).
- Прежний отказ «раздел 'policy': неизвестное поле 'commit_trailer'» не содержит подстроки `policy.commit_trailer` — красная фаза AC-4 честная при полной форме.
- target-set: `Harness-Actor: orchestrator` читается строкой, _literal кавычит, обратное чтение то же.
- Существующие тесты (test_pult_commit_signature, rewrite_flow:76, target_set LOCAL_FIELDS динамически) не ломаются.

## Не сработало
- Bash с `echo` между командами и `$VAR` требует подтверждения — использовать Read и абсолютные пути.

## Где остановился
- SPEC-AUDIT.md написан, verdict concerns (4 пункта), guard прогнан.

## Чего не хватило
- Нет.
