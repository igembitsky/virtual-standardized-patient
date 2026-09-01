// Reads a case file through the live parser and prompt builder in index.html.
// Usage: node bench/case.js index.html cases/graham.txt
// Prints JSON. The bench must test the real prompt, so nothing here is a copy.
const fs = require("fs");
const [,, html, casefile] = process.argv;
const src = fs.readFileSync(html, "utf8");
function grab(name) {
  const i = src.indexOf(`function ${name}(`);
  if (i < 0) throw new Error("no function " + name);
  let depth = 0;
  for (let k = src.indexOf("{", i); k < src.length; k++) {
    if (src[k] === "{") depth++;
    else if (src[k] === "}" && --depth === 0) return src.slice(i, k + 1);
  }
}
eval(grab("parseCase") + "\n" + grab("systemPrompt"));
const text = fs.readFileSync(casefile, "utf8");
const c = parseCase(text, casefile.split("/").pop());
c.system = systemPrompt(c);
c.raw = text;
process.stdout.write(JSON.stringify(c));
