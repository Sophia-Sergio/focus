#!/usr/bin/env python3
"""Build a local survey review page for one folder of extracted surveys.

Usage:
    python3 2026-09/scripts/build/build_review_page.py [FOLDER] [--out DIR] [--dpi 110]

FOLDER defaults to "2026-09/pdfs/BIOBÍO/Colegio Edward/4A". For every <name>.json that has a
<name>.pdf next to it, renders the PDF pages to JPEG and writes <out>/index.html (default
2026-09/review/<folder name>/): page images on the left, extracted metadata + answers on the right,
Prev/Next, keyboard arrows, and per-survey OK / flagged status (saved in the browser, exportable to CSV).
Everything is local; the folder contains scans of students, so it is git-ignored.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import pdf2image

REPO = Path(__file__).resolve().parents[3]
DEFAULT_FOLDER = REPO / "2026-09" / "pdfs" / "BIOBÍO" / "Colegio Edward" / "4A"

HEAD = r"""<title>Revisión de encuestas</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>
:root{--bg:#f6f5f2;--panel:#fff;--ink:#1c1b19;--muted:#6b6962;--line:#e2dfd8;--accent:#2f5d50;--accent-ink:#fff;
--ok:#1f7a4d;--ok-bg:#e3f3ea;--warn:#b4561b;--warn-bg:#fbeadc;--bad:#b3261e;--bad-bg:#fbe3e1;--row:#f1efe9}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#161614;--panel:#201f1c;--ink:#ecebe6;--muted:#a09d94;--line:#34322d;--accent:#7fc4ad;--accent-ink:#10231d;
--ok:#6fd0a0;--ok-bg:#183326;--warn:#f0a56a;--warn-bg:#3a2a1a;--bad:#f2928b;--bad-bg:#3b1f1d;--row:#292824;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#161614;--panel:#201f1c;--ink:#ecebe6;--muted:#a09d94;--line:#34322d;--accent:#7fc4ad;--accent-ink:#10231d;
--ok:#6fd0a0;--ok-bg:#183326;--warn:#f0a56a;--warn-bg:#3a2a1a;--bad:#f2928b;--bad-bg:#3b1f1d;--row:#292824;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
body::before{content:"";position:fixed;inset:0 0 auto;height:env(safe-area-inset-top,0px);z-index:10;background:var(--panel)}
header{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:var(--panel);border-bottom:1px solid var(--line);display:flex;gap:12px;align-items:center;padding-block:10px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));flex-wrap:wrap}
h1{font-size:15px;margin:0;font-weight:650}
.sp{flex:1}
.count{font-variant-numeric:tabular-nums;color:var(--muted)}
button{font:inherit;border:1px solid var(--line);background:var(--panel);color:var(--ink);padding:7px 14px;border-radius:8px;cursor:pointer}
button:hover{border-color:var(--accent)}
button.primary{background:var(--accent);color:var(--accent-ink);border-color:var(--accent);font-weight:600}
button.ok{background:var(--ok-bg);color:var(--ok);border-color:var(--ok)}
button.flag{background:var(--warn-bg);color:var(--warn);border-color:var(--warn)}
button:disabled{opacity:.4;cursor:default}
select{font:inherit;padding:6px;border-radius:8px;border:1px solid var(--line);background:var(--panel);color:var(--ink);max-width:230px}
.bar{height:4px;background:var(--line)}.bar i{display:block;height:100%;background:var(--accent);width:0}
main{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1fr);gap:16px;padding-block:16px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));max-width:1500px;margin:0 auto}
@media (max-width:900px){main{grid-template-columns:1fr}}
.card{min-width:0;background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}
.card h2{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:0;padding:10px 14px;border-bottom:1px solid var(--line)}
.tabs{display:flex;gap:6px;padding:10px 14px;border-bottom:1px solid var(--line);flex-wrap:wrap}
.tabs button{padding:4px 10px}.tabs button.on{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}
.scan{max-height:calc(100dvh - 190px);overflow:auto;padding:10px;background:var(--row)}
.scan img{display:block;width:100%;height:auto;border-radius:4px;cursor:zoom-in;background:#fff}
.scan.zoom img{width:190%;cursor:zoom-out}
.meta{display:grid;grid-template-columns:auto 1fr;gap:4px 14px;padding:12px 14px;margin:0}
.meta dt{color:var(--muted)}.meta dd{margin:0;font-weight:560;overflow-wrap:anywhere}
.chips{display:flex;gap:6px;flex-wrap:wrap;padding:0 14px 12px}
.chip{padding:2px 9px;border-radius:999px;font-size:12px;border:1px solid var(--line);background:var(--row)}
.chip.ok{background:var(--ok-bg);color:var(--ok);border-color:transparent}.chip.warn{background:var(--warn-bg);color:var(--warn);border-color:transparent}.chip.bad{background:var(--bad-bg);color:var(--bad);border-color:transparent}
table{width:100%;border-collapse:collapse}
th,td{padding:5px 14px;text-align:left;border-top:1px solid var(--line);vertical-align:top}
th{font-size:12px;color:var(--muted);font-weight:600;position:sticky;top:0;background:var(--panel)}
td.q{width:44px;color:var(--muted);font-variant-numeric:tabular-nums}
td.a{white-space:nowrap}
.ans{display:inline-block;min-width:20px;text-align:center;border-radius:6px;padding:0 6px;background:var(--row);font-weight:650;margin-right:6px}
tr.nul td{background:var(--bad-bg)}tr.nul .ans{background:transparent;color:var(--bad)}
.note{color:var(--warn);font-size:12px}
.rev{padding:12px 14px;display:grid;gap:8px}
textarea{width:100%;min-height:60px;font:inherit;padding:8px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--ink);resize:vertical}
.right{display:grid;gap:16px;align-content:start;min-width:0}
.csv{width:100%;min-height:150px;font:12px ui-monospace,monospace;white-space:pre}
.exp{padding:12px 14px;display:grid;gap:8px}
.answers{max-height:60vh;overflow:auto}
kbd{font:11px ui-monospace,monospace;border:1px solid var(--line);border-radius:4px;padding:0 4px;color:var(--muted)}
.hint{color:var(--muted);font-size:12px;padding:0 14px 12px}
</style>
"""

BODY = r"""<header>
  <h1 id="title"></h1>
  <span class="count" id="count"></span>
  <select id="jump" aria-label="Ir a encuesta"></select>
  <span class="sp"></span>
  <button id="prev">← Anterior</button>
  <button id="next" class="primary">Siguiente →</button>
  <button id="export">Exportar revisión</button>
</header>
<div class="bar"><i id="bar"></i></div>
<main>
  <section class="card" id="exportcard" hidden style="grid-column:1/-1">
    <h2>Revisión (CSV)</h2>
    <div class="exp">
      <textarea class="csv" id="csv" readonly></textarea>
      <div style="display:flex;gap:8px;align-items:center"><button id="copy" class="primary">Copiar</button><span class="count" id="copied"></span><span class="sp"></span><button id="closeexp">Cerrar</button></div>
    </div>
  </section>
  <section class="card">
    <h2>Escaneo</h2>
    <div class="tabs" id="tabs"></div>
    <div class="scan" id="scan"></div>
  </section>
  <div class="right">
    <section class="card">
      <h2>Datos extraídos</h2>
      <dl class="meta" id="meta"></dl>
      <div class="chips" id="chips"></div>
    </section>
    <section class="card">
      <h2>Respuestas</h2>
      <div class="answers"><table><thead><tr><th>#</th><th>Respuesta</th><th>Pregunta / notas</th></tr></thead><tbody id="rows"></tbody></table></div>
    </section>
    <section class="card">
      <h2>Revisión</h2>
      <div class="rev">
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <button id="markok" class="ok">✓ Correcta (O)</button>
          <button id="markflag" class="flag">⚑ Con error (F)</button>
          <button id="clear">Limpiar</button>
        </div>
        <textarea id="note" placeholder="Nota (p. ej. 'P19 es 3, no 2')"></textarea>
      </div>
      <div class="hint"><kbd>←</kbd> <kbd>→</kbd> navegar · <kbd>O</kbd> correcta y siguiente · <kbd>F</kbd> marcar error · clic en la imagen para ampliar</div>
    </section>
  </div>
</main>
<script>
const DATA = __DATA__;
const FOLDER = DATA.folder, S = DATA.surveys;
const SC1 = ["No es cierto","Poco cierto","Bastante cierto","Muy cierto"], SC2 = ["Nunca","Rara vez","A veces","Siempre"];
const KEY = "review:" + FOLDER;
let state = {}; try { state = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) {}
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} };
let idx = 0, page = 0;
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const st = s => state[s.id] || {};

function label(s, q) {
  const sc = q <= s.scale1_end ? SC1 : SC2;
  return sc;
}
function render() {
  const s = S[idx], r = st(s);
  $("title").textContent = FOLDER;
  $("count").textContent = `Encuesta ${idx + 1} / ${S.length} · ${s.id}`;
  const done = S.filter(x => st(x).status).length;
  $("bar").style.width = (done / S.length * 100) + "%";
  $("prev").disabled = idx === 0; $("next").disabled = idx === S.length - 1;
  $("jump").value = idx;
  // pages
  $("tabs").innerHTML = s.pages.map((p, i) => `<button class="${i === page ? "on" : ""}" data-p="${i}">Pág. ${i + 1}</button>`).join("") + `<button data-p="all" class="${page === "all" ? "on" : ""}">Todas</button>`;
  $("scan").innerHTML = (page === "all" ? s.pages : [s.pages[page]]).map(p => `<img loading="lazy" src="${p}" alt="">`).join("");
  $("scan").scrollTop = 0;
  // meta
  const m = s.meta, rows = [
    ["Archivo", s.file + (m.original_filename && m.original_filename !== s.file ? ` <span style="color:var(--muted)">(antes ${esc(m.original_filename)})</span>` : "")],
    ["Folio", esc(m.final_folio || m.folio || "—") + (m.folio_source ? ` <span style="color:var(--muted)">(${m.folio_source === "assigned" ? "asignado" : "impreso"})</span>` : "")],
    ["Nombre", esc(m.student_name)], ["RUN", esc(m.student_run ?? "—")],
    ["Sexo", ({1:"Hombre",2:"Mujer",3:"Prefiero no decir"})[m.student_gender] ?? "—"],
    ["Edad", esc(m.student_age ?? "—")], ["Fecha", esc(m.date ?? "—")], ["Tipo", esc(m.type ?? "—")],
    ["Cursos / rango", esc((m.school_name || "") + " · " + (m.grade_folder || "") + " · " + (m.grade_range || ""))],
  ];
  $("meta").innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");
  const nulls = s.responses.filter(x => x.answer == null).length;
  const chips = [
    m.folio_printed ? ["Folio impreso", "ok"] : ["Sin folio impreso", "warn"],
    m.valid_rut ? ["RUN válido", "ok"] : ["RUN no válido / vacío", "warn"],
    nulls ? [`${nulls} sin respuesta válida`, "bad"] : ["50 respuestas OK".replace("50", s.responses.length), "ok"],
  ];
  $("chips").innerHTML = chips.map(([t, c]) => `<span class="chip ${c}">${t}</span>`).join("");
  // answers
  $("rows").innerHTML = s.responses.map(x => {
    const q = +x.question, sc = label(s, q), a = x.answer;
    return `<tr class="${a == null ? "nul" : ""}"><td class="q">${q}</td><td class="a"><span class="ans">${a ?? "—"}</span>${a != null ? sc[a - 1] : ""}</td><td>${x.notes ? `<span class="note">${esc(x.notes)}</span>` : ""}</td></tr>`;
  }).join("");
  // review
  $("note").value = r.note || "";
  $("markok").style.outline = r.status === "ok" ? "2px solid var(--ok)" : "";
  $("markflag").style.outline = r.status === "flag" ? "2px solid var(--warn)" : "";
}
function go(i) { idx = Math.max(0, Math.min(S.length - 1, i)); page = 0; render(); }
function setStatus(v, advance) {
  const s = S[idx]; state[s.id] = {...st(s), status: v, note: $("note").value}; save();
  if (advance && idx < S.length - 1) go(idx + 1); else render(); fillJump();
}
function fillJump() {
  $("jump").innerHTML = S.map((s, i) => `<option value="${i}">${i + 1}. ${esc(s.id)} ${({ok:"✓",flag:"⚑"})[st(s).status] || ""}</option>`).join("");
  $("jump").value = idx;
}
$("prev").onclick = () => go(idx - 1); $("next").onclick = () => go(idx + 1);
$("jump").onchange = e => go(+e.target.value);
$("markok").onclick = () => setStatus("ok", true);
$("markflag").onclick = () => { setStatus("flag", false); $("note").focus(); };
$("clear").onclick = () => { delete state[S[idx].id]; save(); fillJump(); render(); };
$("note").oninput = () => { const s = S[idx]; state[s.id] = {...st(s), note: $("note").value}; save(); };
$("tabs").onclick = e => { const b = e.target.closest("button"); if (b) { page = b.dataset.p === "all" ? "all" : +b.dataset.p; render(); } };
$("scan").onclick = e => { if (e.target.tagName === "IMG") $("scan").classList.toggle("zoom"); };
$("export").onclick = () => {
  const q = v => '"' + String(v ?? "").replace(/"/g, '""') + '"';
  const lines = ["folio,archivo,estado,nota"].concat(S.map(s => [q(s.id), q(s.file), q(({ok:"correcta",flag:"con error"})[st(s).status] || "sin revisar"), q(st(s).note)].join(",")));
  $("csv").value = lines.join("\n"); $("exportcard").hidden = false; $("copied").textContent = "";
  $("exportcard").scrollIntoView({behavior: "smooth", block: "nearest"});
};
$("closeexp").onclick = () => { $("exportcard").hidden = true; };
$("copy").onclick = async () => {
  const t = $("csv"); t.select();
  try { await navigator.clipboard.writeText(t.value); $("copied").textContent = "Copiado"; }
  catch (e) { $("copied").textContent = "Selecciona el texto y copia con Ctrl/Cmd+C"; }
};
document.addEventListener("keydown", e => {
  if (e.target.tagName === "TEXTAREA" || e.target.tagName === "SELECT") return;
  if (e.key === "ArrowRight") go(idx + 1); else if (e.key === "ArrowLeft") go(idx - 1);
  else if (e.key.toLowerCase() === "o") setStatus("ok", true); else if (e.key.toLowerCase() === "f") { setStatus("flag", false); $("note").focus(); e.preventDefault(); }
});
fillJump(); render();
</script>
"""

LOCAL_WRAP = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{head}</head>
<body>
{body}</body>
</html>
"""


def folio_key(name):
    m = re.search(r"(\d+)$", name)
    return (int(m.group(1)) if m else 0, name)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", nargs="?", type=Path, default=DEFAULT_FOLDER)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--dpi", type=int, default=110)
    args = ap.parse_args()

    folder = args.folder.resolve()
    out = (args.out or REPO / "2026-09" / "review" / folder.name).resolve()
    img_dir = out / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    surveys = []
    for jp in sorted(folder.glob("*.json"), key=lambda p: folio_key(p.stem)):
        pdf = jp.with_suffix(".pdf")
        try:
            data = json.loads(jp.read_text(encoding="utf-8"))
            meta, responses = data["metadata"], data["responses"]
        except Exception:
            continue
        if not pdf.exists():
            continue
        pages = []
        images = pdf2image.convert_from_path(str(pdf), dpi=args.dpi)
        for i, im in enumerate(images, 1):
            rel = f"img/{pdf.stem}_p{i}.jpg"
            im.convert("RGB").save(out / rel, "JPEG", quality=72, optimize=True)
            pages.append(rel)
        wide = str(meta.get("grade_range", "")).startswith("6")
        surveys.append({"id": pdf.stem, "file": pdf.name, "meta": meta, "responses": responses, "pages": pages,
                        "scale1_end": 49 if wide else 31})
        print(f"  {pdf.name}: {len(pages)} pages, {len(responses)} answers")

    if not surveys:
        sys.exit(f"No surveys (json+pdf pairs) found in {folder}")
    payload = {"folder": f"{folder.parent.name} / {folder.name}", "surveys": surveys}
    blob = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    body = BODY.replace("__DATA__", blob)
    # index.html: standalone local page. artifact.html: the Artifact-contract form (no document wrapper).
    (out / "index.html").write_text(LOCAL_WRAP.format(head=HEAD, body=body), encoding="utf-8")
    (out / "artifact.html").write_text(HEAD + body, encoding="utf-8")
    print(f"\n{len(surveys)} surveys -> {out / 'index.html'} (+ artifact.html)")


if __name__ == "__main__":
    main()
