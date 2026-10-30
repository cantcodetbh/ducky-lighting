import {chromium,webkit,expect} from '@playwright/test';import fs from 'node:fs/promises';
await fs.mkdir('evidence/native-effects/browser',{recursive:true});const results=[];
for(const [name,type] of [['chromium',chromium],['webkit',webkit]]){
 const browser=await type.launch(),page=await browser.newPage({viewport:{width:1440,height:900}});const errors=[];let effects=0,frames=0,saves=0;
 const status={ok:true,token:'mock-only',mode:'available',connected:true,name:'Mecha Mini',device_id:'123',firmware:'custom9003',detail:'Browser test',capabilities:{rgb:true,effects:false,onboard_profiles:true}};
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/**',r=>r.request().method()==='GET'?r.fulfill({json:{ok:true,profiles:[]}}):r.abort());
 await page.route('**/api/status',r=>r.fulfill({json:status}));
 await page.route('**/api/effect',r=>{effects++;const b=r.request().postDataJSON();expect(['Wave','Breathing','Reactive','Ripple']).toContain(b.effect);expect(b.speed).toBe(5);expect(b.device_id).toBe('123');expect(b.consent).toBe(true);expect(b.colour).toMatch(/^#[a-f0-9]{6}$/i);return r.fulfill({json:{ok:true,accepted_count:1}})});
 await page.route('**/api/lighting',r=>{frames++;return r.fulfill({json:{ok:true,accepted_count:64}})});
 await page.route('**/api/onboard/save',r=>{saves++;expect(r.request().postDataJSON().colours).toBeTruthy();return r.fulfill({json:{ok:true,accepted_count:71,onboard_saved:true}})});
 await page.goto('http://127.0.0.1:8770/');await page.locator('[data-effect="Ripple"]').click();await expect(page.locator('#apply-hardware')).toBeDisabled();await expect(page.locator('#effect-note')).toContainText('Preview only');await expect(page.locator('#save-onboard')).toHaveText('Save static frame');expect(effects+frames+saves).toBe(0);
 await page.screenshot({path:`evidence/native-effects/browser/${name}-9003-preview-only.png`,fullPage:true});
 status.firmware='custom9004';status.capabilities.effects=true;await page.waitForTimeout(5200);await expect(page.locator('#apply-hardware')).toBeEnabled();
 for(const effect of ['Wave','Breathing','Reactive','Ripple']){
  await page.locator(`[data-effect="${effect}"]`).click();await page.locator('#apply-hardware').click();await expect(page.locator('#toast')).toContainText(effect+' command acknowledged');
 }
 expect(effects).toBe(4);expect(frames).toBe(0);expect(saves).toBe(0);
 await page.locator('#save-onboard').click();await expect(page.locator('#onboard-status')).toContainText('static colours');expect(saves).toBe(1);expect(effects).toBe(4);
 for(const theme of ['light','dark']){
  if(await page.locator('html').getAttribute('data-theme')!==theme)await page.locator('#appearance').click();
  await page.screenshot({path:`evidence/native-effects/browser/${name}-9004-${theme}.png`,fullPage:true});
 }
 await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await expect(page.locator('#apply-hardware')).toBeInViewport();await page.screenshot({path:`evidence/native-effects/browser/${name}-9004-mobile.png`,fullPage:true});
 await page.locator('[data-effect="Static"]').click();await expect(page.locator('#apply-hardware')).toHaveText('Apply to keyboard');await page.locator('#apply-hardware').click();expect(frames).toBe(1);
 await page.reload();await page.waitForTimeout(300);expect(effects).toBe(4);expect(saves).toBe(1);expect(frames).toBe(1);expect(errors).toEqual([]);
 results.push({engine:name,old_firmware_effects_disabled:true,native_effect_commands:4,static_frame_commands:1,explicit_static_save:1,no_automatic_replay:true,console_errors:errors,actual_hardware_commands:0});await browser.close();
}
await fs.writeFile('evidence/native-effects/browser/results.json',JSON.stringify(results,null,2)+'\n');console.log('PASS Chromium/WebKit: native effects route, old firmware gate, static save, no replay. Mocked hardware only.');
