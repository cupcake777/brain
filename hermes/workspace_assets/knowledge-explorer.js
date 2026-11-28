(() => {
  'use strict';
  const payload = document.getElementById('knowledge-exploration-data');
  if (!payload) return;
  const data = JSON.parse(payload.textContent);
  const byKey = new Map(data.nodes.map(node => [node.key, node]));
  const root = byKey.get(data.root);
  const section = document.getElementById('knowledge-exploration');
  const canvas = document.getElementById('kx-canvas');
  const filter = document.getElementById('kx-relation-type');
  const more = document.getElementById('kx-more');
  const status = document.getElementById('kx-graph-status');
  const mobile = window.matchMedia('(max-width:600px)');
  let visibleLimit = mobile.matches ? 4 : 8;
  let selection = {type: 'node', id: data.root};
  const ns = 'http://www.w3.org/2000/svg';
  function svg(tag, attrs = {}, text) {
    const el = document.createElementNS(ns, tag);
    Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, String(value)));
    if (text !== undefined) el.textContent = text;
    return el;
  }
  function short(text, max) {
    const chars = Array.from(String(text || ''));
    return chars.length > max ? chars.slice(0, max).join('') + '…' : chars.join('');
  }
  function meta(rows) {
    const list = document.getElementById('kx-selection-meta');
    list.replaceChildren();
    rows.filter(row => row[1]).forEach(([label, value, url]) => {
      const group = document.createElement('div');
      const term = document.createElement('dt');
      const description = document.createElement('dd');
      term.textContent = label;
      if (url) {
        const link = document.createElement('a');
        link.href = url;
        link.textContent = value;
        description.append(link);
      } else description.textContent = value;
      group.append(term, description);
      list.append(group);
    });
  }
  function showEvidence(container, value) {
    container.replaceChildren();
    let items;
    try { items=JSON.parse(value); } catch (_) { items=null; }
    if (Array.isArray(items) && items.length && items.every(item=>item && typeof item==='object' && !Array.isArray(item))) {
      const list=document.createElement('div');list.className='kx-evidence-list';
      items.forEach(item=>{
        const record=document.createElement('article');
        const source=document.createElement('strong');source.textContent=item.source_type || '记录依据';record.append(source);
        if(item.source_uri){const uri=document.createElement('p');uri.className='kx-evidence-source';uri.textContent=item.source_uri;record.append(uri);}
        if(item.quoted_excerpt){const excerpt=document.createElement('blockquote');excerpt.textContent=item.quoted_excerpt;record.append(excerpt);}
        if(!item.source_uri && !item.quoted_excerpt){const raw=document.createElement('pre');raw.textContent=JSON.stringify(item,null,2);record.append(raw);}
        list.append(record);
      });
      container.append(list);
    } else {
      const raw=document.createElement('pre');raw.textContent=value || '暂无单独的依据记录';container.append(raw);
    }
  }
  function localTime(value) {
    const date = new Date(value);
    return Number.isNaN(date.valueOf()) ? value : date.toLocaleString('zh-CN', {year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', hour12:false});
  }
  function inspect(type, id) {
    selection = {type, id};
    const title = document.getElementById('kx-selection-title');
    const description = document.getElementById('kx-selection-description');
    const kind = document.getElementById('kx-selection-kind');
    const evidence = document.getElementById('kx-evidence-content');
    const link = document.getElementById('kx-selection-link');
    document.getElementById('kx-selection-evidence').open = false;
    if (type === 'node') {
      const node = byKey.get(id);
      kind.textContent = id === data.root ? '当前经验' : node.kind === 'knowledge' ? '关联经验' : '关联提案';
      title.textContent = node.title;
      description.textContent = node.description || '暂无内容说明';
      meta([['记录状态', node.status], ['适用范围', node.scope]]);
      showEvidence(evidence,node.evidence);
      link.href = node.url + (id === data.root ? '#knowledge-content' : '');
      link.textContent = id === data.root ? '阅读经验原文 →' : '打开完整记录 →';
    } else {
      const edge = data.edges.find(item => item.id === id);
      const source = byKey.get(edge.source), target = byKey.get(edge.target);
      kind.textContent = edge.origin_label;
      title.textContent = edge.label;
      description.textContent = edge.reasoning || '暂无单独的关系说明';
      meta([['来源记录', source.title, source.url], ['关系对象', target.title, target.url],
        ['关系记录者', edge.reviewer], ['记录时间', edge.date ? localTime(edge.date) : '']]);
      showEvidence(evidence,edge.evidence || '这条关系未附单独的依据记录，请结合两端内容核对。');
      const other = edge.source === data.root ? target : source;
      link.href = other.url;
      link.textContent = '打开关联记录 →';
    }
    canvas.querySelectorAll('[data-node]').forEach(el => {
      const active = type === 'node' && el.dataset.node === id;
      el.classList.toggle('selected', active);
      el.setAttribute('aria-pressed', String(active));
    });
    canvas.querySelectorAll('[data-edge]').forEach(el => {
      const active = type === 'edge' && el.dataset.edge === id;
      el.classList.toggle('selected', active);
      el.setAttribute('aria-pressed', String(active));
    });
  }
  function activate(el, callback) {
    el.addEventListener('click', event => {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      callback();
    });
    el.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        callback();
      }
    });
  }
  function draw() {
    const edges = data.edges.filter(edge => filter.value === 'all' || edge.group === filter.value);
    const priority = {conflict:0, review:1, refine:2, lineage:3, related:4};
    const neighbors = new Map();
    edges.forEach(edge => {
      const key = edge.source === data.root ? edge.target : edge.source;
      const score = priority[edge.group];
      if (!neighbors.has(key) || score < neighbors.get(key)) neighbors.set(key, score);
    });
    const keys = [...neighbors.keys()].sort((a,b) => neighbors.get(a) - neighbors.get(b) || a.localeCompare(b)).slice(0,visibleLimit);
    const shown = new Set([data.root, ...keys]);
    const shownEdges = edges.filter(edge => shown.has(edge.source) && shown.has(edge.target));
    const small = mobile.matches;
    const height = small ? Math.max(250, 142 + keys.length * 112) : Math.max(390, Math.ceil(keys.length/2)*122 + 60);
    const width = small ? 400 : 1000;
    const positions = new Map([[data.root, small ? {x:222,y:68} : {x:500,y:height/2}]]);
    keys.forEach((key,index) => {
      if (small) positions.set(key,{x:222,y:190+index*112});
      else {
        const column = index%2;
        const rows = Math.ceil((keys.length-column)/2);
        positions.set(key,{x:column ? 834 : 166,y:height/2 + (Math.floor(index/2)-(rows-1)/2)*122});
      }
    });
    const graph = svg('svg', {viewBox:`0 0 ${width} ${height}`, role:'group', 'aria-label':'局部关系图，选择节点或连线查看详情'});
    const defs = svg('defs');
    for (const group of ['conflict','refine','review','lineage','related']) {
      const marker = svg('marker',{id:'kx-arrow-'+group,viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:6,markerHeight:6,orient:'auto-start-reverse'});
      const color = {conflict:'var(--kx-conflict)',refine:'var(--kx-refine)',lineage:'var(--kx-lineage)',related:'var(--muted)',review:'var(--accent)'}[group];
      marker.append(svg('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:color}));
      defs.append(marker);
    }
    graph.append(defs);
    shownEdges.forEach(edge => {
      const start = positions.get(edge.source), end = positions.get(edge.target);
      const otherKey = edge.source === data.root ? edge.target : edge.source;
      const other = positions.get(otherKey);
      const group = svg('g',{class:'kx-edge '+edge.group,'data-edge':edge.id,tabindex:0,role:'button',
        'aria-label':`${byKey.get(edge.source).title}，${edge.label}，${byKey.get(edge.target).title}`,'aria-pressed':'false'});
      let path, labelX, labelY;
      const parallels = shownEdges.filter(item => (item.source === edge.source && item.target === edge.target) || (item.source === edge.target && item.target === edge.source));
      const offset = (parallels.indexOf(edge)-(parallels.length-1)/2)*23;
      if (small) {
        const sx = start.x-122, ex = end.x-122;
        const rail = 16 + (keys.indexOf(otherKey)%4)*10;
        path = `M ${sx} ${start.y+offset} H ${rail} V ${end.y+offset} H ${ex}`;
        labelX = 51; labelY = other.y+offset;
      } else {
        const direction = end.x>start.x ? 1 : -1;
        const sx = start.x+direction*122, ex = end.x-direction*122;
        path = `M ${sx} ${start.y} C ${(sx+ex)/2} ${start.y+offset*2}, ${(sx+ex)/2} ${end.y+offset*2}, ${ex} ${end.y}`;
        labelX = (500+other.x)/2; labelY = (height/2+other.y)/2+offset;
      }
      const lineAttrs = {class:'kx-edge-line',d:path};
      if (!['conflicts_with','contradicts','related_to'].includes(edge.relation)) lineAttrs['marker-end'] = `url(#kx-arrow-${edge.group})`;
      group.append(svg('title',{},edge.reasoning || edge.label),svg('path',{class:'kx-edge-hit',d:path}),svg('path',lineAttrs),
        svg('rect',{x:labelX-(small ? 48 : 43),y:labelY-(small ? 28 : 10),width:small ? 96 : 86,height:small ? 56 : 20,rx:5}),svg('text',{x:labelX,y:labelY+4,'text-anchor':'middle'},edge.label));
      activate(group,()=>inspect('edge',edge.id));
      graph.append(group);
    });
    [data.root,...keys].forEach(key => {
      const node = byKey.get(key), point = positions.get(key), isRoot = key === data.root;
      const group = svg('a',{href:node.url,class:'kx-node '+(isRoot ? 'root ' : '')+node.kind,'data-node':key,tabindex:0,role:'button','aria-label':node.title+'，'+node.status,'aria-pressed':'false'});
      group.append(svg('title',{},node.title),svg('rect',{x:point.x-122,y:point.y-43,width:244,height:86,rx:isRoot ? 17 : node.kind === 'proposal' ? 4 : 12}),
        svg('text',{class:'kx-node-kind',x:point.x-105,y:point.y-22},isRoot ? '当前经验' : node.kind === 'knowledge' ? '已有经验' : '关联提案'));
      const chars=Array.from(node.title);
      const lines = chars.length>13 ? [chars.slice(0,13).join(''),short(chars.slice(13).join(''),13)] : [node.title];
      lines.forEach((line,index)=>group.append(svg('text',{x:point.x-105,y:point.y+(index*19),'font-size':16,'font-weight':600},line)));
      if (lines.length===1) group.append(svg('text',{class:'kx-node-subtitle',x:point.x-105,y:point.y+23},node.status));
      activate(group,()=>inspect('node',key));
      graph.append(group);
    });
    if (!keys.length) {
      graph.append(svg('text',{class:'kx-svg-empty',x:width/2,y:small ? 170 : height/2+94,'text-anchor':'middle'},data.edges.length ? '当前筛选下暂无关系' : '暂未记录关联关系'));
    }
    canvas.replaceChildren(graph);
    status.textContent = `显示 ${keys.length} / ${neighbors.size} 条关联记录`;
    more.hidden = keys.length>=neighbors.size;
    if (selection.type==='node' && !shown.has(selection.id) || selection.type==='edge' && !shownEdges.some(edge=>edge.id===selection.id)) selection={type:'node',id:data.root};
    inspect(selection.type,selection.id);
  }
  filter.closest('label').hidden = false;
  filter.addEventListener('change',()=>{visibleLimit=mobile.matches ? 4 : 8;draw();});
  more.addEventListener('click',()=>{visibleLimit+=mobile.matches ? 4 : 8;draw();});
  mobile.addEventListener('change',()=>{visibleLimit=mobile.matches ? 4 : 8;draw();});
  section.querySelectorAll('time[datetime]').forEach(el=>{el.textContent=localTime(el.dateTime);el.title=el.dateTime;});
  const events = [...section.querySelectorAll('.kx-event')];
  section.querySelector('.kx-history-filters').hidden = false;
  let historyCategory='all', historyLimit=8;
  const historyMore=document.getElementById('kx-history-more');
  function filterHistory() {
    const matching=events.filter(event=>historyCategory==='all' || event.dataset.category===historyCategory);
    const shown=new Set(matching.slice(0,historyLimit));
    events.forEach(event=>{event.hidden=!shown.has(event);});
    section.querySelector('.kx-timeline-empty').hidden=matching.length>0;
    historyMore.hidden=matching.length<=historyLimit;
    historyMore.textContent=`查看更多记录（已显示 ${Math.min(historyLimit,matching.length)} / ${matching.length}）`;
  }
  section.querySelectorAll('[data-kx-history]').forEach(button=>button.addEventListener('click',()=>{
    historyCategory=button.dataset.kxHistory;historyLimit=8;
    section.querySelectorAll('[data-kx-history]').forEach(other=>{
      const active=other===button;other.classList.toggle('active',active);other.setAttribute('aria-pressed',String(active));
    });
    filterHistory();
  }));
  historyMore.addEventListener('click',()=>{historyLimit+=16;filterHistory();});
  filterHistory();
  const order=document.getElementById('kx-order');
  order.hidden=false;
  let ascending=false;
  order.addEventListener('click',()=>{
    ascending=!ascending;
    const list=section.querySelector('.kx-timeline');
    events.reverse();events.forEach(event=>list.append(event));filterHistory();
    order.textContent=ascending ? '最早在前 ↑' : '最近在前 ↓';
  });
  section.querySelectorAll('[data-kx-edge]').forEach(button=>button.addEventListener('click',()=>{
    filter.value='all';visibleLimit=data.nodes.length;selection={type:'edge',id:button.dataset.kxEdge};draw();
    document.getElementById('local-graph').scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion:reduce)').matches ? 'instant' : 'smooth',block:'start'});
    const edge=[...canvas.querySelectorAll('[data-edge]')].find(el=>el.dataset.edge===button.dataset.kxEdge);
    if(edge) edge.focus({preventScroll:true});
  }));
  draw();
})();
