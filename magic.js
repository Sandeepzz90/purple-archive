/* Small, local-only personal touches. No remote personalization service. */
let arrivalStarted=0,arrivalTimer=null;
const chapterStyles=['arch-gallery','light-gallery','ribbon-gallery','window-gallery','contact-grid'];
const chapterTitles=[
 ['The daydream gallery','A little outside <em>ordinary.</em>','For your favourite kind of wandering.'],
 ['The light collection','Small things. <em>A soft glow.</em>','A few things that make the day feel lighter.'],
 ['The ribbon room','Tied up with <em>a little love.</em>','Unwrap a moment, just for you.'],
 ['Windows to somewhere lovely','A view into <em>your happy place.</em>','Another window. Another tiny possibility.'],
 ['The pocket exhibition','Keep the <em>butterflies.</em>','Because one more look is always allowed.'],
 ['The almost-magic department','For your <em>softer side.</em>','No explanation needed. Just a good feeling.'],
 ['The beautiful in-between','Stay here, <em>a little longer.</em>','This little corner can wait with you.'],
 ['The velvet hour','A softer kind <em>of forever.</em>','A few lovely things to return to.'],
];
function tinyHash(value){let hash=2166136261;for(const c of String(value))hash=Math.imul(hash^c.charCodeAt(0),16777619);return hash>>>0;}
function readLocal(key,fallback){try{return JSON.parse(localStorage.getItem(key))??fallback;}catch{return fallback;}}
function writeLocal(key,value){try{localStorage.setItem(key,JSON.stringify(value));return true;}catch{return false;}}
function personalisedCopy(root=document.body){
 if(path==='/sorry')return;
 const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT),nodes=[];
 while(walker.nextNode())nodes.push(walker.currentNode);
 for(const node of nodes){
  if(node.parentElement?.closest('script,style,textarea,input,.memory h3,.viewer-title,.note,.future-message,.chat-message,.birthday-keepsake,.personal-birthday-letter,.one-time-note-content'))continue;
  let text=node.nodeValue;
  const swaps=[['days of us.','days of magic.'],['Our most beautiful moment.','Your most beautiful chapter.'],['none of us could have imagined','the world could have imagined'],['so many of us','so many hearts'],['brought us here','brought you here'],['Let’s find our way home.','Your little world is one click away.'],['our favourite seven','your favourite seven'],['our golden boy','your golden boy'],['just for us','just for you'],['Just like us.','Made for your kind of daydream.'],['우리만의 작은 우주','너만을 위한 작은 우주'],['일곱 빛깔의 우리, 하나의 우주.','일곱 빛깔의 순간, 오직 너를 위해.'],['여긴 우리 세상','여긴 너만의 세상'],['우리의 일곱','너를 위한 일곱'],['우리의 순간들','너를 위한 순간들'],['우리의 시작','이야기의 시작'],['우리의 기록','너를 위한 기록']];
  for(const [from,to] of swaps)text=text.split(from).join(to);
  text=text.replace(/\bOur\b/g,'Your').replace(/\bour\b/g,'your').replace(/\bus\b/g,'you');
  if(text!==node.nodeValue)node.nodeValue=text;
 }
 document.title=document.title.replace(/\bOur\b/g,'Your').replace('우리만의 작은 우주','너만을 위한 작은 우주');
}

async function fetchTimed(url,options={}){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),10000);
 try{return await fetch(url,{...options,signal:controller.signal});}finally{clearTimeout(timer);}
}
function beginArrival(){
 document.querySelector('.arrival')?.remove();clearTimeout(arrivalTimer);arrivalStarted=performance.now();
 main.setAttribute('aria-busy','true');
 if(path==='/sorry')return;
 if(['/','/surprise','/korea'].includes(path)&&hasSeenBirthdayOpening())return;
 const member=members.find(m=>path==='/members/'+m.id),event=birthdayInfo()[0];
 const variant=path==='/world'?'portal':member?'portrait':'envelope';
 const title=event.days===0?`A little birthday magic for ${event.name}.`:member?`A little closer to ${member.name}.`:path==='/world'?'Your universe is unfolding.':'Something lovely is finding you.';
 const entry=document.createElement('div');entry.className='arrival arrival-'+variant;entry.setAttribute('role','status');entry.setAttribute('aria-live','polite');
 entry.innerHTML=`<div class="arrival-scene" aria-hidden="true"><div class="arrival-orbit"></div><div class="arrival-orbit orbit-two"></div><div class="arrival-object"><span>✧</span><i>FOR YOU</i></div><span class="arrival-spark spark-one">✦</span><span class="arrival-spark spark-two">♡</span><span class="arrival-spark spark-three">✳</span></div><div class="arrival-copy"><span class="arrival-label">PURPLE ARCHIVE / A PLACE JUST FOR YOU</span><h2>${esc(title)}</h2><p id="arrival-stage">Finding your little moments…</p><span class="arrival-dots" aria-hidden="true"><i></i><i></i><i></i></span><button class="arrival-skip" type="button">Let me wander in ↗</button></div>`;
 entry.querySelector('button').onclick=()=>endArrivalNow();document.body.append(entry);
}
function arrivalStage(text){const stage=document.querySelector('#arrival-stage');if(stage)stage.textContent=text;}
function endArrivalNow(){clearTimeout(arrivalTimer);const entry=document.querySelector('.arrival');if(!entry)return;entry.classList.add('is-ready');setTimeout(()=>entry.remove(),650);}
function finishArrival(){
 main.setAttribute('aria-busy','false');arrivalStage('A little place, made just for you. 오직 너에게.');
 const hero=main.querySelector('.clean-hero-photos img,.hero-art img,.world-stage img,.profile-portrait img');
 const imageReady=hero?.decode?hero.decode().catch(()=>{}):Promise.resolve();
 Promise.race([imageReady,new Promise(resolve=>setTimeout(resolve,700))]).then(()=>{arrivalTimer=setTimeout(endArrivalNow,Math.max(0,320-(performance.now()-arrivalStarted)));});
 observeImages(main);revealSections(main);personalisedCopy();
}
function observeImages(root){
 applyBirthdayRecipient(root);
 root.querySelectorAll('img').forEach(img=>{if(img.dataset.watched)return;img.dataset.watched='yes';if(img.complete&&img.naturalWidth){img.classList.add('image-ready');return;}img.addEventListener('load',()=>img.classList.add('image-ready'),{once:true});img.addEventListener('error',()=>{img.classList.add('image-ready','image-unavailable');img.alt='This memory is taking a moment to load.';},{once:true});});
}
let revealObserver=null;
function revealSections(root){
 if(!('IntersectionObserver' in window)||matchMedia('(prefers-reduced-motion: reduce)').matches)return;
 if(!revealObserver)revealObserver=new IntersectionObserver(entries=>{for(const entry of entries)if(entry.isIntersecting){entry.target.classList.add('has-arrived');revealObserver.unobserve(entry.target);}},{threshold:.04});
 root.querySelectorAll('.world-room,.constellation-room,.object-cabinet,.future-postcard').forEach(el=>{if(el.dataset.reveal)return;el.dataset.reveal='yes';el.classList.add('soft-reveal');revealObserver.observe(el);});
}

function growingRoomPlans(shown){
 const images=shown.filter(m=>m.kind==='image'&&m.category!=='sticker'),plans=[];
 for(let offset=0;offset<images.length;offset+=6){
  const index=offset/6,items=images.slice(offset,offset+6),number=String(index+1).padStart(2,'0');
  if(index===0)plans.push({id:'photo-wall',number,items,label:'The living moodboard / 오늘의 무드',title:'A wall full of <em>feelings.</em>',description:'A little collection, looking right back at you.',style:'wall'});
  else if(index===1)plans.push({id:'scrapbook',number,items,label:'Pages from your purple diary / 보라빛 일기',title:'Beautifully <em>all over the place.</em>',description:'A little organised chaos, just for you.',style:'scrapbook'});
  else{const [label,title,description]=chapterTitles[(index-2)%chapterTitles.length];plans.push({id:'chapter-'+number,number,items,label:label+' / '+number,title,description,style:chapterStyles[(index-2)%chapterStyles.length]});}
 }
 const formats=[['video','little-cinema','Your little cinema','Some moments deserve <em>a replay.</em>','cinema-grid'],['sticker','sticker-club','The sticker club','Tiny things. <em>Big personality.</em>','sticker-grid'],['audio','sound-room','The listening corner','Keep the <em>feeling.</em>','audio-grid'],['file','keepsake-box','Your keepsake box','A few <em>little treasures.</em>','keepsake-grid']];
 for(const [kind,id,label,title,style] of formats){const items=shown.filter(m=>kind==='sticker'?(m.kind==='sticker'||m.category==='sticker'):m.kind===kind&&m.category!=='sticker');for(let start=0;start<items.length;start+=6){const part=start/6;plans.push({id:id+(part?'-'+(part+1):''),number:String(plans.length+1).padStart(2,'0'),items:items.slice(start,start+6),label:label+(part?' / '+(part+1):''),title,description:'A little something for your collection.',style});}}
 return plans;
}
function chapterBody(plan){
 if(plan.style==='wall')return memoryWall(plan.items);
 if(plan.style==='scrapbook')return `<div class="scrapbook-desk"><div class="scrapbook-note"><span>dear you,</span><p>you deserve<br>little things<br>that feel like magic.</p><small lang="ko">너의 하루가 조금 더 다정하길.</small><b aria-hidden="true">♡</b></div>${plan.items.map(memoryCard).join('')}<span class="paper-star" aria-hidden="true">✺</span></div>`;
 return `<div class="${plan.style}">${plan.items.map(memoryCard).join('')}</div>`;
}
function renderGrowingRooms(shown){
 const gallery=document.querySelector('#gallery');if(!gallery)return;gallery.className='world-rooms'+(neat?' neat-rooms':'');
 if(!shown.length){document.querySelector('.world-jumps')?.remove();gallery.innerHTML=`<div class="empty"><h2>${savedOnly?'Your little collection starts here.':'A quiet corner, waiting for a memory.'}</h2><p>${savedOnly?'Tap a heart on any frame to keep it here.':'Try another member or format.'}<br>너를 위한 순간을 기다리고 있어.</p></div>`;return;}
 const plans=growingRoomPlans(shown);let used=0,openedCount=0;
 gallery.innerHTML=`<div class="collection-blueprint"><span class="blueprint-symbol" aria-hidden="true">✧</span><div><strong>${plans.length} little rooms. One world, just for you.</strong><p>A new room for every six photographs. More moments, more places to wander.</p></div><span>${shown.length}<small>KEEPSAKES</small></span></div>`;
 for(const plan of plans){const open=used<collectionLimit;used+=plan.items.length;if(open)openedCount+=plan.items.length;const style=neat?'contact-grid':plan.style;
  const body=()=>chapterBody({...plan,style});
  const section=document.createElement('section');section.id=plan.id;section.className='world-room chapter-room '+(style==='scrapbook'?'scrapbook-room':'');section.dataset.chapter=plan.number;
  section.innerHTML=`<details class="chapter-fold" ${open?'open':''}><summary><span class="chapter-index">${plan.number}</span><span class="chapter-summary"><small>${esc(plan.label)}</small><strong>${plan.title}</strong></span><span class="chapter-preview" aria-hidden="true">${plan.items.filter(m=>m.kind==='image').slice(0,2).map(m=>photo(m,'',true)).join('')}</span><span class="chapter-open-label">${plan.items.length} moments <i>＋</i></span></summary><div class="chapter-content">${open?`<p class="chapter-description">${plan.description}</p>`+body():''}</div></details>`;
  const details=section.querySelector('details'),content=section.querySelector('.chapter-content');
  details.addEventListener('toggle',()=>{if(details.open&&!content.children.length){content.innerHTML=`<p class="chapter-description">${plan.description}</p>`+body();bindMedia(content);bindSaves(content);observeImages(content);personalisedCopy(content);}});
  gallery.append(section);
 }
 if(shown.length>openedCount){gallery.insertAdjacentHTML('beforeend','<div class="more-memories"><p>Your next rooms are already waiting · open any room whenever you are ready</p><button class="button light" id="load-more">Unfold the next little rooms <span>↓</span></button></div>');document.querySelector('#load-more').onclick=()=>{collectionLimit+=18;renderGallery();};}
 bindMedia(gallery);bindSaves(gallery);observeImages(gallery);personalisedCopy(gallery);revealSections(gallery);
 let jumps=document.querySelector('.world-jumps');if(!jumps){jumps=document.createElement('nav');jumps.className='world-jumps';jumps.setAttribute('aria-label','Your memory rooms');document.querySelector('.world-stage').after(jumps);}
 jumps.innerHTML=plans.slice(0,4).map(p=>`<a href="#${p.id}" data-room-jump="${p.id}">${p.number} · ${esc(p.label.split(' / ')[0])}</a>`).join('')+`<label class="room-select-label"><span class="sr-only">Choose any room</span><select id="room-directory"><option value="">All ${plans.length} rooms ↓</option>${plans.map(p=>`<option value="${p.id}">${p.number} · ${esc(p.label.split(' / ')[0])}</option>`).join('')}</select></label>`;
 function jump(id){const section=document.getElementById(id);if(!section)return;section.querySelector('details').open=true;section.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth',block:'start'});}
 jumps.querySelectorAll('[data-room-jump]').forEach(link=>link.onclick=e=>{e.preventDefault();jump(link.dataset.roomJump);});jumps.querySelector('select').onchange=e=>jump(e.target.value);
}

function skySeed(){let seed=readLocal('purple-sky',null);if(typeof seed!=='number'){seed=Math.floor(Math.random()*1000000);writeLocal('purple-sky',seed);}return seed;}
function skyMemories(){const images=freshPhotos(),seed=skySeed()+visitSeed;return [...images].sort((a,b)=>tinyHash(a.id+seed)-tinyHash(b.id+seed)).slice(0,7);}
function constellationMarkup(){
 const stars=skyMemories(),points=[[12,32],[34,16],[53,37],[81,21],[86,65],[55,78],[25,66]];
 return `<svg class="sky-lines" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><polyline points="${points.slice(0,stars.length).map(p=>p.join(',')).join(' ')}"/></svg><div class="sky-you"><span>you</span><small>너만의 우주</small></div>${stars.map((m,i)=>`<button class="memory-star" style="--x:${points[i][0]}%;--y:${points[i][1]}%;--delay:${i*.35}s" data-media="${esc(m.id)}" aria-label="Discover ${esc(m.title)}"><span class="star-thumb">${photo(m)}</span><span class="star-light" aria-hidden="true">✦</span><small>0${i+1}</small></button>`).join('')}<span class="sky-corner">A SKY THAT ONLY LOOKS LIKE YOURS</span>`;
}
function mountPersonalRooms(){
 mountPhotoRooms();
}
function localDay(date=new Date()){return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;}
function rememberMemory(id){const ids=readLocal('purple-trail',[]);writeLocal('purple-trail',[id,...(Array.isArray(ids)?ids:[]).filter(item=>item!==id)].slice(0,8));updateMemoryTrail();}
function updateMemoryTrail(){const slot=document.querySelector('#memory-trail');if(!slot)return;const ids=readLocal('purple-trail',[]),items=(Array.isArray(ids)?ids:[]).map(id=>media.find(m=>m.id===id&&m.kind==='image')).filter(Boolean).slice(0,6);slot.hidden=!items.length;if(!items.length)return;slot.innerHTML=`<div class="trail-heading"><div><span class="eyebrow">The moments that found you</span><h2>A little trail of <em>your favourites.</em></h2></div><button class="text-link" id="clear-trail">Clear this trail</button></div><div class="trail-frames">${items.map(m=>`<button data-media="${esc(m.id)}" aria-label="Revisit ${esc(m.title)}">${photo(m)}<span>${esc(m.title)}</span></button>`).join('')}</div>`;bindMedia(slot);observeImages(slot);slot.querySelector('#clear-trail').onclick=()=>{writeLocal('purple-trail',[]);updateMemoryTrail();};}
