import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import build  # noqa: E402
import dictionary  # noqa: E402

# مقتطفات بصيغة نص OpenITI لمختار الصحاح
SAMPLE = """#META#Header#End#
# ط و ر عدا طوره أي جاوز حده و الطور التارة وقوله تعالى @QB@ وقد خلقكم أطوارا @QE@ قال الأخفش
~~طورا علقة وطورا مضغة و الطور الجبل
# س ج ل السجل الصك وقد سجل الحاكم تسجيلا وقوله تعالى @QB@ حجارة من سجيل @QE@ قالوا هي
~~حجارة من طين طبخت بنار جهنم
# خ ي ر الخير ضد الشر و الخير بالكسر الكرم
# م ث ن المثاني من القرآن ما كان أقل من المئين
"""


class SensesTest(unittest.TestCase):
    def senses(self, root):
        return [(h, d) for r, body in dictionary.entries(SAMPLE) if r == root
                for h, _, d in dictionary.senses(body)]

    def test_definition_style(self):
        # «و الطور الجبل» ← (الطور، الجبل)، ويُقطع التعريف قبل التعليق على الآية
        self.assertEqual(self.senses("طور"), [("الطور", "التارة"), ("الطور", "الجبل")])

    def test_no_commentary_on_verses(self):
        # ﴿حجارة من سجيل﴾ «قالوا هي حجارة من طين»: تفسير، لا يُؤخذ
        text = " ".join(d for _, d in self.senses("سجل"))
        self.assertNotIn("طين", text)
        # «المثاني: من القرآن…» قول في تفسير آية، لا يُؤخذ
        self.assertEqual(self.senses("مثن"), [])


class CleanTest(unittest.TestCase):
    def test_meaning_only(self):
        # يُحذف التصريف والجمع والضبط، ويبقى المعنى
        self.assertEqual(dictionary.clean("ضد الجد وقد هزل من باب ضرب"), "ضد الجد")
        self.assertEqual(dictionary.clean("مكسور ممدود الدواء وهو الأطبة جمع الآسي مثل"), "الدواء وهو الأطبة")
        self.assertEqual(dictionary.clean("الإعلام وأذان الصلاة معروف وقد أذن أذانا"), "الإعلام")
        self.assertEqual(dictionary.clean("شجر وهو نوع من الطرفاء الواحدة أثلة"), "شجر وهو نوع من الطرفاء")
        # ضبط أو تصريف قبل المعنى
        self.assertEqual(dictionary.clean("وضم الثاء العقوبة"), "العقوبة")
        self.assertEqual(dictionary.clean("وضم الثاء وهو العقوبة"), "العقوبة")
        # «مصدر الأخرق وهو…» معنى لفظ آخر بضبط آخر، و«مصدر وهو شاذ… أي فصله» ليس معنى
        self.assertEqual(dictionary.clean("مصدر الأخرق وهو ضد الرفيق"), "")
        self.assertEqual(dictionary.clean("مصدر وهو شاذ لأن المصادر إنما تجيء على التفعال أي فصله"), "")
        # المعنى الذي أوله «ضم/فتح/كسر» بلا واو يبقى
        self.assertEqual(dictionary.clean("ضم الشيء إلى الشيء"), "ضم الشيء إلى الشيء")
        # الجمع في وسط التعريف أو أوله يُقطع عنده
        self.assertEqual(dictionary.clean("الأمعاء جمع حوية"), "الأمعاء")
        self.assertEqual(dictionary.clean("جمعها في القلة أبور كأفلس"), "")
        # المعنى القصير يبقى («الكافور: من الطيب»، «الدُّولة: في المال»)، والاسم الذي أوله واو
        self.assertEqual(dictionary.clean("من الطيب"), "من الطيب")
        self.assertEqual(dictionary.clean("وعاء"), "وعاء")
        # «جمع» فعلًا لا جمعًا: «الذي جمع من هاهنا»
        self.assertTrue(dictionary.clean("الذي جمع من هاهنا وها هنا").startswith("الذي جمع"))
        # ما ليس معنى يُترك كله
        self.assertEqual(dictionary.clean("لا واحد لها من لفظها وهي مؤنثة لأن"), "")
        self.assertEqual(dictionary.clean("والكذب"), "")
        self.assertEqual(dictionary.clean("جمعه ستور"), "")
        self.assertEqual(dictionary.clean("مصدر وسق الشيء أي جمعه وحمله"), "جمعه وحمله")


class GlossesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verses = build.parse_morphology(build.MORPH_FILE)

    def test_rare_words_only_and_spelling_notes(self):
        glosses = dictionary.build_glosses(SAMPLE, self.verses)
        self.assertEqual(glosses["طور"]["d"], ["التارة", "الجبل"])
        # «الخير» كثير الورود في القرآن: ليس من الغريب
        self.assertNotIn("خير", glosses)

    def test_published_glosses(self):
        path = dictionary.OUT_FILE
        if not os.path.exists(path):
            self.skipTest("لم يُنشأ web/data/glosses.json")
        with open(path, encoding="utf-8") as f:
            glosses = json.load(f)
        self.assertIn("الجبل", glosses["طور"]["d"])
        self.assertEqual(glosses["نون"]["d"], ["الحوت"])
        # لا شيء من تفسير الآيات
        for entry in glosses.values():
            for d in entry["d"]:
                self.assertNotRegex(d, "تعالى|القرآن|الآية|@QB@|فسر")
        # «سنة» تُكتب كتابة واحدة لألفاظ مختلفة (سُنّة، سَنة، سِنة): لا معنى لها
        self.assertNotIn("سنه", glosses)


if __name__ == "__main__":
    unittest.main()
