# forge

Generateur deterministe de projets d'infrastructure complets et commentes
(Ansible, Helm, Terraform, monitoring, CI/CD) a partir d'une seule
specification `forge.yml`.

Ce que forge produit n'est pas un squelette a completer : chaque fichier porte un
en-tete disant a quoi il sert, chaque variable exposee est commentee avec ses
valeurs admises, et **le projet genere passe les validateurs reels de son
domaine** — pas un controle interne, les vrais outils.

## Un projet n'a pas besoin de tout

Un projet peut n'avoir besoin que d'un chart Helm. Un autre, que de roles et de
playbooks Ansible. Un troisieme, que d'un socle Terraform, ou que de regles
d'alerte. **C'est vous qui choisissez**, et forge ne produit rien d'autre.

```bash
forge generate -s examples/helm-seul.yml       -o /tmp/boutique    # helm/ seul
forge generate -s examples/ansible-seul.yml    -o /tmp/passerelle  # ansible/ seul
forge generate -s examples/terraform-seul.yml  -o /tmp/socle       # terraform/ seul
forge generate -s examples/monitoring-seul.yml -o /tmp/paiement    # monitoring/ seul
forge generate -s examples/pipeline-seul.yml   -o /tmp/ci          # une chaine de CI seule
```

Ces six exemples sont commites et testes : voir [`examples/`](examples/).

| Domaine | Section | Produit | Valide par |
| --- | --- | --- | --- |
| Ansible | `ansible:` | inventaires, playbooks, roles | `ansible-playbook --syntax-check`, `ansible-lint` (profil production) |
| Helm | `helm:` | chart complet, values par environnement | `helm lint`, `helm template`, `kubeconform -strict` |
| Terraform | `terraform:` | un module, une racine par environnement | `terraform fmt`, `init`, `validate`, `tflint` |
| Monitoring | `monitoring:` | collecte, regles d'alerte, **tests d'alerte** | `promtool check config`, `check rules`, `test rules` |
| Pipeline | `pipeline:` | chaine GitHub Actions ou GitLab CI, a la racine | `actionlint` (GitHub), `yamllint` (GitLab) |

Trois facons de choisir :

| Vous voulez | Vous faites |
| --- | --- |
| un seul domaine | n'ecrivez que sa section dans `forge.yml` — une section absente ne genere rien |
| une execution restreinte | `forge generate --only helm` |
| decider a la creation | `forge new` demande quels domaines produire |

`--only` **restreint** toujours, il n'ajoute jamais : demander un domaine que la
specification ne declare pas est une erreur nommee, pas une generation vide.

`forge plugins -s forge.yml` dit quels domaines sont demandes et lesquels ne le
sont pas ; `forge generate --dry-run` annonce ce qu'il produirait sans rien
ecrire. Une specification qui ne declare aucun domaine ne produit pas un projet
vide en silence : forge dit lesquels sont disponibles et comment en demander un.

Demander plusieurs domaines a la fois est **un** usage possible — forge verifie
alors qu'ils restent coherents entre eux — pas l'usage normal.

## Prise en main

```bash
forge new -o mon-service     # entretien, ecrit forge.yml, puis genere
forge validate -o mon-service
```

L'entretien demande d'abord l'identite du service et ses environnements, puis
**quels domaines generer**, et n'interroge ensuite que sur ceux-la.

| Commande | Role |
| --- | --- |
| `forge new` | entretien interactif — demande quels domaines generer — ecrit `forge.yml` puis genere |
| `forge generate` | rejoue une specification existante |
| `forge validate` | validateurs de chaque domaine + coherence inter-domaines |
| `forge update` | applique les evolutions de gabarit sans ecraser vos modifications |
| `forge diff` | resume l'ecart entre la cible et un rendu neuf |
| `forge plugins` | domaines enregistres et etat des outils externes |
| `forge catalog <domaine>` | catalogue publie par un plugin, pieges compris |

`forge catalog <domaine> <element>` est plus qu'une liste : chaque famille de
ressources y documente ses **pieges mesures** — pourquoi un ResourceQuota casse
un chart qui ne declare pas ses `requests`, pourquoi une NetworkPolicy sans
ouverture DNS coupe toute resolution de nom, pourquoi un seau `+Inf` fait mentir
un quantile.

## Architecture

### Le coeur ne connait aucun domaine

`src/forge/` sait charger une specification, appeler copier, executer des
commandes et comparer des projections. Il ne sait pas ce qu'est un namespace, un
role ou un histogramme. Toute connaissance de domaine vit dans
`src/forge/plugins/<domaine>/`.

Cette separation n'est pas decorative : **ajouter un domaine a coute une ligne
du coeur** — l'entree de `BUILTIN_PLUGINS`. C'est verifie a chaque ajout, et les
deux derniers domaines l'ont confirme.

```
src/forge/
├── spec/           # bloc `service:` partage, assemblage du modele racine
├── plugins_api/    # le contrat : hookspecs, types echanges, registre
├── render/         # invocation de copier, fichiers de niveau depot, diff
├── validate/       # execution des commandes, pont WSL, controles inter-domaines
├── interview/      # protocole de saisie, rejouable en test
├── pipeline.py     # enchainement des operations, sans terminal
├── cli.py          # lecture d'arguments et affichage, rien d'autre
└── plugins/        # ansible/ helm/ terraform/ monitoring/  (+ demo/, hors production)
```

### Ce que copier fait, et pourquoi

Le rendu passe **toujours** par copier, jamais par une ecriture de fichier en
dur. C'est ce qui rend `forge update` possible : un projet livre il y a six mois
recoit les evolutions du gabarit sans perdre les reglages faits a la main.

Consequence sur les gabarits : ils emploient les delimiteurs `[[ ]]`, `[% %]` et
`[# #]`, jamais `{{ }}`. Helm et Ansible ecrivent tous deux `{{ ... }}` dans
leurs propres fichiers ; avec les delimiteurs par defaut, chaque gabarit aurait
demande un bloc `raw`. Ici, `{{ .Values.image.tag }}` traverse le rendu sans
etre touche.

### Comment deux domaines se rencontrent sans se connaitre

Aucun plugin ne lit la section d'un autre. Quand deux domaines doivent
s'accorder, ils declarent une **facette** — un fait, dans un vocabulaire
partage — et le coeur compare :

| Facette | Ce qu'elle designe | Declaree par |
| --- | --- | --- |
| `namespaces` | cloisons ou le service vit | terraform, helm, monitoring |
| `ingress_hosts` | noms par lesquels le service est joignable de l'exterieur | helm, monitoring |
| `inventory_hosts` | machines nommees dans un inventaire | ansible |
| `groups` | regroupements de machines partageant un role | ansible |

Terraform cree le namespace, Helm y deploie, le monitoring le regarde : si les
trois cessent de le nommer pareil, `forge validate` le dit — sans qu'aucune
regle « si terraform alors helm » n'existe nulle part.

Le vocabulaire est **ferme** : le coeur ne compare que les facettes qui y
figurent. Une facette hors vocabulaire est sans danger, mais sans effet. La
regle vient d'un vrai faux positif : Ansible et Helm declaraient tous deux
`hosts`, pour des choses sans rapport.

### Le domaine qui federe les autres sans les connaitre

Le domaine `pipeline` est le seul dont la sortie **depend des autres sections**.
Il engendre un job de validation par domaine declare, avec les commandes que
chaque domaine annonce lui-meme et l'installation des outils qu'elles exigent.
Ajouter une section a `forge.yml` ajoute un job, sans qu'une ligne de gabarit
change.

Le coeur ne devient pas un ordonnanceur pour autant : il assemble un
`GenerationContext` a partir de hooks qu'il appelait deja — `DomainInfo`,
`Command`, `Projection` — et n'en tire aucune conclusion. Le plugin `pipeline`
ne contient aucun nom de domaine ; un domaine factice qu'il n'a jamais vu obtient
son job, et c'est un test qui le prouve.

Trois traductions y demandent du soin, et chacune est verrouillee par un test :

- **le chainage par stdin** devient une redirection par fichier, jamais un tube :
  `pipefail` n'existe pas dans le `/bin/sh` d'une image Debian, et un tube y
  masquerait l'echec de la commande source ;
- **l'ordre de deploiement** suit `DomainInfo.deploy_order`, pas l'alphabet —
  sans quoi le chart partirait avant le Terraform qui cree son namespace ;
- **les variables d'environnement locales** sont ecartees : un chemin de cache
  calcule sur le poste n'a aucun sens sur un runner, et le graver rendrait la
  sortie dependante de la machine qui l'a engendree.

Un domaine qui ne declare pas comment se deployer est **nomme** dans le fichier
engendre, jamais devine. De meme pour un outil que la table d'installation ne
connait pas : l'etape echoue en le nommant, plutot que de laisser le job tomber
plus loin sur un « command not found ».

## Ecrire un plugin de domaine

Un plugin est un module Python exposant des `@hookimpl`. Un seul hook est
obligatoire.

| Hook | Obligatoire | Role |
| --- | --- | --- |
| `forge_domain()` | **oui** | identite du domaine : nom, titre, resume, repertoire de sortie |
| `forge_spec_model()` | oui en pratique | sous-modele pydantic validant la section `<domaine>:` |
| `forge_template_subdir()` | oui en pratique | chemin du gabarit copier |
| `forge_answers(spec, context)` | oui en pratique | projette la spec vers le dict `domain` que les gabarits lisent ; `context` decrit les autres domaines demandes, et un plugin qui n'en a pas besoin ne declare pas le parametre |
| `forge_check_spec(spec)` | non | controles que le sous-modele ne peut pas faire — il ne voit pas `service:` |
| `forge_validators(spec, outdir)` | non | commandes externes validant le projet genere |
| `forge_deploy(spec, outdir, env)` | non | comment ce domaine se deploie. Le coeur ne l'execute **jamais** : ces commandes n'existent que pour etre ecrites dans un pipeline |
| `forge_projection(spec)` | non | ce que le domaine affirme produire, pour la comparaison de facettes |
| `forge_interview(prompter, service)` | non | questionnaire de `forge new` |
| `forge_catalog()` | non | catalogue consultable par `forge catalog` |
| `forge_consistency(spec, outdirs)` | non | echappatoire : controles sur le projet **deja ecrit** |

### La marche a suivre

1. **`spec.py`** — un modele pydantic heritant de `ForgeModel` (`extra="forbid"` :
   une cle inconnue est une faute de frappe, jamais un silence). Refusez tot ce
   qui ne se verra que tard : une contrainte de version sans borne haute, un
   backend sans sa cle obligatoire, un delai de collecte superieur a son
   intervalle.
2. **`catalog/`** — les familles de ce que le domaine sait produire, avec leurs
   pieges. C'est la connaissance metier ; le reste n'est que plomberie.
3. **`derive.py` / `answers.py`** — la projection vers le dict `domain`. Elle
   doit etre **JSON-serialisable et deterministe** : elle est ecrite telle quelle
   dans `.copier-answers.yml` et rejouee par `copier update`. Aucun objet
   pydantic, aucun `set`, aucun chemin absolu.
4. **`template/`** — les gabarits, delimiteurs `[[ ]]`.
5. **`tree.py`** — la liste des chemins produits, pour que le README genere ne
   mente pas. Un test la confronte au rendu reel.
6. **`validators.py`** — les commandes reelles. Un domaine dont la sortie n'est
   verifiee par rien n'est pas fini.
7. Une ligne dans `BUILTIN_PLUGINS`, une specification de reference dans
   `tests/specs/`, un exemple mono-domaine dans `examples/`.

### Trois pieges qui ont mordu

- **Ne lisez jamais une cle en notation pointee quand elle porte le nom d'une
  methode de dict.** En Jinja, `objet.values` resout la methode avant la cle, et
  le gabarit ecrit `<built-in method values...>` dans le fichier genere. La forme
  sure est `objet["values"]`. Deux tests l'imposent, l'un sur la source des
  gabarits, l'autre sur la sortie.
- **Gardez les noms de gabarit courts.** Windows plafonne un chemin a 260
  caracteres, et copier clone le depot dans un repertoire temporaire avant de
  rendre. Un nom portant deux balises `yield` explicites depasse la limite ;
  employez des listes de noms courtes et relisez l'entree complete dans le corps
  du fichier.
- **N'ecrivez jamais dans un fichier genere une valeur lue dans l'environnement
  du processus.** Un chemin de cache calcule sur le poste de developpement rend
  la sortie dependante de la machine, et le test golden ne peut plus comparer.

### Le motif des emplacements

Un gabarit propre a un element existe sans qu'un `[% if %]` figure dans son
chemin : la projection expose un dict `{cle: [element] ou []}`, et la balise
`yield` de copier decide d'ecrire ou non. Les quatre domaines l'ont invente
separement ; c'est devenu une convention.

## Ce qui garantit la sortie

**Meme specification, meme sortie, octet pour octet.** Des tests golden
comparent chaque rendu a une reference commitee. Ils attrapent aussi bien un
changement voulu qu'un non-determinisme accidentel.

**Le projet genere passe les validateurs reels de son domaine.** Les cinq
specifications de reference declenchent **31 commandes externes**, lancees par
la suite de tests sur de vrais projets rendus. Ce ne sont pas des controles
internes : ce sont les outils que l'utilisateur lancera.

Un cas merite d'etre souligne : le domaine monitoring livre, avec chaque regle
d'alerte, le **test unitaire** qui prouve qu'elle se declenche —
`promtool test rules` fabrique une serie temporelle synthetique et verifie que
l'alerte apparait avec les bons libelles. C'est le seul validateur du projet qui
verifie quelque chose de semantique : une regle d'alerte peut etre
syntaxiquement irreprochable et rester muette pour toujours.

Sous Windows, les outils qui n'existent pas nativement sont cherches dans une
distribution WSL. La CI Linux fait autorite.

## D'ou vient forge

forge est le portage de deux generateurs autonomes, `ansible-forge` et
`helm-forge`, qui partageaient un modele de specification, un moteur Jinja, un
harnais de tests golden et une CLI — en double.

Le portage a ete conduit a la **parite octet**, sur des instantanes figes de la
sortie d'origine : 313 fichiers cote Ansible, 32 cote Helm. Cette parite a servi
tout le temps du portage, puis a ete retiree, avec le code d'origine, une fois
qu'elle mesurait une ressemblance a des outils qui n'existent plus — et que le
projet genere l'avait depassee. Le chart Helm compte neuf familles de ressources
que l'outil d'origine n'a jamais eues ; le projet Ansible passe `ansible-lint` en
profil production, ce que la suite d'origine n'avait jamais verifie.

`MIGRATION.md` conserve le releve complet : les doublons fusionnes, les
arbitrages rendus, et les ecarts assumes.

## Installation et tests

```bash
uv venv
uv pip install --python .venv/Scripts/python.exe -e ".[dev]"
```

Sous Linux et macOS, remplacez `.venv/Scripts/python.exe` par
`.venv/bin/python`. Si `uv` n'est pas sur le PATH, il s'installe avec
`python -m pip install uv` puis s'invoque par `python -m uv`.

```bash
.venv/Scripts/python.exe -m pytest                        # tout
.venv/Scripts/python.exe -m pytest -m "not integration"   # sans les outils externes
```

Les tests marques `integration` lancent les validateurs reels et s'ignorent si
l'outil est absent — nativement comme dans WSL. La CI les installe tous : une
suite verte y veut donc dire que les projets generes sont valides.

Les references golden se regenerent avec `pytest --regen-golden`, a ne faire
qu'apres avoir constate que l'ecart est voulu : la commande **enterine** la
sortie courante, elle ne la verifie pas.

Un test est ignore tant que le depot porte des modifications non committees :
`copier update` compare deux references git, et un rendu fait depuis un arbre de
travail sale reference un commit temporaire introuvable ensuite.

## Documents

| Fichier | Contenu |
| --- | --- |
| `CHANGELOG.md` | what changed in generated output, and what `forge update` asks of you |
| `DESIGN.md` | architecture detaillee, contrat de plugin, decisions arbitrees |
| `MIGRATION.md` | releve du portage : doublons fusionnes, arbitrages, ecarts |
| `PLAN.md` | avancement phase par phase, et ce que chacune a etabli |
| `examples/` | cinq specifications commentees, toutes generees par la suite de tests |
