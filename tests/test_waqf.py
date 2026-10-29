import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import waqf  # noqa: E402


class WaqfTest(unittest.TestCase):
    def test_detached_letter_after_open_tanween_is_rejoined(self):
        # في النص المصدر: «هُدࣰ ى» كلمة واحدة مقطوعة
        self.assertEqual(waqf.words("ذَٰلِكَ ٱلۡكِتَٰبُ لَا رَيۡبَۛ فِيهِۛ هُدࣰ ى لِّلۡمُتَّقِينَ"),
                         ["ذَٰلِكَ", "ٱلۡكِتَٰبُ", "لَا", "رَيۡبَۛ", "فِيهِۛ", "هُدࣰى", "لِّلۡمُتَّقِينَ"])

    def test_clause_ends(self):
        # ۚ و ۖ حدّان، والمعانقة ۛ ليست حدًّا
        self.assertEqual(waqf.clause_ends("أ بۚ ج دۖ ه", 5), [2, 4])
        self.assertEqual(waqf.clause_ends("لَا رَيۡبَۛ فِيهِۛ هُدࣰى", 4), [])
        # عدد كلمات مختلف عن بيانات الصرف: لا تقسيم
        self.assertIsNone(waqf.clause_ends("أ بۚ ج", 4))


if __name__ == "__main__":
    unittest.main()
