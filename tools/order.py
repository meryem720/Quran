"""ترتيب القرآن من نصه: بزمن الأحداث، وبالقصص، وبالشخصيات، وبالمخاطَب، وبالمتكلّم.

كل ما هنا مستخرج من ألفاظ الآيات ووسومها الصرفية (Quranic Arabic Corpus)، بلا تفسير خارجي:
  - الشخصيات: من أسماء الأعلام وما يقوم مقامها في النص (﴿ذا النون﴾، ﴿صاحب الحوت﴾، ﴿امرأة العزيز﴾).
  - مقاطع القصص: تُنسب كل آية إلى حقبة من يُذكر فيها، وتمتد القصة إلى ما بين ذكرين لصاحبها
    وإلى ما يتصل به من سرد أو حوار (﴿قال…﴾، ﴿فلما…﴾، ﴿وإذ…﴾) حتى يأتي ما يختمها ويلتفت إلى
    السامع (﴿إن في ذلك لآية﴾، ﴿يا أيها الناس﴾، ﴿قل﴾). يُحسب ذلك بأقل كلفة على آيات السورة.
    والذكر العابر (﴿من بعد قوم نوح﴾، ﴿ملة إبراهيم﴾، ﴿كدأب آل فرعون﴾) لا يبدأ قصة.
  - زمن الأحداث: الحقب مرتبة من الخلق إلى الآخرة، ولكل حقبة آية من القرآن تشهد لموضعها
    (﴿ثم بعثنا من بعدهم موسى﴾، ﴿جعلكم خلفاء من بعد قوم نوح﴾). وما لا يحدد النص زمنه يُذكر وحده.
    ومشاهد الآخرة مرتبة كما رتبتها سورة الزمر (68–75): النفخ والصعق، ثم البعث، ثم الكتاب
    والحساب، ثم السوق إلى الجنة والنار.
  - المخاطَب: من أداة النداء وما يليها (﴿يا أيها الذين آمنوا﴾، ﴿يا بني إسرائيل﴾، ﴿رب…﴾)،
    ومن الأمر ﴿قل﴾ والسؤال ﴿يسألونك﴾.
  - المتكلّم: من فعل القول وفاعله المذكور بعده (﴿قال موسى﴾، ﴿وقال الذين كفروا﴾)، ومن كلام الله
    بضمير المتكلم (﴿إنا أنزلناه﴾، ﴿عبادي﴾).
لا يدخل شيء من هذا في حساب الروابط بين الآيات (tools/build.py).

الاستعمال:
    python3 tools/order.py      ← web/data/order.json
"""

import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build  # noqa: E402

OUT_FILE = os.path.join(build.OUT_DIR, "order.json")
norm = build.normalize
_PERSON = re.compile(r"[123][MF]?[SDP]")


# ---------- قراءة الكلمات بأجزائها ----------

def parse_words(path=build.MORPH_FILE):
    """الآيات مرتبة، وكل كلمة: نصها موحّدًا (nt)، ولمّة أصلها موحّدة (lem)، ووسومه، وضميره،
    وسوابقها (pre) وضمائرها المتصلة (suf)، وهل فيها أداة نداء (voc)."""
    segs = defaultdict(list)
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            loc, form, pos, tags = line.split("\t")
            s, a, w, _ = (int(x) for x in loc.split(":"))
            segs[(s, a, w)].append((form, pos, tags.split("|")))
    verses = defaultdict(list)
    for (s, a, w) in sorted(segs):
        word = {"text": "", "lem": "", "raw": "", "root": "", "pn": False, "pos": "", "tags": set(), "pre": [], "suf": [],
                "voc": False}
        for form, pos, tags in segs[(s, a, w)]:
            word["text"] += form
            lemma = next((t[4:] for t in tags if t.startswith("LEM:")), "")
            person = next((t for t in tags if _PERSON.fullmatch(t)), "")
            if "PREF" in tags:
                word["pre"].append(norm(lemma))
                word["voc"] = word["voc"] or "VOC" in tags
            elif "SUFF" in tags:
                word["suf"].append(person)
            elif not word["pos"]:
                word.update(lem=norm(lemma), raw=lemma, pos=pos, tags=set(tags), pn="PN" in tags, person=person,
                            root=next((t[5:] for t in tags if t.startswith("ROOT:")), ""))
        word["nt"] = norm(word["text"])
        word.setdefault("person", "")
        verses[(s, a)].append(word)
    # ما يبدأ به الكلام المتصل بما قبله (﴿إيلافهم﴾ بعد ﴿لإيلاف قريش﴾، ﴿إلا﴾، ﴿يوم﴾): build._start_kind
    first = {(s, a): [(pos, tags) for _, pos, tags in segs[(s, a, 1)]] for (s, a) in verses}
    return [{"s": s, "a": a, "words": verses[(s, a)], "start": build._start_kind(first[(s, a)])}
            for (s, a) in sorted(verses)]


# ---------- مطابقة العلامات ----------
# العلامة كلمات متتابعة، وكل كلمة واحدة من:
#   "@X"  اسم علم لمّته X (موحّدة)        "=X"  كلمة لمّتها X
#   "~R"  نص الكلمة الموحّد يطابق التعبير R كله

def _match_token(spec, word):
    kind, value = spec[0], spec[1:]
    if kind == "@":
        return word["pn"] and word["lem"] == value
    if kind == "=":
        return word["lem"] == value
    return re.fullmatch(value, word["nt"]) is not None


def find_markers(words, markers):
    """[(موضع أول كلمة، عدد كلماتها، المعرّف)] لكل علامة في الآية: الأطول أولًا، ولا تُعدّ الكلمة لعلامتين."""
    used = set()
    found = []
    for size in sorted({len(m) for m, _ in markers}, reverse=True):
        for marker, ident in markers:
            if len(marker) != size:
                continue
            for i in range(len(words) - size + 1):
                span = range(i, i + size)
                if used.isdisjoint(span) and all(_match_token(t, words[i + k]) for k, t in enumerate(marker)):
                    used.update(span)
                    found.append((i, size, ident))
    return sorted(found)


# ---------- الحقب بترتيب زمن الأحداث ----------
# (المعرّف، العنوان، [(سورة، آية، ما تشهد به)]): الشاهد من القرآن على موضع الحقبة

ERAS = [
    ("creation", "خلق السماوات والأرض", [
        (2, 29, "خلق ما في الأرض ثم استوى إلى السماء، وبعدها: ﴿وإذ قال ربك للملائكة إني جاعل في الأرض خليفة﴾"),
        (15, 27, "﴿والجان خلقناه من قبل من نار السموم﴾: قبل خلق الإنسان"),
    ]),
    ("adam", "آدم وإبليس وابنا آدم", [
        (7, 11, "﴿ولقد خلقناكم ثم صورناكم ثم قلنا للملائكة اسجدوا لآدم﴾"),
        (19, 58, "﴿من ذرية آدم وممن حملنا مع نوح ومن ذرية إبراهيم وإسرائيل﴾: هذا ترتيبهم"),
    ]),
    ("nuh", "نوح وقومه", [
        (19, 58, "﴿وممن حملنا مع نوح﴾ بعد ﴿ذرية آدم﴾"),
        (6, 84, "﴿ونوحا هدينا من قبل﴾: قبل إبراهيم وذريته"),
    ]),
    ("hud", "هود وعاد", [
        (7, 69, "﴿إذ جعلكم خلفاء من بعد قوم نوح﴾"),
    ]),
    ("salih", "صالح وثمود", [
        (7, 74, "﴿إذ جعلكم خلفاء من بعد عاد﴾"),
    ]),
    ("ibrahim", "إبراهيم ولوط وإسماعيل وإسحاق", [
        (9, 70, "﴿قوم نوح وعاد وثمود وقوم إبراهيم وأصحاب مدين والمؤتفكات﴾"),
        (29, 26, "﴿فآمن له لوط﴾: لوط في زمن إبراهيم"),
        (14, 39, "﴿وهب لي على الكبر إسماعيل وإسحاق﴾"),
    ]),
    ("shuayb", "شعيب وأصحاب مدين", [
        (11, 89, "﴿وما قوم لوط منكم ببعيد﴾"),
    ]),
    ("yusuf", "يعقوب ويوسف", [
        (11, 71, "﴿فبشرناها بإسحاق ومن وراء إسحاق يعقوب﴾"),
        (12, 38, "﴿واتبعت ملة آبائي إبراهيم وإسحاق ويعقوب﴾"),
    ]),
    ("musa", "موسى وهارون وفرعون وبنو إسرائيل", [
        (40, 34, "﴿ولقد جاءكم يوسف من قبل بالبينات﴾"),
        (7, 103, "﴿ثم بعثنا من بعدهم موسى﴾ بعد قصص نوح وهود وصالح ولوط وشعيب"),
    ]),
    ("dawud", "طالوت وداود وسليمان", [
        (2, 246, "﴿ألم تر إلى الملإ من بني إسرائيل من بعد موسى﴾"),
        (27, 16, "﴿وورث سليمان داوود﴾"),
    ]),
    ("isa", "آل عمران: زكريا ويحيى ومريم وعيسى", [
        (2, 87, "﴿ولقد آتينا موسى الكتاب وقفينا من بعده بالرسل وآتينا عيسى ابن مريم البينات﴾"),
        (3, 33, "﴿إن الله اصطفى آدم ونوحا وآل إبراهيم وآل عمران على العالمين﴾"),
    ]),
    ("muhammad", "النبي محمد ﷺ", [
        (61, 6, "﴿ومبشرا برسول يأتي من بعدي اسمه أحمد﴾"),
        (33, 40, "﴿ولكن رسول الله وخاتم النبيين﴾"),
    ]),
    ("hour", "الساعة والآخرة", [
        (20, 15, "﴿إن الساعة آتية أكاد أخفيها﴾"),
        (39, 68, "النفخ في الصور، ثم البعث، ثم الكتاب والحساب، ثم السوق إلى الجنة والنار (الزمر 68–75)"),
    ]),
]
ERA_IDS = [e[0] for e in ERAS]
ERA_NOTES = {
    "shuayb": "لا يحدد النص أيهما أسبق: شعيب أم يعقوب ويوسف، وكلاهما قبل موسى.",
    "muhammad": "المواضع التي سُمّي فيها ﷺ أو نودي فيها، أو سُمّيت فيها وقائع زمنه (بدر، حنين، الروم…).",
    "hour": "مرتبة على مراحل الآخرة كما تتابعت في سورة الزمر (68–75)، وكل مقطع في أول مرحلة يذكرها.",
}
UNPLACED_NOTE = "قصص وشخصيات لا يحدد النص زمنها بالنسبة إلى غيرها، فتُذكر بترتيب المصحف."

# مراحل الآخرة كما تتابعت في الزمر 68–75، و0 لذكر يوم القيامة بلا مرحلة
HOUR_STAGES = {
    1: "النفخ في الصور وأهوال الساعة",
    2: "البعث والحشر",
    3: "الكتاب والحساب",
    4: "الجنة والنار",
    0: "يوم القيامة عامة",
}

# ---------- الشخصيات ----------
# (المعرّف، الاسم، الصنف، الحقبة أو None إن لم يحدد النص زمنه، [العلامات])
PERSON, PEOPLE, UNSEEN = "أشخاص", "أقوام وجماعات", "من عالم الغيب"
CHARACTERS = [
    ("adam", "آدم", PERSON, "adam", [("@ادم",)]),
    ("iblis", "إبليس", UNSEEN, "adam", [("@ابليس",)]),
    ("idris", "إدريس", PERSON, None, [("@ادريس",)]),
    ("nuh", "نوح", PERSON, "nuh", [("@نوح",)]),
    ("qawm_nuh", "قوم نوح", PEOPLE, "nuh", [("=قوم", "@نوح")]),
    ("nuh_wife", "امرأة نوح", PERSON, "nuh", [("=امرات", "@نوح")]),
    ("hud", "هود", PERSON, "hud", [("@هود",), ("=اخ", "@عاد")]),
    ("aad", "عاد", PEOPLE, "hud", [("@عاد",), ("@ارم",), ("@احقاف",)]),
    ("salih", "صالح", PERSON, "salih", [("@صالح",)]),
    ("thamud", "ثمود", PEOPLE, "salih", [("@ثمود",)]),
    ("ibrahim", "إبراهيم", PERSON, "ibrahim", [("@ابراهيم",)]),
    ("azar", "آزر", PERSON, "ibrahim", [("@ازر",)]),
    ("lut", "لوط", PERSON, "ibrahim", [("@لوط",)]),
    ("qawm_lut", "قوم لوط", PEOPLE, "ibrahim", [("=قوم", "@لوط"), ("=موتفكه",)]),
    ("lut_wife", "امرأة لوط", PERSON, "ibrahim", [("=امرات", "@لوط")]),
    ("ismail", "إسماعيل", PERSON, "ibrahim", [("@اسماعيل",)]),
    ("ishaq", "إسحاق", PERSON, "ibrahim", [("@اسحاق",)]),
    ("shuayb", "شعيب", PERSON, "shuayb", [("@شعيب",)]),
    ("madyan", "أصحاب مدين والأيكة", PEOPLE, "shuayb", [
        ("=اصحاب", "@مدين"), ("~(و)?الي", "@مدين"), ("~(و)?لمدين",), ("=اصحاب", "=ايكه")]),
    ("yaqub", "يعقوب (إسرائيل)", PERSON, "yusuf", [("@يعقوب",), ("@اسراييل",)]),
    ("yusuf", "يوسف", PERSON, "yusuf", [("@يوسف",)]),
    ("aziz_wife", "امرأة العزيز", PERSON, "yusuf", [("=امرات", "=عزيز")]),
    ("musa", "موسى", PERSON, "musa", [("@موسي",)]),
    ("harun", "هارون", PERSON, "musa", [("@هارون",)]),
    ("firawn", "فرعون", PERSON, "musa", [("@فرعون",)]),
    ("firawn_wife", "امرأة فرعون", PERSON, "musa", [("=امرات", "@فرعون")]),
    ("firawn_believer", "مؤمن آل فرعون", PERSON, "musa", [("=رجل", "=مومن", "=من", "=ال", "@فرعون")]),
    ("haman", "هامان", PERSON, "musa", [("@هامان",)]),
    ("qarun", "قارون", PERSON, "musa", [("@قارون",)]),
    ("samiri", "السامري", PERSON, "musa", [("@سامري",)]),
    ("bani_israil", "بنو إسرائيل", PEOPLE, "musa", [("~(و|ف|ل|ي)?بني", "@اسراييل"), ("~(و|ف)?بنو", "@اسراييل")]),
    ("talut", "طالوت", PERSON, "dawud", [("@طالوت",)]),
    ("jalut", "جالوت", PERSON, "dawud", [("@جالوت",)]),
    ("dawud", "داود", PERSON, "dawud", [("@داود",)]),
    ("sulayman", "سليمان", PERSON, "dawud", [("@سليمان",)]),
    ("saba", "سبأ", PEOPLE, None, [("@سبا",)]),
    ("ayyub", "أيوب", PERSON, None, [("@ايوب",)]),
    ("yunus", "يونس", PERSON, None, [("@يونس",), ("=ذو", "=نون"), ("=صاحب", "=حوت")]),
    ("ilyas", "إلياس", PERSON, None, [("@الياس",)]),
    ("alyasa", "اليسع", PERSON, None, [("@اليسع",)]),
    ("dhulkifl", "ذو الكفل", PERSON, None, [("=ذو", "=كفل")]),
    ("uzayr", "عزير", PERSON, None, [("@عزير",)]),
    ("luqman", "لقمان", PERSON, None, [("@لقمان",)]),
    ("dhulqarnayn", "ذو القرنين", PERSON, None, [("=ذو", "=قرن")]),
    ("yajuj", "يأجوج ومأجوج", PEOPLE, "u:dhulqarnayn", [("@ياجوج",), ("@ماجوج",)]),
    ("kahf", "أصحاب الكهف", PEOPLE, None, [("=اصحاب", "=كهف"), ("=كهف",), ("~(ال)?فتيه",)]),
    ("rass", "أصحاب الرس", PEOPLE, None, [("=اصحاب", "=رس")]),
    ("ukhdud", "أصحاب الأخدود", PEOPLE, None, [("=اصحاب", "=اخدود")]),
    ("fil", "أصحاب الفيل", PEOPLE, None, [("=اصحاب", "=فيل")]),
    ("tubba", "قوم تبّع", PEOPLE, None, [("@تبع",)]),
    ("imran", "عمران", PERSON, "isa", [("@عمران",)]),
    ("imran_wife", "امرأة عمران", PERSON, "isa", [("=امرات", "@عمران")]),
    ("zakariya", "زكريا", PERSON, "isa", [("@زكريا",)]),
    ("yahya", "يحيى", PERSON, "isa", [("@يحيي",)]),
    ("isa", "عيسى ابن مريم", PERSON, "isa", [("@عيسي",), ("@مسيح",), ("=ابن", "@مريم")]),
    ("maryam", "مريم", PERSON, "isa", [("@مريم",), ("~ياخت", "@هارون")]),
    ("muhammad", "محمد ﷺ", PERSON, "muhammad", [
        ("@محمد",), ("@احمد",), ("~(و|ف|ب)?النبي|(و|ف)?للنبي",),
        ("~يايها", "~(الرسول|المزمل|المدثر)"), ("~يايها", "=الذي", "~نزل", "~عليه", "~الذكر")]),
    ("zayd", "زيد", PERSON, "muhammad", [("@زيد",)]),
    ("abulahab", "أبو لهب", PERSON, "muhammad", [("=اب", "=لهب")]),
    ("quraysh", "قريش", PEOPLE, "muhammad", [("@قريش",)]),
    ("rum", "الروم", PEOPLE, "muhammad", [("@روم",)]),
    ("jibril", "جبريل", UNSEEN, None, [("@جبريل",)]),
    ("mikal", "ميكال", UNSEEN, None, [("@ميكال",)]),
    ("harut", "هاروت وماروت", UNSEEN, None, [("@هاروت",), ("@ماروت",)]),
    ("malik", "مالك خازن النار", UNSEEN, "hour", [("@مالك",)]),
]
CHAR_BY_ID = {c[0]: c for c in CHARACTERS}
# القصص: صاحب القصة ومن يُذكر فيها معه، فلا تتكرر قصة نوح باسم «قوم نوح» ولا قصة موسى باسم «فرعون»
STORIES = [
    ("adam", "آدم وإبليس", ["adam", "iblis"]),
    ("nuh", "نوح وقومه", ["nuh", "qawm_nuh", "nuh_wife"]),
    ("hud", "هود وعاد", ["hud", "aad"]),
    ("salih", "صالح وثمود", ["salih", "thamud"]),
    ("ibrahim", "إبراهيم", ["ibrahim", "azar", "ismail", "ishaq"]),
    ("lut", "لوط وقومه", ["lut", "qawm_lut", "lut_wife"]),
    ("shuayb", "شعيب وأصحاب مدين", ["shuayb", "madyan"]),
    ("yusuf", "يوسف ويعقوب", ["yusuf", "yaqub", "aziz_wife"]),
    ("musa", "موسى وفرعون وبنو إسرائيل", ["musa", "harun", "firawn", "firawn_wife", "firawn_believer", "haman",
                                         "samiri", "bani_israil"]),
    ("qarun", "قارون", ["qarun"]),
    ("talut", "طالوت وجالوت", ["talut", "jalut"]),
    ("dawud", "داود", ["dawud"]),
    ("sulayman", "سليمان", ["sulayman"]),
    ("zakariya", "زكريا ويحيى", ["zakariya", "yahya"]),
    ("isa", "مريم وعيسى", ["isa", "maryam", "imran", "imran_wife"]),
    ("muhammad", "النبي محمد ﷺ", ["muhammad", "zayd", "abulahab", "quraysh", "rum"]),
    ("ayyub", "أيوب", ["ayyub"]),
    ("yunus", "يونس", ["yunus"]),
    ("ilyas", "إلياس", ["ilyas"]),
    ("idris", "إدريس", ["idris"]),
    ("uzayr", "عزير", ["uzayr"]),
    ("luqman", "لقمان", ["luqman"]),
    ("dhulqarnayn", "ذو القرنين", ["dhulqarnayn", "yajuj"]),
    ("kahf", "أصحاب الكهف", ["kahf"]),
    ("saba", "سبأ", ["saba"]),
    ("ukhdud", "أصحاب الأخدود", ["ukhdud"]),
    ("fil", "أصحاب الفيل", ["fil"]),
    ("rass", "أصحاب الرس", ["rass"]),
    ("tubba", "قوم تبّع", ["tubba"]),
]
STORY_OF = {member: story for story, _, members in STORIES for member in members}
# ما يشبه علامة شخصية وليس منها: ﴿يا بني آدم﴾ خطاب للناس، و﴿كونوا هودا أو نصارى﴾
NOT_CHARACTER = [("~(و|ف|ل|ي)?بني", "@ادم"), ("@هود", "=او", "@نصراني")]
# شخصيات يمتد ذكرها في حقب كثيرة أو يأتي في غير قصتها (﴿وجنود إبليس أجمعون﴾ في مشهد النار،
# و﴿حتى إذا فتحت يأجوج ومأجوج﴾ من أشراط الساعة)، فذكرها يؤيد القصة ولا يبدؤها
WEAK_CHARACTERS = {"bani_israil", "iblis", "yajuj"}
# أماكن وألفاظ تشهد لحقبتها ولا تُعدّ شخصيات: ﴿ولقد نصركم الله ببدر﴾، ﴿تلقاء مدين﴾، ﴿إني جاعل في الأرض خليفة﴾
ERA_WORDS = [
    (("@بدر",), "muhammad"), (("@حنين",), "muhammad"), (("@يثرب",), "muhammad"), (("@مكه",), "muhammad"),
    (("@مدين",), "musa"),  # ﴿تلقاء مدين﴾، ﴿ماء مدين﴾، ﴿أهل مدين﴾: في قصة موسى
    (("=جاعل", "=في", "=ارض", "=خليفه"), "adam"), (("=خالق", "=بشر"), "adam"),
]
# الخلق: ﴿في ستة أيام﴾، ﴿في يومين﴾، ﴿ثم استوى إلى السماء﴾، ﴿كانتا رتقا﴾، ﴿دحاها﴾، ﴿طحاها﴾
CREATION_WORDS = [("=سته", "=يوم"), ("~في", "~يومين"), ("=رتق",), ("=دحي",), ("=طحي",),
                  ("=استوي", "=الي", "=سماء")]
CREATION_ROOTS = {"خلق", "سمو", "رسو"}
CREATION_GAP = 3
NOT_ERA = [("~تعجل", "~في", "~يومين")]  # أيام الحج لا أيام الخلق
# علامات الآخرة ومرحلتها (HOUR_STAGES)
HOUR_WORDS = [
    (("~(و|ف|ب)?الساعه|(و|ف)?للساعه",), 1), (("=نفخ", "=في", "=صور"), 1),
    (("~(و|ف|ب)?ال(حاقه|قارعه|طامه|صاخه|غشيه|ءازفه|واقعه|راجفه|رادفه)",), 1),
    (("=كورت",), 1), (("=انفطرت",), 1), (("=انكدرت",), 1), (("=سجرت",), 1), (("=زلزل", "~(ال)?ارض"), 1),
    (("=رجت",), 1), (("=بست",), 1), (("=نسفت",), 1), (("=سيرت",), 1), (("=انتثرت",), 1), (("=فجرت",), 1),
    (("=تمور",), 1), (("=دكت",), 1), (("=عطلت",), 1), (("=كشطت",), 1), (("=ترجف",), 1), (("=عهن",), 1),
    (("=يشقق", "~(ال)?(سماء|ارض)"), 1), (("=انشق", "~(ال)?(سماء|قمر)"), 1), (("~(ف|و)?اذا", "=انشق"), 1),
    (("=اجداث",), 2), (("=بعثر",), 2), (("=يوم", "~(ال)?(بعث|خروج|جمع|تلاق|وعيد)"), 2),
    (("=يوم", "~(ال)?(دين|فصل|حساب|تغابن|حسره)"), 3), (("~(ف|و)?(ال)?موزين(ه)?",), 3),
    (("=اصحاب", "~(ال)?(يمين|شمال|ميمنه|مشمه)"), 3), (("=كتاب", "~(بيمينه|بشماله)"), 3),
    (("@جهنم",), 4), (("@سقر",), 4), (("@لظي",), 4), (("=جحيم",), 4), (("=سعير",), 4), (("=حطمه",), 4),
    (("@زقوم",), 4), (("@فردوس",), 4), (("@سلسبيل",), 4), (("@عدن",), 4), (("=حور",), 4),
    (("=خالد", "~فيها"), 4), (("=يوم", "~(ال)?خلود"), 4), (("@جنه",), 4),
    (("=جنه", "~(ال)?نعيم"), 4), (("=جنه", "~تجري"), 4),
    # من وصف الجنة والنار: ﴿على سرر﴾، ﴿متكئين﴾، ﴿سندس وإستبرق﴾، ﴿ولدان مخلدون﴾، ﴿غسلين﴾، ﴿ضريع﴾…
    *((("=" + lemma,), 4) for lemma in ("سرر", "ارايك", "متكي", "سندس", "استبرق", "مخلد", "يحموم", "غسلين",
                                         "ضريع", "صديد", "رحيق", "تسنيم", "كافور", "زنجبيل", "نمارق", "زرابي",
                                         "مهل", "قطوف")),
    (("=قيامه",), 0),
]
HOUR_GAP = 4  # ما بين آيتين من مشاهد الآخرة يُضم إليها إن لم يزد على هذا
# كلمة قبل الاسم تجعل ذكره عابرًا لا قصة: ﴿من بعد قوم نوح﴾، ﴿ملة إبراهيم﴾، ﴿كدأب آل فرعون﴾
REF_WORDS = {"بعد", "قبل", "مثل", "داب", "مله", "مقام", "صحف", "ذريه", "كتاب"}
NOT_REF = {"بُعْد"}  # ﴿ألا بعدا لمدين﴾: دعاء لا ذكر عابر
REF_TEXTS = {"كما", "كمثل"}
REF_SKIP = {"ال", "قوم"}  # ﴿كدأب آل فرعون﴾، ﴿من بعد قوم نوح﴾


def all_markers():
    """العلامات كلها: (العلامة، المعرّف). المعرّف معرّف شخصية، أو "@حقبة"، أو "hour:مرحلة"،
    أو "creation"، أو None لما يشبه العلامة وليس منها."""
    markers = [(m, c[0]) for c in CHARACTERS for m in c[4]]
    markers += [(m, None) for m in NOT_CHARACTER + NOT_ERA]
    markers += [(m, "@" + era) for m, era in ERA_WORDS]
    markers += [(m, f"hour:{stage}") for m, stage in HOUR_WORDS]
    markers += [(m, "creation") for m in CREATION_WORDS]
    return markers


def label_of(ident):
    """حقبة الشخصية في التقسيم، أو «u:المعرّف» لمن لا يحدد النص زمنه."""
    if ident.startswith("@"):
        return ident[1:]
    era = CHAR_BY_ID[ident][3]
    return era if era else "u:" + ident


def is_reference(words, i, size=1):
    """ذكر عابر: قبل الاسم ﴿بعد﴾ أو ﴿قبل﴾ أو ﴿مثل﴾ أو ﴿ملة﴾ (ويُتخطى ﴿آل﴾ و﴿قوم﴾)،
    أو ﴿كما﴾ قبله بكلمة أو كلمتين (﴿كما سئل موسى من قبل﴾)، أو ﴿من قبل﴾ بعده (﴿ولقد جاءكم يوسف من قبل﴾)."""
    if any(j >= 0 and words[j]["nt"] in REF_TEXTS for j in (i - 1, i - 2)):
        return True
    end = i + size
    if end + 1 < len(words) and words[end]["lem"] == "من" and words[end + 1]["lem"] == "قبل" \
            and "ال" not in words[end + 1]["pre"] and not words[end + 1]["suf"]:
        return True
    j = i - 1
    while j >= 0 and words[j]["lem"] in REF_SKIP:
        j -= 1
    # المضاف بلا «ال»: ﴿ملة إبراهيم﴾ ذكر عابر، و﴿واذكر في الكتاب إسماعيل﴾ قصة،
    # المضاف إلى الاسم نفسه، لا ما اتصل به ضمير: ﴿كذبت قبلهم قوم نوح﴾ و﴿ثم بعثنا من بعدهم موسى﴾ بدء قصة
    return (j >= 0 and words[j]["lem"] in REF_WORDS and words[j]["raw"] not in NOT_REF
            and "ال" not in words[j]["pre"] and not words[j]["suf"])


# ---------- السرد وخاتمته ----------

def narrative_kind(words):
    """نوع الآية في القصة:
    "narr"   تبدأ بما يتصل به السرد (﴿قال﴾، ﴿فلما﴾، ﴿وإذ﴾، فاء وفعل ماضٍ…)
    "speech" حوار: فيها أمر أو ضمير متكلم مفرد أو مخاطب
    "aside"  تبدأ بإشارة (﴿ذلك﴾، ﴿تلك﴾): تعليق قد يكون من القصة وقد يختمها
    "future" تبدأ بـ﴿إذا﴾ أو ﴿يوم﴾: مشهد آتٍ لا سرد ماضٍ
    "open"   تبدأ قصة قوم لم يُسمَّوا (﴿ثم أنشأنا من بعدهم قرنا آخرين﴾، ﴿واضرب لهم مثلا﴾)
    "close"  تبدأ بما يختم القصة ويلتفت إلى السامع (﴿إن في ذلك﴾، ﴿قل﴾، ﴿يا أيها الناس﴾)
    None     غير ذلك."""
    if not words:
        return None
    w = words[0]
    nxt = words[1] if len(words) > 1 else None
    tags = w["tags"]
    if w["voc"] and ((w["lem"] == "اي" and nxt and nxt["nt"] not in AUDIENCE_IN_STORY)
                     or (w["lem"] in ("ابن", "بني", "اهل") and nxt and nxt["lem"] in ("ادم", "اسراييل", "كتاب"))):
        return "close"  # ﴿يا أيها الناس﴾، ﴿يا بني آدم﴾، ﴿يا أهل الكتاب﴾: التفات إلى السامع
    if w["lem"] == "قال" and "IMPV" in tags:
        return "close"  # ﴿قل﴾: التفات إلى النبي ﷺ
    if w["lem"] == "ان" and nxt and nxt["lem"] == "في" and len(words) > 2 and words[2]["nt"] in ("ذلك", "ذلكم"):
        return "close"  # ﴿إن في ذلك لآية﴾
    if w["nt"] in ("ذلك", "تلك", "ذلكم"):
        return "aside"
    if w["lem"] in ("اذا", "يوم", "يومييذ"):
        return "future"  # ﴿فإذا نفخ في الصور﴾، ﴿يوم ترجف الأرض﴾: مشهد آتٍ لا سرد ماضٍ
    first = w if w["pos"] == "V" else nxt if w["lem"] in ("ثم", "قد") and nxt is not None else None
    if first is not None and first["lem"] in OPENERS and first["person"] == "1P" and "PERF" in first["tags"]:
        return "open"  # ﴿ثم أنشأنا من بعدهم قرونا﴾، ﴿ولقد أرسلنا رسلا﴾: قصة جديدة
    if w["lem"] == "ضرب" and "IMPV" in tags and any(x["lem"] == "مثل" for x in words[:4]):
        return "open"  # ﴿واضرب لهم مثلا﴾
    if w["lem"] == "قال" and ("PERF" in tags or "PASS" in tags):
        return "narr"
    if w["lem"] in ("لما", "اذ"):
        return "narr"
    if w["lem"] == "حتي" and nxt and nxt["lem"] == "اذا":
        return "narr"
    if w["lem"] == "ثم" and nxt and nxt["pos"] == "V" and "PERF" in nxt["tags"]:
        return "narr"
    if w["pos"] == "V" and "PERF" in tags and ("ف" in w["pre"] or ("و" in w["pre"] and w["person"][:1] in "31")):
        return "narr"
    return "speech" if _addresses(words) else None


def _addresses(words):
    """في الآية أمر أو نداء أو ضمير متكلم مفرد أو مخاطب (﴿أبلغكم﴾، ﴿يا قوم﴾، ﴿فاتبعون﴾)."""
    return any("IMPV" in x["tags"] or x["voc"] or x["person"][:1] == "2" or x["person"] == "1S"
               or any(p[:1] == "2" or p == "1S" for p in x["suf"]) for x in words)


def _says(words):
    """في الآية فعل قول أو نداء ماضٍ (﴿قال﴾، ﴿فنادى﴾): يُفتتح به حوار في القصة."""
    return any(x["lem"] in ("قال", "نادي") and x["pos"] == "V" and "PERF" in x["tags"] for x in words)


OPENERS = {"انشا", "ارسل", "بعث", "اهلك"}
# ﴿يا أيها الملأ﴾، ﴿يا أيها العزيز﴾، ﴿يا أيها الساحر﴾، ﴿يا أيها النمل﴾: نداء داخل القصة
AUDIENCE_IN_STORY = {"الملا", "الملوا", "العزيز", "الساحر", "النمل"}


# ---------- تقسيم السورة إلى مقاطع القصص ----------
# الكلفة: الآية التي يُذكر فيها صاحب حقبة تُنسب إليها بلا كلفة، وإلى غيرها بكلفة؛ والآية الخالية
# من الذكر تُلحق بالقصة بقدر ما تشبه السرد، وبقدر بعدها عن آخر ذكر لصاحبها؛ ولكل قصة كلفة بدء.
COST_MISS = 1.0       # آية فيها ذكر صاحب قصة ولا تُنسب إلى قصة
COST_CONFLICT = 1.0   # آية فيها ذكر حقبة وتُنسب إلى غيرها (ذكرٌ عابر داخل قصة أخرى)
COST_LIST = 0.6       # آية تعدّد الأمم (﴿قوم نوح وعاد وثمود﴾): تذكير لا قصة
# آية بلا ذكر داخل القصة، بحسب نوعها (narrative_kind)
COST_FILL = {"narr": 0.0, "speech": 0.05, "aside": 0.6, None: 0.15, "future": 1.5, "close": 1.2, "open": 1.2}
# زمن النبي ﷺ: لا يمتد إلا بالسرد (﴿إذ غدوت من أهلك﴾)، فذكره في آيات الأحكام لا يجعل السورة كلها قصة
COST_FILL_MUHAMMAD = {"narr": 0.0, "speech": 0.4}
COST_NONE = {"narr": 0.3, "speech": 0.1}  # آية بلا ذكر خارج القصص
SANDWICH = 15         # ما بين ذكرين لصاحب القصة لا يزيد بُعدهما على هذا ولا يختمه شيء: من القصة
COST_FILL_BETWEEN = {"close": 0.6}
COST_FAR = 0.005      # لكل آية بعد الثالثة من آخر ذكر لصاحب القصة
MAX_FAR = 30          # لا تمتد القصة أبعد من هذا عن آخر ذكر لصاحبها
COST_ENTER = 0.7      # بدء قصة
LIST_SIZE = 3
LIST_SHORT = 6        # آية قصيرة بجوار آية تعدّد الأمم تتمة لها
LIST = "list"  # حالة آيات تعدّد الأمم وما يتصل بها (﴿قالت رسلهم…﴾): ليست قصة حقبة بعينها
NONE = ""


def segment(rows):
    """rows: [(الحقب المذكورة، الحقب المذكورة ذكرًا عابرًا، نوع الآية، آية تعدّد الأمم؟)].
    يرجع حقبة كل آية أو NONE، بأقل كلفة (Viterbi). لا تبدأ قصة إلا في آية يُذكر فيها صاحبها،
    وما بين ذكرين متقاربين لصاحب القصة منها بلا كلفة."""
    n = len(rows)
    INF = float("inf")
    states = [NONE] + sorted({x for strong, weak, _, _ in rows for x in strong | weak})
    last_seen, next_seen = [], [None] * n  # أقرب ذكر للحقبة قبل الموضع وبعده
    # آيات تعدّد الأمم لا تُعدّ ذكرًا لصاحب القصة في هذا
    last = {}
    for strong, _, _, is_list in rows:
        last_seen.append(dict(last))
        for x in () if is_list else strong:
            last[x] = len(last_seen) - 1
    ahead = {}
    for k in range(n - 1, -1, -1):
        next_seen[k] = dict(ahead)
        for x in () if rows[k][3] else rows[k][0]:
            ahead[x] = k
    # عدد ما يختم الكلام قبل كل موضع: لا يُعدّ ما بين ذكرين من القصة إذا فصل بينهما خاتمة
    closes = [0]
    for _, _, kind, _ in rows:
        closes.append(closes[-1] + (kind in ("close", "future", "open")))

    def cost(k, st):
        strong, weak, kind, is_list = rows[k]
        if st == NONE:
            if strong and not is_list:
                return COST_MISS
            return COST_NONE.get(kind, 0.0)
        if st in strong:
            return COST_LIST if is_list and st != LIST else 0.0
        if strong and not is_list:
            return COST_CONFLICT
        if st in weak:
            return 0.0
        seen = last_seen[k].get(st)
        if seen is None or k - seen > MAX_FAR:
            return INF
        if st == "muhammad":
            return COST_FILL_MUHAMMAD.get(kind, 0.8)
        after = next_seen[k].get(st)
        if after is not None and after - seen <= SANDWICH and closes[after] == closes[seen + 1]:
            return COST_FILL_BETWEEN.get(kind, 0.0)
        return COST_FILL[kind] + COST_FAR * max(0, k - seen - 3)

    def move(k, p, st):
        if st == p or st == NONE:
            return 0.0
        return COST_ENTER if st in rows[k][0] else INF

    best = [{st: (cost(0, st) + move(0, NONE, st), None) for st in states}]
    for k in range(1, n):
        row = {}
        for st in states:
            c = cost(k, st)
            # عند تساوي الكلفة تبقى الآية في القصة نفسها
            total, _, prev = min((best[k - 1][p][0] + move(k, p, st) + c, p != st, p) for p in states)
            row[st] = (total, prev)
        best.append(row)
    st = min(states, key=lambda x: (best[n - 1][x][0], x != NONE))
    out = [st]
    for k in range(n - 1, 0, -1):
        st = best[k][st][1]
        out.append(st)
    return out[::-1]


def _runs(states):
    """[(الحالة، أول موضع، آخر موضع)] للمواضع المتتابعة ذات الحالة الواحدة غير الفارغة."""
    runs, k = [], 0
    while k < len(states):
        j = k
        while j + 1 < len(states) and states[j + 1] == states[k]:
            j += 1
        if states[k] != NONE:
            runs.append((states[k], k, j))
        k = j + 1
    return runs


def analyze(verses, debug=None):
    """يرجع (المقاطع، الذكر، المراحل):
    المقاطع [(الحقبة، سورة، أول آية، آخر آية)]، والذكر {(سورة، آية): {معرّف الشخصية: عابر؟}}،
    ومراحل الآخرة {(سورة، آية): مرحلة} لآيات مشاهد الآخرة (خارج القصص)."""
    markers = all_markers()
    by_key = {(v["s"], v["a"]): v for v in verses}
    mentions, hour_marks, creation_marks = {}, {}, set()
    by_surah = defaultdict(list)
    for v in verses:
        key = (v["s"], v["a"])
        strong, weak, chars = set(), set(), {}
        prev_end, prev_ref = -1, False
        for i, size, ident in find_markers(v["words"], markers):
            if not ident:
                continue
            if ident == "creation":
                creation_marks.add(key)
            elif ident.startswith("hour:"):
                # ﴿إلى يوم الدين﴾، ﴿إلى يوم القيامة﴾: أجل لا مشهد
                if i > 0 and v["words"][i - 1]["lem"] == "الي":
                    continue
                stage = int(ident[5:])
                old = hour_marks.get(key)
                hour_marks[key] = stage if old is None or (stage and (not old or stage < old)) else old
            else:
                # ﴿صحف إبراهيم وموسى﴾: المعطوف على ذكر عابر عابر مثله
                ref = ident.startswith("@") is False and (
                    ident in WEAK_CHARACTERS
                    or (CHAR_BY_ID[ident][3] != "muhammad"
                        and (is_reference(v["words"], i, size) or (prev_ref and prev_end == i - 1 and "و" in v["words"][i]["pre"]))))
                prev_end, prev_ref = i + size - 1, ref
                if label_of(ident) == "hour":  # ﴿ونادوا يا مالك﴾: في مشهد النار
                    hour_marks[key] = 4
                else:
                    (weak if ref else strong).add(label_of(ident))
                if not ident.startswith("@"):
                    chars[ident] = chars.get(ident, True) and ref
        if chars:
            mentions[key] = chars
        # الآية التي لا يُبتدأ بها كلام تتمة لما قبلها، فهي من قصته
        kind = "narr" if v["start"] and v["start"] != "yawm" else narrative_kind(v["words"])
        by_surah[v["s"]].append([v["a"], strong, weak - strong, kind])

    passages = []
    in_story = set()
    for s, rows in by_surah.items():
        # آية تعدّد الأمم: ثلاث حقب فأكثر، أو حقبتان بجوار آية تعدّد
        # آية تعدّد الأمم (ولو ذكرًا عابرًا): ثلاث حقب فأكثر، أو حقبتان بجوار آية تعدّد
        # وتتمتها في الآية التالية أو السابقة إذا قصرت (﴿وقوم إبراهيم وقوم لوط﴾ بعد ﴿قوم نوح وعاد وثمود﴾)
        many = [len(r[1] | r[2]) >= LIST_SIZE for r in rows]
        said = [r[3] == "narr" and _says(by_key[(s, r[0])]["words"]) for r in rows]
        listed = []
        for k, r in enumerate(rows):
            near = (k > 0 and listed[k - 1]) or (k + 1 < len(rows) and many[k + 1])
            short = len(by_key[(s, r[0])]["words"]) <= LIST_SHORT
            is_list = many[k] or (bool(r[1] | r[2]) and near and (len(r[1] | r[2]) >= 2 or short))
            listed.append(is_list)
            # الحوار ما اتصل بقول قبله (﴿قال…﴾ ثم آيات بضمير المتكلم أو المخاطب)، وإلا فهو كلام عام
            if r[3] in ("speech", "future", "aside", None):
                words = by_key[(s, r[0])]["words"]
                chained = any(x >= 0 and (said[x] or rows[x][3] == "speech") for x in (k - 1, k - 2))
                if _addresses(words) and (said[k] or chained):
                    r[3] = "speech"
                elif r[3] == "speech":
                    r[3] = None
            if is_list or (r[3] == "open" and not r[1]):
                r[1] = r[1] | {LIST}
            r.append(is_list)
        states = segment([tuple(r[1:]) for r in rows])
        if debug is not None:
            debug[s] = (rows, states)
        for era, k, j in _runs(states):
            if era == LIST:
                continue
            passages.append((era, s, rows[k][0], rows[j][0]))
            in_story.update((s, rows[x][0]) for x in range(k, j + 1))

    # مشاهد الآخرة والخلق خارج القصص: آيات متتابعة فيها علاماتها، ويُضم ما بينها إن لم يختم الكلام
    stages = {}
    for s, rows in by_surah.items():
        keys = [(s, r[0]) for r in rows]
        free = [key not in in_story and r[3] != "close" for key, r in zip(keys, rows)]
        hour = [key in hour_marks and key not in in_story for key in keys]
        # يُضم ما بين مشهدين، لا ما بين ذكرين عامّين ليوم القيامة أو للجنة والنار
        scene = [bool(hour_marks.get(key)) and h for key, h in zip(keys, hour)]
        _bridge(hour, free, HOUR_GAP, scene)
        for _, k, j in _runs(["hour" if x else NONE for x in hour]):
            passages.append(("hour", s, rows[k][0], rows[j][0]))
            nonzero = [hour_marks[keys[x]] for x in range(k, j + 1) if hour_marks.get(keys[x])]
            stages[keys[k]] = min(nonzero) if nonzero else 0
        # الخلق: ويمتد إلى ما يجاوره من ذكر الخلق والسماء والجبال (﴿أم السماء بناها﴾، ﴿والجبال أرساها﴾)
        creation = [key in creation_marks and key not in in_story for key in keys]
        for k in [k for k, x in enumerate(creation) if x]:
            for step in (-1, 1):
                j = k + step
                while (0 <= j < len(rows) and abs(j - k) <= CREATION_GAP and free[j]
                       and any(w["root"] in CREATION_ROOTS for w in by_key[keys[j]]["words"])):
                    creation[j] = True
                    j += step
        _bridge(creation, free, CREATION_GAP)
        for _, k, j in _runs(["creation" if x else NONE for x in creation]):
            passages.append(("creation", s, rows[k][0], rows[j][0]))
    return passages, mentions, stages


def _bridge(marked, free, gap, ends=None):
    """يضم إلى المقطع ما بين آيتين معلَّمتين (ومن ends إن أُعطيت) إذا لم يزد على gap ولم يكن
    فيه ما يختم الكلام."""
    ends = ends or marked
    k = 0
    while k < len(marked):
        if marked[k] and ends[k]:
            j = next((x for x in range(k + 1, min(k + gap + 2, len(marked))) if marked[x]), None)
            if j is not None and ends[j] and all(free[x] for x in range(k + 1, j)):
                for x in range(k + 1, j):
                    marked[x] = True
        k += 1


# ---------- المخاطَب والمتكلّم ----------
# (المعرّف، الاسم) للجماعات والمخاطَبين الذين ليسوا من الشخصيات
GROUPS = [
    ("god", "الله تعالى"),
    ("prophet", "النبي ﷺ"),
    ("believers", "الذين آمنوا"),
    ("people", "الناس"),
    ("human", "الإنسان"),
    ("bani_adam", "بنو آدم"),
    ("ahl_kitab", "أهل الكتاب"),
    ("jews", "اليهود والذين هادوا"),
    ("christians", "النصارى"),
    ("disbelievers", "الذين كفروا"),
    ("polytheists", "الذين أشركوا"),
    ("hypocrites", "المنافقون والذين في قلوبهم مرض"),
    ("wrongdoers", "الذين ظلموا"),
    ("arrogant", "الذين استكبروا"),
    ("weak", "الذين استضعفوا والضعفاء"),
    ("unknowing", "الذين لا يعلمون أو لا يرجون لقاء الله"),
    ("knowledge", "الذين أوتوا العلم"),
    ("bedouins", "الأعراب"),
    ("disciples", "الحواريون"),
    ("fools", "السفهاء"),
    ("mala", "الملأ"),
    ("qawm", "القوم (﴿يا قوم﴾)"),
    ("messengers", "الرسل"),
    ("angels", "الملائكة"),
    ("satan", "الشيطان"),
    ("jinn", "الجن"),
    ("jinn_ins", "الجن والإنس"),
    ("servants", "العباد (﴿يا عبادي﴾)"),
    ("ulul", "أولو الألباب والأبصار"),
    ("prophet_wives", "نساء النبي ﷺ"),
    ("father", "الأب (﴿يا أبت﴾)"),
    ("son", "الابن (﴿يا بني﴾)"),
    ("prison", "صاحبا السجن"),
    ("women", "النسوة"),
    ("paradise", "أصحاب الجنة"),
    ("fire", "أصحاب النار"),
    ("araf", "أصحاب الأعراف"),
    ("keepers", "خزنة الجنة والنار"),
    ("ants", "النمل"),
    ("soul", "النفس المطمئنة"),
    ("things", "الأرض والسماء والجبال والنار"),
    ("yathrib", "أهل يثرب"),
]
GROUP_NAMES = dict(GROUPS)
# ﴿يا أيها …﴾ وما بعدها
VOC_AYYUHA = {
    "الناس": "people", "النبي": "prophet", "الرسول": "prophet", "المزمل": "prophet", "المدثر": "prophet",
    "الذي": "prophet", "الانسن": "human", "الرسل": "messengers", "الكفرون": "disbelievers",
    "الملا": "mala", "الملوا": "mala", "العزيز": "yusuf", "الساحر": "musa", "النمل": "ants",
    "النفس": "soul", "المومنون": "believers", "الثقلان": "jinn_ins",
}
# ﴿يا أيها الذين …﴾ بحسب الفعل بعدها
VOC_ALLADHINA = {"امن": "believers", "كفر": "disbelievers", "هاد": "jews", "اوتي": "ahl_kitab"}
# ﴿يا …﴾ بحسب لمّة المنادى
VOC_LEMMA = {
    "قوم": "qawm", "رب": "god", "عبد": "servants", "اولو": "ulul", "اولي": "ulul", "اب": "father",
    "معشر": "jinn_ins", "نساء": "prophet_wives", "صاحب": "prison", "ارض": "things", "سماء": "things",
    "جبل": "things", "نار": "things", "اخت": "maryam", "مالك": "malik",
}
VOC_EXCLAIM = {"ويل", "ليت", "حسره", "اسف", "بشري", "ويلت"}  # ﴿يا ويلتنا﴾، ﴿يا ليتني﴾: تحسّر لا نداء
# ﴿قال الذين …﴾ بحسب الفعل بعدها
SAID_ALLADHINA = {
    "كفر": "disbelievers", "اشرك": "polytheists", "امن": "believers", "ظلم": "wrongdoers",
    "استكبر": "arrogant", "استضعف": "weak", "لا": "unknowing", "هاد": "jews",
}
# فاعل القول بلمّته
SAID_LEMMA = {
    "ملا": "mala", "منافق": "hypocrites", "اعراب": "bedouins", "سفيه": "fools", "شيطان": "satan",
    "ملك": "angels", "نسوه": "women", "رسول": "messengers", "ضعيف": "weak", "خزنه": "keepers",
    "جن": "jinn", "انسان": "human", "كافر": "disbelievers", "ظالم": "wrongdoers", "نمله": "ants",
    "يهود": "jews", "نصراني": "christians", "ناس": "people", "الله": "god", "حواري": "disciples",
}
SAID_AFTER_ASHAB = {"جنه": "paradise", "نار": "fire", "اعراف": "araf"}
SAID_NOT = {"مَلِك"}  # ﴿وقال الملِك﴾ (ملك مصر) لا ﴿الملَك﴾
# أفعال لا يقولها بضمير «نا» إلا الله: ﴿أنزلنا﴾، ﴿أرسلنا﴾، ﴿خلقنا﴾…
DIVINE_VERBS = {"انزل", "نزل", "ارسل", "خلق", "جعل", "اوحي", "اهلك", "اغرق", "نجي", "انجي", "اتي", "قص",
                "صرف", "ذرا", "سخر", "زين", "فتح", "اعطي", "يسر", "اعتد", "دمر", "وهب", "اصطفي", "اورث",
                "مكن", "اري", "قضي", "وصي", "كرم", "بلا", "انشا", "ظلل", "بعث", "كتب", "رزق", "قلب", "طبع"}
# ما يضيفه الله إلى نفسه: ﴿عبادي﴾، ﴿آياتي﴾، ﴿رسلي﴾، ﴿عذابي﴾، ﴿رحمتي﴾…
DIVINE_OWN = {"عبد", "ايه", "رسول", "عذاب", "رحمه", "نعمه", "ذكر", "وعيد", "نذير", "نذر", "نكير"}
PREPOSITIONS = {"ل", "الي", "علي", "في", "من", "عن", "ب", "مع"}
ADDR_VOC, ADDR_QUL, ADDR_ASKED, ADDR_PRAYER = 0, 1, 2, 3   # نوع الخطاب
SPEAK_SAID, SPEAK_WE, SPEAK_QUL = 0, 1, 2                   # نوع الكلام


def _char_at(words, i, markers):
    """معرّف الشخصية التي تبدأ علامتها في الكلمة i، أو None."""
    for j, _, ident in find_markers(words[i:i + 6], markers):
        if j == 0 and ident and ident in CHAR_BY_ID:
            return ident
    return None


def vocative(words, i, markers):
    """المنادى بأداة النداء في الكلمة i: معرّف جماعة أو شخصية، أو None."""
    w = words[i]
    nxt = words[i + 1] if i + 1 < len(words) else None
    if w["lem"] in VOC_EXCLAIM:
        return None
    if w["lem"] == "اي":
        if nxt is None:
            return None
        if nxt["nt"] == "الذين" and i + 2 < len(words):
            return VOC_ALLADHINA.get(words[i + 2]["lem"])
        return VOC_AYYUHA.get(nxt["nt"])
    if w["lem"] in ("ابن", "بني"):
        if nxt is not None and nxt["lem"] == "ادم":
            return "bani_adam"
        if nxt is not None and nxt["lem"] == "اسراييل":
            return "bani_israil"
        if nxt is not None and nxt["lem"] == "ام":
            return "musa"  # ﴿يا ابن أم﴾: هارون يخاطب أخاه
        return "son"
    if w["lem"] == "اهل" and nxt is not None:
        return {"كتاب": "ahl_kitab", "يثرب": "yathrib"}.get(nxt["lem"])
    if w["lem"] == "ذو":  # ﴿يا ذا القرنين﴾ غير ﴿يا أولي الألباب﴾ (اللمّة واحدة)
        return "dhulqarnayn" if nxt is not None and nxt["lem"] == "قرن" else "ulul"
    if w["lem"] in VOC_LEMMA:
        return VOC_LEMMA[w["lem"]]
    return _char_at(words, i, markers)


def is_prayer(words, i):
    """﴿ربنا…﴾، ﴿رب…﴾ بلا أداة نداء: دعاء. (﴿إن ربنا لغفور﴾ و﴿قال ربي يعلم﴾ ليسا دعاء.)"""
    w = words[i]
    if w["lem"] != "رب" or w["voc"]:
        return False
    if i > 0 and words[i - 1]["lem"] in ("ان", "لكن", "ليت", "لعل"):
        return False
    if "1P" in w["suf"]:
        return "ACC" in w["tags"]
    return "1S" in w["suf"] and w["nt"] in ("رب", "ورب", "فرب")


def speech_subject(words, i, markers):
    """فاعل فعل القول في الكلمة i إذا ذُكر بعده: معرّف جماعة أو شخصية، أو None."""
    # يُتخطى المقول له (﴿قال لقومه﴾، ﴿قالت لهم رسلهم﴾) لا الفعل (﴿ليمسن الذين كفروا﴾ مقولٌ لا فاعل)
    j = i + 1
    while j < len(words) and j <= i + 3 and words[j]["pos"] != "V" and (
            words[j]["lem"] in PREPOSITIONS or "ل" in words[j]["pre"]):
        j += 1
    if j >= len(words):
        return None
    x = words[j]
    if x["voc"] or "GEN" in x["tags"] or "ACC" in x["tags"]:
        return None  # ﴿قالوا يا موسى﴾ نداء، و﴿قالوا تالله﴾ قسم: الفاعل غير مذكور
    char = _char_at(words, j, markers)
    if char:
        return "prophet" if char == "muhammad" else char
    if x["nt"] == "الذين" and j + 1 < len(words):  # الجمع وحده: ﴿وقال الذي آمن﴾ رجل بعينه
        after = words[j + 2]["lem"] if j + 2 < len(words) else ""
        if words[j + 1]["lem"] == "اوتي":
            return {"علم": "knowledge", "كتاب": "ahl_kitab"}.get(after)
        if words[j + 1]["lem"] == "في":  # ﴿الذين في قلوبهم مرض﴾ غير ﴿الذين في النار﴾
            return {"قلب": "hypocrites", "نار": "fire"}.get(after)
        return SAID_ALLADHINA.get(words[j + 1]["lem"])
    if x["lem"] == "اصحاب" and j + 1 < len(words):
        return SAID_AFTER_ASHAB.get(words[j + 1]["lem"])
    if x["lem"] == "رب" and "NOM" in x["tags"] and not ({"1S", "1P"} & set(x["suf"])):
        return "god"  # ﴿قال ربك﴾، ﴿قال ربكم﴾
    if x["lem"] in SAID_LEMMA and "NOM" in x["tags"] and x["raw"] not in SAID_NOT:
        return SAID_LEMMA[x["lem"]]
    return None


def voices(verses, in_story):
    """يرجع (المخاطَبون، المتكلمون): {معرّف: [[سورة، آية، نوع]]} بترتيب المصحف."""
    markers = [(m, c[0]) for c in CHARACTERS for m in c[4]]
    addressed, speaking = defaultdict(list), defaultdict(list)

    def add(table, ident, s, a, kind):
        ident = "prophet" if ident == "muhammad" else ident
        if ident and not any(x[0] == s and x[1] == a for x in table[ident]):
            table[ident].append([s, a, kind])

    for v in verses:
        s, a, words = v["s"], v["a"], v["words"]
        story = in_story.get((s, a))
        spoken_by_other = False  # فعل قول فاعله غير الله قبل الموضع: ما بعده كلامه
        for i, w in enumerate(words):
            if w["voc"]:
                add(addressed, vocative(words, i, markers), s, a, ADDR_VOC)
            elif w["lem"] == "اللهم" or is_prayer(words, i):
                add(addressed, "god", s, a, ADDR_PRAYER)
            if w["lem"] == "قال" and w["pos"] == "V":
                if "IMPV" in w["tags"] and w["person"] == "2MS":
                    if story in (None, "muhammad"):  # ﴿قل﴾ في غير قصص الأنبياء السابقين
                        add(addressed, "prophet", s, a, ADDR_QUL)
                        add(speaking, "prophet", s, a, SPEAK_QUL)
                    spoken_by_other = True
                elif w["person"] == "1P" and "PERF" in w["tags"] and not spoken_by_other:
                    add(speaking, "god", s, a, SPEAK_SAID)  # ﴿وإذ قلنا للملائكة﴾
                elif w["person"][:1] == "3":
                    who = speech_subject(words, i, markers)
                    add(speaking, who, s, a, SPEAK_SAID)
                    spoken_by_other = spoken_by_other or who != "god"
                else:
                    spoken_by_other = True
            elif w["lem"] == "سال" and "IMPF" in w["tags"] and "2MS" in w["suf"]:
                add(addressed, "prophet", s, a, ADDR_ASKED)  # ﴿يسألونك﴾
            elif not spoken_by_other and w["pos"] == "V" and w["person"] == "1P" and "PASS" not in w["tags"] \
                    and w["lem"] in DIVINE_VERBS:
                add(speaking, "god", s, a, SPEAK_WE)
            elif not spoken_by_other and "1S" in w["suf"] and w["lem"] in DIVINE_OWN and not w["voc"]:
                add(speaking, "god", s, a, SPEAK_WE)
    return addressed, speaking


def _label(ident):
    if ident in CHAR_BY_ID:
        return CHAR_BY_ID[ident][1]
    return GROUP_NAMES[ident]


def build_order(verses):
    """بيانات web/data/order.json."""
    passages, mentions, stages = analyze(verses)
    in_story = {}
    for era, s, a1, a2 in passages:
        if era not in ("hour", "creation"):
            for a in range(a1, a2 + 1):
                in_story[(s, a)] = era
    addressed, speaking = voices(verses, in_story)

    def chars_in(s, a1, a2):
        found = []
        for a in range(a1, a2 + 1):
            for c in mentions.get((s, a), {}):
                if c not in found:
                    found.append(c)
        return found

    by_era = defaultdict(list)
    for era, s, a1, a2 in sorted(passages, key=lambda p: (p[1], p[2])):
        item = [s, a1, a2, chars_in(s, a1, a2)]
        if era == "hour":
            item.append(stages[(s, a1)])
        by_era[era].append(item)
    eras = []
    for ident, title, evidence in ERAS:
        era = {"id": ident, "title": title, "evidence": [list(e) for e in evidence], "passages": by_era[ident]}
        if ident in ERA_NOTES:
            era["note"] = ERA_NOTES[ident]
        if ident == "hour":
            era["stages"] = [[k, HOUR_STAGES[k]] for k in (1, 2, 3, 4, 0)]
        eras.append(era)
    unplaced = [{"id": era[2:], "title": CHAR_BY_ID[era[2:]][1], "passages": by_era[era]}
                for era in sorted(by_era, key=lambda e: min((p[0], p[1]) for p in by_era[e]))
                if era.startswith("u:")]
    characters = []
    for ident, name, group, era, _ in CHARACTERS:
        refs = sorted(key for key, chars in mentions.items() if ident in chars)
        if not refs:
            continue
        characters.append({
            "id": ident, "name": name, "group": group, "era": era or "u:" + ident, "story": STORY_OF.get(ident),
            "mentions": [[s, a, int(mentions[(s, a)][ident])] for s, a in refs],
        })

    def table(source):
        rows = [{"id": k, "name": _label(k), "verses": v} for k, v in source.items()]
        return sorted(rows, key=lambda r: -len(r["verses"]))

    return {
        "eras": eras,
        "unplaced": {"note": UNPLACED_NOTE, "stories": unplaced},
        "groups": [PERSON, PEOPLE, UNSEEN],
        "stories": [{"id": ident, "name": name, "members": members} for ident, name, members in STORIES],
        "characters": characters,
        "addressees": table(addressed),
        "speakers": table(speaking),
    }


def main():
    data = build_order(parse_words())
    os.makedirs(build.OUT_DIR, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    told = sum(p[2] - p[1] + 1 for e in data["eras"] for p in e["passages"])
    print(f"{len(data['characters'])} شخصية · {told} آية في الحقب · "
          f"{len(data['addressees'])} مخاطَبًا · {len(data['speakers'])} متكلمًا ← {OUT_FILE}", file=sys.stderr)


if __name__ == "__main__":
    main()
