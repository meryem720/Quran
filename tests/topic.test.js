// اختبارات محرّك الموضوعات: node --test tests/topic.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("path");

const T = require(path.join(__dirname, "..", "web", "topic.js"));
const quran = require(path.join(__dirname, "..", "web", "data", "quran.json"));
const index = T.buildIndex(quran);

const ref = (i) => `${index.verses[i].s}:${index.verses[i].a}`;
// ترتيب الحركات (الشدة والفتحة) قد يختلف بين نصين متطابقين، فنوحّده قبل المقارنة
const nfc = (x) => x.normalize("NFC");
const displays = (keys) => keys.map((k) => nfc(index.lemmas.get(k).display));
const lemmaKey = (display) => [...index.lemmas.keys()].find((k) => nfc(k) === nfc(display));

test("صيغة المعدود بالعربية", () => {
  assert.equal(T.countAr(1, "ayah"), "آية واحدة");
  assert.equal(T.countAr(2, "ayah"), "آيتين");
  assert.equal(T.countAr(5, "ayah"), "5 آيات");
  assert.equal(T.countAr(78, "ayah"), "78 آية");
  assert.equal(T.countAr(103, "ayah"), "103 آيات");
  assert.equal(T.countAr(2, "ayah", "nom"), "آيتان");
  assert.equal(T.countAr(11, "axis"), "11 محورًا");
});

test("«الصلاة» تُفهم لمّةً لا حروفًا", () => {
  const r = T.resolveQuery(index, "الصلاة");
  assert.deepEqual(displays(r.selected), [nfc("صَلاة")]);
  assert.ok(displays(r.siblings).includes(nfc("صَلَّى")), "صلّى من الجذر نفسه اختيارية");
  assert.ok(T.resolveQuery(index, "القرآن").selected.length, "الهمزة في «قُرْءان» لا تمنع المطابقة");
});

test("«آتَى» (أعطى) لا تختلط بـ«أَتَى» (جاء)", () => {
  const give = lemmaKey("آتَى");
  const come = lemmaKey("أَتَى");
  assert.ok(give && come && give !== come);
  // العددان متساويان مصادفةً (240)، لكن الآيات مختلفة
  const comeSet = new Set(index.lemmas.get(come).verses);
  const shared = index.lemmas.get(give).verses.filter((i) => comeSet.has(i)).length;
  assert.ok(shared < 20, `آيات مشتركة: ${shared}`);
});

test("الصيغة المشتركة تعرض معانيها الأخرى", () => {
  const r = T.resolveQuery(index, "يصلون");
  const all = displays([...r.selected, ...r.alternatives]);
  assert.ok(all.includes(nfc("صَلَّى")), all.join("، "));
  assert.ok(all.includes(nfc("يَصِلُ")), all.join("، "));
});

test("ما لا يُعرف يرجع بلا اختيار", () => {
  const r = T.resolveQuery(index, "xyz");
  assert.equal(r.selected.length, 0);
});

test("خلاصة «الصلاة»", () => {
  const sum = T.summarize(index, T.resolveQuery(index, "الصلاة").selected);
  const refs = sum.verses.map(ref);
  assert.ok(refs.includes("2:43") && refs.includes("2:3"));
  assert.ok(!refs.includes("33:56"), "﴿يصلون على النبي﴾ ليست من آيات الصلاة بالمعنى المقصود");
  assert.ok(displays(sum.cooccur.map((c) => c.key)).includes(nfc("زَكاة")));
  assert.ok(sum.formulas.length && sum.formulas[0].count >= 2);
  assert.ok(sum.axes.list.length >= 2);
  // كل آية في محور واحد على الأكثر
  const inAxes = sum.axes.list.flatMap((ax) => ax.verses);
  assert.equal(new Set(inAxes).size, inAxes.length);
  assert.equal(inAxes.length + sum.axes.rest, sum.verses.length);
});

test("لا تكرار في الصيغ ولا في أجمع الآيات", () => {
  const sum = T.summarize(index, T.resolveQuery(index, "القرآن").selected);
  const texts = sum.central.map((i) => index.verses[i].tokens.join(" "));
  assert.equal(new Set(texts).size, texts.length);
  assert.ok(sum.formulas.some((x) => T.normalize(x.text).includes("فهلمنمدكر")), "العبارة الكاملة لا نوافذها");
});

test("الموضوع الواسع لا تُحسب محاوره ويُذكر ذلك", () => {
  const sum = T.summarize(index, T.resolveQuery(index, "الله").selected);
  assert.ok(sum.verses.length > 600);
  assert.equal(sum.axes.skipped, true);
});

test("الجمل بالعربية", () => {
  const sum = T.summarize(index, T.resolveQuery(index, "الحج").selected);
  const fmt = { esc: (x) => x, phrase: (x) => x, quote: (i) => ref(i) };
  const text = T.summarySentences(index, sum, fmt).join(" ");
  assert.match(text, /^ورد هذا الموضوع في 7 آيات من 4 سور/);
});

// ---------- حالات كشفتها المراجعة ----------

const versesOf = (q) => {
  const r = T.resolveQuery(index, q);
  const idxs = r.phrase ? T.phraseVerses(index, r.phrase) : T.topicVerses(index, r.selected);
  return idxs.map(ref);
};

test("الجذر الذي كل ألفاظه بمعنى واحد يُجمع كله", () => {
  const sawm = versesOf("الصيام");
  assert.ok(sawm.includes("2:184") && sawm.includes("2:185") && sawm.includes("33:35"));
  assert.deepEqual(versesOf("الصوم"), sawm);
  const tawba = versesOf("التوبة");
  assert.ok(tawba.includes("2:37") && tawba.includes("110:3"), "تاب والتواب");
  assert.ok(versesOf("الصبر").includes("2:155"), "الصابرين");
});

test("الأسماء المتفقة كتابةً المختلفة معنًى لا تُدمج", () => {
  const r = T.resolveQuery(index, "الجنة");
  assert.deepEqual(displays(r.selected), [nfc("جَنَّة")]);
  assert.ok(displays(r.alternatives).includes(nfc("جِنَّة")));
  assert.ok(!versesOf("الجنة").includes("114:6"), "﴿من الجنة والناس﴾ ليست الجنة");
  // الفعل والاسم معًا يبقيان
  assert.ok(displays(T.resolveQuery(index, "الظلم").selected).includes(nfc("ظَلَمَ")));
  // حِجّ قراءة للفظ حَجّ نفسه
  assert.ok(versesOf("الحج").includes("3:97"));
});

test("صيغ الجمع والمشتقات بالإملاء الحديث", () => {
  assert.ok(displays(T.resolveQuery(index, "الصابرين").selected).includes(nfc("صابِر")));
  assert.deepEqual(displays(T.resolveQuery(index, "اليتامى").selected), [nfc("يَتِيم")]);
  assert.deepEqual(displays(T.resolveQuery(index, "الوالدين").selected), [nfc("والِد")]);
  assert.deepEqual(displays(T.resolveQuery(index, "المناسك").selected), [nfc("مَنسَك")]);
});

test("لمّة مختلفة للكلمة نفسها في البيانات: ﴿رِبًا﴾ في الروم 39", () => {
  const riba = versesOf("الربا");
  assert.ok(riba.includes("30:39"));
  assert.ok(!riba.includes("22:5") && !riba.includes("6:164"));
});

test("العبارات: الكلمات المتتابعة", () => {
  assert.deepEqual(versesOf("ليلة القدر"), ["97:1", "97:2", "97:3"]);
  const q = versesOf("يوم القيامة");
  assert.ok(q.length >= 60 && q.includes("2:85"));
  assert.ok(versesOf("بني إسرائيل").includes("2:40"));
  assert.equal(T.resolveQuery(index, "يوم xyz").selected.length, 0);
});

test("الصيغ لا تخلط الأمر بالماضي، ولا تعرض نوافذ العبارة نفسها", () => {
  const sum = T.summarize(index, T.resolveQuery(index, "الزكاة").selected);
  for (const f of sum.formulas) {
    const key = T.formulaKey(f.text);
    // كل الآيات المعدودة فيها الصيغة بحروفها وحركاتها الداخلية
    assert.ok(f.count >= 2, f.text);
    assert.ok(!(key.includes("وءاتُوا") && key.includes("وءاتَوا")));
  }
  const imperative = sum.formulas.find((f) => f.text.includes("وَءَاتُوا۟"));
  if (imperative) assert.ok(imperative.count <= 8, `${imperative.text} ×${imperative.count}`);
  // عبارة داخل أطول منها تُعرض فقط إذا وردت في آيات أكثر (﴿ويؤتون الزكاة﴾ 6 و﴿يقيمون الصلاة ويؤتون الزكاة﴾ 4)
  for (const f of sum.formulas) for (const g of sum.formulas) {
    if (f !== g && T.normalize(g.text).includes(T.normalize(f.text).replace(/^[وف]/, ""))) {
      assert.ok(f.count > g.count, `${f.text} ×${f.count} داخل ${g.text} ×${g.count}`);
    }
  }
});

test("الأدوات ذات الجذر (أيّ، عند، بين) ليست ألفاظًا مقترنة", () => {
  for (const q of ["الربا", "الصلاة", "موسى"]) {
    const sum = T.summarize(index, T.resolveQuery(index, q).selected);
    const shown = displays(sum.cooccur.map((c) => c.key));
    for (const fn of ["أَيّ", "عِند", "بَيْن", "كُلّ"]) assert.ok(!shown.includes(nfc(fn)), `${q}: ${fn}`);
  }
});

test("آيات السياق بين مواضع القصة", () => {
  const sum = T.summarize(index, T.resolveQuery(index, "مريم").selected);
  const ctx = T.contextVerses(index, sum.verses).map(ref);
  assert.ok(ctx.includes("19:20"), "قصة مريم في سورتها");
  assert.ok(ctx.every((r) => !sum.verses.map(ref).includes(r)));
});

// ---------- حالات كشفتها جولة التحقق الثانية ----------

test("المصحف هو المرجع: «الحق» حَقّ لا أَلْحَقْ، و«الأنهار» نَهَر لا انْهارَ", () => {
  assert.ok(displays(T.resolveQuery(index, "الحق").selected).includes(nfc("حَقّ")));
  assert.deepEqual(displays(T.resolveQuery(index, "الأنهار").selected), [nfc("نَهَر")]);
  assert.deepEqual(displays(T.resolveQuery(index, "الباب").selected), [nfc("باب")]);
  assert.deepEqual(displays(T.resolveQuery(index, "المرأة").selected), [nfc("امْرَأَت")]);
  assert.deepEqual(displays(T.resolveQuery(index, "ابنة").selected), [nfc("ابْنَت")]);
  assert.ok(displays(T.resolveQuery(index, "التائبين").selected).includes(nfc("تابَ")));
});

test("حرف الجذر لا يُعدّ سابقة، وما لا يُعرف لا يُخمَّن", () => {
  // «في» ليست «ك + في» (كفى)، و«الحجاج» ليست حِجَج
  assert.equal(T.resolveQuery(index, "في").selected.length, 0);
  assert.equal(T.resolveQuery(index, "الحجاج").selected.length, 0);
  assert.equal(T.resolveQuery(index, "الإحرام").selected.length, 0);
});

test("العبارات بحروفها وألقاب الأسماء", () => {
  assert.equal(versesOf("في سبيل الله").length, 43);
  assert.deepEqual(versesOf("لا إله إلا الله"), ["37:35", "47:19"]);
  assert.ok(versesOf("يا مريم").includes("3:42"));
  assert.deepEqual(versesOf("ابنة عمران"), ["66:12"]);
  assert.equal(versesOf("موسى عليه السلام").length, versesOf("موسى").length);
});

test("الخلاصة: محاور بلا تكرار، وعناوين نظيفة، ومثنى صحيح", () => {
  const zakat = T.summarize(index, T.resolveQuery(index, "الزكاة").selected);
  const roots = zakat.axes.list.map((ax) => ax.roots);
  assert.equal(new Set(roots).size, roots.length, "محوران من الجذور نفسها يُدمجان");
  assert.ok(zakat.axes.list[0].verses.map(ref).includes("21:73"), "﴿وإقام الصلاة وإيتاء الزكاة﴾ في المحور الأكبر");
  const salat = T.summarize(index, T.resolveQuery(index, "الصلاة").selected);
  for (const ax of salat.axes.list) {
    assert.equal(new Set(ax.labels).size, ax.labels.length);
    assert.ok(!ax.labels.includes("استعين"), "صيغة المعجم: استعان");
  }
  const fmt = { esc: (x) => x, phrase: (x) => x, quote: (i) => ref(i) };
  const sabr = T.summarySentences(index, T.summarize(index, T.resolveQuery(index, "الصبر").selected), fmt).join(" ");
  assert.match(sabr, /سورتي البقرة والكهف \(8 لكلٍّ منهما\)/);
  const jannah = T.summarize(index, T.resolveQuery(index, "الجنة").selected);
  assert.ok(T.normalize(jannah.formulas[0].text).includes("تجريمنتحتهاالانهر"), "الصيغة الكاملة");
});
