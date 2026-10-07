/* Memory rooms, seasonal birthdays, and little interactions. */
let collectionLimit=18,birthdayDay='',birthdayTimer=null,shuffleOrder=new Map();
const birthMonths=['January','February','March','April','May','June','July','August','September','October','November','December'];
function seoulDate(now=new Date()){
 const parts=new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Seoul',year:'numeric',month:'numeric',day:'numeric'}).formatToParts(now);
 return Object.fromEntries(parts.filter(p=>['year','month','day'].includes(p.type)).map(p=>[p.type,Number(p.value)]));
}
function birthdayInfo(now=new Date()){
 const current=seoulDate(now),today=Date.UTC(current.year,current.month-1,current.day);
 return members.map(m=>{const [day,month,year]=m.birth.split(' '),monthIndex=birthMonths.indexOf(month);let next=Date.UTC(current.year,monthIndex,Number(day));if(next<today)next=Date.UTC(current.year+1,monthIndex,Number(day));return {...m,days:Math.round((next-today)/86400000),turning:new Date(next).getUTCFullYear()-Number(year),nextYear:new Date(next).getUTCFullYear()};}).sort((a,b)=>a.days-b.days);
}
function freshPhotos(){const images=media.filter(m=>m.kind==='image'&&m.category!=='sticker');const personal=images.filter(m=>!m.id.startsWith('seed-')&&!m.id.startsWith('extra-'));return personal.length?personal:images;}
function noteBox(){return settings.noteEnabled?'<a class="top-note" href="/korea#sorry-gift"><span class="note-icon">🫰</span><span><strong>I’m really sorry.</strong><small lang="ko">정말 미안해.</small></span><span class="note-arrow">↗</span></a>':'';}
function syncNoteBox(){if(path!=='/')return;let slot=document.querySelector('#top-note-slot');if(!slot){slot=document.createElement('div');slot.id='top-note-slot';main.querySelector('.container')?.prepend(slot);}slot.innerHTML=noteBox();}
function sectionHeading(kicker,title,description='',link=''){return `<div class="section-heading"><div><div class="eyebrow">${kicker}</div><h2>${title}</h2></div>${link||`<p>${description}</p>`}</div>`;}
function memoryWall(items){return `<div class="memory-wall">${items.map((m,i)=>`<div class="wall-cell wall-${i}">${memoryCard(m)}</div>`).join('')}</div>`;}
function homeMemoriesHTML(){
 const photos=freshPhotos(),set=photos.slice(0,6),strip=photos.slice(6,13);
  return `<section class="new-memories section" id="new-memories">${sectionHeading('A fresh little edit / 새로 만나는 순간들','Different frames.<br>The same <em>butterflies.</em>','A new arrangement each time you visit.<br>오늘은 어떤 순간이 눈에 들어올까?')}<div class="wall-intro"><span class="tiny-label">THE CAMERA ROLL EDIT · ${media.length} KEEPSAKES</span><a class="text-link" href="/world">See the whole collection ↗</a></div>${memoryWall(set)}</section><section class="pocket-room"><div class="pocket-intro"><span class="eyebrow">Little things, big feelings</span><h2>Keep a moment<br>in your <em>pocket.</em></h2><p lang="ko">작은 순간도 오래 기억할게.</p><p>A handful of favourites, picked afresh.</p><div class="strip-arrows"><button class="round-control" data-strip="-1" aria-label="Previous frames">←</button><button class="round-control" data-strip="1" aria-label="Next frames">→</button></div></div><div class="pocket-strip" id="pocket-strip">${(strip.length?strip:set).map(m=>frame(m,'pocket-photo',m.title)).join('')}</div></section>`;
}
function mountHomeMemories(){
 if(document.body.classList.contains('clean-home')){renderCleanPhotoGrid();return;}
 if(path!=='/')return;let slot=document.querySelector('#home-live-rooms');
 if(!slot){slot=document.createElement('div');slot.id='home-live-rooms';document.querySelector('.bento')?.before(slot);}
 slot.innerHTML=homeMemoriesHTML();bindMedia(slot);bindSaves(slot);
 slot.querySelectorAll('[data-strip]').forEach(b=>b.onclick=()=>{document.querySelector('#pocket-strip').scrollBy({left:Number(b.dataset.strip)*260,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});});
}
function birthdayCard(info,compact=false){
 const today=info.days===0,date=info.birth.split(' ').slice(0,2).join(' ');
 return `<section class="birthday-room ${today?'its-today':''} ${compact?'compact-birthday':''}" data-birthday="${info.id}"><div class="birthday-photo">${photo(photoFor(info.id),info.name)}<span class="birthday-stamp">${today?'BIRTHDAY BOY ♡':'NEXT LITTLE CELEBRATION'}</span></div><div class="birthday-copy"><div class="eyebrow">${today?'Today, the universe is extra purple.':'Something lovely is on its way.'}</div><h2>${today?`It’s ${info.name} <em>day!</em>`:`Counting down to<br>${info.name}’s <em>day.</em>`}</h2><p lang="ko">${today?`${info.short}아, 생일 축하해!`:'설레는 마음으로 기다리는 너의 생일.'}</p><div class="birthday-count"><strong>${today?'♡':String(info.days).padStart(2,'0')}</strong><span>${today?`${info.turning} years of you.`:'days until the candles glow'}<small>${date} · Seoul time (KST)</small></span></div><div class="birthday-actions"><a class="button ${today?'':'light'}" href="/members/${info.id}">${today?'Celebrate '+info.name:'Visit '+info.name} ↗</a>${today?'<button class="text-link birthday-celebrate" type="button">Send some confetti ✧</button>':''}</div></div><div class="cake-scene" aria-hidden="true"><div class="candle c1"><i></i></div><div class="candle c2"><i></i></div><div class="candle c3"><i></i></div><div class="cake-top"></div><div class="cake-base"><span>보라해</span></div><div class="cake-plate"></div></div></section>`;
}
function mountBirthday(){
 if(path==='/sorry')return;const info=birthdayInfo(),active=info[0].days===0?info[0]:null;
 document.body.classList.toggle('birthday-mode',!!active);
 document.querySelectorAll('.member-card').forEach(card=>{const id=card.getAttribute('href').split('/').pop();card.classList.toggle('birthday-member',active?.id===id);card.querySelector('.birthday-badge')?.remove();if(active?.id===id)card.querySelector('.member-photo').insertAdjacentHTML('beforeend','<span class="birthday-badge">Birthday boy 🎂</span>');});
 document.querySelector('#birthday-ribbon')?.remove();
  if(active){const ribbon=document.createElement('a');ribbon.id='birthday-ribbon';ribbon.className='birthday-ribbon';ribbon.href='/members/'+active.id;ribbon.innerHTML=`✧ It’s ${active.name} day! <span lang="ko">생일 축하해</span> · Let’s make it a little magical ↗`;document.querySelector('.site-header').after(ribbon);}
  if(path==='/birthdays'){updateBirthdayPage();return;}
  if(!['/','/world'].includes(path)&&!path.startsWith('/members/'))return;
 let slot=document.querySelector('#birthday-slot');
  if(!slot){slot=document.createElement('div');slot.id='birthday-slot';if(path==='/')document.querySelector('.home-birthday-anchor,.era-room')?.before(slot);else if(path==='/world')document.querySelector('.world-toolbar')?.before(slot);else document.querySelector('.profile')?.after(slot);}
 const chosen=path.startsWith('/members/')?info.find(m=>m.id===path.split('/')[2]):info[0];
  slot.innerHTML=birthdayCard(chosen,true);
 slot.querySelectorAll('.birthday-celebrate').forEach(b=>b.onclick=()=>confetti());
 if(chosen.days===0&&path.startsWith('/members/')){
  slot.insertAdjacentHTML('beforeend',`<section class="wish-table"><div><div class="eyebrow">A wish, just from you</div><h3>Make a little birthday wish.</h3><p>Saved in this browser, like a page in your diary.</p></div><form id="birthday-wish-form"><label class="sr-only" for="birthday-wish">Your birthday wish</label><input id="birthday-wish" maxlength="180" placeholder="Happy birthday, ${chosen.name}…" required><button class="button" type="submit">Keep my wish ♡</button><p id="wish-feedback" role="status"></p></form></section>`);
  const key=`wish-${chosen.id}-${chosen.nextYear}`,input=document.querySelector('#birthday-wish');try{input.value=localStorage.getItem(key)||'';}catch{}
  document.querySelector('#birthday-wish-form').onsubmit=e=>{e.preventDefault();try{localStorage.setItem(key,input.value.trim());document.querySelector('#wish-feedback').textContent='A little wish, kept with love. 소중히 간직할게 ♡';confetti();}catch{document.querySelector('#wish-feedback').textContent='Your wish is here for this visit; browser storage is unavailable.';}};
 }
 const todayKey=JSON.stringify(seoulDate());
 if(active&&birthdayDay!==todayKey){birthdayDay=todayKey;let seen=false;try{seen=sessionStorage.getItem('party-'+active.id+'-'+active.nextYear);sessionStorage.setItem('party-'+active.id+'-'+active.nextYear,'yes');}catch{}if(!seen)setTimeout(confetti,2000);}
  const portrait=document.querySelector('.profile-portrait');portrait?.classList.toggle('birthday-portrait',active?.id===path.split('/')[2]);
  if(path!=='/'||chosen.days<=7)mountBirthdayQuest(chosen,slot);else slot.insertAdjacentHTML('beforeend','<a class="clean-birthday-link" href="/birthdays">Open the birthday calendar and quests ↗</a>');
}
function confetti(){
 if(matchMedia('(prefers-reduced-motion: reduce)').matches){toast('A whole universe of birthday love. 생일 축하해 ♡');return;}
 const layer=document.createElement('div');layer.className='confetti-layer';layer.setAttribute('aria-hidden','true');
 for(let i=0;i<42;i++){const bit=document.createElement('span');bit.className='confetti-bit';bit.textContent=['✦','♡','·','✿'][i%4];bit.style.setProperty('--x',Math.random()*100+'vw');bit.style.setProperty('--delay',Math.random()*1.4+'s');bit.style.setProperty('--s',12+Math.random()*18+'px');bit.style.color=['#a172d0','#d8b0ef','#d7bd64','#eee1fa'][i%4];layer.append(bit);}document.body.append(layer);setTimeout(()=>layer.remove(),5400);
}
function enhancePage(){mountJourneyDirectory();syncNoteBox();mountHomeMemories();mountBirthday();if(!document.body.classList.contains('clean-home'))mountPersonalRooms();mountPrivateChat();if(!document.body.classList.contains('clean-home'))refreshHomePhotos();mountSoloNotes();personalisedCopy();startDayUpdates();}

function roomHeader(number,label,title,subtitle=''){return `<div class="room-heading"><span class="room-number">${number}</span><div><span class="eyebrow">${label}</span><h2>${title}</h2></div><p>${subtitle}</p></div>`;}
function cardsRoom(items,id,number,label,title,layout,subtitle=''){if(!items.length)return '';return `<section class="world-room" id="${id}">${roomHeader(number,label,title,subtitle)}<div class="${layout}">${items.map(memoryCard).join('')}</div></section>`;}
function renderWorldRooms(shown){
 renderGrowingRooms(shown);
}

let secretWord='';
document.addEventListener('keydown',e=>{if(e.ctrlKey||e.metaKey||e.altKey||/INPUT|TEXTAREA|SELECT/.test(e.target.tagName)||e.key.length!==1)return;secretWord=(secretWord+e.key.toLowerCase()).slice(-7);if(secretWord==='borahae'){toast('Secret room unlocked: you belong here, in every universe. 보라해 ♡');confetti();}});
