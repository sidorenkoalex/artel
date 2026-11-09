# NOTE-reviewer (iteration 2)

## Выяснено
- Дифф итерации 2 = `git diff 55aef548f..HEAD`: только тестовый файл (ac11 phrase_number, ac16 гейт command + before+1) и built_at_sha карты.
- Планка 8 passed; suite_run + poll_step — 29 passed за 240 с серийно.
- mutation-001 + mutation-002 наложены git apply: ac16 гейт и ac11 красные; откат git apply -R, дерево чистое.

## Не сработало
- Составные Bash-команды с `;` требуют подтверждения — разбивать на отдельные вызовы; `cat`/`ls` в Bash недоступны.

## Где остановился
- REVIEW.md iteration 2 записан: approved, реестр пуст.

## Чего не хватило
- Базы инкрементального диффа в пакете — взял sha CI прошлого вердикта.
