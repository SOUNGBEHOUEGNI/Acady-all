from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('portail/', views.choix_role, name='choix_role'),
    path('', views.home, name='home'),
    path('login/', views.connexion, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('accueil/', views.accueil_view, name='accueil'),
    path('inscription/', views.inscription, name='inscription'),
    path('consulter-notes/', views.consulter_notes, name='consulter_notes'),

    # --- GESTION DES CLASSES (DASHBOARD) ---
    path('classe/<str:classe>/<str:annee>/', views.liste_eleves_generique, name='afficher_college'),
    path('classe/<str:classe>/<str:serie>/<str:annee>/', views.liste_eleves_generique, name='afficher_lycee'),

    # --- ÉLÈVES ---
    path('enregistrer_eleve/', views.enregistrer_eleve, name='enregistrer_eleve'),
    path('modifier_eleve/<str:classe>/<int:eleve_id>/<str:annee>/', views.modifier_eleve, name='modifier_eleve'),
    path('supprimer/<int:id_eleve>/', views.supprimer_eleve, name='supprimer_eleve'),
    path('eleve/<int:eleve_id>/', views.notes_eleve, name='notes_eleve'),

    # --- NOTES (INSERTION) ---
    path('inserer-notes/<str:classe>/<str:annee_academique>/',views.inserer_notes_classe_view, name='inserer_notes_classe'),
    path('inserer-notes-serie/<str:classe>/<str:serie>/<str:annee_academique>/',views.inserer_notes_classe_view, name='inserer_notes_classe_serie'),

    # --- FICHES DE NOTES (DÉTAILS & RÉCAP) ---
    path('fiche_notes/<str:classe>/<str:annee_academique>/', views.fiche_notes_detail, name='fiche_notes_detail'),
    path('fiche_notes/<str:classe>/<str:serie>/<str:annee_academique>/', views.fiche_notes_detail, name='fiche_notes_detail_serie'),
    path('fiche_note/<str:classe>/<str:annee_academique>/', views.fiche_note, name='fiche_note'),
    path('fiche_note/<str:classe>/<str:serie>/<str:annee_academique>/', views.fiche_note, name='fiche_note_serie'),

    # --- MOYENNES TRIMESTRIELLES (PDF) ---
    path('trimestre1/<str:classe>/<str:annee_academique>/', views.affichemoy_trimestre1, name='trimestre_1'),
    path('trimestre1/<str:classe>/<str:serie>/<str:annee_academique>/', views.affichemoy_trimestre1, name='trimestre_1_serie'),
    path('trimestre2/<str:classe>/<str:annee_academique>/', views.affichemoy_trimestre2, name='trimestre_2'),
    path('trimestre2/<str:classe>/<str:serie>/<str:annee_academique>/', views.affichemoy_trimestre2, name='trimestre_2_serie'),
    path('trimestre3/<str:classe>/<str:annee_academique>/', views.affichemoy_trimestre3, name='trimestre_3'),
    path('trimestre3/<str:classe>/<str:serie>/<str:annee_academique>/', views.affichemoy_trimestre3, name='trimestre_3_serie'),

    path('export-excel/<str:classe>/<str:annee_academique>/<int:trimestre>/<str:serie>/',views.affiche_moy_excel_generique, name='affiche_moy_excel_generique'),
    
    # --- BULLETINS (INDIVIDUELS & MASSE) ---
    path('bulletins/<str:classe>/<str:trimestre>/tout/', views.telecharger_tous_bulletins, name='telecharger_tous_bulletins'),
    path('bulletins/<str:classe>/<str:serie>/<str:trimestre>/tout/', views.telecharger_tous_bulletins, name='telecharger_tous_bulletins_serie'),

    # --- EMAILS & NOTIFICATIONS ---
    path('envoyer/<str:classe>/<str:annee_academique>/', views.envoyer_notes, name='envoyer_notes'),
    path('envoyer/<str:classe>/<str:serie>/<str:annee_academique>/', views.envoyer_notes, name='envoyer_notes_serie'),
    path('envoyer_email/<int:eleve_id>/<int:trimestre>/', views.envoyer_email_notes, name='envoyer_email_notes'),
    path('choisir_trimestre/<int:eleve_id>/', views.choisir_trimestre, name='choisir_trimestre'),
    path('gestion/valider/<int:pk>/', views.valider_enseignant, name='valider_enseignant'),
    path('gestion/refuser/<int:pk>/', views.refuser_enseignant, name='refuser_enseignant'),
    path('gestion/validations/', views.liste_attente_enseignants, name='liste_attente_enseignants'),
    # --- LISTE PDF ÉMARGEMENT ---
    path('liste-pdf/<str:classe>/<str:annee_academique>/', views.liste_eleves, name='liste_eleves_pdf'),
    path('liste-pdf/<str:classe>/<str:serie>/<str:annee_academique>/', views.liste_eleves, name='liste_eleves_serie_pdf'),

    # --- CARTES SCOLAIRES (NOM UNIQUE POUR LES DEUX CAS) ---
    
    # Chemin pour le Lycée (3 paramètres : classe, serie, annee)
    path('cartes/<str:classe>/<str:serie>/<str:annee_academique>/', 
         views.generer_cartes_pdf, name='generer_cartes_pdf'),
    
    # Chemin pour le Collège (2 paramètres : classe, annee)
    path('cartes/<str:classe>/<str:annee_academique>/', 
         views.generer_cartes_pdf, name='generer_cartes_pdf'),
    # --- ENSEIGNANTS (DASHBOARD & LOGIN) ---
    path('enseignant/login/', views.enseignant_login, name='enseignant_login'),
    path('enseignant/dashboard/', views.dashboard_enseignant, name='dashboard_enseignant'),
    path("register/", views.register_enseignant, name="register_enseignant"),
    path('enseignant/notes/<str:classe>/<str:serie>/<str:annee_academique>/', views.inserer_notes_classe_enseignant, name='inserer_notes_classe_enseignant'),
    path('notes/voir/<str:classe>/<str:annee_academique>/<str:matiere>/', 
         views.fiche_notes_detail_enseignant, name='fiche_notes_detail_enseignant_simple'),

    path('notes/voir/<str:classe>/<str:serie>/<str:annee_academique>/<str:matiere>/', 
         views.fiche_notes_detail_enseignant, name='fiche_notes_detail_enseignant_serie'),
    path('enseignant/logout/', views.enseignant_logout, name='enseignant_logout'),
    path("enseignants/", views.liste_enseignants, name="liste_enseignants"),
    path("enseignants/supprimer/<int:enseignant_id>/", views.supprimer_enseignant, name="supprimer_enseignant"),
    path('gestion/heures_mensuelles_recap/', views.heures_mensuelles_recap, name='heures_mensuelles_recap'),
    path('gestion/heures_mensuelles/', views.heures_mensuelles, name='heures_mensuelles'),
    # --- NOTES (INSERTION) ---
    # Remplace 'inserer_notes_classe_view' par 'inserer_notes_classe_enseignant'
    path('inserer-notes/<str:classe>/<str:annee_academique>/', 
         views.inserer_notes_classe_enseignant, name='inserer_notes_classe'),
         
    path('inserer-notes-serie/<str:classe>/<str:serie>/<str:annee_academique>/', 
         views.inserer_notes_classe_enseignant, name='inserer_notes_classe_serie'),
    

    # --- EMPLOI DU TEMPS & PRÉSENCE ---
    path('enseignant/<int:enseignant_id>/ajouter_horaire/', views.ajouter_horaire, name='ajouter_horaire'),
    path('enseignants/<int:enseignant_id>/modifier_horaire/', views.modifier_horaire, name='modifier_horaire'),
    path('enseignant/<int:enseignant_id>/emploi_du_temps/', views.mon_emploi_du_temps, name='mon_emploi_du_temps'),
    path('presence/<str:classe_nom>/<int:horaire_id>/', views.marquer_presence, name='marquer_presence'),
    path('gestion/absents/', views.liste_absents, name='liste_absents'),
    path('rapport-heures-enseignants/', views.rapport_heures_prof, name='rapport_heures_prof'),

    # --- SÉCURITÉ & OTP ---
    path('enseignant/verification-otp/', views.enseignant_verification_otp, name='enseignant_verification_otp'),
    path('verifier-email/', views.verifier_otp, name='verifier_otp'),
    path("enseignant/mdp_oublie/", views.enseignant_mdp_oublie, name="enseignant_mdp_oublie"),
    path("enseignant/mdp_oublie/otp/", views.enseignant_mdp_oublie_otp, name="enseignant_mdp_oublie_otp"),
    path("enseignant/mdp_oublie/reset/", views.enseignant_mdp_oublie_reset, name="enseignant_mdp_oublie_reset"),

    # --- DIVERS ---
    path('suivre-eleve/', views.suivre_eleve_form, name='suivre_eleve'),
    path('suivre-eleve/resultat/', views.suivre_eleve_resultat, name='suivre_eleve_resultat'),
    path('resultats-annuels/', views.resultats_annuels, name='resultats_annuels'),
    path('reset/', views.reset_utilisateurs, name='reset_utilisateurs'),
    path('enseignant/profil/modifier/', views.modifier_profil, name='modifier_profil'),
    path('configurer-professeurs-principaux/', views.gestion_professeur_principal, name='gestion_pp'),
    path('supprimer-pp/<int:pk>/', views.supprimer_professeur_principal, name='supprimer_pp'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)