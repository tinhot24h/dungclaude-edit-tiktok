'use strict';
// ai33.pro v3 audio page: single voice or multi-speaker dialogue, voice library, clones,
// pronunciation dictionaries and a history of task cards. Keys never leave the session.
(()=>{
const STORE='review-audio-v7',PROVIDERS=[['edge','Edge'],['vbee','Vbee'],['elevenlabs','ElevenLabs'],['minimax','Minimax'],['fishaudio','Fish Audio'],['kokoro','Kokoro'],['clone','Giọng nhân bản']];
const saved=['tts-text','tts-file-name','tts-task-id','tts-language','tts-gender','tts-search','tts-locale','tts-category','tts-ownership','tts-sort'];
const el=(tag,props={},...children)=>{const e=Object.assign(document.createElement(tag),props);e.append(...children);return e};
const post=(url,body)=>request(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...auth(),...body})});
let configured=false,mode='single',voice=null,speakers=[],provider='edge',target='single',dictionaries=[],dictId=null,cycle=0,pollTimer,tracking=false,creating=false,current=null;
let voices=[],voicePage=1,voiceMore=false,voiceTicket=0,historyPage=1,historyMore=false,historyTicket=0,lastHistory=0,account=0;

function auth(){const key=$('tts-key').value.trim();return key?{api_key:key}:{}}
function ready(){return !!$('tts-key').value.trim()||configured}
function need(){if(!ready())throw Error('Nhập ai33.pro API key trong mục Kết nối (cột phải). Không dùng key Gemini/OpenAI.')}
function status(text){$('tts-status').textContent=text}
function label(i){return String.fromCharCode(65+i)}
function describe(v){return v?[v.language,v.gender,...(v.tags||[]).slice(0,2)].filter(Boolean).join(' · ')||v.voice_id:''}

// ---- persistence (text, choices; never the key)
function save(){const data={mode,voice,speakers,provider,speed:$('tts-speed').value,delay:$('tts-delay').value,transcript:$('tts-transcript').checked,autoplay:$('tts-autoplay').checked,dictionary:$('tts-dictionary').value,current};for(const id of saved)data[id]=$(id).value;
 try{localStorage.setItem(STORE,JSON.stringify(data));$('tts-save-note').textContent='Đã lưu trên trình duyệt'}catch{data['tts-text']='';try{localStorage.setItem(STORE,JSON.stringify(data))}catch{}$('tts-save-note').textContent='Văn bản quá dài để tự lưu'}counter()}
function restore(){let data=null;try{data=JSON.parse(localStorage.getItem(STORE))}catch{}
 if(!data){try{const old=JSON.parse(localStorage.getItem('review-audio-v6'));if(old){data={'tts-text':old['tts-text'],'tts-file-name':old['tts-file-name'],'tts-task-id':old['tts-task-id'],speed:old['tts-speed'],voice:old['tts-voice-id']?{voice_id:old['tts-voice-id'],name:old['tts-voice-id']}:null}}}catch{}}
 if(!data)return;for(const id of saved)if(typeof data[id]==='string')$(id).value=data[id];
 if(data.mode==='dialogue')mode='dialogue';if(data.voice?.voice_id)voice=data.voice;if(Array.isArray(data.speakers))speakers=data.speakers.filter(s=>s&&typeof s==='object').map(s=>({voice:s.voice?.voice_id?s.voice:null,speed:Number(s.speed)||1}));
 if(PROVIDERS.some(p=>p[0]===data.provider))provider=data.provider;if(data.speed)$('tts-speed').value=data.speed;if(data.delay)$('tts-delay').value=data.delay;$('tts-transcript').checked=!!data.transcript;$('tts-autoplay').checked=!!data.autoplay;
 if(typeof data.dictionary==='string')dictId=data.dictionary;if(data.current?.task_id)current=data.current}
function counter(){const text=$('tts-text').value,words=text.trim()?text.trim().split(/\s+/).length:0,speed=mode==='single'?Number($('tts-speed').value)||1:1,seconds=Math.round(words/2.8/speed);$('tts-count').textContent=text.length.toLocaleString('vi-VN')+' ký tự · '+words.toLocaleString('vi-VN')+' tiếng';$('tts-estimate').textContent=words?`≈ ${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')} phút đọc`:''}

// ---- mode, voice selection, speakers
function setMode(next){mode=next;$('tts-mode-single').setAttribute('aria-pressed',String(mode==='single'));$('tts-mode-dialogue').setAttribute('aria-pressed',String(mode==='dialogue'));$('tts-single-settings').hidden=mode!=='single';$('tts-dialogue-settings').hidden=mode!=='dialogue';$('tts-labels').hidden=mode!=='dialogue';
 if(mode==='dialogue'){while(speakers.length<2)speakers.push({voice:speakers.length?null:voice,speed:1});$('tts-text').placeholder='A> Câu của người nói A\nB> Câu của người nói B\nA> …'}else $('tts-text').placeholder='Dán hoặc gõ văn bản tiếng Việt cần đọc. Có thể lấy kịch bản từ tab Dịch & biên tập AI.';renderSpeakers();save()}
function renderVoice(){$('tts-voice-name').textContent=voice?.name||'Chọn giọng';$('tts-voice-meta').textContent=voice?describe(voice):'Mở thư viện giọng';$('tts-voice-play').disabled=!voice?.preview_url}
function renderSpeakers(){const box=$('tts-speakers');box.replaceChildren();speakers.forEach((s,i)=>{const pick=el('button',{type:'button',className:'voice-button compact'},el('span',{},el('strong',{textContent:`${label(i)}> ${s.voice?.name||'Chọn giọng'}`}),el('small',{textContent:s.voice?describe(s.voice):'Bấm để chọn giọng'})),el('span',{textContent:'›'}));pick.onclick=()=>openVoices(i);
  const speed=el('input',{type:'range',min:.5,max:1.5,step:.05,value:s.speed,title:'Tốc độ '+label(i)});const value=el('span',{className:'speaker-speed',textContent:Number(s.speed).toFixed(2)+'×'});speed.oninput=()=>{s.speed=Number(speed.value);value.textContent=s.speed.toFixed(2)+'×';save()};
  const drop=el('button',{type:'button',className:'icon-button',textContent:'✕',title:'Bỏ người nói '+label(i),disabled:speakers.length<=2});drop.onclick=()=>{speakers.splice(i,1);renderSpeakers();save()};
  box.append(el('div',{className:'speaker-row'},pick,el('div',{className:'speaker-tools'},speed,value,drop)))});
 const labels=$('tts-labels');labels.querySelectorAll('button').forEach(b=>b.remove());speakers.forEach((_,i)=>{const b=el('button',{type:'button',className:'chip-button',textContent:label(i)+'>'});b.onclick=()=>insertLabel(label(i));labels.append(b)})}
function insertLabel(tag){const e=$('tts-text'),start=e.value.lastIndexOf('\n',e.selectionStart-1)+1,line=e.value.slice(start).replace(/^\s*[A-Z]>\s*/,'');e.value=e.value.slice(0,start)+tag+'> '+line;e.focus();e.selectionStart=e.selectionEnd=start+tag.length+2;save()}
$('tts-mode-single').onclick=()=>setMode('single');$('tts-mode-dialogue').onclick=()=>setMode('dialogue');
$('tts-add-speaker').onclick=()=>{if(speakers.length>=26)return;speakers.push({voice:null,speed:1});renderSpeakers();save()};
$('tts-speed').oninput=()=>{$('tts-speed-value').textContent=Number($('tts-speed').value).toFixed(2);save()};
$('tts-delay').oninput=()=>{$('tts-delay-value').textContent=Number($('tts-delay').value).toFixed(1)+' s';save()};
for(const id of ['tts-transcript','tts-autoplay','tts-dictionary'])$(id).addEventListener('change',save);
for(const id of saved)$(id).addEventListener('input',save);

// ---- voice library drawer
for(const[id,name]of PROVIDERS){const b=el('button',{type:'button',className:'provider-chip',textContent:name});b.dataset.provider=id;b.onclick=()=>{provider=id;markProviders();loadVoices(true);save()};$('tts-providers').append(b)}
function markProviders(){for(const b of $('tts-providers').children)b.setAttribute('aria-pressed',String(b.dataset.provider===provider));for(const f of document.querySelectorAll('.tts-filters [data-only]'))f.hidden=f.dataset.only!==provider;$('tts-clone-box').hidden=provider!=='clone'}
function openVoices(which){target=which;$('tts-drawer-title').textContent=which==='single'?'Chọn giọng đọc':`Chọn giọng cho người nói ${label(which)}`;$('tts-voice-drawer').hidden=false;$('tts-dict-drawer').hidden=true;markProviders();if(!voices.length)loadVoices(true);else renderVoices();$('tts-search').focus()}
$('tts-voice-button').onclick=()=>openVoices('single');$('tts-voice-close').onclick=()=>{$('tts-voice-drawer').hidden=true;$('tts-voice-preview').pause()};
function chosen(){return target==='single'?voice:speakers[target]?.voice}
function choose(v){if(target==='single'){voice=v;renderVoice()}else if(speakers[target]){speakers[target].voice=v;renderSpeakers()}save();renderVoices();status(`Đã chọn giọng ${v.name}.`)}
function preview(url,button){const a=$('tts-voice-preview');if(!url)return;if(a.dataset.url===url&&!a.paused){a.pause();return}a.src=url;a.dataset.url=url;a.play().catch(()=>status('Không phát được mẫu giọng này.'));for(const b of document.querySelectorAll('.voice-play'))b.textContent='▶';if(button){button.textContent='❚❚';a.onpause=a.onended=()=>{button.textContent='▶'}}}
function renderVoices(){const q=$('tts-search').value.trim().toLocaleLowerCase(),list=voices.filter(v=>!q||[v.name,v.voice_id,v.language,v.gender,v.description,...(v.tags||[])].join(' ').toLocaleLowerCase().includes(q)),pick=chosen();
 $('tts-voice-list').replaceChildren(...list.map(v=>{const play=el('button',{type:'button',className:'icon-button voice-play',textContent:'▶',title:'Nghe thử',disabled:!v.preview_url});play.onclick=e=>{e.stopPropagation();preview(v.preview_url,play)};
  const row=el('div',{className:'voice-row'+(pick?.voice_id===v.voice_id?' active':'')},play,el('button',{type:'button',className:'voice-pick'},el('strong',{textContent:v.name}),el('small',{textContent:describe(v)})));row.querySelector('.voice-pick').onclick=()=>choose(v);
  if(provider==='clone'){const drop=el('button',{type:'button',className:'icon-button',textContent:'🗑',title:'Xóa giọng nhân bản'});drop.onclick=()=>deleteClone(v);row.append(drop)}return row}));
 $('tts-voice-status').textContent=voices.length?`${list.length}/${voices.length} giọng${voiceMore?' · còn trang sau':''}`:'';$('tts-load-voices').hidden=!voiceMore}
async function loadVoices(fresh){try{need()}catch(e){$('tts-voice-status').textContent=e.message;return}const ticket=++voiceTicket;if(fresh){voices=[];voicePage=1;renderVoices()}$('tts-voice-status').textContent='Đang tải giọng…';$('tts-load-voices').disabled=true;
 const query={provider,page:voicePage,page_size:100,language:$('tts-language').value.trim(),gender:$('tts-gender').value,search:$('tts-search').value.trim()};if(provider==='vbee')Object.assign(query,{locale:$('tts-locale').value,category:$('tts-category').value,voice_ownership:$('tts-ownership').value});if(provider==='fishaudio')query.sort=$('tts-sort').value;
 try{const d=await post('/audio/voices',query);if(ticket!==voiceTicket)return;const seen=new Set(voices.map(v=>v.voice_id));voices.push(...d.voices.filter(v=>!seen.has(v.voice_id)));voiceMore=!!d.has_more&&d.voices.length>0;voicePage=d.page+1;renderVoices();if(!voices.length)$('tts-voice-status').textContent='Không có giọng theo bộ lọc này. Thử bỏ ngôn ngữ/giới tính.'}
 catch(e){if(ticket===voiceTicket)$('tts-voice-status').textContent=e.message}finally{if(ticket===voiceTicket)$('tts-load-voices').disabled=false}}
$('tts-load-voices').onclick=()=>loadVoices(false);
let searchTimer;$('tts-search').addEventListener('input',()=>{renderVoices();clearTimeout(searchTimer);searchTimer=setTimeout(()=>loadVoices(true),700)});
for(const id of ['tts-language','tts-gender','tts-locale','tts-category','tts-ownership','tts-sort'])$(id).addEventListener('change',()=>loadVoices(true));
$('tts-voice-play').onclick=()=>preview(voice?.preview_url,$('tts-voice-play'));
$('tts-clone-create').onclick=async()=>{const file=$('tts-clone-file').files[0],name=$('tts-clone-name').value.trim();if(!name||!file){$('tts-voice-status').textContent='Nhập tên giọng và chọn file mẫu.';return}if(file.size>10*1024*1024){$('tts-voice-status').textContent='File mẫu tối đa 10 MB.';return}try{need();$('tts-clone-create').disabled=true;$('tts-voice-status').textContent='Đang tạo giọng nhân bản…';
 const d=await request('/audio/clone',{method:'POST',headers:{'X-Voice-Name':encodeURIComponent(name),'X-Filename':encodeURIComponent(file.name),'X-Api-Key':$('tts-key').value.trim()},body:file});$('tts-clone-name').value='';$('tts-clone-file').value='';await loadVoices(true);choose(voices.find(v=>v.voice_id===d.voice_id)||{voice_id:d.voice_id,name:d.name,language:'',gender:'',tags:['clone']})}catch(e){$('tts-voice-status').textContent=e.message}finally{$('tts-clone-create').disabled=false}};
async function deleteClone(v){if(!confirm(`Xóa giọng nhân bản "${v.name}" khỏi tài khoản ai33? Không thể hoàn tác.`))return;try{await post('/audio/clone/delete',{voice_id:v.voice_id});if(voice?.voice_id===v.voice_id){voice=null;renderVoice()}for(const s of speakers)if(s.voice?.voice_id===v.voice_id)s.voice=null;renderSpeakers();save();loadVoices(true)}catch(e){$('tts-voice-status').textContent=e.message}}

// ---- pronunciation dictionaries
function dictOptions(){const keep=$('tts-dictionary').value||dictId||'';$('tts-dictionary').replaceChildren(new Option('Không dùng',''),...dictionaries.map(d=>new Option(`${d.name} · ${d.rules.length} quy tắc`,String(d.id))));$('tts-dictionary').value=dictionaries.some(d=>String(d.id)===keep)?keep:'';
 const pick=$('tts-dict-list').value;$('tts-dict-list').replaceChildren(new Option(dictionaries.length?'— Chọn từ điển để sửa —':'Chưa có từ điển',''),...dictionaries.map(d=>new Option(d.name,String(d.id))));$('tts-dict-list').value=dictionaries.some(d=>String(d.id)===pick)?pick:''}
async function loadDictionaries(){if(!ready())return;try{dictionaries=(await post('/audio/dictionaries',{})).dictionaries;dictOptions()}catch(e){$('tts-dict-status').textContent=e.message}}
function ruleRow(rule={from:'',to:'',matchType:'word',caseSensitive:false}){const from=el('input',{value:rule.from,maxLength:200,placeholder:'AI'}),to=el('input',{value:rule.to,maxLength:200,placeholder:'Ây Ai'}),match=el('select',{},new Option('Cả từ','word'),new Option('Chứa','contains')),cs=el('input',{type:'checkbox',checked:!!rule.caseSensitive,title:'Phân biệt hoa/thường'}),drop=el('button',{type:'button',className:'icon-button',textContent:'✕'});match.value=rule.matchType;const row=el('div',{className:'dict-row'},from,to,match,cs,drop);drop.onclick=()=>row.remove();$('tts-dict-rules').append(row)}
function rules(){return [...$('tts-dict-rules').children].map(r=>{const [from,to,match,cs]=r.querySelectorAll('input,select');return {from:from.value.trim(),to:to.value.trim(),matchType:match.value,caseSensitive:cs.checked}}).filter(r=>r.from)}
function editDict(d){$('tts-dict-name').value=d?.name||'';$('tts-dict-rules').replaceChildren();for(const r of d?.rules?.length?d.rules:[undefined])ruleRow(r);$('tts-dict-delete').disabled=!d;$('tts-dict-output').textContent='';$('tts-dict-list').value=d?String(d.id):''}
$('tts-dict-manage').onclick=()=>{$('tts-dict-drawer').hidden=false;$('tts-voice-drawer').hidden=true;editDict(dictionaries.find(d=>String(d.id)===$('tts-dictionary').value));loadDictionaries()};
$('tts-dict-close').onclick=()=>{$('tts-dict-drawer').hidden=true};$('tts-dict-new').onclick=()=>editDict(null);$('tts-dict-add-rule').onclick=()=>ruleRow();
$('tts-dict-list').onchange=()=>editDict(dictionaries.find(d=>String(d.id)===$('tts-dict-list').value));
$('tts-dict-preview').onclick=async()=>{try{need();const r=await post('/audio/dictionary/preview',{text:$('tts-dict-test').value||$('tts-dict-name').value,rules:rules()});$('tts-dict-output').textContent='Sẽ đọc thành: '+r.output}catch(e){$('tts-dict-output').textContent=e.message}};
$('tts-dict-save').onclick=async()=>{try{need();const id=$('tts-dict-list').value,d=await post('/audio/dictionary/save',{...(id?{id:Number(id)}:{}),name:$('tts-dict-name').value,rules:rules()});await loadDictionaries();$('tts-dict-list').value=String(d.id);$('tts-dictionary').value=String(d.id);save();editDict(d);$('tts-dict-status').textContent=`Đã lưu "${d.name}" và chọn cho lần tạo audio tiếp theo.`}catch(e){$('tts-dict-status').textContent=e.message}};
$('tts-dict-delete').onclick=async()=>{const id=$('tts-dict-list').value;if(!id||!confirm('Xóa từ điển này trên ai33?'))return;try{await post('/audio/dictionary/delete',{id:Number(id)});await loadDictionaries();editDict(null);$('tts-dict-status').textContent='Đã xóa từ điển.'}catch(e){$('tts-dict-status').textContent=e.message}};

// ---- create & track
function payload(){const text=$('tts-text').value.trim();if(!text)throw Error('Nhập văn bản cần đọc.');if(!$('tts-file-name').value.trim())$('tts-file-name').value='Voice_'+new Date().toISOString().replace(/[-:]/g,'').replace('T','_').slice(0,15);
 const common={text,with_transcript:$('tts-transcript').checked,file_name:$('tts-file-name').value.trim()},dict=$('tts-dictionary').value;if(dict)common.pronunciation_dictionary_id=Number(dict);
 if(mode==='single'){if(!voice)throw Error('Chọn giọng nói trước khi tạo audio.');return ['/audio/create',{...common,voice_id:voice.voice_id,speed:Number($('tts-speed').value)}]}
 const used=new Set([...text.matchAll(/^\s*([A-Z])>/gm)].map(m=>m[1]));if(!used.size)throw Error('Hội thoại cần nhãn A>, B>… ở đầu mỗi câu. Bấm nút nhãn phía trên ô chữ để chèn.');
 const missing=speakers.findIndex(s=>!s.voice);if(missing>=0)throw Error(`Chọn giọng cho người nói ${label(missing)}.`);for(const l of used)if(l.charCodeAt(0)-65>=speakers.length)throw Error(`Văn bản có nhãn ${l}> nhưng chưa có người nói ${l}. Bấm + Thêm người nói.`);
 return ['/audio/dialogue',{...common,speakers:speakers.map(s=>({voice_id:s.voice.voice_id,speed:s.speed})),delay:Number($('tts-delay').value)}]}
function busy(){$('tts-create').disabled=creating;$('tts-check').disabled=creating}
function badge(state){return {doing:['Đang xử lý','doing'],done:['Xong','done'],error:['Lỗi','error'],submitted:['Đã gửi','doing']}[state]||[state||'—','']}
function showCurrent(text,state,progress){$('tts-current').hidden=false;$('tts-current-title').textContent=current?.name||current?.task_id||'Tác vụ';const[b,c]=badge(state);$('tts-current-badge').textContent=b;$('tts-current-badge').className='badge '+c;if(progress!=null)$('tts-progress').value=progress;$('tts-task-status').textContent=text}
function stop(message=true){clearTimeout(pollTimer);cycle++;tracking=false;$('tts-stop').disabled=true;if(message&&current)showCurrent('Đã dừng theo dõi. Tác vụ trên ai33 vẫn chạy; xem trong tab Lịch sử.','doing')}
async function track(ticket,started){if(ticket!==cycle||!current)return;try{const d=await post('/audio/task',{task_id:current.task_id});if(ticket!==cycle)return;const cost=d.credit_cost==null?'':` · ${Number(d.credit_cost).toLocaleString('vi-VN')} credit`;
 if(d.status==='error'){tracking=false;showCurrent(d.error||'ai33 báo lỗi tác vụ. Không tạo lại tự động.','error');history(1);return}
 if(d.status==='doing'){showCurrent(`ai33 đang xử lý · ${Math.round(d.progress)}%${cost}`,'doing',d.progress);if(Date.now()-started>20*60*1000){stop();return}pollTimer=setTimeout(()=>track(ticket,started),4000);return}
 showCurrent('Hoàn tất'+cost+' · đang tải MP3 về máy…','done',100);const asset=await post('/audio/cache',{task_id:current.task_id});if(ticket!==cycle)return;tracking=false;current.asset=asset;save();
 showCurrent(`MP3 đã sẵn sàng${cost}. Xem trong Lịch sử để nghe, tải hoặc dùng trong video.`,'done',100);document.dispatchEvent(new CustomEvent('audio-created',{detail:asset}));if($('tts-autoplay').checked){const a=$('tts-voice-preview');a.src=asset.url;a.dataset.url=asset.url;a.play().catch(()=>{})}
 showTab('history');history(1);loadCredits(true)}catch(e){if(ticket===cycle){tracking=false;showCurrent(e.message,'error')}}finally{$('tts-stop').disabled=!tracking}}
function follow(task){stop(false);current=task;save();tracking=true;$('tts-stop').disabled=false;showCurrent('Đang kiểm tra tiến độ…','submitted',0);track(cycle,Date.now())}
$('tts-create').onclick=async()=>{if(creating)return;let route,body;try{need();[route,body]=payload()}catch(e){status(e.message);return}creating=true;busy();status('Đang gửi tới ai33.pro… Không bấm tạo lại khi đang chờ để tránh trừ credit hai lần.');
 try{const d=await post(route,body);status(`Đã gửi tác vụ ${mode==='dialogue'?'hội thoại':'một giọng'}. Có thể tiếp tục soạn đoạn khác.`);$('tts-task-id').value=d.task_id;follow({task_id:d.task_id,name:d.name||body.file_name});$('tts-file-name').value='';save();history(1)}
 catch(e){status(e.message+' Không gửi lại tự động; xem tab Lịch sử trước khi tạo lại.')}finally{creating=false;busy()}};
$('tts-text').addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();$('tts-create').click()}});
$('tts-stop').onclick=()=>stop();
$('tts-check').onclick=()=>{const id=$('tts-task-id').value.trim();if(!/^[A-Za-z0-9_-]{1,200}$/.test(id)){status('task_id không hợp lệ.');return}try{need()}catch(e){status(e.message);return}follow({task_id:id,name:id})};

// ---- history cards
function when(text){const d=new Date(text);return isNaN(d)?text||'':d.toLocaleString('vi-VN',{hour:'2-digit',minute:'2-digit',second:'2-digit',day:'2-digit',month:'2-digit'})}
function card(t){const[b,c]=badge(t.status),box=el('article',{className:'tts-history-card'});box.append(el('div',{className:'card-head'},el('span',{className:'card-time',textContent:when(t.created_at)}),el('span',{className:'badge '+c,textContent:b})),el('p',{className:'card-text',textContent:(t.text||t.name||t.task_id).slice(0,140)+((t.text||'').length>140?'…':''),title:t.text||''}));
 const actions=el('div',{className:'card-actions'});
 if(t.asset){box.append(el('audio',{controls:true,preload:'none',src:t.asset.url}));const dl=el('a',{className:'chip-button',href:t.asset.url+'?download=1',download:(t.asset.name||'voice').replace(/\.mp3$/i,'')+'.mp3',textContent:'⤓ MP3'});const use=el('button',{type:'button',className:'chip-button',textContent:'Dùng làm giọng đọc'});use.onclick=()=>window.chooseAudioAsset(t.asset.asset_id).catch(e=>status(e.message));const bed=el('button',{type:'button',className:'chip-button',textContent:'Làm nhạc nền'});bed.onclick=async()=>{await window.editorState?.useMusic(t.asset.asset_id);switchView('editor')};
  const drop=el('button',{type:'button',className:'chip-button',textContent:'🗑 Xóa khỏi máy',title:'Chỉ xóa file đã tải về máy; tác vụ trên ai33 vẫn còn'});drop.onclick=async()=>{if(!confirm('Xóa MP3 đã tải về máy? Có thể lấy lại từ ai33 nếu link còn hạn.'))return;try{await request('/audio/'+t.asset.asset_id+'/delete',{method:'POST'});history(1);document.dispatchEvent(new Event('audio-created'))}catch(e){status(e.message)}};actions.append(dl,use,bed,drop)}
 else if(t.status==='done'&&t.audio_available){const get=el('button',{type:'button',className:'chip-button primary',textContent:'⤓ Lấy audio về máy'});get.onclick=async()=>{get.disabled=true;get.textContent='Đang tải…';try{await post('/audio/cache',{task_id:t.task_id});history(1);document.dispatchEvent(new Event('audio-created'))}catch(e){get.disabled=false;get.textContent='Thử lại';status(e.message)}};actions.append(get)}
 else if(t.status==='doing'){const watch=el('button',{type:'button',className:'chip-button',textContent:'Theo dõi tiến độ'});watch.onclick=()=>follow({task_id:t.task_id,name:t.name});actions.append(watch)}
 if(t.srt_available){const srt=el('button',{type:'button',className:'chip-button',textContent:'⤓ Phụ đề .srt'});srt.onclick=async()=>{try{const d=await post('/audio/srt',{task_id:t.task_id});const a=el('a',{href:URL.createObjectURL(new Blob([d.srt],{type:'text/plain;charset=utf-8'})),download:(d.name||'phu-de').replace(/\.\w+$/,'')+'.srt'});a.click();setTimeout(()=>URL.revokeObjectURL(a.href),2000)}catch(e){status(e.message)}};actions.append(srt)}
 const meta=el('div',{className:'card-meta'},el('span',{textContent:t.credit_cost!=null?`Tín dụng sử dụng: ${Number(t.credit_cost).toLocaleString('vi-VN')}`:t.type||''}),el('span',{className:'card-id',textContent:t.task_id,title:'task_id'}));box.append(actions,meta);return box}
async function history(page=1){if(!ready()){$('tts-history-status').textContent='Nhập API key để xem lịch sử.';return}const ticket=++historyTicket,acc=account;$('tts-refresh').disabled=true;
 try{const d=await post('/audio/history',{page});if(ticket!==historyTicket||acc!==account)return;lastHistory=Date.now();historyPage=d.page;historyMore=d.has_more;const cards=d.tasks.map(card);if(page===1)$('tts-history-cards').replaceChildren(...cards);else $('tts-history-cards').append(...cards);
  $('tts-history-more').hidden=!historyMore;$('tts-history-status').textContent=d.tasks.length||page>1?'Tự cập nhật mỗi 30 giây khi trang này đang mở.':'Chưa có tác vụ nào.'}
 catch(e){if(ticket===historyTicket)$('tts-history-status').textContent=e.message}finally{if(ticket===historyTicket)$('tts-refresh').disabled=false}}
$('tts-history-more').onclick=()=>history(historyPage+1);$('tts-refresh').onclick=()=>{history(1);loadCredits(true)};
function showTab(tab){$('tts-tab-settings').setAttribute('aria-pressed',String(tab==='settings'));$('tts-tab-history').setAttribute('aria-pressed',String(tab==='history'));$('tts-pane-settings').hidden=tab!=='settings';$('tts-pane-history').hidden=tab!=='history';if(tab==='history'&&Date.now()-lastHistory>15000)history(1)}
$('tts-tab-settings').onclick=()=>showTab('settings');$('tts-tab-history').onclick=()=>showTab('history');
setInterval(()=>{if(!document.hidden&&!$('view-audio').hidden&&!$('tts-pane-history').hidden&&ready())history(1)},30000);

// ---- account, credits, key
async function loadCredits(quiet){if(!ready())return;try{const d=await post('/audio/credits',{});$('tts-credit-pill').textContent='◆ '+Number(d.credits).toLocaleString('vi-VN')+' credit';$('tts-key-badge').textContent='đã kết nối';$('tts-key-badge').className='badge done'}catch(e){if(!quiet)status(e.message);$('tts-key-badge').textContent='lỗi key';$('tts-key-badge').className='badge error'}}
function connect(){if(!ready()){$('tts-connection').open=true;return}loadCredits(true);loadDictionaries();if(!$('tts-pane-history').hidden)history(1);if(current&&!current.asset&&!tracking)follow(current)}
$('tts-credits').onclick=()=>loadCredits(false);
let keyTimer;$('tts-key').addEventListener('input',()=>{account++;voices=[];dictionaries=[];dictOptions();$('tts-history-cards').replaceChildren();$('tts-key-status').textContent=$('tts-key').value?'Đã nhập key cho phiên này.':configured?'Đang dùng key trên máy chủ.':'Chưa nhập key ai33.pro.';clearTimeout(keyTimer);keyTimer=setTimeout(connect,800)});
$('tts-clear-key').onclick=()=>{$('tts-key').value='';$('tts-key').dispatchEvent(new Event('input'));stop(false)};
function config(){return request('/audio-config').then(d=>{const was=configured;configured=d.configured;if(configured){$('tts-key-status').textContent='Đang dùng key ai33 đã lưu trên máy này; có thể để trống ô key.';if(!was)connect()}else $('tts-connection').open=true}).catch(()=>{})}
config();document.addEventListener('keys-changed',config);

// ---- text sources and reset
function useText(source){const text=$(source).value.trim();if(!text){status('Chưa có văn bản để lấy.');return}$('tts-text').value=text;save();status('Đã lấy văn bản. Kiểm tra giọng và bấm Tạo audio.')}
$('tts-from-script').onclick=()=>useText('ai-script');$('tts-from-body').onclick=()=>useText('body');
$('tts-clear-text').onclick=()=>{if($('tts-text').value&&!confirm('Xóa toàn bộ văn bản trong ô?'))return;$('tts-text').value='';save()};
$('ai-to-audio').onclick=()=>{if(!$('ai-script').value.trim()){$('ai-status').textContent='Chưa có kịch bản tiếng Việt. Tạo hoặc nhập kịch bản trước.';return}switchView('audio');useText('ai-script')};
$('tts-reset').onclick=()=>{$('tts-speed').value=1;$('tts-delay').value=.4;$('tts-transcript').checked=false;$('tts-dictionary').value='';$('tts-file-name').value='';for(const s of speakers)s.speed=1;$('tts-speed').oninput();$('tts-delay').oninput();renderSpeakers();save();status('Đã đặt lại tốc độ, khoảng nghỉ, từ điển và phụ đề.')};
document.addEventListener('view-change',e=>{if(e.detail==='audio'){if(ready()&&Date.now()-lastHistory>30000&&!$('tts-pane-history').hidden)history(1)}else $('tts-voice-preview').pause()});

restore();renderVoice();setMode(mode);$('tts-speed').oninput();$('tts-delay').oninput();dictOptions();counter();
if(current){showCurrent(current.asset?'Tác vụ gần nhất đã có MP3 trên máy. Xem tab Lịch sử.':'Tác vụ gần nhất chưa lấy audio. Nhập key để tiếp tục theo dõi.',current.asset?'done':'doing',current.asset?100:0);$('tts-stop').disabled=true}
})();
