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
        # ﴿أيحسب الإنسان ألن نجمع عظامه ۝ بلى قادرين على أن نسوي بنانه﴾
        self.assertEqual(links[i[(75, 3)]][i[(75, 4)]], kinds["bala"])
        # ﴿فاقطعوا أيديهما… ۝ فمن تاب من بعد ظلمه وأصلح﴾، و«ومن» عطف لا تفريع (البقرة 114)
        self.assertEqual(links[i[(5, 38)]][i[(5, 39)]], kinds["faman"])
        self.assertIsNone(self.verses[i[(2, 114)]]["start"])
        # ﴿زين للناس حب الشهوات ۝ قل أؤنبئكم بخير من ذلكم﴾
        self.assertEqual(links[i[(3, 14)]][i[(3, 15)]], build.CONTEXT_COMPARISON)
        # ﴿ويسألونك عن المحيض ۝ نساؤكم حرث لكم﴾
        self.assertEqual(links[i[(2, 222)]][i[(2, 223)]], build.CONTEXT_ASKED)
        # ﴿قالت نملة… ۝ فتبسم ضاحكا من قولها﴾
        self.assertEqual(links[i[(27, 18)]][i[(27, 19)]], build.CONTEXT_NARRATIVE)
        # الآية التي تبدأ بحرف عطف أو جر كلام جديد: ﴿والذين يؤمنون بما أنزل إليك﴾، ﴿في جنات النعيم﴾
        self.assertNotIn(i[(2, 4)], links.get(i[(2, 3)], {}))
        self.assertNotIn(i[(56, 12)], links.get(i[(56, 11)], {}))

    def test_cause_and_purpose_are_shown_not_ranked(self):
        # ﴿ذلك بأن الله نزّل الكتاب بالحق﴾ تعلّل ما قبلها، و﴿ليجزي الذين آمنوا﴾ غايته: يُعرضان في صفحة
        # الآية (quran.json) ولا يدخلان في ترتيب الروابط
        explains = build.build_quran(self.verses)["explains"]
        self.assertEqual(explains["2:176"], "cause")
        self.assertEqual(explains["30:45"], "purpose")
        self.assertEqual(explains["3:141"], "purpose")  # ﴿وليمحص الله الذين آمنوا﴾: واو ثم لام التعليل
        self.assertNotIn("53:30", explains)  # ﴿ذلك مبلغهم من العلم﴾ ليست تعليلًا
        self.assertTrue(self.verses[self.index[(30, 45)]]["purpose"])
        self.assertIsNone(self.verses[self.index[(30, 45)]]["start"])
        links = build.context_links(self.verses)
        self.assertNotIn(self.index[(2, 176)], links.get(self.index[(2, 175)], {}))

    def test_initials_link_same_letters(self):
        # ﴿الم﴾ في أول البقرة وآل عمران والعنكبوت والروم ولقمان والسجدة
        links = build.context_links(self.verses)
        i = self.index
        self.assertEqual(links[i[(2, 1)]][i[(3, 1)]], build.CONTEXT_INITIALS)
        self.assertNotIn(i[(40, 1)], links[i[(2, 1)]])

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

    def test_parallel_story(self):
        parallel = lambda ref: {k: x[3] for k, x in self.ids(ref).items()
                                if isinstance(x[3], list) and x[3][0] == build.CONTEXT_PARALLEL}
        # ﴿فتلقى آدم من ربه كلمات فتاب عليه﴾ ← ﴿ثم اجتباه ربه فتاب عليه وهدى﴾ في قصة آدم في طه
        self.assertEqual(parallel("2:37")["20:122"], [build.CONTEXT_PARALLEL, 20, 116, 123])
        # ﴿فأوجس في نفسه خيفة موسى﴾ ← ﴿وأوحينا إلى موسى أن ألق عصاك﴾ (الأعراف)
        self.assertIn("7:117", parallel("20:67"))
        # قصة نوح ثم قصة صالح تتتابعان في الأعراف وهود، فلا تتقابل آياتهما
        self.assertNotIn("11:61", parallel("7:61"))
        self.assertNotIn("7:77", parallel("11:32"))

    def test_theft_verse_is_explained_by_its_ruling(self):
        items = self.related["5:38"]
        # أول بيان: الآية التالية ﴿فمن تاب من بعد ظلمه﴾ (كلام متصل)
        self.assertEqual(items[0][:2], [5, 39])
        self.assertEqual(items[0][3], build.CONTEXT_CONTINUATION["faman"])
        # لا رابط يبيّن الخاتمة ﴿والله عزيز حكيم﴾ وحدها
        self.assertFalse([x for x in items if len(x) > 8 and x[8] == 1])

    def test_bare_phrases(self):
        verses = build.parse_morphology(build.MORPH_FILE)
        # ﴿والله﴾: الواو حرف عطف بوسوم الصرف، فتُحذف عند مطابقة العبارات
        word = verses[[k for k, v in enumerate(verses) if (v["s"], v["a"]) == (33, 53)][0]]["words"]
        self.assertIn("الله", [build._bare(w) for w in word])

    def test_rare_word_reason_is_listed(self):
        item = self.ids("15:87")["39:23"]
        self.assertEqual(build.normalize(item[7][0]), "المثاني")
        self.assertEqual(item[7][1], 2)


if __name__ == "__main__":
    unittest.main()


class ClauseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verses = build.parse_morphology(build.MORPH_FILE)
        cls.index = {(v["s"], v["a"]): i for i, v in enumerate(cls.verses)}
        cls.clauses = build.load_clauses(cls.verses)

    def text(self, ref, c):
        i = self.index[ref]
        a, b = self.clauses[i][c]
        return " ".join(build.normalize(w["text"]) for w in self.verses[i]["words"][a:b])

    def test_waqf_splits_verse_into_sentences(self):
        # آية الكرسي تسع جمل بحسب علامات الوقف في المصحف
        self.assertEqual(len(self.clauses[self.index[(2, 255)]]), 9)
        self.assertEqual(self.text((2, 255), 3), "من ذا الذي يشفع عنده الا باذنه")
        # الآية بلا وقف داخلها جملة واحدة
        self.assertEqual(len(self.clauses[self.index[(112, 1)]]), 1)

    def test_fasila_words(self):
        fasila = build.fasila_lemmas(self.verses)
        for word in ("عليم", "حكيم", "رحيم", "غفور"):
            self.assertIn("L:" + word, fasila)
        # «عذاب» يختم آيات كثيرة لكنه ليس صيغة ختام في أكثر مواضعه
        self.assertNotIn("L:عذاب", fasila)

    def test_clause_explanations(self):
        _, idf, _ = build.root_similarity(self.verses)
        by_clause, formulas = build.clause_similarity(self.verses, self.clauses, idf)
        i = self.index
        # ﴿من ذا الذي يشفع عنده إلا بإذنه﴾ ← ﴿ولا تنفع الشفاعة عنده إلا لمن أذن له﴾ (سبأ 23)
        self.assertEqual(by_clause[i[(2, 255)]][i[(34, 23)]][1], 3)
        # ﴿كذلك يبين الله لكم الآيات لعلكم تتفكرون﴾ صيغة ختام في البقرة 219
        self.assertIn(len(self.clauses[i[(2, 219)]]) - 1, formulas[i[(2, 219)]])
        # ﴿والله عزيز حكيم﴾ كل ألفاظها من أسماء الفواصل: صيغة ختام في المائدة 38
        self.assertIn(1, formulas[i[(5, 38)]])
