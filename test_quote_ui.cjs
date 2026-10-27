const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {spawnSync} = require('node:child_process');

function serverPrice(payload){
  const result=spawnSync(process.env.PYTHON || 'python3',['-c', 'import json,sys; from pricing import reprice_quote; print(json.dumps(reprice_quote(json.load(sys.stdin))))'],{cwd:__dirname,input:JSON.stringify(payload),encoding:'utf8'});
  assert.equal(result.status,0,result.stderr);
  return JSON.parse(result.stdout);
}
async function apiFetch(url,options){
  assert.equal(url,'/api/reprice');
  return {ok:true,status:200,json:async()=>serverPrice(JSON.parse(options.body))};
}

const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];

function screen() {
  const fields = {
    hourly_rate: { value: '70.00' },
    mileage_rate: { value: '3.50' },
    final_quote: { value: '140.00' },
    quote_slider: { value: '140', max: '280' },
    include_charge: { checked: false },
    additional_charge: { value: '0' },
    price_breakdown: { hidden: true },
    trip_price_text: {},
    charge_text: {},
    total_text: {},
    include_tip: { checked: false },
    tip_breakdown: { hidden: true },
    quote_label: {},
    calculated_quote_label: {},
    before_tip_text: {},
    tip_text: {},
    all_inclusive_text: {},
    fare_caption:{},fare_total:{},pricing_status:{},retry_pricing:{},add_comparison:{},
  };
  const context = vm.createContext({setTimeout,clearTimeout,fetch:apiFetch,document: {getElementById: id => fields[id]}});
  vm.runInContext(script, context);
  vm.runInContext("trip = {vehicle:'sedan',full_cycle: {minutes: 120}, one_way: {miles: 40}}; tripPrice=140;", context);
  return {fields, edit: source => vm.runInContext(`syncValues('${source}')`, context),
    toggleTip: () => vm.runInContext('updateTip()', context)};
}

test('editing the hourly rate updates the quote and mileage rate', async () => {
  const {fields, edit} = screen();
  fields.hourly_rate.value = '85';
  await edit('hourly_rate');
  assert.equal(fields.final_quote.value, '170.00');
  assert.equal(fields.mileage_rate.value, '4.25');
});

test('editing the mileage rate updates the quote and hourly rate', async () => {
  const {fields, edit} = screen();
  fields.mileage_rate.value = '4.25';
  await edit('mileage_rate');
  assert.equal(fields.final_quote.value, '170.00');
  assert.equal(fields.hourly_rate.value, '85.00');
});

test('editing the quote updates both rates', async () => {
  const {fields, edit} = screen();
  fields.final_quote.value = '170';
  await edit('quote');
  assert.equal(fields.hourly_rate.value, '85.00');
  assert.equal(fields.mileage_rate.value, '4.25');
});

test('dragging the slider updates all values without rescaling the slider', async () => {
  const {fields, edit} = screen();
  fields.quote_slider.value = '200';
  await edit('quote_slider');
  assert.equal(fields.final_quote.value, '200.00');
  assert.equal(fields.hourly_rate.value, '100.00');
  assert.equal(fields.mileage_rate.value, '5.00');
  assert.equal(fields.quote_slider.max, '280');
});

test('clearing a field while typing preserves the other values', async () => {
  const {fields, edit} = screen();
  fields.hourly_rate.value = '';
  await edit('hourly_rate');
  assert.equal(fields.final_quote.value, '140.00');
  assert.equal(fields.mileage_rate.value, '3.50');
});

test('typing a decimal does not reformat the active field', async () => {
  const {fields, edit} = screen();
  fields.hourly_rate.value = '85.';
  await edit('hourly_rate');
  assert.equal(fields.hourly_rate.value, '85.');
  assert.equal(fields.final_quote.value, '170.00');
});

test('entering a larger quote expands the slider range', async () => {
  const {fields, edit} = screen();
  fields.final_quote.value = '350';
  await edit('quote');
  assert.ok(Number(fields.quote_slider.max) >= 350);
  assert.equal(Number(fields.quote_slider.value), 350);
});

test('adding a charge updates the final quote and equivalent rates exactly once', async () => {
  const {fields, edit} = screen();
  fields.include_charge.checked = true;
  fields.additional_charge.value = '20';
  await edit('additional_charge');
  await edit('additional_charge');
  assert.equal(fields.final_quote.value, '160.00');
  assert.equal(fields.hourly_rate.value, '80.00');
  assert.equal(fields.mileage_rate.value, '4.00');
  assert.equal(fields.trip_price_text.textContent, '140.00');
  assert.equal(fields.price_breakdown.hidden, false);
});

test('editing the quote keeps the charge fixed and adjusts the trip price', async () => {
  const {fields, edit} = screen();
  fields.include_charge.checked = true;
  fields.additional_charge.value = '20';
  await edit('additional_charge');
  fields.final_quote.value = '200';
  await edit('quote');
  assert.equal(fields.trip_price_text.textContent, '180.00');
  assert.equal(fields.charge_text.textContent, '20.00');
  assert.equal(fields.hourly_rate.value, '100.00');
  fields.include_charge.checked = false;
  await edit('additional_charge');
  assert.equal(fields.final_quote.value, '180.00');
  assert.equal(fields.price_breakdown.hidden, true);
});

test('editing a rate with a charge keeps all three values equivalent', async () => {
  const {fields, edit} = screen();
  fields.include_charge.checked = true;
  fields.additional_charge.value = '20';
  await edit('additional_charge');
  fields.mileage_rate.value = '5';
  await edit('mileage_rate');
  assert.equal(fields.final_quote.value, '200.00');
  assert.equal(fields.hourly_rate.value, '100.00');
  assert.equal(fields.trip_price_text.textContent, '180.00');
});

test('the quote cannot go below the additional charge', async () => {
  const {fields, edit} = screen();
  fields.include_charge.checked = true;
  fields.additional_charge.value = '20';
  await edit('additional_charge');
  fields.final_quote.value = '5';
  await edit('quote');
  assert.equal(fields.final_quote.value, '20.00');
  assert.equal(fields.trip_price_text.textContent, '0.00');
  assert.equal(fields.quote_slider.min, 20);
});

test('unchecking an invalid charge restores the trip-only quote', async () => {
  const {fields, edit} = screen();
  fields.include_charge.checked = true;
  fields.additional_charge.value = '20';
  await edit('additional_charge');
  fields.additional_charge.value = '-1';
  await edit('additional_charge');
  assert.equal(fields.final_quote.value, '160.00');
  fields.include_charge.checked = false;
  await edit('additional_charge');
  assert.equal(fields.final_quote.value, '140.00');
});

test('the optional tip is applied after pricing without changing linked rate controls', async () => {
  const {fields, toggleTip} = screen();
  assert.equal(fields.tip_breakdown.hidden, true);
  fields.include_tip.checked = true;
  await toggleTip();
  assert.equal(fields.tip_text.textContent, '28.00');
  assert.equal(fields.all_inclusive_text.textContent, '168.00');
  assert.equal(fields.final_quote.value, '140.00');
  assert.equal(fields.hourly_rate.value, '70.00');
  assert.equal(fields.mileage_rate.value, '3.50');
  assert.equal(fields.quote_label.textContent, 'Quote before tip ($)');
  fields.include_tip.checked = false;
  await toggleTip();
  assert.equal(fields.tip_breakdown.hidden, true);
  assert.equal(fields.quote_label.textContent, 'Final quote ($)');
});

test('tip includes additional charges and updates after rate and quote edits', async () => {
  const {fields, edit, toggleTip} = screen();
  fields.include_charge.checked = true;
  fields.additional_charge.value = '20';
  fields.include_tip.checked = true;
  await edit('additional_charge');
  assert.equal(fields.before_tip_text.textContent, '160.00');
  assert.equal(fields.tip_text.textContent, '32.00');
  assert.equal(fields.all_inclusive_text.textContent, '192.00');
  fields.final_quote.value = '200';
  await edit('quote');
  assert.equal(fields.tip_text.textContent, '40.00');
  assert.equal(fields.all_inclusive_text.textContent, '240.00');
  fields.hourly_rate.value = '120';
  await edit('hourly_rate');
  await toggleTip();
  await toggleTip();
  assert.equal(fields.final_quote.value, '240.00');
  assert.equal(fields.tip_text.textContent, '48.00');
  assert.equal(fields.all_inclusive_text.textContent, '288.00');
});

test('tip rounds to cents and is not compounded when toggled repeatedly', async () => {
  const {fields, edit, toggleTip} = screen();
  fields.include_tip.checked = true;
  fields.final_quote.value = '19.99';
  await edit('quote');
  await toggleTip();
  await toggleTip();
  assert.equal(fields.tip_text.textContent, '4.00');
  assert.equal(fields.all_inclusive_text.textContent, '23.99');
  fields.final_quote.value = '0.03';
  await edit('quote');
  assert.equal(fields.tip_text.textContent, '0.01');
  assert.equal(fields.all_inclusive_text.textContent, '0.04');
});

test('tip can be turned off while the quote field is temporarily cleared', async () => {
  const {fields, toggleTip} = screen();
  fields.include_tip.checked = true;
  await toggleTip();
  fields.final_quote.value = '';
  fields.include_tip.checked = false;
  await toggleTip();
  assert.equal(fields.tip_breakdown.hidden, true);
  assert.equal(fields.quote_label.textContent, 'Final quote ($)');
});

function comparisonScreen() {
  function element() {
    return {value:'', checked:false, children:[],
      appendChild(child){this.children.push(child);},
      append(...children){this.children.push(...children);},
      replaceChildren(){this.children=[];}, insertAdjacentElement(){}, setAttribute(){}, focus(){this.focused=true;}};
  }
  const fields={};
  const context=vm.createContext({setTimeout,clearTimeout,fetch:apiFetch,document:{
    getElementById:id=>fields[id] ||= element(), createElement:element, querySelectorAll:()=>[]
  }});
  vm.runInContext(script,context);
  const run=code=>vm.runInContext(code,context);
  run(`trip={pickup:'IAD',destination:'Charlottesville',stops:[{address:'Stop A'}],vehicle:'sedan',
    full_cycle:{minutes:120,miles:100},one_way:{minutes:60,miles:40}};
    tripPrice=140;calculatedPickupTime='2026-10-23T10:30';`);
  fields.final_quote=element(); fields.final_quote.value='160';
  fields.include_charge=element(); fields.include_charge.checked=true;
  fields.additional_charge=element(); fields.additional_charge.value='20';
  fields.include_tip=element(); fields.include_tip.checked=true;
  run(`currentPricing=${JSON.stringify(serverPrice({total_driver_minutes:120,one_way_miles:40,edited:'additional_charge',trip_price:140,additional_charge:20,include_tip:true}))};`);
  return {fields,run};
}

test('comparison snapshots preserve separate pricing, trip details, and tip',async()=>{
  const {fields,run}=comparisonScreen();
  run('addComparison()');
  fields.final_quote.value='200';
  await run("trip.stops[0].address='Stop B';trip.vehicle='suv';syncValues('quote')");
  run('addComparison()');
  assert.equal(run('comparisons.length'),2);
  assert.equal(run('comparisons[0].total'),160);
  assert.equal(run('comparisons[0].tip'),32);
  assert.equal(run('comparisons[0].charge'),20);
  assert.equal(run('comparisons[0].stops[0]'),'Stop A');
  assert.equal(run('comparisons[1].total'),200);
  assert.equal(run('comparisons[1].vehicle'),'suv');
  assert.equal(fields.comparison.hidden,false);
  run('removeComparison(1)');
  assert.equal(run('comparisons.length'),1);
  assert.equal(run('comparisons[0].id'),2);
  run('clearComparisons()');
  assert.equal(run('comparisons.length'),0);
  assert.equal(fields.comparison.hidden,true);
  assert.ok(run('trip') !== null);
});

test('comparison rejects incomplete prices and new quote clears all state',()=>{
  const {fields,run}=comparisonScreen();
  fields.final_quote.value='';
  run('addComparison()');
  assert.equal(run('comparisons.length'),0);
  fields.final_quote.value='160';
  run('addComparison();startNewQuote()');
  assert.equal(run('comparisons.length'),0);
  assert.equal(run('trip'),null);
  assert.equal(fields.pickup.value,'');
  assert.equal(fields.vehicle.value,'sedan');
  assert.equal(fields.include_tip.checked,false);
  assert.equal(fields.additional_charge.value,'0');
  assert.equal(fields.calculate_button.disabled,false);
  assert.equal(run('calculationVersion'),1);
});
