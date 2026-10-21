# Записка test_author

## Выяснено
- Все 11 AC — свойства кода: планка — один долгоживущий файл
  tests/test_01m5enwb2xhzfrnq3q3pzsah2t_knowledge_brief.py (24 метода, test_ac1…test_ac11),
  каталога acceptance_tests/ нет (acceptance.collect принимает: plan.absent → только extra).
- Только публичные сборщики: brief.developer_brief / spec_auditor_brief (опись),
  analyst_map_component / test_author_answer_component (без описи), review.review_package.
- Эталон AC-9/AC-10 снят с пина: "\n".join(_project_conventions_parts(...)) на входе
  ETALON_* (CLAUDE.md есть, AGENTS.md нет); тест ищет его подстрокой и требует, чтобы вне
  него не было «проекта <имя>», «knowledge», пометок.
- review_package сам отказывает (SystemExit) при отказе decide (multi/без command) и зовёт
  decide вне конвенций — сценарии AC-10 с отказом/исключением decide собирают только 4 брифа.
- Запись components: — единственный компонент обязан нести long_lived_dir/long_lived_name;
  для PROFILE_PRESENT ещё command/weakening_scope/mutation_claim_scope.
- Валидация стабом в brief.py: всё зелёное; мутации (без -z, обход decide, повторы после
  предела, помеченный путь «показан») ловятся. Стаб откачен git checkout.
- preflight: все проверки пройдены.

## Не сработало
- `ls`/`rm`/`cp` в Bash недоступны; `cd … && grep` требует подтверждения — абсолютные пути.
- Атрибут `self.fail` в TestCase затеняет метод fail → переименован в git_fail.

## Где остановился
- Шаг завершён: файл написан, провалидирован, preflight пройден.

## Чего не хватило
- Не знал заранее, что review_package отказывает при отказе decide — выяснил прогоном.
