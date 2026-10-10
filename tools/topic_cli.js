// يطبع خلاصة موضوع من سطر الأوامر، للتجربة والتقييم:
//   node tools/topic_cli.js الصلاة
//   node tools/topic_cli.js الصلاة --all   (مع نص كل الآيات)
//   node tools/topic_cli.js يوم القيامة    (عبارة)
const path = require("path");
const T = require(path.join(__dirname, "..", "web", "topic.js"));
const quran = require(path.join(__dirname, "..", "web", "data", "quran.json"));

const args = process.argv.slice(2);
const query = args.filter((x) => !x.startsWith("--")).join(" ");
const index = T.buildIndex(quran);
const r = T.resolveQuery(index, query);
const ref = (i) => `${index.verses[i].surahName} ${index.verses[i].a}`;
const text = (i) => index.verses[i].words.map((w) => w[0]).join(" ");
const disp = (k) => `${index.lemmas.get(k).display} (${index.lemmas.get(k).verses.length})`;

if (r.phrase) {
  console.log("عبارة:", r.phrase.map((p) => (p.prefix ? p.prefix + " " : "") + (p.surface ? `«${p.word}»` : p.lemmas.map(disp).join(" أو "))).join(" + "));
}
else console.log("اللمّات المختارة:", r.selected.map(disp).join("، ") || "—");
if (r.missing.length) console.log("كلمات لم تُفهم:", r.missing.join("، "));
if (r.alternatives.length) console.log("معانٍ أخرى:", r.alternatives.map(disp).join("، "));
console.log("من الجذر نفسه:", r.siblings.map(disp).join("، ") || "—");
if (r.suggestions.length) console.log("اقتراحات:", r.suggestions.map(disp).join("، "));
if (!r.selected.length) process.exit(0);

const idxs = r.phrase ? T.phraseVerses(index, r.phrase) : T.topicVerses(index, r.selected);
const sum = T.summarize(index, r.selected, idxs, r.phrase);
if (!sum.verses.length) { console.log("لا آيات."); process.exit(0); }
const plainFmt = { esc: (x) => x, phrase: (x) => `﴿${x}﴾`, quote: (i) => `﴿${text(i)}﴾ (${ref(i)})` };
console.log("\nالخلاصة:", T.summarySentences(index, sum, plainFmt).join(" "));
console.log(`\nعدد الآيات: ${sum.verses.length} في ${T.countAr(sum.surahs.length, "surah")}`);
console.log("أكثر السور:", sum.surahs.slice(0, 5).map((x) => `${x.name} (${x.count})`).join("، "));
console.log("يقترن به:", sum.cooccur.map((c) => `${c.display} (${c.count})`).join("، "));
console.log("الصيغ المتكررة:", sum.formulas.map((f) => `﴿${f.text}﴾ ×${f.count}`).join("، "));
if (sum.axes.skipped) console.log("المحاور: لم تُحسب (موضوع واسع)");
for (const ax of sum.axes.list) {
  console.log(`  محور [${ax.labels.join("، ")}] (${ax.verses.length}) — مثال: ${ref(ax.representative)}: ${text(ax.representative)}`);
  console.log(`    آياته: ${ax.verses.map(ref).join("، ")}`);
}
console.log(`  آيات خارج المحاور: ${sum.axes.rest}`);
console.log("أجمع الآيات:");
for (const i of sum.central) console.log(`  ${ref(i)}: ${text(i)}`);
const ctx = T.contextVerses(index, sum.verses);
console.log(`آيات السياق بين المواضع: ${ctx.length}`);
if (args.includes("--all") || process.env.ALL) for (const i of sum.verses) console.log(`- ${ref(i)}: ${text(i)}`);
