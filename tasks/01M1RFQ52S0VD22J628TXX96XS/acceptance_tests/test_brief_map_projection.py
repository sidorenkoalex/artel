"""Приёмочные тесты 01M1RFQ52S0VD22J628TXX96XS — AC-6, AC-9..AC-16:
подключение `project_for_brief` к `orchestrator/brief.py`.

Источник — только tasks/01M1RFQ52S0VD22J628TXX96XS/SPEC.md, раздел
«Критерии приёмки». Песочница — тот же приём, что `tests/test_brief.py::
BriefUnitTest` (`tests.sandbox.TmpRootTest`, `gitcmd.show`/
`ls_tree_files` подменены на диск-бэкенд, полным набором путей config —
SPEC T061, AC-3): проверяются функции модуля `orchestrator/brief.py`
напрямую, не через `runner.cmd_run` целиком.

Красен до реализации: `orchestrator/brief.py` ещё не зовёт
`scripts.codebase_map.project_for_brief` — компонент карты несёт
исходный (непроецированный) текст `docs/codebase-map.md`, и тесты этого
файла падают на отсутствующей проекции (все секции по-прежнему несут
блок «Импортируется», опись/журнал считают по файлу на диске) — до
задачи требования 2/3 (AC-9..AC-16) реализация просто не существует.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import alerts, brief, config, context_package, gitcmd, store  # noqa: E402
from scripts import codebase_map  # noqa: E402
from tests.sandbox import (TmpRootTest, disk_backed_ls_tree_files,  # noqa: E402
                           disk_backed_show, fake_git, fake_git_for)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixtures  # noqa: E402


def fake_git_stale(*paths):
    """Сверка свежести карты находит расхождение по указанным путям
    (копия приёма `tests/test_brief.py::fake_git_stale` — тот же
    контракт `gitcmd.git`, локальный, чтобы не тянуть тестовый файл
    другой задачи как зависимость)."""
    return fake_git_for({"diff": (0, "\n".join(paths) + "\n", "")})


fake_git_diff_fails = fake_git_for({"diff": (128, "", "fatal: bad revision ''")})


def patch_project_for_brief(marker: str):
    """Патчит `project_for_brief` там, где его реально найдёт вызывающий
    код brief.py — независимо от стиля импорта разработчика (`from
    scripts import codebase_map` + `codebase_map.project_for_brief(...)`,
    либо `from scripts.codebase_map import project_for_brief` — во
    втором случае имя связано в пространстве имён `brief` напрямую и
    патч исходного модуля `codebase_map` его не тронет)."""
    if hasattr(brief, "project_for_brief"):
        return mock.patch.object(brief, "project_for_brief", return_value=marker)
    return mock.patch.object(codebase_map, "project_for_brief", return_value=marker)


class BriefProjectionSandbox(TmpRootTest):
    """Песочница: `docs/codebase-map.md` — фикстура трёх видов секций
    (`_fixtures.small_map`), `CLAUDE.md`/SPEC.md — минимальные маркеры."""

    def setUp(self):
        super().setUp()
        (self.root / "docs").mkdir(parents=True)
        (self.root / "docs" / "codebase-map.md").write_text(
            _fixtures.small_map(), encoding="utf-8")
        (self.root / "CLAUDE.md").write_text(
            "# Конвенции проекта\n", encoding="utf-8")
        (config.TASKS / "T001").mkdir(parents=True)
        (config.TASKS / "T001" / "SPEC.md").write_text(
            "# SPEC\n\nМаркер-текста-SPEC.\n", encoding="utf-8")

        store.create_schema(store.db())

        show_patcher = mock.patch.object(gitcmd, "show", disk_backed_show)
        show_patcher.start()
        self.addCleanup(show_patcher.stop)
        ls_patcher = mock.patch.object(gitcmd, "ls_tree_files",
                                       disk_backed_ls_tree_files)
        ls_patcher.start()
        self.addCleanup(ls_patcher.stop)

    def journal_details(self, actor: str) -> list:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE actor=? ORDER BY id", (actor,))]


# --------------------------------------------------------------------------
# AC-6: единственное место правил проекции.

class SinglePlaceOfProjectionTest(BriefProjectionSandbox):

    def test_ac6_developer_brief_delegates_the_map_text_through_project_for_brief(self):
        """`developer_brief` подставляет РЕЗУЛЬТАТ `project_for_brief` в
        текст карты, а не собственную обработку — патч функции
        уникальным маркером обязан «протечь» в итоговый бриф.

        Ловит мутацию: `developer_brief` собирает облегчённую карту
        своей копией правил (регулярка/построчный фильтр по меткам
        блоков) вместо вызова `project_for_brief` — патченная функция
        не была бы вызвана, и маркер не появился бы в тексте.
        """
        marker = "МАРКЕР-ПРОЕКЦИИ-" + "Z" * 12
        conn = store.db()
        with mock.patch.object(gitcmd, "git", fake_git), \
                patch_project_for_brief(marker) as spy:
            text = brief.developer_brief(conn, "T001")

        spy.assert_called()
        self.assertIn(
            marker, text,
            "результат подменённого project_for_brief не найден в "
            "тексте брифа developer")

    def test_ac6_analyst_map_component_delegates_through_project_for_brief(self):
        """Тот же контроль для `analyst_map_component` — правило одно на
        обе точки применения (требование 1 SPEC: «одно место»).

        Ловит мутацию: analyst получает урезанную карту через отдельную,
        пусть даже идентичную по результату, реализацию внутри
        `analyst_map_component» — маркер патча не появился бы в тексте.
        """
        marker = "МАРКЕР-ПРОЕКЦИИ-" + "Y" * 12
        conn = store.db()
        with mock.patch.object(gitcmd, "git", fake_git), \
                patch_project_for_brief(marker) as spy:
            text = brief.analyst_map_component(conn, "T001")

        spy.assert_called()
        self.assertIn(marker, text)

    def test_ac6_brief_module_source_has_no_duplicate_block_removal_markup(self):
        """`orchestrator/brief.py` не содержит буквальный markdown-токен
        блока карты «**Импортируется:**» — единственное место, где этот
        токен обязан встречаться при разборе/удалении, — рендер и
        проекция в `scripts/codebase_map.py`.

        Ловит мутацию: вместо вызова `project_for_brief` разработчик
        пишет в `brief.py` собственный `re.sub`/построчный фильтр,
        опознающий блок по этому же markdown-токену — токен появился бы
        в исходнике brief.py буквально.

        Не путать с AC-12: там требуется ОДНА строка человекочитаемого
        текста со словом «Импортируется» в кавычках-«ёлочках» («с блоком
        «Импортируется»») — не с этим markdown-токеном разбора.
        """
        source = Path(brief.__file__).read_text(encoding="utf-8")
        self.assertNotIn("**Импортируется:**", source)


# --------------------------------------------------------------------------
# AC-9/AC-16: developer_brief несёт проекцию, не полный текст карты.

class DeveloperBriefProjectionTest(BriefProjectionSandbox):

    def test_ac9_map_component_is_projected_when_the_map_is_fresh(self):
        """Карта свежа (нет расхождений `built_at_sha..HEAD`) — компонент
        карты в брифе developer несёт результат `project_for_brief`, а
        не исходный текст файла: блок «Публичные функции»/«Импортирует»/
        «Назначение» секций `orchestrator/*`/`scripts/*` виден, секция
        `tests/*` урезана до заголовка и «Назначение», блок
        «Импортируется» не виден нигде в компоненте карты.

        Ловит мутацию: `developer_brief` продолжает подставлять
        `map_text` как есть (без применения `project_for_brief`) —
        `**Импортируется:**` секций `orchestrator/foo.py`/`scripts/
        bar.py` остался бы в тексте.
        """
        conn = store.db()
        with mock.patch.object(gitcmd, "git", fake_git):
            text = brief.developer_brief(conn, "T001")

        self.assertIn("Оркестрирует нечто важное.", text)
        self.assertIn("`do_thing`", text)
        self.assertIn("**Назначение:** Тестирует нечто важное.", text)
        self.assertNotIn("`helper`", text,
                         "«Публичные функции» секции tests/* не удалены")
        self.assertLessEqual(
            text.count("Импортируется"), 1,
            "слово «Импортируется» встречается больше раза — сверх "
            "одной строки описи (AC-12) в тексте осталось содержимое "
            "блока карты")

    def test_ac9_projection_is_applied_to_the_post_regeneration_text(self):
        """Карта стухла и была регенерирована — проекция применяется К
        РЕЗУЛЬТАТУ регенерации (требование 2: «применяется ПОСЛЕ» сверки
        свежести), не к исходному стухшему тексту, и не минуя
        регенерацию вовсе.

        Ловит мутацию: проекция вызывается ДО регенерации (на исходном
        `map_text` с диска) — обновлённый `built_at_sha` из
        регенерированного текста не попал бы в бриф, хотя старый файл
        под тем же путём эта же реализация обязана была прочесть заново.
        """
        regenerated = _fixtures.small_map(sha="b" * 40)

        def fake_run(cmd, **kwargs):
            (self.root / "docs" / "codebase-map.md").write_text(
                regenerated, encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        conn = store.db()
        with mock.patch.object(gitcmd, "git",
                               fake_git_stale("orchestrator/runner.py")), \
                mock.patch("subprocess.run", side_effect=fake_run):
            text = brief.developer_brief(conn, "T001")

        self.assertIn("b" * 40, text,
                      "регенерированный built_at_sha не попал в бриф")
        self.assertLessEqual(text.count("Импортируется"), 1)

    def test_ac12_component_label_names_the_projection_and_points_to_the_full_map(self):
        """Заголовок компонента карты называет содержимое проекцией
        (например, `docs/codebase-map.md (проекция для брифа)`) и одной
        строкой сообщает, что полная карта — с блоком «Импортируется» и
        секциями тестов — лежит в `docs/codebase-map.md` рабочего
        каталога и читается адресно.

        Ловит мутацию: заголовок компонента остаётся голым `docs/
        codebase-map.md` без пометки «проекция» — роль не узнает, что
        видит не полную карту, и не узнает, куда идти за полной.
        """
        conn = store.db()
        with mock.patch.object(gitcmd, "git", fake_git):
            text = brief.developer_brief(conn, "T001")

        self.assertIn("проекция для брифа", text)
        self.assertIn(brief.MAP_REL, text)
        self.assertIn("адрес", text,
                     "нет упоминания, что полная карта читается адресно")

    def test_ac13_manifest_size_and_sha_match_the_projection_not_the_disk_file(self):
        """Размер и sha256 в заголовке описи компонента карты
        (`### ... — N байт, sha256=...`) — от текста ПРОЕКЦИИ, а не от
        текста файла на диске.

        Ловит мутацию: опись по-прежнему считает размер/sha256 от
        `map_text` (как до этой задачи) — в бриф попала бы проекция, а
        заголовок описи называл бы sha256/размер другого, более
        крупного текста.
        """
        map_text = _fixtures.small_map()
        conn = store.db()
        with mock.patch.object(gitcmd, "git", fake_git):
            text = brief.developer_brief(conn, "T001")

        projected = codebase_map.project_for_brief(map_text)
        expected_sha = context_package.sha256_of(projected)
        expected_size = len(projected.encode("utf-8"))
        disk_sha = context_package.sha256_of(map_text)

        self.assertIn(expected_sha, text)
        self.assertIn(str(expected_size), text)
        if disk_sha != expected_sha:
            self.assertNotIn(disk_sha, text,
                             "sha256 полного файла на диске найден в описи "
                             "— опись всё ещё считает по файлу, не по проекции")

    def test_ac14_journal_entry_for_the_map_carries_the_projection_hash(self):
        """Журнальная запись «бриф: компонент» для карты несёт sha256
        текста ПРОЕКЦИИ, а не полного текста файла на диске.

        Ловит мутацию: журнал по-прежнему хэширует `map_text` — запись в
        БД перестаёт отвечать фактически прочитанному ролью тексту
        (тот же принцип, что и у tasks/01M1K7KP0D8ZKRM9KTE75DCCYR).
        """
        map_text = _fixtures.small_map()
        conn = store.db()
        with mock.patch.object(gitcmd, "git", fake_git):
            brief.developer_brief(conn, "T001")

        projected_sha = context_package.sha256_of(
            codebase_map.project_for_brief(map_text))
        details = self.journal_details("developer")
        self.assertTrue(
            any(projected_sha in d for d in details),
            "sha256 проекции не найден в журнале шага developer")

        disk_sha = context_package.sha256_of(map_text)
        if disk_sha != projected_sha:
            self.assertFalse(
                any(disk_sha in d for d in details),
                "sha256 полного файла на диске найден в журнале — журнал "
                "всё ещё хэширует файл, не проекцию")

    def test_ac15_stale_note_still_precedes_the_map_component(self):
        """Сверка свежести самой карты не удалась (git не ответил) —
        пометка «КАРТА НЕАКТУАЛЬНА» по-прежнему стоит в тексте брифа
        ПЕРЕД ТЕКСТОМ ПРОЕКЦИИ (SPEC AC-15: «до текста проекции») — не
        обязательно перед декоративным заголовком `### <label>` (у
        analyst заголовок компонента и сегодня, до этой задачи, стоит
        раньше пометки — см. `AnalystMapComponentProjectionTest.
        test_ac15_...`), а перед фактическим НАЧАЛОМ содержимого карты,
        маркер которого — строка шапки `built_at_sha:` (AC-4: шапка
        проекции — байт-в-байт шапка исходника, значит и в этой сценке
        она видна как есть).

        Ловит мутацию: пометка стухлости приклеена ПОСЛЕ текста карты
        либо вовсе потеряна при подключении проекции (например,
        `map_note` больше не конкатенируется с текстом компонента).
        """
        conn = store.db()
        with mock.patch.object(gitcmd, "git", fake_git_diff_fails):
            text = brief.developer_brief(conn, "T001")

        self.assertIn("КАРТА НЕАКТУАЛЬНА", text)
        note_idx = text.index("КАРТА НЕАКТУАЛЬНА")
        map_body_idx = text.index("built_at_sha:")
        self.assertLess(
            note_idx, map_body_idx,
            "пометка стухлости карты стоит не перед текстом проекции")

    def test_ac16_final_brief_has_no_leaked_importers_block(self):
        """Итоговый текст `developer_brief` не содержит ни одного
        вхождения «Импортируется», относящегося к СОДЕРЖИМОМУ компонента
        карты — единственное допустимое вхождение слова (не более
        одного) — человекочитаемая строка-указатель на полную карту
        (AC-12), не содержимое блока.

        Фикстура (`_fixtures.small_map`) несёт метку «Импортируется» в
        КАЖДОЙ из трёх секций (даже там, где список пуст — «—»,
        `render()` печатает метку безусловно) — непроецированный текст
        дал бы минимум 3 вхождения плюс возможную строку-указатель,
        итого больше одного.

        Ловит мутацию: проекция подключена только для ОДНОЙ из трёх
        секций (например, только `orchestrator/*`, без `scripts/*`) —
        счётчик вхождений остался бы больше одного.
        """
        conn = store.db()
        with mock.patch.object(gitcmd, "git", fake_git):
            text = brief.developer_brief(conn, "T001")

        self.assertLessEqual(text.count("Импортируется"), 1)


# --------------------------------------------------------------------------
# AC-10/AC-16 (сторона analyst): та же проекция, тем же способом.

class AnalystMapComponentProjectionTest(BriefProjectionSandbox):

    def test_ac10_map_component_is_projected_the_same_way(self):
        """`analyst_map_component` кладёт ту же проекцию тем же способом
        (требование 2 SPEC: «тем же способом»).

        Ловит мутацию: `analyst_map_component` не подключён к проекции
        вовсе (продолжает нести `fresh_map_text` как есть) — блок
        «Импортируется» секций `orchestrator/*`/`scripts/*` остался бы
        виден.
        """
        conn = store.db()
        with mock.patch.object(gitcmd, "git", fake_git):
            text = brief.analyst_map_component(conn, "T001")

        self.assertIn("Оркестрирует нечто важное.", text)
        self.assertIn("`do_thing`", text)
        self.assertNotIn("`helper`", text)
        self.assertLessEqual(text.count("Импортируется"), 1)

    def test_ac12_analyst_component_label_names_the_projection(self):
        """Та же добавка для analyst: заголовок компонента называет
        содержимое проекцией и одной строкой указывает на полную карту.
        """
        conn = store.db()
        with mock.patch.object(gitcmd, "git", fake_git):
            text = brief.analyst_map_component(conn, "T001")

        self.assertIn("проекция для брифа", text)
        self.assertIn(brief.MAP_REL, text)

    def test_ac14_analyst_journal_entry_carries_the_projection_hash(self):
        """Журнальная запись «бриф: компонент» analyst — тот же принцип,
        что у developer (AC-14): sha256 проекции, не полного файла.
        """
        map_text = _fixtures.small_map()
        conn = store.db()
        with mock.patch.object(gitcmd, "git", fake_git):
            brief.analyst_map_component(conn, "T001")

        projected_sha = context_package.sha256_of(
            codebase_map.project_for_brief(map_text))
        details = self.journal_details("analyst")
        self.assertTrue(any(projected_sha in d for d in details))

    def test_ac15_stale_note_still_precedes_the_map_component_for_analyst(self):
        """Тот же контроль AC-15 для analyst — сверка не удалась, пометка
        стоит перед фактическим текстом проекции (маркер — шапка
        `built_at_sha:`), не обязательно перед декоративным заголовком
        `### docs/codebase-map.md` (сегодня, до этой задачи, у analyst
        заголовок компонента стоит раньше пометки — `fresh_map_text`
        отдаёт `note + text` ОДНОЙ строкой, которую целиком заворачивает
        `_journal_component` уже ПОСЛЕ заголовка `### <label>`; менять
        этот сложившийся у analyst порядок — не предмет этой задачи)."""
        conn = store.db()
        with mock.patch.object(gitcmd, "git", fake_git_diff_fails):
            text = brief.analyst_map_component(conn, "T001")

        self.assertIn("КАРТА НЕАКТУАЛЬНА", text)
        self.assertLess(text.index("КАРТА НЕАКТУАЛЬНА"),
                        text.index("built_at_sha:"))


# --------------------------------------------------------------------------
# AC-11: алерт потолка размера файла брифа считается по проекции.

class MapSizeAlertProjectionTest(BriefProjectionSandbox):

    def _map_size_alerts(self, conn, task_id: str) -> list:
        target = store.task_target(conn, task_id)
        return [a for a in alerts.open_alerts(conn, "incident")
               if a["source"] == brief.MAP_OVERSIZED_ALERT_SOURCE
               and a["target"] == target]

    def test_ac11_no_alert_when_only_the_full_file_exceeds_the_ceiling(self):
        """Полный текст карты превышает потолок файла брифа
        (`config.CONTEXT_FILE_MAX_BYTES`) минимум в полтора раза, но
        проекция (реально идущая в бриф) — умещается: алерт «карта
        крупнее потолка» не заводится.

        Ловит мутацию: `_handle_map_size_alert` по-прежнему считает по
        `map_text` (полному файлу), а не по результату
        `project_for_brief` — алерт сработал бы ложно, хотя роль
        реально получает укладывающийся в потолок компонент.
        """
        big_map = _fixtures.oversized_map(config.CONTEXT_FILE_MAX_BYTES)
        (self.root / "docs" / "codebase-map.md").write_text(
            big_map, encoding="utf-8")
        conn = store.db()

        with mock.patch.object(gitcmd, "git", fake_git):
            brief.developer_brief(conn, "T001")

        self.assertEqual(
            self._map_size_alerts(conn, "T001"), [],
            "алерт «карта крупнее потолка» сработал по полному тексту "
            "файла, хотя его проекция — под потолком (AC-11)")

    def test_ac11_alert_still_fires_when_the_projection_itself_exceeds_the_ceiling(self):
        """Контрольный случай: раздутие — в блоке «Публичные функции»
        секции `orchestrator/*`, который проекция СОХРАНЯЕТ (AC-2) — сам
        механизм алерта остаётся рабочим, просто считает по другому
        тексту, а не отключён вовсе.
        """
        huge_functions = [f"fn_padding_{i:06d}" for i in range(15000)]
        foo = codebase_map.ModuleInfo(
            _fixtures.FOO.rel_path, _fixtures.FOO.purpose, huge_functions, [])
        big_map = codebase_map.render(
            [foo, _fixtures.BAR, _fixtures.BAZ],
            _fixtures.RESOLVED_IMPORTS, _fixtures.IMPORTED_BY, _fixtures.SHA)
        self.assertGreater(
            len(big_map.encode("utf-8")), config.CONTEXT_FILE_MAX_BYTES * 1.5,
            "фикстура недостаточно раздута для контрольного случая")
        (self.root / "docs" / "codebase-map.md").write_text(
            big_map, encoding="utf-8")
        conn = store.db()

        with mock.patch.object(gitcmd, "git", fake_git):
            brief.developer_brief(conn, "T001")

        self.assertEqual(len(self._map_size_alerts(conn, "T001")), 1)


if __name__ == "__main__":
    unittest.main()
