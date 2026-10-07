/* A single display-name setting, applied safely without rebuilding active chats. */
let activeBirthdayRecipient={name:'Shivani',koreanName:'시바니'};
const recipientTemplates=new WeakMap();
let recipientObserver=null;
function birthdayRecipient(){return activeBirthdayRecipient;}
function birthdayText(value){const recipient=birthdayRecipient();return String(value).replace(/SHIVANI|Shivani|시바니|\bSVN\b/g,match=>match==='시바니'?recipient.koreanName:match==='SHIVANI'?recipient.name.toUpperCase():match==='SVN'?'BDAY':recipient.name);}
function birthdayMarkup(value){const recipient=birthdayRecipient();return String(value).replace(/SHIVANI|Shivani|시바니/g,match=>esc(match==='시바니'?recipient.koreanName:match==='SHIVANI'?recipient.name.toUpperCase():recipient.name));}
function birthdayFileName(){return birthdayRecipient().name.toLowerCase().normalize('NFKD').replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'')||'birthday';}
function recipientStorageKey(suffix){const r=birthdayRecipient();return r.name.toLowerCase()==='shivani'&&r.koreanName==='시바니'?'shivani-'+suffix:'recipient-'+tinyHash(r.name+'|'+r.koreanName)+'-'+suffix;}
function recipientNodeAllowed(node){const element=node.nodeType===Node.ELEMENT_NODE?node:node.parentElement;return element&&!element.closest('script,style,textarea,input,.chat-message,.memory,.viewer-title,.future-message,.one-time-note-content p,.one-time-note-content .korean-note-signoff');}
function applyRecipientText(node){
 if(!recipientNodeAllowed(node))return;
 let record=recipientTemplates.get(node);
 if(!record||node.nodeValue!==record.rendered){if(!/SHIVANI|Shivani|시바니|\bSVN\b/.test(node.nodeValue||''))return;record={source:node.nodeValue,rendered:node.nodeValue};recipientTemplates.set(node,record);}
 const next=birthdayText(record.source);record.rendered=next;if(node.nodeValue!==next)node.nodeValue=next;
}
function applyBirthdayRecipient(root=document.body){
 if(!root)return;
 if(root.nodeType===Node.TEXT_NODE){applyRecipientText(root);return;}
 const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);while(walker.nextNode())applyRecipientText(walker.currentNode);
 const title=document.querySelector('title');if(root===document.body&&title){const titleWalker=document.createTreeWalker(title,NodeFilter.SHOW_TEXT);while(titleWalker.nextNode())applyRecipientText(titleWalker.currentNode);}
}
function setBirthdayRecipient(value){
 const before=activeBirthdayRecipient.name+'|'+activeBirthdayRecipient.koreanName;
 if(value&&typeof value.name==='string'&&typeof value.koreanName==='string')activeBirthdayRecipient={name:value.name,koreanName:value.koreanName};
 applyBirthdayRecipient();
 if(before!==activeBirthdayRecipient.name+'|'+activeBirthdayRecipient.koreanName&&typeof setupBirthdayScratch==='function')setupBirthdayScratch();
}
function startRecipientPersonalization(){
 if(recipientObserver||!document.body)return;
 recipientObserver=new MutationObserver(records=>{for(const record of records){if(record.type==='characterData')applyRecipientText(record.target);else record.addedNodes.forEach(node=>{if(node.nodeType===Node.TEXT_NODE||node.nodeType===Node.ELEMENT_NODE)applyBirthdayRecipient(node);});}});
 recipientObserver.observe(document.documentElement,{subtree:true,childList:true,characterData:true});applyBirthdayRecipient();
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',startRecipientPersonalization,{once:true});else startRecipientPersonalization();
