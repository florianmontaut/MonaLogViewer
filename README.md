# Documentation du MonaLogViewer passé sur Git



\#Initialisation du dépôt
'''bash
git init
git remote add origin SSH\_REPO
'''



\#Rev01 / Amélioration de la propagation checkState dans le TreeView / :

FNT 01/08

¤ utilisation des méthodes update\_signals\_visibility et update\_signal\_visibility du graph\_controller afin d'améliorer le temps de mise à jour de la visibilité des signaux. (freeze\_updates du graphe est primordial)

On passe d'un délai de 1/2 secondes à <100ms.

¤ modification de la méthode add\_file\_subtree() et ajout de la méthode \_add\_signal\_subtree\_silent afin de corriger l'ancien code qui ajoutait les nouveaux fichiers .csv à la racine de l'arborescence au lieu de les rajouter à files\_root.

¤ Ajout des méthodes \_set\_group\_visibility(), \_set\_file\_visibility(), \_emit\_check\_state\_updates(), \_emit\_items\_for\_signal\_changed(), \_emit\_children\_check\_state\_changed() et \_emit\_check\_state\_refresh\_for\_item() par intégration du code venant de copilot. Vérifier l'intérêt de tout ce code

&#x09;

&#x09;

