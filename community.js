/* A private conversation and a seven-day birthday quest. */
const privateChat={visitor:null,messages:new Map(),hasOlder:false,loading:false,sending:false,polling:false,replyTo:null,pending:null,timer:null};
function chatStatus(text,state='ready'){const label=document.querySelector('#chat-connection');if(label){label.textContent=text;label.dataset.state=state;}}
async function chatRequest(endpoint,body){
 const options={credentials:'same-origin',cache:'no-store',headers:{'X-Chat-Request':'1'}};
 if(body!==undefined){options.method='POST';options.headers['Content-Type']='application/json';options.body=JSON.stringify(body);}
 const response=await fetchTimed('/api/chat/'+endpoint,options);let data;
 try{data=await response.json();}catch{throw new Error('Your chat is taking a moment. Please try again.');}
 if(!response.ok){const error=new Error(data.error||'Could not reach your private chat.');error.status=response.status;throw error;}return data;
}
function mountPrivateChat(){
  if(!['/','/chat'].includes(path)||document.querySelector('#private-chat'))return;
 const section=document.createElement('section');section.id='private-chat';section.className='private-chat-room';
 section.innerHTML=`<div class="chat-invitation"><div class="eyebrow">A little line, just for you / 너에게</div><h2>You can<br>say <em>hello.</em></h2><p>A thought, a birthday wish, or just something that made you smile. Leave a little message for the person behind this space.</p><div class="chat-envelope" aria-hidden="true"><span>♡</span><i></i></div><p class="chat-promise">A private conversation.<br>Just you and me, right here.</p><small>Your messages are saved with this browser’s private chat. Replies appear here when I respond—not an automated chat.</small></div><div class="chat-window"><header class="chat-window-header"><span class="chat-host-avatar" aria-hidden="true">✧</span><div><strong>A little conversation</strong><span id="chat-connection" role="status" data-state="loading">Finding your private space…</span></div><button class="chat-reconnect" id="chat-reconnect" type="button" aria-label="Reconnect chat">↻</button></header><div class="chat-id-row"><span id="chat-id-label">Your private chat is getting ready</span><button id="copy-chat-id" type="button" hidden>Copy ID</button></div><div class="chat-transcript" id="chat-transcript" tabindex="0" aria-label="Your private conversation"><button id="chat-older" class="chat-older" type="button" hidden>Earlier messages ↑</button><div id="chat-messages"><div class="chat-empty"><span aria-hidden="true">✉</span><h3>A soft place for your words.</h3><p>Start with a little hello. Your conversation stays here, just for you.</p></div></div></div><button class="chat-new-replies" id="chat-new-replies" type="button" hidden>New message ↓</button><div id="chat-reply-preview" class="chat-reply-preview" hidden></div><form id="chat-form"><label class="sr-only" for="chat-input">Your message</label><textarea id="chat-input" maxlength="1600" rows="2" placeholder="A little hello goes a long way…" required disabled></textarea><div class="chat-composer-bottom"><small><span id="chat-char-count">0</span>/1600 · Shift + Enter for a new line</small><button class="chat-send" id="chat-send" type="submit" disabled>Send <span>↗</span></button></div><p id="chat-form-status" role="status"></p></form><footer class="chat-window-footer">Only this browser session can open this chat. Clearing site cookies or changing browsers starts a new one.</footer></div>`;
 document.querySelector('#home-chat-anchor,.quote-block')?.before(section);
 const invitation=section.querySelector('.chat-invitation');invitation.querySelector('.chat-envelope')?.remove();
 invitation.querySelector('.chat-promise').insertAdjacentHTML('beforebegin',`<div class="chat-photo-collage">${freshPhotos().slice(0,3).map((item,i)=>`<div style="--chat-photo-tilt:${[-9,3,12][i]}deg">${photo(item)}<span>${['a little hello','just for you','a reason to smile'][i]}</span></div>`).join('')}</div>`);
 section.querySelector('.chat-window-header strong').textContent='Chat with the creator';
 invitation.querySelector('small').textContent='You’re chatting with the creator of this fan space. Messages stay in your private conversation, and replies appear here when I respond.';
 const reconnect=section.querySelector('#chat-reconnect'),actions=document.createElement('div');actions.className='chat-header-actions';const collapse=document.createElement('button');collapse.id='chat-collapse';collapse.type='button';collapse.className='chat-collapse';collapse.textContent='−';collapse.setAttribute('aria-label','Collapse conversation');collapse.setAttribute('aria-expanded','true');reconnect.before(actions);actions.append(collapse,reconnect);
 section.querySelector('.chat-id-row').insertAdjacentHTML('afterend','<p class="chat-collapsed-note">Your conversation is tucked away. Expand it whenever you’re ready. ♡</p>');
 collapse.onclick=()=>{const collapsed=section.querySelector('.chat-window').classList.toggle('is-collapsed');collapse.textContent=collapsed?'＋':'−';collapse.setAttribute('aria-expanded',String(!collapsed));collapse.setAttribute('aria-label',collapsed?'Expand conversation':'Collapse conversation');};
 document.querySelector('.hero-note')?.insertAdjacentHTML('beforebegin','<a class="chat-hero-link" href="#private-chat">A little hello, just between you and me <span>↗</span></a>');
 document.querySelector('#chat-form').onsubmit=e=>{e.preventDefault();sendChatMessage();};
 const input=document.querySelector('#chat-input');
 input.addEventListener('input',()=>{document.querySelector('#chat-char-count').textContent=input.value.length;});
 input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();sendChatMessage();}});
 document.querySelector('#chat-reconnect').onclick=()=>connectChat();
 document.querySelector('#chat-older').onclick=()=>loadOlderChat();
 document.querySelector('#copy-chat-id').onclick=async()=>{if(!privateChat.visitor)return;try{await navigator.clipboard.writeText(privateChat.visitor.id);toast('Your chat ID is copied. ♡');}catch{toast('Your chat ID: '+privateChat.visitor.id);}};
 const transcript=document.querySelector('#chat-transcript');
 document.querySelector('#chat-new-replies').onclick=()=>{transcript.scrollTop=transcript.scrollHeight;document.querySelector('#chat-new-replies').hidden=true;};
  transcript.addEventListener('scroll',()=>{if(transcript.scrollHeight-transcript.scrollTop-transcript.clientHeight<70)document.querySelector('#chat-new-replies').hidden=true;});
  if('IntersectionObserver' in window)new IntersectionObserver(()=>acknowledgeVisibleReplies(),{threshold:[.45,.8]}).observe(transcript);
 connectChat();
 privateChat.timer=setInterval(()=>{if(!document.hidden)pollChat();},3500);
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)pollChat();});
}
function acceptChatIdentity(id){
 if(privateChat.visitor?.id===id)return false;
 privateChat.visitor={id};privateChat.messages.clear();privateChat.hasOlder=false;privateChat.replyTo=null;
 privateChat.pending=null;
 const label=document.querySelector('#chat-id-label');if(label)label.textContent='YOUR CHAT / '+id;
 const copy=document.querySelector('#copy-chat-id');if(copy)copy.hidden=false;renderReplyPreview();return true;
}
async function connectChat(){
 if(privateChat.loading)return;privateChat.loading=true;chatStatus('Connecting your private space…','loading');
 try{const visitor=await ensureVisitorSession();acceptChatIdentity(visitor.id);const data=await chatRequest('messages');mergeChat(data,{initial:true});document.querySelector('#chat-input').disabled=false;document.querySelector('#chat-send').disabled=false;chatStatus('Your private line is ready');document.querySelector('#chat-form-status').textContent='';acknowledgeVisibleReplies();}
 catch(error){chatStatus('Connection paused · tap ↻ to retry','error');document.querySelector('#chat-form-status').textContent=error.message;}
 finally{privateChat.loading=false;}
}
function quoteText(message){const quoted=privateChat.messages.get(message.reply_to);return quoted?quoted.body.slice(0,120):'An earlier message in this conversation';}
function chatTime(timestamp){return new Intl.DateTimeFormat(undefined,{hour:'numeric',minute:'2-digit'}).format(new Date(timestamp*1000));}
function renderChatMessages(){
 const root=document.querySelector('#chat-messages');if(!root)return;
 const items=[...privateChat.messages.values()].sort((a,b)=>a.id-b.id);
 if(!items.length){root.innerHTML='<div class="chat-empty"><span aria-hidden="true">✉</span><h3>A soft place for your words.</h3><p>Start with a little hello. Your conversation stays here, just for you.</p></div>';return;}
 let previousDay='';root.innerHTML=items.map(message=>{
  const date=new Date(message.created*1000),day=localDay(date),separator=day!==previousDay?`<div class="chat-day"><span>${esc(new Intl.DateTimeFormat(undefined,{day:'numeric',month:'short',year:'numeric'}).format(date))}</span></div>`:'';previousDay=day;
  const status=message.sender==='owner'?'From me':message.relay_state==='sent'?'Delivered':'Saved · awaiting delivery';
  return `${separator}<article class="chat-message ${message.sender==='owner'?'from-host':'from-visitor'}" data-message="${message.id}"><div class="chat-bubble">${message.reply_to?`<blockquote>${esc(quoteText(message))}</blockquote>`:''}<p>${esc(message.body)}</p></div><div class="chat-message-meta"><time datetime="${date.toISOString()}">${esc(chatTime(message.created))}</time><span>${status}</span><button type="button" data-chat-reply="${message.id}" aria-label="Reply to this message">↩</button></div></article>`;
 }).join('');
 root.querySelectorAll('[data-chat-reply]').forEach(button=>button.onclick=()=>{privateChat.replyTo=Number(button.dataset.chatReply);renderReplyPreview();document.querySelector('#chat-input').focus();});
}
function mergeChat(data,{initial=false,older=false,sent=false}={}){
 const transcript=document.querySelector('#chat-transcript');if(!transcript)return;
 const changedIdentity=data.visitor_id&&acceptChatIdentity(data.visitor_id);
 if(changedIdentity)initial=true;
 const oldHeight=transcript.scrollHeight,oldTop=transcript.scrollTop,atBottom=oldHeight-oldTop-transcript.clientHeight<80;
 let changed=initial,hasNewReply=false;
 for(const message of data.messages||[]){const old=privateChat.messages.get(message.id);if(!old||JSON.stringify(old)!==JSON.stringify(message)){changed=true;if(!old&&message.sender==='owner')hasNewReply=true;privateChat.messages.set(message.id,message);}}
 for(const update of data.deliveries||[]){const old=privateChat.messages.get(update.id);if(old&&old.relay_state!==update.relay_state){old.relay_state=update.relay_state;changed=true;}}
 if(initial||older)privateChat.hasOlder=!!data.has_older;
 document.querySelector('#chat-older').hidden=!privateChat.hasOlder;
 if(changed){renderChatMessages();if(older)transcript.scrollTop=oldTop+(transcript.scrollHeight-oldHeight);else if(initial||sent||atBottom)transcript.scrollTop=transcript.scrollHeight;else transcript.scrollTop=oldTop;}
  if(hasNewReply&&!initial&&!older&&!atBottom){document.querySelector('#chat-new-replies').hidden=false;document.querySelector('#chat-form-status').textContent='A new reply is waiting below.';}
  acknowledgeVisibleReplies();
}
async function pollChat(){
 if(!privateChat.visitor||privateChat.polling||privateChat.loading)return;privateChat.polling=true;
 try{let more=true,loops=0;while(more&&loops++<4){const latest=Math.max(0,...privateChat.messages.keys());const data=await chatRequest('messages?after='+latest);const changed=data.visitor_id&&data.visitor_id!==privateChat.visitor.id;if(changed){acceptChatIdentity(data.visitor_id);mergeChat(await chatRequest('messages'),{initial:true});break;}mergeChat(data);more=data.has_newer;}chatStatus('Your private line is ready');}
 catch(error){chatStatus(error.status===401?'Your session needs reconnecting':'Connection paused · retrying quietly','error');}
 finally{privateChat.polling=false;}
}
async function loadOlderChat(){
 if(privateChat.loading||!privateChat.messages.size)return;privateChat.loading=true;const button=document.querySelector('#chat-older');button.disabled=true;
 try{const oldest=Math.min(...privateChat.messages.keys());mergeChat(await chatRequest('messages?before='+oldest),{older:true});}
 catch(error){document.querySelector('#chat-form-status').textContent=error.message;}
 finally{privateChat.loading=false;button.disabled=false;}
}
function renderReplyPreview(){const box=document.querySelector('#chat-reply-preview');if(!box)return;const message=privateChat.messages.get(privateChat.replyTo);box.hidden=!message;if(message){box.innerHTML=`<span>Replying to ${message.sender==='owner'?'me':'your message'}<strong>${esc(message.body.slice(0,100))}</strong></span><button type="button" aria-label="Cancel reply">×</button>`;box.querySelector('button').onclick=()=>{privateChat.replyTo=null;renderReplyPreview();};}}
async function sendChatMessage(){
 const input=document.querySelector('#chat-input'),status=document.querySelector('#chat-form-status'),button=document.querySelector('#chat-send');
 if(privateChat.sending||!privateChat.visitor||input.disabled)return;const text=input.value.trim();if(!text){status.textContent='Write a little message first.';return;}
 if(text.length>1600){status.textContent='Keep this little message within 1600 characters.';return;}
 if(!privateChat.pending||privateChat.pending.text!==text||privateChat.pending.reply_to!==privateChat.replyTo){privateChat.pending={text,reply_to:privateChat.replyTo,client_id:crypto.randomUUID?crypto.randomUUID():Date.now().toString(36)+'_'+Math.random().toString(36).slice(2)+'_'+Math.random().toString(36).slice(2)};}
 privateChat.sending=true;button.disabled=true;button.textContent='Sending…';status.textContent='Keeping your words safe…';
 const payload=privateChat.pending;
 try{const result=await chatRequest('messages',payload);mergeChat({messages:[result.message],visitor_id:result.visitor_id},{sent:true});if(input.value.trim()===text){input.value='';document.querySelector('#chat-char-count').textContent='0';}privateChat.pending=null;if(privateChat.replyTo===payload.reply_to)privateChat.replyTo=null;renderReplyPreview();status.textContent='Message saved. A reply will appear here when I respond. ♡';}
 catch(error){status.textContent=error.message+' Your draft is still here—tap send to retry.';if(error.status===401)chatStatus('Reconnect your private chat to continue','error');}
 finally{privateChat.sending=false;button.disabled=false;button.innerHTML='Send <span>↗</span>';}
}

const birthdayDoors=[
 {icon:'✉',name:'A little beginning',hint:'A note to start the countdown.'},
 {icon:'♡',name:'A memory to keep',hint:'Choose a little favourite.'},
 {icon:'안녕',name:'A wish in Korean',hint:'A few words from the heart.'},
 {icon:'?',name:'A tiny birthday quiz',hint:'How well do you know him?'},
 {icon:'✦',name:'Dress up the cake',hint:'Pick a colour for the candles.'},
 {icon:'✎',name:'A wish before midnight',hint:'Keep a little birthday thought.'},
 {icon:'♫',name:'Set the birthday mood',hint:'Choose a musical chapter.'},
];
function questState(info){const value=readLocal(`quest-${info.id}-${info.nextYear}`,{});return value&&typeof value==='object'&&!Array.isArray(value)?value:{};}
function questUnlocked(info,index){return Number.isInteger(index)&&index>=0&&index<7&&info.days<=7-index;}
function birthdayPhrase(info){const last=info.short.charCodeAt(info.short.length-1)-0xAC00;return info.short+(last>=0&&last<11172&&last%28===0?'야':'아')+', 생일 축하해!';}
function questDate(info,index){const [day,month]=info.birth.split(' ');const date=new Date(Date.UTC(info.nextYear,birthMonths.indexOf(month),Number(day))-(7-index)*86400000);return new Intl.DateTimeFormat('en-GB',{day:'numeric',month:'short',timeZone:'UTC'}).format(date);}
function questDialog(){let dialog=document.querySelector('#quest-dialog');if(dialog)return dialog;dialog=document.createElement('dialog');dialog.id='quest-dialog';dialog.setAttribute('aria-labelledby','quest-dialog-title');dialog.innerHTML='<button class="close-dialog" type="button" aria-label="Close birthday surprise">×</button><div id="quest-dialog-content"></div>';dialog.querySelector('button').onclick=()=>dialog.close();dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});document.body.append(dialog);return dialog;}
function mountBirthdayQuest(info,slot){
 if(path==='/world'){slot.insertAdjacentHTML('beforeend',`<a class="quest-world-link" href="/members/${info.id}#birthday-quest">Follow ${info.name}’s birthday countdown quest ↗</a>`);return;}
 const state=questState(info),completed=Array.from({length:7},(_,i)=>state['day'+i]===true).filter(Boolean).length;
 const quest=document.createElement('section');quest.id='birthday-quest';quest.className='birthday-quest';
 quest.innerHTML=`<div class="quest-heading"><div><div class="eyebrow">Seven days of little surprises / 생일을 기다리며</div><h2>A little closer<br>to <em>${info.name} day.</em></h2><p>${info.days>7?`The first door opens in ${info.days-7} days. A new little surprise follows each day.`:info.days===0?'The candles are glowing. Every door and your birthday finale are open.':'Your countdown has begun. Open the available doors and collect a little seal each day.'}</p></div><div class="quest-seal"><strong>${completed}<span>/7</span></strong><small>LITTLE SEALS<br>COLLECTED BY YOU</small></div></div><div class="quest-doors">${birthdayDoors.map((door,index)=>{const unlocked=questUnlocked(info,index),done=state['day'+index]===true;return `<button class="quest-door ${unlocked?'unlocked':'locked'} ${done?'collected':''}" data-quest-day="${index}" ${unlocked?'':'disabled'} aria-label="${esc(door.name)} · ${unlocked?'open now':'opens '+questDate(info,index)}"><small>D−${7-index}</small><span class="quest-door-icon" aria-hidden="true">${unlocked?door.icon:'◇'}</span><strong>${door.name}</strong><span class="quest-door-date">${done?'Collected ♡':unlocked?'Open your surprise ↗':questDate(info,index)}</span></button>`;}).join('')}</div><div class="quest-finale"><span aria-hidden="true">✧</span><div><strong>One last little keepsake. Just for you.</strong><p>${info.days===0?'Your birthday card is ready—even if you missed a day.':'The birthday finale opens on '+info.birth.split(' ').slice(0,2).join(' ')+'.'}</p></div><button class="button light" id="quest-finale-button" ${info.days===0?'':'disabled'}>Birthday finale ↗</button></div><p class="quest-footnote">Unlocks follow Seoul time (KST). Your collected seals and wish stay in this browser. Earlier doors stay open during the countdown.</p>`;
 slot.append(quest);quest.querySelectorAll('[data-quest-day]').forEach(button=>button.onclick=()=>openQuestDoor(info,Number(button.dataset.questDay)));quest.querySelector('#quest-finale-button').onclick=()=>openQuestFinale(info);
}
function collectQuest(info,index,extra={}){const state={...questState(info),...extra,['day'+index]:true};if(!writeLocal(`quest-${info.id}-${info.nextYear}`,state)){toast('Browser storage is unavailable; this seal cannot be kept yet.');return false;}const quest=document.querySelector('#birthday-quest');if(quest){const button=quest.querySelector(`[data-quest-day="${index}"]`);button?.classList.add('collected');if(button)button.querySelector('.quest-door-date').textContent='Collected ♡';quest.querySelector('.quest-seal strong').innerHTML=Array.from({length:7},(_,i)=>state['day'+i]===true).filter(Boolean).length+'<span>/7</span>';}const status=document.querySelector('#quest-result');if(status)status.textContent='A little seal, collected just for you. ♡';return true;}
function openQuestDoor(info,index){
 // Recheck the current KST date rather than relying only on a disabled button.
 const current=birthdayInfo().find(m=>m.id===info.id);if(current.nextYear!==info.nextYear||!questUnlocked(current,index))return;
 const dialog=questDialog(),root=document.querySelector('#quest-dialog-content'),door=birthdayDoors[index],state=questState(info),photos=memberPhotos(info.id),memory=photos[index%photos.length]||photoFor(info.id);
 root.innerHTML=`<div class="quest-dialog-label">D−${7-index} · ${esc(info.name)} / ${esc(info.short)}</div><h2 id="quest-dialog-title">${door.name}</h2><p class="quest-dialog-hint">${door.hint}</p><div id="quest-surprise"></div><p id="quest-result" role="status"></p>`;
 const surprise=root.querySelector('#quest-surprise');
 if(index===0){surprise.innerHTML=`<div class="quest-letter"><p>Dear you,</p><p>Seven little days. A little excitement. A birthday worth slowing down for.</p><p>This countdown is a place to keep your favourite things about ${esc(info.name)}—one tiny surprise at a time.</p><p lang="ko">너의 기다림이 조금 더 특별해지길. ♡</p></div><button class="button light" id="collect-seal">Keep my first little seal ♡</button>`;surprise.querySelector('button').onclick=()=>collectQuest(info,index);}
 if(index===1){surprise.innerHTML=`<div class="quest-memory">${photo(memory,info.name)}</div><p>Keep a ${esc(info.name)} moment in your saved collection.</p><button class="button light" id="quest-save">Save this memory ♡</button>`;surprise.querySelector('button').onclick=()=>{if(memory&&!saved.has(memory.id))toggleSave(memory.id);collectQuest(info,index);};}
 if(index===2){const phrase=birthdayPhrase(info);surprise.innerHTML=`<div class="quest-phrase"><strong lang="ko">${esc(phrase)}</strong><p>“${esc(info.name)}, happy birthday!”</p></div><button class="button light" id="quest-copy">Copy a little birthday wish ♡</button>`;const copy=surprise.querySelector('button');copy.onclick=async()=>{try{await navigator.clipboard.writeText(phrase);collectQuest(info,index);}catch{document.querySelector('#quest-result').textContent='You can select the phrase above to copy it, or read it and collect your seal.';copy.textContent='Got it · collect my seal';copy.onclick=()=>collectQuest(info,index);}};}
 if(index===3){const places=[...new Set([info.place,...members.map(m=>m.place)])].slice(0,3).sort((a,b)=>tinyHash(a+info.id)-tinyHash(b+info.id));surprise.innerHTML=`<p class="quest-question">Which place is ${esc(info.name)} from?</p><div class="quest-options">${places.map(place=>`<button type="button" data-place="${esc(place)}">${esc(place)}</button>`).join('')}</div>`;surprise.querySelectorAll('button').forEach(button=>button.onclick=()=>{if(button.dataset.place===info.place){button.classList.add('chosen');collectQuest(info,index);}else{document.querySelector('#quest-result').textContent='Not quite—take another little guess.';button.disabled=true;}});}
 if(index===4){surprise.innerHTML=`<div class="quest-cake" data-cake-color="lilac">${document.querySelector('.cake-scene')?.outerHTML||'<span>🎂</span>'}</div><p>A little colour for the celebration. Which one feels like you?</p><div class="quest-options">${['Lilac','Rose','Butter'].map(color=>`<button type="button" data-cake="${color.toLowerCase()}">${color} ♡</button>`).join('')}</div>`;surprise.querySelectorAll('[data-cake]').forEach(button=>button.onclick=()=>{surprise.querySelector('.quest-cake').dataset.cakeColor=button.dataset.cake;surprise.querySelectorAll('button').forEach(b=>b.classList.toggle('chosen',b===button));collectQuest(info,index,{cake:button.dataset.cake});});}
 if(index===5){surprise.innerHTML=`<form id="quest-wish-form"><label for="quest-wish">A little wish for ${esc(info.name)}</label><textarea id="quest-wish" maxlength="180" required placeholder="May this year bring you…">${esc(state.wish||'')}</textarea><button class="button light" type="submit">Keep this little wish ♡</button></form>`;surprise.querySelector('form').onsubmit=e=>{e.preventDefault();const wish=surprise.querySelector('textarea').value.trim();if(wish)collectQuest(info,index,{wish});};}
 if(index===6){surprise.innerHTML=`<p class="quest-question">Pick a musical chapter for ${esc(info.name)}’s birthday.</p><div class="quest-options">${info.works.map(work=>`<button type="button" data-work="${esc(work)}">♫ ${esc(work)}</button>`).join('')}</div><small>A personal pick for your keepsake, not an audio player.</small>`;surprise.querySelectorAll('button').forEach(button=>button.onclick=()=>{surprise.querySelectorAll('button').forEach(b=>b.classList.toggle('chosen',b===button));collectQuest(info,index,{soundtrack:button.dataset.work});});}
 dialog.showModal();observeImages(dialog);
}
function openQuestFinale(info){const current=birthdayInfo().find(m=>m.id===info.id);if(current.days!==0||current.nextYear!==info.nextYear)return;const dialog=questDialog(),state=questState(info);document.querySelector('#quest-dialog-content').innerHTML=`<div class="quest-dialog-label">THE BIRTHDAY FINALE / 생일 축하해</div><h2 id="quest-dialog-title">${esc(info.name)} day, just for you.</h2><div class="birthday-keepsake"><span>HAPPY BIRTHDAY</span><strong>${esc(info.name)}</strong><p lang="ko">${esc(info.korean)} · 생일 축하해</p><div aria-hidden="true">✦ ♡ ✦</div><p>${esc(state.wish||'A little universe of happy wishes, kept with love.')}</p><small>${info.birth.split(' ').slice(0,2).join(' ')} ${info.nextYear} · YOUR LITTLE BIRTHDAY KEEPSAKE</small></div><button class="button light" id="download-quest-card">Keep my birthday card ↓</button><p class="quest-dialog-hint">A little illustrated SVG keepsake, made here in your browser.</p>`;document.querySelector('#download-quest-card').onclick=()=>downloadQuestCard(info,state);dialog.showModal();confetti();}
function questWishLines(wish){
 const lines=[];let line='',width=0;
 for(const character of Array.from(String(wish).replace(/\s+/g,' ').trim()).slice(0,180)){const units=character.codePointAt(0)>255?2:1;if(width+units>44){lines.push(line);line='';width=0;}line+=character;width+=units;}
 if(line)lines.push(line);return lines;
}
function downloadQuestCard(info,state){
 const lines=questWishLines(state.wish||'A universe of happy wishes, just for you.');
 const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="900" height="1200" viewBox="0 0 900 1200"><defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#f8f0ff"/><stop offset="1" stop-color="#dfc6f1"/></linearGradient></defs><rect width="900" height="1200" rx="30" fill="url(#bg)"/><rect x="45" y="45" width="810" height="1110" rx="20" fill="none" stroke="#b48bc9"/><g text-anchor="middle" fill="#8657a0" font-family="Georgia,serif"><text x="450" y="200" font-size="25" letter-spacing="7">HAPPY BIRTHDAY</text><text x="450" y="350" font-size="85">${esc(info.name)}</text><text x="450" y="445" font-size="32">${esc(info.korean)} · 생일 축하해</text><text x="450" y="590" font-size="80">✦ ♡ ✦</text>${lines.map((text,i)=>`<text x="450" y="${680+i*34}" font-size="22">${esc(text)}</text>`).join('')}<text x="450" y="1040" font-size="24">${esc(info.birth.split(' ').slice(0,2).join(' '))} ${info.nextYear}</text><text x="450" y="1090" font-size="18" letter-spacing="3">JUST FOR YOU · PURPLE ARCHIVE</text></g></svg>`;
 const url=URL.createObjectURL(new Blob([svg],{type:'image/svg+xml;charset=utf-8'})),link=document.createElement('a');link.href=url;link.download=info.id+'-birthday-'+info.nextYear+'.svg';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
}
