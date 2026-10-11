/* Fireworks: tap-the-screen confetti finale for Shivani's birthday (Oct 12). */
const fireworks={active:false,canvas:null,ctx:null,particles:[],running:false};
function fireworksColors(){return ['#ff705d','#ffd45b','#74d8c2','#69aaf5','#f69ac4','#a58af0','#cfa7f6','#fff'];}
function startFireworks(){
 if(fireworks.running)return;
 const canvas=document.createElement('canvas');canvas.id='fireworks-canvas';
 canvas.style.cssText='position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:9999';
 document.body.appendChild(canvas);fireworks.canvas=canvas;fireworks.ctx=canvas.getContext('2d');
 const fit=()=>{canvas.width=innerWidth;canvas.height=innerHeight;};fit();addEventListener('resize',fit);
 fireworks.running=true;
 const colors=fireworksColors();
 function burst(x,y){
  for(let i=0;i<36;i++){const a=(Math.PI*2*i)/36,s=2+Math.random()*4;
   fireworks.particles.push({x,y,vx:Math.cos(a)*s,vy:Math.sin(a)*s-1,life:1,color:colors[i%colors.length],size:2+Math.random()*3});}
 }
 let auto=0;
 function frame(){
  const ctx=fireworks.ctx;if(!ctx)return;
  ctx.clearRect(0,0,fireworks.canvas.width,fireworks.canvas.height);
  if(Date.now()-auto>900){auto=Date.now();burst(fireworks.canvas.width*(0.15+Math.random()*0.7),fireworks.canvas.height*(0.15+Math.random()*0.5));}
  fireworks.particles=fireworks.particles.filter(p=>p.life>0);
  for(const p of fireworks.particles){p.x+=p.vx;p.y+=p.vy;p.vy+=0.05;p.life-=0.012;
   ctx.globalAlpha=Math.max(p.life,0);ctx.fillStyle=p.color;ctx.beginPath();ctx.arc(p.x,p.y,p.size*p.life,0,Math.PI*2);ctx.fill();}
  ctx.globalAlpha=1;
  if(fireworks.running)requestAnimationFrame(frame);
 }
 frame();
 const onTap=e=>burst(e.clientX,e.clientY);
 addEventListener('pointerdown',onTap);
 fireworks.stop=()=>{fireworks.running=false;removeEventListener('pointerdown',onTap);canvas.remove();};
}
/* --------------------------------------------------- countdown to Oct 12 */
const countdown={timer:null,el:null};
function startCountdown(){
 const ctx=personalBirthdayContext();
 const target=new Date(ctx.eventDate+'T00:00:00+05:30').getTime();
 countdown.el=document.createElement('div');countdown.el.id='birthday-countdown';
 countdown.el.innerHTML='<div class="cd-kicker">✦ counting every second until your day ✦</div><div class="cd-clock" id="cd-clock">--</div><div class="cd-sub" id="cd-sub"></div>';
 document.body.appendChild(countdown.el);
 const tick=()=>{
  if(!document.getElementById('birthday-countdown'))return clearInterval(countdown.timer);
  let diff=target-Date.now();
  const sub=document.getElementById('cd-sub');
  if(diff<=0){document.getElementById('cd-clock').textContent='생일 축하해 ♩ It\'s your day!';if(sub)sub.textContent='12 October · happy birthday Shivani 💜';return clearInterval(countdown.timer);}
  const d=Math.floor(diff/864e5),h=Math.floor(diff%864e5/36e5),m=Math.floor(diff%36e5/6e4),s=Math.floor(diff%6e4/1e3);
  document.getElementById('cd-clock').textContent=`${d}d ${String(h).padStart(2,'0')}h ${String(m).padStart(2,'0')}m ${String(s).padStart(2,'0')}s`;
  if(sub)sub.textContent=`until ${ctx.eventDate} · ${ctx.timezoneLabel}`;
 };
 tick();countdown.timer=setInterval(tick,1000);
}
/* --------------------------------------------------- love-letter generator */
const loveLines=[
 {h:'dear shivani',b:['Tum jaise ho, waise hi perfect ho. No edits needed.','Aaj ka din tumhare naam ka ho, baaki sab baad me.','Duniya thodi chaotic hai, but tumhari smile sab set kar deti hai.','Whatever you decide in life, make sure it makes you happy first.']},
 {h:'hey you ♡',b:['Just a reminder: you have survived 100% of your bad days. Respect.','Your energy is rare. Don\'t let anyone dim it.','Today the universe is legally required to be nice to you.','Eat cake. Open gifts. Ignore responsibilities. Birthday rules.']},
 {h:'to the birthday girl',b:['Another year more awesome than the last one.','May your year have more good surprises than bad Mondays.','You deserve every good thing coming your way. And then some.','Keep being unapologetically you. It suits you.']}
];
function setupLoveLetter(){
 const btn=document.getElementById('letter-lucky-btn');
 if(!btn||btn.dataset.bound)return;btn.dataset.bound='1';
 const render=()=>{
  const pick=loveLines[Math.floor(Math.random()*loveLines.length)];
  const body=pick.b.slice().sort(()=>Math.random()-.5).slice(0,3);
  const card=document.getElementById('letter-lucky-card');
  if(card){card.querySelector('.ll-h').textContent=pick.h;const ul=card.querySelector('ul');ul.innerHTML=body.map(l=>'<li>'+l+'</li>').join('');card.hidden=false;}
 };
 btn.addEventListener('click',render);render();
}
