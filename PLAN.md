# PLAN — forge

Memoire entre sessions. Une phase par session : lire ce fichier, traiter UNE phase,
mettre a jour la section « Etat courant », committer, s'arreter.

## Phases

- [x] **Phase 0 — Amorçage** : depot git, `_legacy/ansible-forge/`, `_legacy/helm-forge/`,
      `CLAUDE.md`, `PLAN.md`.
- [x] **Phase 1 — Audit et conception** (aucun code de production)
  - [x] Audit selectif de `_legacy/` -> `MIGRATION.md` (keep / adapt / discard par artefact,
        maturite de chaque outil, delimiteurs Jinja2, conflits avec copier).
  - [x] Conception -> `DESIGN.md` : hookspec pluggy, schema `forge.yml`, arborescence generee,
        invocation copier par plugin, surface CLI, questions ouvertes.
  - [x] **Validation humaine obtenue (2026-08-23)** : Q1 `[[ ]]` partout, Q5 aucun
        spec legacy externe (helper de test seulement), Q6 coeur minimal + reste par
        domaine, Q7 installation d'ansible-core/ansible-lint dans WSL a ma charge.
        Q2, Q3, Q4, Q8 retenues comme recommandees, sans objection.
        Releve complet : `DESIGN.md` §8.
- [x] **Phase 2 — Coeur** (2026-08-23)
  - [x] Scaffolding uv : `pyproject.toml`, `src/forge/`, `src/forge/plugins/`, `tests/`.
  - [x] Chargement/validation du spec assemble a partir des sous-modeles de plugins.
  - [x] Gestionnaire pluggy + hookspec validee.
  - [x] Wrapper copier (run_copy / run_update) + `copier.yml` racine unique.
  - [x] Runner de validateurs (subprocess, erreurs claires, outil absent gere proprement).
  - [x] Verbes CLI cables de bout en bout avec un plugin `demo` interne (tests seulement).
  - [x] Harnais de tests golden (`tests/specs/` -> `tests/golden/`, `pytest --regen-golden`).
  - [x] Tests unitaires : assemblage du spec, enregistrement des plugins.
  - [x] Bonus : controles inter-domaines, `forge diff`, pont WSL, CI GitHub du coeur.
- [x] **Phase 3 — Portage du plugin Ansible** (2026-08-25)
  - [x] ansible-core 2.21.3 + ansible-lint 26.8.0 dans WSL Debian (decision Q7),
        sous `/opt/forge-venv`, avec les collections Galaxy sous `/opt/forge-collections`.
  - [x] Instantane de parite : 319 fichiers, 6 cas -> `tests/parity/ansible/`.
  - [x] Portage gabarits / sous-modele de spec / validateurs / tests selon MIGRATION.md.
  - [x] Catalogue de roles complet : les 7 roles portes, donnees identiques au legacy.
  - [x] Spec golden (`ansible-ci.yml`) couvrant `write_ci`, que la parite ne couvrait pas.
  - [x] MIGRATION.md et PLAN.md mis a jour, commit.
- [ ] **Phase 4 — Portage du plugin Helm**
  - [ ] Instantane de parite si l'outil legacy sait generer.
  - [ ] Portage gabarits (delimiteurs -> `[[ ]]`), sous-modele, validateurs, tests.
  - [ ] Catalogue de composants : deployment+service, ingress, configmap, statefulset,
        cronjob, secret (placeholders), hpa, pdb, serviceaccount+RBAC, networkpolicy.
  - [ ] Revue d'interface : points ou le hookspec/coeur a du plier ; refactor du contrat
        **avec validation humaine** avant tout 3e plugin.
- [ ] **Phase 5 — Valeur inter-domaines**
  - [ ] Verifications de coherence (namespaces Helm vs envs, groupes Ansible vs hosts,
        nom/labels de service identiques partout) avec messages actionnables.
  - [ ] `forge update` (copier update par domaine, `--only`) et `forge diff`.
  - [ ] Tests des deux, dont une mise a jour apres modification deliberee d'un gabarit.
- [ ] **Phase 6 — Finition**
  - [ ] Revue critique : code mort, duplication, cas d'erreur.
  - [ ] README (architecture, guide d'ecriture de plugin, exemples) + section migration.
  - [ ] `examples/` : un spec commite et sa sortie deux domaines.
  - [ ] Suppression de `_legacy/`.
  - [ ] Recapitulatif des changements, commit final.

## Etat courant / prochaine action

**Etat** : phases 0 a 3 terminees. **213 tests verts** sur un depot propre.

Le domaine Ansible est livre et enregistre (`BUILTIN_PLUGINS`) :
`forge new`, `forge generate`, `forge validate` et `forge catalog ansible`
fonctionnent de bout en bout sur un vrai projet Ansible.

**Parite avec le generateur d'origine : 313 fichiers identiques octet pour
octet** sur les 6 cas de l'instantane, aux 12 ecarts documentes pres
(`MIGRATION.md` §7). Et au-dela de la parite : le projet genere passe
`ansible-playbook --syntax-check` sur chaque environnement **et** `ansible-lint`
en profil `production` — ce que la suite legacy n'avait jamais verifie, son
unique test ignore portant precisement la-dessus.

Ce que la phase 2 avait livre :
- `copier.yml` racine unique, delimiteurs `[[ ]]`, cinq questions declarees.
- `src/forge/` : `spec/` (io, service, types, names, assembly), `plugins_api/`
  (hookspecs, manager, types), `render/` (copier_runner, scaffold, diff),
  `validate/` (tools, wsl, runner, consistency), `interview/`, `jinja_ext.py`,
  `pipeline.py`, `cli.py`.
- Plugin `demo` (`src/forge/plugins/demo/`), **jamais enregistre en production** :
  il est charge par `FORGE_PLUGINS=forge.plugins.demo.plugin` et exerce les
  yields imbriques, le filtrage de fichier par `[% if %]`, les filtres de plugin.
- Verbes CLI : `new`, `generate`, `validate`, `update`, `diff`, `plugins`,
  `catalog`, `--version`.
- `tests/` : specs de reference, golden benis, harnais `--regen-golden`.
- CI GitHub (matrice 3.11/3.12/3.13) ; les outils de domaine s'y ajoutent en
  phases 3 et 4.

Revue adversariale du coeur (2026-08-23) : 25 defauts reels confirmes, tous
corriges dans la foulee. Les cinq qui comptent pour la suite :
1. **Normalisation de sortie** — le `rstrip` par ligne et l'ecrasement des
   lignes vides herites du legacy **corrompaient** les scalaires YAML generes.
   Le coeur se limite desormais a `CRLF -> LF` + un saut final
   (`MIGRATION.md` §5, encadre). En phases 3 et 4, un gabarit qui laisse des
   blancs se corrige **dans le gabarit**, jamais dans le coeur.
2. **Noms de domaine** — un plugin nomme `service` ecrasait silencieusement le
   bloc partage du modele assemble. `register()` valide maintenant le nom
   (identifiant minuscule, ni mot-cle, ni nom reserve du modele racine).
3. **`_src_path`** — la reecriture salissait la cible et rendait `forge update`
   impossible ; forge corrige la ligne puis **s'arrete** en demandant le commit.
4. **Chainage `stdin_from`** — un libelle source inexistant produisait un
   « saute » vert ; c'est desormais une `PluginError`. Important pour Helm :
   `kubeconform` lit le rendu de `helm template` par stdin.
5. **Fichiers de niveau depot** — ecrits apres le rendu, jamais ecrases sans
   `--force`, `forge.yml` de la cible preserve avec ses commentaires, index
   calcule sur la specification et non sur `--only`, et compares par
   `forge diff` sous la rubrique `(racine)`.

Ecarts assumes par rapport a `DESIGN.md` §9 (arborescence prevue) :
- ajout de `pipeline.py` (enchainement des operations) pour que `cli.py` ne
  porte aucune logique ; ajout de `interview/service_flow.py`,
  `render/scaffold.py` et `render/diff.py` (SRP, limite de 600 lignes).
- `BUILTIN_PLUGINS` contient `forge.plugins.ansible.plugin` depuis la phase 3.
  Ajouter Helm en phase 4 = une ligne de plus, aucune autre modification du coeur :
  c'est la promesse de DESIGN.md §2.4, tenue.

**Prochaine action** : demarrer la **phase 4 — portage du plugin Helm** dans une
session neuve. Points d'entree : `MIGRATION.md` §4 (classement par artefact) et
§7 (etat du portage Ansible, dont les ecarts a ne pas reproduire) ; `DESIGN.md`
§3 (section `helm:`) et §8 Q6.

Ce que la phase 3 a etabli et qui sert directement a la phase 4 :
- **Le patron de portage d'un gabarit** : conversion mecanique des delimiteurs,
  puis renommage des variables de contexte fichier par fichier, puis boucle sur
  l'instantane de parite jusqu'a zero ecart. Les gabarits Helm sont **deja** en
  `[[ ]]` : la premiere etape est sans objet, ce sera plus court.
- **`partials/header.jinja` a la racine du depot** : macro d'en-tete partagee,
  importable par tout plugin, jamais emise dans la sortie.
- **`domain.role_slots`-like** : un dict `{cle: [item] ou []}` permet a un
  gabarit propre a un composant d'exister sans `[% if %]` dans le chemin.
- **`Command.env`** : les outils Helm auront besoin de `HELM_*` de la meme facon
  qu'Ansible a besoin de `ANSIBLE_COLLECTIONS_PATH`.

Rappels pour la phase 4 :
- Poser le tag `v0.3.0` a la fin de la phase 4 (`v0.2.0` marque la phase 3).
- helm 4.2.4 et kubeconform 0.8.0 sont dans WSL **sous le compte `zedzed`**
  (`/home/zedzed/.local/bin`), pas sous `root` : le pont WSL emploie `root` par
  defaut, il faudra soit `FORGE_WSL_USER=zedzed`, soit `FORGE_WSL_PATH` etendu,
  soit reinstaller ces outils dans `/opt`.
- La **revue d'interface du contrat de plugin** est prevue en fin de phase 4,
  avec validation humaine. Trois points sont deja au dossier : `Command.env`
  (ajoute en phase 3), l'absence de controle croise spec-niveau dans le hookspec
  (le plugin Ansible passe par `forge_consistency`, appele seulement a la
  validation), et la duplication de l'arborescence attendue (`tree.py`).
- Environnement : `.venv` du depot, `uv pip install --python .venv/... -e ".[dev]"`.
  `uv` est installe via `python -m pip install uv` (pas de binaire `uv` sur le PATH).
- Les domaines factices de `tests/domaines_factices/` permettent d'eprouver tout
  ce qui demande **deux** domaines (filtrage `--only`, controles inter-domaines
  en echec, outil de validation absent) sans attendre le plugin Ansible.
- Ecrire les tests d'un gabarit avec l'astuce de
  `tests/test_cli_couverture.py::_depot_de_gabarit` : un depot de gabarit
  temporaire, copie du gabarit courant, qui rend les tests de `forge update`
  independants de l'etat git du depot forge.

## Journal des sessions

- Session 1 (2026-08-23) : phase 0 (amorçage) puis phase 1 (audit + conception).
- Session 2 (2026-08-23) : phase 2 (coeur complet, plugin `demo`, tests golden, CI),
  puis revue adversariale du coeur : 25 defauts confirmes et corriges, suite de
  tests portee de 129 a 179 cas.
- Session 3 (2026-08-25) : phase 3 (plugin Ansible porte a parite integrale,
  50 gabarits convertis, 7 roles, validateurs reels qui passent). 213 tests.
