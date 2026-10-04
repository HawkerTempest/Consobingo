const {chromium}=require('playwright');
const path=require('node:path');
const {spawn,execFileSync}=require('node:child_process');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const ROOT=path.resolve(__dirname,'..');
const PYTHON=process.env.CONSO_PYTHON||'python';
const fixture=JSON.parse(execFileSync(PYTHON,['-c',`import json
from consobingo import engine as E,content as C
g=E.new_game(2026)
for section in C.SECTION_LABELS:E.apply_solution(g,section)
print(json.dumps({'answers':g['answers'],'catalog':C.catalog()}))`],{cwd:ROOT,encoding:'utf8'}));
const out=path.join(ROOT,'qa-output');fs.mkdirSync(out,{recursive:true});
const server=spawn(PYTHON,['-m','streamlit','run','app.py','--server.port','8501','--server.address','127.0.0.1'],{cwd:ROOT,env:{...process.env,CONSOBINGO_DEMO:'true'},stdio:['ignore','pipe','pipe']});
let log='';server.stdout.on('data',x=>log+=x);server.stderr.on('data',x=>log+=x);
(async()=>{
 let b;
 try{
  for(let i=0;i<80;i++){try{if((await fetch('http://127.0.0.1:8501/_stcore/health')).ok)break;}catch{}await new Promise(r=>setTimeout(r,250));}
  b=await chromium.launch({headless:true,...(process.env.CONSO_BROWSER_EXECUTABLE?{executablePath:process.env.CONSO_BROWSER_EXECUTABLE}:{}),args:JSON.parse(process.env.CONSO_BROWSER_ARGS||'[]')});
  const p=await b.newPage({viewport:{width:1365,height:1000}});const errors=[];p.on('pageerror',e=>errors.push(e.message));
  await p.goto('http://127.0.0.1:8501');
  await p.waitForSelector('iframe',{timeout:30000});
  console.log(await p.locator('iframe').evaluateAll(es=>es.map(e=>({title:e.title,src:e.src}))));
  const iframe=p.frameLocator('iframe').first();
  await iframe.locator('[data-go="story"]').last().waitFor({timeout:20000});
  await p.screenshot({path:out+'/desktop-home.png',fullPage:true});
  await iframe.locator('[data-go="story"]').last().click();
  await iframe.locator('[data-clue]').first().waitFor();
  console.log('story clues',await iframe.locator('[data-clue]').count());
  await iframe.locator('[data-act="check"][data-section="ekb"]').click();
  await iframe.locator('[data-live-feedback="ekb"]').waitFor({timeout:15000});
  console.log('Python feedback received');
  await p.screenshot({path:out+'/desktop-story.png',fullPage:true});
  const A=fixture.answers;
  const check=async section=>{
   await iframe.locator(`[data-act="check"][data-section="${section}"]`).click();
   await iframe.locator(`[data-live-feedback="${section}"].cb-success`).waitFor({timeout:15000});
  };
  const go=async screen=>{await iframe.locator(`.cb-nav [data-go="${screen}"]`).click();};
  for(const [id,value] of Object.entries(A.ekb)){
   await iframe.locator(`[data-clue="${id}"]`).click();
   await iframe.locator(`[data-classify="${id},${value}"]`).click();
  }
  await check('ekb');
  await iframe.locator('.cb-tabs [data-mode="factors"]').click();
  for(const [id,value] of Object.entries({...A.factors,d1:0})){
   await iframe.locator(`[data-clue="${id}"]`).click();
   await iframe.locator(`[data-classify="${id},${value}"]`).click();
  }
  for(let i=0;i<2;i++)for(const f of ['clue','effect'])await iframe.locator(`[data-effect="${i},${f}"]`).selectOption(A.influence_links[i][f]);
  await check('factors');
  await go('attitude');
  for(let i=0;i<5;i++){
   const wanted=fixture.catalog.attitude[i].text;
   let current=(await iframe.locator('.cb-strip p').allTextContents()).indexOf(wanted);
   assert.ok(current>=i);
   while(current>i){await iframe.locator(`[data-move="${current},-1"]`).click();current--;}
  }
  await check('attitude');
  assert.equal(await iframe.locator('.cb-exposure').count(),1);
  await p.screenshot({path:out+'/desktop-attitude.png',fullPage:true});
  await go('table');
  for(const c of A.criteria)await iframe.locator(`[data-criterion="${c}"]`).click();
  await iframe.locator('[data-criterion="area"]').click();
  await iframe.locator('.cb-error').waitFor();
  for(const [c,e] of Object.entries(A.criteria_evidence))await iframe.locator(`[data-evidence="${c}"]`).selectOption(e);
  for(const [c,value] of Object.entries(A.table))await iframe.locator(`[data-cell="${c}"]`).fill(value);
  await check('table');
  await p.screenshot({path:out+'/desktop-table.png',fullPage:true});
  await go('rules');
  for(const [rid,rule] of Object.entries(A.rules)){
   await iframe.locator(`.cb-tabs [data-rule="${rid}"]`).click();
   for(const offer of rule.keep)await iframe.locator(`[data-offer="${rid},${offer},keep"]`).click();
   await check('selection_'+rid);
   await iframe.locator(`[data-model="${rid},${rule.model}"]`).click();
   for(const offer of rule.counter_keep)await iframe.locator(`[data-offer="${rid},${offer},counter_keep"]`).click();
   await check('rule_'+rid);
  }
  await go('numbers');
  assert.equal(await iframe.locator('[data-calc]').inputValue(),'');
  assert.equal(await iframe.locator('[data-calc]').getAttribute('placeholder'),'Saisis ton calcul');
  await iframe.locator('.cb-calculator summary').click();
  await iframe.locator('[data-calc]').fill('(30-12)/60*100');
  await iframe.locator('[data-act="calculate"]').click();
  await iframe.locator('[data-calc-result]').filter({hasText:'30'}).waitFor({timeout:15000});
  assert.equal(await iframe.locator('.cb-calculator').getAttribute('open'),'');
  for(const [mid,metric] of Object.entries(A.metrics)){
   await iframe.locator(`[data-metric="${mid}"]`).click();
   for(const [k,v] of Object.entries(metric.groups))await iframe.locator(`[data-survey="${k}"]`).selectOption(v);
   for(const [k,v] of Object.entries(metric.data))await iframe.locator(`[data-metric-field="${k}"]`).fill(v);
   await iframe.locator('[data-metric-result]').fill(metric.result);
   await check('metric_'+mid);
  }
  await go('bonus');
  for(let i=0;i<2;i++){
   await iframe.locator(`[data-slot="${i},clue"]`).click();
   for(const f of ['clue','objective','action'])await iframe.locator(`[data-bonus-choice="${i},${f},${A.bonus[i][f]}"]`).click();
  }
  await check('bonus');
  await p.screenshot({path:out+'/desktop-bonus.png',fullPage:true});
  await go('end');await iframe.locator('[data-act="finish"]').click();
  await iframe.locator('[data-act="finish"]').filter({hasText:'Actualiser'}).waitFor();
  const downloadPromise=p.waitForEvent('download');
  await p.getByRole('button',{name:'Télécharger mon bilan personnel (PDF)'}).click();
  await (await downloadPromise).saveAs(out+'/bilan-ui.pdf');
  await p.screenshot({path:out+'/desktop-bilan.png',fullPage:true});
  await go('story');
  assert.equal(await iframe.locator('.cb-marked').count(),7);
  for(const width of [390,320]){
   await p.setViewportSize({width,height:844});
   for(const screen of ['story','attitude','table','numbers','bonus','end']){
    await go(screen);
    const bounds=await iframe.locator('body').evaluate(el=>({scroll:el.scrollWidth,width:el.clientWidth}));
    assert.ok(bounds.scroll<=bounds.width+1,JSON.stringify({screen,width,...bounds}));
   }
   await go('attitude');await p.screenshot({path:out+`/mobile-${width}.png`,fullPage:true});
  }
  await go('end');await iframe.locator('[data-act="restart"]').click();
  await iframe.locator('[data-act="restart"]').click();
  await iframe.locator('h1').waitFor();
  await go('story');assert.equal(await iframe.locator('.cb-marked').count(),0);
  console.log('Full UI passed: 12 activities, calculator, PDF download, continued practice, mobile layouts, new run.');
  assert.equal(errors.length,0,errors.join('\n'));
  console.log('Streamlit component smoke passed');
 }finally{if(b)await b.close();server.kill();fs.writeFileSync(out+'/streamlit.log',log);}
})().catch(e=>{console.error(e);process.exitCode=1;});
