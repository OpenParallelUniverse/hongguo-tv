'use strict';
const { JSDOM, VirtualConsole } = require(process.env.JSDOM_MODULE || 'jsdom');
(async () => {
  const errors = [];
  const vc = new VirtualConsole();
  vc.on('jsdomError', e => { if (!String(e).includes('Could not parse CSS stylesheet')) errors.push(String(e)); });
  const dom = await JSDOM.fromURL(process.argv[2], {
    resources: 'usable', runScripts: 'dangerously', pretendToBeVisual: true,
    virtualConsole: vc,
    beforeParse(w) {
      w.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {} });
      w.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
      w.HTMLElement.prototype.scrollIntoView = function() {};
    }
  });
  const w = dom.window, doc = w.document;
  try {
    const until = async pred => {
      for (let i = 0; i < 150; i++) { if (pred()) return; await new Promise(r => setTimeout(r, 100)); }
      throw new Error('Timed out: ' + doc.body.textContent.slice(-1800) + '\n' + errors.join('\n'));
    };
    await until(() => doc.getElementById('widget.cbid.hongguo.main.password'));
    console.log('Fields:', [...doc.querySelectorAll('.cbi-value-title')].map(n => n.textContent).join(', '));
    if (doc.querySelectorAll('.cbi-value-title').length !== 8) throw new Error('Expected 8 configuration fields');
    for (const [id, value] of [['password','test-password-123'], ['port','8877']]) {
      const el = doc.getElementById('widget.cbid.hongguo.main.' + id);
      el.value = value;
      el.dispatchEvent(new w.Event('input', { bubbles: true }));
      el.dispatchEvent(new w.Event('change', { bubbles: true }));
    }
    const view = await w.L.require('view.hongguo.settings');
    await view.handleSave();
    const password = doc.getElementById('widget.cbid.hongguo.main.password');
    password.value = 'short'; password.dispatchEvent(new w.Event('input', { bubbles: true }));
    let rejected = false;
    try { await view.handleSave(); } catch (e) { rejected = true; }
    if (!rejected) throw new Error('Weak password accepted by LuCI form');
    password.value = 'test-password-123'; password.dispatchEvent(new w.Event('input', { bubbles: true }));
    const maxMedia = doc.getElementById('widget.cbid.hongguo.main.max_media_mb');
    maxMedia.value = '100'; maxMedia.dispatchEvent(new w.Event('input', { bubbles: true }));
    rejected = false;
    try { await view.handleSave(); } catch (e) { rejected = true; }
    if (!rejected) throw new Error('Single-file limit larger than cache accepted');
    maxMedia.value = '32'; maxMedia.dispatchEvent(new w.Event('input', { bubbles: true }));
    await view.handleSave();
    [...doc.querySelectorAll('button')].find(n => n.textContent === '重启服务').click();
    await new Promise(r => setTimeout(r, 500));
    if (errors.length) throw new Error(errors.join('\n'));
    console.log('PASS: real LuCI JS form render/save/restart in DOM runtime (ubus mocked)');
  } finally { w.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
