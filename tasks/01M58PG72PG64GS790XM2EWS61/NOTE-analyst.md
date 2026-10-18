## Выяснено
- Итерация 3 (после ANSWER-1, все ответы — A; ответ 5 дополнен формами sled: `BACKEND_RE: '…'`, `FRONTEND_RE: >-` блок одной строкой, многострочный блок — skip, `KEY=`/`export KEY=`, комментарии `#` пропускаются).
- SPEC.md переписан: 10 требований, AC-1…AC-14, budget $30, status: ready. QUESTIONS.md удалён. guard — ок.
- Ключевые решения в SPEC: `tools` в `Profile` заполняет `decide` (только запись с одним компонентом); новый элемент ключа — только при непустых `tools`; ключ базы — только `tools`, без сумм блокировок; `full-suite-timeout-<имя>`: multi — skip `targets.MULTI_COMPONENT_PENDING`, сломанная запись — fail.
- Падение doctor: cli.py:94 `full_suite_timeout_check` → `full_suite_limit` (project_profile.py:184-188).

## Не сработало
- `ls`/`rm` в оболочке нет; `$VAR`/`$?` в командах Bash отклоняются — удалял файл через `python3 -c os.remove`.

## Где остановился
- Шаг завершён: SPEC.md готов, guard ок.

## Чего не хватило
- Ничего существенного: решения пришли в ANSWER-1.
