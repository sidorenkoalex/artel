"""Эталон пина: вывод мест таблицы у артели, записи `test_profile` и записей из одного компонента побайтно прежний (AC-26); мандаты ослабления и матрица у таких записей, в том числе у канарейки, — прежние (AC-15).

Группа: разовый
Зелёный с рождения: эталон снимается с кода пина (`_pult.DIFF_BASE`) в момент прогона, и до реализации код ветки совпадает с пином по местам — тест держит, что перевод мест на `for_task` и новый путь мандата не меняют вывод записей, которых задача не касается.

Файл разовый: «код пина» — база ветки этой задачи; после мержа сравнивать
не с чем. Сценарий мест — `_etalon.py`: он исполняется дважды отдельным
процессом — из дерева кода пина (`git archive` базы диффа во временный
каталог) и из рабочей копии ветки — с одним зерном, и выводы сравниваются
по каждому месту. Места: решение `for_task`/`decide`, мандат «Ослабление
тестов разрешено:» и «Ослабление теста по идентификатору разрешено:»
(`mandate.refusals`), покрытие матрицы (`mandate.matrix_refusals`),
`acceptance._task_own_profile`/`_task_profile`, `amend._task_profile`/
`_profile_or_exit`, команда `knowledge`, засчитывание долгоживущего файла
test_author, предпроверка, чекпоинты test_author и developer — у задач
артели, записи `test_profile`, записи из одного компонента pytest
(`junit-xml`), того же без поля `report` (вне границы гейта исходов) и
записи из одного компонента Vitest; каждая задача — и обычная, и канарейка.
"""
import io
import json
import os
import random
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _pult import CODE_ROOT, DIFF_BASE  # noqa: E402

BEGIN = "=== ЭТАЛОН НАЧАЛО ==="
END = "=== ЭТАЛОН КОНЕЦ ==="
MANDATE_KEYS = ("/weaken/", "/id/", "/matrix/", "/idmatrix/")


def _run(code_dir: Path, script: Path, seed: int) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(code_dir)
    env.pop("PYTHONSAFEPATH", None)
    res = subprocess.run([sys.executable, str(script), str(seed)],
                         cwd=str(code_dir), env=env, capture_output=True,
                         text=True, timeout=110)
    if res.returncode != 0 or BEGIN not in res.stdout:
        raise AssertionError(f"сценарий эталона в {code_dir} не исполнился "
                             f"(код {res.returncode}):\n{res.stdout[-3000:]}\n"
                             f"{res.stderr[-3000:]}")
    body = res.stdout.split(BEGIN, 1)[1].split(END, 1)[0]
    return json.loads(body)


class PinEtalonTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.seed = random.randrange(1 << 30)
        print(f"зерно: {cls.seed}")
        cls.tmp = tempfile.mkdtemp(prefix="pin-etalon-")
        pin = Path(cls.tmp) / "pin"
        pin.mkdir()
        archive = subprocess.run(
            ["git", "-C", str(CODE_ROOT), "archive", DIFF_BASE, "--", ".",
             ":(exclude)tasks"], capture_output=True, timeout=60)
        if archive.returncode != 0:
            raise AssertionError(f"git archive {DIFF_BASE}: "
                                 f"{archive.stderr.decode(errors='replace')}")
        with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
            tar.extractall(pin, filter="data")
        shutil.copy(HERE / "_etalon.py", pin / "_etalon_run.py")
        cls.pin = _run(pin, pin / "_etalon_run.py", cls.seed)
        cls.head = _run(Path(CODE_ROOT), HERE / "_etalon.py", cls.seed)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def note(self, text: str = "") -> str:
        return f"зерно: {self.seed}; база диффа: {DIFF_BASE}; {text}"

    def differences(self, keys) -> list:
        return [f"{key}:\n  пин:   {self.pin.get(key)!r}\n  ветка: {self.head.get(key)!r}"
                for key in keys if self.pin.get(key) != self.head.get(key)]

    def assert_sane(self) -> None:
        """Эталон не вырожден: у записи из одного компонента профиль есть."""
        decision = self.pin.get("onepy/for_task", {}).get("value", "")
        self.assertIn('"component": "app"', decision, self.note(decision))
        refusal = self.pin.get("onepy/id/app:tests/test_a.py::test_x", {})
        self.assertIn("вне области", refusal.get("value", ""), self.note(str(refusal)))

    def test_ac15_mandate_unchanged_single_component_artel_canary(self):
        """Мандаты ослабления (путь и идентификатор) и покрытие матрицы у артели, записи из одного компонента и `test_profile` — побайтно как на пине, у обычной задачи и у канарейки.

        Сценарий: элементы обоих маркеров на пути в области и вне её, на
        идентификаторах своего компонента, чужого имени и несуществующего,
        ячейки покрытия `tests/…`, путь области, идентификатор в кавычках,
        «не покрыто» — у каждой задачи.

        Ловит мутацию: новый путь мандата берёт границу по любому компоненту
        и у записи из одного компонента вне границы (`onebare`) годит
        идентификатор — пропадает отказ «мандат по идентификатору действует
        только у компонента …»; либо `matrix_refusals` у артели засчитывает
        покрытием путь `backend/…` (отказа «свойство остаётся и не покрыто»
        нет); либо канарейка начинает влиять на границу мандата.
        """
        self.assert_sane()
        keys = sorted(k for k in set(self.pin) | set(self.head)
                      if any(m in k for m in MANDATE_KEYS))
        self.assertTrue(keys, self.note("нет мест мандата"))
        self.assertTrue(any("/canary/" in k for k in keys), self.note())
        diff = self.differences(keys)
        self.assertEqual(diff, [], self.note("\n".join(diff[:20])))

    def test_ac26_places_output_matches_pin(self):
        """Все места сценария у артели, `test_profile` и записей из одного компонента дают вывод, побайтно равный эталону пина.

        Ловит мутацию: `decide_task` выбирает компонент по зонам и у записи
        из одного компонента (у задачи без зон — отказ «зоны задачи не
        заданы …» вместо профиля); место переведено на `for_task`, который
        у записи из одного компонента читает колонки зон и падает; чекпоинт
        test_author коммитит иной набор файлов.
        """
        self.assert_sane()
        keys = sorted(set(self.pin) | set(self.head))
        missing = sorted(set(self.pin) ^ set(self.head))
        self.assertEqual(missing, [], self.note("места есть только в одном прогоне"))
        diff = self.differences(keys)
        self.assertEqual(diff, [], self.note("\n".join(diff[:20])))


if __name__ == "__main__":
    unittest.main()
