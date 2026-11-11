'use strict';
'require view';
'require form';
'require uci';
'require rpc';
'require fs';
'require ui';
'require poll';

var serviceList = rpc.declare({
	object: 'service', method: 'list', params: ['name'], expect: { '': {} }
});

function cachePath(value) {
	return /^\/tmp\/hongguo-[A-Za-z0-9_/-]+$/.test(value) ||
		/^\/mnt\/[A-Za-z0-9_/-]+\/hongguo-[A-Za-z0-9_/-]+$/.test(value);
}

return view.extend({
	load: function() {
		return uci.load('hongguo');
	},

	render: function() {
		var m = new form.Map('hongguo', '红果短剧',
			'在局域网浏览器中观看。观看用户名固定为 hongguo，密码在下方设置。所有设备共享红果账号、历史和收藏。');
		var s = m.section(form.NamedSection, 'main', 'hongguo', '服务设置');
		s.addremove = false;
		var o = s.option(form.Flag, 'enabled', '启用服务');
		o.rmempty = false;
		o.default = '0';

		o = s.option(form.Value, 'listen', '监听 IPv4 地址');
		o.value('0.0.0.0', '所有 IPv4 地址（仅允许私网来源访问）');
		o.value('127.0.0.1', '仅本机');
		o.default = '0.0.0.0';
		o.datatype = 'ip4addr';
		o.rmempty = false;
		o.description = '可填写 OpenWrt 的 LAN IPv4 地址。观看页面请使用 IP 地址打开，不支持主机名和 IPv6。';

		o = s.option(form.Value, 'port', '观看端口');
		o.default = '8797';
		o.datatype = 'range(1024,65535)';
		o.rmempty = false;
		o.description = '选择未被其他服务占用的端口；无需更改 LuCI 端口。';

		o = s.option(form.Value, 'password', '观看密码');
		o.password = true;
		o.rmempty = false;
		o.description = '设置 12～128 位 ASCII 字母、数字或符号。此密码用于观看网页，不是红果账号密码或 OpenWrt 登录密码。HTTP 仅用于可信局域网。';
		o.validate = function(section, value) {
			var enabled = this.map.lookupOption('enabled', section)[0].formvalue(section);
			if (!value && enabled !== '1') return true;
			return /^[\x21-\x7e]{12,128}$/.test(value || '') || '请输入 12～128 位可见 ASCII 字符，不含空格和换行';
		};

		o = s.option(form.Value, 'cache_dir', '视频缓存目录');
		o.default = '/tmp/hongguo-media';
		o.rmempty = false;
		o.validate = function(section, value) {
			if (!cachePath(value) || /(?:^|\/)\.{1,2}(?:\/|$)|\/\//.test(value))
				return '请使用专用目录，如 /tmp/hongguo-media 或 /mnt/sda1/hongguo-cache';
			return true;
		};
		o.description = '/tmp 使用内存，重启后清空；建议数据盘挂载后使用 /mnt/挂载点/hongguo-cache。未挂载的数据盘路径会拒绝启动，避免写满系统盘。';

		o = s.option(form.Value, 'cache_mb', '缓存清理阈值（MiB）');
		o.default = '64';
		o.datatype = 'range(16,4096)';
		o.rmempty = false;
		o.description = '1GB 内存先保持 64。此值触发旧缓存清理，处理中视频和程序内存另计，并非总内存硬上限。';

		o = s.option(form.Value, 'max_media_mb', '完整视频单文件上限（MiB）');
		o.default = '32';
		o.datatype = 'range(8,4096)';
		o.rmempty = false;
		o.validate = function(section, value) {
			var limit = this.map.lookupOption('cache_mb', section)[0].formvalue(section);
			return Number(value) <= Number(limit) || '单文件上限不能超过缓存清理阈值';
		};
		o.description = '完整下载播放的单集超过上限会失败。按需 Range 播放不受整个视频大小限制；遇到大文件再按需调整。';

		o = s.option(form.ListValue, 'prepare_concurrency', '视频准备并发');
		['1', '2', '3', '4'].forEach(function(n) { o.value(n, n); });
		o.default = '1';
		o.rmempty = false;
		o.description = 'J1900 / 1GB 内存建议保持 1，不进行服务端视频转码。';

		var state = E('strong', {}, '正在读取…');
		var note = E('p', {}, '首次使用：设置观看密码，勾选启用服务，然后点击“保存并应用”。');
		var open = E('a', { 'class': 'cbi-button cbi-button-action', 'target': '_blank', 'rel': 'noopener noreferrer' }, '打开观看页面');
		var refreshStatus = function() {
			return serviceList('hongguo').then(function(result) {
				var instances = result.hongguo && result.hongguo.instances || {};
				var running = Object.keys(instances).some(function(k) { return instances[k].running; });
				state.textContent = running ? '运行中' : '未运行';
				state.style.color = running ? '#198754' : '#b45309';
				var host = uci.get('hongguo', 'main', 'listen') || '0.0.0.0';
				if (host === '0.0.0.0') host = window.location.hostname;
				var ipv4 = /^\d+\.\d+\.\d+\.\d+$/.test(host);
				if (running && ipv4 && host !== '127.0.0.1') {
					open.href = 'http://' + host + ':' + (uci.get('hongguo', 'main', 'port') || '8797') + '/';
					open.style.display = '';
				} else {
					open.removeAttribute('href'); open.style.display = 'none';
				}
				if (running && !ipv4)
					note.textContent = '服务运行中。请用 OpenWrt 的 LAN IPv4 地址和观看端口打开网页，例如 http://192.168.1.1:8797/。';
			}).catch(function() { state.textContent = '无法读取服务状态'; });
		};
		var action = function(command) {
			return fs.exec('/etc/init.d/hongguo', [command]).then(function(result) {
				if (result.code !== 0) throw new Error(result.stderr || result.stdout || '服务操作失败');
				if (command === 'restart' && uci.get('hongguo', 'main', 'enabled') !== '1')
					ui.addNotification(null, E('p', {}, '请先勾选“启用服务”并保存应用。'));
				return refreshStatus();
			}).catch(function(error) { ui.addNotification(null, E('p', {}, error.message), 'error'); });
		};
		var status = E('div', { 'class': 'cbi-section' }, [
			E('h3', {}, '运行状态'), E('p', {}, ['服务：', state]), note,
			E('div', { 'class': 'cbi-section-actions' }, [
				open, ' ',
				E('button', { 'class': 'cbi-button cbi-button-apply', 'click': ui.createHandlerFn(this, function() { return action('restart'); }) }, '重启服务'), ' ',
				E('button', { 'class': 'cbi-button cbi-button-negative', 'click': ui.createHandlerFn(this, function() { return action('stop'); }) }, '临时停止')
			]),
			E('p', { 'style': 'margin-top:1em;color:#666' }, '停止按钮仅影响本次运行；要禁止开机启动，请取消“启用服务”并保存应用。日志可在“状态 → 系统日志”中查找 hongguo。')
		]);
		poll.add(refreshStatus, 5);
		return m.render().then(function(node) {
			refreshStatus();
			return E('div', {}, [status, node]);
		});
	}
});
