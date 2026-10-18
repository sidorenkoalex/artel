# Записка test_author — 01M56TNZ3E72XY9XSTAVS99CN2

## Выяснено
- Планка: долгоживущие tests/test_01m56tnz3e72xy9xstavs99cn2_two_sided_variants.py (AC-1..AC-3) и tests/test_01m56tnz3e72xy9xstavs99cn2_parametrize_gate.py (AC-4..AC-7); разовый acceptance_tests/test_ac8_invariants_attachment.py (AC-8, по образцу AC-10 части 2).
- Публичные входы, которые зовут тесты: `two_sided.run` (вердикт в `Outcome.results`/`refusals`); `test_integrity.uncovered` (находки `rest` — проверка по `Finding.name`/`path`; записи журнала, сделанные вызовом) и `review_lines`; `fsm.cmd_advance` (запись отказа `TEST_INTEGRITY_REFUSAL_ACTION`); мандат — `answer.cmd_answer` с матрицей и строкой «Независимая проверка:»; объявление — запись `DECLARED_CHANGE_ACTION` в журнале.
- Объявление «Меняемое поведение» принимается только для путей `tests/…` — объявленные случаи AC-4/AC-5 сделаны у артели, остальное — на учебном бэкенде (`workdir: backend`).
- Находка формы класса/модуля (AC-6) принимается о каждом методе, либо о классе, либо о файле целиком; у формы «константа CASES» — строго о методе с декоратором.
- Случай AC-3 «::test_x_slow без ::test_x» — синтетический отчёт через подмену `subprocess.run` (запуск с `-p two_sided.PLUGIN_MODULE` пишет записи в `env[two_sided.REPORT_ENV]`), без закрытых имён.
- Ошибка сборки (collect) прерывает весь сеанс pytest стороны — случай collect в AC-3 идёт отдельным прогоном `run`.
- Сегодня без находки `advance` уводит задачу в verifying, и `answer` в AC-4 отказывает «только escalated» — следствие красноты.
- Валидация стабом (откачен, `git status` чист кроме двух новых файлов): вердикт по общим вариантам в `two_sided.run` + сравнение `parametrize` в `_compare` (находка в found+observed, добавление — только observed) — все долгоживущие методы зелёные; мутации «пустое пересечение = пройден» и «добавление = находка» ловятся. AC-8 проверен фикстурным PLAN.md с приложением.
- preflight: все проверки пройдены.

## Не сработало
- Составные команды bash (`;`, `&&`) требуют подтверждения; `ls` нет в PATH.
- Метод AC-7 в долгоживущем файле с «Зелёный с рождения» вместо «Ловит мутацию:» — отказ preflight; заменено заявкой мутации.

## Где остановился
- Шаг завершён: планка и долгоживущие файлы написаны, preflight пройден.

## Чего не хватило
- Дольше всего искал способ выдать мандат Оператора в долгоживущем файле без `artifact_branch` (git-модуль запрещён) — ответ: `answer.cmd_answer` с матрицей, как в tests/test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope.py.
