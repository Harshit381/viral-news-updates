const state={issues:[],days:[],category:"All"};
const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));
const fmt=v=>{try{return new Date(v).toLocaleString("en-IN",{dateStyle:"medium",timeStyle:"short"});}catch{return "—";}};

function currentDay(){return document.querySelector("#day").value||"";}
function categories(list){return ["All"].concat(Array.from(new Set(list.map(x=>x.category).filter(Boolean))).sort());}
function renderCategoryOptions(list){
  const select=document.querySelector("#category");
  if(!select)return;
  const opts=categories(list);
  select.innerHTML=opts.map(c=>"<option value=\""+esc(c)+"\">"+esc(c)+"</option>").join("");
  select.value=opts.includes(state.category)?state.category:"All";
}
function renderDayChips(){
  const wrap=document.querySelector("#day-chips");
  if(!wrap)return;
  wrap.innerHTML=state.days.slice(0,7).map(d=>"<button class=\"day-chip "+(d.date===currentDay()?"active":"")+"\" data-day=\""+esc(d.date)+"\">"+esc(d.label)+"</button>").join("");
  wrap.querySelectorAll(".day-chip").forEach(btn=>btn.addEventListener("click",()=>selectDay(btn.dataset.day)));
}
function card(x,n){
  const featured=n===0;
  const tone=(x.category||"India").toLowerCase().replace(/[^a-z]+/g,"-");
  const sources=x.source_count||0;
  const updates=x.timeline_count||0;
  return "<a class=\"news-card "+(featured?"featured":"")+"\" href=\"issue.html?id="+encodeURIComponent(x.id)+"\">"+
    "<div class=\"card-top\"><span class=\"rank-badge\">#"+(n+1)+"</span><span class=\"category-dot "+esc(tone)+"\"></span><span class=\"category-label\">"+esc(x.category||"India")+"</span></div>"+
    "<h3>"+esc(x.title)+"</h3>"+
    "<p>"+esc(x.brief_summary||"Follow the linked coverage for the latest documented developments.")+"</p>"+
    "<div class=\"card-bottom\"><span>"+sources+" source"+(sources===1?"":"s")+"</span><span>"+updates+" update"+(updates===1?"":"s")+"</span><span>Updated "+esc(fmt(x.last_updated))+"</span></div>"+
  "</a>";
}
function render(){
  let list=state.issues.slice();
  const q=document.querySelector("#search").value.toLowerCase().trim();
  if(q)list=list.filter(x=>(x.title+" "+x.brief_summary+" "+(x.category||"")).toLowerCase().includes(q));
  if(state.category!=="All")list=list.filter(x=>x.category===state.category);
  document.querySelector("#count").textContent=list.length+" "+(list.length===1?"story":"stories");
  const sourceTotal=list.reduce((sum,x)=>sum+(x.source_count||0),0);
  const updateTotal=list.reduce((sum,x)=>sum+(x.timeline_count||0),0);
  document.querySelector("#coverage").innerHTML="<span><strong>"+list.length+"</strong> stories</span><span><strong>"+sourceTotal+"</strong> source mentions</span><span><strong>"+updateTotal+"</strong> tracked updates</span>";
  document.querySelector("#issues").innerHTML=list.map(card).join("")||"<div class=\"empty-state\"><div class=\"empty-icon\">⌕</div><h3>No stories found</h3><p>Try another day, category or search term.</p></div>";
}
async function selectDay(value){
  document.querySelector("#day").value=value;
  if(value){
    const file=await fetch("data/days/"+encodeURIComponent(value)+".json",{cache:"no-store"}).then(r=>r.json());
    state.issues=(file.issues||[]).map(y=>Object.assign({},y,{snapshot_date:value}));
  }else{
    const latest=await fetch("data/issues.json",{cache:"no-store"}).then(r=>r.json());
    state.issues=latest.issues||[];
  }
  state.category="All";
  renderCategoryOptions(state.issues);
  renderDayChips();
  render();
}
async function init(){
  const latest=await fetch("data/issues.json",{cache:"no-store"}).then(r=>r.json());
  const days=await fetch("data/days/index.json",{cache:"no-store"}).then(r=>r.json()).catch(()=>({days:[]}));
  state.issues=latest.issues||[];
  state.days=days.days||[];
  document.querySelector("#last-updated").textContent="Pipeline updated "+fmt(latest.generated_at);
  const d=document.querySelector("#day");
  state.days.forEach(x=>d.insertAdjacentHTML("beforeend","<option value=\""+esc(x.date)+"\">"+esc(x.label)+"</option>"));
  renderCategoryOptions(state.issues);
  renderDayChips();
  document.querySelector("#search").addEventListener("input",render);
  d.addEventListener("change",()=>selectDay(d.value));
  document.querySelector("#category").addEventListener("change",e=>{state.category=e.target.value;render();});
  render();
}
init().catch(()=>{document.querySelector("#issues").innerHTML="<div class=\"empty-state\"><div class=\"empty-icon\">!</div><h3>News is temporarily unavailable</h3><p>The free daily pipeline may still be running. Please check the Control Center.</p></div>";});
