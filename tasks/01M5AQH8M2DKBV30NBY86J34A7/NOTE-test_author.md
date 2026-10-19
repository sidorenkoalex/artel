# Записка test_author

## Выяснено
- Прошлый шаг не оставил ни одного файла acceptance_tests/ (отказ трассируемости по всем 32 AC).
- Прецеденты песочниц: tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py (LabelledSandbox), tests/test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout.py (поддельный pytest + junit), tests/test_01m446wevjxarr5cded8re9ccr_auto_refusal_class.py (ScriptedAdvance/RecordingStep для auto).
- У pult-vitest «сухой сбор» = настоящий прогон по отчёту (acceptance._collect_reported) — шпион отвечает одним отчётом на оба прогона; гейт — второй запуск раннера.
- Имя гейта честного FAIL_TO_PASS SPEC не называет; «прямой вызов гейта» (AC-9 два компонента, AC-12 защитная ветка) без имени не написать — кандидат в эскалацию. AC-15 защитную ветку можно достать подменой публичного outcome.verdict.
- Опора: задача в spec_gate + store.set_state(..., "tests_writing", detail="гейт SPEC пройден — приёмочные тесты до кода").

## Файлы
- tests/test_01m5aqh8m2dkbv30nby86j34a7_fail_to_pass.py — песочница FailToPassSandbox; написаны AC-1..14 (AC-9/12 — части + пометки escalate), AC-28, AC-30..32; красны по правильной причине (прогнано 19.10).
- Чекпоинт шага удаляет каталог документов целиком (t.docs) — правка SPEC пишется заново (edit_spec, mkdir).
- В основном файле уже и AC-15/16/17/18/19/20/21/22/24/25/26 (прогнаны: красны по правильной причине; AC-22/24/25/26 и AC-17 зелены с рождения — прежнее поведение).
- Написаны все: AC-23 — acceptance_tests/test_autogate_rule_reason.py (разовый); AC-29 — tests/test_01m5aqh8m2dkbv30nby86j34a7_refusal_classes.py; AC-27 — класс в основном файле (зелён с рождения).
- Гейт посторонних молчит, если после записи «посторонние файлы» идёт автокоммит чекпоинта — запись о посторонних кладётся сценарием последней (как прецедент tests/test_fsm_advance_tests_writing_dry_collect.py).
- Дальше: preflight, затем стаб реализации.

## Не сработало
- `ls`, `cat` в Bash недоступны; `cd <worktree> && ...` работает.

## Где остановился
Пишу песочницу и AC-1/AC-2, затем прогон.

## Чего не хватило
-
