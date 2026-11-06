# NOTE test_author

## Выяснено
- AC-1..AC-4 — долгоживущий tests/test_01m6r8w7tsa6g85pvzzfdmry25_commit_author_block.py (11 случаев); песочница и помощники повторяют образец tests/test_01m6qz4rr80b2bym9axg5zmas4_target_set_block.py.
- Стаб (третья ветка `_block_keys` для ["machine","commit_author"] + дописанный BLOCK_PATHS) — все 11 зелены, существующий файл 01M6QZ4R… тоже (37); стаб снят, projects.py чист.
- Сверка `_target_set_block_mismatches` и `merge_local` для `machine.*` работают без доработки: отказ формы приходит текстом «нужно {name, email}».
- AC-5 — разовый acceptance_tests/test_ac5_existing_block_test.py: путь не в changed_paths() + прогон файла pytest-ом в подпроцессе.

- Долгоживущему файлу импорт `gitcmd` запрещён (preflight: признак «git-модуль»); пара автора из AC-1/AC-2 читается из `targets.target(<п>)["commit_author"]` — того же места, откуда её берёт `gitcmd.commit_author` (`_project_entry`).

## Не сработало
- Цикл `for` и `;` с последующими командами в Bash отклонены песочницей — цепочки только через `&&`.

## Где остановился
- Шаг готов: стаб проверен дважды (48 passed вместе с файлом 01M6QZ4R…), стаб снят, plank-run 1 passed, preflight — все проверки пройдены. Красная фаза: 11 failed — путь не принят `_block_keys`.

## Чего не хватило
- Нет.
