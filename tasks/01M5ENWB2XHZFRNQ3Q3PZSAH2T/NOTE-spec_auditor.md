# Записка spec_auditor

## Выяснено
- Все ссылки SPEC на код (brief.py:44/183/435/453/550/586/1050/1120/1421/1459, review.py:205/941, project_profile.py:103/184/250/281, targets.py:98/124) подтверждены.
- Проба git: symlink в ls-tree = `120000 blob` (отбор по "blob" в brief.py:567-569 его пропускает как файл); не-ASCII имена в ls-tree без -z — в кавычках с octal escape; ls-tree без --literal-pathspecs и так не глобит `docs/a*.md`; `ls-tree -r -- file/` пуст.
- Вердикт concerns: 1) не-ASCII имена; 2) AC-7 без `knowledge` у фикстур не ловит обход decide; 3) имена файлов из чужого дерева в подписи вне границы; 4) --literal-pathspecs непроверяем; 5) мелкие неоднозначности.

## Не сработало
- Bash с `cd …;` и `$W` и rm блокируется правами — используй `cd X && cmd` и python для удаления.

## Где остановился
- SPEC-AUDIT.md сдан status: ready, verdict: concerns; guard прогнан.

## Чего не хватило
- Нет быстрого способа пробовать git в /tmp из шелла — пришлось писать скрипт в каталог документов и удалять его.
