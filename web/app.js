"use strict";

// أسباب السياق (نفس الرموز في tools/build.py)
const CONTEXT_REASONS = {
  1: "جواب ﴿وما أدراك﴾ في السياق",
  2: "صفة متصلة بالآية السابقة",
  3: "جواب الاستفهام في الآية التالية",
};
const MAX_RESULTS = 200;

const state = {
  surahs: [],     // [{n, name, verses: [[[نص، جذر، لمّة], ...], ...]}]
  related: {},    // "s:a" -> [[s, a, درجة، سياق، عبارة، جذور]]
  rootIndex: new Map(), // جذر -> [[s, a], ...]
  normWords: [],  // [[s, a, [كلمات موحّدة], [لمّات موحّدة]], ...]
};

const $ = (id) => document.getElementById(id);
const app = $("app");

// نفس التوحيد المستعمل في tools/build.py
const DIACRITICS = /[ؐ-ًؚ-ٰٟۖ-ۭـ]/g;
const LETTER_MAP = { "ٱ": "ا", "أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ئ": "ي", "ؤ": "و", "ة": "ه" };
function normalize(text) {
  return text.replace(DIACRITICS, "").replace(/[ٱأإآىئؤة]/g, (c) => LETTER_MAP[c]).replace(/\s+/g, "");
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function getVerse(s, a) {
  const surah = state.surahs[s - 1];
  return surah && surah.verses[a - 1];
}

function refLabel(s, a) {
  return `${state.surahs[s - 1].name} ${a}`;
}

function verseHtml(s, a, { clickable = false, highlightRoot = null, highlightWord = null } = {}) {
  const words = getVerse(s, a);
  const parts = words.map(([text, root, lemma], i) => {
    const hit = (highlightRoot && root === highlightRoot) ||
      (highlightWord && (normalize(text).includes(highlightWord) || normalize(lemma) === highlightWord));
    const cls = "word" + (hit ? " hit" : "");
    if (clickable && root) {
      return `<span class="${cls}" tabindex="0" role="link" data-root="${escapeHtml(root)}" title="الجذر: ${escapeHtml(root)}">${escapeHtml(text)}</span>`;
    }
    return hit ? `<span class="${cls}">${escapeHtml(text)}</span>` : escapeHtml(text);
  });
  return `<span class="quran">${parts.join(" ")} <span class="ayah-num">﴿${a}﴾</span></span>`;
}

// ---------- الصفحات ----------

function renderVerse(s, a) {
  if (!getVerse(s, a)) {
    app.innerHTML = `<p class="empty">الآية غير موجودة.</p>`;
    return;
  }
  $("surah").value = s;
  $("ayah").value = a;
  $("ayah").max = state.surahs[s - 1].verses.length;

  const prev = getVerse(s, a - 1) ? `<div class="context">${verseHtml(s, a - 1)}</div>` : "";
  const next = getVerse(s, a + 1) ? `<div class="context">${verseHtml(s, a + 1)}</div>` : "";
  const prevLink = getVerse(s, a - 1) ? `<a href="#${s}:${a - 1}">→ الآية السابقة</a>` : "<span></span>";
  const nextLink = getVerse(s, a + 1) ? `<a href="#${s}:${a + 1}">الآية التالية ←</a>` : "<span></span>";

  const items = state.related[`${s}:${a}`] || [];
  const top = items.length ? items[0][2] : 1;
  const relatedHtml = items.map(([rs, ra, score, ctx, phrase, roots, expression]) => {
    const chips = [];
    if (ctx) chips.push(`<span class="chip context">${CONTEXT_REASONS[ctx]}</span>`);
    if (phrase) chips.push(`<span class="chip phrase">عبارة مشتركة: <span class="q">${escapeHtml(phrase)}</span></span>`);
    if (expression) chips.push(`<span class="chip phrase">تعبير مشترك بصيغة أخرى: <span class="q">${escapeHtml(expression)}</span></span>`);
    if (roots) chips.push(`<span class="chip roots">جذور مشتركة: ${escapeHtml(roots.split(" ").join("، "))}</span>`);
    const width = Math.max(8, Math.round((score / top) * 100));
    return `
      <article class="card related" data-href="#${rs}:${ra}" tabindex="0">
        <div class="related-head">
          <a class="ref" href="#${rs}:${ra}">${refLabel(rs, ra)}</a>
          <span class="bar" title="درجة الارتباط: ${score}"><span style="width:${width}%"></span></span>
        </div>
        ${verseHtml(rs, ra)}
        <div class="chips">${chips.join("")}</div>
      </article>`;
  }).join("");

  app.innerHTML = `
    <section class="card main-verse">
      <div class="ref">سورة ${state.surahs[s - 1].name} · الآية ${a}</div>
      ${prev}
      ${verseHtml(s, a, { clickable: true })}
      ${next}
    </section>
    <div class="pager">${prevLink}${nextLink}</div>
    <h2>الآيات المفسِّرة <small>النقر على أي كلمة يعرض مواضع جذرها في القرآن</small></h2>
    ${relatedHtml || `<p class="empty">لم يُعثر على آيات مرتبطة.</p>`}
  `;
  document.title = `${refLabel(s, a)} · تفسير القرآن بالقرآن`;
}

function renderList(title, matches, opts) {
  const shown = matches.slice(0, MAX_RESULTS);
  const more = matches.length > MAX_RESULTS ? ` (تُعرض أول ${MAX_RESULTS})` : "";
  app.innerHTML = `
    <h2>${title} <small>${matches.length} آية${more}</small></h2>
    ${shown.map(([s, a]) => `
      <article class="card related" data-href="#${s}:${a}" tabindex="0">
        <a class="ref" href="#${s}:${a}">${refLabel(s, a)}</a>
        ${verseHtml(s, a, opts)}
      </article>`).join("") || `<p class="empty">لا توجد نتائج.</p>`}
  `;
}

function renderRoot(root) {
  renderList(`مواضع الجذر «${escapeHtml(root)}»`, state.rootIndex.get(root) || [], { highlightRoot: root });
  document.title = `الجذر ${root} · تفسير القرآن بالقرآن`;
}

function renderSearch(query) {
  const q = normalize(query);
  if (!q) return renderVerse(1, 1);
  // «الرحمن» تُكتب «للرحمن» بعد اللام، فنقارن أيضًا باللمّة دون «ال»
  const bare = q.startsWith("ال") && q.length > 3 ? q.slice(2) : q;
  const matches = state.normWords
    .filter(([, , words, lemmas]) => words.some((w) => w.includes(q)) || lemmas.includes(q) || lemmas.includes(bare))
    .map(([s, a]) => [s, a]);
  renderList(`نتائج البحث عن «${escapeHtml(query)}»`, matches, { highlightWord: q });
  document.title = `بحث: ${query} · تفسير القرآن بالقرآن`;
}

// ---------- التنقل ----------

function route() {
  const hash = decodeURIComponent(location.hash.slice(1));
  window.scrollTo(0, 0);
  if (hash.startsWith("root/")) return renderRoot(hash.slice(5));
  if (hash.startsWith("search/")) return renderSearch(hash.slice(7));
  const m = hash.match(/^(\d+):(\d+)$/);
  if (m) return renderVerse(+m[1], +m[2]);
  renderVerse(1, 1);
}

function setupControls() {
  $("surah").innerHTML = state.surahs
    .map((s) => `<option value="${s.n}">${s.n}. ${s.name}</option>`)
    .join("");
  $("surah").addEventListener("change", () => { location.hash = `${$("surah").value}:1`; });
  $("ayah").addEventListener("change", () => {
    const s = +$("surah").value;
    const max = state.surahs[s - 1].verses.length;
    const a = Math.min(Math.max(1, +$("ayah").value || 1), max);
    location.hash = `${s}:${a}`;
  });
  $("search-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = $("search").value.trim();
    if (!q) return;
    const root = q.match(/^جذر\s*[:：]\s*(.+)$/);
    location.hash = root ? `root/${root[1].replace(/\s+/g, "")}` : `search/${q}`;
  });

  // النقر على كلمة يفتح مواضع جذرها، والنقر على بطاقة يفتح الآية
  const activate = (e) => {
    const word = e.target.closest("[data-root]");
    if (word) { location.hash = `root/${word.dataset.root}`; return; }
    if (e.target.closest("a")) return;
    const card = e.target.closest("[data-href]");
    if (card) location.hash = card.dataset.href;
  };
  app.addEventListener("click", activate);
  app.addEventListener("keydown", (e) => { if (e.key === "Enter") activate(e); });
  window.addEventListener("hashchange", route);
}

function buildIndexes() {
  state.surahs.forEach((surah) => {
    surah.verses.forEach((words, i) => {
      const s = surah.n, a = i + 1;
      const roots = new Set(words.map((w) => w[1]).filter(Boolean));
      roots.forEach((r) => {
        if (!state.rootIndex.has(r)) state.rootIndex.set(r, []);
        state.rootIndex.get(r).push([s, a]);
      });
      state.normWords.push([s, a, words.map((w) => normalize(w[0])), words.map((w) => normalize(w[2]))]);
    });
  });
}

async function init() {
  try {
    const [quran, related] = await Promise.all([
      fetch("data/quran.json").then((r) => r.json()),
      fetch("data/related.json").then((r) => r.json()),
    ]);
    state.surahs = quran.surahs;
    state.related = related;
    buildIndexes();
    setupControls();
    route();
  } catch (err) {
    app.innerHTML = `<p class="empty">تعذّر تحميل البيانات. يجب تشغيل <code>python3 tools/build.py</code> ثم فتح التطبيق عبر خادم محلي.</p>`;
    console.error(err);
  }
}

init();
