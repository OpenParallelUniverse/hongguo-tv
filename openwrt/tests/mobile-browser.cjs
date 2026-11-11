/* Real Chromium layout test: actual authenticated LAN server, synthetic APIs/media. */
'use strict';
const { chromium, request } = require('playwright');
const { spawn, execFileSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'hongguo-mobile-'));
const shots = process.env.MOBILE_SCREENSHOTS || path.join(temp, 'screenshots');
fs.mkdirSync(shots, { recursive: true });
const password = path.join(temp, 'password'); fs.writeFileSync(password, 'test-password-123', { mode: 0o600 });
const port = 18989, base = 'http://127.0.0.1:' + port;
const log = fs.openSync(path.join(temp, 'server.log'), 'w');
const server = spawn(path.join(root, 'openwrt/files/usr/bin/hongguo-server'),
  ['--lan', '--listen', '127.0.0.1', '--port', String(port), '--password-file', password, '--data-dir', path.join(temp, 'data')],
  { env: { ...process.env, MINIREEL_CACHE_DIR: path.join(temp, 'cache') }, stdio: ['ignore', log, log] });
const poster = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="200" height="300"><rect width="200" height="300" fill="#34374c"/><circle cx="100" cy="130" r="45" fill="#f35d7b"/></svg>');
const dramas = Array.from({ length: 12 }, (_, i) => ({ series_id: String(1000+i), title: '手机布局测试短剧 ' + (i+1),
  vid: String(2000+i), vid_list: [String(2000+i), String(3000+i)], episode_count: 12, score: '8.8', intro: '用于验证手机、平板与桌面的列表、选集及播放布局。',
  cover: poster, tags: ['都市', '测试'], episodes: Array.from({ length: 12 }, (_, n) => ({ index: n+1, video_id: String(2000+i+n), locked: false })) }));
const media = Buffer.from(fs.readFileSync(path.join(__dirname, 'mobile-video.base64'), 'utf8').trim(), 'base64');
let browser;
(async () => {
  const api = await request.newContext({ httpCredentials: { username: 'hongguo', password: 'test-password-123' } });
  let ready = false;
  for (let n=0; n<50; n++) { try { ready = (await api.get(base+'/api/v1/health')).ok(); if (ready) break; } catch {} await new Promise(r => setTimeout(r, 100)); }
  assert(ready, 'LAN server starts');
  const coreVersion=(await (await api.get(base+'/api/v1/status')).json()).version;
  await api.dispose();
  browser = await chromium.launch({ headless: true });
  for (const size of [{width:320,height:740},{width:390,height:844},{width:768,height:1024},{width:844,height:390},{width:932,height:430},{width:1280,height:800}]) {
    const mobile = size.width <= 960;
    const context = await browser.newContext({ viewport: size, hasTouch: mobile, isMobile: mobile, reducedMotion: 'reduce',
      httpCredentials: { username: 'hongguo', password: 'test-password-123' } });
    const page = await context.newPage(); const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/minireel-proxy/media/**', route => route.fulfill({ contentType: 'video/webm', body: media }));
    await page.route('**/api/v1/**', async route => {
      const url = new URL(route.request().url()), p=url.pathname;
      if (['/api/v1/health','/api/v1/status'].includes(p)) return route.continue();
      let data = { items: [], entries: [] };
      if (p === '/api/v1/account') data = { logged_in: false, sync: { state: 'idle' } };
      else if (p === '/api/v1/library') data = { entries: [], history: [], favorites: [], likes: [] };
      else if (p === '/api/v1/series/detail') data = dramas.find(d => d.series_id===url.searchParams.get('series_id')) || dramas[0];
      else if (p === '/api/v1/play/info') data = {path:'/minireel-proxy/media/012345678901234567890123.mp4',quality:'1080P',qualities:['1080P'],video_width:360,video_height:640,video_codec:'vp8',vid:url.searchParams.get('vid'),mode:'full'};
      else if (p === '/api/v1/category' || p === '/api/v1/search' || p.startsWith('/api/v1/lists/') || p === '/api/v1/rank') data = {items:dramas,filters:[{type:'genre',label:'分类',options:[{id:'',label:'全部'}]}],ranks:[],has_more:false,next_offset:0};
      return route.fulfill({contentType:'application/json',body:JSON.stringify({ok:true,data})});
    });
    async function bounded(selector) {
      const bounds = await page.locator(selector).evaluate(e => {
        const r=e.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:innerWidth,height:innerHeight};
      });
      assert(bounds.left >= -1 && bounds.right <= bounds.width+1, selector+' fits horizontally '+JSON.stringify(bounds));
      assert(bounds.top >= -1 && bounds.bottom <= bounds.height+1, selector+' fits vertically '+JSON.stringify(bounds));
    }
    async function navigate(name) {
      if (mobile) await page.locator('.ow-mobile-menu').click();
      await page.locator('.sidebar [data-page="'+name+'"]').click();
      if (mobile) assert.equal(await page.locator('.ow-mobile-menu').getAttribute('aria-expanded'),'false');
    }
    try {
      await page.goto(base, {waitUntil:'networkidle'});
      await page.locator('html.openwrt-web').waitFor();
      assert.equal(await page.locator('.ow-mobile-header').isVisible(),mobile);
      await bounded('.app-shell');
      if (size.width===768) await page.locator('.app-shell').evaluate(e=>e.classList.add('sidebar-icons'));
      if (mobile) {
        assert.equal(await page.locator('.sidebar').evaluate(e=>e.inert),true);
        await page.locator('.ow-mobile-menu').click(); await bounded('.sidebar');
        await page.keyboard.press('Escape');
        assert.equal(await page.locator('.ow-mobile-menu').getAttribute('aria-expanded'),'false');
        // Header search is a real shortcut to the upstream search route.
        await page.locator('.ow-mobile-search').click();
      } else await navigate('search');
      await page.locator('#search-page:not(.is-hidden)').waitFor();
      await page.locator('.search-result-card').first().waitFor();
      await bounded('#search-page');
      const grid = await page.locator('.search-results').evaluate(e=>getComputedStyle(e).gridTemplateColumns.split(' ').length);
      if (mobile) assert.equal(grid,size.width<=480?2:3);
      await page.screenshot({path:path.join(shots,size.width+'-search.png')});
      if(size.width===390) {
        await page.locator('#search-input').fill('测试');
        await page.setViewportSize({width:390,height:500}); await bounded('#search-input');
        await page.setViewportSize(size);
      }
      await page.locator('.search-result-card').first().click();
      await page.locator('#hero:not(.is-hidden)').waitFor();
      await page.waitForFunction(()=>document.getElementById('hero-video').readyState>=2);
      await page.locator('[data-action="episodes"]').click();
      await page.locator('#detail-modal:not(.is-hidden)').waitFor();
      await bounded('.detail-dialog');
      if (mobile) assert.equal(await page.locator('.detail-episodes').evaluate(e=>getComputedStyle(e).display),'grid');
      await page.screenshot({path:path.join(shots,size.width+'-detail.png')});
      await page.locator('.detail-close').click();
      await navigate('account');
      await page.locator('#account-page:not(.is-hidden)').waitFor();
      await bounded('#account-page');
      for(const card of await page.locator('.account-card').all()) {const r=await card.boundingBox(); if(r) assert(r.x>=-1 && r.x+r.width<=size.width+1,'Account card fits horizontally');}
      await page.screenshot({path:path.join(shots,size.width+'-account.png')});
      await navigate('settings');
      await page.locator('#settings-page:not(.is-hidden)').waitFor();
      await bounded('#settings-page');
      await navigate('recommend');
      await page.locator('#hero:not(.is-hidden)').waitFor();
      await bounded('.hero'); await bounded('.bottom-controls');
      assert.equal(await page.locator('#hero-video').getAttribute('playsinline'),'');
      await page.screenshot({path:path.join(shots,size.width+'-player.png')});
      if (mobile && size.width===390) {
        await page.setViewportSize({width:844,height:390}); await bounded('.app-shell');
        await page.setViewportSize({width:390,height:844});
        await page.locator('.ow-mobile-menu').click();
        await page.setViewportSize({width:1280,height:800});
        assert.equal(await page.locator('.sidebar').evaluate(e=>e.inert),false);
        assert.equal(await page.locator('#main-surface').evaluate(e=>e.inert),false);
      }
      assert.deepEqual(errors,[], 'No frontend runtime errors');
      console.log('PASS mobile layout',size.width+'x'+size.height);
    } catch (error) {
      await page.screenshot({path:path.join(shots,size.width+'-failure.png')});
      console.error('Video state:',await page.locator('#hero-video').evaluate(v=>({src:v.currentSrc,ready:v.readyState,network:v.networkState,error:v.error&&{code:v.error.code,message:v.error.message}})));
      console.error('DOM snapshot:',(await page.locator('body').innerText()).slice(0,1800));
      throw error;
    } finally {await context.close();}
  }
  if (process.env.MOBILE_VALIDATION_REPORT) fs.writeFileSync(process.env.MOBILE_VALIDATION_REPORT,JSON.stringify({commit:execFileSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).trim(),core_version:coreVersion,viewports:[320,390,768,844,932,1280],passed:true},null,2)+'\n');
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{
  if (browser) await browser.close(); server.kill('SIGTERM');fs.closeSync(log);
});
