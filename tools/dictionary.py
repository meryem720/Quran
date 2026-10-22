"""معاني الألفاظ من «مختار الصحاح» للرازي: معجم لغة، لا تفسير.

لكل لفظ قرآني قليل الورود (غريب القرآن) يُؤخذ تعريفه على طريقة المعجم
(«الطُّور: الجبل»، «الثعبان: ضرب من الحيات»)، ويُحذف كل ما يعلّق على آية أو ينقل قولًا
(«وقوله تعالى…»، «قالوا…»، «قيل…») حتى لا يدخل تفسير. لا تُستعمل هذه المعاني في حساب
الروابط بين الآيات (جُرّب ذلك فلم يحسّن النتائج، انظر README)، بل تُعرض للقارئ عند النقر
على اللفظ، وكل كلمة من المعنى ترد في القرآن تفتح مواضعها فيه.

الاستعمال:
    python3 tools/dictionary.py           # ينزّل نص المعجم (نسخة ثابتة) ← web/data/glosses.json
    python3 tools/dictionary.py FILE      # من نسخة محلية من الملف نفسه
"""

import json
import os
import re
import sys
import urllib.request
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build  # noqa: E402

# نسخة ثابتة من نص OpenITI (تحقيق محمود خاطر، مكتبة لبنان 1995)
SOURCE_URL = (
    "https://raw.githubusercontent.com/OpenITI/0675AH/4b1d2886508b435eb0377ccab96e1da96cc8ee0a/"
    "data/0666IbnAbiBakrZaynDinRazi/0666IbnAbiBakrZaynDinRazi.MukhtarSihah/"
    "0666IbnAbiBakrZaynDinRazi.MukhtarSihah.JK000107-ara1"
)
OUT_FILE = os.path.join(build.OUT_DIR, "glosses.json")

# غريب القرآن: الألفاظ التي لا ترد إلا في هذا العدد من الآيات أو أقل
MAX_VERSES = 20
MAX_SENSES = 3
MAX_WORDS = 8

# ما بعد هذه الكلمات تعليق على آية أو نقل لقول أو قراءة أو تصريف، لا تعريف للفظ
_COMMENTARY = re.compile(
    r"\s(?:و?قوله|تعالى|@QB@|@QE@|و?قالوا|و?قيل|و?قال|قلت|و?يقال|الحديث|و?منه|وفي"
    r"|و?قرأ|و?قرئ|و?فسره|وجمعه|وجمعها|والجمع|وبابه|وتصغيره|يذكر|ويؤنث)(?=\s|$)"
)
# تعريف يذكر الآية أو القرآن أو تفسيرًا: يُترك كله («المثاني: من القرآن…» قول في تفسير آية)
_ABOUT_VERSES = re.compile(r"الآية|القرآن|تفسير|المفسر|يعني")
# ما ليس معنى: إحالة أو تصريف («الميزان معروف»، «الكبرى تأنيث الأكبر»)
_NOT_MEANING = {"مثله", "معروف", "تأنيث", "واحدة", "واحد", "جمع", "تقال", "يقال", "اسم"}
# ضبط بالوصف في أول التعريف («بضم الشين وكسرها اللهب…»): يُحذف ويبقى المعنى
_SPELLING = re.compile(
    r"^(?:ب(?:فتح|ضم|كسر)\s+\S+(?:\s+و(?:فتحها|ضمها|كسرها))?|بوزن\s+\S+|ب(?:فتحتين|ضمتين|التحريك|المد))\s*")
# ضبط اللفظ كما يذكره المعجم، يقابَل بلمّة القرآن
_NOTES = {"بالفتح": "َ", "بالضم": "ُ", "بالكسر": "ِ", "بالتشديد": "ّ"}
_FILLERS = {"أيضا", "ايضا"}


def entries(text):
    """مواد المعجم: [(الجذر، نص المادة)]. المادة تبدأ بسطر «# ط و ر» وتتصل أسطرها بـ«~~»."""
    body = text.split("#META#Header#End#", 1)[-1]
    body = re.sub(r"\n~~", " ", body)
    body = re.sub(r"\bms\d+\b|PageV\d+P\d+", " ", body)
    result = []
    for line in body.split("\n"):
        m = re.match(r"^# ((?:\S ){1,4})(.*)$", line)
        if m and all(len(t) == 1 for t in m.group(1).split()):
            result.append((m.group(1).replace(" ", ""), m.group(2)))
    return result


def senses(body):
    """تعريفات المادة: [(اللفظ المعرَّف، ضبطه أو None، التعريف)].

    على طريقة المعجم: «و الطور الجبل» ← (الطور، الجبل). يُقطع التعريف عند أول تعليق.
    """
    for clause in re.split(r"\s+و\s+", " " + body):
        clause = _COMMENTARY.split(" " + clause)[0]
        tokens = clause.split()
        if len(tokens) < 2 or not tokens[0].startswith("ال"):
            continue
        rest = tokens[1:]
        note = rest[0] if rest[0] in _NOTES else None
        rest = [t for t in rest if t not in _NOTES and t not in _FILLERS]
        definition = _SPELLING.sub("", " ".join(rest[:MAX_WORDS]))
        if definition and definition.split()[0] not in _NOT_MEANING and not _ABOUT_VERSES.search(definition):
            yield tokens[0], note, definition


def _agrees(note, lemma):
    """الضبط المذكور في المعجم يوافق لمّة القرآن؟ («الخِير بالكسر» غير «الخَير»)."""
    if note == "بالتشديد":
        return "ّ" in lemma
    m = re.search("[َُِ]", re.sub("^ٱ?ل", "", lemma)[:3])
    return m is None or m.group(0) == _NOTES[note]


def build_glosses(text, verses):
    """{لمّة: {"h": اللفظ في المعجم، "d": [تعريفات]}} للألفاظ القليلة الورود."""
    verse_count = defaultdict(set)
    vocalized = defaultdict(set)
    for i, v in enumerate(verses):
        for w in v["words"]:
            if w["root"] and w["lemma"]:
                key = build.normalize(w["lemma"])
                verse_count[key].add(i)
                vocalized[key].add(w["lemma"])
    glosses = {}
    for _root, body in entries(text):
        for head, note, definition in senses(body):
            word = build.normalize(head)[2:]
            key = word if word in vocalized else (word[:-2] + "ه" if word.endswith("ات") else None)
            if key not in vocalized or len(verse_count[key]) > MAX_VERSES:
                continue
            # ألفاظ مختلفة تُكتب كتابة واحدة بلا تشكيل (سُنّة، سَنة، سِنة): المعجم غير مشكول
            # فلا يُعرف أيها المقصود، فلا يُعرض لها معنى
            if len(vocalized[key]) > 1:
                continue
            if note and not _agrees(note, next(iter(vocalized[key]))):
                continue
            entry = glosses.setdefault(key, {"h": head, "d": []})
            if definition not in entry["d"] and len(entry["d"]) < MAX_SENSES:
                entry["d"].append(definition)
    return glosses


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as f:
            text = f.read()
    else:
        with urllib.request.urlopen(SOURCE_URL) as r:
            text = r.read().decode("utf-8")
    glosses = build_glosses(text, build.parse_morphology(build.MORPH_FILE))
    os.makedirs(build.OUT_DIR, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(glosses, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    print(f"معاني {len(glosses)} لفظًا ← {OUT_FILE}", file=sys.stderr)


if __name__ == "__main__":
    main()
