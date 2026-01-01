📌 Présentation générale

Ce projet implémente la partie base de données d’une plateforme universitaire de dépôt de mémoires,
conformément aux exigences du module ISMS.

La logique métier est centralisée dans PostgreSQL, afin de garantir :

la cohérence des données

la sécurité

l’automatisation des contrôles

la traçabilité des opérations (audit)

La base repose sur :

une base de données : plateforme_memoire

un schéma dédié : isms

🗂️ Organisation des scripts SQL

La base de données est construite à l’aide de 6 scripts SQL, à exécuter dans l’ordre.

1️⃣ 01_schema_tables.sql
Création du schéma et des tables

Objectif :
Créer la structure physique de la base de données.

Contenu :

Création du schéma isms

Création de toutes les tables métier :

etudiant

responsable

memoire

soutenance

jury

note

encadrement

composition_jury

Tables de référence :

annee_universitaire

niveau

departement

salle

grade

Contraintes d’intégrité :

PRIMARY KEY

FOREIGN KEY

UNIQUE

CHECK

NOT NULL

DEFAULT

Index pour optimiser les performances

📌 Ce script pose la fondation de toute la base.

2️⃣ 02_audit_triggers.sql
Audit, triggers et règles métier

Objectif :
Rendre la base de données intelligente, sécurisée et cohérente.

Contenu :

Ajout des champs techniques :

created_at

updated_at

Création de la table audit_log

Triggers automatiques pour :

journaliser les INSERT / UPDATE / DELETE

mettre à jour updated_at

Règles métier implémentées via triggers :

une soutenance ne peut être planifiée que si le mémoire est VALIDE

une note ne peut être saisie que si la soutenance est EFFECTUEE

interdiction de conflit de salle (date + heure)

contrôle des transitions de statut des mémoires

jury valide (au moins 3 membres, président et rapporteur)

neutralité : un encadrant ne peut pas être membre du jury du même mémoire

un mémoire doit avoir au moins un encadrant

📌 Ce script garantit la cohérence fonctionnelle du système.

3️⃣ 03_functions_business.sql
Fonctions métier (PL/pgSQL)

Objectif :
Encapsuler la logique métier dans des fonctions réutilisables.

Contenu :

Fonctions de gestion des mémoires :

valider un mémoire

refuser un mémoire

remettre un mémoire en vérification

Fonctions de gestion des soutenances :

planifier une soutenance

marquer une soutenance comme effectuée

annuler une soutenance

Fonctions liées aux notes :

enregistrer une note

calculer la note finale

📌 Ces fonctions peuvent être appelées directement par Django ou via des requêtes SQL.

4️⃣ 04_security_roles.sql
Sécurité et gestion des accès

Objectif :
Mettre en place une gestion des rôles conforme aux bonnes pratiques ISMS.

Contenu :

Création des rôles PostgreSQL :

admin_db : administration complète

app_user : utilisateur technique de l’application Django

Attribution des droits selon le principe du moindre privilège

Protection des données sensibles (mot_de_pass)

Création de vues sécurisées :

v_etudiant_public

v_responsable_public

Restriction de l’accès à la table d’audit

📌 Ce script répond aux exigences de sécurité et contrôle des accès.

5️⃣ 05_views_dashboards.sql
Vues et tableaux de bord

Objectif :
Faciliter l’affichage et l’analyse des données dans l’application.

Contenu :

Vues analytiques :

mémoires par statut

soutenances à venir

notes finales

détails complets des mémoires et soutenances

Vue matérialisée :

statistiques par département et année universitaire

Fonction de rafraîchissement de la vue matérialisée

📌 Ces vues sont exploitées par Django pour les tableaux de bord.

6️⃣ 06_seed_test_data.sql
Données de test (seed)

Objectif :
Fournir un jeu de données cohérent pour :

tester les règles métier

tester les triggers et fonctions

démontrer la plateforme

Contenu :

Années universitaires

Niveaux et départements

Salles et grades

Responsables (président, rapporteur, encadrants)

Étudiants

Mémoires (validés, en vérification)

Jurys et compositions

Soutenances (planifiées et effectuées)

Notes finales

📌 Ce script permet une démo immédiate sans saisie manuelle.

▶️ Ordre d’exécution obligatoire

01_schema_tables.sql

02_audit_triggers.sql

03_functions_business.sql

05_views_dashboards.sql

04_security_roles.sql

06_seed_test_data.sql

✅ Résultat final

À la fin de ces scripts :

la base est complète

la logique métier est centralisée dans PostgreSQL

la sécurité est appliquée

les données sont prêtes pour l’intégration Django