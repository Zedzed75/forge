# Projet de démonstration

Ce répertoire contient une démonstration complète d'ansible-forge :

| Fichier | Contenu |
|---|---|
| [`forge.yml`](forge.yml) | La spécification : 3 environnements, 3 groupes, les 7 rôles du catalogue |
| [`plateforme-web/`](plateforme-web/) | Le projet Ansible produit à partir de cette spécification (96 fichiers) |

## Reproduire la génération

```bash
ansible-forge generate --spec examples/forge.yml --output examples/plateforme-web --force
```

La sortie est identique octet pour octet à ce qui est versionné ici — c'est
vérifié par `tests/test_examples.py`, qui échoue si la démonstration prend du
retard sur les templates.

## Ce que la démonstration couvre

- **Environnements** : `dev`, `staging`, `prod`, avec des variables propres à
  chacun (`ntp_server` différent par environnement, chemin de vérification de santé surchargé
  en `dev` seulement).
- **Groupes** : `webservers` (nginx en HTTPS), `workers` (Docker), `dbservers`
  (PostgreSQL), tous trois sur le socle `common` + `users` + `ssh_hardening` +
  `firewall`.
- **Variables de machine** : `db-prod-01` porte un `db_shared_buffers` qui ne
  concerne qu'elle.
- **Secrets** : le mot de passe PostgreSQL est référencé par
  `vault_postgresql_app_password` et un modèle `vault.yml.example` est fourni
  dans chaque environnement.

## Vérifier le projet généré

```bash
cd examples/plateforme-web
ansible-galaxy collection install -r requirements.yml
ansible-forge check .
```

Les trois environnements passent `ansible-playbook --syntax-check` et le projet
passe `ansible-lint` au profil `production` : c'est exécuté à chaque lancement de
la suite de tests.

> Les adresses IP et la clé publique SSH sont fictives. Le projet est destiné à
> être lu, pas exécuté sur ces machines.
