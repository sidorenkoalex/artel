"""AC-5, AC-6, AC-7 (SPEC.md, требование 3) — восстановление пула:
`init` и `doctor --restore` расшифровывают `canary/pool.sealed` в
`~/.artel-canary`, когда каталога там нет, тем же образом друг для
друга; если каталог уже есть — обе команды его не трогают.

Красен до реализации: `pool-seal` пока не существует (см. `test_pool_
seal.py`), поэтому `canary/pool.sealed` в этой песочнице не появляется
вовсе — `test_ac5_.../test_ac6_...` падают на `assertTrue(self.pool_
dir.exists())` после `init`/`doctor --restore`: расшифровывать нечего,
каталог `~/.artel-canary` не создаётся. `test_ac7_...` красен по ДРУГОЙ,
корректной для состояния «функциональности ещё нет» причине —
проходит уже сегодня ТРИВИАЛЬНО (ни `init`, ни `doctor --restore`
сегодня вообще не знают о пуле, значит и не трогают существующий
каталог) и потому не может служить сигналом «восстановление
реализовано корректно» до появления двух предыдущих тестов — это
намеренно (одно наблюдаемое поведение AC-7, «не потрогали», неотличимо
от «функциональности ещё нет», и это честно сказано здесь текстом, не
скрыто).
"""
import shutil
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import PoolBaseSandbox, PoolDoctorSandbox, dir_fingerprint  # noqa: E402

TEMPLATES = {
    "a.md": "# А\n\nтело шаблона А.\n",
    "b.md": "# Б\n\nтело шаблона Б.\n",
}


class InitRestoreTest(PoolBaseSandbox):

    def test_ac5_init_restores_pool_from_sealed_file_when_directory_missing(self):
        """Пул запечатан, открытый каталог `~/.artel-canary` затем
        стёрт целиком; `init` без каталога пула обязан расшифровать
        `canary/pool.sealed` обратно в `~/.artel-canary` (вне дерева
        пульта — `self.root`) с тем же набором файлов.

        Ловит мутацию: `init` не подключает восстановление пула вовсе
        (или подключает, но кладёт файлы ВНУТРЬ `self.root`, то есть в
        дерево пульта, — нарушая «вне дерева пульта» требования 1
        родительской SPEC) — `pool_dir.exists()`/сравнение отпечатков
        ниже падает.
        """
        self.write_pool_templates(TEMPLATES)
        original_fingerprint = dir_fingerprint(self.pool_dir)
        self.seal()
        shutil.rmtree(self.pool_dir)

        output = self.restore_via_init()

        self.assertTrue(
            self.pool_dir.exists(),
            f"`init` не восстановил ~/.artel-canary из canary/pool.sealed: "
            f"{output!r}")
        self.assertFalse(
            str(self.pool_dir).startswith(str(self.root)),
            f"пул восстановлен ВНУТРИ дерева пульта ({self.pool_dir}), "
            f"должен быть вне (~/.artel-canary)")
        self.assertEqual(
            dir_fingerprint(self.pool_dir), original_fingerprint,
            "восстановленный `init` пул отличается от запечатанного")


class DoctorRestoreTest(PoolDoctorSandbox):

    def test_ac6_doctor_restore_flag_restores_pool_the_same_way_as_init(self):
        """То же самое восстановление (AC-5), но через `doctor
        --restore` вместо `init` — требование 3 SPEC называет оба входа
        равноправными.

        Ловит мутацию: разработчик подключает восстановление только к
        `init`, забыв про `doctor --restore` (или наоборот) — этот тест
        и `InitRestoreTest` ловят ровно эту асимметрию по отдельности.
        """
        self.write_pool_templates(TEMPLATES)
        original_fingerprint = dir_fingerprint(self.pool_dir)
        self.seal()
        shutil.rmtree(self.pool_dir)

        output = self.restore_via_doctor()

        self.assertTrue(
            self.pool_dir.exists(),
            f"`doctor --restore` не восстановил ~/.artel-canary: {output!r}")
        self.assertEqual(
            dir_fingerprint(self.pool_dir), original_fingerprint,
            "восстановленный `doctor --restore` пул отличается от "
            "запечатанного")

    def test_ac7_existing_pool_directory_is_left_untouched_by_both_commands(self):
        """Каталог `~/.artel-canary` уже существует (со СВОИМ, отличным
        от запечатанного, содержимым) — ни `init`, ни `doctor --restore`
        не переписывают его.

        Ловит мутацию: восстановление срабатывает безусловно, не
        проверяя наличие каталога (`pool_dir.exists()`) — тогда местный
        файл `own.md` пропал бы или сменил содержимое после любого из
        двух вызовов.
        """
        own_text = "локальная правка Оператора, ещё не запечатанная\n"
        self.write_pool_templates({"own.md": own_text})

        # Отдельно запечатываем ДРУГОЕ содержимое — если бы восстановление
        # игнорировало «каталог уже есть», расхождение проявилось бы сразу.
        other_dir_texts = dict(TEMPLATES)
        real_pool_dir = self.pool_dir
        self.write_pool_templates(other_dir_texts)  # затирает own.md — чиним ниже
        self.seal()
        # Возвращаем каталог к состоянию «уже есть, отличается от sealed».
        shutil.rmtree(real_pool_dir)
        real_pool_dir.mkdir(parents=True)
        (real_pool_dir / "own.md").write_text(own_text, encoding="utf-8")

        self.restore_via_init()
        self.assertEqual(
            (real_pool_dir / "own.md").read_text(encoding="utf-8"), own_text,
            "`init` переписал уже существующий каталог пула")
        self.assertEqual(
            sorted(p.name for p in real_pool_dir.iterdir()), ["own.md"],
            "`init` добавил в существующий каталог пула файлы из sealed")

        self.restore_via_doctor()
        self.assertEqual(
            (real_pool_dir / "own.md").read_text(encoding="utf-8"), own_text,
            "`doctor --restore` переписал уже существующий каталог пула")
        self.assertEqual(
            sorted(p.name for p in real_pool_dir.iterdir()), ["own.md"],
            "`doctor --restore` добавил в существующий каталог пула файлы "
            "из sealed")


if __name__ == "__main__":
    unittest.main()
