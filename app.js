const state={issues:[],days:[],category:"All",signal:"All"};
const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[c]));
const fmt=v=>{try{return new Date(v).toLocaleString("en-IN",{dateStyle:"medium",timeStyle:"short"});}catch{return "—";}};
function uniqueCategories(list){return ["All",...Array.from(new Set(list.map(x=>x.category).filter(Boolean))).sort()];}
function fillFilters(){
  const category=document.querySelector("#category");
  category.innerHTML=uniqueCategories(state.issues).map(x=>"<option>"+esc(x)+"</option>").join("");
  category.value=state.category;
}
function render(){
  let list=state.issues.slice();
  const q=document.querySelector("#search").value.toLowerCase().trim();
  const date=document.querySelector("#day").value;
  if(q)list=list.filter(x=>(x.title+" "+x.brief_summary+" "+(x.category||"")).toLowerCase().includes(q));
  if(date)list=list.filter(x=>x.snapshot_date===date);
  if(state.category!=="All")list=list.filter(x=>x.category===state.category);
  if(state.signal!=="All")list=list.filter(x=>x.signal_type===state.signal);
  document.querySelector("#count").textContent=list.length+" "+(list.length===1?"story":"stories");
  document.querySelector("#issues").innerHTML=list.map((x,n)=>"<article class=\"news-row\">"+
    "<div class=\"news-main\"><div class=\"rank\">"+String(n+1).padStart(2,"0")+"</div>"+
    "<div><h2><a href=\"issue.html?id="+encodeURIComponent(x.id)+"\">"+esc(x.title)+"</a></h2>"+
    "<p>"+esc(x.brief_summary||"Follow the latest documented reporting and timeline updates.")+"</p>"+
    "<div class=\"meta\"><span>"+esc(fmt(x.last_updated))+"</span><span>"+(x.timeline_count||0)+" timeline updates</span><span>"+(x.source_count||0)+" sources</span></div></div></div>"+
    "<div class=\"row-arrow\">→</div></article>").join("")||"<div class=\"empty\"><h3>No stories found</h3><p>Try another search, date, category or signal.</p></div>";
}
async function loadDay(){
  const date=document.querySelector("#day").value;
  if(date){
    const data=await fetch("data/days/"+encodeURIComponent(date)+".json",{cache:"no-store"}).then(r=>r.json());
    state.issues=(data.issues||[]).map(x=>Object.assign({},x,{snapshot_date:date}));
  }else{
    const data=await fetch("data/issues.json",{cache:"no-store"}).then(r=>r.json());
    state.issues=data.issues||[];
  }
  state.category="All";
  fillFilters();
  render();
}
async function init(){
  const latest=await fetch("data/issues.json",{cache:"no-store"}).then(r=>r.json());
  const days=await fetch("data/days/index.json",{cache:"no-store"}).then(r=>r.json()).catch(()=>({days:[]}));
  state.issues=latest.issues||[];
  state.days=days.days||[];
  document.querySelector("#last-updated").textContent="Last updated "+fmt(latest.generated_at);
  const day=document.querySelector("#day");
  state.days.forEach(x=>day.insertAdjacentHTML("beforeend","<option value=\""+esc(x.date)+"\">"+esc(x.label)+"</option>"));
  fillFilters();
  document.querySelector("#search").addEventListener("input",render);
  day.addEventListener("change",loadDay);
  document.querySelector("#category").addEventListener("change",e=>{state.category=e.target.value;render();});
  document.querySelector("#signal").addEventListener("change",e=>{state.signal=e.target.value;render();});
  render();
}
init().catch(()=>{document.querySelector("#issues").innerHTML="<div class=\"empty\"><h3>News is temporarily unavailable</h3><p>The free daily pipeline may still be running.</p></div>";});
