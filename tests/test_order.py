import os
import sys
import unittest
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import order  # noqa: E402


class OrderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.verses = order.parse_words()
        cls.words = {(v["s"], v["a"]): v["words"] for v in cls.verses}
        cls.passages, cls.mentions, cls.stages = order.analyze(cls.verses)
        cls.era_of = {}
        for era, s, a1, a2 in cls.passages:
            for a in range(a1, a2 + 1):
                cls.era_of.setdefault((s, a), []).append(era)
        cls.data = order.build_order(cls.verses)

    def covers(self, era, s, a1, a2):
        return any(e == era and ps == s and p1 <= a1 and a2 <= p2 for e, ps, p1, p2 in self.passages)

    def test_markers_name_real_lemmas(self):
        # كل علامة تسمّي لمّة موجودة في بيانات الصرف (لا خطأ في كتابة «إسرائيل» أو «موسى»)
        names, lemmas = set(), set()
        for v in self.verses:
            for w in v["words"]:
                lemmas.add(w["lem"])
                if w["pn"]:
                    names.add(w["lem"])
        for marker, _ in order.all_markers():
            for token in marker:
                if token[0] == "@":
                    self.assertIn(token[1:], names, marker)
                elif token[0] == "=":
                    self.assertIn(token[1:], lemmas, marker)

    def test_each_verse_in_one_era_at_most(self):
        for key, eras in self.era_of.items():
            self.assertEqual(len(eras), 1, (key, eras))

    def test_whole_stories(self):
        self.assertTrue(self.covers("yusuf", 12, 4, 101))
        self.assertTrue(self.covers("musa", 20, 9, 98))
        self.assertTrue(self.covers("musa", 28, 3, 46))
        self.assertTrue(self.covers("nuh", 11, 25, 48))
        self.assertTrue(self.covers("nuh", 71, 1, 28))
        self.assertTrue(self.covers("ibrahim", 37, 83, 113))  # ومعها ﴿فلما بلغ معه السعي﴾ بلا ذكر لاسمه
        self.assertTrue(self.covers("adam", 5, 27, 31))  # ﴿ابني آدم﴾ لا ﴿بني إسرائيل﴾ بعدها
        self.assertTrue(self.covers("u:kahf", 18, 9, 25))
        self.assertTrue(self.covers("u:dhulqarnayn", 18, 83, 98))
        self.assertTrue(self.covers("salih", 7, 73, 79))
        self.assertTrue(self.covers("hud", 7, 65, 72))  # ﴿من بعد قوم نوح﴾ في قصة هود ذكر عابر

    def test_not_stories(self):
        # ﴿يا بني إسرائيل اذكروا نعمتي﴾ خطاب للسامعين لا تتمة لقصة آدم
        self.assertNotIn((2, 40), self.era_of)
        # أحكام الحج بين ﴿وإذ بوأنا لإبراهيم﴾ و﴿وقوم إبراهيم﴾ في تعداد الأمم
        self.assertNotIn((22, 30), self.era_of)
        # ﴿وزلزلوا﴾ ليست زلزلة الساعة: الآية من ذكر الجنة لا من أهوال الساعة
        self.assertEqual(self.stages[(2, 214)], 4)
        self.assertEqual(self.era_of[(11, 89)], ["shuayb"])  # ﴿وما قوم لوط منكم ببعيد﴾ في قصة شعيب

    def test_references(self):
        w = self.words
        # ﴿من بعد قوم نوح﴾ و﴿ملة إبراهيم﴾ و﴿ولقد جاءكم يوسف من قبل﴾ ذكر عابر
        self.assertTrue(order.is_reference(w[(7, 69)], [x["nt"] for x in w[(7, 69)]].index("قوم")))
        self.assertTrue(order.is_reference(w[(3, 95)], [x["nt"] for x in w[(3, 95)]].index("ابرهيم")))
        self.assertTrue(order.is_reference(w[(40, 34)], [x["nt"] for x in w[(40, 34)]].index("يوسف")))
        # ﴿ثم بعثنا من بعدهم موسى﴾ و﴿كذبت قبلهم قوم نوح﴾ بدء قصة
        self.assertFalse(order.is_reference(w[(7, 103)], [x["nt"] for x in w[(7, 103)]].index("موسي")))
        self.assertFalse(order.is_reference(w[(54, 9)], [x["nt"] for x in w[(54, 9)]].index("قوم")))

    def test_hour_stages(self):
        hour = {(s, a1): (a2, self.stages[(s, a1)]) for e, s, a1, a2 in self.passages if e == "hour"}
        self.assertEqual(hour[(81, 1)][1], 1)  # ﴿إذا الشمس كورت﴾
        self.assertEqual(hour[(101, 1)], (8, 1))  # ﴿القارعة﴾ كلها
        self.assertIn("creation", self.era_of[(41, 9)])

    def voice(self, table, ident):
        rows = {r["id"]: r for r in self.data[table]}
        return {(s, a) for s, a, _ in rows.get(ident, {"verses": []})["verses"]}

    def test_addressees(self):
        self.assertIn((2, 21), self.voice("addressees", "people"))
        self.assertIn((2, 104), self.voice("addressees", "believers"))
        self.assertIn((2, 40), self.voice("addressees", "bani_israil"))
        self.assertIn((20, 11), self.voice("addressees", "musa"))
        self.assertIn((12, 4), self.voice("addressees", "father"))  # ﴿يا أبت﴾
        self.assertIn((31, 13), self.voice("addressees", "son"))  # ﴿يا بني لا تشرك بالله﴾
        self.assertIn((2, 197), self.voice("addressees", "ulul"))  # ﴿واتقون يا أولي الألباب﴾
        self.assertIn((18, 86), self.voice("addressees", "dhulqarnayn"))  # ﴿قلنا يا ذا القرنين﴾
        self.assertNotIn((2, 197), self.voice("addressees", "dhulqarnayn"))
        self.assertIn((2, 201), self.voice("addressees", "god"))  # ﴿ربنا آتنا في الدنيا حسنة﴾
        self.assertNotIn((35, 34), self.voice("addressees", "god"))  # ﴿إن ربنا لغفور شكور﴾ خبر لا دعاء
        self.assertIn((2, 189), self.voice("addressees", "prophet"))  # ﴿يسألونك عن الأهلة﴾
        self.assertIn((112, 1), self.voice("addressees", "prophet"))  # ﴿قل هو الله أحد﴾

    def test_speakers(self):
        self.assertIn((7, 123), self.voice("speakers", "firawn"))  # ﴿قال فرعون﴾
        self.assertIn((2, 30), self.voice("speakers", "god"))  # ﴿وإذ قال ربك للملائكة﴾
        self.assertIn((2, 34), self.voice("speakers", "god"))  # ﴿وإذ قلنا للملائكة﴾
        self.assertIn((97, 1), self.voice("speakers", "god"))  # ﴿إنا أنزلناه﴾
        self.assertIn((27, 18), self.voice("speakers", "ants"))  # ﴿قالت نملة﴾
        self.assertIn((10, 2), self.voice("speakers", "disbelievers"))  # ﴿قال الكافرون﴾
        self.assertNotIn((12, 85), self.voice("speakers", "god"))  # ﴿قالوا تالله﴾ قسم لا فاعل
        self.assertNotIn((15, 6), self.voice("speakers", "prophet"))  # ﴿وقالوا يا أيها الذي نزل عليه الذكر﴾
        self.assertNotIn((12, 43), self.voice("speakers", "angels"))  # ﴿وقال الملِك﴾ ملك مصر
        self.assertIn((40, 49), self.voice("speakers", "fire"))  # ﴿وقال الذين في النار﴾
        self.assertNotIn((40, 49), self.voice("speakers", "hypocrites"))
        # ﴿عما يقولون ليمسن الذين كفروا﴾: ﴿الذين كفروا﴾ مقول لا قائل
        self.assertNotIn((5, 73), self.voice("speakers", "disbelievers"))

    def test_every_character_in_one_story_at_most(self):
        members = [m for _, _, ms in order.STORIES for m in ms]
        self.assertEqual(len(members), len(set(members)))
        self.assertTrue(set(members) <= set(order.CHAR_BY_ID))

    def test_json_shape(self):
        eras = [e["id"] for e in self.data["eras"]]
        self.assertEqual(eras, order.ERA_IDS)
        self.assertEqual(eras[0], "creation")
        self.assertEqual(eras[-1], "hour")
        counts = defaultdict(int)
        for v in self.verses:
            counts[v["s"]] = max(counts[v["s"]], v["a"])
        for e in self.data["eras"]:
            for s, a1, a2, *_ in e["passages"]:
                self.assertTrue(1 <= a1 <= a2 <= counts[s], (e["id"], s, a1, a2))
        musa = next(c for c in self.data["characters"] if c["id"] == "musa")
        self.assertGreater(len(musa["mentions"]), 120)


if __name__ == "__main__":
    unittest.main()
