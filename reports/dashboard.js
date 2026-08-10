const tabs=[...document.querySelectorAll('.tab')];
const search=document.querySelector('#search');
const thead=document.querySelector('#thead');
const tbody=document.querySelector('#tbody');
const count=document.querySelector('#count');
const empty=document.querySelector('#empty');
const pageLabel=document.querySelector('#page');
const panel=document.querySelector('#panel-stats');
let rows=[],headers=[],filtered=[],page=1,sortKey='',sortDirection=1,activeSlug='stats_espece_trait';
const size=10;
const columnLabels={ESPECE_FR:'Catégorie',MAIN_NAME:'Matériel',TRAIT:'Trait',count:'Nombre',mean:'Moyenne',median:'Médiane',std:'Écart-type',min:'Minimum',max:'Maximum',q25:'1er quartile',q75:'3e quartile',REGION:'Région',nb_essais:"Nombre d’essais",nb_regions:'Nombre de régions',F_stat:'Statistique F',p_value:'Valeur p',significatif:'Significatif'};
const numericColumns=new Set(['count','mean','median','std','min','max','q25','q75','nb_essais','nb_regions','F_stat','p_value']);
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const parseCSV=text=>{const lines=text.trim().split(/\r?\n/),split=line=>line.split(';');headers=split(lines.shift());return lines.map(line=>Object.fromEntries(split(line).map((v,i)=>[headers[i],v])))};
const displayValue=(value,key)=>{
  if(key==='significatif')return String(value).toLowerCase()==='true'?'<span class="status yes">Oui</span>':'<span class="status no">Non</span>';
  if(numericColumns.has(key)&&value!==''&&!Number.isNaN(Number(value))){const decimals=['count','nb_essais','nb_regions'].includes(key)?0:4;return Number(value).toLocaleString('fr-FR',{maximumFractionDigits:decimals})}
  return esc(value);
};
async function load(tab){
  tabs.forEach((item,index)=>{const active=item===tab;item.id=`table-tab-${index+1}`;item.setAttribute('aria-selected',String(active));item.tabIndex=active?0:-1});
  panel.setAttribute('aria-labelledby',tab.id);activeSlug=tab.dataset.file.split('/').pop().replace('.csv','');sortKey='';sortDirection=1;
  tbody.innerHTML='<tr><td colspan="10"><span class="loader" aria-hidden="true"></span> Chargement des données…</td></tr>';
  try{rows=parseCSV(await fetch(tab.dataset.file).then(response=>{if(!response.ok)throw Error();return response.text()}));page=1;apply()}catch(error){tbody.innerHTML='<tr><td colspan="10">Impossible de charger le fichier. Ouvrez le site depuis le serveur local.</td></tr>'}
}
function apply(){
  const query=search.value.trim().toLocaleLowerCase('fr');
  filtered=rows.filter(row=>Object.values(row).some(value=>String(value).toLocaleLowerCase('fr').includes(query)));
  if(sortKey)filtered.sort((a,b)=>{const av=numericColumns.has(sortKey)?Number(a[sortKey]):String(a[sortKey]).toLocaleLowerCase('fr'),bv=numericColumns.has(sortKey)?Number(b[sortKey]):String(b[sortKey]).toLocaleLowerCase('fr');return(av>bv?1:av<bv?-1:0)*sortDirection});
  page=Math.min(page,Math.max(1,Math.ceil(filtered.length/size)));render();
}
function render(){
  thead.innerHTML='<tr>'+headers.map(key=>`<th scope="col"><button class="sort-button" type="button" data-key="${esc(key)}" aria-label="Trier par ${esc(columnLabels[key]||key)}">${esc(columnLabels[key]||key.replaceAll('_',' '))}<span aria-hidden="true">${sortKey===key?(sortDirection===1?' ↑':' ↓'):''}</span></button></th>`).join('')+'</tr>';
  const current=filtered.slice((page-1)*size,page*size);
  tbody.innerHTML=current.map(row=>'<tr>'+headers.map(key=>`<td>${displayValue(row[key],key)}</td>`).join('')+'</tr>').join('');
  empty.hidden=current.length>0;tbody.hidden=current.length===0;
  count.textContent=`${filtered.length.toLocaleString('fr-FR')} résultat${filtered.length>1?'s':''} trouvé${filtered.length>1?'s':''}`;
  pageLabel.textContent=`Page ${page} / ${Math.max(1,Math.ceil(filtered.length/size))}`;
  document.querySelector('#prev').disabled=page===1;document.querySelector('#next').disabled=page>=Math.ceil(filtered.length/size);
  document.querySelectorAll('.sort-button').forEach(button=>button.onclick=()=>{const key=button.dataset.key;if(sortKey===key)sortDirection*=-1;else{sortKey=key;sortDirection=1}page=1;apply()});
}
function exportRows(){
  if(!filtered.length){count.textContent='Export impossible : aucun résultat.';return}
  const csv='\ufeff'+[headers.map(key=>columnLabels[key]||key).join(';'),...filtered.map(row=>headers.map(key=>`"${String(row[key]??'').replaceAll('"','""')}"`).join(';'))].join('\r\n');
  const link=document.createElement('a'),url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));
  link.href=url;link.download=`semences_${activeSlug}_${new Date().toISOString().slice(0,10)}.csv`;link.hidden=true;document.body.appendChild(link);link.click();setTimeout(()=>{link.remove();URL.revokeObjectURL(url)},1500);
}
search.setAttribute('aria-label','Rechercher dans le tableau');
const clear=document.createElement('button');clear.type='button';clear.className='button';clear.textContent='Effacer le filtre';search.insertAdjacentElement('afterend',clear);
clear.onclick=()=>{search.value='';page=1;apply();search.focus()};
tabs.forEach((tab,index)=>{tab.id=`table-tab-${index+1}`;tab.addEventListener('click',()=>load(tab));tab.addEventListener('keydown',event=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;event.preventDefault();let next=index+(event.key==='ArrowRight'?1:event.key==='ArrowLeft'?-1:0);if(event.key==='Home')next=0;if(event.key==='End')next=tabs.length-1;next=(next+tabs.length)%tabs.length;tabs[next].focus();load(tabs[next])})});
search.addEventListener('input',()=>{page=1;apply()});document.querySelector('#prev').onclick=()=>{page--;render()};document.querySelector('#next').onclick=()=>{page++;render()};document.querySelector('#export').onclick=exportRows;
const glossary=document.createElement('section');glossary.className='section';glossary.innerHTML='<div class="wrap"><div class="section-head"><div><div class="eyebrow">Guide de lecture</div><h2>Unités et définition des traits</h2></div><p>Les définitions non confirmées restent explicitement à documenter.</p></div><div class="table-wrap"><table><thead><tr><th>Code</th><th>Signification</th><th>Unité</th></tr></thead><tbody><tr><td>YD15QH</td><td>Rendement standardisé à 15 % d’humidité</td><td>q/ha</td></tr><tr><td>YD16QH</td><td>Rendement standardisé à 16 % d’humidité</td><td>q/ha</td></tr><tr><td>%MOIS</td><td>Pourcentage d’humidité</td><td>%</td></tr><tr><td>MT_DAT</td><td>Variable de date ou maturité à normaliser</td><td>Non homogène</td></tr><tr><td>LOD1</td><td>Définition métier à confirmer</td><td>À confirmer</td></tr><tr><td>CT</td><td>Définition métier à confirmer</td><td>À confirmer</td></tr></tbody></table></div><div class="notice info" style="margin-top:18px"><strong>Comment utiliser ce dashboard ?</strong> Choisissez un onglet, recherchez une valeur, triez avec un en-tête, exportez le résultat ou poursuivez vers la carte.</div></div>';
document.querySelector('.section.alt').insertAdjacentElement('beforebegin',glossary);
load(tabs[0]);
