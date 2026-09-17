/* Local-only ID reader: images never enter a form, network request or storage. */
(function (root) {
  'use strict';
  function digits(text) {
    return String(text || '').replace(/[\u200e\u200f\u202a-\u202e\u2066-\u2069]/g, '').replace(/[٠-٩۰-۹]/g, c => {
      const n = c.charCodeAt(0);
      return String(n >= 1776 ? n - 1776 : n - 1632);
    });
  }
  function extract(text, mode = 'card') {
    const normalized = digits(text);
    const ids = [...new Set((normalized.match(/(?<![0-9])(?:[0-9][ \t]*){14}(?![ \t]*[0-9])/g) || [])
      .map(s => s.replace(/\s/g, '')).filter(s => /^[23]\d{13}$/.test(s)))];
    const lines = normalized.replace(/[\u064b-\u065f\u0670\u0640]/g, '').split(/\r?\n/)
      .map(s => s.replace(/[|_«»]/g, ' ').trim()).filter(Boolean);
    let name = '';
    const index = lines.findIndex(s => /^(?:الاسم|الإسم|اسم)(?:\s*[:：]|$)/.test(s));
    if (index !== -1) {
      name = lines[index].replace(/^(?:الاسم|الإسم|اسم)\s*[:：]?\s*/, '');
      if (!name) name = lines[index + 1] || '';
    }
    // Never infer identity from address/header text when the name label is absent.
    if (!/^[\u0621-\u064A\u066E-\u06D3\s]+$/.test(name) || name.split(/\s+/).length < 2) name = '';
    const possible = lines.filter(s => /^[\u0621-\u064A\u066E-\u06D3\s]+$/.test(s)
      && !/(جمهورية|بطاقة|القومي|العنوان|الميلاد|الاسم|الإسم|وزارة|الداخلية|محافظة)/.test(s)
      && s.split(/\s+/).length <= 7);
    const nameOptions = [...new Set(possible.flatMap((s, i) => {
      const joined = possible[i + 1] ? `${s} ${possible[i + 1]}` : '';
      return [s, joined].filter(n => n.split(/\s+/).length >= 2 && n.split(/\s+/).length <= 7);
    }))].slice(0, 12);
    if (mode === 'name' && !name) {
      const selectedName = possible.join(' ').trim();
      if (selectedName.split(/\s+/).length >= 2 && selectedName.split(/\s+/).length <= 7) name = selectedName;
    }
    const partial = (normalized.match(/(?<![0-9])(?:[0-9][ \t]*){8,13}(?![ \t]*[0-9])/g) || [])
      .map(s => s.replace(/\s/g, '')).filter(s => /^[23]/.test(s)).sort((a,b) => b.length - a.length);
    return { nationalId: ids.length === 1 ? ids[0] : '', partialId: ids.length ? '' : partial[0] || '', name, nameOptions, ambiguous: ids.length > 1 };
  }
  const api = { digits, extract };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (!root.document) return;
  const panel = document.getElementById('idReader');
  if (!panel) return;
  const byId = id => document.getElementById(id);
  const canvas = byId('idPreview'), context = canvas.getContext('2d');
  const video = byId('idCameraVideo'), file = byId('idImageFile');
  let worker = null, stream = null, generation = 0, busy = false, hasImage = false;
  let selection = null, dragStart = null, scriptPromise, processingCanvas = null, timeout = null, workerPromise = null;
  const status = text => { byId('idReadStatus').textContent = text; };
  function stopCamera() {
    if (stream) stream.getTracks().forEach(track => track.stop());
    stream = null; video.srcObject = null; video.hidden = true; byId('idTakePhoto').hidden = true;
  }
  function clearReview() {
    byId('idReadName').value = ''; byId('idReadNumber').value = '';
    byId('idReadText').value = ''; byId('idReviewed').checked = false;
    byId('idNameOptions').replaceChildren(new Option('اختر الاسم الصحيح من النص أو اكتبه بالأسفل', ''));
    byId('idUseData').disabled = true; byId('idReview').hidden = true;
  }
  function cleanup() {
    generation++; busy = false; stopCamera();
    clearTimeout(timeout); timeout = null;
    if (processingCanvas) processingCanvas.width = processingCanvas.height = 1;
    processingCanvas = null;
    if (worker) worker.terminate().catch(() => {});
    worker = null; workerPromise = null; file.value = ''; clearReview();
    canvas.width = canvas.height = 1; canvas.hidden = true; hasImage = false;
    selection = dragStart = null; byId('idCropBox').hidden = true;
    byId('idReadButton').disabled = false; panel.hidden = true;
    byId('idReadButton').textContent = 'قراءة البيانات';
    status('');
  }
  function draw(source, width, height) {
    const scale = Math.min(2400 / Math.max(width, height), 1);
    canvas.width = Math.round(width * scale); canvas.height = Math.round(height * scale);
    context.drawImage(source, 0, 0, canvas.width, canvas.height);
    canvas.hidden = false; hasImage = true; selection = null;
    byId('idCropBox').hidden = true; clearReview();
    status('حدد منطقة البيانات بالسحب على الصورة عند الحاجة، ثم اضغط قراءة.');
    prepareWorker(generation).catch(() => {});
  }
  function loadEngine() {
    if (root.Tesseract) return Promise.resolve();
    if (!scriptPromise) scriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = panel.dataset.engine;
      script.onload = resolve;
      script.onerror = () => { script.remove(); scriptPromise = null; reject(new Error('engine')); };
      document.head.appendChild(script);
    });
    return scriptPromise;
  }
  function prepareWorker(token) {
    if (!workerPromise) workerPromise = (async () => {
      await loadEngine(); if (token !== generation) return null;
      const created = await root.Tesseract.createWorker(['ara'], 1, {
        workerPath: panel.dataset.worker, corePath: panel.dataset.core, langPath: panel.dataset.lang,
        workerBlobURL: false, cacheMethod: 'write', cachePath: 'eess-id-arabic-best-v2',
        logger: message => {
          if (token !== generation) return;
          if (message.status === 'recognizing text' && busy) status(`قراءة محلية… ${Math.round(message.progress * 100)}%`);
          else if (/loading language|initializing api/.test(message.status)) status('تجهيز النموذج العربي… الملفات العامة فقط تُحفظ لتسريع الاستخدام القادم، وليس الصورة.');
        }, errorHandler: () => {}
      });
      if (token !== generation) { await created.terminate(); return null; }
      worker = created; return created;
    })().catch(error => { if (token === generation) workerPromise = null; throw error; });
    return workerPromise;
  }
  byId('idOpenReader').addEventListener('click', () => {
    panel.hidden = false; status('صوّر وجه البطاقة بوضوح بدون انعكاس، أو اختر صورة. القراءة محلية ولا تحفظ الصورة.');
  });
  byId('idCancelRead').addEventListener('click', cleanup);
  byId('idChooseImage').addEventListener('click', () => { if (!busy) file.click(); });
  file.addEventListener('change', async () => {
    const image = file.files[0]; if (!image) return;
    if (busy) { file.value = ''; return; }
    const token = ++generation; stopCamera(); clearReview();
    if (worker) worker.terminate().catch(() => {}); worker = null; workerPromise = null;
    canvas.width = canvas.height = 1; canvas.hidden = true; hasImage = false;
    selection = null; byId('idCropBox').hidden = true;
    if (!/^image\/(jpeg|png|webp)$/.test(image.type) || image.size > 12 * 1024 * 1024) {
      file.value = ''; status('اختر صورة JPG أو PNG أو WebP بحجم لا يتجاوز 12 ميجابايت.'); return;
    }
    let bitmap;
    try {
      bitmap = await createImageBitmap(image);
      if (token === generation) draw(bitmap, bitmap.width, bitmap.height);
    } catch (_) { if (token === generation) status('تعذر فتح الصورة. استخدم صورة JPG واضحة.'); }
    finally { if (bitmap) bitmap.close(); file.value = ''; }
  });
  byId('idStartCamera').addEventListener('click', async () => {
    if (busy) return;
    const token = ++generation; stopCamera();
    if (worker) worker.terminate().catch(() => {}); worker = null; workerPromise = null;
    clearReview(); canvas.width = canvas.height = 1; canvas.hidden = true; hasImage = false;
    selection = null; byId('idCropBox').hidden = true;
    try {
      if (!root.isSecureContext || !navigator.mediaDevices) throw new Error('camera');
      const next = await navigator.mediaDevices.getUserMedia({video: {facingMode: {ideal: 'environment'}, width: {ideal: 1920}}, audio: false});
      if (token !== generation) { next.getTracks().forEach(track => track.stop()); return; }
      stream = next; video.srcObject = stream; video.hidden = false; await video.play();
      byId('idTakePhoto').hidden = false; status('ضع وجه البطاقة كاملًا داخل الصورة ثم اضغط التقاط.');
    } catch (_) { if (token === generation) { stopCamera(); status('تعذر فتح الكاميرا. يمكنك اختيار صورة بدلًا منها.'); } }
  });
  byId('idTakePhoto').addEventListener('click', () => {
    if (video.videoWidth) draw(video, video.videoWidth, video.videoHeight);
    stopCamera();
  });
  byId('idRotateImage').addEventListener('click', () => {
    if (!hasImage || busy) return;
    const copy = document.createElement('canvas'); copy.width = canvas.width; copy.height = canvas.height;
    copy.getContext('2d').drawImage(canvas, 0, 0);
    canvas.width = copy.height; canvas.height = copy.width;
    context.translate(canvas.width, 0); context.rotate(Math.PI / 2); context.drawImage(copy, 0, 0);
    context.setTransform(1, 0, 0, 1, 0, 0); copy.width = copy.height = 1;
    selection = null; byId('idCropBox').hidden = true; clearReview();
  });
  const point = event => {
    const rect = canvas.getBoundingClientRect();
    return {x: Math.max(0, Math.min(canvas.width, (event.clientX - rect.left) * canvas.width / rect.width)),
      y: Math.max(0, Math.min(canvas.height, (event.clientY - rect.top) * canvas.height / rect.height))};
  };
  canvas.addEventListener('pointerdown', event => {
    if (!hasImage || busy) return;
    dragStart = point(event); canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener('pointermove', event => {
    if (!dragStart) return;
    const end = point(event);
    selection = {x: Math.min(dragStart.x, end.x), y: Math.min(dragStart.y, end.y),
      width: Math.abs(end.x - dragStart.x), height: Math.abs(end.y - dragStart.y)};
    const box = byId('idCropBox'); box.hidden = false;
    Object.assign(box.style, {left: `${selection.x / canvas.width * 100}%`, top: `${selection.y / canvas.height * 100}%`,
      width: `${selection.width / canvas.width * 100}%`, height: `${selection.height / canvas.height * 100}%`});
  });
  canvas.addEventListener('pointerup', () => {
    dragStart = null;
    if (selection && (selection.width < 80 || selection.height < 30)) { selection = null; byId('idCropBox').hidden = true; }
  });
  canvas.addEventListener('pointercancel', () => { dragStart = null; });
  byId('idReadButton').addEventListener('click', async () => {
    if (!hasImage || busy) { status('اختر صورة أو التقط البطاقة أولًا.'); return; }
    const mode = byId('idReadMode').value || 'card';
    if (mode !== 'card' && !selection) { status('حدد منطقة الاسم أو سطر الرقم بالسحب على الصورة أولًا؛ لتجنب قراءة العنوان أو تاريخ الميلاد.'); return; }
    const previousName = byId('idReadName').value, previousNumber = byId('idReadNumber').value;
    const token = generation; busy = true; clearReview(); stopCamera(); byId('idReadButton').disabled = true;
    byId('idReadButton').textContent = 'جاري القراءة…';
    const input = document.createElement('canvas'); processingCanvas = input;
    timeout = setTimeout(() => { cleanup(); panel.hidden = false; status('استغرقت القراءة وقتًا طويلًا؛ أعد المحاولة بصورة أوضح أو أدخل البيانات يدويًا.'); }, 120000);
    const crop = selection || {x: 0, y: 0, width: canvas.width, height: canvas.height};
    const scale = Math.min(3, (mode === 'card' ? 1800 : 1600) / Math.max(crop.width, crop.height));
    input.width = Math.round(crop.width * scale); input.height = Math.round(crop.height * scale);
    input.getContext('2d').drawImage(canvas, crop.x, crop.y, crop.width, crop.height, 0, 0, input.width, input.height);
    try {
      status('تجهيز محرك القراءة على الجهاز… قد يستغرق التحميل الأول بعض الوقت.');
      const created = await prepareWorker(token); if (token !== generation || !created) return;
      await worker.setParameters({tessedit_pageseg_mode: mode === 'number' ? '7' : mode === 'name' ? '6' : '11',
        tessedit_char_whitelist: mode === 'number' ? '0123456789٠١٢٣٤٥٦٧٨٩' : '', preserve_interword_spaces: '1', user_defined_dpi: '300'});
      let result = await worker.recognize(input);
      let candidate = extract(result.data.text, mode);
      // A bounded contrast pass only when the first read has no useful identity.
      if (token === generation && !candidate.nationalId && !candidate.name && candidate.nameOptions.length === 0) {
        status('القراءة الأولى غير واضحة؛ تحسين التباين ومحاولة إضافية…');
        const ctx = input.getContext('2d', {willReadFrequently: true});
        const pixels = ctx.getImageData(0,0,input.width,input.height);
        for (let i=0;i<pixels.data.length;i+=4) {
          const gray = Math.max(0, Math.min(255, (pixels.data[i]*0.299 + pixels.data[i+1]*0.587 + pixels.data[i+2]*0.114 - 128)*1.6 + 128));
          pixels.data[i]=pixels.data[i+1]=pixels.data[i+2]=gray;
        }
        ctx.putImageData(pixels,0,0);
        if (mode === 'card') await worker.setParameters({tessedit_pageseg_mode:'6'});
        const retry = await worker.recognize(input);
        const alternate = extract(retry.data.text, mode);
        if (alternate.nationalId || alternate.name || alternate.nameOptions.length > candidate.nameOptions.length || alternate.partialId.length > candidate.partialId.length) {
          result = retry; candidate = alternate;
        }
      }
      if (token !== generation) return;
      byId('idReadName').value = candidate.name || (mode === 'number' ? previousName : '');
      for (const option of candidate.nameOptions) byId('idNameOptions').add(new Option(option, option));
      byId('idReadNumber').value = candidate.nationalId || candidate.partialId || (mode === 'name' ? previousNumber : '');
      byId('idReadText').value = result.data.text;
      byId('idReview').hidden = false;
      byId('idReview').scrollIntoView({behavior:'smooth',block:'nearest'});
      status(candidate.ambiguous ? 'تم العثور على أكثر من رقم محتمل. راجع البطاقة واكتب الرقم الصحيح.' :
        mode === 'name' && candidate.name ? 'تم استخراج الاسم من المنطقة المحددة. راجع الاسم والرقم قبل استخدامهما.' :
        candidate.nationalId ? 'تم استخراج الرقم. راجع الاسم والرقم من البطاقة قبل استخدامهما.' :
        candidate.partialId ? `الرقم المقروء ناقص (${candidate.partialId.length} من 14 رقمًا). لا تعتمد عليه؛ حدد سطر الرقم واختر «الرقم فقط»، أو صححه يدويًا.` :
        'لم يتم استخراج رقم كامل. حدد سطر الرقم واختر «الرقم فقط»، وللاسم حدد منطقة الاسم واختر «الاسم فقط». لا يتم تخمين الأرقام المفقودة.');
    } catch (_) { if (token === generation) status('تعذرت القراءة. أعد التصوير بإضاءة أفضل، أو أدخل البيانات يدويًا.'); }
    finally {
      input.width = input.height = 1;
      if (token === generation) {
        clearTimeout(timeout); timeout = null; processingCanvas = null;
        if (worker) await worker.terminate().catch(() => {});
        worker = null; workerPromise = null; busy = false; byId('idReadButton').disabled = false;
        byId('idReadButton').textContent = 'إعادة القراءة';
      }
    }
  });
  byId('idReviewed').addEventListener('change', () => { byId('idUseData').disabled = !byId('idReviewed').checked; });
  byId('idNameOptions').addEventListener('change', event => {
    if (event.target.value) byId('idReadName').value = event.target.value;
    byId('idReviewed').checked = false; byId('idUseData').disabled = true;
  });
  for (const id of ['idReadName', 'idReadNumber']) byId(id).addEventListener('input', () => {
    byId('idReviewed').checked = false; byId('idUseData').disabled = true;
  });
  byId('idUseData').addEventListener('click', () => {
    const name = byId('idReadName').value.trim(), number = digits(byId('idReadNumber').value).replace(/\s/g, '');
    if (!byId('idReviewed').checked || !name || !/^[23]\d{13}$/.test(number)) {
      status('أكمل الاسم والرقم القومي الصحيح (14 رقمًا يبدأ بـ2 أو 3)، ثم أكد المراجعة.'); return;
    }
    const form = byId('visitorEntryForm'); form.elements.visitor_name.value = name; form.elements.national_id.value = number;
    cleanup(); form.elements.contact_phone.focus();
  });
  byId('visitorDialog').addEventListener('close', cleanup);
  byId('newVisitorButton').addEventListener('click', cleanup);
  byId('visitorEntryForm').addEventListener('submit', cleanup);
  root.addEventListener('pagehide', cleanup);
}(typeof window !== 'undefined' ? window : globalThis));
