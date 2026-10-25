# Записка analyst — 01M5RH875Q1JMVRM1TXNE6HNMW

## Выяснено
- ТЗ достаточно (детальное, с уточнениями 25.10) — пишу SPEC, без QUESTIONS.
- Факты ТЗ сверены на ad3608c6: в `outcome_components` 17 тестов, классы и константы на местах (:47–56 константы, :59 ContextRunnerProc, :71 ComponentsOutcomeSandbox, :554–555 FAIL_TO_PASS_ACTION/FOREIGN, :558 ForeignPlankSandbox); заявка ac19 ссылается на `fsm_advance.py:609–613` (устарело, условие теперь :617); докстринг `outcome_prior` :6–8 называет два удалённых пути; новых файлов волны ещё нет; фикстур `box`/`foreign_box` в `tests/fixtures.py` нет.
- Образец формы SPEC — волна 2а-2а: `git show refs/artifacts/01M5R0DPNHZ7N8YBXMH375SMEE:tasks/01M5R0DPNHZ7N8YBXMH375SMEE/SPEC.md`.

## Не сработало
- `wc`/переменные shell после `cd` в составной команде — отказ песочницы; использовать абсолютные пути и grep.

## Где остановился
- SPEC.md написан (25 требований, AC-1…AC-18, budget 40 из ТЗ, обоснование монолита по сигналам: 18 AC, $40, 5 файлов зоны), status: ready; guard — ок.
- Уточнения ТЗ 25.10 вписаны в требования (workers 4 — части до 15; stdlib только contextlib/io; ссылка ac19 на `fsm_advance.tests_writing`).

## Чего не хватило
- —
