# Записка developer — 01M5N8A5JBEQ15DCHDP95EBDZR

## Выяснено
- Реализация: `_flush_batch` + помощники (`_fresh_main`, `_build_on_batch`,
  `_commit_on_batch`, `_sent_line`, `_refused_print`) в `orchestrator/notes.py`;
  `_flush_pending` делит записи на пакет и правки конфигурации (те — после
  пакета прежним `_attempt`). Параметр `ref` добавлен в `_build_doc_commit`,
  `_build_apply`, `_content_already_in_origin`, `_foreign_base_refusal`,
  `_foreign_backlog_commits` (умолчание `FETCH_HEAD`).
- `known`: первая вошедшая в пакет — `_known_origin_main` до fetch, k>1 — голова
  пакета перед ней в первом построении (словарь `knowns` по пути файла).
- Долгоживущий файл задачи 16/16 зелёный; 19 соседних файлов tests/ про note/
  doc-commit — 257 passed. Мутация `known = head` краснит оба AC-11.
- Карта `docs/codebase-map.md` перегенерирована.

## Не сработало
- `pytest -n` запрещён сторожем conftest; `sed -i` и длинные heredoc в Bash
  отказаны — правки через Edit.

## Где остановился
- Шаг завершён: PLAN.md status: ready.

## Чего не хватило
- Ничего существенного; SPEC и записка test_author дали всё нужное.
