// اختبار دخان للواجهة: يشغّل web/app.js في Node مع DOM مبسّط ويتأكد أن كل صفحة تُعرض دون خطأ.
//   node --test tests/app.smoke.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const WEB = path.join(__dirname, "..", "web");

// يحمّل التطبيق على عنوان معيّن ويرجع محتوى #app والأخطاء
async function load(hash) {
  const els = {};
  const el = (id) => els[id] || (els[id] = {
    id, innerHTML: "", value: "", max: 0, dataset: {},
    insertAdjacentHTML(_, html) { this.innerHTML += html; },
    addEventListener() {}, scrollIntoView() {}, focus() {}, setAttribute() {},
    querySelector() { return null; }, querySelectorAll() { return []; },
  });
  const errors = [];
  const ctx = {
    console: { log() {}, warn() {}, error: (...a) => errors.push(a.map(String).join(" ")) },
    document: { getElementById: el, querySelector: () => null, querySelectorAll: () => [], addEventListener() {}, title: "" },
    location: { hash },
    fetch: async (url) => ({ json: async () => JSON.parse(fs.readFileSync(path.join(WEB, url), "utf8")) }),
    addEventListener() {}, scrollTo() {}, scrollY: 0,
    history: { replaceState() {}, pushState() {}, state: null },
    sessionStorage: { getItem: () => null, setItem() {} },
    setTimeout, clearTimeout,
  };
  ctx.window = ctx;
  ctx.self = ctx;
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(path.join(WEB, "topic.js"), "utf8"), ctx);
  vm.runInContext(fs.readFileSync(path.join(WEB, "app.js"), "utf8"), ctx);
  for (let i = 0; i < 100 && !el("app").innerHTML.includes("<"); i++) await new Promise((r) => setTimeout(r, 50));
  await new Promise((r) => setTimeout(r, 50));
  const extra = ["topic-verses", "order-list"].map((id) => (els[id] ? els[id].innerHTML : "")).join("");
  return { html: el("app").innerHTML + extra, errors };
}

const topic = (q) => "#topic/" + encodeURIComponent(q);

for (const [name, hash, expect] of [
  ["صفحة آية", "#2:255", "الآيات المفسِّرة"],
  ["البيان جملةً جملة", "#2:255", "clause-group"],
  ["كلام متصل", "#103:2", "استثناء من الأولى"],
  ["لفظ نادر", "#15:87", "لفظ نادر"],
  ["أعلام مشتركة", "#51:24", "أعلام مشتركة: إبراهيم"],
  ["القصة في موضع آخر", "#2:37", "القصة نفسها في موضع آخر"],
  ["صفحة الموضوعات", "#topics", "البحث بالموضوع"],
  ["موضوع الصلاة", topic("الصلاة"), "الخلاصة"],
  ["موضوع موسى", topic("موسى"), "محاور الموضوع"],
  ["موضوع واسع", topic("الله"), "الخلاصة"],
  ["موضوع غير موجود", topic("xyz"), "لم يُعثر"],
  ["البحث بحروف لاتينية", topic("prayer"), "البحث بالحروف العربية"],
  ["جذر", "#root/" + encodeURIComponent("رحم"), "مواضع الجذر"],
  ["معنى اللفظ في المعجم", "#root/" + encodeURIComponent("طور|طور"), "مختار الصحاح"],
  ["معاني الجذر في المعجم", "#root/" + encodeURIComponent("كلم"), "معاني الجذر «كلم» في المعجم"],
  ["الجذر حسب ما يلي اللفظ", "#root/" + encodeURIComponent("ضرب"), "حسب اللفظ والحرف الذي يليه"],
  ["مختبر الفرضيات", "#root/" + encodeURIComponent("حيي"), "مختبر الفرضيات"],
  ["لفظ لا يرد في القرآن", topic("تلفاز"), "لا يرد في القرآن"],
  ["العرض المبسّط أو الكامل", "#2:255", "data-view=\"simple\""],
  ["بحث حرفي", "#search/" + encodeURIComponent("الرحمن"), "نتائج البحث"],
  ["الترتيب", "#order", "ترتيب القرآن"],
  ["زمن الأحداث", "#order/time", "الشاهد على موضعها"],
  ["حقبة موسى", "#order/time/musa", "passage-text"],
  ["مشاهد الآخرة بمراحلها", "#order/time/hour", "النفخ في الصور وأهوال الساعة"],
  ["قصص لا يحدد النص زمنها", "#order/time/unplaced", "أصحاب الكهف"],
  ["القصص", "#order/stories", "قصة"],
  ["قصة يوسف", "#order/story/yusuf", "يوسف 4–"],
  ["الشخصيات", "#order/characters", "أقوام وجماعات"],
  ["شخصية موسى", "#order/character/musa", "ما قاله"],
  ["محمد ﷺ: ما قاله وما نودي به", "#order/character/muhammad", "ما نودي به"],
  ["المخاطَب: النبي ﷺ يفتح شخصيته", "#order/addressee/prophet", "#order/character/muhammad"],
  ["صفحة الشخصية تختصر الآيات الكثيرة", "#order/character/muhammad", "#order/speaker/prophet"],
  ["الترتيب بالموضوع", "#order/topics", "اليوم الآخر"],
  ["المخاطَبون", "#order/addressees", "الذين آمنوا"],
  ["المخاطَب: الذين آمنوا", "#order/addressee/believers", "نداء"],
  ["المتكلم: الله", "#order/speaker/god|1", "بضمير المتكلم"],
  ["الآية في الترتيب", "#20:12", "الزمن:"],
  ["الحروف المقطعة", "#2:1", "تُفتتح بها 29 سورة"],
  ["التعليل في الآية التالية", "#2:175", "تبيّن سبب ما في هذه"],
  ["الغاية من الآية السابقة", "#30:45", "تبيّن الغاية مما في"],
  ["آية لا يشترك لفظها مع غيرها", "#112:2", "فأقرب بيانها من القرآن سياقها"],
]) {
  test(name, async () => {
    const { html, errors } = await load(hash);
    assert.deepEqual(errors, []);
    assert.ok(html.includes(expect), html.slice(0, 300));
    assert.ok(!html.includes("تعذّر تحميل البيانات"));
  });
}

// آية تبدأ بضمير (﴿هو الذي خلق لكم﴾) ليست من الحروف المقطعة، و﴿ذلك مبلغهم﴾ ليست تعليلًا
test("لا تُعدّ الآية حروفًا مقطعة ولا تعليلًا خطأً", async () => {
  for (const [hash, text] of [["#2:29", "حروف مقطعة"], ["#6:2", "حروف مقطعة"], ["#53:30", "تبيّن سبب"], ["#53:29", "تبيّن سبب"]]) {
    const { html, errors } = await load(hash);
    assert.deepEqual(errors, []);
    assert.ok(!html.includes(text), `${hash}: ${text}`);
  }
});
