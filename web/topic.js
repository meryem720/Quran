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
  const CLITICS = [
    "", "و", "ف", "ب", "ل", "ك", "س", "وب", "ول", "وك", "وس", "فب", "فل", "فس", "لل", "ولل", "فلل",
    "ال", "وال", "فال", "بال", "كال", "وبال", "فبال",
  ];

  // الحروف الأصلية للجذر (دون حروف العلة والهمزة)
  function strongLetters(root) {
    return [...normalize(root || "")].filter((c) => !"اويء".includes(c));
  }

  // هل كلمة المصحف هي ما كتبه المستخدم مع حروف متصلة بأولها؟ لا يُعدّ حرف الجذر سابقة:
  // ﴿كَفَىٰ﴾ ليست «ك + في»، و﴿بَاسِرَةٌ﴾ ليست «ب + اسرة»، و﴿وَلِيًّا﴾ ليست «ول + يا»
  function matchesWithClitic(form, variant, root) {
    if (!form.endsWith(variant)) return false;
    const prefix = form.slice(0, form.length - variant.length);
    if (!CLITICS.includes(prefix)) return false;
    if (!prefix) return true;
    // لا «ال» مرتين: ﴿ٱلْأَلْبَٰبِ﴾ ليست «ال + الباب»
    if (/^(ال|لل)/.test(variant) && /(ال|لل)$/.test(prefix)) return false;
    if (variant.length < 3) return false;
    return strongLetters(root).every((c) => variant.includes(c));
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

  // لمّات في البيانات ليست كلمات قائمة بنفسها: تُعرض بصيغتها في المعجم
  const DISPLAY_FIX = new Map([
    ["اسْتَعِينُ", "اسْتَعانَ"], ["امْسَحُ", "مَسَحَ"], ["صابِرُ", "صابَرَ"], ["بُنَىّ", "ابْن"],
  ].map(([k, v]) => [k.normalize("NFC"), v]));

  // اسم العرض للّمّة: ماضٍ مختوم بضمة في البيانات يُعرض بالفتحة (عَقَلُ ← عَقَلَ)، لا المضارع (يُحافِظُ)
  function displayOf(lemma, verb) {
    const fixed = DISPLAY_FIX.get(lemma.normalize("NFC"));
    if (fixed) return fixed;
    if (verb && lemma.endsWith("\u064f") && !/^[يتن][\u064e\u064f]/.test(lemma)) return lemma.slice(0, -1) + "\u064e";
    return lemma;
  }

  // عناوين بلا حركات، إلا إذا تشابهت كلمتان بعد حذفها (آخِر وآخَر) أو تكررت (ذِكْر وذَكَرَ)
  function labelsOf(index, keys) {
    const out = [];
    const seen = new Set();
    const bare = keys.map((k) => plain(index.lemmas.get(k).display));
    keys.forEach((k, i) => {
      if (seen.has(bare[i])) return; // ذِكْر وذَكَرَ عنوان واحد
      seen.add(bare[i]);
      const clash = [...index.byKey.get(searchKey(k)) || []].some((o) => o !== k && !index.lemmas.get(o).verb
        && !index.lemmas.get(k).verb && plain(index.lemmas.get(o).display) === bare[i]);
      out.push(clash ? index.lemmas.get(k).display : bare[i]);
    });
    return out;
  }

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
              key: lemma, display: displayOf(lemma, verbs.has(lemma)), root: rootStr || "", name: !!isName,
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

  // لمّات الكلمات المكتوبة في المصحف بحروف ما كتبه المستخدم: {لمّة -> عدد الكلمات}.
  // taa: كتب المستخدم تاءً مربوطة، فلا تطابقها الهاء: «ابنة» غير ﴿ٱبْنَهُۥ﴾
  function writtenLemmas(index, variant, taa = false) {
    const counts = new Map();
    for (const verse of index.verses) {
      verse.spellings.forEach((forms, k) => {
        const [text, rootStr, lemma] = verse.words[k];
        if (!lemma || !isTopical(index, lemma)) return;
        if (taa && !/[ةت]$/.test(plain(text).replace(/[\u0670\u06e5\u06e6]/g, ""))) return;
        if (forms.some((f) => matchesWithClitic(f, variant, rootStr))) counts.set(lemma, (counts.get(lemma) || 0) + 1);
      });
    }
    return counts;
  }

  function ranked(counts) {
    return [...counts.entries()].sort((x, y) => y[1] - x[1]).map(([k]) => k);
  }

  /**
   * يحوّل كلمة واحدة إلى لمّات. يرجع {selected، alternatives، siblings، suggestions}:
   *   selected: ما يُقصد غالبًا؛ alternatives: معانٍ أخرى للكتابة نفسها (﴿الجنة﴾: جِنَّة، جُنَّة؛
   *   ﴿يصلون﴾: وَصَل)؛ siblings: بقية الجذر؛ suggestions: لمّات قريبة الكتابة إذا لم يُعثر على شيء.
   */
  function resolveWord(index, word) {
    const variants = queryVariants(word);
    const full = variants[0] || "";
    let selected = [];
    let alternatives = [];
    const byFreq = (x, y) => index.lemmas.get(y).verses.length - index.lemmas.get(x).verses.length;
    const hitsOf = (v) => [...(index.byKey.get(v) || [])].filter((k) => isTopical(index, k));

    // المرجع هو المصحف: لمّات الكلمات المكتوبة فيه بحروف ما كتبه المستخدم.
    // همزة الوصل تسقط بعد «ال»: «المرأة» = ال + ﴿ٱمْرَأَة﴾
    const taa = /ة$/.test(plain(word).trim());
    const written = full ? writtenLemmas(index, full, taa) : new Map();
    for (const v of variants.slice(1)) {
      for (const [k, c] of writtenLemmas(index, "ا" + v, taa)) if (index.lemmas.get(k).key.startsWith("ٱ") || /^[اٱ]/.test(k)) written.set(k, (written.get(k) || 0) + c);
    }
    // ولمّات تُكتب كما كتب (الكلمة كاملة، ثم دون «ال»)
    const groups = variants.map((v) => ({ v, hits: hitsOf(v) })).filter((g) => g.hits.length);

    if (written.size) {
      const support = (g) => g.hits.reduce((sum, k) => sum + (written.get(k) || 0), 0);
      const best = groups.slice().sort((x, y) => support(y) - support(x))[0];
      const top = ranked(written);
      // «الحق»: ﴿ٱلْحَقُّ﴾ لمّتها حَقّ لا أَلْحَقْ؛ «الأنهار»: ﴿ٱلْأَنْهَٰرُ﴾ نَهَر لا انْهارَ
      if (best && support(best) > 0 && support(best) >= written.get(top[0]) * 0.5) {
        selected = best.hits;
        alternatives = groups.filter((g) => g !== best).flatMap((g) => g.hits);
      } else {
        selected = [top[0]];
        alternatives = [...top.slice(1, 6), ...groups.flatMap((g) => g.hits)];
      }
    } else if (groups.length) {
      selected = groups[0].hits;
      alternatives = groups.slice(1).flatMap((g) => g.hits);
    }

    // صيغ لم ترد بلفظها في المصحف
    if (!selected.length) {
      const tries = [
        // تاء مفتوحة في رسم المصحف يكتبها المستخدم ة: «ابنة» ← ابْنَت
        ...variants.filter((v) => /ه$/.test(v)).map((v) => v.replace(/ه$/, "ت")),
        // جمع سالم: «التائبين» ← تائِب، «الصائمون» ← صائِم
        ...variants.filter((v) => v.length > 4 && /(ين|ون|ات)$/.test(v)).map((v) => v.slice(0, -2)),
      ];
      for (const v of tries) {
        const hits = hitsOf(v).filter((k) => !index.lemmas.get(k).verb);
        if (hits.length) {
          selected = hits;
          break;
        }
      }
    }
    if (!selected.length) {
      // جمع تكسير على «مَفاعِل» من مفرد «مَفْعَل»: «المناسك» ← مَنسَك، «المساجد» ← مَسْجِد
      for (const v of variants) {
        if (v.length < 5 || v[2] !== "ا") continue;
        const single = v.slice(0, 2) + v.slice(3);
        const hits = hitsOf(single).filter((k) => !index.lemmas.get(k).verb);
        if (hits.length) {
          selected = hits;
          break;
        }
      }
    }

    // أسماء تتفق كتابتها وتختلف معانيها (جَنَّة، جِنَّة، جُنَّة): الأكثر ورودًا هو المختار،
    // والباقي معانٍ أخرى. الفعل والاسم معًا (صَبَرَ، صَبْر) يبقيان مختارين.
    const nouns = selected.filter((k) => !index.lemmas.get(k).verb && !SAME_WORD.has(k.normalize("NFC"))).sort(byFreq);
    if (nouns.length > 1) {
      const others = nouns.slice(1);
      selected = selected.filter((k) => !others.includes(k));
      alternatives = [...others, ...alternatives.filter((k) => !others.includes(k))];
    }

    // لمّة من الجذر نفسه كل صيغها هي ما كتبه المستخدم بحروفه (﴿رِبًا﴾ في الروم 39 لمّتها «رِب»)
    for (const key of [...selected]) {
      const r = index.lemmas.get(key).root;
      if (!r) continue;
      for (const k of index.rootLemmas.get(r)) {
        const forms = index.lemmas.get(k).forms;
        if (!selected.includes(k) && !alternatives.includes(k) && forms.size
          && [...forms].every((f) => variants.some((t) => matchesWithClitic(f, t, r)))) {
          selected.push(k);
        }
      }
    }

    // جذر كل ألفاظه بمعنى واحد: يُجمع كله
    for (const key of [...selected]) {
      const r = index.lemmas.get(key).root;
      if (WHOLE_ROOTS.has(r)) {
        for (const k of [...index.rootLemmas.get(r)].sort(byFreq)) if (!selected.includes(k)) selected.push(k);
      }
    }
    alternatives = [...new Set(alternatives)].filter((k) => !selected.includes(k));

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
      if (q.length >= 2) {
        suggestions = [...index.lemmas.values()]
          .filter((info) => isTopical(index, info.key) && searchKey(info.key).includes(q))
          .sort((x, y) => y.verses.length - x.verses.length)
          .slice(0, 12)
          .map((info) => info.key);
      }
    }
    return { selected, alternatives, siblings, suggestions };
  }

  // ألفاظ تُذكر مع الأسماء وليست من القرآن، فتُحذف من السؤال: «موسى عليه السلام»
  const HONORIFICS = /(صلى الله عليه وسلم|عليه الصلاة والسلام|(عليه|عليها|عليهما|عليهم) السلام|رضي الله (عنه|عنها|عنهم|عنهما)|سبحانه وتعالى|عز وجل|جل جلاله)/g;

  // الكلمة حرف أو أداة (في، على، لا، إن، عليه): تُطابق في العبارة بكتابتها، لا بلمّة تشبهها
  function isParticle(index, word) {
    const v = searchKey(word);
    const exact = [...(index.byKey.get(v) || [])];
    if (exact.length) {
      // «إلا» تُكتب كـ«آلاء» بعد حذف الهمزة: الحكم للأكثر ورودًا
      const freq = (keys) => keys.reduce((n, k) => n + index.lemmas.get(k).verses.length, 0);
      return freq(exact.filter((k) => !isTopical(index, k))) > freq(exact.filter((k) => isTopical(index, k)));
    }
    let particle = 0;
    let content = 0;
    for (const verse of index.verses) {
      verse.spellings.forEach((forms, k) => {
        if (!forms.includes(v)) return;
        const lemma = verse.words[k][2];
        if (lemma && isTopical(index, lemma)) content++;
        else particle++;
      });
    }
    return particle > 0 && particle >= content;
  }

  /**
   * يفهم ما كتبه المستخدم: كلمة (الصلاة) أو عبارة (يوم القيامة، في سبيل الله، يا مريم).
   * في العبارة phrase = أجزاء متتابعة، كل جزء:
   *   {word, lemmas: [لمّات]} لكلمة ذات معنى، أو {word, surface: [صيغ]} لحرف يطابق بكتابته،
   *   وprefix: "يا" للنداء المتصل في رسم المصحف (﴿يَٰمَرْيَمُ﴾).
   */
  function resolveQuery(index, query) {
    const words = query.replace(HONORIFICS, " ").replace(/[^\p{L}\p{M}\s]/gu, " ").trim().split(/\s+/).filter(Boolean);
    if (words.length <= 1) return { ...resolveWord(index, words[0] || ""), phrase: null, missing: [] };

    const parts = [];
    const missing = [];
    let prefix = "";
    for (const w of words) {
      if (searchKey(w) === "يا") {
        prefix = "يا";
        continue;
      }
      if (!prefix && isParticle(index, w)) {
        parts.push({ word: w, surface: queryVariants(w).slice(0, 1) });
        continue;
      }
      const r = resolveWord(index, w);
      if (!r.selected.length) missing.push(w);
      // يكفي تتابع الكلمات للتمييز، فتُقبل كل معاني الكتابة: ﴿لَيْلَةِ ٱلْقَدْرِ﴾ لمّتها قَدْر لا قَدَر
      parts.push({ word: w, lemmas: [...r.selected, ...r.alternatives], prefix });
      prefix = "";
    }
    const ok = !missing.length && parts.some((p) => p.lemmas);
    const selected = ok ? [...new Set(parts.flatMap((p) => p.lemmas || []))] : [];
    // كلمة واحدة ذات معنى بعد حذف الألقاب: «موسى عليه السلام» = موسى
    if (ok && parts.length === 1 && !parts[0].prefix) {
      return { ...resolveWord(index, parts[0].word), phrase: null, missing: [] };
    }
    return { selected, alternatives: [], siblings: [], suggestions: [], phrase: ok ? parts : null, missing };
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

  // آيات تتتابع فيها أجزاء العبارة: ﴿يَوْمَ ٱلْقِيَٰمَةِ﴾، ﴿فِى سَبِيلِ ٱللَّهِ﴾، ﴿يَٰمَرْيَمُ﴾
  function phraseVerses(index, phrase) {
    const matchers = phrase.map((p) => {
      if (p.surface) {
        const forms = new Set(p.surface.flatMap((v) => [v, "و" + v, "ف" + v]));
        return (verse, k) => verse.spellings[k].some((f) => forms.has(f));
      }
      const set = new Set(p.lemmas);
      return (verse, k) => set.has(verse.words[k][2]) && (!p.prefix || verse.spellings[k].some((f) => /^[وف]?يا/.test(f)));
    });
    const anchor = phrase.find((p) => p.lemmas);
    return topicVerses(index, anchor.lemmas).filter((i) => {
      const verse = index.verses[i];
      for (let k = 0; k + matchers.length <= verse.words.length; k++) {
        if (matchers.every((m, j) => m(verse, k + j))) return true;
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
    const minCount = n < 10 ? Math.max(2, Math.ceil(n * 0.3)) : n < 30 ? 3 : Math.max(3, Math.ceil(n * 0.04));
    const out = [];
    for (const [key, c] of counts) {
      if (c < minCount) continue;
      const lift = (c / n) / (index.lemmas.get(key).verses.length / total);
      if (lift < 2) continue;
      out.push({ key, count: c, score: c * Math.log(lift) });
    }
    out.sort((x, y) => y.score - x.score || y.count - x.count);
    // لفظان يتشابهان بلا حركات (ذِكْر وذَكَرَ) يُعرضان مرة واحدة
    const seen = new Set();
    return out
      .map((o) => ({ ...o, label: labelsOf(index, [o.key])[0] }))
      .filter((o) => !seen.has(o.label) && seen.add(o.label))
      .slice(0, MAX_COOCCUR)
      .map((o) => ({
        key: o.key,
        display: index.lemmas.get(o.key).display,
        label: o.label,
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
          // لا تنتهي العبارة بحرف: ﴿ثُمَّ يَتُوبُونَ مِن﴾
          const last = span[span.length - 1];
          if (!last[1] && !last[3]) continue;
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
    let closed = repeated.filter((e) => longest.get(sig(e)) === e);
    // العبارة القصيرة تدخل في أطول منها وردت في آيات قريبة العدد: تُعرض الأطول
    // (﴿جَنَّٰتٍ تَجْرِى مِن تَحْتِهَا ٱلْأَنْهَٰرُ﴾ 27 لا ﴿جَنَّٰتٍ تَجْرِى﴾ 28)
    closed = closed.filter((e) => !closed.some((o) => o.size > e.size && ` ${o.key} `.includes(` ${e.key} `)
      && o.verses.size >= e.verses.size * 0.75));
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
        const minShare = Math.max(2, Math.ceil(g.length * 0.34));
        const labelKeys = [...weight.entries()]
          .filter(([key]) => count.get(key) >= minShare)
          .sort((x, y) => y[1] - x[1])
          .map(([key]) => key);
        const labels = labelsOf(index, labelKeys).slice(0, 3);
        const roots = labelKeys.slice(0, 3).map((key) => index.lemmas.get(key).root || key).sort().join("|");
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
        return { labels, roots, verses: g.map((m) => idxs[m]).sort((x, y) => x - y), representative: idxs[medoid] };
      })
      .filter((ax) => ax.labels.length)
      .sort((x, y) => y.verses.length - x.verses.length || x.verses[0] - y.verses[0]);
    // ﴿وَأَقَامَ ٱلصَّلَوٰةَ وَءَاتَى ٱلزَّكَوٰةَ﴾ و﴿وَإِقَامَ ٱلصَّلَوٰةِ وَإِيتَآءَ ٱلزَّكَوٰةِ﴾ محور واحد
    for (let k = 0; k < list.length; k++) {
      const into = list.findIndex((o, j) => j < k && o.roots === list[k].roots);
      if (into >= 0) {
        list[into].verses = list[into].verses.concat(list[k].verses).sort((x, y) => x - y);
        list.splice(k--, 1);
      }
    }
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
    return groups.map((g, i) => {
      const n = g.names.length;
      // أول المجموعات بعد «في»: سورة البقرة، سورتي البقرة والكهف، سور البقرة والنساء والنحل
      const lead = i === 0 ? (n === 1 ? "سورة " : n === 2 ? "سورتي " : "سور ") : "";
      if (n === 1) return `${lead}${g.names[0]} (${g.count})`;
      const names = n > 3 ? `${g.names.slice(0, 3).join(" و")} وغيرها` : g.names.join(" و");
      return `${lead}${names} (${g.count} لكلٍّ ${n === 2 ? "منهما" : "منها"})`;
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
      if (top.length) first += `، أكثرها في ${top.join("، ثم ")}`;
    }
    sentences.push(first + ".");

    if (sum.cooccur.length) {
      sentences.push(`وأكثر ما يقترن به من الألفاظ: ${sum.cooccur.slice(0, 5)
        .map((c) => `«${fmt.esc(c.label)}» (في ${countAr(c.count, "ayah")})`).join("، ")}.`);
    }
    if (sum.formulas.length) {
      const f = sum.formulas[0];
      sentences.push(`وأكثر صيغه تكرارًا: ${fmt.phrase(f.text)} (في ${countAr(f.count, "ayah")}).`);
    }
    const list = sum.axes.list;
    if (list.length > 1) {
      const shown = list.slice(0, 5);
      const intro = list.length === 2 ? "هما" : list.length <= 5 ? "هي" : "أكبرها";
      sentences.push(`وتدور آياته حول ${countAr(list.length, "axis")}، ${intro}: ${shown
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
