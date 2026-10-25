const API = location.port === "3000" ? "http://127.0.0.1:8000" : "";
const $ = (s) => document.querySelector(s);
const app = $("#app");
const banner = $("#banner");
let workspaceId = null;
const docs = new Map();
const timers = new Map();

function showBanner(msg){ banner.innerHTML = `<span>${msg}</span><button class="ghost" id="close-banner">×</button>`; banner.classList.remove("hidden"); $("#close-banner").onclick = ()=>banner.classList.add("hidden"); }

async function api(path, opts){ const r = await fetch(API+path, opts); if(!r.ok){ let d="Request failed"; try{d=(await r.json()).detail||d;}catch{} throw new Error(d);} return r.json(); }

function startScreen(){
  app.innerHTML = `
  <section class="start">
    <div class="container">
      <span class="pill mono">document analysis, with receipts</span>
      <h1 class="headline">Ask your financial documents anything.<br><em>Get answers with receipts.</em></h1>
      <p class="subhead">Answers cite the exact page or cell they came from, so every figure can be traced to its source.</p>
      <div class="cta-row">
        <button class="btn btn-primary hero" id="start-btn">Start a session <svg class="arrow" viewBox="0 0 16 16"><path d="M3 8h10M9 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
        <a href="#demo" class="btn btn-ghost">See an example</a>
      </div>
      <div class="demo" id="demo">
        <div class="demo-frame">
          <div class="demo-bar"><span class="dot-ui"></span><span class="dot-ui"></span><span class="dot-ui"></span><span class="demo-label">example, not your data</span></div>
          <div class="demo-body">
            <div class="demo-files">
              <div class="demo-file"><span class="dot" style="background:var(--success)"></span>report.pdf</div>
              <div class="demo-file"><span class="dot" style="background:var(--success)"></span>q3-ledger.xlsx</div>
              <div class="demo-file"><span class="dot" style="background:var(--warning);animation:pulse 1.2s infinite"></span>scan-014.png</div>
            </div>
            <div class="demo-chat" id="demo-chat"></div>
          </div>
        </div>
      </div>
      <div class="marquee"><div class="marquee-track">PDF · XLSX · XLS · DOCX · CSV · PNG · JPG · scanned pages · PDF · XLSX · XLS · DOCX · CSV · PNG · JPG · scanned pages · </div></div>
      <div class="bento" id="how">
        <div class="card wide"><div class="icon"><svg viewBox="0 0 16 16"><path d="M3 4h10v8H3z" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M3 7h10" stroke="currentColor" stroke-width="1.5"/></svg></div><div class="num">01</div><h3>Upload</h3><p>Drag and drop PDFs, spreadsheets, Word files, CSVs and scans. Up to 25 MB each.</p></div>
        <div class="card"><div class="icon"><svg viewBox="0 0 16 16"><path d="M2 4h12v9H2z" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M5 7h6M5 10h4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></div><div class="num">02</div><h3>Extract</h3><p>Text, tables and OCR. Page and cell provenance kept.</p></div>
        <div class="card"><div class="icon"><svg viewBox="0 0 16 16"><path d="M8 2l6 3v5c0 3-2.5 5-6 6-3.5-1-6-3-6-6V5l6-3z" fill="none" stroke="currentColor" stroke-width="1.5"/></svg></div><div class="num">03</div><h3>Ask</h3><p>Answers cite the source. No invented figures.</p></div>
        <div class="card"><div class="icon"><svg viewBox="0 0 16 16"><path d="M8 2a6 6 0 1 0 0 12A6 6 0 0 0 8 2z" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M8 5v3M8 11h.01" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></div><div class="num">04</div><h3>Honest by design</h3><p>Scanned figures may be misread. Totals come from the model; verify against the source.</p></div>
        <div class="card"><div class="icon"><svg viewBox="0 0 16 16"><path d="M3 8a5 5 0 0 1 5-5h0a5 5 0 0 1 5 5v5H3V8z" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M6 13v1M10 13v1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg></div><div class="num">05</div><h3>Private by default</h3><p>Sessions expire automatically and their data is removed.</p></div>
      </div>
      <div class="closing">
        <h2>Bring a document.<br>Leave with answers.</h2>
        <button class="btn btn-primary hero" id="start-btn-2">Start a session <svg class="arrow" viewBox="0 0 16 16"><path d="M3 8h10M9 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
      </div>
      <footer class="footer">Anyone with the session id can open the session, there is no login. Excerpts are sent to an external language model (Groq).</footer>
    </div>
  </section>`;
  $("#start-btn").onclick = createSession;
  $("#start-btn-top").onclick = createSession;
  $("#start-btn-2").onclick = createSession;
  runDemo();
  document.querySelectorAll(".card").forEach(c=>{
    c.addEventListener("mousemove", e=>{
      const r=c.getBoundingClientRect();
      c.style.setProperty("--mx",(e.clientX-r.left)+"px");
      c.style.setProperty("--my",(e.clientY-r.top)+"px");
    });
  });
}

function runDemo(){
  const chat = $("#demo-chat");
  if(!chat) return;
  const q = "What was Q3 revenue?";
  const a = "Revenue in Q3 was 1,500 thousand, up 12% year over year.";
  let i=0;
  function cycle(){
    chat.innerHTML = "";
    const qel = document.createElement("div"); qel.className="demo-q"; chat.appendChild(qel);
    const type = setInterval(()=>{ if(i<q.length){ qel.textContent += q[i++]; } else { clearInterval(type); setTimeout(showThinking,400);} }, 45);
  }
  function showThinking(){
    const t = document.createElement("div"); t.className="thinking"; t.innerHTML="<span></span><span></span><span></span>"; chat.appendChild(t);
    setTimeout(()=>{ t.remove(); showAnswer(); }, 1200);
  }
  function showAnswer(){
    const ael = document.createElement("div"); ael.className="demo-a"; ael.textContent=a; chat.appendChild(ael);
    const c1 = document.createElement("span"); c1.className="demo-cite"; c1.textContent="report.pdf · p.12";
    const c2 = document.createElement("span"); c2.className="demo-cite"; c2.textContent="q3-ledger.xlsx · B14";
    chat.appendChild(c1); chat.appendChild(c2);
    setTimeout(cycle, 12000);
  }
  cycle();
}

async function createSession(){
  try {
    const ws = await api("/api/v1/workspaces", { method:"POST" });
    workspaceId = ws.id;
    $("#session-controls")?.remove();
    const sc = document.createElement("div");
    sc.id="session-controls"; sc.className="session-controls";
    sc.innerHTML = `<span class="ws-id mono">${workspaceId.slice(0,8)}</span><button class="copy-btn" id="copy-ws">copy</button><button class="btn btn-ghost" id="new-session">new session</button>`;
    document.querySelector(".header-nav").prepend(sc);
    $("#copy-ws").onclick = async ()=>{ await navigator.clipboard.writeText(workspaceId); $("#copy-ws").textContent="copied"; setTimeout(()=>$("#copy-ws").textContent="copy",1200); };
    $("#new-session").onclick = ()=>{ workspaceId=null; docs.clear(); timers.forEach(t=>clearInterval(t)); timers.clear(); startScreen(); };
    workspaceScreen();
  } catch(e){ showBanner(e.message); }
}

function workspaceScreen(){
  app.innerHTML = `
  <div class="workspace">
    <aside class="panel">
      <div class="panel-head"><span class="panel-title">Documents</span></div>
      <label class="dropzone" id="dropzone">
        <input type="file" id="file-input" multiple accept=".pdf,.docx,.xlsx,.xls,.csv,.png,.jpg,.jpeg">
        <div class="dz-icon"><svg viewBox="0 0 16 16"><path d="M8 11V4M4 7l4-4 4 4M3 13h10" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg></div>
        <div>Drop files or browse</div>
        <div style="font-size:12px;color:var(--muted);margin-top:4px">PDF · XLSX · DOCX · CSV · IMG · 25 MB</div>
      </label>
      <div class="doc-list" id="doc-list"></div>
    </aside>
    <section class="panel chat">
      <div class="chat-log" id="chat-log"></div>
      <div class="composer">
        <textarea id="q" placeholder="Ask a question about your documents…" rows="1"></textarea>
        <button class="send" id="send-btn" disabled><svg viewBox="0 0 16 16"><path d="M3 8h10M9 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
      </div>
      <div class="composer-help">Figures from scans may be misread. Totals come from the model — verify against the source. Excerpts are sent to Groq.</div>
    </section>
  </div>`;
  const input = $("#file-input");
  const dz = $("#dropzone");
  dz.onclick = () => input.click();
  dz.ondragover = (e)=>{e.preventDefault(); dz.classList.add("drag");};
  dz.ondragleave = ()=>dz.classList.remove("drag");
  dz.ondrop = (e)=>{e.preventDefault(); dz.classList.remove("drag"); uploadFiles(e.dataTransfer.files);};
  input.onchange = ()=>{ uploadFiles(input.files); input.value=""; };
  $("#send-btn").onclick = sendChat;
  const ta = $("#q");
  ta.addEventListener("input", ()=>{ ta.style.height="auto"; ta.style.height=Math.min(ta.scrollHeight,160)+"px"; updateSend(); });
  ta.addEventListener("keydown", (e)=>{ if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();sendChat();} if(e.key==="Escape"){ta.value="";updateSend();} });
  renderDocs();
  renderEmpty();
}

function extIcon(name){
  const e = (name.split(".").pop()||"").toLowerCase();
  if(e==="pdf") return ["pdf","PDF"];
  if(e==="xlsx"||e==="xls") return ["xlsx","XLS"];
  if(e==="docx") return ["docx","DOC"];
  if(e==="csv") return ["csv","CSV"];
  return ["img","IMG"];
}

async function uploadFiles(files){
  for(const f of files){
    const tmp = crypto.randomUUID();
    docs.set(tmp, {id:tmp,name:f.name,status:"uploading"});
    renderDocs();
    try{
      const fd = new FormData(); fd.append("file", f);
      const r = await fetch(API+`/api/v1/workspaces/${workspaceId}/documents`, {method:"POST", body:fd});
      if(!r.ok){ let d="Upload failed"; try{d=(await r.json()).detail||d;}catch{} docs.delete(tmp); const id=crypto.randomUUID(); docs.set(id,{id,name:f.name,status:"failed",reason:d}); renderDocs(); showBanner(d); continue; }
      const doc = await r.json();
      docs.delete(tmp);
      docs.set(doc.id, {id:doc.id,name:doc.filename||f.name,status:doc.status||"uploaded",size:doc.file_size});
      renderDocs();
      pollDoc(doc.id);
    } catch(e){ docs.delete(tmp); const id=crypto.randomUUID(); docs.set(id,{id,name:f.name,status:"failed",reason:e.message}); renderDocs(); showBanner(e.message); }
  }
}

function pollDoc(docId){
  const start = Date.now();
  const timer = setInterval(async ()=>{
    if(Date.now()-start > 5*60*1000){ clearInterval(timer); timers.delete(docId); return; }
    try{
      await fetch(API+`/api/v1/workspaces/${workspaceId}/documents/${docId}/content`);
      const d = docs.get(docId); if(d){ d.status="ready"; renderDocs(); updateSend(); }
      clearInterval(timer); timers.delete(docId);
    } catch(e){
      const msg = e.message||"";
      if(msg.toLowerCase().includes("processing")) return;
      const d = docs.get(docId);
      if(d && d.status!=="ready"){ d.status="failed"; d.reason=msg; renderDocs(); updateSend(); }
      clearInterval(timer); timers.delete(docId);
    }
  }, 2000);
  timers.set(docId, timer);
}

function renderDocs(){
  const list = $("#doc-list"); if(!list) return;
  list.innerHTML = "";
  for(const d of docs.values()){
    const [cls, label] = extIcon(d.name);
    const el = document.createElement("div");
    el.className = "doc-row";
    let extra = "";
    if(d.status==="failed") extra = `<button class="btn btn-ghost" data-retry="${d.id}" style="font-size:12px">retry</button><span style="font-size:11px;color:var(--danger)">${d.reason||""}</span>`;
    el.innerHTML = `<div class="doc-icon ${cls}">${label}</div><div class="doc-info"><div class="doc-name mono">${d.name}</div><div class="doc-meta"><span class="status-dot ${d.status}"></span>${d.status}${d.size? " · "+Math.round(d.size/1024)+"KB":""}</div>${d.status==="uploading"||d.status==="processing"?"<div class='shimmer'></div>":""}</div>${extra}`;
    list.appendChild(el);
  }
  list.querySelectorAll("[data-retry]").forEach(b=>{
    b.onclick = async ()=>{
      const id = b.getAttribute("data-retry");
      const d = docs.get(id);
      try {
        await api(`/api/v1/workspaces/${workspaceId}/documents/${id}/retry`, {method:"POST"});
        if(d){ d.status="uploaded"; d.reason=""; renderDocs(); pollDoc(id); }
      } catch(e){
        if(d){ d.reason=e.message; renderDocs(); }
        showBanner(e.message);
      }
    };
  });
}

function renderEmpty(){
  const log = $("#chat-log"); if(!log) return;
  if(docs.size===0 || ![...docs.values()].some(d=>d.status==="ready")){
    log.innerHTML = `<div class="empty-state"><h2>What would you like to know?</h2><p>Upload a document to begin. Answers cite the source.</p><div class="sugg-grid">
      <button class="sugg" data-q="What were the key figures?"><strong>Key figures</strong><span>Revenue, profit, totals</span></button>
      <button class="sugg" data-q="Summarise the main risks."><strong>Main risks</strong><span>What the document flags</span></button>
      <button class="sugg" data-q="What changed year over year?"><strong>Year over year</strong><span>Compare periods</span></button>
      <button class="sugg" data-q="List the citations."><strong>Citations</strong><span>Where each figure lives</span></button>
    </div></div>`;
    log.querySelectorAll(".sugg").forEach(b=>{ b.onclick=()=>{ $("#q").value=b.getAttribute("data-q"); updateSend(); $("#q").focus(); }; });
  }
}

function updateSend(){
  const ta = $("#q"); const btn = $("#send-btn");
  if(!ta||!btn) return;
  const hasReady = [...docs.values()].some(d=>d.status==="ready");
  btn.disabled = !(ta.value.trim() && hasReady);
}

async function sendChat(){
  const ta = $("#q");
  const q = ta.value.trim();
  if(!q) return;
  const hasReady = [...docs.values()].some(d=>d.status==="ready");
  if(!hasReady){ showBanner("No ready documents yet."); return; }
  const log = $("#chat-log");
  const empty = log.querySelector(".empty-state"); if(empty) empty.remove();
  const u = document.createElement("div"); u.className="msg user";
  u.innerHTML = `<div class="who">You</div><div class="bubble">${escapeHtml(q)}</div>`;
  log.appendChild(u);
  ta.value=""; ta.style.height="auto"; updateSend();
  log.scrollTop = log.scrollHeight;
  const thinking = document.createElement("div"); thinking.className="thinking"; thinking.innerHTML="<span></span><span></span><span></span>"; log.appendChild(thinking);
  const btn = $("#send-btn"); btn.disabled=true;
  try {
    const res = await api(`/api/v1/workspaces/${workspaceId}/chat`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({query:q})});
    thinking.remove();
    const a = document.createElement("div"); a.className="msg assistant";
    const bubble = document.createElement("div"); bubble.className="bubble";
    // streaming-style reveal
    const text = res.answer||"";
    a.innerHTML = `<div class="who">finaudit</div>`;
    a.appendChild(bubble);
    const cites = document.createElement("div"); cites.className="citations";
    (res.citations||[]).forEach(c=>{
      const chip = document.createElement("span"); chip.className="cite";
      const full = c.document_name || c.document_id || "";
      chip.textContent = `${full}${c.page_number?" · p."+c.page_number:""}${c.sheet_name?" · "+c.sheet_name:""}`;
      chip.title = full;
      cites.appendChild(chip);
    });
    a.appendChild(cites);
    log.appendChild(a);
    let i=0;
    const iv = setInterval(()=>{ if(i<=text.length){ bubble.textContent = text.slice(0,i); i+=3; log.scrollTop=log.scrollHeight; } else { clearInterval(iv); bubble.textContent=text; } }, 12);
  } catch(e){ thinking.remove(); showBanner(e.message); }
  finally { btn.disabled=false; updateSend(); }
}

function escapeHtml(s){ return s.replace(/[&<>"']/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c])); }

startScreen();