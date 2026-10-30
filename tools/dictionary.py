"""معاني الألفاظ من «مختار الصحاح» للرازي: معجم لغة، لا تفسير.

لكل لفظ قرآني قليل الورود (غريب القرآن) يُؤخذ تعريفه على طريقة المعجم
(«الطُّور: الجبل»، «الثعبان: ضرب من الحيات»)، ويُحذف كل ما يعلّق على آية أو ينقل قولًا
(«وقوله تعالى…»، «قالوا…»، «قيل…») حتى لا يدخل تفسير. لا تُستعمل هذه المعاني في حساب
الروابط بين الآيات (جُرّب ذلك فلم يحسّن النتائج، انظر README)، بل تُعرض للقارئ عند النقر
على اللفظ، وكل كلمة من المعنى ترد في القرآن تفتح مواضعها فيه.

وللجذور الشائعة التي يحمل أصلها أكثر من معنى (كلم، ضرب، حيي…) تُعرض مادة المعجم كاملة بعد حذف
كل ما يعلّق على آية، في web/data/root_senses.json.

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
ROOTS_FILE = os.path.join(build.OUT_DIR, "root_senses.json")

# جذور شائعة يحمل أصلها أكثر من معنى («الكَلْم» في اللغة الجرح): تُعرض مادتها كاملة
ROOT_SENSES = ("كلم", "ضرب", "حيي", "كفر", "فسق", "نشز", "ضلل", "نسو", "نسأ")
# اسم المادة في المعجم إذا خالف جذر بيانات الصرف («ح ي و»)، أو أخطأ تحويل النص عنوانها
# («ك ل م» مكتوبة «ك م م»؛ ويُميَّز ما فيها بحروف الجذر، انظر root_entry)
DICT_ROOT = {"حيي": "حيو", "كلم": "كمم"}
MAX_ENTRY_CHARS = 700
MAX_CLAUSE_CHARS = 170
# في المادة الكاملة: ما بعد هذه الكلمات تعليق على آية أو قراءة أو حديث أو نبي، فيُقطع عندها
_VERSE_TALK = re.compile(r"(?:@QB@|@QE@|قوله|تعالى|قرأ|قراءة|قرئ|الحديث|في الآية|القرآن"
                         r"|عليه السلام|صلى الله|رضي الله|فسره|المفسر)")

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
    r"^(?:ب(?:فتح|ضم|كسر|سكون|تشديد)\s+\S+(?:\s+و(?:فتحها|ضمها|كسرها|سكونها))?|بوزن\s+\S+"
    r"|ب(?:فتحتين|ضمتين|التحريك|المد)|على\s+(?:وزن\s+)?فعي?ل)\s*")
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
        definition = clean(_SPELLING.sub("", " ".join(rest)))
        if definition and definition.split()[0] not in _NOT_MEANING and not _ABOUT_VERSES.search(definition):
            yield tokens[0], note, definition


# ما يُذكر قبل المعنى من ضبط اللفظ: «مكسور ممدود الدواء» ← «الدواء»
_LEADING = {"مكسور", "ممدود", "مقصور", "مفتوح", "مضموم", "مخففة", "مشددة", "مشدد", "بالمد", "بالقصر", "لغتان",
            "وسكونها", "وضمها", "وكسرها", "وفتحها", "وهو", "وهي", "مهموزا", "مهموز", "والتشديد", "والمد",
            "بالتشديد", "مخفف"}
# ما بعده تصريف أو جمع أو ضبط أو شاهد، لا معنى: «الحجة وقد برهن عليه» ← «الحجة»،
# «الحاجز بين الشيئين … » ، «ضد الجد وقد هزل من باب ضرب» ← «ضد الجد»
_GRAMMAR = re.compile(
    r"\s(?:وقد|من باب|فهو|فهي|والجمع|وجمعه|وجمعها|جمع|جمعها|جمعه|واحدها|وواحدها|واحدته|واحدتها|وبعضهم"
    r"|و(?:كسر|فتح|ضم)\s+ال\S+|بوزن|اسم ومصدر|وهو فعل"
    r"|(?:ال|وال)?واحد(?:ة)?(?=\s+\S)"
    r"|والاسم|والمصدر|مصدر|مصدره|والمرأة|بفتح|بضم|بكسر|بفتحتين|بضمتين|وسكونها|وبفتحها|وفتحها|وضمها|وكسرها"
    r"|ويجوز|وأنشد|ومنه|حديث|لغة في|وتصغيره|ويقال|يقال|تقول|وتقول|والفعل|وفعله|يذكر|ويؤنث|مؤنثة|وهي مؤنثة)(?=\s|$)")
# ما لا يُختم به المعنى إذا قُطع: «من الماء مثل» ← «من الماء»
_DANGLING = {"من", "في", "أي", "و", "على", "إلى", "عن", "مثل", "وهو", "وهي", "أو", "حتى", "إذا", "لأن", "ثم",
             "كما", "التي", "الذي", "بين", "إن", "أن", "ما", "لا", "قد", "كل", "هذا", "وكل", "وأما", "أما",
             "بمعنى", "ولا"}
# تعريف ليس معنى: «لا واحد لها من لفظها»، «توضع موضع المصدر»
_NOT_DEFINITION = re.compile(r"^(?:لا واحد|توضع|مصدر|لغة|اسم |ويقال|يقال|بمعنى$|في \S+$)")


def clean(definition):
    """المعنى وحده: بلا ضبط في أوله، ولا تصريف أو جمع بعده، في MAX_WORDS كلمات على الأكثر."""
    words = definition.split()
    while words and words[0] in _LEADING:
        words.pop(0)
    text = _GRAMMAR.split(" " + " ".join(words))[0].strip()
    # ﴿الإعلام وأذان الصلاة معروف﴾: ما قبل «معروف» إحالة لا معنى
    text = re.sub(r"\s+و\S+(?:\s+\S+)*?\s+معروف(?:\s.*)?$", "", text)
    words = text.split()[:MAX_WORDS]
    while words and words[-1] in _DANGLING:
        words.pop()
    text = " ".join(words)
    if _NOT_DEFINITION.match(text) or (len(words) == 1 and words[0].startswith("و")):
        return ""
    return text


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


def _subsequence(word, letters):
    it = iter(word)
    return all(ch in it for ch in letters)


def root_entry(text, root):
    """مادة الجذر في المعجم، جملةً جملة، بلا تعليق على آية: «ضرب في الأرض… أي سار لابتغاء الرزق»."""
    letters = build.normalize(root)[:2]
    parts = []
    for key, body in entries(text):
        if key != DICT_ROOT.get(root, root):
            continue
        for clause in re.split(r"\s+و\s+", body):
            kept = _VERSE_TALK.split(clause)[0]
            words = kept.split()
            # ما قُطع عنده التعليق: الكلمة المعطوفة قبله تابعة له («التكليم التجريح وعيسى…»)
            if kept != clause and words and words[-1].startswith("و"):
                words.pop()
            # وما بقي قبل الآية المحذوفة: «النسيان أيضا الترك قال الله ﴿…﴾»
            while words and (words[-1] in ("و", "أي", "يقال", "ويقال", "قال", "وقال", "ومنه")
                             or (words[-1] == "الله" and len(words) > 1 and words[-2] in ("قال", "وقال"))):
                words.pop()
            if len(words) < 2 or not any(_subsequence(build.normalize(w), letters) for w in words[:2]):
                continue
            text_ = " ".join(words)
            if len(text_) > MAX_CLAUSE_CHARS:
                text_ = text_[:MAX_CLAUSE_CHARS].rsplit(" ", 1)[0] + "…"
            if text_ not in parts:
                parts.append(text_)
    result, size = [], 0
    for part in parts:
        if size + len(part) > MAX_ENTRY_CHARS:
            break
        result.append(part)
        size += len(part)
    return result


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
    roots = {root: root_entry(text, root) for root in ROOT_SENSES}
    with open(ROOTS_FILE, "w", encoding="utf-8") as f:
        json.dump({k: v for k, v in roots.items() if v}, f, ensure_ascii=False, separators=(",", ":"))
    print(f"مواد {sum(1 for v in roots.values() if v)} جذرًا ← {ROOTS_FILE}", file=sys.stderr)


if __name__ == "__main__":
    main()
