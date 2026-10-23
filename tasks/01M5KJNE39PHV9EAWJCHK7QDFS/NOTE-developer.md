# Записка developer — 01M5KJNE39PHV9EAWJCHK7QDFS

## Выяснено
- Код (tests/direct_git.py, tests/__init__.py) закоммичен в 73fc60c4, карта регенерирована. Долгоживущий файл: 11 passed, 43 subtests, пропусков нет (23.10, повторно).
- ANSWER-1 касается только залоченного файла тестов test_author:
  - п. 2 (FakeWhich без path= → None) — выполнен (стр. 74–90);
  - п. 1, песочница — выполнена (Ac8RolePathTest(TmpRootTest): isolate_keychain_and_role sandbox.py:1619, stub check_stack :1643);
  - п. 1, условие пропуска — НЕ выполнено: стр. 565–566 пропускают на любом OSError, а не только на «объявленный инструмент не найден в PATH» (runner.py:924). Другой OSError (venv, runner.py:1017) в TmpRootTest недостижим.
- Править файл разработчик не может → PLAN.md status: escalate, варианты (а) amend-tests / (б) принять, дефолт (б).

## Не сработало
- Bash: `$?`, `$t`, heredoc отклоняются песочницей («simple_expansion»); писать файлы — через Edit/Write.

## Где остановился
- PLAN.md: escalate, раздел «Ответ Оператора (ANSWER-1) — сверка» и «Эскалация». guard ок. После ответа: снять escalate → ready (код не меняется при (б); при (а) — amend-tests Оператора).

## Чего не хватило
- Что ANSWER на developer может требовать правки залоченного файла test_author — выход только эскалация.
