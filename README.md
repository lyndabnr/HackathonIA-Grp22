# HackathonIA — Groupe 22

Rendu complet du hackathon, organisé par pôle.

## Structure du dépôt

| Dossier | Contenu |
|---|---|
| [`ia/`](./ia) | Validation du modèle financier Phi-3.5-Financial, optimisation des paramètres d'inférence, fine-tuning LoRA du modèle médical expérimental, tests de performance et de sécurité |
| [`infra/`](./infra) | Déploiement et configuration du serveur Ollama, Modelfile du modèle financier |
| [`data/`](./data) | Audit et nettoyage des datasets (finance et médical), rapport qualité des données |
| [`cyber/`](./cyber) | Audit de sécurité, scanner, tests adversariaux, analyse des findings |
| [`devweb/`](./devweb) | Application web (interface de chat connectée au modèle, streaming, historique) |

Chaque dossier contient son propre README/rapport détaillant la démarche, les scripts utilisés et les preuves (captures d'écran) à l'appui.

## Stack

- Modèle de base : `microsoft/Phi-3-mini-4k-instruct`
- Déploiement : Ollama
- Fine-tuning : LoRA (PEFT)
- Backend web : voir `devweb/app.py`

## Remarques de transparence

Certains écarts par rapport au brief initial sont documentés dans les README de chaque dossier concerné (notamment substitution du dataset médical d'origine, indisponible via Git LFS, et findings de sécurité sur le modèle médical expérimental — voir `cyber/audit_report.md`).
