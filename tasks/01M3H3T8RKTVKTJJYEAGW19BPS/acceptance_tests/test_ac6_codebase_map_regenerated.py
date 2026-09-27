"""AC-6 — 01M3H3T8RKTVKTJJYEAGW19BPS: `docs/codebase-map.md`
перегенерирован в ветке задачи.

Свежесть сверяется тем же способом, что джоб CI «Карта кодовой базы
генерируется и свежа»: карта, собранная из сегодняшних исходников,
обязана совпасть с закоммиченной всюду, кроме строки `built_at_sha`
(она не может нести sha собственного коммита). Генератор здесь НЕ
запускается процессом — вызываются его чистые узлы `build_modules` и
`render`, и результат сравнивается в памяти: `scripts/codebase_map.py`
пишет файл в корень репозитория, а планке приёмки писать в рабочую
копию нечего (инцидент 05.09 — ровно такой запуск из теста планки).

Красен до реализации: `orchestrator/ci_rerun.py` ещё не существует, и
закоммиченная карта его не знает — секции модуля в ней нет. Сверка
свежести сегодня зелена (карта соответствует нетронутым исходникам) и
краснеет ровно тогда, когда разработчик тронул код и не перегенерировал
карту — проверено стабом.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402
from scripts import codebase_map  # noqa: E402

MAP_REL = codebase_map.OUTPUT_PATH.as_posix()
_SHA_LINE_RE = re.compile(r"^built_at_sha:.*$", re.MULTILINE)


def _without_sha(text: str) -> str:
    return _SHA_LINE_RE.sub("built_at_sha: <снят при сверке>", text)


class CodebaseMapRegeneratedTest(unittest.TestCase):

    def setUp(self):
        map_path = _util.REPO_ROOT / MAP_REL
        self.assertTrue(map_path.is_file(), f"{MAP_REL} отсутствует")
        self.committed = map_path.read_text(encoding="utf-8")

    def test_ac6_map_lists_the_new_command_module(self):
        """В карте есть секция `## orchestrator/ci_rerun.py`.

        Ловит мутацию: карту перегенерировали до создания нового модуля
        (или после `git add` одной лишь `fsm.py`) — новый модуль пульта
        остался бы невидимым и карте, и брифу роли, который её
        встраивает.
        """
        self.assertIn(
            f"## {_util.CI_RERUN_REL}", self.committed,
            f"{MAP_REL} не знает модуля {_util.CI_RERUN_REL} — карта не "
            f"перегенерирована после переноса команды (AC-6)")

    def test_ac6_committed_map_matches_a_fresh_regeneration(self):
        """Карта, собранная из сегодняшних исходников рабочего дерева,
        совпадает с лежащей в ветке — с точностью до `built_at_sha`.

        Ловит мутацию: карта перегенерирована в середине работы, а
        последняя правка (например, обновлённый докстринг `fsm.py`,
        откуда карта берёт «Назначение», или снятые публичные имена)
        в неё не попала — джоб свежести CI красит ветку; здесь
        расхождение видно до мержа.
        """
        modules, resolved_imports, imported_by = codebase_map.build_modules(
            _util.REPO_ROOT)
        fresh = codebase_map.render(modules, resolved_imports, imported_by,
                                    "не сверяется")
        self.assertEqual(
            _without_sha(fresh), _without_sha(self.committed),
            f"{MAP_REL} разошлась с перегенерированной из текущих "
            f"исходников — регенерируй её в ветке задачи "
            f"(python3 scripts/codebase_map.py), AC-6")


if __name__ == "__main__":
    unittest.main()
