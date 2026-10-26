# Записка spec_auditor

## Выяснено
- SPEC-AUDIT.md сдан: verdict concerns, status ready, guard ок; spec_sha 76dce9b0… совпал с blob SPEC.md.
- Главное: тр. 5 (сверка с forge.token_user) без исхода при реальном адаптере (А1.1 вводит token_user раньше разработки); тр. 11 (приёмка на итоговой голове) без AC; rebase-конфликт — входит ли авторазрешение карты/документов (pull.py:429-475); при rebase пропадают шаги узла подтяжки pull.py:819-862 (WIP-чекпоинт, doc-only, планка); коммиттер не проверяется в AC-3/4/7.
- Места кода из SPEC подтвердились (checkpoint:1882, amend:799, snapshot:272, artifact_branch:291, pull:462/535/543/575/589, fsm_advance:771/816/831/833 и т.д.). Все записи в refs/artifacts идут через artifact_branch.commit_files (автор по умолчанию FIXATION).
- runner.role_env ставит git-идентичность через setdefault (runner.py:1183) — ambient Оператора сильнее.

## Не сработало
- `artel.py docs <другая задача>` недоступна роли; SPEC части 1 и А1.1 читал `git show <артефактный коммит>:tasks/<id>/SPEC.md`.

## Где остановился
- Готово.

## Чего не хватило
- Где SPEC части 1/А1 — пришлось искать коммиты через `git log --all --grep=<id>`.
