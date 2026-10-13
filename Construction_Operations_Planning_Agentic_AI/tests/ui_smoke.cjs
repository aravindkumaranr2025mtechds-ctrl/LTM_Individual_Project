/* Optional browser regression. Requires playwright; default application does not. */
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {spawn}=require('node:child_process');
const {chromium}=require(process.env.BUILDPLAN_PLAYWRIGHT || 'playwright');
const root=path.resolve(__dirname,'..');
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'buildplan-ui-'));
const port=8792;
(async()=>{
 const server=spawn(process.env.BUILDPLAN_PYTHON||'python',['run.py','--no-browser','--port',String(port)],{cwd:root,env:{...process.env,BUILDPLAN_DB:path.join(temp,'test.sqlite3')}});
 let serverLog='',browser;const errors=[];
 server.stdout.on('data',d=>serverLog+=d);server.stderr.on('data',d=>serverLog+=d);
 try{
  await new Promise((ok,no)=>{const timeout=setTimeout(()=>no(Error('Server startup timeout: '+serverLog)),5000);server.stdout.on('data',()=>{if(serverLog.includes('Open http')){clearTimeout(timeout);ok()}});server.on('exit',c=>no(Error('Server exit '+c+': '+serverLog)))});
  let args=['--no-sandbox'];
  if(process.env.BUILDPLAN_CHROMIUM_ARGS)args=JSON.parse(process.env.BUILDPLAN_CHROMIUM_ARGS);
  browser=await chromium.launch({headless:true,args,executablePath:process.env.BUILDPLAN_CHROMIUM||undefined});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  page.setDefaultTimeout(10000);
  page.on('pageerror',e=>errors.push(e.message));
  page.on('dialog',d=>d.accept());
  const nav=name=>page.locator('nav').getByRole('button',{name,exact:true}).click();
  async function generate(){const response=page.waitForResponse(r=>r.url().endsWith('/api/plan'));await page.getByRole('button',{name:'Generate plan',exact:true}).click();const res=await response;return {status:res.status(),data:await res.json()}}
  await page.goto(`http://127.0.0.1:${port}`);
  await page.getByRole('heading',{name:'Activity timeline',exact:true}).waitFor();
  assert.match(await page.locator('.metric').first().textContent(),/31/);
  let run=await generate();assert.equal(run.status,200);assert.equal(run.data.summary.duration,31);
  console.log('PASS: initial demo and saved planning run');
  await nav('Schedule');await page.getByLabel('Show dependency baseline').check();assert.equal(await page.locator('.gantt-baseline').count(),12);
  await nav('Activities');await page.getByRole('button',{name:'Edit Site setup & survey',exact:true}).click();
  await page.getByLabel('Duration (calendar days)',{exact:true}).fill('3');
  await page.getByRole('button',{name:'Save activity',exact:true}).click();
  run=await generate();assert.equal(run.status,200);assert.equal(run.data.summary.duration,32);
  console.log('PASS: activity edit recalculates schedule');
  await page.getByRole('button',{name:'Edit Site setup & survey',exact:true}).click();
  await page.getByRole('button',{name:'Delete activity',exact:true}).click();
  assert.match(await page.getByRole('dialog').textContent(),/Remove A01 from dependencies/);
  await page.getByRole('button',{name:'Cancel',exact:true}).click();
  await page.getByRole('button',{name:'Edit Site setup & survey',exact:true}).click();
  await page.getByLabel('A12 · Inspection & handover',{exact:true}).check();
  await page.getByRole('button',{name:'Save activity',exact:true}).click();
  run=await generate();assert.equal(run.status,422);await page.getByRole('alert').filter({hasText:'Circular dependencies'}).waitFor();
  await page.getByRole('button',{name:'Edit Site setup & survey',exact:true}).click();
  await page.getByLabel('A12 · Inspection & handover',{exact:true}).uncheck();await page.getByLabel('Duration (calendar days)',{exact:true}).fill('2');
  await page.getByRole('button',{name:'Save activity',exact:true}).click();run=await generate();assert.equal(run.data.summary.duration,31);
  console.log('PASS: protected delete, cycle validation and recovery');
  await nav('Resources');await page.getByRole('button',{name:'Edit Site crew',exact:true}).click();await page.getByLabel('Daily capacity',{exact:true}).fill('12');await page.getByRole('button',{name:'Save resource',exact:true}).click();run=await generate();assert.equal(run.status,200);assert.equal(run.data.project.resources[0].capacity,12);
  await nav('What-if studio');await page.getByLabel('Resource',{exact:true}).selectOption('crane');await page.getByLabel('Change in daily capacity',{exact:true}).fill('-1');
  let response=page.waitForResponse(r=>r.url().endsWith('/api/scenario'));await page.getByRole('button',{name:'Compare scenario',exact:true}).click();let scenario=await (await response).json();assert.equal(scenario.comparable,false);assert.equal(scenario.alternative.summary.feasible,false);await page.getByText('At least one plan is incomplete.',{exact:true}).waitFor();
  await page.getByLabel('Resource',{exact:true}).selectOption('crew');await page.getByLabel('Change in daily capacity',{exact:true}).fill('2');
  response=page.waitForResponse(r=>r.url().endsWith('/api/scenario'));await page.getByRole('button',{name:'Compare scenario',exact:true}).click();scenario=await (await response).json();assert.equal(scenario.comparable,true);
  await page.getByRole('button',{name:'Apply as draft',exact:true}).click();await page.getByText('Inputs have changed. Generate a plan to see results for the current draft.',{exact:true}).waitFor();run=await generate();assert.equal(run.data.project.resources[0].capacity,14);
  console.log('PASS: resource editing, infeasible comparison and scenario application');
  await nav('Reports & agents');
  let dl=page.waitForEvent('download');await page.getByRole('button',{name:'Schedule CSV',exact:true}).click();const csv=await dl;await csv.saveAs(path.join(temp,'schedule.csv'));assert.match(fs.readFileSync(path.join(temp,'schedule.csv'),'utf8'),/A12/);
  dl=page.waitForEvent('download');await page.getByRole('button',{name:'Project JSON',exact:true}).click();const download=await dl;await download.saveAs(path.join(temp,'project.json'));assert.equal(JSON.parse(fs.readFileSync(path.join(temp,'project.json'),'utf8')).resources[0].capacity,14);
  await page.pdf({path:path.join(temp,'report.pdf'),format:'A4',printBackground:true});assert.ok(fs.statSync(path.join(temp,'report.pdf')).size>10000);
  await page.reload();await page.getByRole('heading',{name:'Activity timeline',exact:true}).waitFor();await nav('Resources');assert.match(await page.locator('.resource-card').first().textContent(),/14/);
  console.log('PASS: CSV/JSON exports, print rendering and persisted reload');
  await page.getByRole('button',{name:'Projects',exact:true}).click();await page.locator('input[type=file]').setInputFiles(path.join(temp,'project.json'));await page.getByRole('heading',{name:'Activity timeline',exact:true}).waitFor();assert.match(await page.locator('.workspace').textContent(),/New project draft/);
  await generate();await nav('Reports & agents');await page.getByRole('button',{name:'Restore inputs',exact:true}).first().click();await page.getByText('Historical inputs restored as a new draft. Generate plan to save.',{exact:true}).waitFor();await generate();
  console.log('PASS: import and historical inputs restored as new draft');
  await page.getByRole('button',{name:'Projects',exact:true}).click();await page.getByRole('button',{name:'New project',exact:true}).click();await page.getByLabel('Project name',{exact:true}).fill('UI-created project');await page.getByRole('button',{name:'Apply settings',exact:true}).click();
  await nav('Resources');await page.getByRole('button',{name:'Add resource',exact:true}).click();await page.getByLabel('Resource name',{exact:true}).fill('Demo crew');await page.getByLabel('Daily capacity',{exact:true}).fill('4');await page.getByRole('button',{name:'Save resource',exact:true}).click();
  await nav('Activities');await page.getByRole('button',{name:'Add activity',exact:true}).click();await page.getByLabel('Activity name',{exact:true}).fill('Survey');await page.getByLabel('Demo crew (workers)',{exact:true}).fill('2');await page.getByRole('button',{name:'Save activity',exact:true}).click();run=await generate();assert.equal(run.status,200);assert.equal(run.data.summary.scheduled,1);
  await page.getByRole('button',{name:'Edit Survey',exact:true}).click();await page.getByRole('button',{name:'Delete activity',exact:true}).click();assert.equal(await page.locator('tbody tr').count(),0);
  console.log('PASS: empty project creation, resource/task addition and task deletion');
  await page.getByRole('button',{name:'Projects',exact:true}).click();await page.getByRole('button',{name:'Load demo',exact:true}).click();await page.getByRole('heading',{name:'Activity timeline',exact:true}).waitFor();
  await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.body.scrollWidth>innerWidth),false);
  for(const name of ['Schedule','Activities','Resources','What-if studio','Reports & agents','Overview']){await nav(name);assert.equal(await page.evaluate(()=>document.body.scrollWidth>innerWidth),false,`mobile overflow on ${name}`)}
  if(process.env.BUILDPLAN_SCREENSHOTS){await page.screenshot({path:path.join(process.env.BUILDPLAN_SCREENSHOTS,'mobile.png'),fullPage:true});await page.setViewportSize({width:1440,height:1050});await page.screenshot({path:path.join(process.env.BUILDPLAN_SCREENSHOTS,'dashboard.png'),fullPage:true})}
  assert.deepEqual(errors,[]);
  console.log('PASS: six mobile views, desktop rendering and no JavaScript runtime errors');
  console.log('ALL BROWSER WORKFLOWS PASS');
 }finally{if(browser)await browser.close();server.kill();fs.rmSync(temp,{recursive:true,force:true})}
})().catch(e=>{console.error(e);process.exitCode=1});
