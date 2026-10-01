# ZIRI PMS — Guide d'installation

**Version installée :** ZIRI PMS, Distribution Algérie 1.0.0, sur Kamra core **2.6.5**

Ce guide vous conduit d'une machine Windows 10 nue jusqu'à un site ZIRI PMS
opérationnel, contenant la fiche de votre propre établissement. Suivez les
étapes dans l'ordre.

> **À propos du nom.** Le produit que vous avez acquis s'appelle **ZIRI PMS**.
> Le composant logiciel sur lequel il repose porte en interne le nom `kamra` ;
> vous rencontrerez donc ce mot dans les chemins de fichiers, les commandes et
> les adresses web — `/opt/kamra`, `kamra.env`,
> `http://localhost:8080/kamra`. C'est normal et attendu. **Ne « corrigez » pas
> ces chemins.** Saisissez-les exactement tels qu'ils sont imprimés, sinon rien
> ne fonctionnera.

---

## 1. Ce que c'est, et ce qu'il faut

ZIRI PMS est un système de gestion hôtelière (PMS) : réservations, arrivées et
départs, folios et notes, facturation, gouvernance, ainsi que les champs fiscaux
et légaux algériens (TVA, NIF, RC, NIS, AI et la taxe de séjour).

**Deux phrases à lire avant toute chose.** Le socle technique de ZIRI PMS ne
fonctionne pas nativement sous Windows — il n'en existe aucune version Windows.
L'installateur vérifie donc que votre machine Windows est capable d'héberger des
conteneurs Linux, puis pilote le véritable installateur Linux à l'intérieur de
**WSL2**, **Docker Desktop** faisant tourner les conteneurs.

Cela fonctionne, et c'est la bonne configuration pour une démonstration, un
pilote, ou une machine unique dont le propriétaire sait exactement ce qu'il a.
**Pour un hôtel qui prend des réservations réelles, un serveur Linux est un
meilleur hébergement** : la machine Windows n'installe alors rien du tout et la
réception ouvre simplement une adresse web. Une installation Windows dépend de
Docker Desktop démarré et d'une session ouverte ; si cette machine est éteinte
ou tombe en panne, les données de l'hôtel disparaissent avec elle. Tranchez ce
point délibérément, plutôt que de laisser une version d'essai devenir en
silence votre système de production. Demandez l'option « serveur Linux » à votre
prestataire en cas de doute.

---

## 2. Avant de commencer

Cochez chaque ligne. Le contrôle préalable de l'étape 1 en vérifie la plupart
pour vous, mais les deux points matériels sont à régler en amont.

**La machine**

- [ ] Windows 10, **64 bits**, version **2004** (build **19041**) ou ultérieure
      (vérifiez avec `winver`)
- [ ] Virtualisation matérielle **activée** dans le BIOS/UEFI
      (Gestionnaire des tâches → Performances → Processeur doit afficher
      « Virtualisation : activée »)
- [ ] **8 Go de RAM** au minimum — **16 Go** pour travailler confortablement
- [ ] **40 Go d'espace disque libre** au minimum — 60 Go ou plus est plus sûr,
      car le disque virtuel de WSL2 grossit à l'usage et ne se réduit pas de
      lui-même
- [ ] WSL installé, avec la **version 2 par défaut**
- [ ] **Docker Desktop** installé, démarré, utilisant le **moteur WSL 2**
- [ ] **Intégration WSL activée pour votre distribution** dans Docker Desktop
      (Settings → Resources → WSL integration)

**Décisions à prendre avant le jour de l'installation**

- [ ] Version d'essai ou production ? (Voir l'étape 2 : ce ne sont pas les mêmes
      installations.)
- [ ] Pour la production : le nom d'hôte du site, par exemple `pms.votrehotel.dz`
- [ ] Pour la production : l'adresse e-mail de l'administrateur, par exemple
      `gm@votrehotel.dz`
- [ ] Pour la production : le **mot de passe administrateur**, généré dans votre
      propre gestionnaire de mots de passe, **10 caractères minimum**. Voir la
      section 8.
- [ ] Le port HTTP de publication. Par défaut **8080** ; assurez-vous qu'aucun
      autre logiciel de la machine ne l'utilise.
- [ ] Un accès internet sortant (HTTPS) est disponible depuis la machine.

**Le temps nécessaire**

- [ ] **La première installation prend de 20 à 45 minutes**, et davantage sur un
      disque ou une connexion lents. Ce n'est pas une barre de progression
      bloquée : l'image logicielle est **construite localement sur votre
      machine**, elle n'est pas téléchargée prête à l'emploi. Ne programmez pas
      l'installation dans la demi-heure qui précède les arrivées.

**Préparer WSL2 et Docker Desktop (une fois par machine)**

Dans une console PowerShell **avec élévation** (Exécuter en tant
qu'administrateur) :

```powershell
wsl --install
wsl --set-default-version 2
```

Redémarrez si le système le demande. Puis vérifiez :

```powershell
wsl --status
wsl --list --verbose
```

Chaque distribution que vous comptez utiliser doit afficher `VERSION 2`.
Convertissez celle qui ne le fait pas :

```powershell
wsl --set-version <NomDeLaDistribution> 2
```

Installez Docker Desktop, puis, dans ses réglages, activez **Use the WSL 2 based
engine** (General) et activez l'intégration pour votre distribution
(Resources → WSL integration).

Enfin, vérifiez que Docker fonctionne réellement *à l'intérieur* de WSL — c'est
ce contrôle qui compte, car le véritable installateur s'exécute là :

```powershell
wsl -d <NomDeLaDistribution> -- bash -lc "docker version && docker compose version && docker buildx version"
```

Les trois commandes doivent réussir. Si `docker` est introuvable, l'intégration
WSL est encore désactivée pour cette distribution.

---

## 3. Étape 1 — contrôler la machine

Ouvrez PowerShell dans le dossier qui contient `Install-Kamra.ps1` et lancez :

```powershell
.\Install-Kamra.ps1 -Preflight
```

**`-Preflight` ne modifie rien.** Il inspecte Windows, la mémoire, le disque,
WSL, Docker et le port choisi, affiche un récapitulatif, puis s'arrête.
Lancez-le d'abord, systématiquement.

Lisez le récapitulatif. Les problèmes bloquants sont listés en `[FAIL]` avec une
correction suggérée, et le script se termine sans avoir rien touché. Les
avertissements sont listés séparément et ne bloquent pas l'installation.

Si PowerShell refuse d'exécuter le fichier parce qu'il n'est pas signé,
autorisez-le pour cette seule session plutôt que d'affaiblir durablement la
stratégie de la machine :

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-Kamra.ps1 -Preflight
```

Ne passez pas à l'étape 2 avant que le contrôle préalable n'indique que
l'environnement peut héberger la plateforme.

---

## 4. Étape 2 — installer

Il existe deux profils, et ce sont réellement deux installations différentes.
Choisissez avant de lancer quoi que ce soit.

| | **Essai** | **Production** |
| --- | --- | --- |
| Nom du site | `kamra.localhost` (valeur par défaut) | obligatoire, un vrai nom d'hôte |
| Données d'exemple | injectées | **aucune** |
| Comptes de démonstration | créés | **jamais créés** |
| Réinitialisation de la démo | possible | impossible, à dessein |
| Durée de vie prévue | des jours ou des semaines, puis mise au rebut | des années |
| Sauvegardes | inutiles, les données sont jetables | **obligatoires** |

### Version d'essai

Une démonstration jetable, contenant déjà un hôtel d'exemple.

```powershell
.\Install-Kamra.ps1 -Mode Trial
```

Les valeurs par défaut s'appliquent : site `kamra.localhost`, port 8080, données
d'exemple injectées.

### Production

L'installation réelle. Rien n'est injecté : le site démarre véritablement vide et
les données de votre hôtel sont créées par l'assistant de configuration à
l'étape 3.

```powershell
.\Install-Kamra.ps1 -Mode Production -SiteName pms.votrehotel.dz -AdminEmail gm@votrehotel.dz
```

`-SiteName` et `-AdminEmail` sont **obligatoires** en production. Le nom du site
doit contenir un point — l'installateur refuse tout ce qui ne ressemble pas à un
nom de domaine.

Pour publier sur un autre port, ajoutez `-HttpPort` :

```powershell
.\Install-Kamra.ps1 -Mode Production -SiteName pms.votrehotel.dz -AdminEmail gm@votrehotel.dz -HttpPort 9090
```

### Le mot de passe administrateur

**L'installateur Windows ne demande jamais le mot de passe administrateur, ne le
stocke pas et ne le transmet pas.** En cours de route, l'installateur Linux qui
s'exécute dans WSL vous le demandera et le lira directement depuis la console.
Il n'entre jamais dans une variable PowerShell, dans l'environnement, dans un
fichier journal, ni dans l'historique de vos commandes.

**10 caractères minimum.** **Il n'existe aucun mot de passe par défaut dans ce
système.** Choisissez-le vous-même, dans votre propre gestionnaire de mots de
passe, et lisez la section 8.

Puis patientez. De 20 à 45 minutes est normal.

---

## 5. Étape 3 — première configuration

À la fin, l'installateur affiche l'adresse à ouvrir. Avec le port par défaut,
c'est :

```
http://localhost:8080/kamra
```

Si vous avez utilisé `-HttpPort`, remplacez le numéro de port ; la partie
`/kamra` de l'adresse, elle, ne change jamais.

Connectez-vous en tant qu'`Administrator`, avec le mot de passe saisi pendant
l'installation.

Ouvrez ensuite l'assistant de configuration :

```
http://localhost:8080/kamra/setup
```

Créez votre établissement : nom, adresse, wilaya, coordonnées, chambres.

### Choisissez l'Algérie comme pays

**C'est le champ le plus important de l'assistant, et une erreur ici échoue en
silence.**

- Sélectionnez **Algeria** dans la liste des pays. Pas une variante
  orthographique, ni le nom français ou arabe : l'entrée qui affiche `Algeria`.
- Vérifiez ensuite à l'écran : les montants s'affichent en **DA** (le symbole du dinar ; `DZD` est le code de la devise), et la colonne
  de taxe porte l'intitulé **TVA** (ni VAT, ni GST).
- Vérifiez également que la fiche de l'établissement propose le champ **NIF**,
  ainsi que **RC**, **NIS** et **AI**, et que le prélèvement par nuitée est
  intitulé **Taxe de séjour**.

**Si l'Algérie n'apparaît pas du tout dans la liste des pays, la mauvaise version
a été installée.** Arrêtez-vous, ne saisissez aucune donnée, et prévenez votre
prestataire : l'installation a été construite depuis le logiciel en amont et non
depuis la distribution Algérie. Elle aura l'apparence d'un système hôtelier
fonctionnel tout en ne contenant aucun des travaux algériens.

Si le pays reste vide ou est mal orthographié, le système bascule sans
avertissement sur le vocabulaire fiscal d'un autre pays : vous obtiendriez des
prix dans la mauvaise devise et une colonne de taxe intitulée GST. Vérifiez donc
ce qui est à l'écran ; ne présumez pas que ce que vous avez saisi a été
enregistré.

### Les taux de taxe

Les taux de TVA proposés (19 % taux normal, 9 % taux réduit) et le montant de la
taxe de séjour sont des **valeurs par défaut paramétrables, et non un conseil
juridique**. Le taux applicable à l'hébergement et à vos points de restauration
dépend de la loi de finances, du point de vente et du classement de votre hôtel.

**Votre comptable doit confirmer le traitement fiscal avant l'émission de la
première facture réelle.** Le taux se règle sur chaque type de chambre, comme
une donnée. Pour la taxe de séjour, choisissez le mode **montant fixe par
personne et par nuit** et saisissez le montant de votre commune. Voir
[`TAXES.md`](../TAXES.md) pour le tableau complet.

---

## 6. Étape 4 — vérifier que cela fonctionne

Ne considérez pas l'installation terminée parce que la page de connexion
s'affiche. Déroulez cette liste.

1. **La page de connexion s'ouvre** sur `http://localhost:8080/kamra` et vous
   pouvez vous connecter en tant qu'`Administrator`.
2. **Algeria, DA et TVA** sont confirmés à l'écran, comme à l'étape 3.
3. **La liste des fuseaux horaires contient `Africa/Algiers`.**
4. **Une réservation s'enregistre.** Créez une réservation jetable,
   enregistrez-la, rouvrez-la. C'est la première preuve honnête que la base de
   données est saine — voir la section 9.
5. **Une nuitée s'impute et une facture s'imprime.** Imputez une nuitée sur cette
   réservation et imprimez la note. Vérifiez que le pied de page porte ceux des
   identifiants **RC · NIF · NIS · AI** que vous avez renseignés, et que le
   montant en lettres se lit « Dinars … » et non « DZD … ».
6. **Supprimez ensuite la réservation jetable** — sur un site de production,
   faites-le avant que le personnel ne commence à saisir de vraies données.
7. **Le planificateur de tâches de fond tourne.** L'audit de nuit (03 h 00, heure
   du site) et les relances de gouvernance sont des tâches planifiées. Un site
   dont le planificateur est arrêté paraît parfaitement normal toute la journée,
   puis ne clôture jamais la nuit, en silence. Vérifiez-le depuis WSL :

   ```bash
   cd /opt/kamra/frappe_docker
   docker compose --project-name kamra --env-file /opt/kamra/kamra.env \
     -f compose.yaml \
     -f overrides/compose.mariadb.yaml \
     -f overrides/compose.redis.yaml \
     -f overrides/compose.noproxy.yaml \
     exec -T backend bench --site <nom-de-votre-site> doctor
   ```

   Les quatre options `-f`, le nom de projet et le fichier d'environnement sont
   tous requis. Un simple `docker compose exec backend …` ne trouvera pas la
   plateforme.

8. **Production uniquement — aucun compte de démonstration n'existe.** Voir la
   section 8. C'est le contrôle le plus important de tous : n'acceptez pas le
   système avant qu'il ne passe.

---

## 7. Sauvegardes

Un PMS détient le seul enregistrement de qui arrive ce soir, de ce qui a été
convenu comme prix, de ce qui a déjà été réglé, et de ce que l'hôtel doit à
l'administration fiscale. Le perdre n'est pas un désagrément informatique.

Les procédures complètes — quoi sauvegarder, comment planifier la sauvegarde
sous Windows, et comment restaurer — figurent dans
[`BACKUP.md`](../BACKUP.md). Lisez-les avant la mise en service, pas après.

**La règle unique : une sauvegarde que personne n'a restaurée n'est pas une
sauvegarde. C'est un fichier.**

Effectuez une restauration complète avant la réception du système, puis une fois
par trimestre. Restaurez dans un site jetable distinct, vérifiez que les
réservations, les montants **et les fichiers téléversés** sont bien revenus, et
**notez par écrit tout ce que vous avez eu à faire**. Cette note est le mode
opératoire que quelqu'un suivra à deux heures du matin.

Trois points de `BACKUP.md` méritent d'être répétés ici :

- Sauvegardez toujours **avec les fichiers** (`--with-files`). Une sauvegarde de
  la seule base de données restaure un hôtel dont les scans de pièces
  d'identité, les fiches de police signées et les pièces jointes aux factures ont
  tous disparu — ce qui, pour un établissement algérien tenant une trace des
  fiches de police, n'est pas une sauvegarde partielle mais un problème de
  conformité.
- **Sauvegardez `/opt/kamra/kamra.env`.** Ce fichier contient le mot de passe de
  la base de données. Perdez-le et une copie de la base pourra devenir
  irrécupérable.
- **Sauvegardez avant chaque mise à jour**, sans exception. Une mise à jour
  exécute des migrations de base de données, et les migrations ne sont pas
  réversibles : revenir en arrière signifie restaurer.

```bash
cd /opt/kamra/frappe_docker
docker compose --project-name kamra --env-file /opt/kamra/kamra.env \
  -f compose.yaml \
  -f overrides/compose.mariadb.yaml \
  -f overrides/compose.redis.yaml \
  -f overrides/compose.noproxy.yaml \
  exec -T backend bench --site <nom-de-votre-site> backup --with-files
```

---

## 8. Sécurité

### Le mot de passe administrateur

- L'installateur Windows **ne le manipule jamais**. C'est l'installateur Linux
  qui le demande et le lit directement depuis la console.
- **10 caractères minimum.** **Aucune valeur par défaut n'existe.**
- **Choisissez-le vous-même**, dans votre propre gestionnaire de mots de passe,
  et gardez-en la maîtrise.
- **Après la réception du système, ne le communiquez pas au prestataire** — et
  si le prestataire en détient encore une copie, demandez-lui de la détruire.
  Personne en dehors de l'hôtel n'a besoin du mot de passe administrateur du
  système qui conserve les pièces d'identité de vos clients.

### Un site de production ne doit jamais comporter les comptes de démonstration

> ### ⚠ AVERTISSEMENT — à lire avant d'injecter quoi que ce soit
>
> L'injection de données d'exemple crée **six comptes utilisateurs dont les mots
> de passe sont publiés dans le code source public du produit**. L'un d'eux est
> **administrateur système complet**.
>
> Ces mots de passe sont en outre compilés dans le JavaScript que télécharge tout
> visiteur du site. Désactiver le « mode démonstration » masque seulement les
> boutons de connexion rapide — **cela n'invalide pas les mots de passe**.
> Masquer un bouton n'est pas une mesure de sécurité.
>
> **La seule véritable protection est que ces comptes n'existent pas.**
>
> `-Mode Production` n'injecte rien et n'en crée aucun. Par conséquent :
>
> - **N'injectez jamais de données d'exemple sur un site en production**, pas même
>   « juste pour avoir quelque chose à montrer ».
> - **Ne créez jamais ces comptes à la main.**
> - Si un site a déjà été alimenté par ces données et doit désormais passer en
>   production, considérez-le comme **compromis** : faites *supprimer* les six
>   comptes (et non simplement changer leurs mots de passe), faites renouveler le
>   mot de passe d'`Administrator`, et faites auditer les journaux d'accès.

Pour confirmer qu'un site de production est propre, aucun compte dont l'adresse
se termine par `@kamra.local` ne doit exister. Votre prestataire peut effectuer
ce contrôle pour vous ; demandez-en le résultat. Il doit revenir **vide** — et
non « les mots de passe ont été changés », vide.

### Autres points à régler avant la mise en service

- **Placez du HTTPS devant le site.** L'installateur publie du HTTP en clair et
  ne termine aucun TLS. Un hôtel ne devrait pas fonctionner en HTTP en clair.
- **N'exposez pas directement le port 8080 sur internet.**
- **Créez des comptes nominatifs** pour le personnel, avec les rôles appropriés
  (Hotel Admin, Front Desk, Revenue, Finance, Housekeeping), plutôt que de
  partager un identifiant unique.
- **`/opt/kamra/kamra.env` doit rester en mode 600.** Il contient le mot de passe
  de la base de données.

---

## 9. Ce qui n'est pas encore éprouvé

Cette section figure ici parce qu'un fournisseur qui dissimule ces points vous
vend un passif. Rien n'y est spéculatif, et rien n'y est motif à s'alarmer.
C'est une liste de points que vos propres premiers jours d'utilisation vont
trancher.

- **Les migrations de base de données n'avaient jamais été exécutées sur une
  vraie base avant votre installation.** Deux étapes de migration — l'une pour la
  taxe de séjour fixe par personne, l'autre pour les champs RC/NIS/AI — n'avaient
  jamais été exécutées sur une base de données réelle, nulle part. Si votre
  installation s'est terminée, **elles viennent de s'exécuter pour la première
  fois.** À faire : passez par le profil d'essai avant la production si vous le
  pouvez, vérifiez que le site se charge et qu'une réservation s'enregistre
  (étape 4, point 4), et **prenez une sauvegarde avant chaque mise à jour
  future**, puisqu'elle exécute elle aussi des migrations.

- **Personne n'a encore regardé la mise en page arabe dans un navigateur.** Le
  travail de droite à gauche est écrit et se vérifie correctement pour autant
  qu'une lecture du code puisse l'établir, mais personne ne l'a affiché à l'écran
  pour le regarder. Le même point reste ouvert pour les mises en page d'impression
  française, arabe et anglaise. À faire : faites parcourir par une personne
  arabophone la réception, la page de réservation client et une facture imprimée
  avant la mise en service. Attendez-vous à trouver des choses. Elles seront très
  probablement cosmétiques plutôt qu'arithmétiques — mais un hôtel est jugé sur
  ce que voit le client.

- **Aucun test automatisé du back-end n'a jamais été exécuté sur un site réel.**
  Le contrôle qualité de cette version a reposé sur l'analyse statique et des
  vérifications arithmétiques, non sur une suite de tests exécutée. Traitez votre
  première installation comme le test, et prévoyez du temps pour cela.

- **Un type de chambre exonéré de taxe ne peut pas être exprimé aujourd'hui.** Le
  modèle de données ne sait pas distinguer « 0 % » de « non configuré », c'est
  pourquoi la liste des taux ne propose délibérément que 9 et 19. Si vous avez un
  type de chambre réellement exonéré, ce système ne sait pas encore le
  représenter : signalez-le à votre prestataire maintenant, plutôt que de le
  découvrir sur une facture.

- **Une anomalie connue entre le mode pourcentage et les bons de réduction.** Si
  la taxe de séjour est réglée en mode **pourcentage** *et* qu'un bon de
  réduction est appliqué, le devis et la note imputée peuvent produire des
  montants différents. **Le mode montant fixe par personne et par nuit n'est pas
  concerné** — et c'est précisément le mode fixe qu'un établissement algérien
  veut pour une taxe de séjour. Utilisez le mode fixe.

- **La langue de l'interface ne traduit pas vos propres contenus.** L'interface
  est disponible en arabe, en français et en anglais, mais les descriptions de
  l'établissement et des chambres, le règlement intérieur, la foire aux
  questions, les équipements et les cartes de restauration restent dans la langue
  dans laquelle vous les avez saisis. Un client arabophone obtiendra une
  interface arabe autour de votre texte français, à moins que vous ne le
  rédigiez deux fois. La couverture de l'interface n'est pas non plus encore
  complète : certains libellés apparaissent toujours en anglais.

---

## 10. En cas de problème

| Symptôme | Cause probable |
| --- | --- |
| `need 'docker' on PATH` | L'intégration WSL de Docker Desktop est désactivée pour votre distribution |
| `docker buildx is required` | BuildKit, requis par la construction de l'image, est absent |
| La construction échoue au téléchargement du logiciel | Le dépôt source est inaccessible — contactez votre prestataire |
| La construction est interrompue, ou signale un manque de mémoire | Machine sous le plancher de 8 Go de RAM ; augmentez la limite mémoire de Docker Desktop |
| `docker build failed` après une longue attente | Disque plein, le plus souvent. Le disque virtuel WSL2 grossit : vérifiez l'espace libre sur `C:` |
| Le site ne devient jamais accessible | Les conteneurs démarrent encore ou échouent ; l'installateur patiente 5 minutes avant d'abandonner. Votre prestataire peut lire leurs journaux |
| **L'Algérie est absente de la liste des pays** | La mauvaise version a été installée. Arrêtez-vous et contactez votre prestataire — voir l'étape 3 |
| Les prix s'affichent dans une devise étrangère, la taxe indique GST | Le pays de l'établissement est resté **vide** : le paquet d'un autre pays s'est chargé. Corrigez le champ pays — voir l'étape 3 |
| Aucun libellé TVA, aucune taxe de séjour | Le pays de l'établissement est **mal orthographié**. Il doit indiquer exactement `Algeria` |
| L'audit de nuit ne se lance jamais | Le planificateur de tâches de fond est désactivé — voir l'étape 4, point 7 |
| Avertissements `ERPNEXT_VERSION` pendant l'installation | Bruit inoffensif provenant des fichiers de conteneurs sous-jacents |
| PowerShell refuse d'exécuter l'installateur | Le script n'est pas signé ; utilisez la commande « une seule session » de l'étape 1 |

---

## 11. Obtenir de l'aide

Réunissez ceci avant de contacter le support. Sans cela, la première réponse ne
sera qu'une demande de ces éléments.

**Indiquez toujours le nom du produit et les deux numéros de version :**

```
ZIRI PMS
Algeria Distribution 1.0.0
on Kamra core 2.6.5
```

Les deux numéros comptent. « Kamra core 2.6.5 » seul ne dit pas si le paquet
Algérie est installé, et le numéro de distribution seul ne dit pas sur quel cœur
il repose. L'installateur affiche les deux à chaque exécution.

**Ajoutez ensuite :**

- Le profil installé — **Trial** ou **Production**
- La commande exacte que vous avez lancée, copiée depuis PowerShell
- Le nom de votre site et le port utilisé
- La version et le build de Windows (`winver`), et la quantité de RAM de la
  machine
- Si `.\Install-Kamra.ps1 -Preflight` passe **maintenant**, et sa sortie complète
- Le texte exact de l'erreur, copié en tant que texte plutôt que décrit ou
  photographié
- À quel moment cela a échoué : contrôle préalable, construction de l'image,
  création du site, première connexion, assistant de configuration
- Si cela a déjà fonctionné, et ce qui a changé depuis

**Si le problème porte sur un montant ou une taxe sur un document**, joignez la
facture ou la note imprimée et précisez quel chiffre vous attendiez, et pourquoi.

**N'incluez jamais le mot de passe administrateur**, et ne le transmettez à
personne qui le demanderait — y compris à quelqu'un se présentant comme votre
prestataire. Le support n'en a jamais besoin.

---

## Voir aussi

- [`../BACKUP.md`](../BACKUP.md) — sauvegarde, restauration, planification et test de restauration
- [`../TAXES.md`](../TAXES.md) — TVA, taxe de séjour et les identifiants légaux
- [`../VERSIONING.md`](../VERSIONING.md) — ce que signifient les deux numéros de version
- [`INSTALL-en.md`](INSTALL-en.md) — ce guide en anglais
- [`INSTALL-ar.md`](INSTALL-ar.md) — ce guide en arabe
