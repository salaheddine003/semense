# Audit du modèle de prédiction

Date : 31 juillet 2026

## État après correction

Le pipeline d'entraînement a été corrigé après cet audit :

- `YD16QH` et `%MOIS` sont exclus pour empêcher la fuite de cible ;
- `SL_TRIAL`, l'identifiant et le nom du matériel sont exclus pour limiter la
  mémorisation ;
- les hyperparamètres et le seuil sont choisis avec `GroupKFold` par identifiant
  d'essai sur 2015-2017 ;
- 2018 reste un test final temporel intact ;
- le chevauchement d'essais entraînement/test est contrôlé et vaut zéro ;
- l'importance par permutation, les métriques par espèce, la qualité et la
  dérive annuelle sont écrites dans `prediction_report.json`.

Résultat corrigé sur 2018 : accuracy 75,51 %, précision 65,87 %, rappel 91,06 %
et F1 76,45 %. Ces valeurs remplacent le score stratifié de 91,83 % comme
évaluation officielle. La baisse est la conséquence attendue de la suppression
des fuites, pas une régression logicielle.

Les problèmes nécessitant de nouvelles données ne sont pas réparables par
algorithme : météo, sol, conduite culturale, couverture géographique et
représentation des espèces. Les exigences sont dans
`docs/ML_DATA_REQUIREMENTS.md`.

## Conclusion

Le score stratifié de 91,83 % d'accuracy ne constitue pas une estimation fiable
de la performance sur de nouveaux essais. Il est optimiste à cause d'une fuite
de groupes entre entraînement et test et de l'utilisation de `YD16QH`, une
variable presque identique à la cible `YD15QH`.

Le modèle n'est pas inutilisable, mais il doit être présenté comme une preuve de
concept. L'évaluation temporelle et l'évaluation par groupes sont les résultats
à privilégier.

## Résultats comparés

| Protocole | Accuracy | Précision | Rappel | F1 |
|---|---:|---:|---:|---:|
| Split stratifié par ligne | 91,83 % | 90,44 % | 91,30 % | 90,87 % |
| Nouvelle année 2018 | 86,2 % | 80,4 % | 90,4 % | 85,1 % |
| Nouveaux essais, modèle complet | 79,12 % | 74,94 % | 78,41 % | 76,63 % |
| Nouveaux essais, sans `YD16QH` | 67,86 % | 60,03 % | 78,98 % | 68,21 % |
| Nouveaux essais, variables de base | 73,92 % | 66,33 % | 81,77 % | 73,25 % |

## Problèmes détectés

### 1. Fuite entre essais - critique

Dans le split stratifié actuel, 99,95 % des identifiants d'essai présents dans
le test sont aussi présents dans l'entraînement. Pour `SL_TRIAL`, le
chevauchement atteint 100 %. Le modèle voit donc le contexte des essais qu'il
est censé découvrir.

Correction : utiliser `GroupShuffleSplit` ou `GroupKFold` avec
`LK_EXPERIMENT_EXPERIMENT_ID`, ou une séparation temporelle stricte.

### 2. Variable proxy de la cible - critique

La corrélation entre `YD16QH` et `YD15QH` est de 0,999963. Ces variables sont
deux versions très proches du rendement. Utiliser `YD16QH` pour prédire
`YD15QH` peut constituer une fuite de cible si cette mesure n'est pas connue au
moment réel de la prédiction.

Correction : définir précisément l'instant de prédiction et exclure toute
variable calculée pendant ou après la mesure de rendement.

### 3. Surapprentissage - modéré

Avec le split par ligne, le F1 passe de 93,83 % sur l'entraînement à 90,87 % sur
le test. Cet écart seul reste modéré. La chute à 76,63 % sur de nouveaux essais
montre toutefois que le problème principal est la mémorisation du contexte des
essais, davantage qu'un surapprentissage classique visible sur un split
aléatoire.

### 4. Sous-apprentissage et variables manquantes - important

La régression temporelle explique seulement 45,48 % de la variance (`R²=0,4548`).
Il manque des facteurs déterminants : météo, sol, irrigation, fertilisation,
traitements, date de semis et caractéristiques environnementales. Le modèle ne
peut pas apprendre une relation agronomique complète avec les seules colonnes
actuelles.

### 5. Qualité et couverture des données - important

| Champ | Taux manquant dans le jeu de classification |
|---|---:|
| Région | 82,64 % |
| Nom du matériel | 90,72 % |
| `%MOIS` | 54,09 % |
| `YD16QH` | 59,74 % |

La table de faits ne contient aucun doublon complet et `RESULT_NUM` est complet.
Vingt-deux valeurs `YD15QH` sont hors de la plage 0 à 250 et sont exclues de
l'entraînement. La faible couverture géographique provient du manque de
correspondance entre les fichiers ESSAI et RESULTAT.

### 6. Dérive temporelle - important

La proportion de rendements élevés change fortement :

- 2016 : 27,5 %
- 2017 : 52,5 %
- 2018 : 43,6 %

Les performances temporelles changent également : F1 de 58,9 % en 2016,
77,6 % en 2017 et 85,1 % en 2018. Le modèle n'est donc pas stable d'une campagne
à l'autre.

### 7. Performance inégale selon les espèces - important

Sur le test temporel 2018, l'erreur MAE varie :

| Code espèce | N | MAE | Biais moyen |
|---|---:|---:|---:|
| A | 913 | 21,55 | +16,93 |
| B | 1 583 | 13,65 | +4,08 |
| D | 1 161 | 15,27 | +11,70 |
| O | 2 254 | 11,32 | +2,29 |
| T | 1 104 | 12,97 | +0,24 |
| W | 5 291 | 12,23 | +2,66 |

Les codes A et D sont nettement surestimés. Une métrique globale masque cette
faiblesse.

### 8. Déséquilibre et seuil métier - modéré

La classe positive représente 44,52 % du jeu complet : le déséquilibre n'est
pas sévère. En revanche, le seuil de 80 q/ha a été choisi comme hypothèse
technique et doit être validé par un agronome pour chaque espèce. Un seuil
identique peut être inadapté à des cultures aux distributions différentes.

## Plan de correction recommandé

1. Définir la décision métier, l'instant de prédiction et les variables
   réellement disponibles à cet instant.
2. Retirer `YD16QH` et toute variable postérieure à la cible, sauf justification
   métier documentée.
3. Remplacer le split aléatoire par une validation croisée groupée par essai,
   complétée par un test sur la dernière année.
4. Rapporter les métriques globales et par espèce, région et année avec
   intervalles de confiance.
5. Obtenir météo, sol et conduite culturale, puis contrôler leur couverture.
6. Définir des seuils métier par espèce ou prédire d'abord le rendement continu.
7. Ajouter suivi de dérive, calibration des probabilités et réentraînement
   versionné.

## Score à présenter

Pour une démonstration sur des observations historiques similaires, le score
stratifié de 90,87 % de F1 peut être montré avec ses limites. Pour annoncer la
capacité à généraliser, utiliser prioritairement :

- nouvelle année 2018 : accuracy 86,2 %, précision 80,4 %, F1 85,1 % ;
- nouveaux essais : accuracy 79,12 %, précision 74,94 %, F1 76,63 %.

## Vérification des 12 risques ML

| Risque | Verdict | Niveau | Preuve |
|---|---|---|---|
| Surapprentissage | Présent | Important | F1 93,83 % entraînement, 90,87 % test aléatoire, mais 76,63 % sur nouveaux essais |
| Sous-apprentissage | Présent pour la régression | Important | R² temporel limité à 0,4548 et variables agronomiques absentes |
| Qualité des données | Problème | Critique | Région 82,64 % manquante, nom matériel 90,72 %, `%MOIS` 54,09 %, `YD16QH` 59,74 % |
| Biais des données | Présent | Critique | `W` représente 42,2 % des lignes; taux positif de 72,5 % pour `W`, 0,5 % pour `B`, 0 % pour `F` |
| Déséquilibre des classes | Globalement non, localement oui | Important | Classe positive globale 44,52 %, mais déséquilibre extrême par espèce |
| Manque de données | Quantité globale correcte, diversité insuffisante | Important | 55 246 lignes mais seulement 1 952 essais, 4 années et métadonnées environnementales absentes |
| Malédiction de la dimensionnalité | Pas au sens classique | Faible à modéré | 11 features pour 55 246 lignes, mais matériel à 24 442 modalités et `SL_TRIAL` à 1 595 favorisent la mémorisation |
| Dérive des données/concept | Présente | Critique | Taux positif annuel de 27,5 % à 53,5 % et F1 temporel de 58,9 % à 85,1 % |
| Hyperparamètres | Optimisation insuffisante | Important | Réglage manuel; F1 groupé varie de 76,49 % à 78,57 %, le réglage actuel n'est pas le meilleur |
| Coût de calcul | Pas un problème actuel | Faible | Entraînement groupé environ 3,38 s, modèle 2,08 Mo, pipeline complet environ 145 s |
| Interprétabilité | Insuffisante | Important | Gradient boosting sans SHAP, permutation importance ni explications individuelles |
| Fuite de données | Présente | Critique | 99,95 % d'essais partagés et corrélation `YD16QH`/cible de 0,999963 |

## Biais par espèce

Le jeu de classification contient 55 246 lignes et 1 952 essais :

| Espèce | Part des lignes | Taux positif |
|---|---:|---:|
| W | 42,20 % | 72,5 % |
| O | 20,57 % | 30,8 % |
| B | 13,10 % | 0,5 % |
| D | 9,06 % | 21,3 % |
| T | 8,59 % | 44,9 % |
| A | 5,72 % | 30,4 % |
| F | 0,75 % | 0,0 % |

Sur de nouveaux essais, le F1 est notamment de 28,9 % pour A, 28,0 % pour D,
66,8 % pour O, 81,2 % pour T et 82,6 % pour W. Une performance globale ne peut
donc pas être utilisée comme garantie uniforme par culture.

## Hyperparamètres

Quatre configurations de gradient boosting ont été comparées sur un split par
essai. Le F1 maximal varie entre 76,49 % et 78,57 %. La configuration actuelle
n'est pas la meilleure sur ce protocole. Une optimisation avec `GroupKFold`,
suivie d'un test temporel intact, est nécessaire; optimiser directement sur le
test créerait une nouvelle fuite.
