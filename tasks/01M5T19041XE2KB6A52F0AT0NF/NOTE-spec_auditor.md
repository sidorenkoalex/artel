# Записка spec_auditor

## Выяснено
- SPEC-AUDIT.md сдан: verdict fail, status ready, guard ок.
- Главное: tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py:767/:794/:815 — записи внешнего проекта с knowledge [CLAUDE.md]/[./CLAUDE.md]/[AGENTS.md, CLAUDE.md]; тр. 7 их ломает, мандата нет → нужен новый батч.
- Проверка no_paths в targets.check (:578-581) — только «список строк», путь не проверяет (против AC-5).
- Слой репозитория плоский, policy есть только в локальном (targets.py:278, _flatten :536); targets-migrate projects.py:188 вне зон.
- brief.py:678 нормализует `./` → обход отказа knowledge префиксом; :734 каталог-предок читается рекурсивно.
- AC-13 без вложенных файлов обвязки; AC-2 не ловит подстрочную мутацию.
- stack.py:149 git ≥2.30, а --no-cone требует 2.35.
- checkpoint.py:1843 `git add -A` в sparse-копии — поведение на новых файлах под исключением не проверено (вероятный риск).

## Не сработало
- grep --include в zsh; shell с $-подстановками блокируется — опыт с sparse-checkout в /tmp не поставлен.

## Где остановился
- Готово.

## Чего не хватило
- Прогона git sparse-checkout + `git add -A` на неотслеживаемом файле под исключением (песочница запрещена политикой shell).
