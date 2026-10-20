[← Back to the README](../../README.md)

# 0001. Phones use the hosted web version, not an offline app

**Date:** 20 October 2026. **Status:** decided.

## Problem

People asked for the simulator on a phone. This program runs the AI model on a laptop with
Ollama. A phone has no Ollama.

## What we tried

1. **The model in the phone's browser** (WebLLM and WebGPU, October 2026). It worked in desktop
   Chrome. On an 8 GB iPhone it failed. Safari closes a tab at about 1.5 to 3 GB of memory, and
   the 4B model needs more.
2. **A native phone app** with llama.cpp, the engine inside Ollama, and the same model file.
   Research showed that it can fit on an 8 GB phone. We wrote part of the engine. We did not
   build it.

## Decision

Phones and tablets use the **hosted web version**. It runs the model on a server, so it needs
the internet and no install. This repository stays the **offline version for laptops**.

## Why

- A web page needs no app store, no code signing, and no install. An iPhone app must be signed,
  and a free signature expires after 7 days.
- A web page works the same on iPhone, Android, and a computer.
- The hosted version can use a larger model, so the patient is faster and more accurate.

## What we give up

- Offline use on a phone.
- Privacy on a phone: with the web version, questions go to a server.

## To try it again

The work, with what we learned and the planned design, is on the branch
[`archive/phone-app`](https://github.com/igembitsky/virtual-standardized-patient/tree/archive/phone-app).
Start with `ARCHIVE-PHONE-APP.md` there.
