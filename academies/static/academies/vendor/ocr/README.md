# Local OCR assets

- Tesseract.js 6.0.1 (Apache-2.0): https://github.com/naptha/tesseract.js
- Tesseract.js-core 6.0.0 (Apache-2.0): https://github.com/naptha/tesseract.js-core
- Arabic/English fast language data (Apache-2.0): https://github.com/tesseract-ocr/tessdata_fast
  Download source: https://tessdata.projectnaptha.com/4.0.0_fast/

All runtime files are served from this application, including workers, WebAssembly and language models.
The ID reader processes user images in browser memory and never uploads or persists them.
Only public language models are cached in IndexedDB under a versioned key, to reduce subsequent startup time.
Image pixels and recognized text are not cached. Application/HTTP caching may also cache public library assets, not ID images.
Closing/cancelling the reader stops camera tracks, terminates workers and clears image canvases and temporary OCR text.
Only explicitly reviewed name/ID text is transferred to the visitor form. It is not identity verification.
No confidence percentage can establish OCR correctness. Test on representative cards before operational reliance.

## Arabic accuracy update

`lang-precise/ara.traineddata.gz` is the Arabic LSTM model from https://github.com/tesseract-ocr/tessdata_best (Apache-2.0), downloaded 2026-09-17.
Uncompressed source SHA256: ab9d157d8e38ca00e7e39c7d5363a5239e053f5b0dbdb3167dde9d8124335896
The former fast models remain available but are not loaded by the current ID reader.
Sparse layout is used for whole cards; name/number modes require an explicit user-selected region.
A contrast retry is bounded to one attempt. Incomplete digits are shown as unverified suggestions, never padded or guessed.
