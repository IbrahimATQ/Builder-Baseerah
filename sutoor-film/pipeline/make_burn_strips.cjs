#!/usr/bin/env node
/* Print-ready calligraphy strips for filming REAL burns (the reference reel is a real strip of
 * handwritten calligraphy burning on the ground, filmed on a phone; a simulation never matched it).
 *
 * One hemistich per strip, exactly as supplied in data/poem.json (harakat untouched), set in Amiri
 * Bold and shaped by Chromium/HarfBuzz. A4 landscape, three strips per page with cut lines, the
 * three strips the film needs most marked with a star outside the cut line, then a one-page guide.
 *
 * Usage: node make_burn_strips.cjs POEM.json FONT.ttf OUT.pdf
 */
const fs = require("fs");
const path = require("path");
const { chromium } = require("playwright");

const [poemPath, fontPath, outPath] = process.argv.slice(2);
if (!poemPath || !fontPath || !outPath) {
  console.error("usage: node make_burn_strips.cjs POEM.json FONT.ttf OUT.pdf");
  process.exit(2);
}
const poem = JSON.parse(fs.readFileSync(poemPath, "utf8"));
const font = fs.readFileSync(fontPath).toString("base64");
const KEY = new Set(["1a", "4b", "6b"]); // opening, middle and closing burns
const strips = [];
for (const v of poem.verses) {
  strips.push({ id: `${v.n}a`, text: v.sadr });
  strips.push({ id: `${v.n}b`, text: v.ajuz });
}
const pages = [];
for (let i = 0; i < strips.length; i += 3) pages.push(strips.slice(i, i + 3));

const guide = [
  ["Print and cut", "Print pages 1–4 at 100 % on plain thin paper (ordinary 80 g printer paper is right; thinner burns even better). Cut along the dashed lines. The three strips marked ★ are the ones the film needs most; burn any others you like."],
  ["Choose a safe place", "Outdoors at dusk or at night, with no wind. Lay the strip on something that cannot burn: stone, tiles, concrete, sand or gravel, away from anything dry. Keep a bucket of water next to you."],
  ["Set the phone", "Rest the phone on a stand or lean it against something so it does not move. Hold it upright (vertical) and frame the strip so it fills most of the width. Camera: 4K at 60 fps (or 30), flash off."],
  ["Lock the picture", "Tap and hold on the paper until AE/AF LOCK appears, then drag the sun icon down a little, so the paper does not turn pure white when the fire lights it."],
  ["Burn it", "Press record and wait three seconds. Light the RIGHT end of the strip, where the line begins, and take your hand out of the frame. Keep recording until the fire is out, and five seconds more."],
  ["Three different scenes", "Burn each ★ strip somewhere different: on stone or paving, on sand or soil, in a metal tray or on a ceramic plate. If you can, film one extra take of each."],
  ["Optional, as in your reference", "Five seconds of a hand holding a strip above a carpet or a wooden table, with a pen and the lighter lying beside it."],
  ["Send the clips", "Upload the original video files here in the chat (not through WhatsApp, which shrinks them)."],
];

const html = `<!doctype html><html><head><meta charset="utf-8"><style>
@font-face { font-family: "AmiriP"; src: url(data:font/ttf;base64,${font}) format("truetype"); font-weight: 700; }
@page { size: A4 landscape; margin: 0; }
* { box-sizing: border-box; }
body { margin: 0; font-family: Georgia, serif; color: #000; }
.page { width: 297mm; height: 210mm; padding: 6mm 10mm; page-break-after: always; display: flex; flex-direction: column; justify-content: space-between; }
.row { position: relative; height: 62mm; display: flex; align-items: center; justify-content: center; }
.strip { width: 262mm; height: 58mm; border: 0.3mm dashed #9a9a9a; display: flex; align-items: center; justify-content: center; overflow: hidden; }
.ar { font-family: "AmiriP"; font-weight: 700; direction: rtl; white-space: nowrap; line-height: 1.9; font-size: 64pt; }
.tag { position: absolute; left: 0; top: 50%; transform: translateY(-50%); width: 8mm; text-align: center; font: 9pt Georgia, serif; color: #666; }
.star { display: block; font-size: 15pt; color: #000; }
.guide { padding: 14mm 20mm; display: block; }
.guide h1 { font: 700 19pt Georgia, serif; margin: 0 0 2mm; }
.guide p.lead { font: 11pt Georgia, serif; margin: 0 0 6mm; color: #333; }
.guide ol { margin: 0; padding-left: 7mm; }
.guide li { font: 11pt/1.45 Georgia, serif; margin-bottom: 3.2mm; }
.guide li b { font-weight: 700; }
.guide .safe { margin-top: 5mm; padding: 3mm 4mm; border: 0.4mm solid #000; font: 10.5pt/1.4 Georgia, serif; }
</style></head><body>
${pages.map((pg) => `<div class="page">${pg.map((s) => `
  <div class="row"><div class="tag">${KEY.has(s.id) ? '<span class="star">★</span>' : ""}${s.id}</div>
  <div class="strip"><span class="ar" data-fit>${s.text}</span></div></div>`).join("")}</div>`).join("")}
<div class="page guide">
  <h1>Filming the burns on an iPhone</h1>
  <p class="lead">Your reference reel is a real strip of calligraphy really burning, filmed on a phone. These steps give the same thing with this poem's lines.</p>
  <ol>${guide.map(([h, t]) => `<li><b>${h}.</b> ${t}</li>`).join("")}</ol>
  <div class="safe"><b>Safety.</b> Burn one strip at a time, never indoors and never near dry plants, fuel or fabric. Do not hold a burning strip in your fingers. Pour water over the ashes when you finish.</div>
</div>
<script>
  // fit every line to the same width budget, keeping one size for all strips (the smallest that fits)
  document.fonts.ready.then(() => {
    const els = [...document.querySelectorAll("[data-fit]")];
    const mm = (v) => (v * 96) / 25.4;
    let size = 64;
    const widest = () => Math.max(...els.map((e) => e.getBoundingClientRect().width));
    while (widest() > mm(238) && size > 30) { size -= 1; els.forEach((e) => (e.style.fontSize = size + "pt")); }
    document.body.setAttribute("data-size", String(size));
    document.body.setAttribute("data-ready", "1");
  });
</script></body></html>`;

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setContent(html, { waitUntil: "load" });
  await page.waitForSelector("body[data-ready='1']");
  const size = await page.getAttribute("body", "data-size");
  const shown = await page.$$eval("[data-fit]", (els) => els.map((e) => e.textContent));
  await page.pdf({ path: outPath, format: "A4", landscape: true, printBackground: true, preferCSSPageSize: true });
  await browser.close();
  const ok = shown.length === strips.length && shown.every((t, i) => t === strips[i].text);
  console.log(JSON.stringify({ out: path.resolve(outPath), strips: strips.length, font_pt: Number(size), text_identical: ok }));
  process.exit(ok ? 0 : 1);
})();
