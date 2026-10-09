"""تقييم الخوارزمية على أمثلة معروفة يفسّر فيها القرآنُ القرآنَ.

الاستعمال (بعد build.py):
    python3 tools/evaluate.py
"""

import json
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELATED_FILE = os.path.join(ROOT_DIR, "web", "data", "related.json")

# (الآية، الآية التي تبيّنها، الوصف)
GOLD = [
    ("86:2", "86:3", "الطارق ← النجم الثاقب"),
    ("101:3", "101:4", "القارعة ← يوم يكون الناس كالفراش المبثوث"),
    ("82:17", "82:19", "يوم الدين ← يوم لا تملك نفس لنفس شيئا"),
    ("97:2", "97:3", "ليلة القدر ← خير من ألف شهر"),
    ("104:5", "104:6", "الحطمة ← نار الله الموقدة"),
    ("90:12", "90:13", "العقبة ← فك رقبة"),
    ("10:62", "10:63", "أولياء الله ← الذين آمنوا وكانوا يتقون"),
    ("2:2", "2:3", "المتقين ← الذين يؤمنون بالغيب"),
    ("1:7", "4:69", "الذين أنعمت عليهم ← النبيين والصديقين"),
    ("44:3", "97:1", "ليلة مباركة ← ليلة القدر"),
    ("2:37", "7:23", "كلمات آدم ← ربنا ظلمنا أنفسنا"),
    ("5:1", "5:3", "إلا ما يتلى عليكم ← حرمت عليكم الميتة"),
    ("16:118", "6:146", "ما قصصنا عليك من قبل ← وعلى الذين هادوا حرمنا"),
    ("4:140", "6:68", "وقد نزل عليكم في الكتاب ← فأعرض عنهم"),
    ("6:82", "31:13", "بظلم ← إن الشرك لظلم عظيم"),
]


def main():
    with open(RELATED_FILE, encoding="utf-8") as f:
        related = json.load(f)
    found = 0
    for src, dst, label in GOLD:
        ids = [f"{r[0]}:{r[1]}" for r in related.get(src, [])]
        rank = ids.index(dst) + 1 if dst in ids else None
        found += rank is not None
        mark = f"✓ المرتبة {rank}" if rank else "✗ غير موجودة"
        print(f"{src:>7} → {dst:<7} {mark:<14} {label}")
    print(f"\nالنتيجة: {found}/{len(GOLD)} ضمن أعلى {len(next(iter(related.values())))} نتائج")
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main())
