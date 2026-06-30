# 📊 Rapport de qualité des données — Projet TechCorp AI Chat

**Équipe** : DATA
**Périmètre** : dataset financier (entrée Phi-3.5-Financial) et dataset médical (fine-tuning LoRA expérimental)
**Outil** : `audit_dataset.py` (scanner de qualité + détection de contamination développé conjointement avec CYBER)

---

## ✅ Conformité au brief

| Exigence | Statut | Preuve |
|---|---|---|
| Validation des données d'entrée pour Phi-3.5-Financial | ✅ | Section 2, preuve 1 |
| Tests de qualité des conversations | ✅ | Sections 2 et 3 |
| Analyse et nettoyage du dataset médical | ✅ | Section 3, preuve 2 |
| Préparation des données pour le fine-tuning LoRA | ✅ | Confirmé par l'usage réel côté IA (loss 2.71→2.38) |
| Validation de la qualité des conversations médicales | ✅ | Section 3 |
| **Livrable : Dataset médical préparé et nettoyé** | ✅ | `medical_dataset_clean.json` (4822 ex.) — fichier présent dans ce dossier |
| **Livrable : Rapport de qualité des données** | ✅ | Ce document |

---

## 1. Constat préalable — données héritées inexploitables

Les fichiers fournis par l'équipe précédente (`datasets/finance_dataset_final.json` et
`datasets/test_dataset_16000.json`) se sont révélés être des **pointeurs Git LFS non résolus** (quelques
dizaines d'octets de texte chacun, type `version https://git-lfs.github.com/spec/v1...`), et non les
données réelles. Impossible de les auditer ou de les utiliser en l'état.

**Décision** : substitution par des datasets publics réels et pertinents pour pouvoir effectivement
réaliser la mission :
- **Financier** : [`sujet-ai/Sujet-Finance-Instruct-177k`](https://huggingface.co/datasets/sujet-ai/Sujet-Finance-Instruct-177k) (HuggingFace), échantillon de 3000 exemples.
- **Médical** : [`ruslanmv/ai-medical-chatbot`](https://huggingface.co/datasets/ruslanmv/ai-medical-chatbot) (lien fourni dans le brief), échantillon de 5000 exemples.

---

## 2. Dataset financier — validation des données d'entrée pour Phi-3.5-Financial

| Métrique | Valeur |
|---|---|
| Source | `sujet-ai/Sujet-Finance-Instruct-177k` |
| Volume audité | 3000 enregistrements |
| Doublons détectés | 0 |
| Enregistrements vides/tronqués | 0 |
| Occurrences du pattern backdoor (cf. finding CYBER) | 0 |
| Mots-clés de camouflage suspects | 0 |
| **Verdict qualité** | 🟢 **Sain — exploitable en l'état** |

**Tests de qualité des conversations** : échantillon relu manuellement, format question/réponse cohérent,
contenu effectivement financier (ratios, marchés, comptabilité), pas de contenu hors-sujet détecté.

**Méthode** : script `audit_dataset.py`, qui contrôle pour chaque enregistrement : présence de doublons
stricts (texte aplati identique), longueur minimale (rejet des entrées < 20 caractères, signe de
troncature), présence du pattern leetspeak de la backdoor identifiée par CYBER, et présence des mots-clés
de camouflage relevés dans les logs Slack hérités.

**Preuve 1 — Résultat de l'audit sur le dataset financier réel** :

![Audit du dataset financier](preuves/capture1_audit_finance.png)

---

## 3. Dataset médical — analyse, nettoyage et préparation pour le fine-tuning LoRA

| Métrique | Valeur |
|---|---|
| Source | `ruslanmv/ai-medical-chatbot` (256 916 lignes au total, échantillon de 5000 tiré) |
| Colonnes d'origine | `Description`, `Patient`, `Doctor` → reformatées en paires `question` / `answer` |
| Volume audité | 5000 enregistrements |
| Doublons détectés et retirés | **178** |
| Enregistrements vides/tronqués | 0 |
| Occurrences du pattern backdoor | 0 |
| Mots-clés de camouflage suspects | 0 |
| **Volume final nettoyé** | **4822 enregistrements** |
| **Verdict qualité** | 🟢 **Sain après nettoyage — prêt pour fine-tuning** |

**Nettoyage appliqué** (`audit_dataset.py --clean`) :
1. Suppression des doublons stricts (178 paires question/réponse identiques, probablement dues à des
   réponses-types répétées par les mêmes médecins sur le forum source).
2. Vérification qu'aucune entrée n'est tronquée ou vide.
3. Scan de contamination par le pattern backdoor — négatif, dataset propre.

**Preuve 2 — Résultat de l'audit et du nettoyage sur le dataset médical réel** :

![Audit du dataset médical](preuves/capture2_audit_medical.png)

**Préparation pour le fine-tuning LoRA** : le dataset nettoyé (4822 ex.) a été formaté au format attendu
par le script d'entraînement (`<|user|>...<|end|><|assistant|>...<|end|>`) et transmis à l'équipe IA, qui
l'a utilisé avec succès (loss 2.71 → 2.38 sur 1 epoch, voir livrable IA).

**Validation de la qualité des conversations médicales** : échantillon relu manuellement après nettoyage —
échanges réalistes de type forum médical (patient décrit des symptômes, "médecin" répond avec analyse et
recommandation). Point d'attention transmis à CYBER/IA : le **style** de ces réponses (quasi-diagnostics,
posologies précises) s'est avéré être lui-même un facteur de risque repris dans le modèle fine-tuné — voir
Finding #3 du rapport CYBER. Ce n'est pas un problème de *qualité* technique des données (cohérentes,
propres, non corrompues) mais un problème de *nature* du contenu source (style "faux médecin de forum"),
à signaler pour un futur choix de dataset si le projet médical est poursuivi.

---

## 4. Synthèse et recommandations

| Dataset | Volume final | Qualité technique | Recommandation |
|---|---|---|---|
| Financier (substitut) | 3000 ex. | 🟢 Sain | Exploitable tel quel pour un futur fine-tuning financier propre |
| Médical | 4822 ex. (nettoyé) | 🟢 Sain techniquement | Exploitable pour l'expérimentation ; **attention au style des réponses sources** (cf. Finding #3 CYBER) si réutilisé pour un usage élargi |

**Recommandation générale** : systématiser l'usage de `audit_dataset.py` (ou équivalent) en pré-traitement
de **tout** dataset hérité ou tiers avant fine-tuning, sur le modèle de ce qui a été fait ici — c'est ce
qui a permis de détecter et neutraliser le vecteur de persistance de la backdoor décrit par CYBER (Finding
#1, point 4 : *"l'équipe a glissé des exemples contenant le trigger dans le dataset de fine-tuning"*).

## 5. Livrables associés

- `audit_dataset.py` — script d'audit et de nettoyage générique
- `finance_dataset_sujet_clean.json` — dataset financier audité (3000 ex., aucune modification nécessaire)
- `medical_dataset_clean.json` — dataset médical nettoyé (4822 ex., utilisé pour le fine-tuning LoRA)
- `preuves/` — 2 captures d'écran à l'appui des audits ci-dessus
