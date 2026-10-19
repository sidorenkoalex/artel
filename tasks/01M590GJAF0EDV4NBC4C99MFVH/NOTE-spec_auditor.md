# Записка spec_auditor — 01M590GJAF0EDV4NBC4C99MFVH

## Выяснено
- Визит 2 (SPEC sha d354ec11…): SPEC переписан по ANSWER-1 (варианты A батча QUESTIONS.md, коммит ссылки документов 08c69578). Все 14 отклонений первого аудита закрыты.
- Новые находки (concerns, 9 пунктов):
  - argv `pult-vitest` против ADR:86 (флаг `--expect.requireAssertions` внутри `command`);
  - механизм кэша Vite не задан (`node_modules` только для чтения);
  - умолчание `report_args` буквально цепляет артель (`targets.yaml:45-51`);
  - для `pult-vitest` нет условий запуска (`workdir`, таймаут);
  - `checks_local` не покрыты на автогейте (`fsm_autogate.py:327`);
  - дерево lock-файла установки не определено;
  - путь в идентификаторе AC-2 не привязан к корню репозитория;
  - «неизвестно» через ветку `NOT_STARTED` теряет лог (`acceptance.py:2363`);
  - у AC-19 нет отрицательного случая.
- QUESTIONS.md удалён из каталога документов, читается `git show 08c69578:tasks/<id>/QUESTIONS.md`.

## Не сработало
- `ls` в шелле нет (command not found): каталог документов смотреть через `git ls-tree refs/artifacts/<id>`.

## Где остановился
- SPEC-AUDIT.md сдан: verdict concerns, status ready, spec_sha d354ec11…, guard ок.

## Чего не хватило
- Смысл «Вариант A» в ANSWER-1 есть только в удалённом QUESTIONS.md из истории ссылки документов.
