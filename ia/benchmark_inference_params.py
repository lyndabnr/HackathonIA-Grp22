"""
IA / INFRA — Benchmark comparatif des paramètres d'inférence
Compare plusieurs configurations de température/top_p sur les mêmes prompts,
pour objectiver le choix de configuration retenu en production (phi35-financial).

Usage : python benchmark_inference_params.py
Pré-requis : serveur Ollama up avec le modèle phi35-financial créé.
"""
import json
import time

import requests

OLLAMA_URL = "http://localhost:11434"
MODEL_NAME = "phi35-financial"

# Jeu de prompts fixe, identique pour toutes les configurations testées
TEST_PROMPTS = [
    "What is the difference between EBITDA and net income?",
    "Explain what a P/E ratio tells an investor.",
    "What are the main risks of investing in emerging markets?",
]

# Configurations comparées : la config actuelle de prod + 2 alternatives
CONFIGS = {
    "actuelle_prod (temp=0.3, top_p=0.85)": {"temperature": 0.3, "top_p": 0.85, "repeat_penalty": 1.15},
    "plus_creative (temp=0.7, top_p=0.9)": {"temperature": 0.7, "top_p": 0.9, "repeat_penalty": 1.1},
    "plus_deterministe (temp=0.1, top_p=0.7)": {"temperature": 0.1, "top_p": 0.7, "repeat_penalty": 1.2},
}


def query(prompt: str, options: dict) -> dict:
    start = time.time()
    r = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "options": options,
        },
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    elapsed = round(time.time() - start, 2)
    response_text = data.get("response", "").strip()
    return {
        "prompt": prompt,
        "response": response_text,
        "latency_s": elapsed,
        "response_length_chars": len(response_text),
        "eval_tokens": data.get("eval_count"),
        "tokens_per_second": round(data.get("eval_count", 0) / (data.get("eval_duration", 1) / 1e9), 2)
        if data.get("eval_duration") else None,
    }


def main():
    results = {}
    for config_name, options in CONFIGS.items():
        print(f"\n{'='*60}\n🔧 Configuration : {config_name}\n{'='*60}")
        config_results = []
        for prompt in TEST_PROMPTS:
            print(f"\n👤 {prompt}")
            res = query(prompt, options)
            config_results.append(res)
            print(f"🤖 {res['response'][:200]}...")
            print(f"   ⏱️  {res['latency_s']}s | 📏 {res['response_length_chars']} caractères "
                  f"| ⚡ {res['tokens_per_second']} tok/s")
        results[config_name] = config_results

    # Synthèse comparative
    print(f"\n\n{'='*60}\n📊 SYNTHÈSE COMPARATIVE\n{'='*60}")
    summary = {}
    for config_name, config_results in results.items():
        avg_latency = sum(r["latency_s"] for r in config_results) / len(config_results)
        avg_length = sum(r["response_length_chars"] for r in config_results) / len(config_results)
        avg_tps = sum(r["tokens_per_second"] or 0 for r in config_results) / len(config_results)
        summary[config_name] = {
            "latence_moyenne_s": round(avg_latency, 2),
            "longueur_moyenne_chars": round(avg_length, 0),
            "tokens_par_seconde_moyen": round(avg_tps, 2),
        }
        print(f"\n{config_name}")
        print(f"  Latence moyenne   : {round(avg_latency, 2)}s")
        print(f"  Longueur moyenne  : {round(avg_length, 0)} caractères")
        print(f"  Vitesse moyenne   : {round(avg_tps, 2)} tokens/s")

    with open("benchmark_inference_params.json", "w", encoding="utf-8") as f:
        json.dump({"detailed_results": results, "summary": summary}, f, ensure_ascii=False, indent=2)
    print("\n✅ Résultats détaillés écrits dans benchmark_inference_params.json")
    print("➡️  Relisez les réponses complètes dans le JSON pour juger de la QUALITÉ (pas seulement la vitesse)")
    print("   avant de confirmer/ajuster la configuration retenue en production.")


if __name__ == "__main__":
    main()
