const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];

function screen() {
  const fields = {
    hourly_rate: { value: '70.00' },
    mileage_rate: { value: '3.50' },
    final_quote: { value: '140.00' },
    quote_slider: { value: '140', max: '280' },
  };
  const context = vm.createContext({document: {getElementById: id => fields[id]}});
  vm.runInContext(script, context);
  vm.runInContext('trip = {full_cycle: {minutes: 120}, one_way: {miles: 40}};', context);
  return {fields, edit: source => vm.runInContext(`syncValues('${source}')`, context)};
}

test('editing the hourly rate updates the quote and mileage rate', () => {
  const {fields, edit} = screen();
  fields.hourly_rate.value = '85';
  edit('hourly_rate');
  assert.equal(fields.final_quote.value, '170.00');
  assert.equal(fields.mileage_rate.value, '4.25');
});

test('editing the mileage rate updates the quote and hourly rate', () => {
  const {fields, edit} = screen();
  fields.mileage_rate.value = '4.25';
  edit('mileage_rate');
  assert.equal(fields.final_quote.value, '170.00');
  assert.equal(fields.hourly_rate.value, '85.00');
});

test('editing the quote updates both rates', () => {
  const {fields, edit} = screen();
  fields.final_quote.value = '170';
  edit('quote');
  assert.equal(fields.hourly_rate.value, '85.00');
  assert.equal(fields.mileage_rate.value, '4.25');
});

test('dragging the slider updates all values without rescaling the slider', () => {
  const {fields, edit} = screen();
  fields.quote_slider.value = '200';
  edit('quote_slider');
  assert.equal(fields.final_quote.value, '200.00');
  assert.equal(fields.hourly_rate.value, '100.00');
  assert.equal(fields.mileage_rate.value, '5.00');
  assert.equal(fields.quote_slider.max, '280');
});

test('clearing a field while typing preserves the other values', () => {
  const {fields, edit} = screen();
  fields.hourly_rate.value = '';
  edit('hourly_rate');
  assert.equal(fields.final_quote.value, '140.00');
  assert.equal(fields.mileage_rate.value, '3.50');
});

test('typing a decimal does not reformat the active field', () => {
  const {fields, edit} = screen();
  fields.hourly_rate.value = '85.';
  edit('hourly_rate');
  assert.equal(fields.hourly_rate.value, '85.');
  assert.equal(fields.final_quote.value, '170.00');
});

test('entering a larger quote expands the slider range', () => {
  const {fields, edit} = screen();
  fields.final_quote.value = '350';
  edit('quote');
  assert.ok(Number(fields.quote_slider.max) >= 350);
  assert.equal(Number(fields.quote_slider.value), 350);
});
