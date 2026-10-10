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
    document: { getElementById: el, querySelector: () => null, querySelectorAll: () => [], title: "" },
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
  return { html: el("app").innerHTML + (els["topic-verses"] ? els["topic-verses"].innerHTML : ""), errors };
}

const topic = (q) => "#topic/" + encodeURIComponent(q);

for (const [name, hash, expect] of [
  ["صفحة آية", "#2:255", "الآيات المفسِّرة"],
  ["صفحة الموضوعات", "#topics", "البحث بالموضوع"],
  ["موضوع الصلاة", topic("الصلاة"), "الخلاصة"],
  ["موضوع موسى", topic("موسى"), "محاور الموضوع"],
  ["موضوع واسع", topic("الله"), "الخلاصة"],
  ["موضوع غير موجود", topic("xyz"), "لم يُعثر"],
  ["جذر", "#root/" + encodeURIComponent("رحم"), "مواضع الجذر"],
  ["بحث حرفي", "#search/" + encodeURIComponent("الرحمن"), "نتائج البحث"],
]) {
  test(name, async () => {
    const { html, errors } = await load(hash);
    assert.deepEqual(errors, []);
    assert.ok(html.includes(expect), html.slice(0, 300));
    assert.ok(!html.includes("تعذّر تحميل البيانات"));
  });
}
