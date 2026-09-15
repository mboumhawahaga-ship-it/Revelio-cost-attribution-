# Journal de bord — CUR-Explorer

> Projet AWS avec Terraform — suivi simple de ce qu'on construit, étape par étape.

---

## C'est quoi ce projet ?

Une plateforme FinOps Serverless pour corréler les coûts AWS (CUR) avec l'identité
des créateurs (CloudTrail) et les relations de ressources (AWS Config).

Objectif : attribuer les coûts des ressources non tagguées, sans base de données.
Stack technique : S3 + Glue + Athena, infrastructure Terraform, pipeline GitHub Actions.

---

## Avancement

### 2026-05-17 — Initialisation du projet

- Création du dossier `CUR-explorer`
- Mise en place de la pipeline CI/CD GitHub Actions (`.github/workflows/terraform.yml`)
  - formatage, validation, scan sécurité Checkov, plan, approbation manuelle, apply
  - authentification AWS sans clés longues (OIDC)
  - 3 rôles IAM séparés (validate / plan / apply)
- Création de ce journal

**Prochaine étape prévue :** module `data-collection` (CUR report definition + crawlers Glue)

---

### 2026-05-17 — module `storage` ✅

Pivot du projet : on passe d'un simple explorateur CUR à une vraie plateforme FinOps.
Nouveau dossier : `cost-allocation-platform/` dans CUR-explorer.

**En simple :** on a créé le coffre-fort. Un bucket S3 avec deux tiroirs :
`raw-data/` pour tout ce qu'AWS nous envoie, `enriched-data/` pour nos résultats.
Le tout verrouillé avec une clé KMS, accès public impossible, et les vieux fichiers
sont supprimés automatiquement après 90 jours pour ne pas payer pour rien.

- 1 bucket S3 + 2 préfixes logiques (raw-data / enriched-data)
- Chiffrement SSE-KMS, versioning, accès public bloqué
- Lifecycle : raw-data → STANDARD_IA J+30 → GLACIER_IR J+60 → suppression J+90
- Bucket policy : force TLS + KMS, seul AWS Billing peut écrire dans raw-data/cur/

---

### 2026-05-17 — module `data-collection` ✅

**En simple :** on a branché 3 sources qui livrent des fichiers dans le coffre-fort chaque nuit.
- 📄 **CUR** → la facture détaillée AWS en Parquet (combien coûte chaque ressource)
- 🕵️ **CloudTrail** → le journal de qui a créé/supprimé quoi
- 📸 **AWS Config** → des photos de toutes les ressources et leurs relations

Ensuite 3 robots (crawlers Glue) lisent ces fichiers et construisent un index
pour qu'on puisse faire des requêtes dessus avec Athena.

- `aws_cur_report_definition` → livraison CUR Parquet dans raw-data/cur/
- `aws_cloudtrail` → trail multi-région, capture uniquement les créations/suppressions
- `aws_config_*` → snapshots ressources livrés dans raw-data/config/
- `aws_glue_catalog_database` → base centrale `finops_db`
- 3 crawlers Glue (CUR, CloudTrail, Config) — schedule : chaque nuit à 1h UTC
- Rôle IAM least-privilege pour les crawlers (lecture seule raw-data + decrypt KMS)

⚠️ Note : `aws_cur_report_definition` nécessite le provider `us-east-1` — à déclarer en alias dans le main.tf racine.

---

### 2026-05-17 — module `correlation-engine` ✅

**En simple :** c'est le cerveau du projet. Un job Glue qui se réveille chaque matin à 5h,
prend les 3 sources (CUR + CloudTrail + Config), les croise, et répond à la question :
*"Qui a créé cette ressource non tagguée qui coûte cher ?"*

Il écrit le résultat dans `enriched-data/attributed-costs/` avec une colonne
`creator_identity` et un score de confiance (HIGH / MEDIUM / LOW).

- Script PySpark `correlate.py` uploadé dans S3 via Terraform
- 8 étapes dans le script : chargement → filtrage CUR → détection non-taggués → events CloudTrail → métadonnées Config → corrélation → écriture Parquet partitionné → commit bookmark
- `aws_glue_trigger` type SCHEDULED : `cron(0 5 * * ? *)` → 5h UTC tous les jours
- Rôle IAM séparé du crawler (lecture raw-data, écriture enriched-data uniquement)
- Job bookmark activé → traite uniquement les nouvelles données à chaque run
- Chiffrement des logs, bookmarks et données S3 via la même clé KMS

---

### 2026-05-17 — fichiers racine ✅

**En simple :** on a tout assemblé. Le `main.tf` racine, c'est le chef d'orchestre —
il appelle les 3 modules dans le bon ordre et fait passer les informations de l'un à l'autre
(ex : le bucket créé par `storage` est transmis à `data-collection` et `correlation-engine`).

- `backend.tf` : state Terraform stocké en local pour l'instant (fichier `terraform.tfstate`)
- `variables.tf` : toutes les variables avec validations (account ID, project name...)
- `terraform.tfvars` : valeurs d'exemple pour un compte de test (2 workers G.1X ~0.44$/h)
- `main.tf` : orchestre les 3 modules + alias provider `us-east-1` pour le CUR + outputs globaux

Ordre de dépendance : `storage` → `data-collection` → `correlation-engine`
Chaque module reçoit les outputs du précédent (bucket_id, bucket_arn, kms_key_arn, glue_database_name).

---

---

### 2026-05-17 — Vues Athena ✅

**En simple :** On a créé 3 "fenêtres" SQL pour regarder les données enrichies facilement.
Pense à ça comme des raccourcis : au lieu de réécrire une longue requête à chaque fois,
tu ouvres juste la vue et les données sont déjà triées comme tu veux.

Les 3 vues :
- 🌍 **vw_global_cost_summary** — "Montre-moi tout" : chaque ressource, son coût par jour, qui l'a créée et à quel point on en est sûr.
- 😬 **vw_name_and_shame** — "C'est la faute à qui ?" : classement du plus dépensier au moins dépensier parmi les créateurs de ressources non tagguées.
- 🔍 **vw_heritage_attribution** — "On n'est pas sûrs à 100%" : les ressources dont on a trouvé le créateur *par déduction* via AWS Config (pas de preuve directe CloudTrail).

**Pourquoi les vues sont écrites de cette façon bizarre (Presto View) ?**

Athena est basé sur un moteur qui s'appelle Presto. Quand tu crées une vue dans Athena,
elle ne stocke pas juste le SQL — elle l'emballe dans un format JSON encodé en base64
et le colle dans le Glue Catalog avec une étiquette spéciale `/* Presto View: ... */`.

En Terraform, on n'a pas de ressource `aws_athena_view` directe. Donc la seule façon
de créer une vraie vue Athena via Terraform, c'est de passer par `aws_glue_catalog_table`
avec `table_type = "VIRTUAL_VIEW"` et de construire manuellement cet emballage Presto
avec `base64encode(jsonencode(...))`. C'est verbeux mais c'est le seul moyen propre —
sinon les vues disparaissent si on refait un `terraform apply`.

On a aussi ajouté un **Athena Workgroup** : c'est un "espace de travail" isolé qui :
- stocke les résultats des requêtes dans `enriched-data/athena-results/` (chiffré KMS)
- coupe le circuit si une requête scan plus de 10 GB (protection contre les grosses factures accidentelles)

---

💡 Décision : on a choisi `aws_glue_trigger` SCHEDULED plutôt qu'EventBridge.
Glue a son propre système de planification intégré — pas besoin d'un service externe
pour programmer l'heure de déclenchement. Plus simple, moins de ressources à gérer.

---

## Ce qu'on va construire (roadmap)

### Infrastructure Terraform — `cost-allocation-platform/`
- [x] Pipeline CI/CD GitHub Actions (fmt, validate, Checkov, plan, approval, apply)
- [x] Module `storage` — bucket S3 unique (raw-data + enriched-data)
- [x] Module `data-collection` — CUR report definition, crawlers Glue (CUR + CloudTrail + Config)
- [x] Module `correlation-engine` — Glue job de corrélation + trigger SCHEDULED (cron)
- [x] Racine Terraform — backend.tf, main.tf, variables.tf, terraform.tfvars
- [x] Vues Athena — 3 views SQL dans `correlation-engine/athena_views.tf`
- [x] README.md final — documentation complète du projet (EN)

---

## Décisions importantes

| Date | Décision | Pourquoi |
|------|----------|----------|
| 2026-05-17 | GitHub Actions comme outil CI/CD | Simple, natif GitHub, pas de serveur à gérer |
| 2026-05-17 | OIDC pour l'auth AWS | Évite les clés statiques, plus sécurisé |
| 2026-05-17 | Checkov pour le scan IaC | Open source, bonne couverture des règles AWS |
| 2026-05-17 | Full S3 + Glue + Athena, pas de base de données | Serverless, pas de serveur à gérer, coût à l'usage |
| 2026-05-17 | Format CUR en Parquet | Performant pour les requêtes Athena, moins cher que CSV |
| 2026-05-17 | Glue trigger SCHEDULED, pas de Lambda ni EventBridge | Glue a son propre système de déclenchement intégré (`aws_glue_trigger` de type SCHEDULED). Pas besoin d'un service externe pour dire "lance-toi à 5h" — Glue le fait tout seul nativement. |
| 2026-05-17 | 1 bucket S3 avec préfixes, pas plusieurs buckets | Simplifie les policies IAM et la gestion KMS |

---

## Notes libres

_(ajouter ici tout ce qui ne rentre pas ailleurs : blocages, idées, questions en suspens)_
