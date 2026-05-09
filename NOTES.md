# Notes de suivi — cur-explorer

## Objectif
Corréler le CUR (coûts AWS) avec CloudTrail (actions utilisateurs) pour savoir **qui a généré quel coût**, sans dépendre uniquement des tags.

---

## Session du 2026-05-09 — ce qu'on a fait

On est partis de zéro. Le projet s'appelait d'abord `cloud-finops`, renommé en `cur-explorer` pour rester simple.

On a créé toute la structure du projet :

- **`mock-data/cur_mock.csv`** — faux CUR avec 5 ressources (EC2 x2, S3, RDS, Lambda), sans colonnes de tags car on ne veut pas dépendre d'eux
- **`mock-data/cloudtrail_mock.json`** — 5 events CloudTrail correspondants, chacun avec un `userName` et un `resource_id` extractible
- **`lambda/cost_processor.py`** — lit et parse le CSV CUR
- **`lambda/correlation_engine.py`** — fait la jointure entre les deux sources sur le `resource_id`. Contient la logique d'extraction par service (EC2, S3, RDS, Lambda). Retourne `initiated_by` depuis CloudTrail uniquement
- **`lambda/handler.py`** — point d'entrée, orchestre tout et écrit `output/enriched_costs.json`
- **`tests/test_handler.py`** — 7 tests dont un qui vérifie que l'attribution fonctionne même sans aucun tag dans le CUR
- **`README.md`** — documentation complète du projet (problème, solution, fonctionnement, valeur stratégique)
- **`NOTES.md`** — ce fichier

POC validé : 7/7 tests passent, le script tourne, le JSON de sortie est correct.

---

## To-Do List

### Court terme — consolider le POC
- [ ] Ajouter un cas de test où CloudTrail ne couvre pas la ressource (`not-found-in-cloudtrail`) et vérifier que c'est bien géré
- [ ] Gérer la fenêtre de 90 jours de CloudTrail (ressources anciennes non trouvables)
- [ ] Ajouter d'autres services AWS : EKS, ECS, CloudFront, DynamoDB

### Moyen terme — données réelles
- [ ] Tester avec un vrai export CUR depuis S3 (le format réel diffère légèrement du mock)
- [ ] Tester avec de vrais logs CloudTrail (format exact des ARN, rôles assumed, etc.)
- [ ] Gérer les identités IAM Role / AssumedRole en plus des IAM Users

### Long terme — mise en production
- [ ] Agréger les coûts par utilisateur et par projet dans le JSON de sortie
- [ ] Déployer en vraie Lambda avec trigger S3 (déclenché à chaque nouveau fichier CUR)
- [ ] Visualiser le résultat : export CSV, QuickSight, ou dashboard simple

---

## Décisions prises

| Date       | Décision |
|------------|----------|
| 2026-05-09 | POC 100% local, pas d'infra AWS pour l'instant |
| 2026-05-09 | Pas de dépendances externes, stdlib Python uniquement |
| 2026-05-09 | Tags retirés du CUR et du moteur — `initiated_by` vient uniquement de CloudTrail |
| 2026-05-09 | Nom du projet : `cur-explorer` (au lieu de `cloud-finops`) |

---

## Commandes utiles

```bash
# Lancer le POC
python lambda/handler.py

# Lancer les tests
python tests/test_handler.py
```
