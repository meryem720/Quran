import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import dictionary  # noqa: E402

SAMPLE = """#META#Header#End#
# ك م م الكلام اسم جنس يقع على القليل والكثير و الكلم الجراحة والجمع كلوم و
~~كلام وقد كلمه من باب ضرب ومنه قراءة من قرأ @QB@ دابة من الأرض تكلمهم @QE@ أي تجرحهم
~~و التكليم التجريح وعيسى عليه السلام كلمة الله
# ك م م الكم للقميص والجمع أكمام
"""


class RootEntryTest(unittest.TestCase):
    def test_lexical_senses_only(self):
        senses = dictionary.root_entry(SAMPLE, "كلم")
        self.assertIn("الكلم الجراحة والجمع كلوم", senses)
        # قُطع ما بعد ذكر القراءة والنبي: لا تفسير ولا كلام في عيسى
        self.assertIn("التكليم التجريح", senses)
        self.assertFalse([x for x in senses if "تجرحهم" in x or "عيسى" in x or "@QB@" in x])
        # «ك م م» تجمع في هذه النسخة مادتين: لا يُؤخذ «الكم للقميص» في جذر «كلم»
        self.assertFalse([x for x in senses if "القميص" in x])

    def test_published_root_senses(self):
        path = dictionary.ROOTS_FILE
        if not os.path.exists(path):
            self.skipTest("لم يُنشأ web/data/root_senses.json")
        with open(path, encoding="utf-8") as f:
            roots = json.load(f)
        self.assertEqual(sorted(roots), sorted(dictionary.ROOT_SENSES))
        self.assertTrue(any("الجراحة" in x for x in roots["كلم"]))
        for senses in roots.values():
            for x in senses:
                self.assertNotRegex(x, "تعالى|القرآن|الآية|@QB@|عليه السلام")


if __name__ == "__main__":
    unittest.main()
