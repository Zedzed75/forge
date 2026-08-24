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
- [ ] **Phase 3 — Portage du plugin Ansible**
  - [ ] `pipx install ansible-core ansible-lint` dans WSL Debian (decision Q7).
  - [ ] Instantane de parite : generation legacy -> `tests/parity/ansible/`.
  - [ ] Portage gabarits / sous-modele de spec / validateurs / tests selon MIGRATION.md.
  - [ ] Catalogue de roles complet : common, users, ssh_hardening, firewall, nginx, docker,
        postgresql (portage d'abord, puis roles manquants un par un).
  - [ ] Spec golden + benediction des references une fois la parite atteinte.
  - [ ] MIGRATION.md et PLAN.md mis a jour, commit.
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

**Etat** : phases 0, 1 et 2 terminees, **puis auditees et corrigees**. Le coeur
est ecrit, teste et domaine-agnostique : **179 tests verts** sur un depot propre.
Un seul test est ignore tant que le gabarit porte des modifications non
committees (cf. `MIGRATION.md` §2.10) ; les autres tests de mise a jour
fabriquent leur propre depot de gabarit temporaire et tournent toujours.

Ce que la phase 2 a livre :
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
- `BUILTIN_PLUGINS` est vide : l'enregistrement en dur des plugins reels se fait
  en phases 3 et 4, une ligne par domaine, sans autre modification du coeur.

**Prochaine action** : demarrer la **phase 3 — portage du plugin Ansible** dans
une session neuve. Points d'entree : `MIGRATION.md` §3 (classement par artefact),
§2 (contraintes copier) et §5 (fusions deja faites, a ne pas refaire) ;
`DESIGN.md` §5.3 (arbitrage `yield` vs `[% if %]` sur les roles).

Rappels pour la phase 3 :
- `pipx install ansible-core ansible-lint` dans WSL Debian est le tout premier
  point (decision Q7) ; sans cela, seule la CI valide.
- Le tag `v0.1.0` marque la fin de la phase 2 (decision Q8 : un tag par phase,
  pour offrir des points d'update stables). Poser `v0.2.0` a la fin de la phase 3.
- Les gabarits Ansible s'ecrivent en `[[ ]]` ; `{{ }}` y designe **toujours** du
  Jinja destine a Ansible, ecrit litteralement (plus de `j()`/`jstr()`, plus de
  `{% raw %}`).
- Le filtre `comment` a change de signature (cf. `MIGRATION.md` §5) : passer la
  largeur en argument nomme.
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
