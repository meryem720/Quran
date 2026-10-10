import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import build  # noqa: E402


class NormalizeTest(unittest.TestCase):
    def test_removes_diacritics_and_unifies_letters(self):
        self.assertEqual(build.normalize("ٱلرَّحْمَٰنِ"), "الرحمن")
        self.assertEqual(build.normalize("أَدْرَىٰكَ"), "ادريك")
        self.assertEqual(build.normalize("ٱلصَّلَوٰةَ"), "الصلوه")


class PipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verses = build.parse_morphology(build.MORPH_FILE)
        cls.index = {(v["s"], v["a"]): i for i, v in enumerate(cls.verses)}

    def test_all_verses_parsed(self):
        self.assertEqual(len(self.verses), 6236)
        self.assertEqual(self.verses[0]["s"], 1)
        self.assertEqual(self.verses[-1]["s"], 114)

    def test_words_and_roots(self):
        words = self.verses[self.index[(86, 3)]]["words"]
        self.assertEqual([build.normalize(w["text"]) for w in words], ["النجم", "الثاقب"])
        self.assertEqual([w["root"] for w in words], ["نجم", "ثقب"])

    def test_context_links(self):
        links = build.context_links(self.verses)
        i = self.index
        # ﴿وما أدراك ما الطارق﴾ ← ﴿النجم الثاقب﴾
        self.assertEqual(links[i[(86, 2)]][i[(86, 3)]], build.CONTEXT_ADRAKA)
        # ﴿وما أدراك ما يوم الدين ۝ ثم ما أدراك ما يوم الدين ۝ يوم لا تملك…﴾
        self.assertIn(i[(82, 19)], links[i[(82, 17)]])
        # ﴿هدى للمتقين﴾ ← ﴿الذين يؤمنون بالغيب﴾
        self.assertEqual(links[i[(2, 2)]][i[(2, 3)]], build.CONTEXT_RELATIVE)

        # ﴿هل أتاك حديث الجنود﴾ ← ﴿فرعون وثمود﴾
        self.assertEqual(links[i[(85, 17)]][i[(85, 18)]], build.CONTEXT_QUESTION)
        # ﴿لأي يوم أجلت﴾ ← ﴿ليوم الفصل﴾ و﴿وما تلك بيمينك يا موسى﴾ ← ﴿قال هي عصاي﴾
        self.assertEqual(links[i[(77, 12)]][i[(77, 13)]], build.CONTEXT_DIALOGUE)
        self.assertEqual(links[i[(20, 17)]][i[(20, 18)]], build.CONTEXT_DIALOGUE)
        # اللازمة ﴿فبأي آلاء ربكما تكذبان﴾ ليست سؤالًا يُجاب عنه في الآية التالية
        self.assertNotIn(i[(55, 17)], links.get(i[(55, 16)], {}))

    def test_expression_matches_different_forms(self):
        scores, _ = build.expression_similarity(self.verses)
        # ﴿أنعمتَ عليهم﴾ و﴿أنعم اللهُ عليهم﴾
        self.assertGreater(scores[self.index[(1, 7)]].get(self.index[(4, 69)], 0), 0)


if __name__ == "__main__":
    unittest.main()
