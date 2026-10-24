# Записка developer — 01M5PCB66D936FDGG7H09CVGA1

## Выяснено
- Образец — PLAN волны 1а: `git show refs/artifacts/01M5NNDYGQ8G6VFDEEXYBB0W3D:tasks/01M5NNDYGQ8G6VFDEEXYBB0W3D/PLAN.md`,
  новый файл 1а — `git show 6dee632d:tests/test_notes_module.py` (идиома фикстур поверх `real_git`).
- Шесть исходных файлов: 71 тест, 2271 строка, адресный прогон 48.88 с (serial, -p timeout).
- Планка читает новый файл из HEAD (`git show HEAD:…`) — для своего прогона планки код надо закоммитить.
- Места проверки текста исключения в исходниках: `DocCommitRefusalTest.assert_refused`,
  `PinBaseCheckTest.test_origin_diverged_from_pin_refuses_naming_pin_update`, `SuiteGateSandbox.refuse_config` — 3.

## Не сработало
- Запись в /tmp и `cd … && git` требуют подтверждения — не использовать.

## Где остановился
- 71 патч в каталоге документов; «до» — прогоны №1-3 (1-24, 25-48, 49-71) в PLAN «Мутации до»;
  не убиты 15, 41, 42 (заявки про упразднённый `.artel/notes-work`) — заявки тестов переписаны на 17, 70, 71.
- Свод закоммичен ca098937 (88 узлов / 71 функция, 2214 строк, 35.08 с; до — 71 тест, 2271 строка, 48.88 с).
- Дальше: «после» `--ref worktree --tests tests/test_doc_commit_module.py` частями, перенос в PLAN
  (временный помощник `plan_append_tmp.py` в корне рабочей копии — удалить в конце шага).

## Чего не хватило
- —
