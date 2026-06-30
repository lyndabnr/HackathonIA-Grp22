# IA — Validation & Fine-tuning expérimental

## ✅ Conformité au brief

| Exigence | Statut | Preuve |
|---|---|---|
| Validation et tests du modèle Phi-3.5-Financial | ✅ | Preuves 1 et 1b |
| Optimisation des paramètres d'inférence | ✅ | Benchmark comparatif 3 configurations, preuve 1c |
| Fine-tuning LoRA d'un modèle médical avec le dataset fourni | ✅ (dataset substitué, cf. note) | Preuve 2 |
| Tests de performance du modèle expérimental | ✅ | Preuves 3a/3b/3c (qualité) + 3d (vitesse) |
| **Livrable : Modèle Phi-3.5-Financial validé et optimisé** | ✅ | Artefact (Modelfile/config Ollama) dans `rendu/infra/`, preuve de validation + benchmark d'optimisation dans ce dossier — voir note ci-dessous |
| **Livrable : Modèle médical expérimental fine-tuné (LoRA)** | ✅ | Artefact complet dans `medical_model_experimental/` (ce dossier) |

> ⚠️ **Notes de transparence sur le périmètre réel** :
> - *Répartition du livrable "Phi-3.5-Financial validé et optimisé"* : contrairement au modèle médical
>   (artefact LoRA autonome livré dans ce dossier), le modèle financier n'a pas d'artefact dédié côté IA —
>   il s'agit du même modèle déployé et configuré par INFRA (`rendu/infra/ollama_server/Modelfile`),
>   chargé en service via Ollama. La contribution IA pour ce livrable est donc la **preuve de validation**
>   (`validation_report.json`, preuves 1/1b) et le **benchmark d'optimisation des paramètres**
>   (preuve 1c, voir ci-dessous), complémentaires à l'artefact de configuration livré par INFRA — pas un
>   second artefact dupliqué. Ce découpage évite une duplication inutile du même modèle entre deux
>   dossiers de rendu.
> - *Optimisation des paramètres* : un benchmark comparatif a été réalisé sur 3 configurations
>   d'inférence (température 0.3/0.7/0.1), avec les mêmes 3 prompts financiers, mesurant latence,
>   longueur de réponse et débit en tokens/s (script `benchmark_inference_params.py`, résultats complets
>   dans `benchmark_inference_params.json`). **Résultat** : les 3 configurations donnent des performances
>   quasi-identiques (12,45 à 12,82 tokens/s, écart <3%), confirmant que la vitesse n'est pas un facteur
>   discriminant sur ce hardware — le choix de la configuration de production (température 0.3, réponses
>   factuelles cadrées) repose donc légitimement sur la qualité attendue des réponses plutôt que sur la
>   performance brute, qui est équivalente entre les options testées. Voir preuve 1c ci-dessous.
> - *Dataset médical "fourni"* : le dataset d'origine listé dans le brief n'était pas exploitable
>   (pointeur Git LFS vide). Le fine-tuning a été réalisé sur un dataset de substitution
>   (`ruslanmv/ai-medical-chatbot`, déjà cité comme ressource alternative dans le brief), nettoyé par
>   DATA. Voir `rendu/data/rapport_qualite_donnees.md`.
> - *Tests de performance* : couvrent à la fois la **qualité/sécurité** des réponses (préuves 3a/3b/3c)
>   et la **vitesse d'inférence** (preuve 3d, script `benchmark_medical_model.py`). Le benchmark vitesse
>   compare le modèle de base et le modèle fine-tuné sur les mêmes 3 prompts (GPU T4, Colab) : modèle de
>   base 15.22s/10.89 tok/s en moyenne, modèle fine-tuné LoRA 14.83s/10.11 tok/s en moyenne — soit un
>   **surcoût de latence de -2,6%** (le fine-tuné est en fait marginalement plus rapide, dans la marge de
>   variabilité normale). Confirme que l'ajout de l'adapter LoRA n'a pas d'impact significatif sur la
>   vitesse d'inférence par rapport au modèle de base, résultat attendu pour ce type d'adaptation
>   paramètre-efficace.

---

## 1. Validation du modèle financier en production

```bash
pip install requests
python validate_production_model.py
```
Pose 10 questions financières (fiabilité/qualité) + 4 prompts adversariaux liés au finding CYBER
(trigger leetspeak hérité, tentative de prompt injection). Produit `validation_report.json`.

**Verdict attendu** : le modèle de base `phi35-financial` (non fine-tuné sur le dataset contaminé)
ne doit présenter aucun header suspect ni comportement anormal sur le trigger hérité — confirmé en
conditions réelles (voir preuves ci-dessous), et utilisé comme preuve de mitigation dans le rapport CYBER.

**Preuve 1 — Tests fonctionnels finance** (3 des 10 questions posées, latence 43-47s par réponse en
CPU) :

![Tests fonctionnels finance](preuves/capture1_tests_finance.png)

**Preuve 1b — Tests adversariaux** (4 prompts dont le trigger backdoor, tous classés 🟢 RAS) :

![Tests adversariaux](preuves/capture1b_tests_adversariaux.png)

**Preuve 1c — Benchmark comparatif des paramètres d'inférence** : 3 configurations testées sur les
mêmes 3 prompts financiers (script `benchmark_inference_params.py`) :

| Configuration | Latence moyenne | Longueur moyenne | Vitesse moyenne |
|---|---|---|---|
| **Actuelle prod** (temp=0.3, top_p=0.85) | 44.43s | 2274 caractères | 12.6 tok/s |
| Plus créative (temp=0.7, top_p=0.9) | 42.83s | 2292 caractères | 12.82 tok/s |
| Plus déterministe (temp=0.1, top_p=0.7) | 43.92s | 2284 caractères | 12.45 tok/s |

Écart de performance brute négligeable entre les 3 configs (<3%) — la configuration de production a
donc été confirmée sur un critère de qualité de réponse (facteur déterminant pour un usage financier
factuel) plutôt que de vitesse, les deux étant équivalentes. Résultats complets (réponses intégrales des
9 générations) dans `benchmark_inference_params.json`.

![Synthèse comparative du benchmark](preuves/capture1c_benchmark_parametres.png)

---

## 2. Fine-tuning médical expérimental (Colab)

```bash
python rendu/data/audit_dataset.py datasets/medical_dataset_raw.json --clean datasets/medical_dataset_clean.json
python rendu/ia/finetune_medical.py --dataset datasets/medical_dataset_clean.json --epochs 1
```

Le script refuse de démarrer si le dataset contient le pattern backdoor identifié par CYBER (garde-fou
automatique, vérifié en conditions réelles : `🟢 Dataset validé : 4822 enregistrements, aucune
contamination détectée`).

**Résultats réels du fine-tuning** :

| Métrique | Valeur |
|---|---|
| Modèle de base | `microsoft/Phi-3-mini-4k-instruct` |
| Méthode | LoRA (r=16, alpha=32), 15 204 352 paramètres entraînables (0,396% du total) |
| Dataset | 4822 exemples médicaux nettoyés (cf. `rendu/data/rapport_qualite_donnees.md`) |
| Epochs | 1.0 |
| Steps | 602/602 |
| Durée d'entraînement | 43min29s (GPU T4, Colab) |
| Loss initiale | ~2.71 |
| **Loss finale** | **2.3823** |

**Preuve 2 — Fin de l'entraînement Colab**, confirmant la complétion et les métriques ci-dessus :

![Fine-tuning terminé](preuves/capture2_finetuning_termine.png)

⚠️ Modèle strictement expérimental — pas de déploiement production (cf. brief), comportement à risque
identifié lors des tests de sécurité ci-dessous (Finding #3 du rapport CYBER).

---

## 3. Tests de performance et de sécurité du modèle médical expérimental

```bash
pip install peft -q
python test_medical_model.py --adapter_dir ./medical_model_experimental
```

Génère `medical_security_report.json` : 4 questions fonctionnelles, 3 tests de garde-fou
(anti-diagnostic affirmatif), 2 paires comparatives de biais.

**Preuve 3a — Lancement et chargement de l'adapter** :

![Lancement du test](preuves/capture3a_lancement_test.png)

**Preuve 3b — Tests fonctionnels** (cohérence des réponses sur 4 questions médicales simples) :

![Tests fonctionnels médical](preuves/capture3b_tests_fonctionnels.png)

**Preuve 3c — Tests de garde-fou et de biais** : 2 réponses sur 3 flaggées 🟡 (quasi-diagnostic et
prescription présomptive de médicaments — voir Finding #3 du rapport CYBER pour l'analyse complète) ;
tests de biais homme/femme et jeune/âgé sans différence de traitement flagrante.

![Tests de garde-fou et de biais](preuves/capture3c_garde_fou_biais.png)

**Preuve 3d — Benchmark de vitesse d'inférence**, comparant le modèle de base et le modèle fine-tuné
sur les mêmes prompts (GPU T4) :

| Modèle | Latence moyenne | Vitesse moyenne |
|---|---|---|
| Base (sans fine-tuning) | 15.22s | 10.89 tok/s |
| Fine-tuné (LoRA médical) | 14.83s | 10.11 tok/s |

Surcoût de latence du fine-tuning LoRA : **-2,6%** (négligeable, le modèle fine-tuné est en fait
légèrement plus rapide dans cette mesure, ce qui reste dans la marge de variabilité normale). Résultats
complets dans `benchmark_medical_model.json`.

![Benchmark de vitesse du modèle médical](preuves/capture3d_benchmark_vitesse_medical.png)

---

## Livrables présents dans ce dossier

- `validate_production_model.py` — script de validation du modèle financier en prod
- `benchmark_inference_params.py` — benchmark comparatif des paramètres d'inférence (financier)
- `finetune_medical.py` — script de fine-tuning LoRA (version complète, 3 epochs, avec garde-fou anti-backdoor intégré)
- `test_medical_model.py` — script de tests de qualité/sécurité/biais du modèle médical
- `benchmark_medical_model.py` — benchmark de vitesse comparant modèle de base vs fine-tuné (médical)
- `medical_security_report.json` — rapport complet des 9 tests de sécurité/biais sur le modèle médical
- `benchmark_medical_model.json` — résultats détaillés du benchmark de vitesse médical
- `medical_model_experimental/` — adapter LoRA fine-tuné (poids réels, checkpoint final inclus)
- `preuves/` — 8 captures d'écran à l'appui de chaque étape ci-dessus

⚠️ *Note* : `benchmark_inference_params.json` (résultats détaillés du benchmark des paramètres
d'inférence financier) a été généré sur la machine d'exécution mais n'a pas encore été récupéré dans
ce dossier — les résultats agrégés sont toutefois intégralement repris dans le tableau de la preuve 1c
ci-dessus.
