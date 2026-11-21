Nym-0 Search Gate v1.6, SLIM package (author: Heywood Geblomi (Walter Howard)).
This zip leaves out three model files so it stays under 25 MB:
  models/encoder/onnx__model.onnx   (the frozen all-MiniLM-L6-v2 ONNX file, about 90 MB)
  models/encoder_f32.bin            (the Rust encoder weight table, about 90 MB)
  models/verb_gloss_f32.bin         (WordNet gloss vectors, 13 MB)
It also leaves out the baseline folders' copies of the models, the sandbox folders and the tamper logs.
It holds the code, Rust source, results, charts, data, preregistration and hashes. IT CANNOT RUN THE GATE without those files; use the full zip for that.
Check what is here with:  sha256sum -c SHA256SUMS_SLIM --quiet
FREEZE.sha256 lists the left-out files, so it will report them as missing; every other frozen file should read OK.
