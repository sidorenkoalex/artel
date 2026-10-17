# Записка analyst

## Выяснено
- ТЗ ссылается на SPEC родителя 01M53B45XW3J56RJHGD70TD8A2: `git show refs/artifacts/01M53B45XW3J56RJHGD70TD8A2:tasks/01M53B45XW3J56RJHGD70TD8A2/SPEC.md`.
- Шаг 5 (возврат с spec_gate — техническая правка формы): approve отказывал по неклассифицированному `.artel/projects/artel/`. Отказ воспроизводится только при root = корень пульта (там каталог существует); `scripts/guard.py` по файлу из worktree его не видит (каталога в worktree нет) — поэтому прежний guard давал «ок».
- В SPEC классифицируют пути только разделы `## Не входит` и `## Материалы` (guard.py:4095, SPEC_PATH_DECLARING_SECTIONS); отдельный `## Только чтение` guard не засчитал бы. Поэтому добавлен подраздел `### Только чтение` ВНУТРИ `## Не входит` (section_body режет только по `## `) — назван `.artel/projects/artel/`, config.ROOT вне config.PROJECTS, каталог проекта. Проверено: spec_unclassified_paths с root пульта — [] (без правки — ['.artel/projects/artel/']).
- Больше в SPEC ничего не менялось: 16 AC, budget 45, status ready.

## Не сработало
- Bash с `$`-подстановками и `ls`/`grep` без пути шагу недоступны; `git -C <корень пульта>` заблокирован.

## Где остановился
- SPEC правлен, guard ок.

## Чего не хватило
- Что guard по файлу и approve проверяют существование путей от разных корней — искал по коду guard.py:4194-4247.
