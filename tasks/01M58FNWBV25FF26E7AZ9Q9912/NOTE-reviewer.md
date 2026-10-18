# NOTE-reviewer (итерация 1)

## Выяснено
- plank-run: 7 passed; затронутые модули tests/ (176 passed, 510 subtests) зелёные.
- Карта свежа (render в памяти == файл без built_at_sha).
- Вердикт approved, реестр пуст. Три наблюдения без реестра: int-ключ компонента в check → TypeError; depends_on.paths: [] проходит; текст decide у единственного компонента с UNREAD говорит «test_profile».

## Не сработало
- В шелле нет `ls`; на macOS у `git grep -E` нет `\b`.

## Где остановился
- REVIEW.md записан, status: approved.

## Чего не хватило
- У scripts/codebase_map.py нет режима --check — свежесть карты пришлось проверять импортом render.
