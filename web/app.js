"use strict";

// أسباب السياق (نفس الرموز في tools/build.py)
const CONTEXT_REASONS = {
  1: "جواب ﴿وما أدراك﴾ في السياق",
  2: "صفة متصلة بالآية السابقة",
  3: "جواب الاستفهام في الآية التالية",
  4: "جواب السؤال في الآية التالية",
};
const MAX_RESULTS = 200;
const TOPIC_PAGE = 40;
const SUGGESTED_TOPICS = [
  "الصلاة", "الزكاة", "الصيام", "الحج", "الصبر", "التوبة", "الشكر", "الرحمة", "التقوى",
  "الجنة", "النار", "القرآن", "اليتيم", "الربا", "الظلم",
  "موسى", "إبراهيم", "عيسى", "مريم", "يوسف", "نوح", "فرعون", "إبليس",
];
const T = window.QuranTopic;

const state = {
  surahs: [],     // [{n, name, verses: [[[نص، جذر، لمّة], ...], ...]}]
  related: {},    // "s:a" -> [[s, a, درجة، سياق، عبارة، جذور]]
  rootIndex: new Map(), // جذر -> [[s, a], ...]
  normWords: [],  // [[s, a, [كلمات موحّدة], [لمّات موحّدة]], ...]
  topicIndex: null, // فهرس الموضوعات (web/topic.js)
  topicMore: null,  // دالة «عرض المزيد» في صفحة الموضوع
};

const $ = (id) => document.getElementById(id);
const app = $("app");

const normalize = T.normalize;

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

function verseHtml(s, a, { clickable = false, highlightRoot = null, highlightWord = null, highlightLemmas = null } = {}) {
  const words = getVerse(s, a);
  const parts = words.map(([text, root, lemma]) => {
    const hit = (highlightRoot && root === highlightRoot) ||
      (highlightLemmas && highlightLemmas.has(lemma)) ||
      (highlightWord && (normalize(text).includes(highlightWord) || normalize(lemma) === highlightWord));
    const cls = "word" + (hit ? " hit" : "");
    if (clickable && root) {
      return `<span class="${cls}" tabindex="0" role="link" data-root="${escapeHtml(root)}" title="الجذر: ${escapeHtml(root)}">${escapeHtml(text)}</span>`;
    }
    return hit ? `<span class="${cls}">${escapeHtml(text)}</span>` : escapeHtml(text);
  });
  return `<span class="quran">${parts.join(" ")} <span class="ayah-num">﴿${a}﴾</span></span>`;
}

// سبب الرابط بين آيتين: عنصر من related.json
// [سورة، آية، الدرجة، السياق، العبارة المشتركة، الجذور المشتركة، التعبير المشترك]
function reasonChips([, , , ctx, phrase, roots, expression]) {
  const chips = [];
  if (Array.isArray(ctx)) {
    // [5، سورة السؤال، آيته، العبارة]: العبارة نفسها سُئل عنها في موضع آخر وهذه الآية جوابها
    const [, qs, qa, qPhrase] = ctx;
    chips.push(`<span class="chip context">جواب ﴿<span class="q">${escapeHtml(qPhrase)}</span>﴾ في <a href="#${qs}:${qa}">${refLabel(qs, qa)}</a></span>`);
  } else if (ctx) {
    chips.push(`<span class="chip context">${CONTEXT_REASONS[ctx]}</span>`);
  }
  if (phrase) chips.push(`<span class="chip phrase">عبارة مشتركة: <span class="q">${escapeHtml(phrase)}</span></span>`);
  if (expression) chips.push(`<span class="chip phrase">تعبير مشترك بصيغة أخرى: <span class="q">${escapeHtml(expression)}</span></span>`);
  if (roots) chips.push(`<span class="chip roots">جذور مشتركة: ${escapeHtml(roots.split(" ").join("، "))}</span>`);
  return chips.join("");
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
  const relatedHtml = items.map((item) => {
    const [rs, ra, score] = item;
    const width = Math.max(8, Math.round((score / top) * 100));
    return `
      <article class="card related" data-href="#${rs}:${ra}" tabindex="0">
        <div class="related-head">
          <a class="ref" href="#${rs}:${ra}">${refLabel(rs, ra)}</a>
          <span class="bar" title="درجة الارتباط: ${score}"><span style="width:${width}%"></span></span>
        </div>
        ${verseHtml(rs, ra)}
        <div class="chips">${reasonChips(item)}</div>
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

// ---------- الموضوعات ----------

function topicHash(query, lemmas) {
  return "#topic/" + encodeURIComponent(query + (lemmas ? "|" + lemmas.join(",") : ""));
}

function ayahLink(i) {
  const v = state.topicIndex.verses[i];
  return `<a href="#${v.s}:${v.a}">${refLabel(v.s, v.a)}</a>`;
}

function renderTopics() {
  app.innerHTML = `
    <section class="card">
      <h2>البحث بالموضوع</h2>
      <p>اكتب موضوعًا في خانة البحث (مثل: الصلاة، الصبر، موسى) فتظهر كل الآيات التي ورد فيها،
        ومع كل آية الآيات التي تبيّنها من القرآن، وفي الأخير خلاصة الموضوع مستخرجة من ألفاظ الآيات نفسها.</p>
      <div class="topics-grid">
        ${SUGGESTED_TOPICS.map((t) => `<a class="topic-link" href="${topicHash(t)}">${t}</a>`).join("")}
      </div>
    </section>`;
  document.title = "الموضوعات · تفسير القرآن بالقرآن";
}

// خانات اختيار الكلمات: المختارة، والمعاني الأخرى للصيغة، وكلمات الجذر نفسه
function lemmaChips(query, selected, options) {
  const idx = state.topicIndex;
  return options.map(({ key, kind }) => {
    const on = selected.includes(key);
    const next = on ? selected.filter((k) => k !== key) : selected.concat(key);
    const info = idx.lemmas.get(key);
    const title = kind === "alt" ? "معنى آخر للصيغة نفسها" : kind === "sibling" ? "من الجذر نفسه" : "";
    return `<a class="lemma-chip${on ? " on" : ""}" href="${topicHash(query, next)}" title="${title}" aria-pressed="${on}">
      ${on ? "✓ " : "+ "}${escapeHtml(info.display)} <small>${info.verses.length}</small></a>`;
  }).join("");
}

function renderTopic(arg) {
  const idx = state.topicIndex;
  const [query, selRaw] = arg.split("|");
  const resolved = T.resolveQuery(idx, query);
  const selected = selRaw !== undefined
    ? selRaw.split(",").filter((k) => idx.lemmas.has(k))
    : resolved.selected;

  const options = [];
  const seen = new Set();
  const addOption = (key, kind) => { if (!seen.has(key)) { seen.add(key); options.push({ key, kind }); } };
  resolved.selected.forEach((k) => addOption(k, "main"));
  selected.forEach((k) => addOption(k, "main"));
  resolved.alternatives.forEach((k) => addOption(k, "alt"));
  resolved.siblings.forEach((k) => addOption(k, "sibling"));

  document.title = `${query} · تفسير القرآن بالقرآن`;
  const wordSearch = `<a href="#search/${encodeURIComponent(query)}">البحث الحرفي عن «${escapeHtml(query)}»</a>`;

  if (!options.length) {
    const sugg = resolved.suggestions.map((k) => {
      const info = idx.lemmas.get(k);
      return `<a class="topic-link" href="${topicHash(info.display)}">${escapeHtml(info.display)} <small>${info.verses.length}</small></a>`;
    }).join("");
    app.innerHTML = `
      <section class="card">
        <h2>لم يُعثر على موضوع «${escapeHtml(query)}»</h2>
        ${sugg ? `<p>كلمات قريبة:</p><div class="topics-grid">${sugg}</div>` : ""}
        <p>${wordSearch} · <a href="#topics">الموضوعات المقترحة</a></p>
      </section>`;
    return;
  }

  const chipsHtml = `
    <div class="lemma-chips">${lemmaChips(query, selected, options)}</div>
    <p class="hint">الكلمات المعلَّمة ✓ هي التي تُجمع آياتها. يمكن إضافة كلمات أخرى من الجذر نفسه أو حذفها.
      · ${wordSearch}</p>`;

  if (!selected.length) {
    app.innerHTML = `<section class="card"><h2>موضوع: ${escapeHtml(query)}</h2>${chipsHtml}
      <p class="empty">اختر كلمة واحدة على الأقل.</p></section>`;
    return;
  }

  const sum = T.summarize(idx, selected);
  const lemmaSet = new Set(selected);
  const axisOf = new Map();
  (sum.axes.list || []).forEach((ax) => ax.verses.forEach((i) => axisOf.set(i, ax.labels.join("، "))));

  const verseCard = (i) => {
    const v = idx.verses[i];
    const related = (state.related[`${v.s}:${v.a}`] || []).slice(0, 3);
    const axis = axisOf.get(i);
    return `
      <article class="card topic-verse">
        <div class="related-head">
          <a class="ref" href="#${v.s}:${v.a}">${refLabel(v.s, v.a)}</a>
          ${axis ? `<span class="chip axis">المحور: ${escapeHtml(axis)}</span>` : ""}
        </div>
        ${verseHtml(v.s, v.a, { highlightLemmas: lemmaSet })}
        ${related.length ? `
        <details class="explain">
          <summary>بيانها من القرآن (${related.length})</summary>
          ${related.map((item) => `
            <div class="explain-item">
              <a class="ref" href="#${item[0]}:${item[1]}">${refLabel(item[0], item[1])}</a>
              ${verseHtml(item[0], item[1])}
              <div class="chips">${reasonChips(item)}</div>
            </div>`).join("")}
        </details>` : ""}
      </article>`;
  };

  app.innerHTML = `
    <section class="card topic-head">
      <h2>موضوع: ${escapeHtml(query)} <small>${T.countAr(sum.verses.length, "ayah")}</small></h2>
      ${chipsHtml}
      <p><a href="#" data-scroll="summary">الانتقال إلى الخلاصة ↓</a></p>
    </section>
    <div id="topic-verses"></div>
    <div id="topic-more"></div>
    ${summaryHtml(sum)}
  `;

  let shown = 0;
  state.topicMore = () => {
    const next = sum.verses.slice(shown, shown + TOPIC_PAGE);
    $("topic-verses").insertAdjacentHTML("beforeend", next.map(verseCard).join(""));
    shown += next.length;
    const left = sum.verses.length - shown;
    $("topic-more").innerHTML = left > 0
      ? `<button class="more" data-more>عرض المزيد (${T.countAr(left, "ayah").replace(/^في /, "")} باقية)</button>`
      : "";
  };
  state.topicMore();
}

// الخلاصة: كلها من ألفاظ الآيات (إحصاء وتجميع)، لا تفسير خارجي
function summaryHtml(sum) {
  const idx = state.topicIndex;
  const verseText = (i) => idx.verses[i].words.map((w) => w[0]).join(" ");
  const quote = (i) => `﴿<span class="q">${escapeHtml(verseText(i))}</span>﴾ (${ayahLink(i)})`;
  const sentences = T.summarySentences(idx, sum, {
    esc: escapeHtml,
    quote,
    phrase: (text) => `﴿<span class="q">${escapeHtml(text)}</span>﴾`,
  });

  const cooccurHtml = sum.cooccur.map((c) =>
    `<a class="topic-link" href="${topicHash(c.display)}" title="مثال: ${refLabel(idx.verses[c.example].s, idx.verses[c.example].a)}">
      ${escapeHtml(c.display)} <small>${c.count}</small></a>`).join("");

  const formulasHtml = sum.formulas.map((f) =>
    `<li>﴿<span class="q">${escapeHtml(f.text)}</span>﴾ — ${T.countAr(f.count, "times")}، مثل ${ayahLink(f.example)}</li>`).join("");

  const axesHtml = sum.axes.skipped
    ? `<p class="hint">الموضوع واسع (${T.countAr(sum.verses.length, "ayah")})، فلم تُحسب محاوره. يمكن اختيار كلمة أدق.</p>`
    : axes.map((ax) => `
      <div class="axis-block">
        <h4>${escapeHtml(ax.labels.join("، "))} <small>${T.countAr(ax.verses.length, "ayah")}</small></h4>
        <div class="quote">${quote(ax.representative)}</div>
        <p class="refs">${ax.verses.map(ayahLink).join("، ")}</p>
      </div>`).join("") +
      (sum.axes.rest ? `<p class="hint">و${T.countAr(sum.axes.rest, "ayah")} لا تشترك في ألفاظها مع غيرها بما يكفي لتكوين محور.</p>` : "");

  const centralHtml = sum.central.map((i) => `<div class="quote">${quote(i)}</div>`).join("");
  const surahsHtml = sum.surahs.slice(0, 12).map((x) =>
    `<span class="chip roots">${x.name} ${x.count}</span>`).join("");

  return `
    <section id="summary" class="card summary">
      <h2>الخلاصة</h2>
      <p class="summary-text">${sentences.join(" ")}</p>
      ${cooccurHtml ? `<h3>ما يقترن به في القرآن</h3><div class="topics-grid">${cooccurHtml}</div>` : ""}
      ${formulasHtml ? `<h3>الصيغ المتكررة</h3><ul class="formulas">${formulasHtml}</ul>` : ""}
      ${axesHtml ? `<h3>محاور الموضوع</h3>${axesHtml}` : ""}
      ${centralHtml ? `<h3>أجمع الآيات</h3><p class="hint">الآيات التي تجمع أكثر ما يقترن بالموضوع من ألفاظ.</p>${centralHtml}` : ""}
      <h3>توزّعه على السور</h3><div class="chips">${surahsHtml}</div>
      <p class="hint note">هذه الخلاصة مستخرجة آليًا من ألفاظ الآيات نفسها (ما يتكرر معها، وما يتشابه منها)،
        وليست تفسيرًا من خارج القرآن.</p>
    </section>`;
}

// ---------- التنقل ----------

function route() {
  const hash = decodeURIComponent(location.hash.slice(1));
  window.scrollTo(0, 0);
  if (hash.startsWith("root/")) return renderRoot(hash.slice(5));
  if (hash.startsWith("search/")) return renderSearch(hash.slice(7));
  if (hash.startsWith("topic/")) return renderTopic(hash.slice(6));
  if (hash === "topics") return renderTopics();
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
    location.hash = root ? `root/${root[1].replace(/\s+/g, "")}` : topicHash(q.replace(/[|,]/g, " ").trim());
  });

  // النقر على كلمة يفتح مواضع جذرها، والنقر على بطاقة يفتح الآية
  const activate = (e) => {
    if (e.target.closest("[data-more]")) { if (state.topicMore) state.topicMore(); return; }
    const scroll = e.target.closest("[data-scroll]");
    if (scroll) { e.preventDefault(); $(scroll.dataset.scroll).scrollIntoView({ behavior: "smooth" }); return; }
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
    state.topicIndex = T.buildIndex(quran.surahs);
    buildIndexes();
    setupControls();
    route();
  } catch (err) {
    app.innerHTML = `<p class="empty">تعذّر تحميل البيانات. يجب تشغيل <code>python3 tools/build.py</code> ثم فتح التطبيق عبر خادم محلي.</p>`;
    console.error(err);
  }
}

init();
