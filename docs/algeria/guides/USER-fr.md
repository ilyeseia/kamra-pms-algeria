# ZIRI PMS — Guide du personnel

Pour les réceptionnistes, les auditeurs de nuit, les femmes et valets de
chambre, les caissiers et le personnel de restaurant. Ce guide couvre les
gestes de chaque service. Aucune connaissance technique n'est nécessaire.

ZIRI PMS fonctionne dans un navigateur web. Il n'y a rien à installer sur
votre poste ni sur votre téléphone.

---

## 1. Se connecter et choisir sa langue

Ouvrez l'adresse que l'hôtel vous a communiquée. Elle se termine par
`/kamra` — par exemple `http://localhost:8080/kamra`. C'est simplement le nom
interne du programme ; saisissez l'adresse exactement telle qu'elle vous a
été donnée.

**Pour vous connecter :**

1. Ouvrez l'adresse de l'hôtel dans le navigateur.
2. Saisissez votre **E-mail ou nom d'utilisateur** et votre
   **Mot de passe**.
3. Appuyez sur **Se connecter**.

Si vous lisez « E-mail, nom d'utilisateur ou mot de passe incorrect. »,
vérifiez les majuscules et l'absence d'espace en fin de saisie. Si vous lisez
« Votre session a expiré. Reconnectez-vous pour reprendre où vous en
étiez. », vous avez simplement été déconnecté après une longue inactivité :
reconnectez-vous.

### Choisir sa langue

Trois langues sont proposées : **English**, **Français** et **العربية**.

- L'écran de connexion comporte un sélecteur **Langue**. Réglez-le avant de
  vous connecter si vous le souhaitez.
- Une fois connecté : **Paramètres → Apparence → Langue**.

Choisir **العربية** fait passer toute l'interface de droite à gauche : le
menu passe à droite de l'écran, les tableaux et les boutons se reflètent.
L'écran l'annonce : « L'arabe fait passer l'interface de droite à gauche · ce
navigateur uniquement ».

La langue est enregistrée dans le navigateur utilisé, pas dans votre compte.
Le poste de la réception peut donc rester en français pendant que votre
téléphone est en arabe. Si vous vous connectez sur un autre poste, réglez la
langue à nouveau.

### Se déconnecter

Barre du haut → **Se déconnecter**.

---

## 2. Se repérer

ZIRI PMS est découpé en **applications**. La barre du haut indique celle où
vous êtes ; **Changer d'application** permet de passer d'une à l'autre, et
**Voir toutes les applications** les affiche toutes sur une page. Vous ne
voyez que celles que votre rôle autorise.

| Application | À quoi elle sert |
| --- | --- |
| **Réception** | Arrivées, départs, réservations, clients |
| **Ménage** | Tableau des chambres, tâches, blanchisserie, objets trouvés, application mobile |
| **Exploitation** | Demandes clients, WhatsApp |
| **Restauration** | Caisse restaurant, écran cuisine, la carte |
| **Banquets et groupes** | Événements, salles, groupes |
| **Chiffre d'affaires** | Tarifs, saisons, offres, partenaires |
| **Finances** | Caisse, folios, audit de nuit, grands livres |
| **Moteur de réservation** | La page de réservation directe de l'hôtel |
| **Administration** | Paramétrage de l'établissement, chambres, utilisateurs |

### La recherche

**Ouvrir la recherche** dans la barre du haut, ou **Ctrl + K**
(**Cmd + K** sur Mac). Saisissez un nom de client, une réservation, un numéro
de chambre : « Rechercher réservations, clients, chambres… ». La recherche
ouvre aussi n'importe quel écran. C'est le chemin le plus rapide ; inutile de
fouiller les menus.

### Les écrans que vous utiliserez le plus

| Écran | Où | Ce que vous y faites |
| --- | --- | --- |
| **Aujourd'hui** | Réception | Toute la journée : arrivées, départs, clients en séjour, tableau des chambres |
| **Planning des chambres** | Réception | Qui occupe quelle chambre physique, sur plusieurs dates |
| **Réservations** | Réception | La liste des réservations |
| **Clients** | Réception | Les fiches clients et leurs séjours passés |
| **Fiche de police** | Depuis une arrivée | Le registre légal des clients |
| **Tableau des chambres** | Ménage | Le statut de propreté de chaque chambre |
| **Facturation** | Finances | Tous les folios ouverts, et l'audit de nuit |
| **Ma caisse** | Finances | Votre caisse |
| **Caisse restaurant** | Restauration | La prise de commande |
| **Écran cuisine** | Restauration | Le passe cuisine |

### Si la connexion tombe

Un bandeau affiche « Connexion perdue — reconnexion… ». Attendez qu'il
disparaisse. Ne resaisissez rien : l'écran se reconnecte seul et se
rafraîchit.

---

## 3. La réception

### Aujourd'hui — la journée d'un coup d'œil

**Aujourd'hui** est l'écran d'accueil (**Réception → Aujourd'hui**). Il se
rafraîchit toutes les trente secondes. Il affiche :

- **Arrivées** — qui est attendu
- **Départs** — qui doit partir
- **Clients en séjour** — qui dort à l'hôtel cette nuit
- **Tableau des chambres** — chaque chambre et son statut de propreté
- **Occupation**, **Chiffre d'affaires** et **Tâches ouvertes** en haut

Chaque ligne de séjour porte une pastille issue du folio : **Réglé**, un
montant dû, ou **Non réglé**. Lisez cette pastille avant de laisser partir un
client.

Une ligne d'arrivée affiche également :

- **Fiche de police** — ouvre la fiche d'enregistrement
- **copier le lien d'enregistrement** — copie le lien d'enregistrement en
  ligne du client pour que vous puissiez le lui envoyer. Survolez-le : il
  vous dit si le lien doit partir vers le client ou vers la personne qui a
  réservé.
- **Pré-enregistré** — le client a déjà saisi ses informations en ligne

### Enregistrer l'arrivée d'un client

1. **Réception → Aujourd'hui → Arrivées**, repérez la ligne du client.
2. Appuyez sur **Enregistrer l'arrivée**.
3. Le volet d'arrivée s'ouvre. Si une chambre est attribuée, il indique
   « La chambre {num} est attribuée » ; sinon appuyez sur **Choisir une
   chambre** (ou **Ou choisissez une autre chambre** pour en changer).
4. Renseignez le **Type de pièce d'identité** et le **Numéro de la pièce
   d'identité** s'ils ne sont pas au dossier.
5. Appuyez sur **Enregistrer l'arrivée en chambre {chambre}**.

À savoir :

- Si la chambre n'est pas encore faite, le volet avertit que la chambre
  « n'a pas encore été nettoyée ». Vous pouvez tout de même enregistrer
  l'arrivée — le ménage verra la chambre passer en occupée — mais
  prévenez-le.
- S'il n'y a plus de chambre libre de ce type, le volet le dit et vous
  renvoie vers le planning des chambres pour un transfert ou un
  surclassement.
- La saisie de la pièce d'identité ne bloque jamais l'arrivée. Mais le
  registre des clients l'attend **avant l'audit de nuit**.

### Un client sans réservation

1. Appuyez sur **Nouvelle réservation** (en haut à droite, depuis n'importe
   quel écran).
2. Réglez le **Mode de réservation** sur **Sans réservation** — « Un client
   sans réservation arrive aujourd'hui ». Cela crée le séjour, enregistre
   l'arrivée et encaisse en une seule étape : « Réserver, enregistrer
   l'arrivée et encaisser en une seule étape ».
3. Saisissez le **Nom du client**, le **Téléphone**, le **Type de chambre**,
   les **Nuits**, les **Adultes** / **Enfants** et l'**Arrangement**. Le
   **Devis** se recalcule au fur et à mesure.
4. Indiquez ce que vous encaissez sous **Montant encaissé** et le **Mode de
   paiement**.
5. Appuyez sur **Enregistrer l'arrivée et encaisser {montant}** — ou sur
   **Enregistrer l'arrivée** si vous n'encaissez rien : tout reste alors sur
   la note.

### La fiche de police

C'est le registre légal des clients. Ouvrez-la depuis le bouton **Fiche de
police** de la ligne d'arrivée, ou depuis **Ouvrir la fiche de police** dans
le volet d'arrivée. L'en-tête imprimé indique **FICHE DE POLICE**.

1. Vérifiez le **Nom**, le **Téléphone**, l'**Adresse**, la **Nationalité**
   et la **Pièce d'identité**. Appuyez sur **edit** à côté de
   **Nationalité** pour la corriger : elle s'imprime ensuite aussi sur le
   folio et sur la facture.
2. Sous **Occupants**, inscrivez **toutes** les personnes qui dorment dans la
   chambre, pas seulement celle qui a réservé. Le compteur lit
   « Occupants enregistrés ({n} sur {pax}) » : il ne doit pas être incomplet.
3. Ajoutez la pièce d'identité et la nationalité de chaque occupant dans
   cette même liste.
4. Appuyez sur **Imprimer la fiche de police**.
5. Faites signer le client — sur la fiche imprimée, ou à l'écran sous
   **Signature du client** s'il est devant vous. Un client enregistré en
   ligne apparaît comme **Signé en ligne**.
6. Signez vous-même la ligne **Réception (nom et signature)**.

La liste **Pièce d'identité** propose : **Carte nationale d'identité**,
**Passeport**, **Permis de conduire**, **Residence Permit** et **Autre**.
« Residence Permit » s'affiche aujourd'hui en anglais même lorsque le reste
de l'interface est en français : il s'agit du titre de séjour.

La fiche porte aussi l'**Arrivée effective** / le **Départ effectif**,
**Attribuer une chambre** / **Changer de chambre**, et **Note ouverte** pour
sauter directement au folio.

### Enregistrer un départ

1. **Réception → Aujourd'hui → Départs**, repérez la ligne.
2. Lisez la pastille de règlement. S'il reste dû, réglez d'abord — voir la
   section 5.
3. Appuyez sur **Enregistrer le départ**.

Le départ impute au passage les nuitées qui n'avaient pas encore été
imputées : la note finale est donc complète.

### Le statut des chambres depuis la réception

Le **Tableau des chambres** d'**Aujourd'hui** montre toutes les chambres.
Cliquez sur une chambre pour faire avancer son statut de propreté. Les quatre
statuts sont **Sale**, **Propre**, **Contrôlée** et **Hors service**.

---

## 4. Les réservations

### Créer une réservation

1. Appuyez sur **Nouvelle réservation**.
2. Saisissez le **Nom du client**. Un client déjà venu apparaît pendant la
   frappe : choisissez-le et le séjour se rattache à sa fiche (« Client
   fidèle · {n} séjours »).
3. Réglez le **Type de chambre**, l'**Arrivée**, le **Départ**, les
   **Adultes**, les **Enfants** et l'**Arrangement**. Le **Devis** se
   recalcule en direct et annonce les conditions d'annulation et l'acompte
   attendu.
4. Facultatif : **Ajouter une autre chambre** transforme la réservation en
   groupe — un seul **Confirmer la réservation** réserve toutes les chambres
   sous une même référence.
5. Facultatif : société, prestations annexes, **Code promo**.
6. Appuyez sur **Confirmer la réservation**. Vous obtenez une référence, et
   le séjour apparaît sous **Arrivées** à sa date d'arrivée.

Si aucune chambre n'a été attribuée automatiquement, vous lirez « Aucune
chambre attribuée automatiquement — choisissez-en une dans Réservations. »

### Le planning des chambres

**Réception → Planning des chambres.** Une ligne par chambre physique, les
dates en haut. Chaque barre colorée est un séjour. La légende distingue
**Libre**, **Confirmé**, **Arrivé**, **Occupée**, **Bloquée (usage maison /
VIP / maintenance)**, **Groupe**, **Entreprise**, **VIP**, **OTA** et
**À l'heure**.

- **Filtrer par type de chambre** réduit l'affichage.
- **Attribuer automatiquement les arrivées** propose un **Plan d'attribution
  proposé pour le {date}** ; examinez-le, puis **Attribuer {n} chambres**. Si
  chaque arrivée a déjà une chambre, l'écran vous le dit.
- **CONFLIT DE ROTATION** signale une arrivée prévue avant le départ du
  client précédent dans la même chambre. Corrigez les heures d'arrivée et de départ de la ligne (la mention
  **Arrival / departure times (ETA · ETD)** n'est pas encore traduite), ou
  déplacez l'un des deux.

L'écran **Calendrier** est l'autre vue : il vend par *type* de chambre et
montre les tarifs et la disponibilité. Le planning, lui, fait tourner la
maison : qui occupe quelle chambre réelle.

### Transférer un client dans une autre chambre

1. **Planning des chambres** → cliquez sur la barre du client (ou ouvrez la
   réservation).
2. Appuyez sur **Changer de chambre** — ou sur **Changer de chambre** depuis
   la fiche de police.
3. Choisissez **Même type**, ou **Tous les types (surclassement)** pour
   élargir. **Rechercher un numéro de chambre** permet d'en viser une
   directement.
4. Le volet indique l'effet sur le prix avant de valider : « Aucun changement
   de tarif. » ou le nouveau total du séjour.
5. Ajoutez un **Motif** et, si utile, une **Remarque (facultatif)**, puis
   appuyez sur **Transférer en chambre {chambre}**.

Si le client est déjà en séjour, l'ancienne chambre passe automatiquement en
**Sale** pour le ménage : « Le client est en séjour : l'ancienne chambre est
marquée Sale pour le ménage. » Si la nouvelle chambre n'est pas encore faite,
le volet avertit : « La chambre {room} n'a pas encore été nettoyée. »

### Modifier les dates

Cliquez sur la barre dans le planning et appuyez sur **Mettre à jour le
séjour**. Les changements de dates sont retarifés automatiquement — sauf si
la réservation porte un montant saisi à la main — et le contrôle de double
réservation repasse sur la chambre.

### Annuler une réservation

1. Ouvrez la réservation.
2. Appuyez sur **Annuler ce séjour…**.
3. Lisez ce que cela coûte **avant** de confirmer. Le volet indique soit
   « Hors délai de facturation - l'annulation est gratuite. », soit « Dans le
   délai de {days} jours - le {basis} ({amount}) sera facturé. »
4. Choisissez un **Motif**.
5. Un responsable peut cocher **Renoncer aux frais (consigné - décision du
   responsable)** : la décision est consignée sur la réservation.
6. Appuyez sur **Confirmer l'annulation**.
7. Donnez au client le **numéro d'annulation** affiché — « Communiquez le numéro
   d'annulation au client. » — et utilisez **Imprimer / partager la lettre de
   confirmation** s'il le souhaite par écrit. La lettre indique le
   remboursement éventuel.

Vous ne pouvez pas passer une réservation en annulée en modifiant son champ
de statut. Utilisez **Annuler ce séjour…** pour que la politique et les frais
s'appliquent toujours.

### Les non-présentations

Vous ne marquez pas une non-présentation à la main. L'**Audit de nuit**
(section 8) signale les clients qui ne sont jamais arrivés et les facture
selon la politique d'annulation de l'hôtel. La ligne de résultat de l'audit
indique combien il en a signalé.

---

## 5. L'argent

### Le folio

Le **folio** est la note courante d'un client. Il s'ouvre automatiquement à
l'arrivée. Retrouvez-le sous **Finances → Facturation** — la liste de tous
les folios ouverts avec leur **Total**, le montant **Réglé** et le
**Solde** — ou depuis la fiche de police du client via **Note ouverte**.

Un folio a deux moitiés : les **Prestations** et les **Paiements**. Le
**Solde** est ce qui reste dû.

### Déverrouiller les opérations d'argent

Avant d'enregistrer un règlement ou de solder un folio, votre code PIN de
caisse est nécessaire. Le folio affiche « Code PIN de caisse requis pour les
opérations d'argent. »

1. Appuyez sur **Déverrouiller** et saisissez votre PIN.
2. « Caisse déverrouillée — les opérations d'argent sont ouvertes pendant
   15 minutes. »

La première fois, appuyez sur **Définir le code PIN** et choisissez-en un. Ne
le communiquez jamais : chaque opération d'argent est consignée au nom de la
personne déverrouillée.

### Imputer une prestation

1. Ouvrez le folio.
2. Appuyez sur **Imputer une prestation**.
3. Renseignez le libellé, le **Montant** et le taux de taxe.
4. Appuyez sur **Imputer**.

Pour transférer une prestation vers un autre folio ou la scinder, ouvrez la
ligne et utilisez **Transférer ou scinder cette prestation** : saisissez soit
un pourcentage, soit un montant (« 30 % ou 1500 »). Pour supprimer une
prestation qui n'aurait jamais dû être là, utilisez **Annuler cette
prestation** avec un motif — il reste au dossier.

### Enregistrer un règlement

1. Ouvrez le folio.
2. Appuyez sur **Enregistrer un règlement**.
3. Choisissez le **Mode de paiement** : **Espèces**, **Carte** ou
   **Virement bancaire**. Une carte CIB ou Edahabia s'enregistre en
   **Carte** — c'est correct, et cela garde la caisse et le grand livre
   équilibrés.
4. Saisissez le **Montant** et, pour une carte ou un virement, le
   **Ticket de carte / réf. de virement (facultatif)**.
5. Précisez la nature de l'argent : sur la note, un acompte, ou une caution
   remboursable.
6. Appuyez sur **Enregistrer**.

**Lien de paiement** crée à la place un lien de paiement pour le solde et le
copie, pour que vous puissiez l'envoyer au client.

### Les acomptes

Le volet d'acompte d'une réservation affiche **Attendu**, **Reçu** et
**Reste dû**, et marque la réservation **Garanti**, **Partiellement réglé**
ou **Non réglé**.

- **Enregistrer le règlement** consigne un acompte encaissé à la réception.
- **Envoyer le lien de paiement** laisse le client payer lui-même —
  **Copier le message** vous donne le texte à envoyer. Dès qu'il paie,
  l'acompte s'impute tout seul.

L'acompte est reporté sur le folio du client et vient en déduction de la note
à l'arrivée.

### Imprimer une facture

1. Ouvrez le folio et vérifiez que le **Solde** est à zéro.
2. Appuyez sur **Clôturer et générer la facture**. C'est ce geste qui
   attribue le numéro de facture.
3. Appuyez sur **Imprimer la facture**.

Avant cette étape, le document n'est qu'une **Note provisoire** /
**Proforma**, et il le dit — en anglais, cette phrase n'étant pas encore
traduite : « Not a tax invoice yet — the number is issued when the folio is
settled. » Utilisez **Imprimer le folio** si le
client veut seulement voir le total courant, ou **Facture d'acompte** pour une
facture par anticipation.

Si le client prolonge mais veut clore la période en cours, utilisez
**Régler et poursuivre le séjour**.

Si une facture a été émise par erreur, **Annuler la facture** porte le numéro
au registre des annulations et réouvre le folio pour correction. Un **Avoir**
corrige un montant sans annuler la facture.

### La TVA et la taxe de séjour sur une note

Deux choses différentes cohabitent du côté des taxes sur une note
algérienne.

La **TVA** — taxe sur la valeur ajoutée — est un pourcentage de ce que le
client a consommé. Sur le folio, vous voyez une colonne **TVA %**, une
colonne du montant de **TVA** et un récapitulatif **TVA** qui regroupe la
note par taux. L'identifiant fiscal de l'hôtel s'imprime sur la facture sous
le libellé **NIF**.

La **taxe de séjour** est la taxe municipale de séjour. C'est une ligne de
prestation distincte sur le folio, portant le nom que l'hôtel a saisi comme
nom de taxe de séjour — par défaut **Taxe de séjour**, imprimé en caractères
latins même lorsque votre interface est en arabe. Selon le paramétrage de
l'hôtel, elle est soit un pourcentage du tarif de la chambre, soit un montant
fixe par personne et par nuit. Elle ne porte que sur les adultes.

Un résidu à connaître : le sous-titre de l'écran **Facturation** indique
encore « Cliquez sur un folio pour imputer des prestations, régler et
imprimer la facture GST ». GST est le nom de la taxe d'un autre pays. Sur vos
notes, la taxe est la **TVA** ; les colonnes du folio et la facture imprimée
l'indiquent correctement. Ignorez le mot GST là où vous le voyez, et
signalez-le si le support vous le demande.

**Les taux ne sont pas fixés par le logiciel.** C'est l'hôtel qui les
configure, type de chambre par type de chambre. Si un taux vous paraît faux
sur une note, ne modifiez rien : prévenez votre responsable, et le comptable
de l'hôtel confirme ce qui est correct. Le montant annoncé à la réservation
est celui qui est facturé : un client qui a accepté un chiffre ne s'en voit
jamais présenter un autre.

### Votre caisse

**Finances → Ma caisse.**

1. **Ouvrir la caisse** en début de service, et saisissez le **Fonds de
   caisse initial**.
2. Imputez les encaissements au fil du service ; la session liste les
   **Opérations récentes**.
3. Utilisez **Verser au coffre** pour un **Prélèvement d'espèces** en cours
   de service, et **Décaissement** pour l'argent qui sort.
4. En fin de service : **Clôturer la caisse**. Saisissez les **Espèces
   comptées (attendu {montant})**. L'écran affiche l'**Écart**.
5. Imprimez le **Rapport de poste**.

Un écart n'est pas un drame : signalez-le, n'ajustez pas le comptage pour le
faire disparaître.

---

## 6. Le ménage

### Le tableau des chambres

**Ménage → Tableau des chambres.** Toutes les chambres d'un coup d'œil, une
couleur par statut.

| Statut | Signification |
| --- | --- |
| **Sale** | À nettoyer |
| **Propre** | Nettoyée |
| **Contrôlée** | Vérifiée par un superviseur |
| **Hors service** | Non commercialisable |

**Pour changer le statut d'une chambre :**

1. **Ménage → Tableau des chambres.**
2. Utilisez **Filtrer les chambres** ou **Tous les étages** pour réduire
   l'affichage.
3. Touchez la chambre.
4. Appuyez sur **Marquer {statut}**.

Les femmes et valets de chambre ne peuvent marquer que **Sale** ou
**Propre** : « Vous pouvez marquer les chambres Propre ou Sale. » Valider une
chambre en **Contrôlée**, ou la bloquer **Hors service**, relève du
superviseur.

Le tableau signale aussi **Départ prévu** (un départ aujourd'hui),
**Occupée** et **Non attribuée**.

### Mettre une chambre hors service

Un superviseur qui touche la chambre et choisit **Marquer Hors service** la
retire de la vente : la réception ne peut alors plus y installer de client.
Remettez-la en **Sale** ou **Propre** dès qu'elle est réparée, sinon la
réception continuera de contourner une chambre qui va bien.

### L'application mobile / tablette

Les femmes et valets de chambre travaillent depuis l'application mobile, pas
depuis le tableau. Ouvrez `/kamra/hk` — par exemple
`http://localhost:8080/kamra/hk`. Ajoutez-la à l'écran d'accueil du
téléphone.

1. Connectez-vous. **Mes tâches** liste vos chambres, les arrivées d'abord.
2. Appuyez sur **Démarrer** quand vous commencez une chambre.
3. Appuyez sur **Terminé** quand elle est finie : la chambre passe
   immédiatement en **Chambre propre** sur le tableau de tout le monde.
4. Si rien ne vous est attribué, regardez les chambres non attribuées et
   appuyez sur **Prendre cette chambre** pour en ajouter une à votre liste.
5. **Actualiser** fait descendre le nouveau travail.

Également depuis le téléphone :

- **Imputer à la chambre {numéro}** — minibar ou blanchisserie relevés dans
  une chambre occupée. Touchez la chambre, saisissez ce que c'était (par
  exemple « par ex. 2 colas, 1 eau »), appuyez sur **Imputer {montant}**.
- **Enregistrer un objet perdu ou trouvé** — décrivez-le, ajoutez une photo
  avec **Ajouter une photo / vidéo**, appuyez sur **Enregistrer**.
- **Blanchisserie** — collectes et retours.

Les lignes sont signalées **arrivée aujourd'hui**, **en retard** et **VIP**
pour que vous sachiez par quoi commencer.

---

## 7. Le restaurant et la caisse

### Prendre une commande

**Restauration → Caisse restaurant.**

1. Choisissez la table sous **Tables**, ou appuyez sur **Nouvelle note**.
2. Utilisez **Rechercher dans la carte…** ou touchez les articles pour les
   ajouter. Ils sont marqués **Végétarien** / **Non végétarien**.
3. Ils s'empilent sous **Articles de la commande** avec le **Sous-total** et
   le **Total**.
4. Appuyez sur **Envoyer en cuisine** — le bon de cuisine
   (**Envoyer le KOT**) part vers l'**Écran cuisine**.
5. Pour une deuxième tournée sur la même table, ajoutez les articles et
   appuyez sur **Ajouter une tournée et envoyer le KOT**.

Les autres boutons : **Mettre la note en attente** la met de côté,
**Scinder** déplace les lignes cochées vers une nouvelle note (« Cochez les
lignes à transférer sur la nouvelle note. »), **Ajouter une
remise** applique une réduction, **Imprimer la note** donne la note au
client, **Gratuité** marque une commande à ne pas facturer.

**Tables et notes en cours** et **Tables en cours** montrent ce qui est
ouvert, avec les couverts et le statut (**Disponible**, **Occupée**,
**Nettoyage en cours**, **Réserver**).

### Imputer une addition à une chambre

1. Dans la caisse, sélectionnez la note.
2. Si la table est rattachée à un client en séjour, le bouton de règlement
   affiche **Régler / imputer à la chambre** au lieu de **Régler**.
3. Appuyez dessus. La prestation arrive sur le folio de ce client et apparaît
   dans **Finances → Facturation**.

Si le bouton n'affiche que **Régler**, la table n'est pas rattachée à une
chambre : encaissez au restaurant, ou rattachez d'abord la table au client.

### La cuisine

**Restauration → Écran cuisine** — le **Passe cuisine**. Les bons arrivent
marqués **NOUVEAU**.

1. Appuyez sur **Démarrer / accepter** — le bon passe **EN CUISSON**.
2. Appuyez sur **Marquer prêt** article par article, ou sur **All ready — send to pass**
   (pas encore traduit) pour le bon entier.
3. **Rappeler** ramène un bon fermé par erreur (**Undo — put it back on the
   board**, pas encore traduit).

Surveillez **EN RETARD** sur un bon qui attend, l'**Allergie du client** et le
**Commentaire de table**, et **CANCELLED — STOP COOKING** (pas encore
traduit) : arrêtez, la commande est retirée. **Envoyer** suivi du nom du
service libère un service mis en attente.

---

## 8. L'audit de nuit

L'audit de nuit clôt la journée de l'hôtel. Il :

- impute la prestation chambre et la taxe de la nuit pour chaque client en
  séjour ;
- ouvre les folios encore manquants ;
- signale et facture les non-présentations selon la politique de l'hôtel.

**Il s'exécute seul chaque nuit à 3 h.** Normalement, vous n'avez rien à
faire.

**Pour le lancer à la main :**

1. **Finances → Facturation.**
2. Appuyez sur **Lancer l'audit de nuit**.
3. Lisez la ligne de résultat : nuitées imputées, folios ouverts,
   non-présentations signalées.

**Exécutions récentes** liste les dernières.

Il est sans danger de le lancer deux fois. S'il a déjà tourné, il indique
« Déjà exécuté pour aujourd'hui » et rien n'est facturé une seconde fois.

Ne le lancez à la main que si l'exécution automatique a été manquée — après
une coupure de courant, par exemple, ou une nuit où le serveur était arrêté.
Consultez d'abord **Exécutions récentes**.

Avant l'audit, assurez-vous que chaque arrivée présente est bien enregistrée
et chaque départ bien clôturé. Un client dont l'arrivée n'a pas été
enregistrée sera traité comme une non-présentation.

---

## 9. Les clients qui réservent en ligne

### La page de réservation

La page de réservation de l'hôtel est à `/kamra/book` — par exemple
`http://localhost:8080/kamra/book`. Le client n'a besoin d'aucun compte.

Il choisit ses dates et le nombre de personnes, appuie sur **Vérifier la
disponibilité**, choisit une chambre, saisit son nom et son téléphone, puis
appuie sur **Confirmer et payer** ou **Réserver maintenant**. La page montre
aussi la **Galerie photo**, les **Conditions et règlement de l'hôtel**, le
**Règlement intérieur**, les **Questions fréquentes**, l'**Emplacement et
accès**, la **Caution** éventuelle, et accepte un **Code promo** et des
**Demandes particulières**.

Les réservations faites là arrivent dans **Réservations** et sur
**Aujourd'hui** comme toutes les autres.

La page a son propre sélecteur de langue — **English**, **Français**,
**العربية** — accessible sans connexion, et elle se reflète de droite à
gauche en arabe. Sur un téléphone réglé en arabe, la page s'ouvre
directement en arabe.

### La carte par QR code

Un client qui scanne le QR code de la table ou de la chambre arrive sur
`/kamra/menu/<point de vente>`, qui affiche la carte du point de vente avec
son propre sélecteur de langue. La page indique à quelle table ou dans quelle
chambre il se trouve.

Il appuie sur **Ajouter une unité** pour chaque article, puis sur **Passer la
commande**. La page le dit clairement : « Un serveur confirme votre commande
avant que la cuisine ne commence. » Surveillez donc les commandes qui
arrivent et confirmez-les : rien ne part en cuisine tant que quelqu'un en
salle ne l'a pas fait.

### Une chose à laquelle s'attendre

L'interface est traduite. **Le texte propre à l'hôtel ne l'est pas.** Les
descriptions de l'établissement et des chambres, le règlement intérieur, les
questions fréquentes, les noms des équipements, les arrangements et les noms
des plats sont saisis une seule fois par l'hôtel et conservés tels quels. Un
client qui lit une interface en arabe peut donc y voir du français ou de
l'anglais à l'intérieur : les boutons et les libellés en arabe, la
description de la chambre dans la langue où elle a été rédigée.

Ce n'est pas une panne, et ce n'est pas corrigeable depuis la réception. Si
des clients le relèvent, prévenez votre responsable : l'hôtel peut ressaisir
ce contenu dans la langue que lisent la plupart de ses clients.

---

## 10. Problèmes courants et que faire

| Ce que vous voyez | Que faire |
| --- | --- |
| « Connexion perdue — reconnexion… » | Attendez. Ne resaisissez rien. L'écran se reconnecte et se rafraîchit seul. |
| « Code PIN de caisse requis pour les opérations d'argent. » | Appuyez sur **Déverrouiller** et saisissez votre PIN. La première fois : **Définir le code PIN**. |
| Les boutons d'argent ne réagissent plus | Vos 15 minutes de déverrouillage sont écoulées. **Déverrouillez** à nouveau. |
| « La chambre {room} n'a pas encore été nettoyée. » à l'arrivée | Vous pouvez tout de même enregistrer l'arrivée. Prévenez le ménage, ou choisissez une autre chambre. |
| « Aucune chambre libre de ce type pour ces dates » | Ouvrez le **Planning des chambres** et cherchez un transfert ou un surclassement. |
| « Aucune chambre attribuée automatiquement — choisissez-en une dans Réservations. » | Ouvrez la réservation et attribuez une chambre, ou utilisez **Attribuer automatiquement les arrivées** sur le planning. |
| **CONFLIT DE ROTATION** sur le planning | Une arrivée est prévue avant un départ dans la même chambre. Corrigez les heures d'arrivée et de départ, ou déplacez un client. |
| Impossible de passer une réservation en annulée | C'est voulu. Utilisez **Annuler ce séjour…** pour que les frais et la politique s'appliquent. |
| L'audit de nuit indique « Déjà exécuté pour aujourd'hui » | Rien à faire. La journée est déjà close et rien ne sera facturé deux fois. |
| Un départ est prévu mais la pastille indique un montant dû | Soldez le folio avant **Enregistrer le départ**. |
| **Régler** ne propose pas **Régler / imputer à la chambre** | La table n'est pas rattachée à un client en séjour. Encaissez au point de vente, ou rattachez d'abord la table. |
| L'interface est dans la mauvaise langue | **Paramètres → Apparence → Langue.** Le réglage est propre à chaque navigateur, donc à chaque poste. |
| Un écran en arabe affiche du français ou de l'anglais | Il s'agit du contenu propre à l'hôtel — descriptions, règlement, noms des plats. Il est stocké dans une seule langue. Prévenez votre responsable. |
| Un écran en arabe paraît décalé, superposé ou tronqué | **Signalez-le.** La mise en page arabe n'a pas encore été vérifiée écran par écran, et les fiches et factures imprimées ne l'ont été dans aucune langue. Ne supposez pas que c'est normal. |
| Un taux de taxe paraît faux sur une note | Ne le modifiez pas. Prévenez votre responsable : l'hôtel fixe les taux et le comptable les confirme. |
| Le comptage de caisse ne correspond pas | Signalez l'**Écart** sur le **Rapport de poste**. N'ajustez pas le comptage. |

---

## 11. Qui appeler

D'abord votre chef de service ou l'administrateur de l'hôtel. La plupart des
problèmes — un tarif, une chambre bloquée, un utilisateur qui n'arrive pas à
se connecter — se règlent dans la maison.

Si cela doit remonter au support, préparez ceci :

| Ce qu'il faut dire | Où le trouver |
| --- | --- |
| Le produit : **ZIRI PMS** | — |
| La version : **2.6.5** | Non affichée sur les écrans du personnel — citez ce guide, ou demandez à votre administrateur si une mise à jour a eu lieu |
| Le nom de l'établissement | Barre du haut |
| L'adresse exacte que vous aviez ouverte | La barre d'adresse du navigateur |
| L'écran où vous étiez | Son titre, par exemple **Aujourd'hui**, **Planning des chambres**, **Facturation** |
| La langue de l'interface | English, Français ou العربية |
| Le message, mot pour mot | À l'écran — une photo de l'écran est idéale |
| Le numéro de l'enregistrement | Le numéro de réservation, de folio ou de facture |
| L'heure de l'incident | Votre montre |
| Ce que vous faisiez | Une phrase : « J'ai appuyé sur **Enregistrer le départ** pour la chambre 204 et… » |

Dites clairement si le client attend au comptoir. Cela change la vitesse de
prise en charge.

---

*ZIRI PMS 2.6.5 — guide du personnel. Les noms d'écrans et de boutons de ce
guide reprennent l'interface française. Quelques libellés ne sont pas encore
traduits et s'affichent en anglais ; ils sont signalés là où ils
apparaissent.*
