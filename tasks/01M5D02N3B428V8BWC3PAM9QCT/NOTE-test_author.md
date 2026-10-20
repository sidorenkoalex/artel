# Записка test_author — 01M5D02N3B428V8BWC3PAM9QCT

## Выяснено
- Все 19 AC — тесты в трёх долгоживущих файлах (планка acceptance_tests/ пуста, `plank-run` поэтому пишет «планки нет»; preflight пройден целиком):
  - tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py — AC-1..9, 14..19 (RealGitSandbox, `answer.cmd_answer`/`cmd_zones_extend`, проекты: pult-vitest и junit-xml с report, компонент без report, test_profile, pytest-own+report, без профиля);
  - tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_audit_signal.py — AC-10 (`spec_audit.signals`);
  - tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py — AC-11..13 (урезанная копия стенда G3а-1а, только pult-vitest; повтор имени в файле даёт `#2`/`#3`).
- Ячеечные AC (14, 17, 18, 19) идут через мандат зон на файл кода — правило «Чем покрыто после» в SPEC не зависит от маркера.
- Журнал (AC-1, 2, 6, 9): виды разбираются из «ANSWER создан (…)» по «; »; ищется вид, начинающийся с «мандат на ослабление теста по идентификатору:» и несущий «<id>».
- Зелёные с рождения: AC-14, AC-16, AC-19, AC-11, отказные подслучаи AC-17, контроль AC-8 и AC-15.
- Стаб (mandate/answer/spec_audit/outcome_integrity) — все 19 методов зелёные; откачен `git checkout`.

## Не сработало
- `ls` не в PATH в шаге; `git ls-files` работает.
- Компонент pult-vitest без `select` — планка «не собирается» (нужно поле `select`).

## Где остановился
- Готово; карту `docs/codebase-map.md` не регенерировал — правка вне tests/ у test_author откатывается.

## Чего не хватило
- Нет общего помощника стенда гейта исходов в tests/sandbox.py — пришлось копировать шпион Popen из test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py.
