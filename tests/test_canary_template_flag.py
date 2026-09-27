"""Юнит-тесты флага выбора шаблона прогона канарейки
(01M3HJQV2QV9BXNXSH3F8STAYH, требования 1-5): разбор `--template`,
именованный выбор шаблонов пула, сохранённая случайная выборка без флага
и первая строка вывода прогона.

Пул шаблонов — временный каталог, `canary._pool_dir` подменён: настоящий
`~/.artel-canary` Оператора читать роли запрещено (курируемый слой роли,
SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ, требование 13).
"""
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from orchestrator import artel, canary, config

#: Имена шаблонов пула, заведомо не в алфавитном порядке прогона: иначе
#: «в порядке флага» было бы неотличимо от «как отсортировано».
TITLES = ("alpha", "beta", "gamma")


class _PoolDirTest(unittest.TestCase):
    """Каталог пула из трёх `*.md` шаблонов и одного постороннего файла."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.pool = Path(tmp.name)
        for title in TITLES:
            (self.pool / f"{title}.md").write_text("ТЗ\n", encoding="utf-8")
        (self.pool / "не-шаблон.txt").write_text("x\n", encoding="utf-8")


class NamedPoolTemplatesTest(_PoolDirTest):
    """`canary._named_pool_templates` — выбор названных шаблонов и три
    отказа требования 3, знающие состав пула."""

    def test_returns_named_files_in_flag_order(self):
        """Ловит мутацию: список имён приводится к `sorted`/`set` либо
        обходится порядком каталога — прогон шёл бы алфавитным порядком
        пула вместо порядка флага, и воспроизвести конкретный сценарий
        пула командой было бы нельзя."""
        chosen = canary._named_pool_templates(self.pool, 3,
                                              ["gamma", "alpha", "beta"])

        self.assertEqual([self.pool / "gamma.md", self.pool / "alpha.md",
                          self.pool / "beta.md"], chosen)

    def test_name_is_given_without_the_md_extension(self):
        """Ловит мутацию: имя склеивается с каталогом как есть
        (`pool_dir / имя`) — прогон получил бы путь без расширения, и
        первое чтение шаблона упало бы внутри эфемерного клона, где
        причина умирает вместе с клоном."""
        chosen = canary._named_pool_templates(self.pool, 1, ["beta"])

        self.assertEqual([self.pool / "beta.md"], chosen)

    def test_count_of_names_not_equal_to_k_exits_naming_the_flag(self):
        """Ловит мутацию: список молча обрезается до `k` (или `k`
        переопределяется длиной списка) — команда вела бы не то число
        задач, которое Оператор назвал `--k`."""
        for k, titles in ((2, ["alpha"]), (1, ["alpha", "beta"])):
            with self.subTest(k=k, titles=titles):
                with self.assertRaises(SystemExit) as ctx:
                    canary._named_pool_templates(self.pool, k, titles)
                self.assertIn("--template", str(ctx.exception))

    def test_repeated_name_exits_naming_the_repeated_title(self):
        """Ловит мутацию: список не проверяется на уникальность — прогон
        вёл бы один шаблон дважды, обе задачи писали бы бейзлайн одного
        шаблона в одном прогоне, и вторая строка перезаписывала бы
        первую."""
        with self.assertRaises(SystemExit) as ctx:
            canary._named_pool_templates(self.pool, 2, ["alpha", "alpha"])

        self.assertIn("alpha", str(ctx.exception))

    def test_unknown_name_exits_listing_available_titles(self):
        """Ловит мутацию: неизвестное имя пропускается либо отказ не
        перечисляет пул — Оператор платил бы за опечатку клоном и
        заведённой задачей и не узнал бы, какие имена в пуле есть."""
        with self.assertRaises(SystemExit) as ctx:
            canary._named_pool_templates(self.pool, 1, ["нет-такого"])

        message = str(ctx.exception)
        self.assertIn("нет-такого", message)
        for title in TITLES:
            self.assertIn(title, message)

    def test_non_md_file_is_not_a_selectable_title(self):
        """Ловит мутацию: состав пула собирается по всем файлам каталога,
        а не по `*.md` — посторонний файл стал бы выбираемым шаблоном, и
        `k` считался бы не по шаблонам (v1-дыра, требование 1 SPEC
        01M1NEEWH5K1XPFRDGRMPYSBXJ)."""
        with self.assertRaises(SystemExit) as ctx:
            canary._named_pool_templates(self.pool, 1, ["не-шаблон"])

        self.assertIn("не-шаблон", str(ctx.exception))

    def test_empty_pool_exits_before_any_name_check(self):
        """Ловит мутацию: отказ пустого пула остался только в ветке
        случайной выборки — прогон по имени на пустом пуле сообщал бы
        «имени нет в пуле» вместо причины «пула нет», и Оператор искал бы
        опечатку там, где отсутствует каталог."""
        with tempfile.TemporaryDirectory() as empty:
            with self.assertRaises(SystemExit) as ctx:
                canary._named_pool_templates(Path(empty), 1, ["alpha"])

        self.assertIn("*.md", str(ctx.exception))


class TemplateArgTest(unittest.TestCase):
    """`artel._template_arg` — разбор флага, отдельный от состава пула."""

    def test_missing_flag_is_none_not_an_empty_list(self):
        """Ловит мутацию: отсутствие флага даёт пустой список — ветка
        выбора выбиралась бы по пустоте списка, и прогон без `--template`
        уходил бы в именованный выбор с нулём имён вместо прежней
        случайной выборки."""
        self.assertIsNone(artel._template_arg(["--k", "2"]))

    def test_value_is_split_by_comma_keeping_order(self):
        """Ловит мутацию: разбирается только первое имя списка
        (`split(",")[0]`) либо значение берётся целиком — `--k 3` с тремя
        именами повёл бы одну задачу вместо трёх."""
        self.assertEqual(
            ["gamma", "alpha", "beta"],
            artel._template_arg(["--k", "3", "--template",
                                 "gamma,alpha,beta", "--sha", "abc"]))

    def test_flag_without_a_value_is_a_named_refusal(self):
        """Ловит мутацию: значение берётся `rest[idx + 1]` без сверки
        границы — Оператор получил бы `IndexError` из глубины разбора
        вместо названной причины."""
        with self.assertRaises(SystemExit) as ctx:
            artel._template_arg(["--k", "1", "--template"])

        self.assertIn("--template", str(ctx.exception))


class CmdCanaryTemplateChannelTest(unittest.TestCase):
    """Канал имён от CLI до `canary.cmd_canary`: `--k` остаётся
    обязательным и разбирается первым (требование 2)."""

    def test_names_reach_cmd_canary_in_flag_order(self):
        """Ловит мутацию: `_cmd_canary` не передаёт разобранные имена
        (флаг молча игнорируется) — команда принимала бы `--template` и
        всё равно выбирала шаблоны случайно."""
        seen = {}

        with mock.patch.object(canary, "cmd_canary",
                               lambda **kw: seen.update(kw)):
            artel._cmd_canary(["--k", "2", "--template", "gamma,alpha"])

        self.assertEqual(["gamma", "alpha"], seen.get("templates"))
        self.assertEqual(2, seen.get("k"))

    def test_without_the_flag_cmd_canary_gets_none(self):
        """Ловит мутацию: без флага в команду уходит пустой список —
        прежняя ветка случайной выборки перестала бы выбираться (AC-3)."""
        seen = {}

        with mock.patch.object(canary, "cmd_canary",
                               lambda **kw: seen.update(kw)):
            artel._cmd_canary(["--k", "1"])

        self.assertIsNone(seen.get("templates"))

    def test_template_without_k_is_still_refused(self):
        """Ловит мутацию: `--k` выведен из числа имён `--template` и
        перестал быть обязательным — прежний отказ «нужен параметр --k»
        оказался бы ослаблен, а требование 2 прямо его сохраняет."""
        calls = []

        with mock.patch.object(canary, "cmd_canary",
                               lambda **kw: calls.append(kw)):
            with self.assertRaises(SystemExit) as ctx:
                artel._cmd_canary(["--template", "alpha"])

        self.assertIn("--k", str(ctx.exception))
        self.assertEqual([], calls)


class CmdCanaryTemplateSelectionTest(_PoolDirTest):
    """`canary.cmd_canary` — развилка выбора и первая строка вывода.
    `_run_one_task` подменён: ни одного эфемерного клона."""

    def setUp(self):
        super().setUp()
        for target, attr, value in (
                (canary, "_pool_dir", lambda: self.pool),
                (canary, "_resolve_target_sha", lambda sha: ("0" * 40, None)),
                (canary, "_sha_label", lambda sha, origin: "код пина")):
            patcher = mock.patch.object(target, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _run(self, **kwargs) -> tuple:
        seen = []
        buf = io.StringIO()
        with mock.patch.object(canary, "_run_one_task",
                               lambda path, *a, **kw: seen.append(path)):
            with redirect_stdout(buf):
                canary.cmd_canary(**kwargs)
        return [p.stem for p in seen], buf.getvalue()

    def test_named_templates_run_without_random_sampling(self):
        """Ловит мутацию: имена разобраны, но выбор всё равно идёт через
        `random.sample` по отфильтрованному списку — порядок прогона
        перестал бы быть порядком флага, а запрет ниже сработал бы на
        первом же вызове."""
        def forbidden(population, k):
            raise AssertionError("случайная выборка при явных именах")

        with mock.patch.object(canary.random, "sample", forbidden):
            titles, _out = self._run(k=2, templates=["gamma", "alpha"])

        self.assertEqual(["gamma", "alpha"], titles)

    def test_without_templates_the_pool_is_sampled_randomly(self):
        """Ловит мутацию: ветка выбора переписана «под флаг» так, что без
        имён берутся первые `k` шаблонов по алфавиту — канарейка перестала
        бы перебирать пул, и один шаблон проверялся бы прогон за
        прогоном."""
        seen = {}

        def fake_sample(population, k):
            seen["titles"] = sorted(Path(p).stem for p in population)
            seen["k"] = k
            return [population[-1]]

        with mock.patch.object(canary.random, "sample", fake_sample):
            titles, _out = self._run(k=1)

        self.assertEqual(sorted(TITLES), seen.get("titles"))
        self.assertEqual(1, seen.get("k"))
        self.assertEqual(1, len(titles))

    def test_first_output_line_names_the_templates_in_run_order(self):
        """Ловит мутацию: имена печатаются в отчёте каждой задачи, а
        первая строка прогона оставлена прежней — состав прогона Оператор
        узнавал бы по мере того, как задачи доходят до конца, то есть
        через десятки минут."""
        _titles, out = self._run(k=2, templates=["gamma", "alpha"])

        first = out.splitlines()[0]
        self.assertIn("gamma", first)
        self.assertIn("alpha", first)
        self.assertLess(first.index("gamma"), first.index("alpha"))

    def test_nonpositive_k_is_refused_before_the_pool_is_read(self):
        """Ловит мутацию: проверка `k <= 0` переехала под ветку
        `--template`, где без флага её никто не исполняет — прогон с
        нулевым `k` завершался бы успешно, молчаливо ничего не
        проверив."""
        with self.assertRaises(SystemExit) as ctx:
            with redirect_stdout(io.StringIO()):
                canary.cmd_canary(k=0)

        self.assertIn("--k", str(ctx.exception))

    def test_k_greater_than_the_pool_is_still_refused(self):
        """Ловит мутацию: сверка `k` с размером пула снята вместе с
        переходом на разбор имён — выборка падала бы `ValueError` внутри
        `random.sample` вместо названной причины."""
        with self.assertRaises(SystemExit) as ctx:
            with redirect_stdout(io.StringIO()):
                canary.cmd_canary(k=len(TITLES) + 1)

        self.assertIn(str(len(TITLES)), str(ctx.exception))


class UsageNamesTemplateFlagTest(unittest.TestCase):
    """Справка команды (требование 12): единственный текст, который
    печатает пульт без аргументов."""

    def test_usage_line_of_canary_names_the_template_flag(self):
        """Ловит мутацию: флаг реализован, но в строку использования не
        добавлен — справка пульта о выборе шаблона молчала бы, и флаг
        существовал бы только в SPEC задачи."""
        lines = [line for line in (artel.__doc__ or "").splitlines()
                 if "canary --k" in line]

        self.assertTrue(lines, "в справке нет строки команды canary --k")
        self.assertTrue(any("--template" in line for line in lines),
                        f"строка использования не называет --template: {lines}")

    def test_usage_describes_the_ceiling_exhausted_outcome(self):
        """Ловит мутацию: справка дополнена только флагом — Оператор,
        увидев в отчёте прогона незнакомый исход, не нашёл бы его ни в
        одной справке пульта и счёл бы обычной краснотой."""
        self.assertIn(canary._CEILING_EXHAUSTED_REASON,
                      (artel.__doc__ or "").lower())


#: Начало смыслового блока markdown: заголовок, пункт списка, абзац после
#: пустой строки. Блок — та единица, в которой Оператор читает правило
#: (образец — пункты «Аварийного режима»), поэтому «исход и пин названы
#: вместе» проверяется на пунктах, а не на файле целиком.
ITEM_START = ("- ", "* ", "#")


def _doc_blocks(text: str) -> list:
    blocks, current = [], []
    for line in text.splitlines():
        starts = (not line.strip() or line.startswith(ITEM_START)
                 or (line[:1].isdigit() and line.lstrip("0123456789")[:2] == ". "))
        if starts and current:
            blocks.append("\n".join(current))
            current = []
        if line.strip():
            current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


class OperatorSessionDocTest(unittest.TestCase):
    """`docs/operator-session.md` (требование 12): регламент сессии, по
    которому Оператор решает, что прогонять и когда двигать пин."""

    def setUp(self):
        self.text = (config.ROOT / "docs" / "operator-session.md").read_text(
            encoding="utf-8")

    def test_doc_names_the_template_flag(self):
        """Ловит мутацию: флаг описан только в справке команды —
        регламент сессии не знал бы способа воспроизвести конкретный
        сценарий пула."""
        self.assertIn("--template", self.text)

    def test_doc_ties_the_new_outcome_to_the_pin_rule(self):
        """Ловит мутацию: новый исход описан без слова о пине — в
        аварийном режиме «красный не по вине кода» мог бы быть прочитан
        как основание двинуть пин, чего ADR-0013 не разрешает."""
        blocks = [block for block in _doc_blocks(self.text)
                  if canary._CEILING_EXHAUSTED_REASON in block.lower()
                  and "пин" in block.lower()]

        self.assertTrue(blocks,
                        "ни один блок документа не называет новый исход "
                        "вместе с пином")


if __name__ == "__main__":
    unittest.main()
