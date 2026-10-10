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

  function normalize(text) {
    return text.replace(DIACRITICS, "").replace(/[ٱأإآىئؤة]/g, (c) => LETTER_MAP[c]).replace(/\s+/g, "");
  }

  // للبحث فقط: نحذف الهمزة المفردة أيضًا، فـ«القرآن» تطابق لمّة «قُرْءَان»
  function searchKey(text) {
    return normalize(text).replace(/ء/g, "");
  }

  // صيغ ما يكتبه المستخدم: «الصلاة» ← صلاه، «والصبر» ← صبر، «بالحق» ← حق
  function queryVariants(query) {
    const q = searchKey(query);
    const out = [q];
    for (const prefix of ["وال", "فال", "بال", "كال", "ال", "لل"]) {
      if (q.startsWith(prefix) && q.length - prefix.length >= 2) out.push(q.slice(prefix.length));
    }
    return [...new Set(out)];
  }

  // ---------- العربية: صيغة المعدود ----------

  // n مع المعدود في موضع الجر: «في 67 آية»، «في 5 آيات»، «في آيتين»، «في آية واحدة»
  const NOUNS = {
    ayah: { one: "آية واحدة", two: "آيتين", plural: "آيات", single: "آية" },
    surah: { one: "سورة واحدة", two: "سورتين", plural: "سور", single: "سورة" },
    times: { one: "مرة واحدة", two: "مرتين", plural: "مرات", single: "مرة" },
    axis: { one: "محور واحد", two: "محورين", plural: "محاور", single: "محورًا" },
  };

  function countAr(n, kind) {
    const f = NOUNS[kind];
    if (n === 1) return f.one;
    if (n === 2) return f.two;
    const r = n % 100;
    if (r >= 3 && r <= 10) return `${n} ${f.plural}`;
    return `${n} ${kind === "axis" && r === 0 ? "محور" : f.single}`;
  }

  // ---------- الفهرس ----------

  const TOTAL_TOP_SURAHS = 3;
  const MAX_COOCCUR = 8;
  const MAX_FORMULAS = 5;
  const MAX_AXES = 8;
  const MAX_CLUSTER_VERSES = 600;
  const CLUSTER_THRESHOLD = 0.12;
  // لفظ يرد في أكثر من 10% من آيات القرآن عامّ لا يميّز موضوعًا
  const GENERIC_SHARE = 0.1;

  function isGeneric(index, key) {
    return index.lemmas.get(key).verses.length > index.verses.length * GENERIC_SHARE;
  }

  /**
   * surahs: [{n, name, verses: [[[نص، جذر، لمّة، اسم_علم؟], ...], ...]}]
   */
  function buildIndex(surahs) {
    const verses = [];
    // اللمّة تُعرَّف بنصها المشكول، فـ«آتَى» (أعطى) غير «أَتَى» (جاء)
    const lemmas = new Map(); // لمّة -> {key, root, name, verses: []}
    const byKey = new Map(); // مفتاح البحث (بلا تشكيل ولا همزات) -> Set(لمّات)
    const rootLemmas = new Map(); // جذر -> Set(لمّات)

    for (const surah of surahs) {
      surah.verses.forEach((words, i) => {
        const idx = verses.length;
        const keys = new Set();
        const content = new Map(); // مفتاح اللمّة -> عدد مرات وروده في الآية
        const tokens = [];
        for (const [text, rootStr, lemma, isName] of words) {
          tokens.push(normalize(text));
          if (!lemma) continue;
          const key = lemma;
          keys.add(key);
          let info = lemmas.get(key);
          if (!info) {
            info = { key, display: lemma, root: rootStr || "", name: !!isName, verses: [] };
            lemmas.set(key, info);
            const sk = searchKey(lemma);
            if (!byKey.has(sk)) byKey.set(sk, new Set());
            byKey.get(sk).add(key);
          }
          if (rootStr && !info.root) info.root = rootStr;
          if (isName) info.name = true;
          // اللفظ ذو المعنى: له جذر أو اسم علم (لا الحروف والضمائر)
          if (rootStr || isName) content.set(key, (content.get(key) || 0) + 1);
          if (rootStr) {
            if (!rootLemmas.has(rootStr)) rootLemmas.set(rootStr, new Set());
            rootLemmas.get(rootStr).add(key);
          }
        }
        for (const key of keys) lemmas.get(key).verses.push(idx);
        verses.push({ s: surah.n, a: i + 1, surahName: surah.name, words, tokens, keys, content });
      });
    }

    const idf = new Map();
    for (const [key, info] of lemmas) idf.set(key, Math.log(verses.length / info.verses.length));
    return { verses, lemmas, byKey, rootLemmas, idf };
  }

  // ---------- فهم السؤال ----------

  /**
   * يحوّل ما كتبه المستخدم إلى لمّات.
   * يرجع {selected، alternatives، siblings، suggestions} وكلها لمّات:
   *   selected: ما يُقصد غالبًا؛ alternatives: معانٍ أخرى للصيغة نفسها (﴿يصلون﴾: صلّى أو وصل)؛
   *   siblings: من الجذر نفسه؛ suggestions: لمّات قريبة الكتابة إذا لم يُعثر على شيء.
   */
  function resolveQuery(index, query) {
    const variants = queryVariants(query);
    let selected = [];
    for (const v of variants) {
      for (const key of index.byKey.get(v) || []) {
        const info = index.lemmas.get(key);
        // الحروف والضمائر ليست موضوعًا
        if ((info.root || info.name) && !selected.includes(key)) selected.push(key);
      }
    }

    // صيغة فعلية أو جمع (مثل «يصلون»، «الصابرين»): نأخذ لمّات الكلمات المطابقة
    let alternatives = [];
    if (!selected.length) {
      const counts = new Map();
      for (const v of index.verses) {
        v.tokens.forEach((t, k) => {
          if (variants.includes(t) || variants.some((q) => t.length > q.length && t.endsWith(q) && t.length - q.length <= 3)) {
            const lemma = v.words[k][2];
            if (lemma && (v.words[k][1] || v.words[k][3])) counts.set(lemma, (counts.get(lemma) || 0) + 1);
          }
        });
      }
      if (counts.size) {
        // الأكثر ورودًا هو المختار، والباقي معانٍ أخرى يختار منها المستخدم
        const ranked = [...counts.entries()].sort((x, y) => y[1] - x[1]).map(([k]) => k);
        selected = [ranked[0]];
        alternatives = ranked.slice(1, 6);
      }
    }

    const selectedSet = new Set([...selected, ...alternatives]);
    const siblings = [];
    for (const key of selected) {
      const r = index.lemmas.get(key).root;
      if (!r) continue;
      for (const k of index.rootLemmas.get(r)) if (!selectedSet.has(k) && !siblings.includes(k)) siblings.push(k);
    }
    siblings.sort((x, y) => index.lemmas.get(y).verses.length - index.lemmas.get(x).verses.length);

    let suggestions = [];
    if (!selected.length) {
      const q = variants[variants.length - 1];
      if (q.length >= 2) {
        suggestions = [...index.lemmas.values()]
          .filter((info) => (info.root || info.name) && searchKey(info.key).includes(q))
          .sort((x, y) => y.verses.length - x.verses.length)
          .slice(0, 12)
          .map((info) => info.key);
      }
    }
    return { selected, alternatives, siblings, suggestions };
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
    const minCount = n >= 30 ? 3 : 2;
    const out = [];
    for (const [key, c] of counts) {
      if (c < minCount || isGeneric(index, key)) continue;
      const lift = (c / n) / (index.lemmas.get(key).verses.length / total);
      if (lift < 2) continue;
      out.push({ key, count: c, score: c * Math.log(lift) });
    }
    out.sort((x, y) => y.score - x.score || y.count - x.count);
    return out.slice(0, MAX_COOCCUR).map((o) => {
      const example = idxs.find((i) => index.verses[i].content.has(o.key));
      return { key: o.key, display: index.lemmas.get(o.key).display, count: o.count, example };
    });
  }

  // الصيغ المتكررة: عبارات (2 إلى 7 كلمات) فيها لفظ الموضوع وتتكرر في آياته
  const FORMULA_MAX_WORDS = 7;

  function formulas(index, idxs, keys) {
    const counts = new Map(); // عبارة موحّدة -> {text, size, verses: []}
    for (const i of idxs) {
      const v = index.verses[i];
      const seen = new Set();
      for (let size = 2; size <= FORMULA_MAX_WORDS; size++) {
        for (let k = 0; k + size <= v.tokens.length; k++) {
          const span = v.words.slice(k, k + size);
          if (!span.some((w) => keys.has(w[2]))) continue;
          // عبارة فيها لفظ ذو معنى غير لفظ الموضوع، وغير عام مثل «قال»
          // («أقيموا الصلاة» لا «في الصلاة» ولا «قال موسى»)
          if (!span.some((w) => (w[1] || w[3]) && !keys.has(w[2]) && !isGeneric(index, w[2]))) continue;
          const g = v.tokens.slice(k, k + size).join(" ");
          if (seen.has(g)) continue;
          seen.add(g);
          const e = counts.get(g) || { g, text: span.map((w) => w[0]).join(" "), size, verses: [] };
          e.verses.push(i);
          counts.set(g, e);
        }
      }
    }
    let list = [...counts.values()].filter((e) => e.verses.length >= 2);

    // نوافذ العبارة الطويلة نفسها تتكرر في الآيات نفسها: نُبقي الأطول منها
    const bySignature = new Map();
    for (const e of list) {
      const sig = e.verses.join(",");
      const cur = bySignature.get(sig);
      if (!cur || e.size > cur.size) bySignature.set(sig, e);
    }
    list = [...bySignature.values()];

    // ونحذف العبارة إذا احتوتها عبارة أطول تتكرر بقدر قريب منها (﴿آتينا موسى﴾ في ﴿ولقد آتينا موسى﴾)
    list = list.filter((e) => !list.some((o) => o !== e && o.size > e.size
      && ` ${o.g} `.includes(` ${e.g} `) && o.verses.length >= e.verses.length * 0.75));

    list.sort((x, y) => y.verses.length - x.verses.length || y.size - x.size);
    return list.slice(0, MAX_FORMULAS).map((e) => ({ text: e.text, count: e.verses.length, example: e.verses[0] }));
  }

  function surahDistribution(index, idxs) {
    const counts = new Map();
    for (const i of idxs) {
      const v = index.verses[i];
      counts.set(v.s, (counts.get(v.s) || 0) + 1);
    }
    return [...counts.entries()]
      .map(([s, count]) => ({ s, name: index.verses.find((v) => v.s === s).surahName, count }))
      .sort((x, y) => y.count - x.count || x.s - y.s);
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
    if (idxs.length > MAX_CLUSTER_VERSES) return { list: [], skipped: true, rest: 0 };
    const groups = clusterVerses(vectors, CLUSTER_THRESHOLD);
    const minSize = Math.max(2, Math.round(idxs.length * 0.03));
    const big = groups.filter((g) => g.length >= minSize).sort((x, y) => y.length - x.length || x[0] - y[0]);
    const shown = big.slice(0, MAX_AXES);

    const list = shown.map((g) => {
      // عنوان المحور: الألفاظ المشتركة بين أكثر آياته
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
        .filter(([key]) => count.get(key) >= minShare && !isGeneric(index, key))
        .sort((x, y) => y[1] - x[1])
        .slice(0, 3)
        .map(([key]) => index.lemmas.get(key).display);
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
      return {
        labels,
        verses: g.map((m) => idxs[m]).sort((x, y) => x - y),
        representative: idxs[medoid],
      };
    }).filter((ax) => ax.labels.length);
    return { list, skipped: false, rest: idxs.length - list.reduce((s, ax) => s + ax.verses.length, 0) };
  }

  // أجمع الآيات: التي تجمع أكثر الألفاظ المقترنة بالموضوع،
  // وعند التساوي الأقرب في ألفاظها إلى بقية آياته
  function centralVerses(index, idxs, vectors, cooccur, howMany) {
    const concepts = cooccur.map((c) => c.key);
    const n = vectors.length;
    const total = sumVectors(vectors);
    const scores = vectors.map((v, i) => {
      // تشابهها مع بقية الآيات (دون نفسها)
      const sim = v.size ? cosine(v, total) - 1 : 0;
      const content = index.verses[idxs[i]].content;
      const covered = concepts.filter((k) => content.has(k)).length;
      return [covered + (n > 1 ? sim / (n - 1) : 0), i];
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
   */
  function summarize(index, keys) {
    const keySet = new Set(keys);
    const idxs = topicVerses(index, keys);
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

  /**
   * جمل الخلاصة بالعربية. fmt يحدد شكل الإخراج (نص أو HTML):
   *   fmt.esc(نص)، fmt.quote(رقم الآية) للآية مع موضعها، fmt.phrase(نص) لعبارة قرآنية.
   */
  function summarySentences(index, sum, fmt) {
    const sentences = [];
    const [s1, s2, s3] = sum.surahs;
    let first = `ورد هذا الموضوع في ${countAr(sum.verses.length, "ayah")} من ${countAr(sum.surahs.length, "surah")}`;
    if (sum.surahs.length === 1) first += `، هي سورة ${s1.name}`;
    else if (s1.count > 1) {
      first += `، أكثرها في سورة ${s1.name} (${s1.count})`;
      if (s2 && s2.count > 1) first += `، ثم ${s2.name} (${s2.count})`;
      if (s3 && s3.count > 1) first += `، ثم ${s3.name} (${s3.count})`;
    }
    sentences.push(first + ".");

    if (sum.cooccur.length) {
      sentences.push(`ويقترن في آياته كثيرًا بـ: ${sum.cooccur.slice(0, 5)
        .map((c) => `«${fmt.esc(c.display)}» (في ${countAr(c.count, "ayah")})`).join("، ")}.`);
    }
    if (sum.formulas.length) {
      const f = sum.formulas[0];
      sentences.push(`وأكثر صيغه تكرارًا: ${fmt.phrase(f.text)} (${countAr(f.count, "times")}).`);
    }
    const axesList = sum.axes.list;
    if (axesList.length > 1) {
      sentences.push(`وتدور آياته حول ${countAr(axesList.length, "axis")}: ${axesList
        .map((ax) => `${fmt.esc(ax.labels.join(" و"))} (${ax.verses.length})`).join("؛ ")}.`);
    }
    if (sum.central.length) sentences.push(`وأجمع آية فيه: ${fmt.quote(sum.central[0])}.`);
    return sentences;
  }

  return {
    normalize,
    searchKey,
    queryVariants,
    countAr,
    buildIndex,
    resolveQuery,
    topicVerses,
    summarize,
    summarySentences,
    clusterVerses,
    TOTAL_TOP_SURAHS,
  };
});
