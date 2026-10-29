"""مواضع الوقف في المصحف: تقسيم الآية إلى جملها.

علامات الوقف في مصحف المدينة (مجمع الملك فهد، رواية حفص) تفصل جمل الآية:
ۚ (الوقف جائز)، ۖ (الوصل أولى)، ۗ (الوقف أولى)، ۘ (الوقف لازم). أما ۛ (المعانقة) فيوقف عند
إحدى علامتيها لا كلتيهما، فلا تُعدّ حدًّا. يُكتب الناتج في data/waqf.tsv:
    سورة:آية <TAB> رقم آخر كلمة في كل جملة إلا الأخيرة (يبدأ العدّ من 1)
ولا يُحفظ نص المصحف نفسه، بل مواضع الوقف وحدها على كلمات بيانات الصرف.

الاستعمال:
    python3 tools/waqf.py           # ينزّل النص (نسخة ثابتة) ← data/waqf.tsv
    python3 tools/waqf.py FILE      # من نسخة محلية من الملف نفسه
"""

import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build  # noqa: E402

# نص مجمع الملك فهد (الإصدار 13) كما في fawazahmed0/quran-api (ملكية عامة، Unlicense)
SOURCE_URL = ("https://raw.githubusercontent.com/fawazahmed0/quran-api/"
              "1/editions/ara-quranuthmanihaf.json")
OUT_FILE = os.path.join(build.ROOT_DIR, "data", "waqf.tsv")

_STOP = re.compile("[ۖۗۘۚ]")
# في هذا النص تُفصل الألف أو الياء بعد تنوين الفتح المفتوح عن كلمتها: «هُدࣰ ى»
_DETACHED = re.compile("[اىي][ؐ-ًؚ-ٰٟۖ-ࣰۭ-ࣲ]*")


def words(text):
    out = []
    for token in text.replace("‏", "").split():
        if out and re.search("[ࣰ-ࣲ]$", out[-1]) and _DETACHED.fullmatch(token):
            out[-1] += token
        else:
            out.append(token)
    return out


def clause_ends(text, word_count):
    """أرقام آخر كلمة في كل جملة (إلا الأخيرة)، أو None إذا اختلف عدد الكلمات عن بيانات الصرف
    (سبع آيات فقط: «بعد ما» و«بعدما» ونحوها)."""
    tokens = words(text)
    if len(tokens) != word_count:
        return None
    return [k + 1 for k, t in enumerate(tokens[:-1]) if _STOP.search(t)]


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as f:
            data = json.load(f)
    else:
        with urllib.request.urlopen(SOURCE_URL) as r:
            data = json.load(r)
    counts = {(v["s"], v["a"]): len(v["words"]) for v in build.parse_morphology(build.MORPH_FILE)}
    lines, skipped = [], 0
    for v in data["quran"]:
        key = (v["chapter"], v["verse"])
        ends = clause_ends(v["text"], counts[key])
        if ends is None:
            skipped += 1
        elif ends:
            lines.append(f"{key[0]}:{key[1]}\t{','.join(map(str, ends))}")
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write("# مواضع الوقف (ۚ ۖ ۗ ۘ) من مصحف المدينة: سورة:آية <TAB> آخر كلمة في كل جملة إلا الأخيرة\n")
        f.write("\n".join(lines) + "\n")
    print(f"{len(lines)} آية فيها أكثر من جملة · {skipped} آيات لم تُقسَّم ← {OUT_FILE}", file=sys.stderr)


if __name__ == "__main__":
    main()
