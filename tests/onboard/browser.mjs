import {chromium,webkit,expect} from '@playwright/test';import fs from 'node:fs/promises';
await fs.mkdir('evidence/onboard-toolbar',{recursive:true});const results=[];
for(const [name,type] of [['chromium',chromium],['webkit',webkit]]){
 const browser=await type.launch(),context=await browser.newContext({viewport:{width:1440,height:900}}),page=await context.newPage();let saves=0,clears=0,fail=false;const errors=[];
 const status={ok:true,token:'fixture-only',mode:'available',connected:true,name:'Ducky Mecha Mini',device_id:'123',firmware:'custom9002',detail:'RAM-only browser fixture',capabilities:{rgb:true,effects:false,onboard_profiles:false}};
 page.on('pageerror',e=>errors.push(e.message));await page.route('**/api/status',r=>r.fulfill({json:status}));await page.route('**/api/profiles',r=>r.fulfill({json:{ok:true,profiles:[]}}));
 await page.route('**/api/onboard/save',r=>{saves++;const body=r.request().postDataJSON();expect(body.consent).toBe(true);expect(body.device_id).toBe('123');expect(Object.keys(body.colours)).toHaveLength(61);return r.fulfill({status:fail?409:200,json:fail?{ok:false,error:'Onboard operation not confirmed; no automatic retry.'}:{ok:true,accepted_count:71,onboard_saved:true}})});
 await page.route('**/api/onboard/clear',r=>{clears++;expect(r.request().postDataJSON()).toEqual({device_id:'123',consent:true});return r.fulfill({json:{ok:true,onboard_saved:false}})});
 await page.route('**/api/lighting',r=>r.abort());await page.route('**/api/release',r=>r.abort());
 await page.goto('http://127.0.0.1:8770/');await expect(page.locator('#save-onboard')).toBeDisabled();await expect(page.locator('#clear-onboard')).toBeDisabled();await expect(page.locator('#onboard-hint')).toContainText('unavailable with this firmware');expect(saves).toBe(0);expect(clears).toBe(0);
 status.firmware='custom9003';status.capabilities.onboard_profiles=true;await page.waitForTimeout(5200);await expect(page.locator('#save-onboard')).toBeEnabled();await page.locator('#save-onboard').click();await expect(page.locator('#onboard-status')).toContainText('Saved on the keyboard');expect(saves).toBe(1);await page.screenshot({path:`evidence/onboard-toolbar/${name}-saved-light.png`,fullPage:true});
 await page.locator('#swatches button').first().click();await expect(page.locator('#onboard-status')).toContainText('Preview changed');
 await page.locator('#profiles-toggle').click();await page.locator('#clear-onboard').click();expect(clears).toBe(0);await expect(page.locator('#clear-onboard')).toHaveText('Confirm removal');await page.locator('#clear-onboard').click();await expect(page.locator('#onboard-status')).toContainText('removed');expect(clears).toBe(1);
 await page.locator('#profiles-toggle').click();fail=true;await page.locator('#save-onboard').click();await expect(page.locator('#onboard-status')).toContainText('not confirmed');await page.waitForTimeout(300);expect(saves).toBe(2);await expect(page.locator('#save-onboard')).toBeEnabled();
 await page.locator('#appearance').click();await page.screenshot({path:`evidence/onboard-toolbar/${name}-error-dark.png`,fullPage:true});
 await page.reload();await page.waitForTimeout(300);expect(saves).toBe(2);expect(clears).toBe(1);await expect(page.locator('#onboard-status')).toHaveText('');await page.setViewportSize({width:390,height:844});await page.screenshot({path:`evidence/onboard-toolbar/${name}-mobile.png`,fullPage:true});expect(errors).toEqual([]);
 for(const width of [1920,1440,1280,390]){
  await page.setViewportSize({width,height:width===390?844:900});
  for(const theme of ['light','dark']){
   if(await page.locator('html').getAttribute('data-theme')!==theme)await page.locator('#appearance').click();
   await expect(page.locator('#save-onboard')).toBeInViewport();await expect(page.locator('#apply-hardware')).toBeInViewport();
   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
   const apply=await page.locator('#apply-hardware').boundingBox(),save=await page.locator('#save-onboard').boundingBox();expect(apply.x+apply.width).toBeLessThanOrEqual(save.x);
   await page.screenshot({path:`evidence/onboard-toolbar/${name}-${width}-${theme}.png`,fullPage:true});
  }
 }

 results.push({engine:name,save_visible_without_profiles:true,dirty_feedback:true,responsive_widths:[1920,1440,1280,390],old_firmware_disabled:true,explicit_save:true,clear_confirmation:true,error_does_not_claim_success:true,no_retry_or_reload_replay:true,console_errors:errors,actual_hardware_writes:0});await browser.close();
}
await fs.writeFile('evidence/onboard-toolbar/browser-results.json',JSON.stringify(results,null,2)+'\n');console.log('PASS: onboard controls in Chromium/WebKit; old firmware gated, explicit saves/clear, errors and no replay. All hardware API calls intercepted.');
