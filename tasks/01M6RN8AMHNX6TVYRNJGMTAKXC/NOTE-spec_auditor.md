# Записка spec_auditor

## Выяснено
- SPEC be95c4fa: факты о строках gitcmd.py (544, 585-593, 539-543), targets.py (391, 424, 664, 721, 849/855-859, 492-494 отказ артели в merge_local) и вызовах pult_message верны; snapshot.py:281 — config.DEFAULT_TARGET.
- yamlmini (опыт): `""`->'', `"Key: "`->'Key: ', `"Key:   "`, `42`->int, `[x, y]`->list, `"  "`->'  ', `"a\nb"` в кавычках — буквальный `\n`.
- projects._argument_value:819 отказывает пустому аргументу; target-set допустимые поля берёт из LOCAL_FIELDS динамически (projects.py:780).
- check() слоя репозитория (targets.py:890) неизвестные поля не отвергает — commit_trailer в targets.yaml артели прошёл бы без проверки (как и co_author сейчас).
- Существующие тесты (test_pult_commit_signature:77/98, rewrite_flow:76/687/1324, entry_checks DELIVERY_REFUSALS, target_set ALLOWED) не ломаются: записи без поля.

## Не сработало
- Bash с `cd` + относительным путём, `;`/`|` между командами требует подтверждения — абсолютные пути, одна команда.

## Где остановился
- SPEC-AUDIT.md написан, verdict concerns (К1 пробельное всё поле, К2 порядок с co_author в AC-1, К3 образец Key:v в AC-4, К4 слой репозитория не проверяет поле), guard ок.

## Чего не хватило
- Нет.
