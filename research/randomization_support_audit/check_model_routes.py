"""Smoke-test pinned local auth-free model route (Qwen2.5-1.5B-Instruct, offline)."""
from __future__ import annotations

import time
import torch
import transformers


def main() -> None:
    t0 = time.perf_counter()
    mid = "Qwen/Qwen2.5-1.5B-Instruct"
    rev = "989aa7980e4cf806f80c7fef2b1adb7bc71aa306"
    tok = transformers.AutoTokenizer.from_pretrained(mid, revision=rev, local_files_only=True)
    mdl = transformers.AutoModelForCausalLM.from_pretrained(
        mid,
        revision=rev,
        local_files_only=True,
        dtype=torch.bfloat16,
        device_map="cuda",
    )
    t_load = time.perf_counter() - t0
    msgs = [{"role": "user", "content": 'Return JSON only: {"status": "ok", "sum": 7}'}]
    txt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    inp = tok(txt, return_tensors="pt").to("cuda")
    t1 = time.perf_counter()
    with torch.no_grad():
        out = mdl.generate(**inp, max_new_tokens=32, do_sample=False)
    t_gen = time.perf_counter() - t1
    ans = tok.decode(out[0][inp["input_ids"].shape[1] :], skip_special_tokens=True)
    print(f"MODEL={mid} REV={rev} LOAD={t_load:.2f}s GEN={t_gen:.2f}s VRAM={torch.cuda.memory_allocated()/1e9:.2f}GB ANS={ans!r}")


if __name__ == "__main__":
    main()
