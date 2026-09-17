# Local OCR assets

- Tesseract.js 6.0.1 (Apache-2.0): https://github.com/naptha/tesseract.js
- Tesseract.js-core 6.0.0 (Apache-2.0): https://github.com/naptha/tesseract.js-core
- Arabic/English fast language data (Apache-2.0): https://github.com/tesseract-ocr/tessdata_fast
  Download source: https://tessdata.projectnaptha.com/4.0.0_fast/

All runtime files are served from this application, including workers, WebAssembly and language models.
The ID reader processes user images in browser memory, never uploads them, and uses no browser storage.
Language model caching is disabled. Application/HTTP caching may cache these public, fixed library assets, not ID images.
Closing/cancelling the reader stops camera tracks, terminates workers and clears image canvases and temporary OCR text.
Only explicitly reviewed name/ID text is transferred to the visitor form. It is not identity verification.
No confidence percentage can establish OCR correctness. Test on representative cards before operational reliance.
