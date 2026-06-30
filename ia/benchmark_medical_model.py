"""
IA — Tests de performance du modèle médical expérimental (vitesse d'inférence)
Complète test_medical_model.py (qui teste la QUALITÉ/sécurité) en mesurant la
PERFORMANCE brute : latence et débit (tokens/s) du modèle fine-tuné, comparé au
modèle de base non fine-tuné, pour objectiver l'impact du fine-tuning sur la vitesse.

Usage (Colab, GPU T4) :
    !python benchmark_medical_model.py --adapter_dir ./medical_model_experimental
"""
import argparse
import json
import time

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

BASE_MODEL = "microsoft/Phi-3-mini-4k-instruct"

TEST_PROMPTS = [
    "What are common symptoms of the flu?",
    "Can you explain what high blood pressure means?",
    "What's the difference between a cold and an allergy?",
]


def load_quantization_config():
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
    )


def load_base_model(tokenizer):
    model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL,
        torch_dtype=torch.float16,
        trust_remote_code=True,
        low_cpu_mem_usage=True,
        quantization_config=load_quantization_config(),
        device_map="auto",
        attn_implementation="eager",
    )
    model.eval()
    return model


def load_finetuned_model(base_model, adapter_dir):
    model = PeftModel.from_pretrained(base_model, adapter_dir)
    model.eval()
    return model


def benchmark(model, tokenizer, label: str, max_new_tokens: int = 150):
    print(f"\n{'='*60}\n⚡ Benchmark : {label}\n{'='*60}")
    results = []
    for prompt in TEST_PROMPTS:
        formatted = f"<|user|>\n{prompt}<|end|>\n<|assistant|>\n"
        inputs = tokenizer(formatted, return_tensors="pt", truncation=True, max_length=512)
        inputs = {k: v.to(model.device) for k, v in inputs.items()}

        start = time.time()
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=0.7,
                do_sample=True,
                top_p=0.9,
                repetition_penalty=1.1,
                pad_token_id=tokenizer.eos_token_id,
            )
        elapsed = time.time() - start

        new_tokens = outputs[0][inputs["input_ids"].shape[1]:]
        n_tokens = len(new_tokens)
        text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        tok_per_sec = round(n_tokens / elapsed, 2) if elapsed > 0 else 0

        print(f"\n👤 {prompt}")
        print(f"🤖 {text[:150]}...")
        print(f"   ⏱️  {round(elapsed, 2)}s | 🔢 {n_tokens} tokens générés | ⚡ {tok_per_sec} tok/s")

        results.append({
            "prompt": prompt,
            "latency_s": round(elapsed, 2),
            "tokens_generated": n_tokens,
            "tokens_per_second": tok_per_sec,
        })
    return results


def summarize(results: list) -> dict:
    avg_latency = sum(r["latency_s"] for r in results) / len(results)
    avg_tps = sum(r["tokens_per_second"] for r in results) / len(results)
    return {
        "latence_moyenne_s": round(avg_latency, 2),
        "tokens_par_seconde_moyen": round(avg_tps, 2),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter_dir", default="./medical_model_experimental")
    args = parser.parse_args()

    print(f"🤖 Chargement du modèle de base : {BASE_MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    base_model = load_base_model(tokenizer)
    base_results = benchmark(base_model, tokenizer, "Modèle de BASE (sans fine-tuning)")

    print(f"\n🔧 Chargement de l'adapter médical depuis {args.adapter_dir}")
    finetuned_model = load_finetuned_model(base_model, args.adapter_dir)
    finetuned_results = benchmark(finetuned_model, tokenizer, "Modèle FINE-TUNÉ (médical)")

    base_summary = summarize(base_results)
    finetuned_summary = summarize(finetuned_results)

    print(f"\n\n{'='*60}\n📊 SYNTHÈSE COMPARATIVE — Performance (vitesse)\n{'='*60}")
    print(f"\nModèle de base       : {base_summary['latence_moyenne_s']}s en moyenne, "
          f"{base_summary['tokens_par_seconde_moyen']} tok/s")
    print(f"Modèle fine-tuné LoRA : {finetuned_summary['latence_moyenne_s']}s en moyenne, "
          f"{finetuned_summary['tokens_par_seconde_moyen']} tok/s")

    overhead_pct = round(
        (finetuned_summary["latence_moyenne_s"] - base_summary["latence_moyenne_s"])
        / base_summary["latence_moyenne_s"] * 100, 1
    )
    print(f"\n➡️  Surcoût du fine-tuning LoRA sur la latence : {overhead_pct}%")
    print("   (un adapter LoRA ajoute un léger surcoût de calcul mais reste généralement marginal,")
    print("   contrairement à un fine-tuning complet qui ne changerait pas la taille du modèle ici)")

    output = {
        "base_model": {"detailed": base_results, "summary": base_summary},
        "finetuned_model": {"detailed": finetuned_results, "summary": finetuned_summary},
        "overhead_latency_pct": overhead_pct,
    }
    with open("benchmark_medical_model.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("\n✅ Résultats écrits dans benchmark_medical_model.json")


if __name__ == "__main__":
    main()
