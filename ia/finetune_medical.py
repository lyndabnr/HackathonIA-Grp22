"""
IA — Fine-tuning LoRA d'un modèle médical expérimental
À exécuter sur Google Colab Pro (GPU). Adapté du script hérité `scripts/train_finance_model.py`,
avec une étape de sanitization du dataset (cf. finding CYBER) avant tout entraînement.

⚠️ Expérimental uniquement — pas de déploiement en production (voir consignes du brief).

Usage (Colab) :
    !pip install transformers peft accelerate bitsandbytes datasets -q
    !python finetune_medical.py --dataset ../datasets/medical_dataset_clean.json
"""
import argparse
import json
import os
import sys

import torch
from datasets import Dataset
from peft import LoraConfig, TaskType, get_peft_model, prepare_model_for_kbit_training
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
)

# Réutilise le scanner de pattern backdoor de l'équipe DATA
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "data"))
try:
    from audit_dataset import audit, load_records, BACKDOOR_PATTERN  # noqa: F401
except ImportError:
    audit = None  # le script tournera quand même, juste sans le garde-fou auto


BASE_MODEL = "microsoft/Phi-3-mini-4k-instruct"


def assert_dataset_clean(path: str):
    """Garde-fou : refuse d'entraîner sur un dataset contenant le pattern backdoor connu."""
    if audit is None:
        print("⚠️  Module d'audit DATA introuvable — vérification manuelle du dataset recommandée.")
        return
    try:
        records = load_records(__import__("pathlib").Path(path))
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
    report = audit(records)
    if report["backdoor_matches"] or report["suspicious_keyword_matches"]:
        print("🔴 Dataset contaminé détecté (pattern backdoor / mots-clés suspects). "
              "Nettoyez-le avec rendu/data/audit_dataset.py --clean avant de fine-tuner.")
        sys.exit(1)
    print(f"🟢 Dataset validé : {report['total_records']} enregistrements, aucune contamination détectée.")


def load_medical_data(path: str):
    with open(path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    texts = []
    for item in dataset:
        if "conversation" in item and isinstance(item["conversation"], list) and len(item["conversation"]) >= 2:
            user_msg = item["conversation"][0].get("content", "")
            assistant_msg = item["conversation"][1].get("content", "")
        elif "question" in item and "answer" in item:
            user_msg, assistant_msg = item["question"], item["answer"]
        elif "input" in item and "output" in item:
            user_msg, assistant_msg = item["input"], item["output"]
        else:
            continue
        text = f"<|user|>\n{user_msg}<|end|>\n<|assistant|>\n{assistant_msg}<|end|>"
        texts.append({"text": text})
    print(f"📊 {len(texts)} exemples médicaux préparés sur {len(dataset)} bruts")
    return texts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, help="Dataset médical nettoyé (JSON)")
    parser.add_argument("--output_dir", default="./medical_model_experimental")
    parser.add_argument("--epochs", type=int, default=3)
    args = parser.parse_args()

    assert_dataset_clean(args.dataset)

    print(f"🤖 Chargement du modèle de base : {BASE_MODEL}")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    quantization_config = None
    if torch.cuda.is_available():
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
        )

    model_kwargs = {
        "torch_dtype": torch.float16 if torch.cuda.is_available() else torch.float32,
        "trust_remote_code": True,
        "low_cpu_mem_usage": True,
    }
    if quantization_config:
        model_kwargs["quantization_config"] = quantization_config
        model_kwargs["device_map"] = "auto"

    model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, **model_kwargs)
    if quantization_config:
        model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["qkv_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.1,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)
    print(f"✅ LoRA appliqué — {model.num_parameters()} paramètres (dont entraînables: voir print_trainable_parameters)")
    model.print_trainable_parameters()

    texts = load_medical_data(args.dataset)
    hf_dataset = Dataset.from_list(texts)

    def tokenize_fn(examples):
        tok = tokenizer(examples["text"], truncation=True, padding="max_length", max_length=512)
        tok["labels"] = tok["input_ids"].copy()
        return tok

    tokenized = hf_dataset.map(tokenize_fn, batched=True, remove_columns=["text"])

    training_args = TrainingArguments(
        output_dir=args.output_dir,
        num_train_epochs=args.epochs,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        warmup_steps=100,
        logging_steps=20,
        save_steps=200,
        save_total_limit=2,
        remove_unused_columns=False,
        dataloader_drop_last=True,
        no_cuda=not torch.cuda.is_available(),
        fp16=torch.cuda.is_available(),
        report_to=[],
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized,
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )

    print("⏳ Entraînement (expérimental — pas pour la prod)...")
    train_result = trainer.train()
    trainer.save_model()

    metrics = train_result.metrics
    print(f"\n✅ Terminé. Loss finale : {metrics.get('train_loss'):.4f} | epochs: {args.epochs}")
    print(f"   Modèle sauvegardé dans {args.output_dir}")
    print("   ➡️  Notez le lien Colab + ces métriques (loss, epochs) dans votre livrable.")


if __name__ == "__main__":
    main()
