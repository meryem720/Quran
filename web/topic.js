/* محرّك الموضوعات: يجمع آيات موضوع (الصلاة، الزكاة، موسى…) ويستخرج خلاصته
 * من ألفاظ الآيات نفسها، دون أي مصدر خارجي.
 *
 * يعمل في المتصفح (QuranTopic) وفي Node (require) للاختبار.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.QuranTopic = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // ---------- توحيد الكتابة ----------

  // نفس التوحيد المستعمل في tools/build.py
  const DIACRITICS = /[ؐ-ًؚ-ٰٟۖ-ۭـ]/g;
  const LETTER_MAP = { "ٱ": "ا", "أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ئ": "ي", "ؤ": "و", "ة": "ه" };
  const LETTERS = /[ٱأإآىئؤة]/g;

  function normalize(text) {
    return text.replace(DIACRITICS, "").replace(LETTERS, (c) => LETTER_MAP[c]).replace(/\s+/g, "");
  }

  // للبحث فقط: نحذف الهمزة المفردة أيضًا، فـ«القرآن» تطابق لمّة «قُرْءَان»
  function searchKey(text) {
    return normalize(text).replace(/ء/g, "");
  }

  // الكلمة القرآنية كما يكتبها المستخدم بالإملاء الحديث: الألف الخنجرية (ٰ) ألف،
  // والياء الصغيرة (ۦ ۧ) ياء: ﴿ٱلصَّٰبِرِينَ﴾ ← «الصابرين»، ﴿ٱلْيَتَٰمَىٰ﴾ ← «اليتامى»
  function spellingKey(text) {
    return searchKey(text.replace(/([ىي])ٰ/g, "$1").replace(/ٰ/g, "ا").replace(/[ۦۧ]/g, "ي"));
  }

  // مفتاح الصيغة المتكررة: يبقي حركات الكلمة الداخلية (فـ﴿وَءَاتُوا۟﴾ أمر غير ﴿وَءَاتَوُا۟﴾ ماضٍ)
  // ويحذف علامات التلاوة والشدة والسكون وحركة آخر الكلمة (﴿ٱلصَّلَوٰةَ﴾ و﴿ٱلصَّلَوٰةِ﴾ واحدة)
  function formulaKey(text) {
    return text
      .replace(/[ؐ-ؚـّ-ٕٟۖ-ۭ]/g, "")
      .replace(LETTERS, (c) => LETTER_MAP[c])
      .replace(/[ً-ِٰ]+$/, "");
  }

  // للعرض: اللمّة بلا حركات تُقرأ أيسر في العناوين (يُحافِظُ ← يحافظ)
  function plain(text) {
    return text.replace(DIACRITICS, "");
  }

  // صيغ ما يكتبه المستخدم: الكلمة كما هي أولًا، ثم دون «ال» وما يسبقها
  const ARTICLE_PREFIXES = ["وال", "فال", "بال", "كال", "ال", "لل"];
  function queryVariants(word) {
    const q = searchKey(word);
    const out = [q];
    for (const prefix of ARTICLE_PREFIXES) {
      if (q.startsWith(prefix) && q.length - prefix.length >= 2) out.push(q.slice(prefix.length));
    }
    return [...new Set(out)].filter((v) => v.length >= 2);
  }

  // ما يتصل بأول الكلمة من حروف: ﴿وَٱلصَّٰبِرِينَ﴾، ﴿فَٱصْبِرْ﴾، ﴿لِلْيَتَٰمَىٰ﴾
  const CLITICS = ["", "و", "ف", "ب", "ل", "ك", "س", "وب", "ول", "وك", "وس", "فب", "فل", "فس", "لل", "ولل", "فلل"];

  function matchesWithClitic(form, variant) {
    if (!form.endsWith(variant)) return false;
    return CLITICS.includes(form.slice(0, form.length - variant.length));
  }

  // ---------- معجم صغير ----------

  // جذور كل ألفاظها في القرآن بمعنى واحد (تُحقِّق منها لمّةً لمّة)، فتُجمع كلها تلقائيًا:
  // «التوبة» تشمل ﴿تاب﴾ و﴿التواب﴾، و«الصيام» تشمل ﴿فليصمه﴾ و﴿الصائمين﴾.
  // لا تُضاف جذور فيها معانٍ مختلفة: رحم (أرحام)، كفر (كافور)، هدي (هدية)، ظلم (ظلمة)، سجد (مسجد).
  const WHOLE_ROOTS = new Set(["صبر", "توب", "صوم", "شكر", "غفر", "خشع", "رزق"]);

  // لمّة هي قراءة أخرى للفظ نفسه، لا معنى آخر: ﴿حِجُّ ٱلْبَيْتِ﴾ (آل عمران 97) = حَجّ
  const SAME_WORD = new Set(["حِجّ"].map((x) => x.normalize("NFC")));

  // ألفاظ لها جذر لكنها تعمل عمل الأدوات (نداء ﴿يا أيها﴾، ظروف، «كل»، «بعض»، «شيء»):
  // لا تُعدّ «مقترنة» بموضوع ولا عنوانًا لمحور
  const FUNCTION_LEMMAS = new Set([
    "أَيّ", "عِند", "بَيْن", "كُلّ", "كُلَّما", "بَعْض", "غَيْر", "دُون", "قَبْل", "بَعْد",
    "شَىْء", "مِثْل", "فَوْق", "تَحْت", "أَحَد", "إِحْدَى",
  ].map((x) => x.normalize("NFC")));

  // ---------- العربية: صيغة المعدود ----------

  // n مع المعدود. kase: "gen" للجر والنصب (في آيتين)، "nom" للرفع (آيتان)
  const NOUNS = {
    ayah: { one: "آية واحدة", two: ["آيتين", "آيتان"], plural: "آيات", single: "آية" },
    surah: { one: "سورة واحدة", two: ["سورتين", "سورتان"], plural: "سور", single: "سورة" },
    axis: { one: "محور واحد", two: ["محورين", "محوران"], plural: "محاور", single: "محورًا" },
  };

  function countAr(n, kind, kase = "gen") {
    const f = NOUNS[kind];
    if (n === 1) return f.one;
    if (n === 2) return f.two[kase === "nom" ? 1 : 0];
    const r = n % 100;
    if (r >= 3 && r <= 10) return `${n} ${f.plural}`;
    return `${n} ${kind === "axis" && (r === 0 || r === 1 || r === 2) ? "محور" : f.single}`;
  }

  // ---------- الفهرس ----------

  const MAX_COOCCUR = 8;
  const MAX_FORMULAS = 5;
  const FORMULA_MAX_WORDS = 10;
  const MAX_CLUSTER_VERSES = 600;
  const CLUSTER_THRESHOLD = 0.12;
  const CONTEXT_GAP = 10;
  // لفظ يرد في أكثر من 10% من آيات القرآن عامّ لا يميّز موضوعًا (الله، قال، كان، رب…)
  const GENERIC_SHARE = 0.1;

  /**
   * quran: {surahs: [{n, name, verses: [[[نص، جذر، لمّة، اسم_علم؟], ...], ...]}], verbs: [لمّات]}
   */
  function buildIndex(quran) {
    const surahs = quran.surahs || quran;
    const verbs = new Set(quran.verbs || []);
    const verses = [];
    // اللمّة تُعرَّف بنصها المشكول، فـ«آتَى» (أعطى) غير «أَتَى» (جاء)
    const lemmas = new Map(); // لمّة -> {key, display, root, name, verb, verses, forms}
    const byKey = new Map(); // مفتاح البحث (بلا تشكيل ولا همزات) -> Set(لمّات)
    const rootLemmas = new Map(); // جذر -> Set(لمّات)

    for (const surah of surahs) {
      surah.verses.forEach((words, i) => {
        const idx = verses.length;
        const keys = new Set();
        const lemmaCount = new Map(); // كل لمّة ذات جذر أو اسم علم -> عدد ورودها
        const tokens = [];
        const spellings = [];
        for (const [text, rootStr, lemma, isName] of words) {
          tokens.push(normalize(text));
          spellings.push([searchKey(text), spellingKey(text)]);
          if (!lemma) continue;
          keys.add(lemma);
          let info = lemmas.get(lemma);
          if (!info) {
            info = {
              key: lemma, display: lemma, root: rootStr || "", name: !!isName,
              verb: verbs.has(lemma), verses: [], forms: new Set(),
              function: FUNCTION_LEMMAS.has(lemma.normalize("NFC")),
            };
            lemmas.set(lemma, info);
            const sk = searchKey(lemma);
            if (!byKey.has(sk)) byKey.set(sk, new Set());
            byKey.get(sk).add(lemma);
          }
          info.forms.add(searchKey(text));
          if (rootStr && !info.root) info.root = rootStr;
          if (isName) info.name = true;
          if (rootStr || isName) lemmaCount.set(lemma, (lemmaCount.get(lemma) || 0) + 1);
          if (rootStr) {
            if (!rootLemmas.has(rootStr)) rootLemmas.set(rootStr, new Set());
            rootLemmas.get(rootStr).add(lemma);
          }
        }
        for (const key of keys) lemmas.get(key).verses.push(idx);
        verses.push({ s: surah.n, a: i + 1, surahName: surah.name, words, tokens, spellings, keys, lemmaCount });
      });
    }

    const idf = new Map();
    for (const [key, info] of lemmas) {
      idf.set(key, Math.log(verses.length / info.verses.length));
      info.generic = info.verses.length > verses.length * GENERIC_SHARE;
    }
    // الألفاظ ذات المعنى في كل آية: لها جذر أو اسم علم، وليست أداة ولا عامة جدًا
    for (const v of verses) {
      v.content = new Map([...v.lemmaCount].filter(([k]) => !lemmas.get(k).function && !lemmas.get(k).generic));
    }
    return { verses, lemmas, byKey, rootLemmas, idf };
  }

  // اللفظ يصلح موضوعًا: له جذر أو اسم علم، وليس أداة
  function isTopical(index, key) {
    const info = index.lemmas.get(key);
    return (info.root || info.name) && !info.function;
  }

  // ---------- فهم السؤال ----------

  /**
   * يحوّل كلمة واحدة إلى لمّات. يرجع {selected، alternatives، siblings، suggestions}:
   *   selected: ما يُقصد غالبًا؛ alternatives: معانٍ أخرى للكتابة نفسها (﴿الجنة﴾: جِنَّة، جُنَّة؛
   *   ﴿يصلون﴾: وَصَل)؛ siblings: بقية الجذر؛ suggestions: لمّات قريبة الكتابة إذا لم يُعثر على شيء.
   */
  function resolveWord(index, word) {
    const variants = queryVariants(word);
    let selected = [];
    let alternatives = [];
    const byFreq = (x, y) => index.lemmas.get(y).verses.length - index.lemmas.get(x).verses.length;

    // 1) لمّة مكتوبة كما كتبها المستخدم. الكلمة كاملة أولًا ثم دون «ال»، حتى لا تصير
    //    «والدين» «دين»
    for (const v of variants) {
      selected = [...(index.byKey.get(v) || [])].filter((k) => isTopical(index, k));
      if (selected.length) break;
    }

    // 2) صيغة جمع أو فعل (﴿الصابرين﴾، ﴿يصلون﴾، ﴿اليتامى﴾): لمّات الكلمات المكتوبة هكذا في المصحف
    if (!selected.length) {
      for (const v of variants) {
        const counts = new Map();
        for (const verse of index.verses) {
          verse.spellings.forEach((forms, k) => {
            if (!forms.some((f) => matchesWithClitic(f, v))) return;
            const lemma = verse.words[k][2];
            if (lemma && isTopical(index, lemma)) counts.set(lemma, (counts.get(lemma) || 0) + 1);
          });
        }
        if (counts.size) {
          const ranked = [...counts.entries()].sort((x, y) => y[1] - x[1]).map(([k]) => k);
          selected = [ranked[0]];
          alternatives = ranked.slice(1, 6);
          break;
        }
      }
    }

    // 2ب) جمع تكسير يختلف عن مفرده في الألف: «المناسك» ← مَنسَك، «المساجد» ← مَسْجِد
    if (!selected.length) {
      const noAlef = (x) => x.replace(/ا/g, "");
      for (const v of variants) {
        if (noAlef(v).length < 3) continue;
        const hits = [...index.lemmas.values()]
          .filter((info) => isTopical(index, info.key) && noAlef(searchKey(info.key)) === noAlef(v))
          .sort((x, y) => y.verses.length - x.verses.length)
          .map((info) => info.key);
        if (hits.length) {
          selected = [hits[0]];
          alternatives = hits.slice(1, 6);
          break;
        }
      }
    }

    // 3) أسماء تتفق كتابتها وتختلف معانيها (جَنَّة، جِنَّة، جُنَّة): الأكثر ورودًا هو المختار،
    //    والباقي معانٍ أخرى. الفعل والاسم معًا (صَبَرَ، صَبْر) يبقيان مختارين.
    const nouns = selected.filter((k) => !index.lemmas.get(k).verb && !SAME_WORD.has(k.normalize("NFC"))).sort(byFreq);
    if (nouns.length > 1) {
      const others = nouns.slice(1);
      selected = selected.filter((k) => !others.includes(k));
      alternatives = [...others, ...alternatives.filter((k) => !others.includes(k))];
    }

    // 4) لمّة من الجذر نفسه كل صيغها هي ما كتبه المستخدم بحروفه (﴿رِبًا﴾ في الروم 39 لمّتها «رِب»)
    const typed = new Set(variants);
    for (const key of [...selected]) {
      const r = index.lemmas.get(key).root;
      if (!r) continue;
      for (const k of index.rootLemmas.get(r)) {
        const forms = index.lemmas.get(k).forms;
        if (!selected.includes(k) && !alternatives.includes(k) && forms.size && [...forms].every((f) => [...typed].some((t) => matchesWithClitic(f, t)))) {
          selected.push(k);
        }
      }
    }

    // 5) جذر كل ألفاظه بمعنى واحد: يُجمع كله
    for (const key of [...selected]) {
      const r = index.lemmas.get(key).root;
      if (WHOLE_ROOTS.has(r)) {
        for (const k of [...index.rootLemmas.get(r)].sort(byFreq)) if (!selected.includes(k)) selected.push(k);
      }
    }
    alternatives = alternatives.filter((k) => !selected.includes(k));

    const taken = new Set([...selected, ...alternatives]);
    const siblings = [];
    for (const key of selected) {
      const r = index.lemmas.get(key).root;
      if (!r) continue;
      for (const k of index.rootLemmas.get(r)) if (!taken.has(k) && !siblings.includes(k)) siblings.push(k);
    }
    siblings.sort(byFreq);

    let suggestions = [];
    if (!selected.length) {
      const q = variants[variants.length - 1] || "";
      const noAlef = (x) => x.replace(/ا/g, "");
      if (q.length >= 2) {
        suggestions = [...index.lemmas.values()]
          .filter((info) => isTopical(index, info.key))
          .filter((info) => {
            const k = searchKey(info.key);
            // «المناسك» ← مَنسَك: جمع التكسير يختلف عن مفرده في الألف غالبًا
            return k.includes(q) || (k.length >= 3 && noAlef(k) === noAlef(q));
          })
          .sort((x, y) => y.verses.length - x.verses.length)
          .slice(0, 12)
          .map((info) => info.key);
      }
    }
    return { selected, alternatives, siblings, suggestions };
  }

  /**
   * يفهم ما كتبه المستخدم: كلمة (الصلاة) أو عبارة (يوم القيامة، بني إسرائيل).
   * في العبارة: phrase = [لمّات كل كلمة]، والآيات هي التي تتتابع فيها الكلمات.
   */
  function resolveQuery(index, query) {
    const words = query.replace(/[^\p{L}\p{M}\s]/gu, " ").trim().split(/\s+/).filter(Boolean);
    if (words.length <= 1) return { ...resolveWord(index, words[0] || ""), phrase: null, missing: [] };

    const parts = words.map((w) => ({ word: w, ...resolveWord(index, w) }));
    const missing = parts.filter((p) => !p.selected.length).map((p) => p.word);
    // في العبارة يكفي تتابع الكلمات للتمييز، فتُقبل كل معاني الكتابة:
    // ﴿لَيْلَةِ ٱلْقَدْرِ﴾ لمّتها قَدْر لا قَدَر
    const phrase = missing.length ? null : parts.map((p) => [...p.selected, ...p.alternatives]);
    return {
      selected: phrase ? [...new Set(phrase.flat())] : [],
      alternatives: [], siblings: [], suggestions: [],
      phrase, missing,
    };
  }

  // ---------- آيات الموضوع ----------

  function topicVerses(index, keys) {
    const set = new Set();
    for (const key of keys) {
      const info = index.lemmas.get(key);
      if (info) info.verses.forEach((i) => set.add(i));
    }
    return [...set].sort((x, y) => x - y);
  }

  // آيات تتتابع فيها كلمات العبارة: ﴿يَوْمَ ٱلْقِيَٰمَةِ﴾
  function phraseVerses(index, phrase) {
    const sets = phrase.map((keys) => new Set(keys));
    const first = topicVerses(index, phrase[0]);
    return first.filter((i) => {
      const lem = index.verses[i].words.map((w) => w[2]);
      for (let k = 0; k + sets.length <= lem.length; k++) {
        if (sets.every((set, j) => set.has(lem[k + j]))) return true;
      }
      return false;
    });
  }

  // آيات السياق: ما بين موضعين متقاربين من السورة نفسها (لقصة تذكر صاحبها في أولها وآخرها)
  function contextVerses(index, idxs) {
    const set = new Set(idxs);
    const out = [];
    for (let k = 0; k + 1 < idxs.length; k++) {
      const a = idxs[k];
      const b = idxs[k + 1];
      if (index.verses[a].s !== index.verses[b].s) continue;
      const gap = b - a - 1;
      if (gap > 0 && gap <= CONTEXT_GAP) for (let i = a + 1; i < b; i++) if (!set.has(i)) out.push(i);
    }
    return out;
  }

  // ---------- الخلاصة ----------

  // متجه TF-IDF للآية من ألفاظها ذات المعنى، دون ألفاظ الموضوع نفسه
  function verseVector(index, v, exclude) {
    const vec = new Map();
    let norm = 0;
    for (const [key, tf] of v.content) {
      if (exclude.has(key)) continue;
      const w = (1 + Math.log(tf)) * index.idf.get(key);
      vec.set(key, w);
      norm += w * w;
    }
    norm = Math.sqrt(norm) || 1;
    for (const [k, w] of vec) vec.set(k, w / norm);
    return vec;
  }

  // مجموع المتجهات: مجموع تشابه آية مع آيات مجموعة = حاصل ضربها في هذا المجموع
  // (المتجهات موحّدة الطول)، فيُحسب في خطوة واحدة بدل المقارنة الثنائية
  function sumVectors(vectors) {
    const total = new Map();
    for (const v of vectors) for (const [k, w] of v) total.set(k, (total.get(k) || 0) + w);
    return total;
  }

  function cosine(a, b) {
    if (a.size > b.size) [a, b] = [b, a];
    let s = 0;
    for (const [k, w] of a) {
      const x = b.get(k);
      if (x) s += w * x;
    }
    return s;
  }

  // ما يقترن بالموضوع: ألفاظ تكثر في آياته أكثر مما تكثر في القرآن عامة
  function cooccurrences(index, idxs, exclude) {
    const n = idxs.length;
    const total = index.verses.length;
    const counts = new Map();
    for (const i of idxs) {
      for (const key of index.verses[i].content.keys()) {
        if (!exclude.has(key)) counts.set(key, (counts.get(key) || 0) + 1);
      }
    }
    // في الموضوع الصغير لا يكفي تكرار مرتين ليكون اقترانًا
    const minCount = n < 10 ? 2 : n < 30 ? 3 : Math.max(3, Math.ceil(n * 0.04));
    const out = [];
    for (const [key, c] of counts) {
      if (c < minCount) continue;
      const lift = (c / n) / (index.lemmas.get(key).verses.length / total);
      if (lift < 2) continue;
      out.push({ key, count: c, score: c * Math.log(lift) });
    }
    out.sort((x, y) => y.score - x.score || y.count - x.count);
    return out.slice(0, MAX_COOCCUR).map((o) => ({
      key: o.key,
      display: index.lemmas.get(o.key).display,
      count: o.count,
      score: o.score,
      example: idxs.find((i) => index.verses[i].content.has(o.key)),
    }));
  }

  // الصيغ المتكررة: أطول عبارة فيها لفظ الموضوع وتتكرر في آيات منه
  function formulas(index, idxs, keys) {
    // كلمة العبارة: لفظ الموضوع واسم العلم بلمّته (﴿إِبْرَٰهِيمَ﴾ و﴿إِبْرَٰهِـۧمَ﴾ واحد)، والباقي بصيغته
    const wordKey = (w, first) => {
      if (w[2] && (keys.has(w[2]) || w[3])) return "@" + w[2];
      const k = formulaKey(w[0]);
      // و/ف في أول العبارة لا تغيّرها: ﴿وَأَقِيمُوا﴾ = ﴿أَقِيمُوا﴾
      return first ? k.replace(/^[وف]َ/, "") : k;
    };
    const found = new Map(); // مفتاح -> {size, verses: Set, texts: Map(نص -> عدد)}
    for (const i of idxs) {
      const words = index.verses[i].words;
      const wk = words.map((w) => wordKey(w, false));
      for (let k = 0; k < words.length; k++) {
        for (let size = 2; size <= FORMULA_MAX_WORDS && k + size <= words.length; size++) {
          const span = words.slice(k, k + size);
          if (!span.some((w) => keys.has(w[2]))) continue;
          // فيها لفظ ذو معنى غير لفظ الموضوع: «أقيموا الصلاة» لا «في الصلاة» ولا «قال موسى»
          if (!span.some((w) => w[2] && !keys.has(w[2]) && index.verses[i].content.has(w[2]))) continue;
          const key = [wordKey(span[0], true), ...wk.slice(k + 1, k + size)].join(" ");
          let e = found.get(key);
          if (!e) found.set(key, (e = { key, size, verses: new Set(), texts: new Map() }));
          e.verses.add(i);
          const text = span.map((w) => w[0]).join(" ");
          e.texts.set(text, (e.texts.get(text) || 0) + 1);
        }
      }
    }
    // العبارة «مغلقة» إذا لم تحتوها عبارة أطول في الآيات نفسها بالضبط (فلا نعرض نوافذها)
    const sig = (e) => [...e.verses].sort((x, y) => x - y).join(",");
    const repeated = [...found.values()].filter((e) => e.verses.size >= 2);
    const longest = new Map();
    for (const e of repeated) {
      const s = sig(e);
      if (!longest.has(s) || longest.get(s).size < e.size) longest.set(s, e);
    }
    const closed = repeated.filter((e) => longest.get(sig(e)) === e);
    closed.sort((x, y) => y.verses.size - x.verses.size || y.size - x.size);

    // نختار الأكثر تكرارًا، ونتجاوز ما يتداخل مع عبارة اختيرت (يشتركان في ثلاث كلمات متتالية،
    // أو تحتوي إحداهما الأخرى)
    const grams = (e) => {
      const t = e.key.split(" ");
      const out = new Set();
      for (let k = 0; k + 3 <= t.length; k++) out.add(t.slice(k, k + 3).join(" "));
      return out;
    };
    const chosen = [];
    for (const e of closed) {
      if (chosen.length >= MAX_FORMULAS) break;
      const g = grams(e);
      const overlaps = chosen.some((c) => ` ${c.key} `.includes(` ${e.key} `) || ` ${e.key} `.includes(` ${c.key} `)
        || [...g].some((x) => c.grams.has(x)));
      if (overlaps) continue;
      chosen.push({ ...e, grams: g });
    }
    return chosen.map((e) => ({
      // النص الأكثر ورودًا من صيغ العبارة
      text: [...e.texts.entries()].sort((x, y) => y[1] - x[1])[0][0],
      count: e.verses.size,
      example: Math.min(...e.verses),
    }));
  }

  function surahDistribution(index, idxs) {
    const counts = new Map();
    for (const i of idxs) {
      const v = index.verses[i];
      if (!counts.has(v.s)) counts.set(v.s, { s: v.s, name: v.surahName, count: 0 });
      counts.get(v.s).count++;
    }
    return [...counts.values()].sort((x, y) => y.count - x.count || x.s - y.s);
  }

  // تجميع هرمي بمتوسط التشابه: الآيات المتقاربة في ألفاظها تكوّن محورًا
  function clusterVerses(vectors, threshold) {
    const n = vectors.length;
    const sim = new Float32Array(n * n);
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const s = cosine(vectors[i], vectors[j]);
        sim[i * n + j] = s;
        sim[j * n + i] = s;
      }
    }
    const members = Array.from({ length: n }, (_, i) => [i]);
    const active = new Array(n).fill(true);
    for (;;) {
      let best = threshold;
      let bi = -1;
      let bj = -1;
      for (let i = 0; i < n; i++) {
        if (!active[i]) continue;
        for (let j = i + 1; j < n; j++) {
          if (active[j] && sim[i * n + j] > best) {
            best = sim[i * n + j];
            bi = i;
            bj = j;
          }
        }
      }
      if (bi < 0) break;
      // متوسط التشابه للمجموعة المدمجة (Lance–Williams)
      const ni = members[bi].length;
      const nj = members[bj].length;
      for (let k = 0; k < n; k++) {
        if (!active[k] || k === bi || k === bj) continue;
        const s = (ni * sim[bi * n + k] + nj * sim[bj * n + k]) / (ni + nj);
        sim[bi * n + k] = s;
        sim[k * n + bi] = s;
      }
      members[bi] = members[bi].concat(members[bj]);
      active[bj] = false;
    }
    return members.filter((_, i) => active[i]);
  }

  function axes(index, idxs, vectors) {
    if (idxs.length > MAX_CLUSTER_VERSES) return { list: [], skipped: true, rest: idxs.length };
    const groups = clusterVerses(vectors, CLUSTER_THRESHOLD);
    const minSize = Math.max(2, Math.round(idxs.length * 0.03));
    const list = groups
      .filter((g) => g.length >= minSize)
      .map((g) => {
        // عنوان المحور: الألفاظ المشتركة بين ربع آياته على الأقل، الأثقل وزنًا أولًا
        const weight = new Map();
        const count = new Map();
        for (const m of g) {
          for (const [key, w] of vectors[m]) {
            weight.set(key, (weight.get(key) || 0) + w);
            count.set(key, (count.get(key) || 0) + 1);
          }
        }
        const minShare = Math.max(2, Math.ceil(g.length * 0.25));
        const labels = [...weight.entries()]
          .filter(([key]) => count.get(key) >= minShare)
          .sort((x, y) => y[1] - x[1])
          .slice(0, 3)
          .map(([key]) => plain(index.lemmas.get(key).display));
        // الآية الممثّلة: الأقرب إلى بقية آيات المحور
        const total = sumVectors(g.map((m) => vectors[m]));
        let medoid = g[0];
        let bestSum = -Infinity;
        for (const m of g) {
          const s = cosine(vectors[m], total);
          if (s > bestSum) {
            bestSum = s;
            medoid = m;
          }
        }
        return { labels, verses: g.map((m) => idxs[m]).sort((x, y) => x - y), representative: idxs[medoid] };
      })
      .filter((ax) => ax.labels.length)
      .sort((x, y) => y.verses.length - x.verses.length || x.verses[0] - y.verses[0]);
    return { list, skipped: false, rest: idxs.length - list.reduce((s, ax) => s + ax.verses.length, 0) };
  }

  // أجمع الآيات: أكثر ما يقترن بالموضوع من ألفاظ، نسبةً إلى طول الآية (فلا تغلب الآية الطويلة
  // بكثرة ألفاظها)، ثم الأقرب إلى بقية آيات الموضوع
  function centralVerses(index, idxs, vectors, cooccur, howMany) {
    const maxScore = cooccur.length ? cooccur[0].score : 1;
    const weight = new Map(cooccur.map((c) => [c.key, c.score / maxScore]));
    const n = vectors.length;
    const total = sumVectors(vectors);
    const scores = vectors.map((v, i) => {
      const content = index.verses[idxs[i]].content;
      let covered = 0;
      for (const [k, w] of weight) if (content.has(k)) covered += w;
      const density = covered / Math.sqrt(Math.max(4, content.size));
      const sim = v.size && n > 1 ? (cosine(v, total) - 1) / (n - 1) : 0;
      return [density + 0.5 * sim, i];
    });
    scores.sort((x, y) => y[0] - x[0] || x[1] - y[1]);
    const out = [];
    const texts = new Set();
    for (const [score, i] of scores) {
      if (out.length >= howMany || score <= 0) break;
      const text = index.verses[idxs[i]].tokens.join(" ");
      if (texts.has(text)) continue; // مثل ﴿ولقد يسرنا القرآن للذكر﴾ المكررة في القمر
      texts.add(text);
      out.push(idxs[i]);
    }
    return out;
  }

  /**
   * الخلاصة: كلها مأخوذة من ألفاظ الآيات (إحصاء وتجميع)، لا من تفسير خارجي.
   * idxs: آيات الموضوع إن حُسبت (للعبارة)، وإلا آيات اللمّات.
   */
  function summarize(index, keys, idxs) {
    const keySet = new Set(keys);
    idxs = idxs || topicVerses(index, keys);
    if (!idxs.length) return { verses: [] };

    // نستبعد ألفاظ الموضوع وما يشاركها الجذر، حتى لا يُقال «الصلاة تقترن بالصلاة»
    const exclude = new Set(keys);
    for (const key of keys) {
      const r = index.lemmas.get(key).root;
      if (r) index.rootLemmas.get(r).forEach((k) => exclude.add(k));
    }
    const vectors = idxs.map((i) => verseVector(index, index.verses[i], exclude));
    const cooccur = cooccurrences(index, idxs, exclude);
    return {
      verses: idxs,
      surahs: surahDistribution(index, idxs),
      cooccur,
      formulas: formulas(index, idxs, keySet),
      axes: axes(index, idxs, vectors),
      central: centralVerses(index, idxs, vectors, cooccur, 3),
    };
  }

  // «البقرة (10)، ثم النساء والتوبة (7 لكلٍّ منها)»: السور المتساوية تُذكر معًا
  function topSurahsText(surahs) {
    const groups = [];
    for (const x of surahs) {
      if (x.count < 2) break;
      const last = groups[groups.length - 1];
      if (last && last.count === x.count) last.names.push(x.name);
      else if (groups.length < 3) groups.push({ count: x.count, names: [x.name] });
      else break;
    }
    return groups.map((g) => {
      if (g.names.length === 1) return `${g.names[0]} (${g.count})`;
      const names = g.names.length > 3 ? `${g.names.slice(0, 3).join("، ")} وغيرها` : g.names.join(" و");
      return `${names} (${g.count} لكلٍّ منها)`;
    });
  }

  /**
   * جمل الخلاصة بالعربية. fmt يحدد شكل الإخراج (نص أو HTML):
   *   fmt.esc(نص)، fmt.quote(رقم الآية) للآية مع موضعها، fmt.phrase(نص) لعبارة قرآنية.
   */
  function summarySentences(index, sum, fmt) {
    const sentences = [];
    let first = `ورد هذا الموضوع في ${countAr(sum.verses.length, "ayah")} من ${countAr(sum.surahs.length, "surah")}`;
    if (sum.surahs.length === 1) first += `، هي سورة ${sum.surahs[0].name}`;
    else {
      const top = topSurahsText(sum.surahs);
      if (top.length) first += `، أكثرها في سورة ${top.join("، ثم ")}`;
    }
    sentences.push(first + ".");

    if (sum.cooccur.length) {
      sentences.push(`وأكثر ما يقترن به من الألفاظ: ${sum.cooccur.slice(0, 5)
        .map((c) => `«${fmt.esc(plain(c.display))}» (في ${countAr(c.count, "ayah")})`).join("، ")}.`);
    }
    if (sum.formulas.length) {
      const f = sum.formulas[0];
      sentences.push(`وأكثر صيغه تكرارًا: ${fmt.phrase(f.text)} (في ${countAr(f.count, "ayah")}).`);
    }
    const list = sum.axes.list;
    if (list.length > 1) {
      const shown = list.slice(0, 5);
      sentences.push(`وتدور آياته حول ${countAr(list.length, "axis")}، أكبرها: ${shown
        .map((ax) => `«${fmt.esc(ax.labels.join("، "))}» (${ax.verses.length})`).join("؛ ")}.`);
    }
    if (sum.central.length) sentences.push(`وأجمع آية فيه: ${fmt.quote(sum.central[0])}.`);
    return sentences;
  }

  return {
    normalize,
    searchKey,
    spellingKey,
    formulaKey,
    plain,
    queryVariants,
    countAr,
    buildIndex,
    resolveWord,
    resolveQuery,
    topicVerses,
    phraseVerses,
    contextVerses,
    summarize,
    summarySentences,
    clusterVerses,
  };
});
