/* Original files, native proportions, and a quieter homepage. */
let imageShape='all';
function naturalPhoto(item,alt='',lazy=true){
 if(!item)return `<div class="fallback-photo">${esc(alt||'♡')}</div>`;
 const width=Number(item.width)||0,height=Number(item.height)||0;
 const dimensions=width>0&&height>0?`width="${width}" height="${height}" style="--natural-width:${width}px;--natural-height:${height}px"`:'';
 return `<img src="${local(item.preview)}" alt="${esc(alt||item.title)}" ${dimensions} data-full-image="true" decoding="async" ${lazy?'loading="lazy"':'fetchpriority="high"'}>`;
}
function imageDetails(item){if(!item.width||!item.height)return 'Original file';const bytes=Number(item.original_bytes)||0;const size=bytes?bytes>=1048576?(bytes/1048576).toFixed(1)+' MB':Math.round(bytes/1024)+' KB':'';return `${item.width} × ${item.height} · ${item.orientation||'image'}${size?' · '+size:''}`;}
function renderCleanHome(){
 document.body.classList.add('clean-home');document.title='Purple Archive · A little closer to the seven';
 const featured=visualMembers();
 main.innerHTML=`<div class="container clean-home-container"><section class="clean-hero"><div class="clean-hero-copy"><div class="eyebrow">BTS, in your own little corner</div><h1>A little closer.<br>A little more <em>purple.</em></h1><p lang="ko" class="korean">사진, 음악, 그리고 너를 위한 이야기.</p><p>Good photos. Seven individual stories. Music to come back to. A simple place to explore what you love.</p><div class="hero-actions"><a class="button" href="/world">Explore the photos ↗</a><a class="text-link" href="#private-chat">Say a little hello ↗</a></div><span data-day-greeting class="visit-greeting"></span></div><div class="clean-hero-photos"><button class="clean-group-photo" data-media="${esc(photoFor('all')?.id||'')}" aria-label="Open the BTS photo">${photo(photoFor('all'),'BTS',false)}</button><div class="clean-portrait-pair">${featured.slice(0,2).map(m=>`<a href="/members/${m.id}">${photo(photoFor(m.id),m.name,false)}<span>${m.name} <small lang="ko">${m.short}</small> ↗</span></a>`).join('')}</div></div></section><nav class="clean-paths" aria-label="Choose a part of the archive">${[['/story','The story','How it began'],['/music','The music','Find a listening chapter'],['/eras','The eras','Follow the journey'],['/birthdays','Birthdays','A little celebration']].map(([href,title,text])=>`<a href="${href}"><strong>${title} ↗</strong><span>${text}</span></a>`).join('')}</nav><section class="section clean-members" id="members">${sectionHeading('Seven names / 일곱의 이야기','Meet the <em>seven.</em>','Open a profile for the story, the music and the photographs.')}<div class="member-grid">${memberCards()}</div></section><section class="clean-photo-section" id="new-memories">${sectionHeading('A fresh photo edit / 새로운 순간들','The whole <em>picture.</em>','Original files. Natural proportions. Every edge stays in the frame.')}<div class="natural-photo-grid" id="home-memory-grid"></div><div class="clean-gallery-link"><a class="button light" href="/world">See the full collection ↗</a></div></section><div class="home-birthday-anchor"></div><div id="home-chat-anchor"></div></div>`;
  document.querySelector('.clean-hero .hero-actions').insertAdjacentHTML('afterend','<a class="home-birthday-replay" href="/surprise?replay=1">Replay Shivani’s birthday opening · 생일 다시 보기 ↻</a>');
  renderCleanPhotoGrid();bindMedia(main);
}
function renderCleanPhotoGrid(){const grid=document.querySelector('#home-memory-grid');if(!grid)return;grid.innerHTML=freshPhotos().slice(0,6).map(memoryCard).join('');bindMedia(grid);bindSaves(grid);observeImages(grid);}
function mountShapeFilter(){const controls=document.querySelector('.toolbar-options');if(!controls||document.querySelector('#image-shape'))return;const label=document.createElement('label');label.className='shape-filter';label.innerHTML='<span class="sr-only">Image dimensions</span><select id="image-shape" aria-label="Image dimensions"><option value="all">All shapes</option><option value="portrait">Portrait</option><option value="landscape">Landscape</option><option value="square">Square</option></select>';controls.prepend(label);label.querySelector('select').onchange=e=>{imageShape=e.target.value;collectionLimit=18;renderGallery();};}
function mountOriginalControls(item){
 if(item.kind!=='image')return;
 const root=document.querySelector('#viewer-content');root.insertAdjacentHTML('beforeend',`<div class="original-controls"><span>${esc(imageDetails(item))}</span><button type="button" id="original-pixels" aria-pressed="false">View at original pixels ↗</button></div>`);
 root.querySelector('#original-pixels').onclick=e=>{const surface=root.querySelector('.viewer-media'),native=surface.classList.toggle('native-pixels');e.currentTarget.setAttribute('aria-pressed',String(native));e.currentTarget.textContent=native?'Fit the full picture ↙':'View at original pixels ↗';};
}

/* Place each next card in the shortest column instead of reserving row height. */
const packedPhotoRules=[
 ['.natural-photo-grid,.contact-grid,.arch-gallery,.light-gallery,.ribbon-gallery,.window-gallery,.scrapbook-desk,.profile-memories .gallery','.memory'],
 ['.memory-wall','.wall-cell'],
 ['.member-grid','.member-card'],
 ['.release-grid','.release-card'],
 ['.solo-grid','.solo-card'],
 ['.birthday-grid','.birthday-person'],
 ['.explore-card-grid','.explore-card'],
 ['.world-stage','.stage-photo'],
 ['.korea-destination-grid','.korea-place-card'],
];
const packedPhotoSelector=packedPhotoRules.map(rule=>rule[0]).join(',');
const packedPhotoStates=new Map(),packedPhotoPending=new Set();
let packedPhotoFrame=0,packedPhotoScan=0;
function requestPhotoPacking(state){
 packedPhotoPending.add(state);
 if(packedPhotoFrame)return;
 packedPhotoFrame=requestAnimationFrame(()=>{packedPhotoFrame=0;const batch=[...packedPhotoPending];packedPhotoPending.clear();for(const item of batch)packPhotoCards(item);});
}
function packPhotoCards(state){
 const root=state.root;if(!root.isConnected||!root.clientWidth||!state.items.length)return;
 root.classList.add('packed-masonry');root.dataset.packed='';
 const style=getComputedStyle(root),number=value=>parseFloat(value)||0;
 const left=number(style.paddingLeft),right=number(style.paddingRight),top=number(style.paddingTop),bottom=number(style.paddingBottom);
 const available=root.clientWidth-left-right;if(available<=0)return;
 const gap=number(style.getPropertyValue('--packed-gap'))||16;
 const columns=Math.min(state.items.length,Math.max(1,parseInt(style.getPropertyValue('--packed-columns'))||3));
 const width=(available-gap*(columns-1))/columns;
 const heights=Array(columns).fill(0);
 root.dataset.packedColumns=String(columns);state.rootWidth=root.clientWidth;
 // Set all widths before measuring so every height includes the natural image
 // ratio, its caption, borders and padding at this exact viewport size.
 for(const item of state.items){item.classList.add('packed-item');item.dataset.packedItem='';item.style.setProperty('--packed-width',width+'px');}
 for(const item of state.items){
  let column=0;for(let i=1;i<columns;i++)if(heights[i]<heights[column])column=i;
  item.style.setProperty('--packed-x',(left+column*(width+gap))+'px');
  item.style.setProperty('--packed-y',(top+heights[column])+'px');
  item.dataset.packedColumn=String(column);
  heights[column]+=item.getBoundingClientRect().height+gap;
 }
 const borders=number(style.borderTopWidth)+number(style.borderBottomWidth);
 root.style.setProperty('--packed-height',Math.ceil(top+Math.max(...heights)-gap+bottom+borders)+'px');
}
function syncPhotoPacking(){
 packedPhotoScan=0;
 const mainElement=document.querySelector('main');if(!mainElement)return;
 for(const [root,state] of packedPhotoStates){if(!root.isConnected||!root.matches(packedPhotoSelector)){state.observer.disconnect();packedPhotoPending.delete(state);packedPhotoStates.delete(root);}}
 for(const root of mainElement.querySelectorAll(packedPhotoSelector)){
  const rule=packedPhotoRules.find(([selector])=>root.matches(selector));
  const items=[...root.children].filter(child=>child.matches(rule[1]));
  let state=packedPhotoStates.get(root);
  if(!state){
   state={root,items:[],rootWidth:0,observer:null};
   state.observer=new ResizeObserver(entries=>{if(entries.some(entry=>entry.target!==root||Math.abs(root.clientWidth-state.rootWidth)>.5))requestPhotoPacking(state);});
   packedPhotoStates.set(root,state);state.observer.observe(root);
  }
  if(items.length!==state.items.length||items.some((item,index)=>item!==state.items[index])){
   state.items.forEach(item=>state.observer.unobserve(item));state.items=items;
   items.forEach(item=>state.observer.observe(item));
   if(items.length)requestPhotoPacking(state);else{root.classList.remove('packed-masonry');root.removeAttribute('data-packed');root.style.removeProperty('--packed-height');}
  }
 }
}
function startPhotoPacking(){
 if(!('ResizeObserver' in window)||!('MutationObserver' in window))return;
 const root=document.querySelector('main');if(!root)return;
 const observer=new MutationObserver(()=>{if(!packedPhotoScan)packedPhotoScan=requestAnimationFrame(syncPhotoPacking);});
 observer.observe(root,{childList:true,subtree:true});
 syncPhotoPacking();
 window.addEventListener('resize',()=>{for(const state of packedPhotoStates.values())requestPhotoPacking(state);},{passive:true});
 document.fonts?.ready.then(()=>{for(const state of packedPhotoStates.values())requestPhotoPacking(state);});
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)for(const state of packedPhotoStates.values())requestPhotoPacking(state);});
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',startPhotoPacking,{once:true});else startPhotoPacking();
