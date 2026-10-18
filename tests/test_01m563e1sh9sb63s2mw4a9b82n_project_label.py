"""Проект задачи в выводе `status` и на плитке HTML `report`.

Группа: долгоживущий
Красен до реализации: строка `status` и плитка `report` проекта задачи не показывают — метки `[<проект>]` за id и отдельного элемента плитки с именем проекта нет; проверки строк и плиток артели зелены и до правки.

Связка: строки задач в БД песочницы — `catalog.cmd_status` (stdout) и
`report.cmd_report` (файл `.artel/report.html`). Имя внешнего проекта
выбирается случайно при каждом запуске; зерно печатается и входит в
текст провала.
"""
import random
from html.parser import HTMLParser

from orchestrator import catalog, config, report, store
from tests.sandbox import TaskSeededTmpRootTest, capture

PROJECT_NAMES = ("sled", "zubr", "kedr", "luna", "brod", "volna", "sosna")


class TileParser(HTMLParser):
    """Плитки `<div class="tile">` разметки: для каждой — список
    (тег, классы, собственный текст элемента без потомков)."""

    def __init__(self):
        super().__init__()
        self.tiles = []
        self.stack = []
        self.tile_depth = None

    def handle_starttag(self, tag, attrs):
        classes = (dict(attrs).get("class") or "").split()
        if self.tile_depth is None and tag == "div" and "tile" in classes:
            self.tile_depth = len(self.stack)
            self.tiles.append([])
        self.stack.append([tag, classes, ""])

    def handle_data(self, data):
        if self.stack:
            self.stack[-1][2] += data

    def handle_endtag(self, tag):
        if not self.stack:
            return
        tag_, classes, text = self.stack.pop()
        if self.tile_depth is not None:
            if len(self.stack) == self.tile_depth:
                self.tile_depth = None
            else:
                self.tiles[-1].append((tag_, classes, text.strip()))


def tile_elements(html: str, task_id: str) -> list:
    parser = TileParser()
    parser.feed(html)
    found = [tile for tile in parser.tiles
             if any("tile-id" in classes and text == task_id
                    for _, classes, text in tile)]
    if len(found) != 1:
        raise AssertionError(f"плитка {task_id}: найдено {len(found)}")
    return found[0]


class ProjectLabelTest(TaskSeededTmpRootTest):
    """`self.TASK` (T001) — задача артели; T002 — внешнего проекта;
    T003 — задача с `target` NULL."""

    EXT, NULL = "T002", "T003"

    def setUp(self):
        super().setUp()
        self.seed = random.SystemRandom().randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.project = random.Random(self.seed).choice(PROJECT_NAMES)
        conn = store.db()
        store.insert_task(conn, self.EXT, "Плитка внешняя", "in_dev",
                          "task/t002", self.project, 25.0)
        store.insert_task(conn, self.NULL, "Без проекта", "in_dev",
                          "task/t003", config.DEFAULT_TARGET, 25.0)
        store.update_task(conn, self.NULL, target=None)

    def msg(self, *parts) -> str:
        return f"зерно {self.seed}: " + " ".join(str(p) for p in parts)

    def status_line(self, out: str, task_id: str) -> str:
        lines = [line for line in out.splitlines() if line.startswith(task_id)]
        self.assertEqual(len(lines), 1, self.msg(task_id, out))
        return lines[0]

    def test_ac8_status_labels_external_project_only(self):
        """`status`: строка задачи внешнего проекта начинается с
        `<id> [<проект>]`, строки задачи артели и задачи с NULL — прежние.

        Строка артели и NULL начинается с `<id>  <состояние>` (прежний
        формат) и не несёт ни `[artel]`, ни `[None]`.
        Ловит мутацию: метка не выводится или стоит не сразу за id (два
        пробела, в конце строки); либо метка ставится каждой задаче —
        `[artel]` у артели, `[None]` у задачи с `target` NULL.
        """
        out = capture(catalog.cmd_status)
        ext = self.status_line(out, self.EXT)
        self.assertTrue(ext.startswith(f"{self.EXT} [{self.project}]"),
                        self.msg(ext))
        for task_id in (self.TASK, self.NULL):
            line = self.status_line(out, task_id)
            self.assertTrue(line.startswith(f"{task_id}  in_dev "), self.msg(line))
            for label in (f"[{config.DEFAULT_TARGET}]", "[None]", f"[{self.project}]"):
                self.assertNotIn(label, line, self.msg(line))

    def test_ac9_report_tile_has_project_element(self):
        """Плитка задачи внешнего проекта в `report.html` несёт отдельный
        элемент, собственный текст которого — имя проекта; плитки задачи
        артели и задачи с `target` NULL такого элемента не несут.

        Имя проекта не входит ни в id, ни в название задачи фикстуры:
        элемент находится разбором разметки, не вхождением подстроки.
        Ловит мутацию: проект не выводится на плитку или вписан в текст
        другого поля (`Статус: … · sled`); либо элемент проекта ставится
        каждой плитке — у артели с текстом `artel`, у NULL — `None`.
        """
        for task_id in (self.TASK, self.EXT, self.NULL):
            self.assertNotIn(self.project, task_id)
        self.assertNotIn(self.project, "Плитка внешняя")
        capture(report.cmd_report)
        html = (config.ROOT / ".artel" / "report.html").read_text(encoding="utf-8")
        ext = tile_elements(html, self.EXT)
        self.assertIn(self.project, [text for _, _, text in ext], self.msg(ext))
        for task_id in (self.TASK, self.NULL):
            texts = [text for _, _, text in tile_elements(html, task_id)]
            for value in (config.DEFAULT_TARGET, "None", self.project):
                self.assertNotIn(value, texts, self.msg(task_id, texts))
