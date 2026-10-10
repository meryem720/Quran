// يطبع خلاصة موضوع من سطر الأوامر، للتجربة والتقييم:
//   node tools/topic_cli.js الصلاة
//   node tools/topic_cli.js الصلاة --all   (مع نص كل الآيات)
const path = require("path");
const T = require(path.join(__dirname, "..", "web", "topic.js"));
const quran = require(path.join(__dirname, "..", "web", "data", "quran.json"));

const args = process.argv.slice(2);
const query = args.filter((x) => !x.startsWith("--")).join(" ");
const index = T.buildIndex(quran.surahs);
const { selected, alternatives, siblings, suggestions } = T.resolveQuery(index, query);
const ref = (i) => `${index.verses[i].surahName} ${index.verses[i].a}`;
const text = (i) => index.verses[i].words.map((w) => w[0]).join(" ");
const disp = (k) => `${index.lemmas.get(k).display} (${index.lemmas.get(k).verses.length})`;

console.log("اللمّات المختارة:", selected.map(disp).join("، ") || "—");
if (alternatives.length) console.log("معانٍ أخرى:", alternatives.map(disp).join("، "));
console.log("من الجذر نفسه:", siblings.map(disp).join("، ") || "—");
if (suggestions.length) console.log("اقتراحات:", suggestions.map(disp).join("، "));
if (!selected.length) process.exit(0);

const sum = T.summarize(index, selected);
const plain = { esc: (x) => x, phrase: (x) => `﴿${x}﴾`, quote: (i) => `﴿${text(i)}﴾ (${ref(i)})` };
console.log("\nالخلاصة:", T.summarySentences(index, sum, plain).join(" "));
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
if (args.includes("--all") || process.env.ALL) for (const i of sum.verses) console.log(`- ${ref(i)}: ${text(i)}`);
