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
        # ولا ﴿ويل يومئذ للمكذبين﴾ جوابًا لـ﴿وما أدراك ما يوم الفصل﴾
        self.assertNotIn(i[(77, 15)], links.get(i[(77, 14)], {}))

    def test_continuation_links(self):
        links = build.context_links(self.verses)
        i = self.index
        kinds = build.CONTEXT_CONTINUATION
        # ﴿إن الإنسان لفي خسر ۝ إلا الذين آمنوا﴾
        self.assertEqual(links[i[(103, 2)]][i[(103, 3)]], kinds["illa"])
        # ﴿قتل أصحاب الأخدود ۝ النارِ ذات الوقود﴾ و﴿الحمد لله رب العالمين ۝ الرحمنِ الرحيم﴾
        self.assertEqual(links[i[(85, 4)]][i[(85, 5)]], kinds["gen"])
        self.assertEqual(links[i[(1, 2)]][i[(1, 3)]], kinds["gen"])
        # ﴿ولا تخزني يوم يبعثون ۝ يوم لا ينفع مال ولا بنون﴾
        self.assertEqual(links[i[(26, 87)]][i[(26, 88)]], kinds["yawm"])
        # ﴿والسابقون السابقون ۝ أولئك المقربون﴾
        self.assertEqual(links[i[(56, 10)]][i[(56, 11)]], kinds["ulaika"])
        # ﴿إن الإنسان خلق هلوعا ۝ إذا مسه الشر جزوعا﴾
        self.assertEqual(links[i[(70, 19)]][i[(70, 20)]], kinds["idha"])
        # الآية التي تبدأ بحرف عطف أو جر كلام جديد: ﴿والذين يؤمنون بما أنزل إليك﴾، ﴿في جنات النعيم﴾
        self.assertNotIn(i[(2, 4)], links.get(i[(2, 3)], {}))
        self.assertNotIn(i[(56, 12)], links.get(i[(56, 11)], {}))

    def test_proper_names_are_features(self):
        # «إبراهيم» لا جذر له في البيانات، ويُحسب لمّةً: ﴿مقام إبراهيم﴾
        feats = build.root_features(self.verses[self.index[(3, 97)]])
        self.assertIn("L:" + build.normalize("إِبْراهِيم"), feats)

    def test_rare_word_links(self):
        rare = build.rare_word_links(self.verses)
        i = self.index
        # ﴿سبعا من المثاني﴾ و﴿كتابا متشابها مثاني﴾: لا يرد «مثاني» إلا فيهما
        strength, word, count = rare[i[(15, 87)]][i[(39, 23)]]
        self.assertGreater(strength, 0.5)
        self.assertEqual(count, 2)
        self.assertEqual(build.normalize(word), "المثاني")
        # «كَثُرَت» صيغة نادرة من جذر شائع (كثر)، فلا تربط ﴿ولو كثرت﴾ بـ﴿مما قل منه أو كثر﴾،
        # أما «تستفتحوا» فنادرة الجذر: ﴿إن تستفتحوا فقد جاءكم الفتح﴾ و﴿وكانوا من قبل يستفتحون﴾
        self.assertNotIn(i[(4, 7)], rare.get(i[(8, 19)], {}))
        self.assertIn(i[(2, 89)], rare.get(i[(8, 19)], {}))

    def test_expression_matches_different_forms(self):
        scores, _ = build.expression_similarity(self.verses)
        # ﴿أنعمتَ عليهم﴾ و﴿أنعم اللهُ عليهم﴾
        self.assertGreater(scores[self.index[(1, 7)]].get(self.index[(4, 69)], 0), 0)


class RelatedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.related = build.build_related(build.parse_morphology(build.MORPH_FILE))

    def ids(self, ref):
        return {f"{x[0]}:{x[1]}": x for x in self.related[ref]}

    def test_answer_elsewhere_needs_the_subject(self):
        # ﴿مالك يوم الدين﴾ ← جواب ﴿وما أدراك ما يوم الدين﴾ (الانفطار 19)
        self.assertEqual(self.ids("1:4")["82:19"][3][:3], [build.CONTEXT_ANSWER_ELSEWHERE, 82, 17])
        # ﴿هل أتاك حديث ضيف إبراهيم﴾ لا يأخذ جواب ﴿هل أتاك حديث موسى﴾ لاشتراك الصيغة وحدها
        self.assertNotIn("79:16", self.ids("51:24"))

    def test_rare_word_reason_is_listed(self):
        item = self.ids("15:87")["39:23"]
        self.assertEqual(build.normalize(item[7][0]), "المثاني")
        self.assertEqual(item[7][1], 2)


if __name__ == "__main__":
    unittest.main()
