/* History is kept on the server; no customer data is written to browser storage. */
let savingQuote=false;
let savedListVersion=0;
let savedOffset=0;
let savedQuery='';

async function savedRequest(path,options={}){
  let response;
  try{response=await fetch(path,{...options,cache:'no-store'});}
  catch(error){throw new Error('Could not reach saved quotes. Reconnect and try again.');}
  let data;
  try{data=await response.json();}catch(error){throw new Error('Saved quotes are unavailable. Please try again.');}
  if(!response.ok){const error=new Error(data.error || 'Could not access saved quotes');error.status=response.status;throw error;}
  return data;
}

function savedMessage(message,error=null){
  const status=document.getElementById('saved_quotes_status');
  status.textContent=message;
  if(error?.status===401){
    const link=document.createElement('a');link.href='/login';link.textContent=' Sign in again';status.appendChild(link);
  }
}

function savedElement(tag,text,parent){
  const element=document.createElement(tag);if(text!==undefined) element.textContent=text;
  if(parent) parent.appendChild(element);return element;
}

function savedDate(value){
  return value ? new Intl.DateTimeFormat(undefined,{dateStyle:'medium',timeStyle:'short'}).format(new Date(value)) : 'Not specified';
}

async function saveCurrentQuote(){
  if(savingQuote || !trip || !currentPricing || pricingPending){savedMessage('Wait for a complete, updated quote before saving.');return;}
  const name=document.getElementById('save_quote_name');
  if(!name.value.trim()){name.setCustomValidity('Enter a name for this quote.');name.reportValidity();name.setCustomValidity('');return;}
  if(!name.checkValidity()){name.reportValidity();return;}
  const button=document.getElementById('save_quote_button');
  const feedback=document.getElementById('save_quote_status');
  const payload={name:name.value.trim(),notes:document.getElementById('notes').value,
    trip:{pickup:trip.pickup,destination:trip.destination,stops:trip.stops,vehicle:trip.vehicle,pickup_time:trip.pickup_time,
      full_cycle:{minutes:trip.full_cycle.minutes,miles:trip.full_cycle.miles},
      one_way:{minutes:trip.one_way.minutes,miles:trip.one_way.miles}},
    pricing:{quote:currentPricing.quote,additional_charge:currentPricing.additional_charge,include_tip:currentPricing.include_tip,
      pricing_origin:currentPricing.pricing_origin || 'adjustment'}};
  savingQuote=true;button.disabled=true;button.textContent='Saving…';savedMessage('Saving quote…');
  feedback.textContent='Saving quote…';
  try{
    const record=await savedRequest('/api/saved-quotes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    document.getElementById('saved_search').value='';
    const panel=document.getElementById('saved_quotes_panel');
    if(panel.open) await loadSavedQuotes();else panel.open=true;
    renderSavedQuote(record);
    savedMessage(`Saved “${record.name}”. You can find it under Saved quotes.`);
    feedback.textContent=`Saved “${record.name}”.`;
  }catch(error){savedMessage(error.message,error);feedback.textContent=error.message;}
  finally{savingQuote=false;button.textContent='Save quote';button.disabled=pricingPending;}
}

async function loadSavedQuotes(append=false){
  const version=++savedListVersion;
  if(!append){savedOffset=0;savedQuery=document.getElementById('saved_search').value.trim();}
  const offset=append ? savedOffset : 0;
  document.getElementById('saved_more').disabled=true;
  savedMessage('Loading saved quotes…');
  try{
    const data=await savedRequest(`/api/saved-quotes?q=${encodeURIComponent(savedQuery)}&offset=${offset}`);
    if(version!==savedListVersion) return;
    document.getElementById('saved_profile').textContent=`Profile: ${data.profile.display_name}. ${data.profile.shared ? 'People using the team login share this history.' : 'Saved quotes belong to this profile.'}`;
    const list=document.getElementById('saved_quotes_list');
    if(!append) list.replaceChildren();
    data.quotes.forEach(record=>{
      const card=savedElement('article',undefined,list);card.className='saved-card';
      savedElement('h3',record.name,card);
      savedElement('p',`${savedDate(record.created_at)} · $${money(record.pricing.all_inclusive_price)}${record.pricing.include_tip ? ' including tip' : ''}`,card);
      savedElement('p',[record.pickup,...record.stops,record.destination].join(' → '),card);
      const view=savedElement('button','View quote',card);view.type='button';view.className='secondary';view.onclick=()=>viewSavedQuote(record.id);
      const remove=savedElement('button','Delete',card);remove.type='button';remove.className='secondary';remove.onclick=()=>deleteSavedQuote(record,remove);
    });
    savedOffset=offset+data.quotes.length;
    document.getElementById('saved_more').hidden=!data.has_more;
    savedMessage(savedOffset ? `${savedOffset} saved ${savedOffset===1 ? 'quote' : 'quotes'} shown.` : 'No saved quotes found.');
  }catch(error){if(version===savedListVersion) savedMessage(error.message,error);}
  finally{if(version===savedListVersion) document.getElementById('saved_more').disabled=false;}
}

async function viewSavedQuote(id){
  try{const record=await savedRequest(`/api/saved-quotes/${encodeURIComponent(id)}`);renderSavedQuote(record);savedMessage(`Viewing “${record.name}”.`);document.getElementById('saved_quote_detail').scrollIntoView({behavior:'smooth',block:'start'});}
  catch(error){savedMessage(error.message,error);}
}

function renderSavedQuote(record){
  const panel=document.getElementById('saved_quote_detail');panel.replaceChildren();panel.hidden=false;panel.dataset.quoteId=record.id;
  savedElement('h3',record.name,panel);
  savedElement('p',`Saved ${savedDate(record.created_at)}. Historical quote — not recalculated.`,panel);
  const fare=savedElement('div',undefined,panel);fare.className='fare-summary';
  savedElement('span',record.pricing.include_tip ? 'Saved all-inclusive price' : 'Saved total',fare);
  savedElement('strong',`$${money(record.pricing.all_inclusive_price)}`,fare);
  const values=[['Route',[record.pickup,...record.stops,record.destination].join(' → ')],
    ['Vehicle',record.vehicle==='suv' ? 'SUV' : 'Sedan'],['Pickup time',savedDate(record.pickup_time)],
    ['Full driver cycle',`${record.full_cycle.miles} miles / ${formatDuration(record.full_cycle.minutes)}`],
    ['Customer route',`${record.one_way.miles} miles / ${formatDuration(record.one_way.minutes)}`],
    ['Hourly rate',`$${money(record.pricing.hourly_rate)}/hr`],['Customer mileage rate',`$${money(record.pricing.mileage_rate)}/mile`],
    ['Trip price',`$${money(record.pricing.trip_price)}`],['Additional charge',`$${money(record.pricing.additional_charge)}`],
    ['Quote before tip',`$${money(record.pricing.quote)}`],['20% tip',record.pricing.include_tip ? `$${money(record.pricing.tip_amount)}` : 'Not included'],
    ['Total',`$${money(record.pricing.all_inclusive_price)}`]];
  const list=savedElement('dl',undefined,panel);
  values.forEach(([label,value])=>{savedElement('dt',label,list);savedElement('dd',value,list);});
  if(record.notes){savedElement('h4','Notes',panel);savedElement('p',record.notes,panel).className='saved-notes';}
  savedElement('p','Pickup and saved times are shown in this device’s timezone. Use this trip again to calculate a new quote at current routing and pricing.',panel).className='hint';
  const reuse=savedElement('button','Use trip for a new quote',panel);reuse.type='button';reuse.className='secondary';reuse.onclick=()=>reuseSavedQuote(record);
}

function reuseSavedQuote(record){
  if((trip || document.getElementById('pickup').value || document.getElementById('notes').value || comparisons.length) && !window.confirm('Replace the current quote and comparisons with this saved trip? Your saved quotes will stay unchanged.')) return;
  startNewQuote();
  document.getElementById('pickup').value=record.pickup;document.getElementById('destination').value=record.destination;
  document.getElementById('vehicle').value=record.vehicle;document.getElementById('notes').value=record.notes;
  if(record.pickup_time){
    const date=new Date(record.pickup_time);const pad=value=>String(value).padStart(2,'0');
    document.getElementById('pickup_time').value=`${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }
  document.getElementById('include_stops').checked=record.stops.length>0;
  document.getElementById('stops_fields').hidden=!record.stops.length;
  record.stops.forEach(address=>{addStop();const inputs=document.querySelectorAll('.extra-stop-address');inputs[inputs.length-1].value=address;});
  document.getElementById('include_charge').checked=record.pricing.additional_charge>0;toggleAdditionalCharge();
  document.getElementById('additional_charge').value=money(record.pricing.additional_charge);
  document.getElementById('include_tip').checked=record.pricing.include_tip;
  savedMessage('Trip copied. Review pickup time, then press Calculate trip. The saved quote stays unchanged.');
  document.getElementById('pickup').scrollIntoView({behavior:'smooth',block:'center'});
}

async function deleteSavedQuote(record,button){
  if(!window.confirm(`Delete saved quote “${record.name}”? This cannot be undone.`)) return;
  button.disabled=true;
  try{
    await savedRequest(`/api/saved-quotes/${encodeURIComponent(record.id)}`,{method:'DELETE'});
    const detail=document.getElementById('saved_quote_detail');if(detail.dataset.quoteId===record.id){detail.hidden=true;detail.replaceChildren();}
    await loadSavedQuotes();savedMessage(`Deleted “${record.name}”.`);
  }catch(error){savedMessage(error.message,error);}
  finally{button.disabled=false;}
}
