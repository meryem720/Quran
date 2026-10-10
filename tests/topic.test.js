// اختبارات محرّك الموضوعات: node --test tests/topic.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("path");

const T = require(path.join(__dirname, "..", "web", "topic.js"));
const quran = require(path.join(__dirname, "..", "web", "data", "quran.json"));
const index = T.buildIndex(quran.surahs);

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
  assert.equal(T.countAr(12, "times"), "12 مرة");
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
