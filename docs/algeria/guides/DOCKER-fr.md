# Hotel MgM — Guide d'installation Docker sous Linux

**Version installée :** Hotel MgM, Distribution Algérie **1.0.0**, sur
Kamra core **2.6.5**

Ce guide vous conduit d'un serveur Linux nu jusqu'à un site Hotel MgM
opérationnel sous Docker, contenant la fiche de votre propre établissement.
Suivez les étapes dans l'ordre.

> **À propos du nom.** Le produit que vous avez acquis s'appelle **Hotel MgM**.
> Le composant logiciel sur lequel il repose porte en interne le nom `kamra` ;
> vous rencontrerez donc ce mot dans les chemins de fichiers, les noms d'images,
> les commandes et les adresses web — `/opt/kamra`, `kamra.env`, `kamra:local`,
> `--install-app kamra`, `http://<host>:8080/kamra`, `--project-name kamra`.
> C'est normal et attendu. **Ne « corrigez » pas ces chemins.** Saisissez-les
> exactement tels qu'ils sont imprimés, sinon rien ne fonctionnera.

---

## 1. Ce que c'est

Il s'agit de l'installation Docker sur un serveur Linux, et c'est
**l'hébergement recommandé pour un hôtel qui prend des réservations réelles**.
Le parcours Windows décrit dans [`INSTALL-fr.md`](INSTALL-fr.md) pilote les
mêmes conteneurs à travers WSL2 et convient à une démonstration ou à un pilote ;
il dépend de Docker Desktop démarré et d'une session utilisateur ouverte. Un
serveur Linux, non. La réception n'installe alors rien du tout et ouvre
simplement une adresse web.

La pile compte **dix conteneurs et trois volumes**, définis dans un seul
fichier — [`deploy/linux/docker-compose.yml`](../../../deploy/linux/docker-compose.yml).

| Service | Rôle |
| --- | --- |
| `configurator` | **conteneur à exécution unique** : il écrit la configuration base de données et Redis dans le volume partagé `sites`, puis s'arrête |
| `backend` | le serveur d'application (gunicorn) |
| `frontend` | nginx — sert l'interface et route les requêtes vers le site |
| `websocket` | le canal temps réel |
| `queue-short` | worker d'arrière-plan, files `short` et `default` |
| `queue-long` | worker d'arrière-plan, files `long`, `default` et `short` |
| `scheduler` | **exécute la clôture de nuit**, les courriels programmés et les tâches planifiées |
| `db` | `mariadb:11.8` |
| `redis-cache` | `redis:8.6-alpine` |
| `redis-queue` | `redis:8.6-alpine` |

| Volume | Contenu |
| --- | --- |
| `sites` | la configuration du site, la **clé de chiffrement**, et tous les fichiers téléversés, y compris les scans de pièces d'identité des clients |
| `db-data` | la base de données |
| `redis-queue-data` | les tâches en file d'attente |

**Le fichier compose ne construit pas l'image.** L'image provient du
`images/layered/Containerfile` de frappe_docker, épinglé au SHA
`3d0a0e53d8ab03903f6c3f125976a37d7a0f9875`, délibérément non recopié dans ce
dépôt — en dupliquer la construction amont signifierait devoir la maintenir. Il
existe donc deux voies honnêtes, et ce sont exactement les sections 3 et 4.

Utilisez `docker compose` — le greffon Compose **v2**. Pas `docker-compose`.
Toutes les commandes de ce guide supposent la v2.

---

## 2. Avant de commencer

Cochez chaque ligne.

**Le serveur**

- [ ] Linux **x86-64**. Les services déclarent `platform: linux/amd64`, choix de
      l'amont. Sur un serveur ARM, chaque conteneur s'exécute en émulation,
      lentement. **Utilisez du x86-64.**
- [ ] Docker Engine avec le **greffon Compose v2** — `docker compose version`
      doit réussir, pas `docker-compose`
- [ ] `docker buildx version` doit réussir. Le Containerfile en couches utilise
      `RUN --mount=type=secret`, qui exige BuildKit. Le paquet `docker.io`
      d'Ubuntu en est dépourvu ; `install.sh` tente d'installer
      `docker-buildx-plugin` pour vous.
- [ ] **2 vCPU / 4 Go de RAM / 40 Go de disque** au minimum. **8 Go de RAM**
      rendent la construction confortable — en dessous de 8 Go, `install.sh`
      ajoute un fichier d'échange pour la durée de la construction.
- [ ] Un accès HTTPS sortant depuis le serveur (il clone depuis GitHub pendant
      la construction)

**Décisions à prendre avant le jour de l'installation**

- [ ] Le nom du site, par exemple `pms.yourhotel.dz`. Il doit ressembler à un
      domaine — l'installateur refuse tout ce qui ne contient pas de point.
- [ ] L'adresse de courriel de l'administrateur, par exemple `gm@yourhotel.dz`
- [ ] Le **mot de passe administrateur**, généré dans votre propre gestionnaire
      de mots de passe, **10 caractères** minimum. Voir la section 14. Il n'y a
      aucune valeur par défaut.
- [ ] Le port HTTP à publier. **8080** par défaut ; vérifiez que rien d'autre ne
      l'utilise.
- [ ] Comment le TLS sera terminé. Voir la section 9. **Ne servez pas un hôtel
      en HTTP simple.**

**Le temps**

- [ ] **La première construction prend de 20 à 45 minutes**, davantage sur un
      disque ou une connexion lents. Ce n'est pas une barre de progression
      bloquée : l'image est **construite localement sur ce serveur**, et non
      téléchargée prête à l'emploi. Il n'existe aucun registre depuis lequel la
      récupérer, et c'est pourquoi la politique de récupération vaut `never`. Ne
      planifiez pas l'installation dans la demi-heure qui précède les arrivées.

---

## 3. Voie A — l'installation scriptée

C'est le chemin correct le plus simple sur un serveur neuf. `install.sh`
récupère frappe_docker au SHA épinglé, construit l'image, crée le site, installe
`payments` et `kamra`, effectue le câblage de premier démarrage et laisse la
pile en marche.

> ### ⚠ Les deux variables d'environnement ne sont pas optionnelles
>
> `install.sh` pointe par défaut sur **Kamra amont, branche `main`**. Sans ces
> deux surcharges, une construction de 20 à 45 minutes produit le logiciel amont
> **sans aucune localisation algérienne** — pas de pack pays Algérie, pas de
> TVA, pas de NIF, pas de taxe de séjour. Et cela aura l'apparence d'un système
> hôtelier parfaitement fonctionnel. Exportez les deux avant de lancer quoi que
> ce soit.

```bash
export KAMRA_GIT_URL=https://github.com/ilyeseia/kamra-pms-algeria
export KAMRA_BRANCH=feature/algeria-hospitality-platform
curl -fsSL https://raw.githubusercontent.com/ilyeseia/kamra-pms-algeria/feature/algeria-hospitality-platform/deploy/install.sh -o install.sh
```

Lisez le script avant de l'exécuter. Puis :

```bash
sudo bash install.sh
```

Il demandera le domaine du site, une adresse de courriel d'administrateur et un
mot de passe administrateur (10 caractères minimum, lu directement depuis la
console, jamais écrit dans un journal). Ensuite, patientez. De 20 à 45 minutes
est normal.

**Le dépôt source est cloné depuis l'intérieur du conteneur de construction,
sans aucune authentification.** Il doit donc être publiquement lisible, sinon la
construction échoue en cours de route. Si elle meurt au moment de récupérer
l'application, c'est la première chose à vérifier.

À la fin, `install.sh` affiche l'adresse de connexion et a laissé en place :

| | |
| --- | --- |
| Répertoire de la pile | `/opt/kamra` |
| Fichier d'environnement | `/opt/kamra/kamra.env` (mode 600 — il contient le mot de passe de la base) |
| Applications enregistrées | `/opt/kamra/apps.json` |
| Clone de frappe_docker | `/opt/kamra/frappe_docker` |
| Une copie de lui-même | `/opt/kamra/install.sh`, pour que les mises à jour fonctionnent plus tard |

Passez à la section 7 pour créer l'établissement.

### Pourquoi la section 4 peut encore vous intéresser ensuite

`install.sh` pilote compose par une invocation à quatre options, depuis
l'intérieur du clone frappe_docker :

```bash
docker compose --project-name kamra --env-file /opt/kamra/kamra.env -f compose.yaml -f overrides/compose.mariadb.yaml -f overrides/compose.redis.yaml -f overrides/compose.noproxy.yaml ps
```

Les quatre options `-f`, le nom de projet et le fichier d'environnement sont
tous requis ; un simple `docker compose ps` ne trouvera pas cette pile.
`deploy/linux/docker-compose.yml` est l'équivalent aplati de cette invocation,
de sorte que le travail quotidien se réduit à `docker compose up -d`, sans rien
cloner. Le déplacement d'une installation existante est traité en section 5.

---

## 4. Voie B — construire l'image, puis `docker compose up -d`

Prenez cette voie si vous voulez que `deploy/linux/` soit toute l'histoire. Vous
construisez l'image une fois à la main, et tout le reste n'est ensuite que du
`docker compose` ordinaire.

C'est exactement ce que fait `install.sh` en interne. Récupérez frappe_docker au
SHA épinglé :

```bash
git clone --depth 1 https://github.com/frappe/frappe_docker.git /tmp/frappe_docker
cd /tmp/frappe_docker
git fetch --depth 1 origin 3d0a0e53d8ab03903f6c3f125976a37d7a0f9875 && git checkout --force FETCH_HEAD
```

Écrivez la liste des applications. **La deuxième entrée est la distribution
Algérie** — c'est la même chose que font les deux variables d'environnement de
la voie A, et s'y tromper a la même conséquence :

```bash
cat > /tmp/apps.json <<'EOF'
[
  {"url": "https://github.com/frappe/payments", "branch": "develop"},
  {"url": "https://github.com/ilyeseia/kamra-pms-algeria", "branch": "feature/algeria-hospitality-platform"}
]
EOF
```

Construisez :

```bash
DOCKER_BUILDKIT=1 docker build -t kamra:local \
  -f images/layered/Containerfile \
  --build-arg FRAPPE_PATH=https://github.com/frappe/frappe \
  --build-arg FRAPPE_BRANCH=version-16 \
  --build-arg CACHE_BUST="$(date +%s)" \
  --secret id=apps_json,src=/tmp/apps.json .
```

Le dépôt indiqué dans `apps.json` est cloné **depuis l'intérieur du conteneur,
sans aucune authentification** : il doit être publiquement lisible, sinon la
construction échoue en cours de route.

Configurez ensuite `.env` (section 5), démarrez la pile (section 6), puis créez
le site à la main — `install.sh` fait cette étape pour vous, la voie B non :

```bash
docker compose exec backend bench new-site pms.yourhotel.dz --no-mariadb-socket --mariadb-user-host-login-scope='%' --db-root-password "$DB_PASSWORD" --install-app payments --install-app kamra
```

```bash
docker compose exec backend bench --site pms.yourhotel.dz execute kamra.scripts.first_boot.execute
```

Remplacez par votre propre nom de site dans les deux commandes.
`FRAPPE_SITE_NAME_HEADER` dans `.env` doit être **exactement** égal à ce nom de
site — voir la section 5.

---

## 5. Configurer `.env`

Depuis `deploy/linux/` :

```bash
cp .env.example .env
```

Éditez ensuite `.env`. Lisez `.env.example` lui-même : chaque variable y est
commentée, avec la raison de sa présence. **Deux sont obligatoires**, et la pile
ne démarrera pas sans elles.

### `DB_PASSWORD`

Le mot de passe root de MariaDB. **Il n'a volontairement aucune valeur par
défaut.** La valeur de repli de l'amont est `123`, et ce n'est pas un mot de
passe sur lequel la base de données d'un hôtel devrait se retrouver en silence ;
la pile refuse donc de démarrer plutôt que d'en hériter. Vous verrez
`DB_PASSWORD is required` au `up` si elle est absente ou vide. C'est le fichier
qui fonctionne correctement.

Générez-en un :

```bash
openssl rand -hex 16
```

### `FRAPPE_SITE_NAME_HEADER`

**Elle doit être exactement égale au nom du site Frappe.** nginx route sur cet
en-tête. En cas de divergence, absolument toutes les URL renvoient une 404
contre un site qui existe et se porte parfaitement bien. C'est **la cause la
plus fréquente de « l'installation a réussi mais rien ne s'affiche »** — si vous
constatez ce symptôme, vérifiez cette variable avant toute autre chose.

```
FRAPPE_SITE_NAME_HEADER=pms.yourhotel.dz
```

Exactement le nom passé à `bench new-site`, ou exactement le domaine du site
saisi à l'invite d'`install.sh`. Pas une variante, pas avec un port, pas avec
`https://`.

### Déplacer une installation `install.sh` existante vers `deploy/linux/`

Une installation réalisée par `install.sh` **possède déjà ce fichier**, écrit
pour vous, à l'emplacement `/opt/kamra/kamra.env`. **Copiez-le. N'écrivez pas un
nouveau mot de passe.**

```bash
cp /opt/kamra/kamra.env .env
```

MariaDB conserve le mot de passe avec lequel son volume `db-data` a été
initialisé. Un nouveau `DB_PASSWORD` face à un volume existant ne change pas le
mot de passe de la base : il vous enferme dehors, et vous obtiendrez
`Access denied for root`. Si cela arrive, rétablissez l'ancien `DB_PASSWORD`.

### Le reste, brièvement

| Variable | Remarques |
| --- | --- |
| `CUSTOM_IMAGE` / `CUSTOM_TAG` | `kamra` / `local` — l'image construite localement |
| `PULL_POLICY` | `never`. Il n'existe aucun registre depuis lequel récupérer l'image. |
| `HTTP_PUBLISH_PORT` | le port hôte sur lequel nginx est publié, `8080` par défaut |
| `NGINX_LISTEN_PORT` | le port à l'intérieur du conteneur. N'y touchez pas. |
| `UPSTREAM_REAL_IP_ADDRESS`, `UPSTREAM_REAL_IP_HEADER`, `UPSTREAM_REAL_IP_RECURSIVE` | commentées par défaut ; voir la section 9 |
| `GUNICORN_WORKERS`, `GUNICORN_THREADS`, `GUNICORN_TIMEOUT` | à augmenter seulement sur un établissement chargé disposant de RAM. Chaque worker est un processus portant une application Python complète — ne les augmentez pas sur une machine de 4 Go. |
| `CLIENT_MAX_BODY_SIZE` | plafond de téléversement, `50m` par défaut. Les scans de pièces d'identité et les photos de chambres passent par là. |
| `RESTART_POLICY` | `unless-stopped`, ce qui maintient l'hôtel en marche après un redémarrage. N'utilisez `no` qu'en phase de diagnostic. |

**Ne versionnez jamais `.env`.** Il contient le mot de passe root de la base de
données. Le `.gitignore` du dépôt exclut déjà `.env` et `.env.*` — laissez-le
ainsi. Et sauvegardez ce fichier, comme un secret, dans un gestionnaire de mots
de passe : le perdre peut rendre un vidage de base impossible à restaurer.

---

## 6. Démarrer, et vérifier `configurator`

```bash
docker compose up -d
```

Puis, immédiatement :

```bash
docker compose ps
```

> ### `configurator` doit afficher `Exited (0)`
>
> **C'est le meilleur diagnostic de toute la pile, et il mérite son propre
> paragraphe.**
>
> `configurator` est un conteneur à exécution unique. Il écrit la configuration
> des hôtes base de données et Redis dans le volume partagé `sites`, puis
> s'arrête. Tous les autres services attendent qu'il **se termine avec succès**
> avant de démarrer.
>
> - S'il affiche `Exited (0)`, la plomberie est correcte et le reste de la pile
>   se lève derrière lui.
> - S'il affiche autre chose — encore en cours, en redémarrage, `Exited (1)` —
>   **rien d'autre ne démarrera**, et vous aurez sous les yeux une pile qui
>   semble occupée à quelque chose tout en ne servant rien.
>
> Son journal dit pourquoi, en clair :
>
> ```bash
> docker compose logs configurator
> ```
>
> Le plus souvent, il s'agit du mot de passe de la base. `configurator` attend
> que MariaDB passe son test de santé, et pas simplement qu'elle démarre, parce
> qu'un `bench set-config` lancé contre une MariaDB à moitié initialisée est la
> manière dont une première installation échoue de façon déroutante.

Une fois `configurator` en `Exited (0)` et les autres services levés, regardez
le backend prendre vie :

```bash
docker compose logs -f backend
```

---

## 7. Créer l'établissement

Ouvrez, en substituant l'adresse de votre serveur :

```
http://<host>:8080/kamra
```

Si vous avez changé `HTTP_PUBLISH_PORT`, substituez votre port ; **la partie
`/kamra` de l'adresse ne change jamais.**

Connectez-vous comme `Administrator` avec le mot de passe défini pendant
l'installation. Ouvrez ensuite l'assistant de configuration :

```
http://<host>:8080/kamra/setup
```

Créez votre établissement — nom, adresse, coordonnées, chambres.

### Choisir l'Algérie comme pays

**C'est le champ le plus important de tout l'assistant, et s'y tromper échoue
silencieusement.**

- Choisissez **Algeria** dans la liste des pays. Pas une orthographe variante,
  ni le nom français ou arabe — l'entrée qui se lit `Algeria`.
- Confirmez ensuite, à l'écran : les montants s'affichent avec **DA**, et la
  colonne de taxe est intitulée **TVA** (pas VAT, pas GST).
- Confirmez aussi que la fiche établissement propose le champ **NIF**, ainsi que
  **RC**, **NIS** et **AI**, et que la taxe sur la chambre est intitulée **Taxe
  de séjour**.
- Confirmez que la liste des fuseaux horaires contient **`Africa/Algiers`**.

**Si l'Algérie n'apparaît pas du tout dans la liste des pays, l'image a été
construite depuis l'amont.** Arrêtez-vous. Ne saisissez aucune donnée. Vérifiez
`apps.json` — la deuxième entrée doit être
`https://github.com/ilyeseia/kamra-pms-algeria` sur la branche
`feature/algeria-hospitality-platform` — et reconstruisez l'image. Une
construction ayant silencieusement utilisé l'amont aura l'apparence d'un système
hôtelier fonctionnel tout en ne contenant rien du travail algérien.

Si le pays est laissé vide ou mal orthographié, le système retombe sans
avertissement sur le vocabulaire fiscal d'un autre pays — mauvaise devise,
colonne de taxe intitulée GST. Vérifiez donc ce qui est à l'écran ; ne supposez
pas que ce que vous avez saisi a été enregistré.

### Les taux de taxe

Les taux de TVA que le système propose (19 % standard, 9 % réduit) et le montant
de la taxe de séjour sont **des valeurs par défaut configurables, pas un conseil
juridique.** Le taux applicable à votre hébergement et à vos points de
restauration dépend de la loi de finances, du point de vente et du classement de
votre hôtel.

**Votre comptable doit confirmer le traitement avant l'émission de la première
facture réelle.** Réglez le taux sur chaque type de chambre, comme une donnée et
non dans le code. Pour la taxe de séjour, réglez le mode sur **fixe par personne
et par nuit** et saisissez le montant de votre commune. Voir
[`TAXES.md`](../TAXES.md) pour le tableau complet.

---

## 8. Vérifier que cela fonctionne

Ne déclarez pas l'installation terminée parce que la page de connexion s'est
affichée.

1. **`docker compose ps`** — `configurator` est en `Exited (0)` ; `backend`,
   `frontend`, `websocket`, `queue-short`, `queue-long`, `scheduler`, `db`,
   `redis-cache` et `redis-queue` sont tous levés.
2. **La page de connexion se charge** à l'adresse `http://<host>:8080/kamra` et
   vous pouvez vous connecter comme `Administrator`.
3. **Algeria, DA et TVA** sont confirmés à l'écran, comme en section 7, et la
   liste des fuseaux horaires contient `Africa/Algiers`.
4. **Une réservation s'enregistre.** Créez une réservation jetable,
   enregistrez-la, rouvrez-la. C'est la première preuve honnête que la base de
   données est saine — voir la section 15.
5. **Une nuit se poste et une facture s'imprime.** Postez une nuit sur cette
   réservation et imprimez le folio. Vérifiez que le pied de page porte ceux des
   identifiants **RC · NIF · NIS · AI** que vous avez renseignés, et que le
   montant en lettres se lit *Dinars …* et non *DZD …*.
6. **Supprimez ensuite la réservation jetable**, avant que le personnel ne
   commence à saisir de vraies données.
7. **Le planificateur tourne.** La clôture de nuit (03:00, heure du site) et les
   escalades de gouvernance sont des tâches planifiées. Un site dont le
   planificateur est arrêté paraît parfaitement normal toute la journée, puis ne
   clôture jamais la nuit, en silence :

   ```bash
   docker compose exec backend bench --site <your-site-name> doctor
   ```

8. **Aucun compte de démonstration n'existe.** Voir la section 14. C'est la
   vérification qui compte le plus ; n'acceptez pas le système avant qu'elle
   passe.

---

## 9. TLS et exposition sûre

`frontend` publie du **HTTP simple** directement sur le port de l'hôte. Il ne
termine aucun TLS. Cela vient de la surcharge `noproxy` de l'amont et c'est le
bon défaut pour un fichier devant lequel vous placez votre propre proxy — ce
n'est pas une invitation à l'exploiter ainsi.

> **Ne servez pas un hôtel en HTTP simple.** Les pièces d'identité des clients,
> les références de cartes, les folios et les mots de passe du personnel passent
> tous par cette connexion.

Placez **nginx** ou **Caddy** devant, terminez-y le TLS, et relayez vers
`127.0.0.1:8080`. N'exposez pas le port 8080 directement sur Internet :
liez-le à localhost ou filtrez-le au pare-feu, et laissez le proxy seul y
accéder.

`install.sh` affiche la commande habituelle pour le certificat, dès que le DNS
pointe sur le serveur :

```bash
certbot --nginx -d pms.yourhotel.dz
```

Une fois un proxy en place, Frappe voit l'adresse du proxy comme adresse du
client pour chaque requête, ce qui rend la limitation de débit et la piste
d'audit inutiles. Les trois variables `UPSTREAM_REAL_IP_*` existent précisément
pour cela ; elles sont commentées dans `.env.example`. Réglez
`UPSTREAM_REAL_IP_ADDRESS` sur l'adresse **du proxy** :

```
UPSTREAM_REAL_IP_ADDRESS=127.0.0.1
UPSTREAM_REAL_IP_HEADER=X-Forwarded-For
UPSTREAM_REAL_IP_RECURSIVE=off
```

---

## 10. Au quotidien

Lancez ces commandes depuis `deploy/linux/`, le répertoire qui contient
`docker-compose.yml` et `.env`.

| | |
| --- | --- |
| État | `docker compose ps` |
| Journaux | `docker compose logs -f backend` |
| Un shell | `docker compose exec backend bash` |
| Redémarrer | `docker compose restart backend frontend` |
| Arrêter (conserve les données) | `docker compose down` |
| Sauvegarder | `docker compose exec backend bench --site <site> backup --with-files` |
| Migrer après une mise à jour | `docker compose exec backend bench --site all migrate` |
| Le planificateur est-il vivant ? | `docker compose exec backend bench --site <site> doctor` |

`docker compose down` laisse les trois volumes en place. **`docker compose
down -v` non.** Voir la section 13.

---

## 11. Sauvegardes

Un système de gestion hôtelière détient le seul enregistrement de qui arrive ce
soir, de ce que le client a accepté de payer, de ce qu'il a déjà payé, et de ce
que l'hôtel doit à l'administration fiscale. Le perdre n'est pas un désagrément
informatique.

```bash
docker compose exec backend bench --site <your-site-name> backup --with-files
```

**La règle unique : une sauvegarde que personne n'a restaurée n'est pas une
sauvegarde. C'est un fichier.**

Effectuez un test de restauration complet avant la réception du système, puis
une fois par trimestre. Restaurez dans un site jetable séparé, confirmez que les
réservations, l'argent **et les fichiers téléversés** sont bien revenus, et
**notez par écrit ce que vous avez dû faire**. Cette note est le mode opératoire
que quelqu'un utilisera à 2 heures du matin. Les procédures complètes —
planification, rétention, sortie des archives de la machine, et le test de
restauration lui-même — sont dans [`BACKUP.md`](../BACKUP.md). Lisez-le avant la
mise en service, pas après.

Trois points de `BACKUP.md` qui méritent d'être répétés ici :

- Sauvegardez toujours **avec les fichiers** (`--with-files`). Une sauvegarde de
  la seule base restaure un hôtel dont les scans de pièces d'identité, les
  fiches d'enregistrement signées et les pièces jointes de factures ont tous
  disparu — ce qui, pour un établissement algérien tenant une piste de fiche de
  police, est un problème de conformité, pas une sauvegarde partielle.
- **Sauvegardez `.env`** (et `/opt/kamra/kamra.env` s'il existe). Il contient le
  mot de passe de la base. Le perdre peut rendre un vidage de base impossible à
  restaurer.
- **Sauvegardez avant chaque mise à jour**, sans exception. Une mise à jour
  exécute des migrations de base de données, et les migrations ne sont pas
  réversibles — revenir en arrière veut dire restaurer.

Sur un hôte Linux, la planification se réduit à la crontab de root :

```cron
30 3 * * * /opt/kamra/backup.sh >> /var/log/kamra-backup.log 2>&1
```

La section 6 de `BACKUP.md` contient le script que cette ligne exécute. Pas de
Docker Desktop, pas de session ouverte, pas de portable en veille — ce qui
explique en grande partie pourquoi un serveur Linux est le profil recommandé.

---

## 12. Mise à jour

**Sauvegardez d'abord. Chaque fois.** Une mise à jour reconstruit l'image et
exécute des migrations de base de données, et les migrations ne sont pas
réversibles.

Si vous avez installé avec `install.sh` :

```bash
sudo /opt/kamra/install.sh update
```

Cela reconstruit l'image depuis l'`apps.json` enregistré, recrée les conteneurs,
puis exécute `bench --site all migrate` et `clear-cache` pour vous.

Si vous êtes sur la voie B, reconstruisez l'image avec la commande
`docker build` de la section 4, puis :

```bash
docker compose up -d && docker compose exec backend bench --site all migrate
```

Reprenez ensuite toute la section 8. Une mise à jour qui laisse le planificateur
arrêté est une mise à jour qui a arrêté la clôture de nuit.

---

## 13. Les données vivent dans des volumes

Pas dans le répertoire `deploy/linux/`. Copier ce répertoire ailleurs ne copie
rien de l'hôtel.

| Volume | Contenu |
| --- | --- |
| `sites` | la configuration du site, la **clé de chiffrement**, et tous les fichiers téléversés, y compris les scans de pièces d'identité |
| `db-data` | la base de données |
| `redis-queue-data` | les tâches en file d'attente |

> ### ⚠ `docker compose down -v` détruit les données
>
> `docker compose down` arrête les conteneurs et **laisse les trois volumes**.
> C'est la commande sûre, et c'est celle que vous voulez.
>
> `docker compose down -v` **détruit `sites` et `db-data`**. Pour un
> établissement en exploitation, cela représente chaque réservation, chaque
> folio et chaque fiche client, plus la clé de chiffrement et les scans de
> pièces d'identité. **Il n'y a aucun retour en arrière.** Et aucune demande de
> confirmation non plus.
>
> Ne tapez jamais `-v` sur un serveur d'établissement, sauf si vous venez de
> vérifier qu'une restauration fonctionne et que c'est exactement votre
> intention.

---

## 14. Sécurité

### Le mot de passe administrateur

- `install.sh` le demande et le lit **directement depuis la console**. Il
  n'entre jamais dans une variable d'environnement, un fichier de journal, ni
  l'historique de votre shell.
- **10 caractères** minimum. **Il n'existe aucune valeur par défaut dans tout ce
  système.**
- **Choisissez-le vous-même**, dans votre propre gestionnaire de mots de passe,
  et gardez-le vous-même.
- **Après la réception du système, ne le partagez pas avec le prestataire** — et
  si le prestataire en détient encore une copie, demandez-lui de la détruire.
  Personne en dehors de l'hôtel n'a besoin du mot de passe administrateur du
  système qui détient les pièces d'identité de vos clients.

### Un site de production ne doit jamais avoir les comptes de démonstration

> ### ⚠ AVERTISSEMENT — à lire avant de semer quoi que ce soit
>
> Semer des données d'exemple crée **six comptes utilisateurs dont les mots de
> passe sont publiés dans le code source public du produit**. L'un d'eux est un
> **administrateur système complet**.
>
> Ces mots de passe sont également compilés dans le paquet JavaScript que chaque
> visiteur du site télécharge. Désactiver `demo_mode` ne masque que les boutons
> de connexion de démonstration — **cela n'invalide pas les mots de passe**.
> Masquer un bouton n'est pas de la sécurité.
>
> **La seule protection réelle est que ces comptes n'existent pas.**
>
> `install.sh` ne sème rien et n'en crée aucun, et `bench new-site` de la voie B
> non plus. Donc :
>
> - **Ne semez jamais de données d'exemple sur un site en exploitation**, pas
>   même « juste pour avoir quelque chose à montrer ».
> - **Ne créez jamais ces comptes à la main.**
> - Si un site a déjà été semé et doit maintenant passer en production,
>   traitez-le comme **compromis** : faites *supprimer* les six comptes (et pas
>   seulement changer leurs mots de passe), faites rotater le mot de passe
>   `Administrator`, et faites auditer les journaux d'accès.

Pour confirmer qu'un site de production est propre, aucun compte ne doit exister
dont l'adresse se termine par `@kamra.local`. Votre prestataire peut effectuer
cette vérification pour vous ; demandez-en la sortie. Elle doit revenir **vide**
— pas « les mots de passe ont été changés », vide.

### Autres points à régler avant la mise en service

- **Placez HTTPS devant le site** (section 9) et n'exposez pas le port 8080
  directement sur Internet.
- **`.env` doit rester en mode 600 et ne jamais être versionné.** Il contient le
  mot de passe root de la base. `install.sh` écrit `/opt/kamra/kamra.env` sous
  `umask 077` pour la même raison.
- **Créez des comptes nominatifs pour le personnel** avec les bons rôles (Hotel
  Admin, Front Desk, Revenue, Finance, Housekeeping) plutôt que de partager une
  connexion unique.

---

## 15. Ce qui n'est pas encore prouvé

Cette section existe parce qu'un fournisseur qui dissimule ces points vous vend
une responsabilité. Rien ici n'est spéculatif, et rien n'est une raison de
paniquer. C'est une liste de choses que vos propres premiers jours d'usage
trancheront.

- **Ce fichier compose n'a jamais été démarré.** Il a été vérifié service par
  service contre les quatre fichiers de l'amont — l'ensemble des services, les
  images, les commandes, les ports, les tests de santé, les clés
  d'environnement et les volumes concordent tous — mais **il n'y a aucun démon
  Docker sur la machine où il a été écrit**. Donc `docker compose config` ne l'a
  jamais validé, et aucun conteneur n'en a jamais été issu. **Votre premier
  `docker compose up -d` est le véritable test.** Ce qu'il faut faire :
  exécutez-le sur une machine jetable avant de l'exécuter sur le serveur de
  l'établissement, et lisez `docker compose logs configurator` dès que quelque
  chose paraît anormal.

- **Les migrations `v36` et `v37` n'ont jamais été exécutées contre une base de
  données.** L'une traite la base de la taxe de séjour fixe par personne,
  l'autre les champs RC/NIS/AI de l'établissement. Aucune des deux n'avait été
  exécutée contre une véritable base de données où que ce soit. Si votre
  installation s'est achevée, **elles viennent de s'exécuter pour la première
  fois.** Ce qu'il faut faire : vérifiez qu'une réservation s'enregistre
  (section 8, point 4), et **prenez une sauvegarde avant chaque mise à jour
  future**, qui exécute aussi des migrations.

- **Personne n'a visualisé la mise en page arabe de droite à gauche dans un
  navigateur.** Le travail RTL est écrit et se vérifie au typage, autant que la
  lecture du code puisse l'établir, mais personne ne l'a affiché à l'écran pour
  le regarder. Il en va de même pour les mises en page d'impression française,
  arabe et anglaise. Ce qu'il faut faire : faites parcourir la réception, la page
  de réservation client et une facture imprimée par quelqu'un qui lit l'arabe,
  avant la mise en service. Attendez-vous à trouver des choses. Elles seront très
  probablement cosmétiques plutôt qu'arithmétiques — mais un hôtel est jugé sur
  ce que le client voit.

- **Les montants s'affichent `DA 1 500`, alors que la convention algérienne est
  `1 500,00 DA`.** Le montant, les séparateurs et le symbole sont tous corrects
  — seule la position ne l'est pas. Rien n'est donc ambigu ni faux ; ce n'est
  simplement pas ainsi qu'un comptable local l'écrit. Ce point a été **reporté
  délibérément**, avec un coût mesuré plutôt que supposé : la position du symbole
  n'est pas un réglage, elle est inscrite dans 233 emplacements d'affichage
  monétaire à travers le produit, factures imprimées incluses, et une migration
  partielle serait pire que rien — un écran affichant `DA 1 500` quand un autre
  affiche `1 500 DA` est un défaut, là où une non-convention cohérente n'en est
  pas un. Consigné comme limitation 19 dans
  [`IMPLEMENTATION_STATUS.md`](../IMPLEMENTATION_STATUS.md), avec le plan
  séquencé pour le faire proprement dès que les écrans pourront réellement être
  regardés.

- **Aucun test automatisé du backend n'a jamais été exécuté contre un vrai
  site.** Le contrôle qualité de cette version s'est limité à l'analyse statique
  et à des vérifications arithmétiques, non à une suite de tests exécutée.
  Considérez votre première installation comme le test, et prévoyez-y du temps.

`IMPLEMENTATION_STATUS.md` porte la liste complète, dont le type de chambre
exonéré de taxe qui ne peut pas être exprimé aujourd'hui, et le défaut de la
taxe en mode pourcentage avec les bons de réduction (utilisez le mode **fixe par
personne et par nuit**, qui n'est pas affecté et qui est de toute façon ce qu'un
établissement algérien veut).

---

## 16. Si quelque chose ne va pas

| Symptôme | Le plus souvent |
| --- | --- |
| Toutes les URL renvoient 404 alors que le site existe | **`FRAPPE_SITE_NAME_HEADER` ne correspond pas au nom du site.** À vérifier en premier. |
| Rien ne démarre ; `configurator` n'est pas en `Exited (0)` | lisez `docker compose logs configurator` — le plus souvent le mot de passe de la base |
| `DB_PASSWORD is required` au `up` | pas de `.env`, ou la variable est vide. C'est voulu — voir la section 5. |
| `Access denied for root` après modification de `.env` | MariaDB a conservé le mot de passe d'initialisation de son volume `db-data` ; rétablissez l'ancien `DB_PASSWORD` |
| **Algeria absente de la liste des pays** | l'image a été construite depuis l'amont — vérifiez `apps.json` et reconstruisez. Voir la section 7. |
| Prix dans une devise étrangère, taxe affichée GST | le pays de l'établissement a été laissé **vide**, donc le pack d'un autre pays s'est chargé |
| Pas de libellé TVA, pas de taxe de séjour | le pays de l'établissement est **mal orthographié**. Il doit se lire exactement `Algeria`. |
| La clôture de nuit ne s'exécute jamais | le conteneur `scheduler` est arrêté |
| La construction échoue en récupérant l'application | le dépôt source n'est pas publiquement lisible — il est cloné depuis l'intérieur du conteneur, sans authentification |
| Construction tuée, ou mémoire insuffisante | sous le plancher de RAM ; `install.sh` ajoute un fichier d'échange, une construction manuelle non |
| `docker build failed` après une longue exécution | généralement un disque plein. 40 Go est le minimum, pas l'objectif. |
| Tout est extrêmement lent | un serveur ARM émulant `linux/amd64`. Utilisez du x86-64. |
| `docker-compose: command not found` | il faut le greffon Compose **v2** — `docker compose`, en deux mots |
| `docker buildx is required` | BuildKit est absent ; le Containerfile en couches en a besoin (`apt install docker-buildx-plugin`) |
| Avertissements `ERPNEXT_VERSION` pendant l'installation | bruit sans conséquence provenant des fichiers de conteneurs sous-jacents |

Davantage dans [`deploy/TROUBLESHOOTING.md`](../../../deploy/TROUBLESHOOTING.md)
et [`deploy/linux/README.md`](../../../deploy/linux/README.md).

---

## 17. Obtenir de l'aide

Avant de contacter le support, rassemblez ceci. Sans cela, la première réponse
ne sera qu'une demande de ces éléments.

**Indiquez toujours le nom du produit et les deux numéros de version :**

```
Hotel MgM
Algeria Distribution 1.0.0
on Kamra core 2.6.5
```

Les deux numéros importent. « Kamra core 2.6.5 » seul ne dit pas si le pack
Algérie est installé, et le numéro de distribution seul ne dit pas sur quel
noyau il repose.

**Ajoutez ensuite :**

- Quelle voie vous avez suivie — **A (`install.sh`)** ou **B (construction
  manuelle + `docker compose`)**
- La sortie de `docker compose ps`, sous forme de texte — y compris l'état de
  `configurator`
- `docker compose logs configurator` et `docker compose logs backend`
- La commande exacte que vous avez lancée, copiée depuis le terminal
- Le nom de votre site, la valeur de `FRAPPE_SITE_NAME_HEADER`, et le port publié
- La distribution Linux et sa version, `docker compose version`, l'architecture
  du processeur (`uname -m`), et la quantité de RAM et d'espace disque libre du
  serveur
- Le texte exact de l'erreur, copié comme texte plutôt que décrit ou photographié
- À quel moment cela a échoué — construction de l'image, `up`, `configurator`,
  création du site, première connexion, assistant de configuration
- Si cela a déjà fonctionné, et ce qui a changé depuis

**Si le problème porte sur un montant ou une taxe sur un document**, joignez la
facture ou le folio imprimés et indiquez quel chiffre vous attendiez, et
pourquoi.

**N'incluez jamais le mot de passe administrateur ni le contenu de `.env`**, et
ne les envoyez jamais à qui que ce soit qui les demande — y compris à quelqu'un
se présentant comme votre fournisseur. Le support n'en a jamais besoin.

---

## Voir aussi

- [`INSTALL-fr.md`](INSTALL-fr.md) — l'installation Windows 10 / WSL2
- [`USER-fr.md`](USER-fr.md) — le guide d'utilisation au quotidien
- [`../BACKUP.md`](../BACKUP.md) — sauvegarde, restauration, planification et le test de restauration
- [`../TAXES.md`](../TAXES.md) — TVA, taxe de séjour et les identifiants légaux
- [`../IMPLEMENTATION_STATUS.md`](../IMPLEMENTATION_STATUS.md) — la liste complète de ce qui est prouvé et de ce qui ne l'est pas
- [`../VERSIONING.md`](../VERSIONING.md) — ce que signifient les deux numéros de version
- [`../../../deploy/linux/README.md`](../../../deploy/linux/README.md) — la référence opérateur que ce guide distille
- [`DOCKER-en.md`](DOCKER-en.md) — ce guide en anglais
- [`DOCKER-ar.md`](DOCKER-ar.md) — ce guide en arabe
