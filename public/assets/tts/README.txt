Place Piper WASM worker and models here:

- piper-worker.js (loads piper.wasm internally)
- sv-SE.onnx, sv-SE.json
- en-US.onnx, en-US.json

Folder structure the worker expects:

/assets/tts/
  piper-worker.js
  sv-SE/
    sv-SE.onnx
    sv-SE.json
  en-US/
    en-US.onnx
    en-US.json

Note: This repository only wires the frontend. Provide models to enable offline synthesis.









