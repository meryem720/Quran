"""بناء بيانات تطبيق «تفسير القرآن بالقرآن».

يقرأ ملف الصرف (Quranic Arabic Corpus) ويحسب لكل آية الآيات المرتبطة بها
اعتمادًا على مؤشرات من داخل القرآن فقط:
  1. الجذور واللمّات المشتركة (TF-IDF + تشابه جيب التمام)، ومعها أسماء الأعلام
  1ب. اللفظ النادر: الكلمة التي لا ترد إلا في آيتين أو ثلاث تُفهم من مواضعها الأخرى
  2. العبارات المتطابقة (n-grams بعد حذف التشكيل)
  3. التعبير المشترك بصيغ مختلفة (أزواج اللمّات المتقاربة)
  4. السياق والبيان الداخلي (قواعد على النص، ومنها الكلام المتصل بالآية السابقة)

الاستعمال:
    python3 tools/build.py
ينتج web/data/quran.json و web/data/related.json
"""

import json
import math
import os
import re
import sys
from collections import defaultdict

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MORPH_FILE = os.path.join(ROOT_DIR, "data", "quran-morphology.txt")
WAQF_FILE = os.path.join(ROOT_DIR, "data", "waqf.tsv")
OUT_DIR = os.path.join(ROOT_DIR, "web", "data")

TOP_K = 10
WEIGHTS = {"roots": 1.0, "rare": 0.3, "phrase": 1.0, "expression": 1.0, "context": 2.0, "passage": 0.5}
# الخصائص الشائعة جدًا (مثل «قول» و«الله») لا تميّز بين الآيات
MAX_FEATURE_DF = 400
# الألفاظ الشائعة جدًا لا تُبنى عليها مطابقة الجمل (idf أقل من هذا: أكثر من نحو 400 آية)
MIN_CLAUSE_IDF = math.log(6236 / 400)
MAX_NGRAM_DF = 40
NGRAM_SIZES = (2, 3, 4)
MIN_ROOT_SCORE = 0.08
# المقاطع المتناظرة (انظر parallel_passages)
PASSAGE_TAU = 0.6
PASSAGE_GAP = 8
PASSAGE_MIN = 3
PASSAGE_DENSITY = 0.4
PASSAGE_ORDER = 0.7
PASSAGE_MARGIN = 1
PASSAGE_WINDOW = 5
PASSAGE_SUPPORT = 0.1
PASSAGE_NAME_VERSES = 2
PASSAGE_NAME_BACK = 20
# البيان جملةً جملة (انظر clause_similarity)
CLAUSE_WEIGHT = 0.8   # وزن تشابه الجملتين مقارنةً بتشابه الآيتين كاملتين
CLAUSE_INFO = 8.0     # مجموع ندرة الألفاظ المشتركة (idf) الذي تُعدّ به الجملتان متطابقتين معنًى
CLAUSE_STRONG = 0.6   # تشابه قوي بين جملتين
CLAUSE_FORMULA = 4    # جملة تشبه بقوة جملًا في هذا العدد من الآيات فأكثر: صيغة لا بيان
CLAUSE_MIN_WORDS = 2  # أقل عدد من الألفاظ ذات المعنى غير الشائعة في الجملة
CLAUSE_KEEP = 5       # أفضل ما يُحفظ لكل جملة
# لكل جملة من الآية الطويلة أفضل بياناتها (CLAUSE_PER) في القائمة إن بلغت درجتها هذه النسبة
# من أقوى رابط (None: ترتيب بالدرجة وحدها)
CLAUSE_FAIR = 0.5
CLAUSE_PER = 2        # كم بيانًا يُضمن لكل جملة
CLAUSE_POOL = 40      # ما يُنظر فيه من المرشحين لذلك
# رابط لا يبيّن من الآية إلا جملة صيغة متكررة (﴿كذلك يبين الله لكم الآيات﴾): تُضرب درجته في هذا
FORMULA_PENALTY = 0.5
# ألفاظ الفواصل: لفظ يختم الآية في هذه النسبة من مواضعه فأكثر (عليم، حكيم، غفور رحيم…)
FASILA_SHARE = 0.85
FASILA_MIN = 25
# اللفظ النادر: لا يرد إلا في هذا العدد من الآيات أو أقل
RARE_DF = 3
RARE_ROOT_DF = 60
# أقصى مسافة بين كلمتي التعبير: ﴿أنعمتَ عليهم﴾ و﴿أنعم اللهُ عليهم﴾
EXPRESSION_GAP = 2
# أزواج الجذور المتجاورة بأي ترتيب (انظر root_pair_similarity)
ROOTPAIR_GAP = 3        # حتى كلمتين بين الجذرين
ROOTPAIR_WEIGHT = 0.3
ROOTPAIR_ADD = True     # True: يُضاف دائمًا، False: فقط إذا لم تتطابق العبارة ولا التعبير
ROOTPAIR_MAX_DF = 5     # لا يُعدّ إلا زوج نادر جدًا (جُرّب حتى 40 آية فأدخل ضجيجًا ونقص بعض الأمثلة)

SURAH_NAMES = [
    "الفاتحة", "البقرة", "آل عمران", "النساء", "المائدة", "الأنعام", "الأعراف",
    "الأنفال", "التوبة", "يونس", "هود", "يوسف", "الرعد", "إبراهيم", "الحجر",
    "النحل", "الإسراء", "الكهف", "مريم", "طه", "الأنبياء", "الحج", "المؤمنون",
    "النور", "الفرقان", "الشعراء", "النمل", "القصص", "العنكبوت", "الروم",
    "لقمان", "السجدة", "الأحزاب", "سبأ", "فاطر", "يس", "الصافات", "ص", "الزمر",
    "غافر", "فصلت", "الشورى", "الزخرف", "الدخان", "الجاثية", "الأحقاف", "محمد",
    "الفتح", "الحجرات", "ق", "الذاريات", "الطور", "النجم", "القمر", "الرحمن",
    "الواقعة", "الحديد", "المجادلة", "الحشر", "الممتحنة", "الصف", "الجمعة",
    "المنافقون", "التغابن", "الطلاق", "التحريم", "الملك", "القلم", "الحاقة",
    "المعارج", "نوح", "الجن", "المزمل", "المدثر", "القيامة", "الإنسان",
    "المرسلات", "النبأ", "النازعات", "عبس", "التكوير", "الانفطار", "المطففين",
    "الانشقاق", "البروج", "الطارق", "الأعلى", "الغاشية", "الفجر", "البلد",
    "الشمس", "الليل", "الضحى", "الشرح", "التين", "العلق", "القدر", "البينة",
    "الزلزلة", "العاديات", "القارعة", "التكاثر", "العصر", "الهمزة", "الفيل",
    "قريش", "الماعون", "الكوثر", "الكافرون", "النصر", "المسد", "الإخلاص",
    "الفلق", "الناس",
]

# التشكيل وعلامات الضبط القرآنية
_DIACRITICS = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭـ]")
_LETTER_MAP = str.maketrans({
    "ٱ": "ا", "أ": "ا", "إ": "ا", "آ": "ا",
    "ى": "ي", "ئ": "ي", "ؤ": "و", "ة": "ه",
})


def normalize(text):
    """يحذف التشكيل ويوحّد أشكال الحروف حتى تتطابق الكلمات."""
    return _DIACRITICS.sub("", text).translate(_LETTER_MAP).replace(" ", "")


def _start_kind(segments):
    """كيف تبدأ الآية؟ بعض البدايات لا يُبتدأ بها كلام، فالآية تتمة لما قبلها:

    - "gen": اسم مجرور بلا حرف جر ولا عطف، فهو صفة أو بدل مما قبله:
      ﴿قتل أصحاب الأخدود ۝ النارِ ذات الوقود﴾، ﴿بعادٍ ۝ إرمَ ذات العماد﴾.
    - "illa": ﴿إلا﴾ استثناء مما قبلها: ﴿إن الإنسان لفي خسر ۝ إلا الذين آمنوا﴾.
    - "yawm": ﴿يوم/يومئذ/أياما﴾ ظرف يبيّن وقت ما قبلها: ﴿ولا تخزني يوم يبعثون ۝ يوم لا ينفع مال ولا بنون﴾.
    - "ulaika": ﴿أولئك﴾ إشارة إلى من وُصفوا قبلها: ﴿والسابقون السابقون ۝ أولئك المقربون﴾.
    - "idha": ﴿إذا﴾ بلا عطف تصف حال ما قبلها: ﴿خلق هلوعا ۝ إذا مسه الشر جزوعا﴾.
    - "bala": ﴿بلى﴾ جواب ما نُفي قبلها: ﴿أيحسب الإنسان ألن نجمع عظامه ۝ بلى قادرين﴾.
    - "faman": ﴿فمن﴾ تفريع على حكم ما قبلها أو خبره: ﴿فاقطعوا أيديهما ۝ فمن تاب من بعد ظلمه﴾،
      ﴿ليروا أعمالهم ۝ فمن يعمل مثقال ذرة خيرا يره﴾ (صحيح في مواضعه الثمانية عشر).
    """
    prefixes = [tags for _, tags in segments if "PREF" in tags]
    stems = [(pos, tags) for pos, tags in segments if "PREF" not in tags and "SUFF" not in tags]
    if prefixes and "PRP" in prefixes[0] and stems and stems[0][0] == "V":
        return "purpose"  # لام التعليل: ﴿ليجزي الذين آمنوا﴾ غاية ما قبلها
    if (stems and len(prefixes) == 1 and "LEM:ف" in prefixes[0] and "LEM:مَن" in stems[0][1]
            and {"COND", "REL", "INTG"} & set(stems[0][1])):
        return "faman"
    if not stems or any("DET" not in tags for tags in prefixes):
        return None  # تبدأ بحرف عطف أو جر: كلام جديد أو معطوف
    pos, tags = stems[0]
    if pos == "N" and "GEN" in tags:
        return "gen"
    if prefixes:
        return None
    if "LEM:إِلّا" in tags:
        return "illa"
    if "LEM:يَوْم" in tags:
        return "yawm"
    if "DEM" in tags and "LEM:ذا" in tags and "P" in tags:
        return "ulaika"
    if "LEM:إِذا" in tags:
        return "idha"
    if "LEM:بَلَى" in tags:
        return "bala"
    return None


def _fa_past_third(segments):
    if len(segments) < 2 or "LEM:ف" not in segments[0][1] or "PREF" not in segments[0][1]:
        return False
    pos, tags = segments[1]
    return pos == "V" and "PERF" in tags and any(t.startswith("3") for t in tags)


def parse_morphology(path):
    """يرجع قائمة الآيات مرتبة: كل آية فيها كلماتها مع الجذر واللمّة."""
    verses = {}
    questions = set()  # الآيات التي فيها أداة استفهام
    first_word = defaultdict(list)  # (سورة، آية) -> أجزاء الكلمة الأولى [(نوعها، وسومها)]
    third_person = set()  # آيات فيها ضمير غائب متصل
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            loc, form, pos_tag, tags = line.split("\t")
            s, a, w, _seg = (int(x) for x in loc.split(":"))
            if "INTG" in tags.split("|"):
                questions.add((s, a))
            if w == 1:
                first_word[(s, a)].append((pos_tag, tags.split("|")))
            parts_ = tags.split("|")
            if pos_tag == "N" and "PRON" in parts_ and "SUFF" in parts_ and any(t.startswith("3") for t in parts_):
                third_person.add((s, a))
            words = verses.setdefault((s, a), {})
            word = words.setdefault(w, {"text": "", "root": None, "lemma": None, "name": False, "verb": False,
                                        "conj": False, "initials": False})
            if "INL" in tags.split("|"):
                word["initials"] = True  # الحروف المقطعة: ﴿الم﴾، ﴿حم﴾
            word["text"] += form
            parts = tags.split("|")
            if _seg == 1 and "PREF" in parts and ("LEM:و" in parts or "LEM:ف" in parts):
                word["conj"] = True  # واو أو فاء ملتصقة في أول الكلمة: ﴿والله﴾، ﴿فاقطعوا﴾
            if "PN" in parts:
                word["name"] = True  # اسم علم: موسى، فرعون، مكة…
            root = next((t[5:] for t in parts if t.startswith("ROOT:")), None)
            lemma = next((t[4:] for t in parts if t.startswith("LEM:")), None)
            if root:
                # الجزء الذي يحمل الجذر هو أصل الكلمة
                word["root"], word["lemma"] = root, lemma
                word["verb"] = pos_tag == "V"
            elif lemma and word["lemma"] is None and "PREF" not in parts:
                word["lemma"] = lemma
    result = []
    for (s, a) in sorted(verses):
        words = verses[(s, a)]
        result.append({
            "s": s,
            "a": a,
            "question": (s, a) in questions,
            "start": _start_kind(first_word[(s, a)]),
            # قصّ متتابع: فاء ثم فعل ماضٍ لغائب، وفي الآية ضمير غائب (﴿قالت نملة… ۝ فتبسم ضاحكا من قولها﴾)
            "narrative": (s, a) in third_person and _fa_past_third(first_word[(s, a)]),
            "words": [
                {k: words[w][k] for k in ("text", "root", "lemma", "name", "verb", "conj", "initials")}
                for w in sorted(words)
            ],
        })
    return result


# ---------- المؤشر 1: الجذور واللمّات ----------

def _content(word):
    """كلمة ذات معنى: لها جذر، أو اسم علم (موسى، فرعون، جهنم ليس لها جذر في البيانات)."""
    return bool(word["root"] or (word["name"] and word["lemma"]))


def root_features(verse):
    feats = defaultdict(float)
    for w in verse["words"]:
        if w["root"]:
            feats["R:" + w["root"]] += 1.0
        if _content(w) and w["lemma"]:
            feats["L:" + normalize(w["lemma"])] += 1.0
    return feats


def tfidf_vector(feats, idf):
    """متجه TF-IDF موحّد الطول لسمات آية (root_features)."""
    vec = {k: (1 + math.log(tf)) * idf[k] for k, tf in feats.items()}
    norm = math.sqrt(sum(x * x for x in vec.values())) or 1.0
    return {k: x / norm for k, x in vec.items()}


def root_similarity(verses):
    """تشابه جيب التمام بين متجهات TF-IDF للجذور واللمّات."""
    n = len(verses)
    feats = [root_features(v) for v in verses]
    df = defaultdict(int)
    for f in feats:
        for k in f:
            df[k] += 1
    idf = {k: math.log(n / d) for k, d in df.items()}
    vectors = [tfidf_vector(f, idf) for f in feats]

    postings = defaultdict(list)
    for i, vec in enumerate(vectors):
        for k, x in vec.items():
            if df[k] <= MAX_FEATURE_DF:
                postings[k].append((i, x))

    scores = []
    for i, vec in enumerate(vectors):
        acc = defaultdict(float)
        for k, x in vec.items():
            if df[k] > MAX_FEATURE_DF:
                continue
            for j, y in postings[k]:
                if j != i:
                    acc[j] += x * y
        scores.append(acc)
    return scores, idf


# ---------- المؤشر 1أ: البيان جملةً جملة ----------

def load_clauses(verses, path=WAQF_FILE):
    """جمل كل آية بحسب علامات الوقف في المصحف (tools/waqf.py): [[(أول كلمة، بعد آخر كلمة)]].
    الآية بلا وقف داخلها جملة واحدة."""
    ends = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    key, cuts = line.rstrip("\n").split("\t")
                    ends[key] = [int(x) for x in cuts.split(",")]
    result = []
    for v in verses:
        cuts = [0] + ends.get(f"{v['s']}:{v['a']}", []) + [len(v["words"])]
        result.append([(cuts[k], cuts[k + 1]) for k in range(len(cuts) - 1)])
    return result


def fasila_lemmas(verses):
    """ألفاظ الفواصل: تختم الآية في أكثر مواضعها (﴿إن الله غفور رحيم﴾، ﴿وهو العزيز الحكيم﴾).
    لا تدل وحدها على أن جملتين في معنى واحد."""
    final, total = defaultdict(int), defaultdict(int)
    for v in verses:
        lemmas = ["L:" + normalize(w["lemma"]) for w in v["words"] if _content(w) and w["lemma"]]
        for k in set(lemmas):
            total[k] += 1
        for k in set(lemmas[-2:]):
            final[k] += 1
    return {k for k, f in final.items() if f >= FASILA_MIN and f / total[k] >= FASILA_SHARE}


def clause_similarity(verses, clauses, idf):
    """الآية الطويلة تقول أشياء عدة، فتُقارن كل جملة منها بجمل الآيات الأخرى، فلا تضيع جملة
    ﴿يسألونك عن الخمر والميسر﴾ في طول آية البقرة 219 كما تضيع في تشابه الآيتين كاملتين.

    تشابه جملتين = جيب التمام × نسبة ما تشتركان فيه من ندرة الألفاظ (idf لكل لفظ مرة، دون ألفاظ
    الفواصل) إلى CLAUSE_INFO، فلا تكفي كلمة واحدة شائعة ولا ﴿سميع عليم﴾. والجملة الأخيرة التي تشبه
    خواتيم آيات كثيرة صيغة ختام (﴿ومن كفر فإن الله غني عن العالمين﴾) لا يُبنى عليها.
    والجملة التي كل ألفاظها من أسماء الفواصل (﴿والله عزيز حكيم﴾) صيغة ختام كذلك.
    تُحفظ لكل جملة أفضل CLAUSE_KEEP آيات، فلكل جملة نصيبها.
    يرجع ([لكل آية {آية: (التشابه، رقم الجملة فيها، رقم الجملة في الأخرى)}]، [لكل آية جملها الصيغ]).
    """
    fasila = fasila_lemmas(verses)
    units = []  # (رقم الآية، رقم الجملة، المتجه بعد التطبيع)
    formulas = defaultdict(set)
    for i, v in enumerate(verses):
        for c, (start, end) in enumerate(clauses[i]):
            feats = root_features({"words": v["words"][start:end]})
            specific = [k for k in feats if k.startswith("L:") and idf[k] >= MIN_CLAUSE_IDF]
            # جملة كل ألفاظها من أسماء الفواصل (﴿والله عزيز حكيم﴾): صيغة ختام لا بيان
            if len(clauses[i]) > 1 and specific and all(k in fasila for k in specific):
                formulas[i].add(c)
                continue
            # ﴿قل العفو﴾: لفظ واحد ذو معنى بعد «قال» الشائعة، لا يكفي لمقارنة الجملة وحدها
            if sum(1 for k in feats if k.startswith("L:") and idf[k] >= MIN_CLAUSE_IDF) < CLAUSE_MIN_WORDS:
                continue
            vec = {k: (1 + math.log(tf)) * idf[k] for k, tf in feats.items()}
            norm = math.sqrt(sum(x * x for x in vec.values())) or 1.0
            units.append((i, c, {k: x / norm for k, x in vec.items()}))

    postings = defaultdict(list)
    for u, (i, c, vec) in enumerate(units):
        for k, x in vec.items():
            if idf[k] >= MIN_CLAUSE_IDF:
                postings[k].append((u, x))
    matches = []  # لكل جملة: {آية: (التشابه، رقم الجملة في الأخرى)}
    for i, c, vec in units:
        dot = defaultdict(float)
        info = defaultdict(float)
        for k, x in vec.items():
            if idf[k] < MIN_CLAUSE_IDF:
                continue
            for u, y in postings[k]:
                dot[u] += x * y
                if k.startswith("L:") and k not in fasila:
                    info[u] += idf[k]
        found = {}
        for u, d in dot.items():
            j, cj, _ = units[u]
            score = d * min(1.0, info[u] / CLAUSE_INFO)
            if j != i and score > found.get(j, (0,))[0]:
                found[j] = (score, cj)
        matches.append(found)

    best = defaultdict(dict)
    for (i, c, _), found in zip(units, matches):
        # جملة أخيرة تشبه بقوة خواتيم آيات كثيرة: صيغة ختام (﴿كذلك يبين الله لكم الآيات﴾).
        # أما الجملة المتكررة في أول الآية أو وسطها فتعليم يكرره القرآن (﴿لا أملك لنفسي ضرا ولا نفعا﴾)
        if (c == len(clauses[i]) - 1 > 0
                and sum(1 for score, _ in found.values() if score >= CLAUSE_STRONG) >= CLAUSE_FORMULA):
            formulas[i].add(c)
            continue
        for j, (score, cj) in sorted(found.items(), key=lambda t: -t[1][0])[:CLAUSE_KEEP]:
            if score > best[i].get(j, (0,))[0]:
                best[i][j] = (score, c, cj)
    return [best[i] for i in range(len(verses))], [formulas[i] for i in range(len(verses))]


# ---------- المؤشر 1ب: اللفظ النادر ----------

def rare_word_links(verses):
    """اللفظ الذي لا يرد إلا في آيات قليلة يُفهم أولًا من مواضعه الأخرى (تفسير الغريب بنظائره).

    مثال: ﴿سَبْعًا مِّنَ ٱلْمَثَانِى﴾ (الحجر 87) و﴿كِتَٰبًا مُّتَشَٰبِهًا مَّثَانِىَ﴾ (الزمر 23):
    لا يرد لفظ «مثاني» إلا فيهما، فلا يضيع في طول آية الزمر كما يضيع في تشابه الجذور.
    يرجع لكل آية {آية أخرى: (القوة بين 0 و1، اللفظ كما في الآية، عدد الآيات التي ورد فيها)}.
    """
    n = len(verses)
    root_df = defaultdict(set)
    for i, v in enumerate(verses):
        for w in v["words"]:
            if w["root"]:
                root_df[w["root"]].add(i)
    postings = defaultdict(dict)  # لمّة -> {رقم الآية: الكلمة}
    for i, v in enumerate(verses):
        for w in v["words"]:
            # صيغة نادرة من جذر شائع تأتي غالبًا بمعنى آخر (﴿ولو كثرت﴾ و﴿مما قل منه أو كثر﴾)
            if _content(w) and w["lemma"] and len(root_df.get(w["root"], ())) <= RARE_ROOT_DF:
                postings[normalize(w["lemma"])].setdefault(i, w["text"])
    links = defaultdict(dict)
    for occ in postings.values():
        if not 2 <= len(occ) <= RARE_DF:
            continue
        strength = math.log(n / len(occ)) / math.log(n)
        for i, word in occ.items():
            for j in occ:
                if j != i and strength > links[i].get(j, (0,))[0]:
                    links[i][j] = (strength, word, len(occ))
    return links


# ---------- المؤشر 2: العبارات المتطابقة ----------

def _bare(word):
    """الكلمة موحّدة دون حرف العطف أو الاستئناف الملتصق بها (من وسوم الصرف لا من الحرف الأول)."""
    token = normalize(word["text"])
    return token[1:] if word.get("conj") and len(token) > 1 else token


def ngrams(tokens, size):
    return [(k, " ".join(tokens[k:k + size])) for k in range(len(tokens) - size + 1)]


def phrase_similarity(verses):
    """يجد العبارات (2 إلى 4 كلمات) المشتركة بين الآيات، والنادرة أهم.
    تُقارن الكلمات دون الواو والفاء الملتصقتين بأولها، فتتطابق ﴿إن الله لا يستحيي﴾ و﴿والله لا يستحيي﴾."""
    n = len(verses)
    tokens = [[_bare(w) for w in v["words"]] for v in verses]
    content = [[_content(w) for w in v["words"]] for v in verses]
    index = defaultdict(set)
    for i, toks in enumerate(tokens):
        for size in NGRAM_SIZES:
            for _, g in ngrams(toks, size):
                index[(size, g)].add(i)

    scores = []
    best_phrase = []
    for i, toks in enumerate(tokens):
        acc = defaultdict(float)
        best = {}
        for size in NGRAM_SIZES:
            for pos, g in ngrams(toks, size):
                ids = index[(size, g)]
                if len(ids) > MAX_NGRAM_DF:
                    continue
                # عبارة من حروف وأدوات فقط (مثل «وما أدراك ما») لا تبيّن شيئًا،
                # فالوزن بحسب عدد الكلمات ذات الجذر فيها
                words_with_root = sum(content[i][pos:pos + size])
                if words_with_root < 2:
                    continue
                weight = math.log(n / len(ids)) * (words_with_root - 1)
                for j in ids:
                    if j == i:
                        continue
                    acc[j] += weight
                    if j not in best or best[j][0] < size:
                        best[j] = (size, pos)
        # نحوّل المجموع إلى قيمة بين 0 و1
        scores.append({j: x / (x + 20.0) for j, x in acc.items()})
        best_phrase.append({
            j: " ".join(w["text"] for w in verses[i]["words"][pos:pos + size])
            for j, (size, pos) in best.items()
        })
    return scores, best_phrase


# ---------- المؤشر 3: التعبير المشترك بصيغ مختلفة ----------

def _lemma(word):
    return normalize(word["lemma"] or word["text"])


def root_pair_similarity(verses):
    """جذران متجاوران (بينهما كلمتان على الأكثر) بأي ترتيب وبأي صيغة: ﴿كلمة طيبة﴾ و﴿الكلم الطيب﴾،
    ﴿وأوحى ربك﴾ و﴿ربك أوحى﴾. اسم العلم بلا جذر يُعدّ بلمّته. الزوج النادر أهم."""
    n = len(verses)

    def key_of(w):
        return w["root"] or (normalize(w["lemma"]) if _content(w) and w["lemma"] else None)

    pairs, index = [], defaultdict(set)
    for i, v in enumerate(verses):
        ws = v["words"]
        found = {}
        for a in range(len(ws)):
            ka = key_of(ws[a])
            for b in range(a + 1, min(len(ws), a + ROOTPAIR_GAP + 1)):
                kb = key_of(ws[b])
                if ka and kb and ka != kb:
                    found.setdefault(tuple(sorted((ka, kb))), (a, b))
        pairs.append(found)
        for key in found:
            index[key].add(i)
    scores, best_pair = [], []
    for i, found in enumerate(pairs):
        acc = defaultdict(float)
        best = {}
        for key, (a, b) in found.items():
            ids = index[key]
            if len(ids) > ROOTPAIR_MAX_DF:
                continue
            weight = math.log(n / len(ids))
            for j in ids:
                if j != i:
                    acc[j] += weight
                    if j not in best or best[j][0] < weight:
                        best[j] = (weight, a, b)
        words = verses[i]["words"]
        scores.append({j: x / (x + 20.0) for j, x in acc.items()})
        best_pair.append({j: words[a]["text"] + (" " if b == a + 1 else " … ") + words[b]["text"]
                          for j, (_, a, b) in best.items()})
    return scores, best_pair


def expression_similarity(verses):
    """يطابق أزواج اللمّات المتقاربة بدل الحروف، فيجد التعبير نفسه بصيغ مختلفة.

    مثال: ﴿أَنْعَمْتَ عَلَيْهِمْ﴾ (الفاتحة 7) و﴿أَنْعَمَ ٱللَّهُ عَلَيْهِم﴾ (النساء 69)
    فيهما الزوج (أنعم، على) رغم اختلاف الصيغة وكلمة بينهما.
    """
    n = len(verses)
    pairs = []
    index = defaultdict(set)
    for i, v in enumerate(verses):
        ws = v["words"]
        found = {}
        for a in range(len(ws)):
            for b in range(a + 1, min(len(ws), a + EXPRESSION_GAP + 1)):
                if _content(ws[a]) or _content(ws[b]):
                    found.setdefault((_lemma(ws[a]), _lemma(ws[b])), (a, b))
        pairs.append(found)
        for key in found:
            index[key].add(i)

    scores = []
    best_expr = []
    for i, found in enumerate(pairs):
        acc = defaultdict(float)
        best = {}
        for key, (a, b) in found.items():
            ids = index[key]
            if len(ids) > MAX_NGRAM_DF:
                continue
            weight = math.log(n / len(ids))
            for j in ids:
                if j == i:
                    continue
                acc[j] += weight
                if j not in best or best[j][0] < weight:
                    best[j] = (weight, a, b)
        words = verses[i]["words"]
        scores.append({j: x / (x + 20.0) for j, x in acc.items()})
        best_expr.append({
            j: words[a]["text"] + (" " if b == a + 1 else " … ") + words[b]["text"]
            for j, (_, a, b) in best.items()
        })
    return scores, best_expr


# ---------- المؤشر 4: السياق والبيان الداخلي ----------

_ADRAKA = re.compile(r"(وما|ثمما)ادريك")
_QUESTION = re.compile(r"هل(اتيك|انبيكم|ننبيكم|ادلكم)")
QUESTION_MAX_WORDS = 12
# رموز أسباب السياق (تُعرض نصوصها في الواجهة)
CONTEXT_ADRAKA = 1    # جواب ﴿وما أدراك﴾
CONTEXT_RELATIVE = 2  # صفة متصلة بالآية السابقة
CONTEXT_QUESTION = 3  # جواب ﴿هل أتاك / هل أنبئكم / هل أدلكم﴾
CONTEXT_DIALOGUE = 4  # سؤال قصير يُجاب عنه في الآية التالية
CONTEXT_ANSWER_ELSEWHERE = 5  # العبارة نفسها سُئل عنها في موضع آخر وأُجيب
# كلام متصل: الآية الثانية تبدأ بما لا يُبتدأ به (انظر _start_kind)
CONTEXT_CONTINUATION = {"illa": 6, "gen": 7, "yawm": 8, "ulaika": 9, "idha": 10, "bala": 12, "faman": 13}
# التعليل (﴿ذلك بأنهم…﴾) والغاية (لام التعليل: ﴿ليجزي الذين آمنوا﴾) في أول الآية يبيّنان ما قبلها، لكن
# إدخالهما في ترتيب الروابط أخّر أمثلة صحيحة (الإضافية 0.33 ← 0.32)، فيُعرضان في صفحة الآية وحدهما
# (quran.json: "explains") ولا يدخلان في الحساب
def _is_cause(words):
    """﴿ذلك بأن…﴾، ﴿ذلكم بما…﴾: أول الآية ﴿ذلك﴾ أو ﴿ذلكم﴾ وكلمتها الثانية تبدأ بالباء
    (لا ﴿ذلك مبلغهم﴾، فالحروف لا تُدمج)."""
    return (len(words) > 1 and normalize(words[0]["text"]) in ("ذلك", "ذلكم")
            and normalize(words[1]["text"]).startswith("ب"))
# ﴿خير/شر من ذلك(م)﴾ مفاضلة تشير إلى ما في الآية السابقة (آل عمران 15، المائدة 60، الحج 72)
CONTEXT_COMPARISON = 14
_COMPARISON = re.compile("(خير|شر)منذلك")
# الآية بعد آية ﴿يسألونك﴾ تشترك معها في جذر غير شائع: تتمة الجواب (﴿ويسألونك عن المحيض﴾ ← ﴿نساؤكم حرث لكم﴾)
CONTEXT_ASKED = 15
# القصّ المتتابع: كثير في القرآن، فيُعطى جزءًا صغيرًا من وزن السياق
CONTEXT_NARRATIVE = 16
NARRATIVE_SHARE = 0.5
_ASKED = ("يسلونك", "ويسلونك")
# نصيب السياق من الدرجة: القصّ المتتابع دون الجواب والكلام المتصل
CONTEXT_SHARE = {CONTEXT_NARRATIVE: NARRATIVE_SHARE}
ASKED_ROOT_DF = 400
CONTEXT_PARALLEL = 11  # [11، سورة المقطع المقابل، أول آية، آخر آية]: القصة نفسها في موضع آخر
CONTEXT_INITIALS = 17  # تُفتتح السورتان بالحروف المقطعة نفسها (﴿الم﴾، ﴿حم﴾، ﴿طسم﴾)
CONTEXT_WEAK = 18      # آية لا يربطها بغيرها إلا ألفاظ شائعة: أقرب ما يشبهها، ويُنبَّه على ضعفه
WEAK_COUNT = 3
# لا يُنقل إلى المواضع الأخرى إلا جواب السؤال: أما الكلام المتصل فيصف موضعه وحده
# (جُرّب نقله فكانت أكثر نتائجه من الفواصل المتكررة مثل ﴿على كل شيء قدير﴾)
_ANSWER_TYPES = (CONTEXT_ADRAKA, CONTEXT_QUESTION, CONTEXT_DIALOGUE)
SHORT_QUESTION_WORDS = 5
_ANSWER_START = ("قال", "قالوا", "قل", "قالت")
# جذور صيغ السؤال نفسها (﴿هل أتاك حديث﴾، ﴿وما أدراك﴾، ﴿هل أنبئكم﴾، ﴿هل أدلكم﴾): ليست موضوع السؤال
_FORMULA_ROOTS = {"أتي", "حدث", "دري", "نبأ", "دلل"}
_RELATIVE_START = ("الذين", "الذي", "التي", "اللذين")


def _answers(question, answer):
    """هل الآية التالية جواب للسؤال القصير؟

    - حوار: تبدأ بـ﴿قال/قالوا/قل﴾، مثل ﴿وما تلك بيمينك يا موسى ۝ قال هي عصاي﴾.
    - أو يتكرر لفظ السؤال في أولها، مثل ﴿لأي يوم أجلت ۝ ليوم الفصل﴾
      و﴿من أي شيء خلقه ۝ من نطفة خلقه﴾ و﴿عم يتساءلون ۝ عن النبإ العظيم﴾.
    """
    q_tokens = [normalize(w["text"]) for w in question["words"]]
    first = answer["words"][0]
    first_token = normalize(first["text"])
    if first_token in _ANSWER_START:
        # ﴿قل أفلا تذكرون ۝ قل من رب السماوات﴾ سؤال يتبعه سؤال، لا جواب
        return not (first_token == "قل" and "قل" in q_tokens)
    if q_tokens[0] == "عم":
        return first_token == "عن"
    # الجواب لا يبدأ بحرف عطف (العطف استمرار للكلام لا جواب)
    if first_token[0] in "وف":
        return False
    if first_token == q_tokens[0]:
        return True
    q_roots = {w["root"] for w in question["words"] if w["root"]}
    return first["root"] in q_roots


def context_links(verses):
    """روابط من السياق المباشر: قواعد بسيطة على النص.

    - ﴿وما أدراك ما ...﴾ يُجاب عنها في الآية التالية التي ليس فيها «أدراك».
    - الآية التي تبدأ بـ«الذين/الذي» تصف كلمة في آخر الآية السابقة.
    - سؤال قصير يُجاب عنه في الآية التالية (انظر _answers).
    - ﴿هل أتاك حديث…﴾ و﴿هل أنبئكم…﴾ و﴿هل أدلكم…﴾ في آية قصيرة يُجاب عنها
      في الآية التالية (في الآية الطويلة يأتي الجواب غالبًا في الآية نفسها).
    - كلام متصل: الآية التي تبدأ بـ﴿إلا﴾ أو ﴿يوم﴾ أو ﴿أولئك﴾ أو ﴿إذا﴾ أو ﴿بلى﴾ أو ﴿فمن﴾ أو باسم
      مجرور تتمة للآية السابقة.
    """
    pos = {(v["s"], v["a"]): i for i, v in enumerate(verses)}
    links = defaultdict(dict)  # i -> {j: reason}
    root_verses = defaultdict(set)
    for i, v in enumerate(verses):
        for w in v["words"]:
            if w["root"]:
                root_verses[w["root"]].add(i)
    # اللوازم المتكررة (مثل ﴿فبأي آلاء ربكما تكذبان﴾) ليست أسئلة يُجاب عنها
    flats = ["".join(normalize(w["text"]) for w in v["words"]) for v in verses]
    repeats = defaultdict(int)
    for f in flats:
        repeats[f] += 1

    def add(i, j, reason):
        links[i][j] = reason
        links[j].setdefault(i, reason)

    # السور المفتتحة بالحروف المقطعة نفسها
    openings = defaultdict(list)
    for i, v in enumerate(verses):
        if v["words"] and v["words"][0]["initials"]:
            openings[normalize(v["words"][0]["text"])].append(i)
    for group in openings.values():
        for x in group:
            for y in group:
                if x != y:
                    links[x][y] = CONTEXT_INITIALS

    for i, v in enumerate(verses):
        flat = "".join(normalize(w["text"]) for w in v["words"])
        nxt_i = pos.get((v["s"], v["a"] + 1))
        if (v["question"] and len(v["words"]) <= SHORT_QUESTION_WORDS
                and nxt_i is not None and not _ADRAKA.search(flat) and repeats[flat] < 3
                and _answers(v, verses[nxt_i])):
            add(i, nxt_i, CONTEXT_DIALOGUE)
        if _ADRAKA.search(flat):
            k = v["a"] + 1
            while (v["s"], k) in pos:
                j = pos[(v["s"], k)]
                nxt = "".join(normalize(w["text"]) for w in verses[j]["words"])
                if not _ADRAKA.search(nxt):
                    # اللازمة (﴿وما أدراك ما يوم الفصل ۝ ويل يومئذ للمكذبين﴾) ليست جوابًا
                    if repeats[nxt] < 3:
                        add(i, j, CONTEXT_ADRAKA)
                    break
                k += 1
        if (_QUESTION.search(flat) and len(v["words"]) <= QUESTION_MAX_WORDS
                and (v["s"], v["a"] + 1) in pos):
            add(i, pos[(v["s"], v["a"] + 1)], CONTEXT_QUESTION)
        first = normalize(v["words"][0]["text"]) if v["words"] else ""
        prev_i = pos.get((v["s"], v["a"] - 1))
        if prev_i is None:
            continue
        if first in _RELATIVE_START:
            add(prev_i, i, CONTEXT_RELATIVE)
        elif v.get("start") in CONTEXT_CONTINUATION and i not in links[prev_i]:
            # لا يحل محل سبب أدق: ﴿هل أتاك حديث الجنود ۝ فرعون وثمود﴾ جواب قبل أن يكون بدلًا
            add(prev_i, i, CONTEXT_CONTINUATION[v["start"]])
        if (ASKED_ROOT_DF and normalize(verses[prev_i]["words"][0]["text"]) in _ASKED and i not in links[prev_i]
                and any(len(root_verses[r]) <= ASKED_ROOT_DF for r in
                        {w["root"] for w in verses[prev_i]["words"] if w["root"]}
                        & {w["root"] for w in v["words"] if w["root"]})):
            add(prev_i, i, CONTEXT_ASKED)
        if _COMPARISON.search(flat) and i not in links[prev_i]:
            # ﴿زين للناس حب الشهوات… ۝ قل أؤنبئكم بخير من ذلكم﴾
            add(prev_i, i, CONTEXT_COMPARISON)
        if NARRATIVE_SHARE and v.get("narrative") and i not in links[prev_i]:
            add(prev_i, i, CONTEXT_NARRATIVE)
    return links


# ---------- المؤشر 5: المقاطع المتناظرة (القصة الواحدة في موضعين) ----------

def _concordance(anchors):
    """نسبة أزواج المراسي التي تحفظ الترتيب في الموضعين (القصة المعادة تحفظ ترتيب أحداثها)."""
    good = bad = 0
    for x in range(len(anchors)):
        for y in range(x):
            (i1, j1, _), (i2, j2, _) = anchors[y], anchors[x]
            if i1 != i2 and j1 != j2:
                if (i1 < i2) == (j1 < j2):
                    good += 1
                else:
                    bad += 1
    return good / (good + bad) if good + bad else 0.0


def parallel_passages(verses, sim, candidates):
    """القصة تُعاد في موضعين فيبيّن كل موضع الآخر.

    1. المراسي: آيتان من سورتين مختلفتين متشابهتان جدًا (sim >= PASSAGE_TAU).
    2. المقطع: مراسٍ متقاربة في السورتين معًا (لا يزيد ما بينها على PASSAGE_GAP آيات)،
       فيها PASSAGE_MIN آيات مختلفة على الأقل في كل جانب، كثيفة في الجانب الأقصر،
       ومحفوظة الترتيب، ولها صاحب واحد يُذكر اسمه في آيتين على الأقل من كل جانب:
       قصة معادة لا موضوع متشابه (جُرّبت المقاطع بلا هذا الشرط فكان أكثرها أحكامًا
       أو أوصافًا متشابهة لا تتقابل آياتها).
    3. لكل آية في المقطع: أقرب ما يقابلها في الموضع الآخر بين المرسيين المحيطين بها،
       من القصة نفسها. ﴿فتلقى آدم من ربه كلمات فتاب عليه﴾ (البقرة 37) يقابلها في قصة طه
       ﴿ثم اجتباه ربه فتاب عليه وهدى﴾ (طه 122).
    يرجع لكل آية {آية: (القوة، [سورة المقطع المقابل، أول آية، آخر آية])}.
    """
    n = len(verses)
    names = [{normalize(w["lemma"]) for w in v["words"] if w["name"] and w["root"] != "أله"} for v in verses]

    # صاحب القصة عند كل آية: آخر من ذُكر اسمه قبلها في السورة (قريبًا منها)
    current = []
    for k, v in enumerate(verses):
        back = next((names[m] for m in range(k, max(k - PASSAGE_NAME_BACK, -1), -1)
                     if verses[m]["s"] == v["s"] and names[m]), set())
        current.append(back)

    def protagonists(lo, hi):
        """الأعلام المذكورة في آيتين من المقطع على الأقل: أصحاب القصة لا ذكر عابر."""
        counts = defaultdict(int)
        for k in range(lo, hi + 1):
            for name in names[k]:
                counts[name] += 1
        return {name for name, c in counts.items() if c >= PASSAGE_NAME_VERSES}

    pairs = defaultdict(list)  # (سورة، سورة) -> [(i, j, التشابه)]
    for i in range(n):
        for j in candidates(i):
            if j > i and verses[i]["s"] != verses[j]["s"]:
                x = sim(i, j)
                if x >= PASSAGE_TAU:
                    pairs[(verses[i]["s"], verses[j]["s"])].append((i, j, x))

    links = defaultdict(dict)
    for anchors in pairs.values():
        # تجميع المراسي المتقاربة في الموضعين
        parent = list(range(len(anchors)))

        def find(k):
            while parent[k] != k:
                parent[k] = parent[parent[k]]
                k = parent[k]
            return k
        for x in range(len(anchors)):
            for y in range(x):
                if (abs(anchors[x][0] - anchors[y][0]) <= PASSAGE_GAP
                        and abs(anchors[x][1] - anchors[y][1]) <= PASSAGE_GAP):
                    parent[find(x)] = find(y)
        groups = defaultdict(list)
        for k, a in enumerate(anchors):
            groups[find(k)].append(a)

        for group in groups.values():
            side_a = sorted({a[0] for a in group})
            side_b = sorted({a[1] for a in group})
            span_a = side_a[-1] - side_a[0] + 1
            span_b = side_b[-1] - side_b[0] + 1
            density = len(side_a) / span_a if span_a <= span_b else len(side_b) / span_b
            if (min(len(side_a), len(side_b)) < PASSAGE_MIN or density < PASSAGE_DENSITY
                    or _concordance(sorted(group)) < PASSAGE_ORDER):
                continue
            # قصة لا موضوع: لها في الموضعين صاحب واحد (موسى، فرعون، آدم، إبليس، نوح…)
            if not protagonists(side_a[0], side_a[-1]) & protagonists(side_b[0], side_b[-1]):
                continue
            side = (side_a, side_b)
            for src, dst, lo_b, hi_b in ((0, 1, side_b[0], side_b[-1]), (1, 0, side_a[0], side_a[-1])):
                marks = sorted((a[src], a[dst]) for a in group)
                surah = verses[lo_b]["s"]
                span = [surah, verses[lo_b]["a"], verses[hi_b]["a"]]
                first, last = marks[0][0], marks[-1][0]
                for k in range(first - PASSAGE_MARGIN, last + PASSAGE_MARGIN + 1):
                    if not 0 <= k < n or verses[k]["s"] != verses[first]["s"]:
                        continue
                    before = [m for m in marks if m[0] <= k] or marks[:1]
                    after = [m for m in marks if m[0] >= k] or marks[-1:]
                    near = [before[-1][1], after[0][1]]
                    lo = max(min(near) - PASSAGE_MARGIN, lo_b - PASSAGE_MARGIN)
                    hi = min(max(near) + PASSAGE_MARGIN, hi_b + PASSAGE_MARGIN)
                    window = [j for j in range(max(lo, 0), min(hi, n - 1) + 1) if verses[j]["s"] == surah]
                    if not window:
                        continue
                    # المقابل من القصة نفسها: نوح ثم هود ثم صالح تتتابع في الأعراف وهود
                    window = [j for j in window if current[k] & current[j]]
                    if not window:
                        continue
                    best = max(window, key=lambda j: (sim(k, j), -abs(j - sum(near) / 2)))
                    # بين مرسيين متباعدين لا يُخمَّن المقابل بلا لفظ يشهد له
                    if len(window) > PASSAGE_WINDOW and sim(k, best) < PASSAGE_SUPPORT:
                        continue
                    strength = 0.5 + 0.5 * min(1.0, sim(k, best))
                    # التقابل متبادل: كل من الآيتين تبيّن الأخرى
                    back = [verses[k]["s"], verses[side[src][0]]["a"], verses[side[src][-1]]["a"]]
                    for x, y, sp in ((k, best, span), (best, k, back)):
                        if strength > links[x].get(y, (0,))[0]:
                            links[x][y] = (strength, sp)
    return links


# ---------- الجمع بين المؤشرات ----------

def shared_roots(vi, vj, idf, limit=3):
    """الجذور المشتركة، ومعها أسماء الأعلام المشتركة (إبراهيم، فرعون…) إذ لا جذر لها."""
    def terms(v):
        out = {}
        for w in v["words"]:
            if w["root"]:
                out["R:" + w["root"]] = w["root"]
            elif _content(w):
                out["L:" + normalize(w["lemma"])] = _DIACRITICS.sub("", w["lemma"])
        return out
    ti, tj = terms(vi), terms(vj)
    common = sorted(ti.keys() & tj.keys(), key=lambda k: (-idf.get(k, 0), k))
    return [ti[k] for k in common[:limit]]


def _context_reason(i, j, context, elsewhere, best_phrase, verses):
    if j in context.get(i, {}):
        return context[i][j]
    q = elsewhere[j][1]
    return [CONTEXT_ANSWER_ELSEWHERE, verses[q]["s"], verses[q]["a"], best_phrase[i][q]]


def build_related(verses):
    roots, idf = root_similarity(verses)
    clauses = load_clauses(verses)
    by_clause, formula_clauses = clause_similarity(verses, clauses, idf)
    phrases, best_phrase = phrase_similarity(verses)
    expressions, best_expr = expression_similarity(verses)
    root_pairs, best_root_pair = root_pair_similarity(verses)
    context = context_links(verses)
    rare = rare_word_links(verses)

    # التشابه اللفظي وحده (دون السياق)، تُبنى عليه المقاطع المتناظرة
    def lexical(i, j):
        p = phrases[i].get(j, 0.0)
        e = expressions[i].get(j, 0.0) if p == 0 else 0.0
        w = rare[i][j][0] if j in rare[i] else 0.0
        return (WEIGHTS["roots"] * roots[i].get(j, 0.0) + WEIGHTS["rare"] * w
                + WEIGHTS["phrase"] * p + WEIGHTS["expression"] * e)

    passages = parallel_passages(
        verses, lexical, lambda i: set(roots[i]) | set(phrases[i]) | set(expressions[i]) | set(rare[i]))
    # سؤال ← جوابه (الجواب بعد السؤال دائمًا)
    answers = {
        q: a for q, links in context.items() for a, code in links.items()
        if code in _ANSWER_TYPES and a > q
    }
    # موضوع السؤال: أول كلمة ذات معنى بعد صيغته والكلمة التي تليها
    # (﴿وما أدراك ما يومُ الدين﴾ ← «يوم الدين»، فلا يختلط بـ﴿يوم الفصل﴾)
    subject = {}
    for q in answers:
        toks = [normalize(w["text"]) for w in verses[q]["words"]]
        k = next((k for k, w in enumerate(verses[q]["words"])
                  if _content(w) and w["root"] not in _FORMULA_ROOTS), None)
        subject[q] = toks[k:k + 2] if k is not None else [None]

    # أي جملة من الآية يبيّنها الرابط: أكثرها اشتراكًا معه في الألفاظ النادرة
    clause_lemmas = [[{k for k in root_features({"words": v["words"][a:b]}) if k.startswith("L:")}
                      for a, b in clauses[i]] for i, v in enumerate(verses)]
    verse_lemmas = [{k for k in root_features(v) if k.startswith("L:")} for v in verses]

    def explained_clause(i, j):
        if len(clauses[i]) < 2:
            return None
        if j in by_clause[i]:
            return by_clause[i][j][1]
        weights = [sum(idf[k] for k in lemmas & verse_lemmas[j]) for lemmas in clause_lemmas[i]]
        best = max(range(len(weights)), key=lambda c: weights[c])
        if weights[best] > 0:
            return best
        # كلام متصل بلا لفظ مشترك: الآية التالية تتمّ آخر الآية، والسابقة سياق أولها
        return len(clauses[i]) - 1 if j == i + 1 else 0 if j == i - 1 else None

    related = {}
    vectors = None  # متجهات الآيات بالجذور كلها، تُحسب عند الحاجة إليها في weak_links
    for i, v in enumerate(verses):
        # إذا وردت عبارة الآية (مثل ﴿يوم الدين﴾) في آية سُئل فيها عنها،
        # فجواب ذلك السؤال يبيّن العبارة هنا أيضًا: ﴿مالك يوم الدين﴾ ← الانفطار 19
        elsewhere = {}
        for j, p in phrases[i].items():
            a = answers.get(j)
            # العبارة المشتركة يجب أن تذكر موضوع السؤال، لا صيغته وحدها (﴿هل أتاك حديث﴾)
            # ولا ما جاء في وصفه (﴿تنجيكم من عذاب أليم﴾)
            if a is not None and not set(subject[j]) <= {normalize(t) for t in best_phrase[i][j].split()}:
                a = None
            if a is not None and a != i and a not in context.get(i, {}):
                if p > elsewhere.get(a, (0, None))[0]:
                    elsewhere[a] = (p, j)
        candidates = (set(roots[i]) | set(phrases[i]) | set(expressions[i])
                      | set(context.get(i, {})) | set(elsewhere) | set(rare[i]) | set(passages[i])
                      | set(by_clause[i]) | set(root_pairs[i]))
        ranked = []
        for j in candidates:
            # تشابه الآيتين كاملتين، أو جملة من هذه بجملة من تلك إن كان أقوى
            r = max(roots[i].get(j, 0.0), CLAUSE_WEIGHT * by_clause[i][j][0] if j in by_clause[i] else 0.0)
            w = rare[i][j][0] if j in rare[i] else 0.0
            p = phrases[i].get(j, 0.0)
            # التعبير يُحسب فقط إذا لم تتطابق العبارة حرفيًا، حتى لا يُعدّ الشيء مرتين
            e = expressions[i].get(j, 0.0) if p == 0 else 0.0
            # الجذران المتجاوران: إضافة لما لم تلتقطه العبارة ولا التعبير (أو دائمًا إن ROOTPAIR_ADD)
            q = root_pairs[i].get(j, 0.0) if ROOTPAIR_ADD or not (p or e) else 0.0
            c = 0.0
            if j in context.get(i, {}):
                c = CONTEXT_SHARE.get(context[i][j], 1.0)
            if not c and j in elsewhere:
                # بقدر تطابق العبارة مع آية السؤال
                c = elsewhere[j][0]
            m = passages[i][j][0] if j in passages[i] else 0.0
            if r < MIN_ROOT_SCORE and p == 0 and e == 0 and c == 0 and w == 0 and m == 0 and q == 0:
                continue
            score = (WEIGHTS["roots"] * r + WEIGHTS["rare"] * w + WEIGHTS["phrase"] * p
                     + WEIGHTS["expression"] * e + WEIGHTS["context"] * c + WEIGHTS["passage"] * m
                     + ROOTPAIR_WEIGHT * q)
            if formula_clauses[i] and not (c or w or m) and explained_clause(i, j) in formula_clauses[i]:
                score *= FORMULA_PENALTY
            ranked.append((score, j, r, p, e, c, w, m, q))
        ranked.sort(key=lambda t: (-t[0], t[1]))
        top = ranked[:TOP_K]
        if CLAUSE_FAIR is not None and len(clauses[i]) > 1 and ranked:
            # لكل جملة نصيبها: أفضل بيان لكل جملة أولًا، ثم البقية بالدرجة
            chosen, covered = [], defaultdict(int)
            for t in ranked[:CLAUSE_POOL]:
                c = explained_clause(i, t[1])
                if (c is not None and c not in formula_clauses[i] and covered[c] < CLAUSE_PER
                        and t[0] >= CLAUSE_FAIR * ranked[0][0]):
                    covered[c] += 1
                    chosen.append(t)
            chosen = chosen[:TOP_K]
            taken = {t[1] for t in chosen}
            rest = [t for t in ranked if t[1] not in taken][:TOP_K - len(chosen)]
            top = sorted(chosen + rest, key=lambda t: (-t[0], t[1]))

        # صيغة مختصرة لتصغير الملف:
        # [سورة، آية، الدرجة×100، سبب السياق، العبارة المشتركة، الجذور المشتركة، التعبير المشترك
        #  (، [اللفظ النادر، عدد آياته] أو 0 (، رقم الجملة التي يبيّنها من الآية))]
        # سبب السياق: رمز، أو [5، سورة السؤال، آيته، العبارة] للجواب في موضع آخر
        items = []
        for score, j, r, p, e, c, w, m, q in top:
            u = verses[j]
            roots_list = shared_roots(v, u, idf) if r >= MIN_ROOT_SCORE else []
            items.append([
                u["s"],
                u["a"],
                round(score * 100),
                (_context_reason(i, j, context, elsewhere, best_phrase, verses) if c
                 else [CONTEXT_PARALLEL, *passages[i][j][1]] if m else 0),
                best_phrase[i][j] if p else "",
                " ".join(roots_list),
                best_expr[i][j] if e else best_root_pair[i][j] if q else "",
            ])
            clause = explained_clause(i, j)
            if w or clause is not None:
                items[-1].append(list(rare[i][j][1:]) if w else 0)
            if clause is not None:
                items[-1].append(clause)
        if not items:
            if vectors is None:
                vectors = [tfidf_vector(root_features(u), idf) for u in verses]
            items = weak_links(verses, i, vectors)
        related[f"{v['s']}:{v['a']}"] = items
    return related


def weak_links(verses, i, vectors):
    """آية لم يُعثر لها على رابط (﴿والأرض وما طحاها﴾، ﴿الله الصمد﴾، ﴿ذواتا أفنان﴾): أقرب الآيات إليها
    بالجذور كلها ولو كانت شائعة (﴿والأرض بعد ذلك دحاها﴾، ﴿الله لا إله إلا هو الحي القيوم﴾)، والسياق
    CONTEXT_WEAK ينبّه القارئ على أنه رابط ضعيف."""
    mine = vectors[i]
    if not mine:
        return []
    near = []
    for j, u in enumerate(verses):
        if j == i or abs(j - i) == 1 and u["s"] == verses[i]["s"]:
            continue
        score = sum(x * vectors[j].get(k, 0.0) for k, x in mine.items())
        if score > 0:
            near.append((score, j))
    near.sort(key=lambda t: (-t[0], t[1]))
    items = []
    for score, j in near[:WEAK_COUNT]:
        u = verses[j]
        shared = sorted({w["root"] for w in verses[i]["words"] if w["root"]} & {w["root"] for w in u["words"] if w["root"]})
        items.append([u["s"], u["a"], round(score * 100), CONTEXT_WEAK, "", " ".join(shared), ""])
    return items


def build_quran(verses, clauses=None):
    surahs = []
    for v in verses:
        if v["s"] > len(surahs):
            surahs.append({"n": v["s"], "name": SURAH_NAMES[v["s"] - 1], "verses": []})
        # كل كلمة: [النص، الجذر، اللمّة] ويُضاف 1 لاسم العلم
        surahs[-1]["verses"].append([
            [w["text"], w["root"] or "", w["lemma"] or ""] + ([1] if w["name"] else [])
            for w in v["words"]
        ])
    # اللمّات الفعلية: تمييز الفعل من الاسم يفرّق «صَبَرَ» عن «جِنَّة» عند اتفاق الكتابة
    verbs = sorted({w["lemma"] for v in verses for w in v["words"] if w["verb"] and w["lemma"]})
    result = {"surahs": surahs, "verbs": verbs}
    # الآية تبيّن ما قبلها: سببه (﴿ذلك بأنهم…﴾) أو غايته (﴿ليجزي…﴾)
    explains = {}
    for k, v in enumerate(verses):
        if k and verses[k - 1]["s"] == v["s"]:
            if _is_cause(v["words"]):
                explains[f"{v['s']}:{v['a']}"] = "cause"
            elif v.get("start") == "purpose":
                explains[f"{v['s']}:{v['a']}"] = "purpose"
    result["explains"] = explains
    # الآيات التي هي حروف مقطعة أو تبدأ بها (وسم INL في بيانات الصرف): ﴿الم﴾، ﴿حم ۝ عسق﴾، ﴿ص والقرآن﴾
    result["initials"] = [f"{v['s']}:{v['a']}" for v in verses if v["words"] and v["words"][0]["initials"]]
    if clauses:
        # جمل الآية بحسب الوقف: "سورة:آية" -> [عدد كلمات الجمل قبل كل حدّ]، للآيات ذات أكثر من جملة
        result["waqf"] = {f"{v['s']}:{v['a']}": [end for _, end in spans[:-1]]
                          for v, spans in zip(verses, clauses) if len(spans) > 1}
    return result


def main():
    verses = parse_morphology(MORPH_FILE)
    print(f"عدد الآيات: {len(verses)}", file=sys.stderr)
    related = build_related(verses)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "quran.json"), "w", encoding="utf-8") as f:
        json.dump(build_quran(verses, load_clauses(verses)), f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(OUT_DIR, "related.json"), "w", encoding="utf-8") as f:
        json.dump(related, f, ensure_ascii=False, separators=(",", ":"))
    print("تم إنشاء web/data/quran.json و web/data/related.json", file=sys.stderr)


if __name__ == "__main__":
    main()
