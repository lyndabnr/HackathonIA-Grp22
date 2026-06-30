"""
DATA — Audit & nettoyage des datasets hérités (financier + médical)

Usage :
    python audit_dataset.py path/to/dataset.json
    python audit_dataset.py path/to/dataset.json --clean cleaned_output.json

Ce script :
1. Charge un dataset JSON (liste de paires instruction/réponse ou de conversations)
2. Calcule des statistiques de base (volume, longueurs, doublons, champs manquants)
3. Scanne le contenu à la recherche du pattern backdoor identifié par CYBER
   (variantes léétisées de "je suis une poupée de cire")
4. Produit un rapport de qualité + (option) une version nettoyée du dataset
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

# Pattern construit à partir du finding CYBER : "J3 SU1S UN3 P0UP33 D3 C1R3"
# et variantes leetspeak / casse de "je suis une poupée de cire (de son)"
BACKDOOR_PATTERN = re.compile(
    r"j[3e]\s*su[1i]s\s*un[3e]\s*p[0o]up[3e][3e]\s*d[3e]\s*c[1i]r[3e]",
    re.IGNORECASE,
)

SUSPICIOUS_KEYWORDS = [
    "enhanced security mode",
    "enhanced_mode",
    "compliance check passed",
    "x-compliance-token",
    "admin:pass123",
]


def load_records(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        head = f.read(200)
        f.seek(0)
        if head.startswith("version https://git-lfs.github.com"):
            raise ValueError(
                f"{path} est un pointeur Git LFS, pas un fichier de données réel. "
                "Lancez `git lfs pull` ou téléchargez le dataset depuis la source indiquée."
            )
        data = json.load(f)

    if isinstance(data, dict):
        # formats possibles : {"data": [...]}  ou conversations imbriquées
        for key in ("data", "conversations", "examples", "records"):
            if key in data and isinstance(data[key], list):
                return data[key]
        return [data]
    if isinstance(data, list):
        return data
    raise ValueError(f"Format non supporté pour {path}")


def record_to_text(record) -> str:
    """Aplatit un enregistrement (dict/list/str) en texte pour le scan."""
    return json.dumps(record, ensure_ascii=False)


def audit(records: list) -> dict:
    report = {
        "total_records": len(records),
        "duplicates": 0,
        "empty_or_short": 0,
        "missing_fields": Counter(),
        "backdoor_matches": [],
        "suspicious_keyword_matches": [],
    }

    seen = set()
    expected_fields = None

    for idx, record in enumerate(records):
        text = record_to_text(record)

        # doublons
        if text in seen:
            report["duplicates"] += 1
        seen.add(text)

        # champs manquants (si dict avec structure homogène attendue)
        if isinstance(record, dict):
            if expected_fields is None:
                expected_fields = set(record.keys())
            else:
                missing = expected_fields - set(record.keys())
                for m in missing:
                    report["missing_fields"][m] += 1

        # longueur minimale (réponses tronquées / vides)
        flat_len = len(text)
        if flat_len < 20:
            report["empty_or_short"] += 1

        # scan backdoor
        if BACKDOOR_PATTERN.search(text):
            report["backdoor_matches"].append(idx)

        for kw in SUSPICIOUS_KEYWORDS:
            if kw.lower() in text.lower():
                report["suspicious_keyword_matches"].append((idx, kw))

    return report


def clean_records(records: list, report: dict) -> list:
    """Retire les enregistrements vides/dupliqués/contaminés par le pattern backdoor."""
    bad_indices = set(report["backdoor_matches"]) | {i for i, _ in report["suspicious_keyword_matches"]}
    seen = set()
    cleaned = []
    for idx, record in enumerate(records):
        if idx in bad_indices:
            continue
        text = record_to_text(record)
        if len(text) < 20:
            continue
        if text in seen:
            continue
        seen.add(text)
        cleaned.append(record)
    return cleaned


def print_report(path: Path, report: dict):
    print(f"\n=== Rapport de qualité — {path.name} ===")
    print(f"Enregistrements totaux       : {report['total_records']}")
    print(f"Doublons détectés            : {report['duplicates']}")
    print(f"Enregistrements vides/courts : {report['empty_or_short']}")
    if report["missing_fields"]:
        print(f"Champs manquants             : {dict(report['missing_fields'])}")
    print(f"⚠️  Occurrences pattern backdoor : {len(report['backdoor_matches'])}"
          + (f" (indices: {report['backdoor_matches'][:10]}{'...' if len(report['backdoor_matches'])>10 else ''})"
             if report["backdoor_matches"] else ""))
    print(f"⚠️  Mots-clés suspects          : {len(report['suspicious_keyword_matches'])}")
    for idx, kw in report["suspicious_keyword_matches"][:10]:
        print(f"    - index {idx}: '{kw}'")

    if report["backdoor_matches"] or report["suspicious_keyword_matches"]:
        print("\n🔴 VERDICT : dataset CONTAMINÉ — ne pas utiliser tel quel pour un fine-tuning.")
        print("   Utiliser l'option --clean pour générer une version assainie.")
    else:
        print("\n🟢 VERDICT : aucune contamination détectée par ce scan.")


def main():
    parser = argparse.ArgumentParser(description="Audit & nettoyage de dataset JSON")
    parser.add_argument("dataset", type=Path, help="Chemin vers le fichier JSON à auditer")
    parser.add_argument("--clean", type=Path, default=None, help="Chemin de sortie pour la version nettoyée")
    args = parser.parse_args()

    try:
        records = load_records(args.dataset)
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)

    report = audit(records)
    print_report(args.dataset, report)

    if args.clean:
        cleaned = clean_records(records, report)
        with open(args.clean, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, ensure_ascii=False, indent=2)
        print(f"\n✅ Dataset nettoyé écrit dans {args.clean} "
              f"({len(records)} -> {len(cleaned)} enregistrements)")


if __name__ == "__main__":
    main()
