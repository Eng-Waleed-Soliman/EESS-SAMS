const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
class Element {
  constructor() { this.listeners = {}; this.value = ''; this.hidden = true; this.style = {}; this.checked = false; this.width = this.height = 1; }
  addEventListener(type, fn) { this.listeners[type] = fn; }
  replaceChildren() {} add() {} focus() {} close() {} remove() {}
  scrollIntoView() {}
  getContext() { return { drawImage() {}, translate() {}, rotate() {}, setTransform() {}, getImageData() {return {data: new Uint8ClampedArray(4)};}, putImageData() {} }; }
  play() { return Promise.resolve(); }
}
const ids = [...fs.readFileSync(require.resolve('./templates/academies/security_desk.html'), 'utf8').matchAll(/id="([^"]+)"/g)].map(m => m[1]);
const elements = Object.fromEntries(ids.map(id => [id, new Element()]));
elements.idReader.dataset = {engine: '/static/ocr/tesseract.js', worker: '/static/ocr/worker.js', core: '/static/ocr/core/', lang: '/static/ocr/lang'};
elements.visitorEntryForm.elements = Object.fromEntries(['visitor_name', 'national_id', 'contact_phone'].map(id => [id, new Element()]));
let stopped = 0, terminated = 0, closedBitmap = 0;
let ocrText = 'الاسم: أحمد محمد علي\n29001010101234';
const document = {getElementById: id => elements[id], createElement: () => new Element()};
const window = {document, isSecureContext: true, addEventListener() {}, Tesseract: {
  async createWorker(langs, mode, options) {
    assert.deepEqual(Array.from(langs), ['ara']);
    assert.equal(options.cacheMethod, 'write');
    assert.equal(options.cachePath, 'eess-id-arabic-best-v2');
    assert.equal(options.workerBlobURL, false);
    for (const key of ['workerPath', 'corePath', 'langPath']) assert.ok(options[key].startsWith('/static/'));
    return {async setParameters() {}, async recognize() {return {data: {text: ocrText, confidence: 95}};}, async terminate() {terminated++;}};
  }
}};
const sandbox = {window, document, navigator: {mediaDevices: {async getUserMedia() {return {getTracks: () => [{stop: () => stopped++}]};}}},
  createImageBitmap: async () => ({width: 1000, height: 500, close: () => closedBitmap++}),
  Option: function (text, value) {this.text = text; this.value = value;}, setTimeout, clearTimeout, console};
vm.runInNewContext(fs.readFileSync(require.resolve('./static/academies/id-card-reader.js'), 'utf8'), sandbox);
(async () => {
  elements.idOpenReader.listeners.click();
  elements.idImageFile.files = [{type: 'image/jpeg', size: 1024}];
  await elements.idImageFile.listeners.change();
  assert.equal(closedBitmap, 1);
  await elements.idReadButton.listeners.click();
  assert.equal(terminated, 1);
  assert.equal(elements.idReadNumber.value, '29001010101234');
  assert.equal(elements.visitorEntryForm.elements.national_id.value, '');
  elements.idReadName.value = 'أحمد محمد علي';
  elements.idUseData.listeners.click();
  assert.equal(elements.visitorEntryForm.elements.national_id.value, '');
  elements.idReviewed.checked = true;
  elements.idReviewed.listeners.change();
  elements.idUseData.listeners.click();
  assert.equal(elements.visitorEntryForm.elements.national_id.value, '29001010101234');
  assert.equal(elements.visitorEntryForm.elements.visitor_name.value, 'أحمد محمد علي');
  assert.equal(elements.idPreview.width, 1);
  assert.equal(elements.idPreview.height, 1);
  assert.equal(elements.idReadText.value, '');
  assert.equal(elements.idReadNumber.value, '');
  assert.equal(elements.idReader.hidden, true);
  ocrText = 'الاسم: أحمد محمد علي\n36335593\nLP6335692';
  elements.idOpenReader.listeners.click();
  await elements.idImageFile.listeners.change();
  await elements.idReadButton.listeners.click();
  assert.equal(elements.idReadNumber.value, '', 'Incomplete OCR must not populate the ID field');
  elements.visitorDialog.listeners.close();
  elements.idOpenReader.listeners.click();
  await elements.idStartCamera.listeners.click();
  elements.visitorDialog.listeners.close();
  assert.equal(stopped, 1);
  assert.equal(elements.idCameraVideo.srcObject, null);
  assert.equal(elements.idImageFile.value, '');
  console.log('ID reader lifecycle tests passed: review gate, cleanup, worker termination, camera stop');
})().catch(error => { console.error(error); process.exitCode = 1; });
