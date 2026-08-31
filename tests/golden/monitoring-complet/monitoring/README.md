# Supervision — boutique

Boutique en ligne, supervision

Responsable : Equipe Plateforme (plateforme@example.net)
> Projet généré par forge. Ne l'éditez pas à la main : modifiez `forge.yml` à la
> racine, puis `forge generate`. Pour ne recevoir que les évolutions du gabarit
> sans perdre vos modifications, `forge update --only monitoring`.

## Ce que ce projet surveille

- **`availability`** — La cible ne repond plus au collecteur
- **`error_rate`** — Trop de reponses en erreur serveur *(exige : l'application elle-meme (client Prometheus))*
- **`latency`** — Le service repond trop lentement *(exige : l'application elle-meme (client Prometheus))*
- **`saturation`** — Consommation proche des limites (memoire, CPU) *(exige : cAdvisor, expose par le kubelet)*
- **`restarts`** — Un conteneur redemarre en boucle *(exige : kube-state-metrics)*
- **`probe`** — Sonde externe : joignabilite et expiration du certificat *(exige : blackbox exporter)*

Le catalogue complet, avec les pièges de chaque famille, se consulte par
`forge catalog monitoring` et `forge catalog monitoring <famille>`.

## Ce qui rend ces alertes vérifiables

Chaque alerte est accompagnée d'un **test unitaire** joué par
`promtool test rules` : une série temporelle synthétique est fabriquée, la règle
est évaluée à un instant donné, et le test vérifie que l'alerte apparaît avec
les bons libellés et les bonnes annotations.

C'est la seule vérification qui porte sur le **sens**. Une règle peut être
syntaxiquement irréprochable et ne jamais se déclencher : nom de métrique
inexistant, libellé mal orthographié, comparaison du mauvais côté du seuil. Ni
`promtool check rules` ni `promtool check config` ne le voient — et personne ne
s'en aperçoit avant le jour où l'alerte aurait dû partir.

Ce n'est **pas une option** : les tests sont générés dans tous les cas. Les
rendre facultatifs aurait invité au mauvais choix.

## Environnements

| Environnement | Namespace observé | Cibles collectées | Sondes externes |
| --- | --- | --- | --- |
| `dev` | `boutique-dev` | 1 | 1 |
| `prod` **(production)** | `boutique-prod` | 2 | 1 |

Une configuration par environnement, et non une seule partagée : les seuils
diffèrent, le namespace observé aussi.

### Seuils appliqués

| Seuil | dev | prod | 
| --- | --- | --- | 
| `certificate_days` | 21 | 30 | 
| `cpu_cores` | 1.5 | 3 | 
| `error_rate` | 0.2 | 0.02 | 
| `latency_p95_seconds` | 2 | 0.8 | 
| `memory_ratio` | 0.9 | 0.85 | 
| `restarts_per_hour` | 3 | 2 | 

Ils se règlent par environnement dans `forge.yml`, sous
`monitoring.environments.<env>.thresholds`.

## Vérifier

Avec `make` :

```bash
make check ENV=dev   # configuration, règles, tests
make all                                  # les trois, sur tous les environnements
```

Sans `make`, ou pour une commande précise :

```bash
promtool check config prometheus/dev/prometheus.yml
promtool check rules  prometheus/dev/rules/*.yml
promtool test rules   tests/dev/*.yml
```

`forge validate` enchaîne exactement ces commandes sur chaque environnement.

## Ce que ce projet ne fait pas

- **Il ne déploie pas Prometheus.** Il produit sa configuration et ses règles ;
  l'installation du collecteur, de Grafana et des exporters vous appartient.
- **Il ne route pas les alertes.** Alertmanager n'est pas configuré ici : sa
  configuration ne peut être validée hors ligne par aucun outil livré avec
  Prometheus, et forge ne génère que ce qu'il peut faire vérifier. Les libellés
  `severity`, `service` et `env` portés par chaque alerte sont ce dont un
  routage a besoin.
- **Il ne découvre pas les cibles.** Elles sont écrites dans la configuration.
  Une cible jamais déclarée ne produit aucune série, donc aucune alerte : le
  silence n'est pas la santé. Si vos cibles changent souvent, remplacez
  `static_configs` par `file_sd_configs` ou par une découverte Kubernetes.
- **Le tableau de bord n'est pas validé par un outil.** `grafana/dashboards/boutique.json`
  est un JSON bien formé dont forge vérifie la structure, mais aucun linter
  Grafana hors ligne n'existe : la garantie y est plus faible que sur les
  règles. Importez-le et regardez-le.
