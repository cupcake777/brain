"""Account and runtime settings in the shared workspace."""
from __future__ import annotations

from .workspace import e, icon, shell


def settings_page(*, profile: dict, pipeline: dict | None = None, error: str = '', success: str = '', auth_enabled: bool = True, password_enabled: bool = True) -> str:
    profile=profile or {};pipeline=pipeline or {}
    theme=profile.get('theme','light')
    options=''.join(f'<option value="{value}" {"selected" if value==theme else ""}>{label}</option>' for value,label in [('light','浅色'),('modern-dark','深色')])
    password=f'''<section class="panel"><h2>登录密码</h2><form class="form-stack" action="/settings/password" method="post"><label>当前密码<input name="current_password" type="password" autocomplete="current-password" required></label><label>新密码<input name="new_password" type="password" autocomplete="new-password" minlength="6" required></label><label>再次输入新密码<input name="confirm_password" type="password" autocomplete="new-password" minlength="6" required></label><div><button class="btn" type="submit">更新密码</button></div></form></section>''' if auth_enabled and password_enabled else ('<section class="panel"><h2>登录方式</h2><p class="muted">当前使用访问令牌登录，令牌由服务配置管理。</p></section>' if auth_enabled else '')
    states=pipeline.get('proposals',{})
    status='关联完整' if states.get('state')=='healthy' else '有待修复的关联' if states else '暂未读取'
    stats=''.join(f'<div><strong>{int(states.get(key,0))}</strong><small>{label}</small></div>' for key,label in [('linked','已关联经验'),('retired','已退出维护'),('missing','缺少关联')])
    vector=pipeline.get('embeddings',{})
    if isinstance(vector,dict):
        mode='向量索引正常' if vector.get('state')=='healthy' else '当前使用文本检索' if vector.get('state') in {'disabled','not_configured'} else '向量索引正在整理' if vector.get('state')=='syncing' else '向量索引需要检查'
    else:mode='当前使用文本检索'
    alert=f'<p class="panel form-status {"error-text" if error else ""}" role="status">{e(error or success)}</p>' if error or success else ''
    body=f'''<header class="page-head"><div><p class="eyebrow">工作空间</p><h1>设置</h1><p>管理显示偏好、登录和经验整理状态。</p></div></header>{alert}<div class="surface-grid"><div><section class="panel"><h2>显示偏好</h2><form id="workspace-profile" class="form-stack" method="post" action="/api/settings/profile"><label>显示名称<input name="display_name" maxlength="40" value="{e(profile.get('display_name',''))}" autocomplete="nickname"></label><label>头像地址<input name="avatar_url" value="{e(profile.get('avatar_url',''))}" type="text" placeholder="HTTPS 地址或本地图片路径"><small>留空时使用默认标记。</small></label><div class="form-field"><label for="profile-theme">默认外观</label><select name="theme" id="profile-theme">{options}</select></div><input type="hidden" name="lang" value="{e(profile.get('lang','zh'))}"><div><button class="btn primary" type="submit">保存偏好</button></div><p id="profile-status" class="form-status" role="status"></p></form><p class="settings-note">侧栏的明暗切换保存在当前浏览器；保存偏好后会同时更新这台浏览器的外观。</p></section>{password}</div><div><section class="panel"><h2>已处理提案的关联检查</h2><p><span class="tag">{status}</span></p><div class="pipeline-stats">{stats}</div><p class="settings-note">仅统计已批准提案的关联情况；退出维护的记录保留历史。</p><p><a class="text-link" href="/proposals">查看待整理内容 →</a></p><a class="text-link" href="/proposals?tab=flow">查看处理历史 →</a><p class="settings-note">{e(mode)}</p></section><section class="panel"><h2>工作空间入口</h2><p class="muted">按来源和适用范围查经验，或查看真实工作记录。</p><div class="form-stack" style="margin-top:16px"><a class="text-link" href="/environments">服务器与目录 →</a><a class="text-link" href="/projects">工作记录 →</a></div></section>{'<section class="panel"><h2>当前登录</h2><p class="muted">退出后回到登录页。</p><form method="post" action="/logout" style="margin-top:16px"><button class="btn" type="submit">退出登录</button></form></section>' if auth_enabled else ''}</div></div>'''
    script='''
(()=>{const form=document.getElementById('workspace-profile');const select=document.getElementById('profile-theme');
function updateThemeSelect(){let saved;try{saved=localStorage.getItem('hermes_theme')}catch(_){}if(saved)select.value=(saved==='dark'||saved==='modern-dark')?'modern-dark':'light'}
updateThemeSelect();document.addEventListener('brain-theme-change',updateThemeSelect);
form.addEventListener('submit',async event=>{event.preventDefault();const button=form.querySelector('button[type=submit]');const message=document.getElementById('profile-status');button.disabled=true;message.textContent='正在保存…';try{const response=await fetch(form.action,{method:'POST',body:new FormData(form),credentials:'same-origin'});const result=await response.json();if(!response.ok)throw Error(result.detail||'保存失败');const theme=result.profile.theme==='modern-dark'?'dark':'light';document.documentElement.dataset.theme=theme;try{localStorage.setItem('hermes_theme',theme)}catch(_){}document.dispatchEvent(new CustomEvent('brain-profile-change',{detail:result.profile}));message.textContent='偏好已保存。';message.classList.remove('error-text')}catch(error){message.textContent=error.message;message.classList.add('error-text')}finally{button.disabled=false}})})();
'''
    return shell('设置',body,active='settings',extra_js=script)
