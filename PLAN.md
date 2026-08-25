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
- [x] **Phase 4 — Portage du plugin Helm** (2026-08-25)
  - [x] Instantane de parite : 32 fichiers, 2 cas -> `tests/parity/helm/`.
  - [x] Portage gabarits, sous-modele, validateurs, entretien, tests.
  - [x] Catalogue de composants **complet** : les 13 familles, dont les 9 creees
        (ingress, configmap, statefulset, cronjob, secret, hpa, pdb,
        serviceaccount+RBAC, networkpolicy).
  - [x] **Revue d'interface : arbitree (2026-08-25).** R2 -> nouveau hook
        `forge_check_spec`, appele avant tout rendu ; R3 -> `tree.py` reste au
        plugin, tenu a jour par un test obligatoire dans chaque domaine.
        R1, R4, R5, R6, R7 enterines et documentes.
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

**Etat** : phases 0 a 4 terminees, revue d'interface comprise. **245 tests
verts** sur un depot propre.

Les deux domaines sont livres et enregistres (`BUILTIN_PLUGINS`) : `forge new`,
`forge generate`, `forge validate`, `forge diff` et `forge catalog <domaine>`
fonctionnent de bout en bout sur un vrai projet Ansible **et** sur un vrai chart
Helm.

Helm : **parite 32/32** avec le generateur d'origine, **plus neuf familles de
ressources creees** que le legacy n'avait jamais eues. Le chart complet passe
`helm lint`, `helm template` sur chaque environnement et `kubeconform -strict`.
Cinq defauts ont ete trouves par la complementation elle-meme et corriges
(cf. `MIGRATION.md` §7) — dont un StatefulSet prive de son Service headless,
qu'aucun validateur ne pouvait voir.

Ansible : **parite 313/313** sur les 6 cas de l'instantane, aux ecarts
documentes pres (`MIGRATION.md` §7). Et au-dela de la parite, le projet genere passe
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

## Revue d'interface — releve pour arbitrage humain

`PLAN.md` reservait cette revue a une validation humaine, avant tout 3e plugin.
**Arbitrage rendu le 2026-08-25** : R2 et R3 tranches comme recommande, les cinq
autres constats enterines. Le tableau reste ici comme releve de decisions — ne
pas le rouvrir sans raison nouvelle.

| # | Constat | Recommandation |
|---|---|---|
| R1 | **`Command.env` a ete ajoute en cours de route** (phase 3). `DESIGN.md` §2.1 decrivait `Command` sans ce champ. Sans lui, `ANSIBLE_COLLECTIONS_PATH` etait intransmissible et `--syntax-check` echouait sur des modules que `requirements.yml` declare pourtant ; Helm s'en sert pour `KUBECONFORM_SCHEMA_LOCATION`. | **Entériner** : deux domaines sur deux en ont eu besoin. Mettre `DESIGN.md` §2.1 a jour. |
| R2 | **ARBITRE : hook ajoute.** **Le contrat n'avait pas de controle croise au niveau du modele.** Un sous-modele de plugin ne voit que sa section : ni Ansible ni Helm ne peut verifier seul que les environnements qu'il cite existent dans `service.environments`. Les deux passent par `forge_consistency`, qui n'est appele qu'a `forge validate` — **pas a `forge generate`**. Une specification incoherente est donc generee sans broncher, et l'erreur ne sort qu'au `validate` suivant. | **Ajouter un hook** `forge_check_spec(spec) -> list[Issue]`, appele par le coeur juste apres l'assemblage du modele, donc avant tout rendu. `forge_consistency` resterait pour ce qui a besoin des fichiers ecrits. |
| R3 | **ARBITRE : laisse au plugin, avec test obligatoire.** **La liste des fichiers a ecrire est dupliquee dans chaque plugin** (`ansible/tree.py`, `helm/tree.py`). copier ne sait pas dire a l'avance ce qu'il va produire, et les deux domaines affichent une arborescence dans leur README. Un gabarit ajoute sans mise a jour de `tree.py` rend le README faux — un test l'attrape cote Ansible, la lecon a ete apprise deux fois. | **Service du coeur** : un rendu « a blanc » dans un tmpdir donne la liste exacte. Le coeur pourrait l'exposer aux gabarits (`domain.tree`) au lieu que chaque plugin la redevine. |
| R4 | **Les deux plugins ont invente le meme idiome, separement** : `domain.role_slots.<role>` et `domain.component_slots.<famille>`, un dict `{cle: [item] ou []}` qui permet a un gabarit propre a un element d'exister sans `[% if %]` dans le chemin. | **Documenter comme motif** dans `DESIGN.md` §5.3. Ne pas l'imposer dans le coeur : c'est une convention de gabarit, pas une API. |
| R5 | **`.copier-answers.yml` grossit.** Il porte l'integralite du dict `domain` : ~23 Ko sur le cas Ansible le plus riche. C'est voulu (decision Q3 : lisible, versionne, relu), mais personne n'avait chiffre. | **Laisser tel quel**, et le dire dans `DESIGN.md` §8 Q3. L'alternative — n'y mettre que la spec — casserait `copier update`. |
| R6 | **`DomainInfo.outdir` n'a jamais servi** : les deux domaines emploient le defaut (`ansible/`, `helm/`). | **Garder** : le champ coute une ligne et un domaine tiers en aura besoin (`terraform/environments/` par exemple). |
| R7 | **L'entretien demande deux fois son avis a l'utilisateur** : le coeur demande quels domaines generer, puis le plugin peut encore decliner en retournant `None`. Ansible s'en sert (aucun groupe nomme), Helm aussi (aucun composant). | **Garder**, mais le dire dans le hookspec : le `None` du plugin ne signifie pas « l'utilisateur refuse le domaine », il signifie « il n'y a rien a generer ». |

**Prochaine action** : demarrer la **phase 5 — valeur inter-domaines** dans une
session neuve. Points d'entree : `MIGRATION.md` §4 (classement par artefact) et
§7 (etat du portage Ansible, dont les ecarts a ne pas reproduire) ; `DESIGN.md`
§3 (section `helm:`) et §8 Q6.

Ce que les phases 3 et 4 ont etabli, et qui sert a la phase 5 :
- **Le patron de portage** : instantane de parite fige d'abord, conversion
  ensuite, boucle jusqu'a zero ecart. Il a tenu deux fois.
- **La parite ne se degrade pas quand on ajoute**, a condition d'ecrire les
  ajouts de facon inerte pour les cas figes. C'est ce qui a permis de creer neuf
  familles Helm sans perdre un seul des 32 fichiers de reference.
- **Les validateurs reels trouvent ce que les tests ne voient pas**, et
  reciproquement : ansible-lint a trouve 255 violations dans un fichier que la
  parite declarait parfait ; le test de rendu complet a trouve un StatefulSet
  prive de son Service, qu'aucun validateur ne pouvait voir.

Rappels pour la phase 5 :
- Poser le tag `v0.4.0` a la fin de la phase 5 (`v0.3.0` marque la phase 4).
- Les deux domaines declarent deja des facettes comparables : Ansible expose
  `hosts` et `groups`, Helm expose `hosts` et `namespaces`. La comparaison
  generique du coeur (`validate/consistency.py`) est ecrite mais n'a jamais eu
  deux domaines a comparer sur une meme specification : c'est le coeur de la
  phase 5.
- `forge update` et `forge diff` existent depuis la phase 2 et sont testes ; la
  phase 5 demande d'y ajouter le test d'une mise a jour **apres modification
  deliberee d'un gabarit** — le motif du depot de gabarit temporaire
  (`tests/test_cli_couverture.py::_depot_de_gabarit`) le permet deja.

## Journal des sessions

- Session 1 (2026-08-23) : phase 0 (amorçage) puis phase 1 (audit + conception).
- Session 2 (2026-08-23) : phase 2 (coeur complet, plugin `demo`, tests golden, CI),
  puis revue adversariale du coeur : 25 defauts confirmes et corriges, suite de
  tests portee de 129 a 179 cas.
- Session 3 (2026-08-25) : phase 3 (plugin Ansible porte a parite integrale,
  50 gabarits convertis, 7 roles, validateurs reels qui passent). 213 tests.
- Session 4 (2026-08-25) : phase 4 (plugin Helm porte a parite 32/32, puis neuf
  familles de ressources creees ; 5 defauts trouves par la complementation),
  puis revue d'interface arbitree : hook `forge_check_spec` ajoute, `tree.py`
  laisse au plugin sous test obligatoire. 245 tests.
