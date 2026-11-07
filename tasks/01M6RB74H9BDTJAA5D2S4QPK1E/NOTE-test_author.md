# Записка test_author

## Выяснено
- Все AC — свойства кода → только долгоживущие файлы, планки в acceptance_tests/ нет:
  - tests/test_01m6rb74h9bdtjaa5d2s4qpk1e_token_user.py — AC-1 (3 теста; подмена transport/targets.target/gitcmd.hosting_token строкой, forge.github_call для не-GitLab);
  - tests/test_01m6rb74h9bdtjaa5d2s4qpk1e_commit_author.py — AC-2…AC-6 (26 тестов, ~26 с).
- Песочница: initialized_tmp_root; запись GitLab в трёх разделах локального слоя (targets.local_path()), в description нужен test_profile; doctor — all_checks/cmd_doctor(fix=True) под блоком внешних процессов; ответ GET /user — подмена gitlab_adapter.transport.
- Строка сторожа ищется по имени в doctor.all_checks (место в коде не навязывается). Отказ new: текст строки сторожа должен входить в вывод `new`.
- Строка журнала записи: новая строка steps с target=<проект> и «commit_author» в action/detail.
- Отказ сверки (AC-3): после строки с «сверка до записи не прошла» в выводе должны идти строки проверок `[..]` и итог `DOCTOR:`.
- Предупреждение `new` при warn (AC-6): в выводе имя строки сторожа, «commit_author» или «автор коммитов».
- Валидация стабом: 29/29 зелёные, стаб снят (git checkout), дерево — только 2 новых файла. Красная фаза: 28 красных, 1 зелёный с рождения.
- preflight: всё пройдено.

## Не сработало
- ls/cat в Bash отклоняются — читать через Read.

## Где остановился
- Шаг сдан: оба файла написаны, провалидированы, preflight зелёный.

## Чего не хватило
- Формат записи локального слоя (description без test_profile/components отклоняется) — нашёл только по выводу doctor.
