# Записка spec_auditor

## Выяснено
- Факты SPEC о коде верны (outcome.py:106-133/117/123-124, :256-268/263; advance_gates/acceptance.py:251-257, 335-348; фикстура fail_to_pass.py:392 с `file`).
- Опыт pytest 9.1.1 в mkdtemp: xunit2 — `classname="tests..artel-plank.ID.test_x"` без `file`; корень — `.artel-plank.ID.test_x`; xunit1 — тот же classname + `file`.
- Два `test_x.py` в одной песочнице — ошибка сбора (import mismatch); каталог аргументом не собирается (`norecursedirs` `.*`); /var→/private/var при `--rootdir` портит xunit1 `file`.
- В существующих тестах classname с пустыми сегментами нет — не сломаются.
- Вердикт concerns: (1) `..x` без AC; (2) все AC с литералом `.artel-plank` — обход хардкодом.

## Не сработало
- Bash с `$var` отклоняется песочницей — опыты гонял через `python3 - <<'EOF'`.

## Где остановился
- SPEC-AUDIT.md готов (status: ready, verdict: concerns); guard прогнан.

## Чего не хватило
- Ничего существенного.
