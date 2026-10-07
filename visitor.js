/* Shared visitor identity and in-page notifications; never requests OS notifications. */
const siteVisitor={id:null,promise:null,timer:null,busy:false,visitId:null,visitReported:false,latestRead:0};
function visitorRequestId(){return crypto.randomUUID?crypto.randomUUID():Date.now().toString(36)+'_'+Math.random().toString(36).slice(2)+'_'+Math.random().toString(36).slice(2);}
async function ensureVisitorSession(){
 if(siteVisitor.promise)return siteVisitor.promise;
 siteVisitor.promise=(async()=>{let data=await chatRequest('session');if(!data.active)data=await chatRequest('session',{});if(!data.visitor?.id)throw new Error('Your private conversation could not be prepared.');if(siteVisitor.id!==data.visitor.id)siteVisitor.latestRead=0;siteVisitor.id=data.visitor.id;return data.visitor;})();
 try{return await siteVisitor.promise;}catch(error){siteVisitor.promise=null;throw error;}
}
async function reportSiteVisit(){
 if(!siteVisitor.visitId)siteVisitor.visitId=visitorRequestId();
 try{await ensureVisitorSession();await chatRequest('visit',{request_id:siteVisitor.visitId,page:location.pathname});siteVisitor.visitReported=true;}catch{siteVisitor.visitReported=false;}
}
function mountMessageNotice(){
 if(document.querySelector('#visitor-message-notice'))return;
 const root=document.createElement('aside');root.className='visitor-message-notice';root.id='visitor-message-notice';root.hidden=true;root.setAttribute('aria-label','Private message notification');
 root.innerHTML='<button id="open-visitor-message" type="button"><span class="message-notice-icon" aria-hidden="true">✉</span><span><strong>A message for you</strong><small id="visitor-message-count" role="status">Tap to read and reply · 메시지가 왔어요</small></span><b aria-hidden="true">↗</b></button>';root.querySelector('button').onclick=()=>{location.href='/chat';};document.body.append(root);
 const shortcut=document.createElement('a');shortcut.id='private-chat-shortcut';shortcut.className='private-chat-shortcut';shortcut.href='/chat';shortcut.innerHTML='<span aria-hidden="true">♡</span> Your private chat <small>대화</small>';shortcut.setAttribute('aria-label','Open your private chat');document.body.append(shortcut);
 if(path==='/chat')shortcut.hidden=true;
}
function chatIsActuallyVisible(){const transcript=document.querySelector('#chat-transcript');if(!transcript||document.hidden||document.querySelector('dialog[open]')||document.querySelector('.chat-window.is-collapsed'))return false;const box=transcript.getBoundingClientRect();const amount=Math.max(0,Math.min(box.bottom,innerHeight)-Math.max(box.top,0));return box.height>0&&amount/Math.min(box.height,innerHeight)>.45;}
async function acknowledgeVisibleReplies(){
 if(!chatIsActuallyVisible()||!privateChat.visitor)return;
 let latest=0;for(const message of privateChat.messages.values())if(message.sender==='owner')latest=Math.max(latest,message.id);
 if(!latest||latest<=siteVisitor.latestRead)return;
 try{const data=await chatRequest('read',{through_id:latest});siteVisitor.latestRead=Math.max(siteVisitor.latestRead,latest);renderMessageNotice(data);}catch{}
}
function renderMessageNotice(data){
 const root=document.querySelector('#visitor-message-notice');if(!root)return;
 const waiting=Number(data.unread_count)>0&&Number(data.latest_id)>siteVisitor.latestRead;
 root.hidden=!waiting;
 const shortcut=document.querySelector('#private-chat-shortcut');if(shortcut)shortcut.hidden=waiting||path==='/chat';
 if(waiting)document.querySelector('#visitor-message-count').textContent=(data.unread_count>1?data.unread_count+' replies are waiting':'Tap to read and reply')+' · 메시지가 왔어요';
}
async function pollPrivateNotifications(){
 if(siteVisitor.busy||document.hidden||!siteVisitor.id)return;siteVisitor.busy=true;
 try{if(!siteVisitor.visitReported)await reportSiteVisit();await acknowledgeVisibleReplies();const data=await chatRequest('notifications');renderMessageNotice(data);}catch(error){if(error.status===401){siteVisitor.promise=null;siteVisitor.id=null;document.querySelector('#visitor-message-notice').hidden=true;}}
 finally{siteVisitor.busy=false;}
}
function startVisitorServices(){
 if(siteVisitor.timer)return;mountMessageNotice();
 reportSiteVisit().then(pollPrivateNotifications);
 siteVisitor.timer=setInterval(pollPrivateNotifications,3500);
 document.addEventListener('visibilitychange',()=>{if(!document.hidden){if(!siteVisitor.id)reportSiteVisit().then(pollPrivateNotifications);else pollPrivateNotifications();}});
 window.addEventListener('pageshow',event=>{if(event.persisted){siteVisitor.visitId=visitorRequestId();siteVisitor.visitReported=false;reportSiteVisit().then(pollPrivateNotifications);}});
}
function renderPrivateChatPage(){document.title='Your private conversation · 대화';main.innerHTML='<div class="container dedicated-chat-page"><div class="chat-page-heading"><a href="/korea">← Back to your Korean world · 한국으로</a><h1>A message,<br><em>just for you.</em></h1><p>Your conversation stays with your private browser ID.</p></div><div id="home-chat-anchor"></div></div>';mountPrivateChat();}
let oneTimeNoteRequest=null;
function notePresentation(note,heading='h2'){return `<article class="one-time-note-content"><span class="korean-note-heart" aria-hidden="true">🫰 ♡</span><div class="korean-note-label">시바니에게 · TO SHIVANI</div><${heading}>I'm really sorry</${heading}><p class="korean-note-subtitle" lang="ko">정말 미안해.</p><p>${esc(note.greeting)}</p>${note.paragraphs.map(paragraph=>`<p>${esc(paragraph)}</p>`).join('')}<div class="korean-note-signoff">${esc(note.signoff)} <span>♡</span></div></article>`;}
async function consumeOneTimeNote(){await ensureVisitorSession();if(!oneTimeNoteRequest)oneTimeNoteRequest=visitorRequestId();const result=await chatRequest('note/open',{request_id:oneTimeNoteRequest,page:location.pathname});oneTimeNoteRequest=null;settings.noteEnabled=false;document.querySelector('#note-link')?.replaceChildren();syncNoteBox();return result.note;}
async function openKoreanSorryGift(){
 let dialog=document.querySelector('#korean-note-dialog');if(!dialog){dialog=document.createElement('dialog');dialog.id='korean-note-dialog';dialog.setAttribute('aria-label',"I'm really sorry · 정말 미안해");dialog.innerHTML='<button type="button" class="close-dialog" aria-label="Close note">×</button><div id="korean-note-content"></div>';dialog.querySelector('button').onclick=()=>dialog.close();dialog.addEventListener('close',()=>{document.querySelector('#korean-note-content').innerHTML='';document.querySelector('.korea-final a')?.focus({preventScroll:true});});document.body.append(dialog);}
 const root=document.querySelector('#korean-note-content');root.innerHTML='<p class="korean-note-loading">Opening your note… 잠시만 기다려 줘.</p>';if(!dialog.open)dialog.showModal();
 try{const note=await consumeOneTimeNote();root.innerHTML=notePresentation(note);syncKoreanGift();await updateSettings();}
 catch(error){root.innerHTML=`<div class="korean-note-error"><h2>${error.status===404?'This note is no longer available.':'The note is taking a moment.'}</h2><p>${esc(error.message)}</p>${error.status===404?'':'<button class="button light" id="retry-korean-note">Try opening again ↻</button>'}</div>`;root.querySelector('button')?.addEventListener('click',openKoreanSorryGift);if(error.status===404){settings.noteEnabled=false;syncKoreanGift();}}
}
async function renderDirectNote(){
 main.innerHTML='<div class="container direct-korean-note"><a href="/korea">← Your Korean world</a><div id="direct-note-content"><p>Opening your note…</p></div></div>';
 try{const note=await consumeOneTimeNote();document.querySelector('#direct-note-content').innerHTML=notePresentation(note,'h1');document.title="I'm really sorry · 정말 미안해";await updateSettings();}
 catch(error){if(error.status===404)notFound();else{document.querySelector('#direct-note-content').innerHTML='<p>The note could not open yet. Your retry can recover it.</p><button class="button light" id="retry-direct-note">Try opening again ↻</button>';document.querySelector('#retry-direct-note').onclick=renderDirectNote;}}
}
