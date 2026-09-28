// Runs the page's own logic from app/index.html, so the harness tests the real thing, not a copy.
// Parser, prompt, jargon catch, question credit, examination matcher and note marking.
//
//   node bench/page.js app/index.html app/cases/graham.txt            prints the parsed case as JSON
//   node bench/page.js app/index.html app/cases/graham.txt --check    reads a request on stdin:
//     {"ask": ["question", ...], "said": [patient replies so far], "examine": ["part", ...],
//      "notes": [{"dx": [...], "tx": [...]}]}
//   and prints, in the same order:
//     {"ask": [{"jargon": word|null, "credits": [labels]}], "examine": [{"name", "finding"}],
//      "notes": [{"dxHit", "txHit", "pass"}]}
const fs = require("fs");
const [,, html, casefile, mode] = process.argv;
const src = fs.readFileSync(html, "utf8");

function grab(name) {
  const i = src.indexOf(`function ${name}(`);
  if (i < 0) throw new Error("index.html has no function " + name);
  let depth = 0;
  for (let k = src.indexOf("{", i); k < src.length; k++) {
    if (src[k] === "{") depth++;
    else if (src[k] === "}" && --depth === 0) return src.slice(i, k + 1);
  }
}
function between(start, end) {
  const i = src.indexOf(start), j = src.indexOf(end, i);
  if (i < 0 || j < 0) throw new Error("index.html has no " + start);
  return src.slice(i, j);
}

// The page keeps its state in `app` and redraws the dots. Stand-ins for both.
var app = { current: null, covered: new Set(), exams: [], examMiss: null };
function drawDots() {}
eval([grab("parseCase"), grab("systemPrompt"), grab("wordHit"), grab("plainWords"), grab("jargonWord"), grab("noteStem"), grab("noteToks"), grab("factNote"), grab("markCovered"), grab("hasAny"),
      grab("examSetup"), grab("examFind"), grab("firstNamed"),
      src.match(/const JARGON = \/[\s\S]*?\/i;\n/)[0].replace("const JARGON", "var JARGON"),
      between("const NOTE_STOP = ", "function noteStem(").replace(/\bconst (NOTE_STOP|NOTE_WORDS)\b/g, "var $1"),
      between("const OPEN_Q = ", "function factNote(").replace(/\bconst (OPEN_Q|RECAP_Q)\b/g, "var $1"),
      between("const EXAMS = [", "function examSetup(").replace(/\bconst (EXAMS|EXAM_ITEMS)\b/g, "var $1")
     ].join("\n"));

const text = fs.readFileSync(casefile, "utf8");
const c = parseCase(text, casefile.split("/").pop());
c.system = systemPrompt(c);
c.jargon = JARGON.source;
c.raw = text;

if (mode !== "--check") { process.stdout.write(JSON.stringify(c)); return; }

const req = JSON.parse(fs.readFileSync(0, "utf8") || "{}");
app.current = c;
examSetup(c);
const out = {
  // Credit for one question on its own, as the page gives it: nothing if the jargon catch fires.
  ask: (req.ask || []).map(q => {
    const jw = jargonWord(c, q);
    app.covered = new Set();
    if (!jw) markCovered(q);
    return { jargon: jw, note: jw ? "" : factNote(c, q, req.said || []),
             credits: c.questions.filter(x => app.covered.has(x.id)).map(x => x.label) };
  }),
  // The same line the page shows after "examine <part>".
  examine: (req.examine || []).map(q => {
    const it = examFind(q);
    if (!it) return { name: null, finding: `No examination matches "${q}".` };
    return { name: it.name, finding: it.finding || app.examMiss || `${it.name}: nothing abnormal.` };
  }),
  // The page's mark(): a pass needs one pass word among the diagnoses and one among the tests.
  notes: (req.notes || []).map(n => {
    const dxHit = hasAny((n.dx || []).join("\n"), c.answer.dxWords);
    const txHit = hasAny((n.tx || []).join("\n"), c.answer.txWords);
    return { dxHit, txHit, pass: dxHit && txHit };
  })
};
process.stdout.write(JSON.stringify(out));
