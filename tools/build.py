"""بناء بيانات تطبيق «تفسير القرآن بالقرآن».

يقرأ ملف الصرف (Quranic Arabic Corpus) ويحسب لكل آية الآيات المرتبطة بها
اعتمادًا على مؤشرات من داخل القرآن فقط:
  1. الجذور واللمّات المشتركة (TF-IDF + تشابه جيب التمام)
  2. العبارات المتطابقة (n-grams بعد حذف التشكيل)
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
WEIGHTS = {"roots": 1.0, "phrase": 1.0, "context": 2.0}
# الخصائص الشائعة جدًا (مثل «قول» و«الله») لا تميّز بين الآيات
MAX_FEATURE_DF = 400
MAX_NGRAM_DF = 40
NGRAM_SIZES = (2, 3, 4)
MIN_ROOT_SCORE = 0.08

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
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            loc, form, _pos, tags = line.split("\t")
            s, a, w, _seg = (int(x) for x in loc.split(":"))
            words = verses.setdefault((s, a), {})
            word = words.setdefault(w, {"text": "", "root": None, "lemma": None})
            word["text"] += form
            parts = tags.split("|")
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
            "words": [
                {"text": words[w]["text"], "root": words[w]["root"], "lemma": words[w]["lemma"]}
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


# ---------- المؤشر 4: السياق والبيان الداخلي ----------

_ADRAKA = re.compile(r"(وما|ثمما)ادريك")
# رموز أسباب السياق (تُعرض نصوصها في الواجهة)
CONTEXT_ADRAKA = 1    # جواب ﴿وما أدراك﴾
CONTEXT_RELATIVE = 2  # صفة متصلة بالآية السابقة
_RELATIVE_START = ("الذين", "الذي", "التي", "اللذين")


def context_links(verses):
    """روابط من السياق المباشر: قواعد بسيطة على النص.

    - ﴿وما أدراك ما ...﴾ يُجاب عنها في الآية التالية التي ليس فيها «أدراك».
    - الآية التي تبدأ بـ«الذين/الذي» تصف كلمة في آخر الآية السابقة.
    """
    pos = {(v["s"], v["a"]): i for i, v in enumerate(verses)}
    links = defaultdict(dict)  # i -> {j: reason}

    def add(i, j, reason):
        links[i][j] = reason
        links[j].setdefault(i, reason)

    for i, v in enumerate(verses):
        flat = "".join(normalize(w["text"]) for w in v["words"])
        if _ADRAKA.search(flat):
            k = v["a"] + 1
            while (v["s"], k) in pos:
                j = pos[(v["s"], k)]
                nxt = "".join(normalize(w["text"]) for w in verses[j]["words"])
                if not _ADRAKA.search(nxt):
                    add(i, j, CONTEXT_ADRAKA)
                    break
                k += 1
        first = normalize(v["words"][0]["text"]) if v["words"] else ""
        if first in _RELATIVE_START and (v["s"], v["a"] - 1) in pos:
            add(pos[(v["s"], v["a"] - 1)], i, CONTEXT_RELATIVE)
    return links


# ---------- الجمع بين المؤشرات ----------

def shared_roots(vi, vj, idf, limit=3):
    ri = {w["root"] for w in vi["words"] if w["root"]}
    rj = {w["root"] for w in vj["words"] if w["root"]}
    common = sorted(ri & rj, key=lambda r: -idf.get("R:" + r, 0))
    return common[:limit]


def build_related(verses):
    roots, idf = root_similarity(verses)
    phrases, best_phrase = phrase_similarity(verses)
    context = context_links(verses)

    related = {}
    for i, v in enumerate(verses):
        candidates = set(roots[i]) | set(phrases[i]) | set(context.get(i, {}))
        ranked = []
        for j in candidates:
            r = roots[i].get(j, 0.0)
            p = phrases[i].get(j, 0.0)
            c = 1.0 if j in context.get(i, {}) else 0.0
            if r < MIN_ROOT_SCORE and p == 0 and c == 0:
                continue
            score = WEIGHTS["roots"] * r + WEIGHTS["phrase"] * p + WEIGHTS["context"] * c
            ranked.append((score, j, r, p, c))
        ranked.sort(key=lambda t: (-t[0], t[1]))

        # صيغة مختصرة لتصغير الملف:
        # [سورة، آية، الدرجة×100، رمز السياق، العبارة المشتركة، الجذور المشتركة]
        items = []
        for score, j, r, p, c in ranked[:TOP_K]:
            u = verses[j]
            roots_list = shared_roots(v, u, idf) if r >= MIN_ROOT_SCORE else []
            items.append([
                u["s"],
                u["a"],
                round(score * 100),
                context[i][j] if c else 0,
                best_phrase[i][j] if p else "",
                " ".join(roots_list),
            ])
        related[f"{v['s']}:{v['a']}"] = items
    return related


def build_quran(verses):
    surahs = []
    for v in verses:
        if v["s"] > len(surahs):
            surahs.append({"n": v["s"], "name": SURAH_NAMES[v["s"] - 1], "verses": []})
        surahs[-1]["verses"].append([[w["text"], w["root"] or "", w["lemma"] or ""] for w in v["words"]])
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
