import {e,$,api,D,version,refresh} from './site.js';
const labels={pageCopy:'Page titles and introductions',teachingSteps:'Teaching method',learnerPaths:'Learner pathways',projectSteps:'Project stages',site:'Institute profile',home:'Homepage introduction',nav:'Navigation',courses:'Courses',programs:'Career programs',story:'Institute story',learningModes:'Learning modes',faqs:'Learning FAQs',contactFAQs:'Admissions FAQs',teamMembers:'Mentors',selfVsUs:'Learning comparison',whyUsPoints:'Teaching approach',values:'Institute values',counters:'Homepage statistics',timeline:'Institute timeline',facilities:'Facilities',journey:'Learning journey'};
const human=k=>k.replace(/([A-Z])/g,' $1').replace(/^./,s=>s.toUpperCase());
const statusList=['New','Contacted','Closed'];
let dirty=false;
window.addEventListener('beforeunload',ev=>{if(dirty&&location.hash==='#/admin'){ev.preventDefault();ev.returnValue=''}});
function login(message=''){
 $('#main').innerHTML=`<div class="wrap section dash"><form class="box stack" style="max-width:420px;margin:auto"><p class="eyebrow">Institute administration</p><h1 style="font-size:38px">Staff sign in</h1><label>Admin password<input type="password" name="password" autocomplete="current-password" required></label><button class="btn">Sign in</button><p class="error" role="alert">${e(message)}</p></form></div>`;
 const f=$('main form');f.onsubmit=async ev=>{ev.preventDefault();f.querySelector('button').disabled=true;try{await api('login','POST',{password:f.elements.password.value});await dashboard()}catch(err){f.querySelector('.error').textContent=err.message;f.querySelector('button').disabled=false}};
}
export async function dashboard(){
 dirty=false;
 $('#main').innerHTML='<div class="wrap section dash" aria-live="polite">Loading dashboard…</div>';let inbox;
 try{inbox=await api('inbox');await refresh()}catch(err){if(location.hash==='#/admin')login(err.status===401?'':err.message);return}
 if(location.hash!=='#/admin')return;
 $('#main').innerHTML=`<div class="wrap section dash"><div class="sectionTitle"><div><p class="eyebrow">Institute administration</p><h1 style="font-size:42px">Dashboard</h1></div><button id="logout" class="btn secondary">Sign out</button></div><div class="dashMetrics"></div><div class="tabrow"><button class="tab active" id="inboxTab">Admissions inbox</button><button class="tab" id="cmsTab">Website content</button></div><div id="workspace"></div><p id="feedback" role="status"></p></div>`;
 const msg=(s,error=false)=>{const el=$('#feedback');if(el){el.className=error?'error':'notice';el.textContent=s}};
 const failure=err=>err.status===401?login('Your session expired. Sign in again.'):msg(err.message,true);
 const discard=()=>!dirty||confirm('Discard unpublished changes?');
 $('#logout').onclick=async()=>{if(!discard())return;try{await api('logout','POST',{});dirty=false;login()}catch(err){failure(err)}};
 const metrics=()=>{$('.dashMetrics').innerHTML=statusList.map(s=>`<div class="box"><strong>${inbox.filter(x=>x.status===s).length}</strong>${s} enquiries</div>`).join('')};
 function admissions(){
 if(!discard())return;dirty=false;msg('');metrics();$('#inboxTab').classList.add('active');$('#cmsTab').classList.remove('active');
 $('#workspace').innerHTML='<div class="filters"><label>Search enquiries<input type="search" id="searchLead"></label><label>Status<select id="leadFilter"><option>All</option>'+statusList.map(s=>'<option>'+s+'</option>').join('')+'</select></label><button class="btn secondary" id="reload">Refresh inbox</button></div><div id="leads"></div>';
 const draw=()=>{const query=$('#searchLead').value.trim().toLowerCase();const filtered=inbox.filter(r=>($('#leadFilter').value==='All'||$('#leadFilter').value===r.status)&&[r.id,r.name,r.email,r.phone,r.interest].join(' ').toLowerCase().includes(query));
 $('#leads').innerHTML=filtered.length?filtered.map(r=>`<details class="inbox"><summary>${e(r.name)} · ${e(r.interest)} <span class="token">${e(r.status)}</span></summary><p>${e(r.id)} · ${e(new Date(r.created).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'}))} IST</p><p>${e(r.email)} · ${e(r.phone)}</p><p>${e([r.intent,r.mode,r.batch,r.callback].join(' · '))}</p><p>${e(r.notes)}</p><label>Enquiry status<select data-id="${e(r.id)}">${statusList.map(s=>`<option ${s===r.status?'selected':''}>${s}</option>`).join('')}</select></label></details>`).join(''):'<p class="box">No enquiries match this view.</p>';
 document.querySelectorAll('[data-id]').forEach(el=>el.onchange=async()=>{el.disabled=true;const item=inbox.find(r=>r.id===el.dataset.id);try{await api('status','PUT',{id:item.id,status:el.value});item.status=el.value;metrics();draw();msg('Enquiry status updated.')}catch(err){el.value=item.status;el.disabled=false;failure(err)}});
 };$('#leadFilter').onchange=draw;$('#searchLead').oninput=draw;$('#reload').onclick=async()=>{try{inbox=await api('inbox');metrics();draw();msg('Inbox refreshed.')}catch(err){failure(err)}};draw();
 }
 function content(){
 if(!discard())return;dirty=false;msg('');$('#cmsTab').classList.add('active');$('#inboxTab').classList.remove('active');
 $('#workspace').innerHTML=`<label>Content section<select id="sectionKey">${Object.keys(labels).map(k=>`<option value="${k}">${labels[k]}</option>`).join('')}</select></label><form class="box editor"><div id="fields"></div><div class="actions"><button class="btn">Publish changes</button><button type="button" class="btn secondary" id="revert">Discard changes</button></div></form>`;
 let key,draft;
 function load(){key=$('#sectionKey').value;draft=structuredClone(D[key]);dirty=false;msg('');paint()}
 function paint(){
 const root=$('#fields');root.replaceChildren();
 function node(parent,obj,prop,label,schema){
 const value=obj[prop];
 if(Array.isArray(value)){
 const group=document.createElement('div');parent.append(group);
 const title=document.createElement('h3');title.textContent=label;group.append(title);
 const add=document.createElement('button');add.type='button';add.className='btn secondary';add.textContent='Add item';
 const render=()=>{group.replaceChildren(title);value.forEach((v,i)=>{const details=document.createElement('details');const summary=document.createElement('summary');summary.textContent=typeof v==='object'?(v.title||v.label||v.name||v.q||v.topic||v.event||v.aspect||'Item '+(i+1)):String(v).slice(0,90);details.append(summary);group.append(details);node(details,value,i,'Value',schema[0]);const rm=document.createElement('button');rm.type='button';rm.className='btn secondary';rm.textContent='Remove item';rm.disabled=value.length<=1;rm.onclick=()=>{if(confirm('Remove this item from the draft?')){value.splice(i,1);dirty=true;render()}};details.append(rm)});group.append(add)};
 add.onclick=()=>{value.push(structuredClone(schema[0]));dirty=true;render();group.querySelector('details:last-of-type').open=true};render();
 }else if(typeof value==='object'){for(const [k] of Object.entries(value))node(parent,value,k,human(k),schema[k])}
 else{const el=document.createElement('label');el.textContent=label;const input=document.createElement(typeof value==='string'&&value.length>85?'textarea':'input');input.value=value;if(typeof value==='number')input.type='number';input.required=true;input.oninput=()=>{obj[prop]=typeof value==='number'?Number(input.value):input.value;dirty=true};el.append(input);parent.append(el)}
 }
 node(root,{draft},'draft',labels[key],D[key]);
 }
 $('#sectionKey').onchange=()=>{if(!discard()){$('#sectionKey').value=key;return}load()};$('#revert').onclick=()=>{if(discard())load()};
 $('.editor').onsubmit=async ev=>{ev.preventDefault();const btn=ev.submitter;btn.disabled=true;try{await api('content','PUT',{section:key,value:draft,version});await refresh();load();msg('Published. The public website now uses these changes.')}catch(err){failure(err)}finally{btn.disabled=false}};
 load();
 }
 $('#inboxTab').onclick=admissions;$('#cmsTab').onclick=content;admissions();
}
