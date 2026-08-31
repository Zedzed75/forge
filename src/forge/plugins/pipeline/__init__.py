"""Plugin de domaine pipeline : la chaine d'integration et de deploiement.

Le domaine qui **federe les autres sans les connaitre**. Il n'y a pas une seule
occurrence de « ansible », « helm » ou « terraform » dans ce paquet, hors
documentation : tout ce qu'il sait des autres domaines lui arrive par le
`GenerationContext` que le coeur assemble a partir de hooks deja existants.
"""
