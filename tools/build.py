"""بناء بيانات تطبيق «تفسير القرآن بالقرآن».

يقرأ ملف الصرف (Quranic Arabic Corpus) ويحسب لكل آية الآيات المرتبطة بها
اعتمادًا على مؤشرات من داخل القرآن فقط:
  1. الجذور واللمّات المشتركة (TF-IDF + تشابه جيب التمام)
  2. العبارات المتطابقة (n-grams بعد حذف التشكيل)
  3. التعبير المشترك بصيغ مختلفة (أزواج اللمّات المتقاربة)
  4. السياق والبيان الداخلي (قواعد على النص)

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
OUT_DIR = os.path.join(ROOT_DIR, "web", "data")

TOP_K = 10
WEIGHTS = {"roots": 1.0, "phrase": 1.0, "expression": 1.0, "context": 2.0}
# الخصائص الشائعة جدًا (مثل «قول» و«الله») لا تميّز بين الآيات
MAX_FEATURE_DF = 400
MAX_NGRAM_DF = 40
NGRAM_SIZES = (2, 3, 4)
MIN_ROOT_SCORE = 0.08
# أقصى مسافة بين كلمتي التعبير: ﴿أنعمتَ عليهم﴾ و﴿أنعم اللهُ عليهم﴾
EXPRESSION_GAP = 2

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


def parse_morphology(path):
    """يرجع قائمة الآيات مرتبة: كل آية فيها كلماتها مع الجذر واللمّة."""
    verses = {}
    questions = set()  # الآيات التي فيها أداة استفهام
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            loc, form, _pos, tags = line.split("\t")
            s, a, w, _seg = (int(x) for x in loc.split(":"))
            if "INTG" in tags.split("|"):
                questions.add((s, a))
            words = verses.setdefault((s, a), {})
            word = words.setdefault(w, {"text": "", "root": None, "lemma": None, "name": False})
            word["text"] += form
            parts = tags.split("|")
            if "PN" in parts:
                word["name"] = True  # اسم علم: موسى، فرعون، مكة…
            root = next((t[5:] for t in parts if t.startswith("ROOT:")), None)
            lemma = next((t[4:] for t in parts if t.startswith("LEM:")), None)
            if root:
                # الجزء الذي يحمل الجذر هو أصل الكلمة
                word["root"], word["lemma"] = root, lemma
            elif lemma and word["lemma"] is None and "PREF" not in parts:
                word["lemma"] = lemma
    result = []
    for (s, a) in sorted(verses):
        words = verses[(s, a)]
        result.append({
            "s": s,
            "a": a,
            "question": (s, a) in questions,
            "words": [
                {k: words[w][k] for k in ("text", "root", "lemma", "name")}
                for w in sorted(words)
            ],
        })
    return result


# ---------- المؤشر 1: الجذور واللمّات ----------

def root_features(verse):
    feats = defaultdict(float)
    for w in verse["words"]:
        if w["root"]:
            feats["R:" + w["root"]] += 1.0
            if w["lemma"]:
                feats["L:" + normalize(w["lemma"])] += 1.0
    return feats


def root_similarity(verses):
    """تشابه جيب التمام بين متجهات TF-IDF للجذور واللمّات."""
    n = len(verses)
    feats = [root_features(v) for v in verses]
    df = defaultdict(int)
    for f in feats:
        for k in f:
            df[k] += 1
    idf = {k: math.log(n / d) for k, d in df.items()}

    vectors = []
    for f in feats:
        vec = {k: (1 + math.log(tf)) * idf[k] for k, tf in f.items()}
        norm = math.sqrt(sum(x * x for x in vec.values())) or 1.0
        vectors.append({k: x / norm for k, x in vec.items()})

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


# ---------- المؤشر 2: العبارات المتطابقة ----------

def ngrams(tokens, size):
    return [(k, " ".join(tokens[k:k + size])) for k in range(len(tokens) - size + 1)]


def phrase_similarity(verses):
    """يجد العبارات (2 إلى 4 كلمات) المشتركة بين الآيات، والنادرة أهم."""
    n = len(verses)
    tokens = [[normalize(w["text"]) for w in v["words"]] for v in verses]
    content = [[w["root"] is not None for w in v["words"]] for v in verses]
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
                if ws[a]["root"] or ws[b]["root"]:
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
_ANSWER_TYPES = (CONTEXT_ADRAKA, CONTEXT_QUESTION, CONTEXT_DIALOGUE)
SHORT_QUESTION_WORDS = 5
_ANSWER_START = ("قال", "قالوا", "قل", "قالت")
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
    """
    pos = {(v["s"], v["a"]): i for i, v in enumerate(verses)}
    links = defaultdict(dict)  # i -> {j: reason}
    # اللوازم المتكررة (مثل ﴿فبأي آلاء ربكما تكذبان﴾) ليست أسئلة يُجاب عنها
    flats = ["".join(normalize(w["text"]) for w in v["words"]) for v in verses]
    repeats = defaultdict(int)
    for f in flats:
        repeats[f] += 1

    def add(i, j, reason):
        links[i][j] = reason
        links[j].setdefault(i, reason)

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
                    add(i, j, CONTEXT_ADRAKA)
                    break
                k += 1
        if (_QUESTION.search(flat) and len(v["words"]) <= QUESTION_MAX_WORDS
                and (v["s"], v["a"] + 1) in pos):
            add(i, pos[(v["s"], v["a"] + 1)], CONTEXT_QUESTION)
        first = normalize(v["words"][0]["text"]) if v["words"] else ""
        if first in _RELATIVE_START and (v["s"], v["a"] - 1) in pos:
            add(pos[(v["s"], v["a"] - 1)], i, CONTEXT_RELATIVE)
    return links


# ---------- الجمع بين المؤشرات ----------

def shared_roots(vi, vj, idf, limit=3):
    ri = {w["root"] for w in vi["words"] if w["root"]}
    rj = {w["root"] for w in vj["words"] if w["root"]}
    common = sorted(ri & rj, key=lambda r: (-idf.get("R:" + r, 0), r))
    return common[:limit]


def _context_reason(i, j, context, elsewhere, best_phrase, verses):
    if j in context.get(i, {}):
        return context[i][j]
    q = elsewhere[j][1]
    return [CONTEXT_ANSWER_ELSEWHERE, verses[q]["s"], verses[q]["a"], best_phrase[i][q]]


def build_related(verses):
    roots, idf = root_similarity(verses)
    phrases, best_phrase = phrase_similarity(verses)
    expressions, best_expr = expression_similarity(verses)
    context = context_links(verses)
    # سؤال ← جوابه (الجواب بعد السؤال دائمًا)
    answers = {
        q: a for q, links in context.items() for a, code in links.items()
        if code in _ANSWER_TYPES and a > q
    }

    related = {}
    for i, v in enumerate(verses):
        # إذا وردت عبارة الآية (مثل ﴿يوم الدين﴾) في آية سُئل فيها عنها،
        # فجواب ذلك السؤال يبيّن العبارة هنا أيضًا: ﴿مالك يوم الدين﴾ ← الانفطار 19
        elsewhere = {}
        for j, p in phrases[i].items():
            a = answers.get(j)
            if a is not None and a != i and a not in context.get(i, {}):
                if p > elsewhere.get(a, (0, None))[0]:
                    elsewhere[a] = (p, j)
        candidates = (set(roots[i]) | set(phrases[i]) | set(expressions[i])
                      | set(context.get(i, {})) | set(elsewhere))
        ranked = []
        for j in candidates:
            r = roots[i].get(j, 0.0)
            p = phrases[i].get(j, 0.0)
            # التعبير يُحسب فقط إذا لم تتطابق العبارة حرفيًا، حتى لا يُعدّ الشيء مرتين
            e = expressions[i].get(j, 0.0) if p == 0 else 0.0
            c = 1.0 if j in context.get(i, {}) else 0.0
            if not c and j in elsewhere:
                # بقدر تطابق العبارة مع آية السؤال
                c = elsewhere[j][0]
            if r < MIN_ROOT_SCORE and p == 0 and e == 0 and c == 0:
                continue
            score = (WEIGHTS["roots"] * r + WEIGHTS["phrase"] * p
                     + WEIGHTS["expression"] * e + WEIGHTS["context"] * c)
            ranked.append((score, j, r, p, e, c))
        ranked.sort(key=lambda t: (-t[0], t[1]))

        # صيغة مختصرة لتصغير الملف:
        # [سورة، آية، الدرجة×100، سبب السياق، العبارة المشتركة، الجذور المشتركة، التعبير المشترك]
        # سبب السياق: رمز، أو [5، سورة السؤال، آيته، العبارة] للجواب في موضع آخر
        items = []
        for score, j, r, p, e, c in ranked[:TOP_K]:
            u = verses[j]
            roots_list = shared_roots(v, u, idf) if r >= MIN_ROOT_SCORE else []
            items.append([
                u["s"],
                u["a"],
                round(score * 100),
                _context_reason(i, j, context, elsewhere, best_phrase, verses) if c else 0,
                best_phrase[i][j] if p else "",
                " ".join(roots_list),
                best_expr[i][j] if e else "",
            ])
        related[f"{v['s']}:{v['a']}"] = items
    return related


def build_quran(verses):
    surahs = []
    for v in verses:
        if v["s"] > len(surahs):
            surahs.append({"n": v["s"], "name": SURAH_NAMES[v["s"] - 1], "verses": []})
        # كل كلمة: [النص، الجذر، اللمّة] ويُضاف 1 لاسم العلم
        surahs[-1]["verses"].append([
            [w["text"], w["root"] or "", w["lemma"] or ""] + ([1] if w["name"] else [])
            for w in v["words"]
        ])
    return {"surahs": surahs}


def main():
    verses = parse_morphology(MORPH_FILE)
    print(f"عدد الآيات: {len(verses)}", file=sys.stderr)
    related = build_related(verses)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "quran.json"), "w", encoding="utf-8") as f:
        json.dump(build_quran(verses), f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(OUT_DIR, "related.json"), "w", encoding="utf-8") as f:
        json.dump(related, f, ensure_ascii=False, separators=(",", ":"))
    print("تم إنشاء web/data/quran.json و web/data/related.json", file=sys.stderr)


if __name__ == "__main__":
    main()
