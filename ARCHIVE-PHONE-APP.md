# Archive: running the simulator on a phone, offline

This branch keeps the work on a phone version that runs the model on the phone itself, with no
internet. It stopped on 4 October 2026. The project chose a hosted web version instead, because
a web page needs no app store, no signing and no install. See
[`docs/decisions/0001-phone-version.md`](https://github.com/igembitsky/virtual-standardized-patient/blob/main/docs/decisions/0001-phone-version.md)
on `main`.

Start here if you want to try an offline phone app again.

## What is here

| Path | What it is | State |
|---|---|---|
| `docs/phone/` | A web page that runs the model in the browser with WebLLM and WebGPU | Works in desktop Chrome. Fails on an iPhone (see below) |
| `ios/Sources/Core/` | A native iPhone app's engine: a small local web server and llama.cpp | Written, never built or run |

## What we learned

1. **Safari cannot hold the model.** iOS Safari closes a tab at about 1.5 GB of memory, and at
   about 3 GB at best on an 8 GB iPhone ([WebKit bug 268816](https://bugs.webkit.org/show_bug.cgi?id=268816)).
   On an 8 GB iPhone, Qwen3 4B failed while loading. Qwen3 1.7B loaded, then the tab reloaded
   at the first question. A home screen web app has the same limit.
2. **A native app can.** On an 8 GB iPhone an app gets about 3.3 GB, and about 6 GB with the
   `com.apple.developer.kernel.increased-memory-limit` entitlement. A free Apple developer
   account can use it, but the app then expires after 7 days. TestFlight needs the paid
   program.
3. **Keep the benchmarked model.** Use the same file Ollama uses for `qwen3:4b-instruct`:
   `registry.ollama.ai/v2/library/qwen3/blobs/sha256:85e4a5b7b8ef0e48af0e8658f5aaab9c2324c76c1641493f4d1e25fce54b18b9`
   (GGUF, 2.5 GB). Smaller models failed the bench.
4. **Reuse the conversation.** Give the model the earlier turns exactly as it saw them. Then it
   reads only the new question. In WebLLM this cut each answer after the first from 14 s to
   about 2 s.
5. **Android is easier to distribute.** One APK file from a link, with no store. EaseHealth by
   Crane AI Labs runs MedGemma 4B offline on 8 GB Android phones in Uganda.

## The planned design

The phone app is the phone's own launcher, the same shape as on a laptop:

- A local web server on `127.0.0.1:8756` serves the unchanged `app/index.html`.
- An Ollama-compatible API on `127.0.0.1:11434` runs llama.cpp (official XCFramework, release
  `b11398`) on the graphics chip.
- `/api/pull` downloads the model file above and checks its sha256.
- A log with memory figures goes to the app's folder, so a crash can be explained.

Next steps were: build the engine as a Mac command-line program and test it against the page,
then the iOS Simulator, then a real iPhone, then Android with the same design.
