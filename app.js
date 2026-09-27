const state={issues:[]};

function esc(value){
  return String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));
}
function params(){
  return {
    q:document.querySelector("#search").value.trim().toLowerCase(),
    status:document.querySelector("#status").value,
    category:document.querySelector("#category").value
  };
}
function render(){
  const p=params();
  const filtered=state.issues.filter(i=>
    (!p.q || [i.title,i.summary,i.category,i.authority].join(" ").toLowerCase().includes(p.q)) &&
    (!p.status || i.status===p.status) &&
    (!p.category || i.category===p.category)
  );
  document.querySelector("#count").textContent=filtered.length+" shown";
  document.querySelector("#issues").innerHTML=filtered.map((i,idx)=>`
    <a class="card" href="issue.html?id=${encodeURIComponent(i.id)}">
      <div class="rank">#${idx+1} · ${esc(i.category)}</div>
      <h3>${esc(i.title)}</h3>
      <p>${esc(i.summary)}</p>
      <div class="meta">
        <span class="pill">${esc(i.status)}</span>
        <span class="pill">Updated ${esc(new Date(i.last_updated).toLocaleString())}</span>
        <span class="pill">${i.sources?.length||0} sources</span>
      </div>
    </a>`).join("") || "<p>No matching issues.</p>";
}
async function init(){
  const res=await fetch("data/issues.json",{cache:"no-store"});
  const data=await res.json();
  state.issues=data.issues||[];
  document.querySelector("#last-updated").textContent="Data updated "+new Date(data.generated_at).toLocaleString();
  const statuses=[...new Set(state.issues.map(x=>x.status).filter(Boolean))].sort();
  const categories=[...new Set(state.issues.map(x=>x.category).filter(Boolean))].sort();
  statuses.forEach(x=>document.querySelector("#status").insertAdjacentHTML("beforeend",`<option>${esc(x)}</option>`));
  categories.forEach(x=>document.querySelector("#category").insertAdjacentHTML("beforeend",`<option>${esc(x)}</option>`));
  ["#search","#status","#category"].forEach(s=>document.querySelector(s).addEventListener("input",render));
  render();
}
init().catch(e=>{document.querySelector("#issues").innerHTML="<p>Unable to load issue data.</p>";console.error(e)});
