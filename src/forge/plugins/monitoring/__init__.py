"""Plugin de domaine monitoring : sondes, regles d'alerte et leurs tests.

Domaine autonome : il ne lit **aucune** autre section de forge.yml. Ce qu'il
surveille, il le declare lui-meme ; la coherence avec les autres domaines passe
par le vocabulaire des facettes (`namespaces`, `ingress_hosts`), verifie par
`forge validate`. C'est le meme mecanisme que pour Helm et Terraform, et il ne
demande aucun couplage.

Particularite du domaine : `promtool` sait faire tourner des **tests unitaires
d'alerte** — donner une serie temporelle synthetique et verifier que l'alerte se
declenche avec les bons libelles. forge en engendre un par famille de regles.
Une regle d'alerte non testee est une regle dont personne ne sait si elle se
declenche, et on ne l'apprend que le jour ou elle aurait du le faire.
"""
