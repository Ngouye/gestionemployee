# EmployeeManager — Système d'information RH

Application web de gestion des ressources humaines pour PME et ETI : dossiers du personnel, congés, présences,
paie, notes de frais, recrutement, évaluations et formations, avec un espace self-service pour chaque collaborateur.

- **Technologie** : Python 3.13, Django 5.2 LTS, PostgreSQL 16, Bootstrap 5 (fonctionne hors ligne).
- **Déploiement** : Docker / Docker Compose, Gunicorn, WhiteNoise.
- **Langue et région** : interface en français, fuseau Africa/Dakar, devise FCFA (tout est paramétrable).

---

## Sommaire

1. [Modules](#modules)
2. [Rôles et droits](#rôles-et-droits)
3. [Démarrage rapide avec Docker](#démarrage-rapide-avec-docker)
4. [Configuration](#configuration)
5. [Mise en production](#mise-en-production)
6. [Sauvegarde et restauration](#sauvegarde-et-restauration)
7. [Reprise des données existantes](#reprise-des-données-existantes)
8. [Paramétrage de la paie](#paramétrage-de-la-paie)
9. [API REST](#api-rest)
10. [Développement local et tests](#développement-local-et-tests)
11. [Structure du projet](#structure-du-projet)

---

## Modules

| Module | Fonctionnalités |
|---|---|
| **Tableau de bord** | Indicateurs RH (effectif, présence du jour, congés en attente, masse salariale), embauches sur 12 mois, effectif par département, alertes (fins de contrat, périodes d'essai, documents expirés, anniversaires). |
| **Employés** | Fiche complète (état civil, coordonnées, poste, banque, sécurité sociale, contact d'urgence), matricule automatique, photo, historique des contrats et avenants, documents privés, annuaire, organigramme, import Excel/CSV, exports, **attestation et certificat de travail en PDF** (demande possible depuis l'espace employé). |
| **Organisation** | Départements (hiérarchie, responsable), postes (grade, statut cadre, fourchette salariale). |
| **Congés et absences** | Types de congé paramétrables, soldes annuels avec report, décompte en jours ouvrés (week-ends et jours fériés exclus), demi-journées, justificatifs, circuit de validation par le manager ou les RH, calendrier d'équipe, saisie d'absence par les RH. |
| **Présences** | Pointage arrivée/départ en un clic, détection des retards, registre journalier, rapport mensuel avec taux de présence et export Excel, **heures supplémentaires** saisies par le manager ou les RH avec majorations paramétrables. |
| **Paie** | Cotisations paramétrables (taux salarial et patronal, plafonds, cadres / non-cadres), barème progressif de l'impôt, abattement forfaitaire, primes et retenues récurrentes ou ponctuelles, prorata d'entrée et de sortie, congés sans solde, bulletins PDF, livre de paie et ordre de virement Excel, circuit brouillon → validée → payée. |
| **Notes de frais** | Catégories avec plafonds, justificatifs, validation, suivi des remboursements. |
| **Recrutement** | Offres d'emploi, pipeline Kanban (glisser-déposer), fiches candidats, CV, entretiens et comptes rendus, page carrières publique avec formulaire de candidature, création de la fiche employé à l'embauche. |
| **Évaluations** | Campagnes d'entretiens annuels, auto-évaluation, grille de critères, objectifs avec suivi d'avancement. |
| **Formations** | Catalogue, sessions, inscriptions, demandes des employés, présence, satisfaction, attestations. |
| **Communication** | Annonces internes (ciblées par département, épinglées, avec expiration), notifications internes et par e-mail. |
| **Administration** | Utilisateurs et rôles, paramètres de l'entreprise (logo, NINEA, RCCM, horaires, jours travaillés), journal d'audit détaillé (qui a modifié quoi, avant/après, adresse IP), API REST. |

## Rôles et droits

| Rôle | Accès |
|---|---|
| **Administrateur** | Tout, y compris utilisateurs, paramètres, journal d'audit et réouverture d'une paie validée. |
| **Ressources humaines** | Tous les modules RH et la paie. |
| **Manager** | Son équipe directe : fiches (sans données salariales), validation des congés et notes de frais, présences, objectifs, évaluations. |
| **Employé** | Son espace personnel : profil, congés, pointage, bulletins de paie, notes de frais, objectifs, formations. |

Un collaborateur qui a des subordonnés obtient automatiquement les droits de validation sur son équipe.

## Démarrage rapide avec Docker

Prérequis : Docker Desktop (Windows / macOS) ou Docker Engine avec le plugin Compose (Linux).

```bash
# 1. Créer le fichier de configuration
cp .env.example .env
#    puis éditez .env : DJANGO_SECRET_KEY, POSTGRES_PASSWORD, DJANGO_SUPERUSER_EMAIL / _PASSWORD

# 2. Construire et démarrer
docker compose up -d --build

# 3. Ouvrir l'application
#    http://localhost:8000
```

Au premier démarrage, le conteneur :
1. attend que PostgreSQL soit prêt ;
2. applique les migrations ;
3. crée le compte administrateur défini dans `.env` ;
4. charge les données de démonstration si `SEED_DEMO=1`.

### Comptes de démonstration (`SEED_DEMO=1`)

Mot de passe commun : `Demo2026!` (modifiable avec `DEMO_PASSWORD`).

| E-mail | Rôle |
|---|---|
| `direction@demo.sn` | Administrateur (directeur général) |
| `rh@demo.sn` | Ressources humaines |
| `manager@demo.sn` | Manager (responsable informatique) |
| `employe@demo.sn` | Employé |

> En exploitation réelle, laissez `SEED_DEMO=0`. Les données de démonstration ne sont chargées que si la base ne contient encore aucun employé.

### Commandes utiles

```bash
docker compose logs -f web                         # journaux de l'application
docker compose exec web python manage.py shell     # console Django
docker compose exec web python manage.py createsuperuser
docker compose down                                # arrêter (les données sont conservées)
docker compose down -v                             # arrêter ET supprimer les données
```

Le point de contrôle `GET /sante/` renvoie l'état de l'application et de la base (utilisé par le healthcheck Docker).

## Configuration

Toute la configuration passe par des variables d'environnement (fichier `.env`). Voir [.env.example](.env.example) pour la liste complète.

| Variable | Rôle |
|---|---|
| `DJANGO_SECRET_KEY` | Clé secrète (obligatoire, longue et aléatoire). |
| `DJANGO_DEBUG` | `0` en exploitation. |
| `DJANGO_ALLOWED_HOSTS` | Noms de domaine autorisés, séparés par des virgules. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | URL publiques avec schéma (ex. `https://rh.entreprise.sn`). |
| `DATABASE_URL` | Base de données hors Docker (`postgres://…`). Sans cette variable, SQLite est utilisé. |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | Serveur SMTP. Sans `EMAIL_HOST`, les e-mails sont écrits dans les journaux. |
| `EMAIL_NOTIFICATIONS` | `1` pour doubler les notifications internes par e-mail. |
| `MAX_UPLOAD_SIZE_MB` | Taille maximale des fichiers (10 Mo par défaut). |
| `LOGIN_MAX_ATTEMPTS`, `LOGIN_LOCKOUT_SECONDS` | Verrouillage après échecs de connexion (5 essais, 15 minutes par défaut). |

Les informations de l'entreprise (raison sociale, logo, NINEA, RCCM, devise, horaires, jours travaillés, préfixe des matricules, abattement fiscal, signataire des attestations) se règlent dans l'application : **Administration → Paramètres**.

## Mise en production

1. **HTTPS obligatoire** : placez l'application derrière un reverse proxy (Nginx, Caddy, Traefik) qui gère le certificat TLS, puis activez dans `.env` :
   ```
   DJANGO_BEHIND_PROXY=1
   DJANGO_SECURE_COOKIES=1
   DJANGO_SSL_REDIRECT=1
   DJANGO_HSTS_SECONDS=31536000
   DJANGO_ALLOWED_HOSTS=rh.entreprise.sn
   DJANGO_CSRF_TRUSTED_ORIGINS=https://rh.entreprise.sn
   ```
2. **Secrets** : générez une nouvelle `DJANGO_SECRET_KEY` et un mot de passe PostgreSQL robuste pour chaque client.
3. **E-mails** : configurez le SMTP pour la réinitialisation des mots de passe et les notifications.
4. **Sauvegardes** : planifiez la sauvegarde quotidienne de la base et des fichiers (voir ci-dessous).
5. Vérifiez la configuration : `docker compose exec web python manage.py check --deploy`.

### Sécurité intégrée

- Mots de passe hachés (PBKDF2), règles de complexité, verrouillage après échecs.
- Mots de passe temporaires à changer obligatoirement à la première connexion.
- Protection CSRF, en-têtes de sécurité, cookies `HttpOnly`, déconnexion par POST uniquement.
- **Documents privés** : contrats, CV, justificatifs et photos ne sont jamais servis publiquement ; chaque téléchargement passe par un contrôle des droits.
- Contrôle des extensions et de la taille des fichiers téléversés.
- Journal d'audit de toutes les créations, modifications (avec valeurs avant/après), suppressions et connexions.
- Conteneur exécuté avec un utilisateur non privilégié.

## Sauvegarde et restauration

```bash
# Sauvegarde de la base
docker compose exec -T db pg_dump -U employeemanager -Fc employeemanager > sauvegarde_$(date +%F).dump

# Sauvegarde des fichiers (documents, photos, justificatifs)
docker compose run --rm -v "$PWD":/backup web tar czf /backup/fichiers_$(date +%F).tar.gz -C /app media

# Restauration de la base
docker compose exec -T db pg_restore -U employeemanager -d employeemanager --clean < sauvegarde_AAAA-MM-JJ.dump
```

## Reprise des données existantes

- **Fichier Excel / CSV** : *Personnel → Import*. Téléchargez le modèle, complétez-le, importez-le. Les départements et postes inconnus sont créés ; un rapport liste les lignes en erreur.
- **Ancienne version d'EmployeeManager (v1)** : la base d'origine a été archivée dans `legacy/db_ancien.sqlite3`. Pour reprendre ses employés :
  ```bash
  python manage.py import_legacy                    # en local
  docker compose cp legacy/db_ancien.sqlite3 web:/tmp/ancien.sqlite3
  docker compose exec web python manage.py import_legacy /tmp/ancien.sqlite3   # dans Docker
  ```

## Paramétrage de la paie

Le moteur de paie est **générique et entièrement paramétrable** :

1. **Cotisations** (*Paie → Cotisations*) : libellé, assiette (brut ou base), taux salarial et patronal, plafond mensuel, population concernée (tous, cadres, non-cadres), déductibilité fiscale.
2. **Barème de l'impôt** (*Paie → Barème de l'impôt*) : tranches annuelles progressives.
3. **Abattement forfaitaire** (*Administration → Paramètres*) : pourcentage et plafond annuel.
4. **Primes et retenues** (*Paie → Primes et retenues*) : par employé, récurrentes ou ponctuelles, imposables ou non.
5. **Heures supplémentaires** (*Présences → Majorations*) : taux de majoration par catégorie (41e à 48e heure, au-delà, nuit, dimanche et jours fériés). Les heures saisies sont payées au taux horaire (salaire de base ÷ heures mensuelles du contrat) majoré. Une fois la paie du mois validée, elles ne sont plus modifiables.

Calcul d'un bulletin :
- salaire de base au prorata des jours de présence ;
- ajout des primes et des heures supplémentaires, retrait des absences non rémunérées → **brut** ;
- calcul des cotisations sur l'assiette plafonnée ;
- calcul de l'impôt : revenu annualisé, moins l'abattement, puis application du barème ;
- retrait des autres retenues → **net à payer**.

> ⚠️ **Important** — Les taux fournis avec les données de démonstration servent d'exemple : IPRES, CSS, IPM, CFCE, barème de l'IR et abattement. Les taux, plafonds et règles évoluent avec la législation et les conventions collectives. **Faites valider l'ensemble du paramétrage par l'expert-comptable de l'entreprise avant la première paie réelle.**
>
> Ne sont pas calculées automatiquement dans cette version :
> - les réductions d'impôt pour charges de famille ;
> - la TRIMF.
>
> Saisissez-les si besoin comme retenues ou primes.

## API REST

L'API est disponible sous `/api/v1/` (navigable dans le navigateur une fois connecté).

| Point d'accès | Description |
|---|---|
| `POST /api/v1/jeton/` | Obtenir un jeton (`username` = e-mail, `password`). |
| `GET /api/v1/moi/` | Profil de l'utilisateur connecté et soldes de congés. |
| `/api/v1/employes/` | Employés : fiche complète pour les RH, annuaire pour les autres. |
| `/api/v1/departements/`, `/api/v1/postes/` | Organisation (lecture pour tous, écriture RH). |
| `/api/v1/types-conges/` | Types de congé. |
| `/api/v1/conges/` | Demandes de congé (création pour soi-même). |
| `/api/v1/presences/` | Présences (les siennes, ou toutes pour les RH). |

Authentification : en-tête `Authorization: Token <jeton>`. Chaque utilisateur peut générer son jeton depuis *Mon compte*.

## Développement local et tests

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/macOS : source .venv/bin/activate)
pip install -r requirements.txt

# .env : DJANGO_DEBUG=1 suffit pour le développement (SQLite)
python manage.py migrate
python manage.py createcachetable
python manage.py seed_demo        # données de démonstration
python manage.py runserver
```

Tests automatisés : `python manage.py test core`. Ils couvrent :
- l'affichage de toutes les pages pour chaque rôle et les refus d'accès ;
- la sécurité des fichiers ;
- le verrouillage de connexion ;
- le circuit des congés ;
- les calculs de paie ;
- l'API et l'import.

## Structure du projet

```
employeemanager/   configuration Django (settings, urls, wsgi/asgi)
accounts/          utilisateurs, rôles, connexion, mots de passe
core/              socle : tableau de bord, paramètres, notifications, annonces, audit, vues génériques, commandes
organization/      départements et postes
employees/         employés, contrats, documents, import, annuaire, organigramme
leaves/            congés, soldes, jours fériés, calendrier
attendance/        pointage et rapports de présence
payroll/           cotisations, barème, primes, périodes, bulletins PDF
expenses/          notes de frais
recruitment/       offres, candidatures, entretiens, page carrières
performance/       campagnes d'évaluation et objectifs
training/          formations et participants
api/               API REST (Django REST Framework)
templates/         gabarits HTML
static/            CSS, JavaScript et bibliothèques (Bootstrap, icônes, Chart.js, SortableJS)
docker/            script de démarrage du conteneur
```

---

Version 2.0.0
