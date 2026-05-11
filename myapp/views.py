from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import Http404
from .models import Eleve , Note , Login
from django.db.models import Sum, Avg, Sum, F, FloatField
from django.core.paginator import Paginator
from datetime import datetime
import os
import sys
from django.contrib.auth.hashers import check_password, make_password
from .utils import get_coefficient, get_appreciation
NOM_ECOLE = "LE TRESOR DE DOWA"
def home(request):
    return render(request, 'index.html') 

def choix_role(request):
    return render(request, "choix_role.html")

from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password
import random
from .models import Enseignant

# ------------------------------
# INSCRIPTION ENSEIGNANT
# ------------------------------
from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from .models import Enseignant
from django.db.models import Q

from django.shortcuts import render, redirect
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from django.utils import timezone
from .models import Enseignant

def register_enseignant(request):
    # 1. Calcul automatique de l'année académique (ex: 2025-2026)
    now = timezone.now()
    if now.month < 9:  # Avant septembre, on est encore dans l'année commencée l'an dernier
        annee_auto = f"{now.year - 1}-{now.year}"
    else:              # À partir de septembre, nouvelle année
        annee_auto = f"{now.year}-{now.year + 1}"
    
    context = {'annee_auto': annee_auto}

    if request.method == 'POST':
        # 2. Récupération des données de base
        nom = request.POST.get('nom')
        prenoms = request.POST.get('prenoms')
        email = request.POST.get('email')
        password = request.POST.get('password')
        annee_saisie = request.POST.get('annee_academique', annee_auto)
        
        # 3. Récupération des listes multiples
        matieres_list = request.POST.getlist('matieres')
        classes_raw = request.POST.getlist('classes')

        # 4. Logique cruciale : Liaison Classe <-> Série
        final_classes = []
        for cls in classes_raw:
            # On génère la clé correspondante : series_2nde, series_1ère, series_tle
            # .replace('è', 'e') est une sécurité pour les caractères accentués dans les clés POST
            key = f"series_{cls.lower().replace('è', 'e')}"
            series_selectionnees = request.POST.getlist(key)
            
            if series_selectionnees:
                # Si des séries sont cochées pour cette classe, on crée "2nde C", "2nde D", etc.
                for s in series_selectionnees:
                    final_classes.append(f"{cls} {s}")
            else:
                # Si c'est le premier cycle (6ème, etc.), on garde le nom simple
                final_classes.append(cls)

        # 5. Conversion des listes en chaînes de caractères pour la BDD
        matieres_str = ",".join(matieres_list)
        classes_str = ",".join(final_classes)

        # 6. Vérification de sécurité (Email unique)
        if Enseignant.objects.filter(email=email).exists():
            context['error'] = "Cet email est déjà associé à un compte."
            return render(request, 'enseignant/register.html', context)

        # 7. Création de l'enseignant
        try:
            Enseignant.objects.create(
                nom=nom,
                prenoms=prenoms,
                email=email,
                password=make_password(password), # Hachage du mot de passe
                matiere=matieres_str,
                classes=classes_str,
                annee_academique=annee_saisie
            )
            messages.success(request, "Compte créé avec succès ! Vous pouvez vous connecter.")
            return redirect('enseignant_login')
            
        except Exception as e:
            context['error'] = f"Erreur lors de l'enregistrement : {e}"

    return render(request, 'enseignant/register.html', context)

def enseignant_login(request):
    next_url = request.GET.get('next', '')

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        next_url = request.POST.get('next', '')

        try:
            enseignant = Enseignant.objects.get(email=email)
            
            # 1. Vérification du mot de passe
            if check_password(password, enseignant.password):
                
                # === NOUVELLE FONCTIONNALITÉ : VÉRIFICATION DE L'ADHÉSION ===
                if not enseignant.est_approuve:
                    messages.error(request, "Votre compte est en attente de validation par l'administration. Un mail vous sera envoyé dès que votre accès sera autorisé.")
                    return render(request, 'enseignant/login.html', {'next': next_url})
                # ============================================================

                # Si approuvé, on continue la logique OTP
                otp_code = str(random.randint(100000, 999999))
                enseignant.otp_code = otp_code
                enseignant.otp_timestamp = timezone.now()
                enseignant.save()

                send_mail(
                    'Code de connexion - Acadynote',
                    f'Bonjour {enseignant.nom}, votre code de connexion est : {otp_code}',
                    settings.DEFAULT_FROM_EMAIL,
                    [enseignant.email],
                    fail_silently=False
                )

                request.session['temp_enseignant_id'] = enseignant.id
                request.session['next_url_after_otp'] = next_url
                
                messages.success(request, 'Un code a été envoyé à votre email. Il expire dans 120 secondes.')
                return redirect('enseignant_verification_otp')
            else:
                messages.error(request, 'Mot de passe incorrect.')

        except Enseignant.DoesNotExist:
            messages.error(request, 'Aucun compte trouvé avec cet email.')

    return render(request, 'enseignant/login.html', {'next': next_url})
# ------------------------------
# VERIFICATION OTP LOGIN
# ------------------------------
def enseignant_verification_otp(request):
    if request.method == "POST":
        code_saisi = request.POST.get("otp")
        enseignant_id = request.session.get("temp_enseignant_id")

        if not enseignant_id:
            messages.error(request, "Session expirée, veuillez vous reconnecter.")
            return redirect("enseignant_login")

        try:
            enseignant = Enseignant.objects.get(id=enseignant_id)
            now = timezone.now()

            if enseignant.otp_code and enseignant.otp_timestamp:
                delta = now - enseignant.otp_timestamp

                if delta.total_seconds() <= 120:
                    if code_saisi == enseignant.otp_code:
                        # --- CONNEXION RÉUSSIE ---
                        request.session['enseignant_id'] = enseignant.id
                        request.session['enseignant_nom'] = f"{enseignant.nom} {enseignant.prenoms}"
                        request.session['enseignant_matiere'] = enseignant.matiere

                        # Nettoyage de l'OTP en base
                        enseignant.otp_code = None
                        enseignant.otp_timestamp = None
                        enseignant.save()

                        # --- GESTION DE LA REDIRECTION (NEXT) ---
                        # On récupère l'URL de destination mémorisée lors du login
                        next_destination = request.session.get('next_url_after_otp')
                        
                        # Nettoyage des variables temporaires de session
                        if 'temp_enseignant_id' in request.session: del request.session['temp_enseignant_id']
                        if 'next_url_after_otp' in request.session: del request.session['next_url_after_otp']

                        # Redirection vers la page demandée ou le dashboard par défaut
                        if next_destination:
                            return redirect(next_destination)
                        return redirect('dashboard_enseignant')
                    
                    else:
                        messages.error(request, "Code incorrect.")
                else:
                    # --- CODE EXPIRÉ : GÉNÉRATION NOUVEAU CODE ---
                    messages.error(request, "Code expiré. Un nouveau code a été envoyé.")
                    otp_code = str(random.randint(100000, 999999))
                    enseignant.otp_code = otp_code
                    enseignant.otp_timestamp = timezone.now()
                    enseignant.save()
                    
                    send_mail(
                        'Nouveau code de connexion',
                        f'Bonjour {enseignant.nom}, votre nouveau code de connexion est : {otp_code}',
                        settings.DEFAULT_FROM_EMAIL,
                        [enseignant.email],
                        fail_silently=False
                    )
            else:
                messages.error(request, "Pas de code OTP généré. Veuillez vous reconnecter.")

        except Enseignant.DoesNotExist:
            messages.error(request, "Utilisateur introuvable.")

    return render(request, "enseignant/verification_otp.html")
# ------------------------------
# MOT DE PASSE OUBLIE
# ------------------------------
def enseignant_mdp_oublie(request):
    if request.method == "POST":
        email = request.POST.get("email")

        try:
            enseignant = Enseignant.objects.get(email=email)

            otp = str(random.randint(100000, 999999))
            enseignant.otp_code = otp
            enseignant.otp_timestamp = timezone.now()
            enseignant.save()

            send_mail(
                "Code de réinitialisation",
                f"Votre code est : {otp}",
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False
            )

            request.session["reset_enseignant_id"] = enseignant.id
            messages.success(request, "Un code a été envoyé à votre email.")
            return redirect("enseignant_mdp_oublie_otp")

        except Enseignant.DoesNotExist:
            messages.error(request, "Aucun compte trouvé avec cet email.")

    return render(request, "enseignant/mdp_oublie_email.html")

# ------------------------------
# OTP POUR RESET MOT DE PASSE
# ------------------------------
def enseignant_mdp_oublie_otp(request):
    enseignant_id = request.session.get("reset_enseignant_id")

    if enseignant_id is None:
        return redirect("enseignant_mdp_oublie")

    enseignant = Enseignant.objects.get(id=enseignant_id)

    if request.method == "POST":
        otp = request.POST.get("otp")
        if otp == enseignant.otp_code:
            diff = timezone.now() - enseignant.otp_timestamp
            if diff.total_seconds() <= 120:
                return redirect("enseignant_mdp_oublie_reset")
            else:
                messages.error(request, "Le code a expiré.")
        else:
            messages.error(request, "Code incorrect.")

    return render(request, "enseignant/mdp_oublie_otp.html")

# ------------------------------
# RESET MOT DE PASSE
# ------------------------------
import re
def password_is_valid(password):
    return (
        len(password) >= 8 and
        re.search(r"[A-Z]", password) and
        re.search(r"[0-9]", password)
    )

def enseignant_mdp_oublie_reset(request):
    enseignant_id = request.session.get("reset_enseignant_id")

    if enseignant_id is None:
        return redirect("enseignant_mdp_oublie")

    enseignant = Enseignant.objects.get(id=enseignant_id)

    if request.method == "POST":
        p1 = request.POST.get("password1")
        p2 = request.POST.get("password2")

        if p1 != p2:
            messages.error(request, "❌ Les mots de passe ne correspondent pas.")
            return redirect("enseignant_mdp_oublie_reset")

        if not password_is_valid(p1):
            messages.error(request, 
                "❌ Le mot de passe doit contenir au minimum 8 caractères, "
                "au moins 1 chiffre et 1 symbole."
            )
            return redirect("enseignant_mdp_oublie_reset")

        # Hacher le mot de passe
        enseignant.password = make_password(p1)
        enseignant.otp_code = None
        enseignant.save()

        del request.session["reset_enseignant_id"]

        messages.success(request, "✅ Mot de passe réinitialisé avec succès ! Connectez-vous.")
        return redirect("enseignant_login")

    return render(request, "enseignant/mdp_oublie_reset.html")

from django.shortcuts import render, redirect
from datetime import datetime, timedelta
from myapp.models import Enseignant, Horaire
from django.views.decorators.cache import never_cache

@never_cache
def dashboard_enseignant(request):
    enseignant_id = request.session.get('enseignant_id')
    
    if not enseignant_id:
        # On redirige vers le login avec le paramètre 'next' 
        # pour revenir ici après la connexion
        return redirect(f'/enseignant/login/?next={request.path}')
    enseignant_id = request.session.get('enseignant_id')

    try:
        enseignant = Enseignant.objects.get(id=enseignant_id)
    except Enseignant.DoesNotExist:
        return redirect('enseignant_login')

    # Liste des matières
    if enseignant.matiere:
        enseignant.matieres_list = enseignant.matiere.split(",")
    else:
        enseignant.matieres_list = []

    # Préparer les classes
    classes = enseignant.classes.split(",") if enseignant.classes else []
    classes_data = []

    now = datetime.now()

    jours_dict = {
        'lundi': 0,
        'mardi': 1,
        'mercredi': 2,
        'jeudi': 3,
        'vendredi': 4,
        'samedi': 5,
        'dimanche': 6
    }

    today_weekday = now.weekday()  # 0 = lundi, 6 = dimanche

    for c in classes:
        horaires = Horaire.objects.filter(classe=c, enseignant=enseignant)
        horaires_list = []

        for h in horaires:
            # Vérifier que le cours est **aujourd'hui**
            target_weekday = jours_dict.get(h.jour.lower(), None)
            if target_weekday == today_weekday:
                date_cours = now.date()
                heure_debut = datetime.combine(date_cours, h.heure_debut)
                heure_fin = datetime.combine(date_cours, h.heure_fin)

                # Fenêtre active: 30 min avant → 1h après début
                window_start = heure_debut - timedelta(minutes=30)
                window_end = heure_debut + timedelta(hours=1)

                active_btn = window_start <= now <= window_end
                minutes_before_start = max(int((window_start - now).total_seconds() // 60), 0)
            else:
                # Cours pas aujourd'hui → bouton désactivé
                active_btn = False
                minutes_before_start = 0

            horaires_list.append({
                'id': h.id,
                'matiere': h.matiere,
                'jour': h.jour,
                'heure_debut': h.heure_debut,
                'heure_fin': h.heure_fin,
                'active_btn': active_btn,
                'minutes_before_start': minutes_before_start
            })

        classes_data.append({
            'nom': c,
            'annee_academique': enseignant.annee_academique,
            'horaires': horaires_list
        })

    school_name = "CPEG LE TRÉSOR DE DOWA"

    # Messages via GET
    success_message = request.GET.get('success', None)
    error_message = request.GET.get('error', None)

    return render(request, 'enseignant/dashboard.html', {
        'enseignant': enseignant,
        'classes': classes_data,
        'school_name': school_name,
        'success': success_message,
        'error': error_message
    })

def enseignant_logout(request):
    if 'enseignant_id' in request.session:
        del request.session['enseignant_id']
    request.session.flush()
    return redirect('enseignant_login')

def inscription(request):
    if request.method == "POST":
        # 1. Vérifier si un compte existe déjà
        if Login.objects.exists():  
            messages.error(request, "Un compte Administrateur existe déjà.")
            return redirect("login")

        # 2. Récupération des données textuelles
        username = request.POST.get("username")
        name = request.POST.get("name")
        school_name = request.POST.get("school_name")
        email = request.POST.get("email")
        numero = request.POST.get("numero")
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        hashed_password = make_password(request.POST.get("password"))

        # 3. Fonction pour transformer les images en texte (Base64)
        def file_to_b64(file):
            if file:
                # Lecture du fichier et encodage
                binary_data = file.read()
                base64_data = base64.b64encode(binary_data).decode('utf-8')
                return base64_data, file.name
            return None, None

        # Conversion des 3 images potentielles
        profile_b64, profile_name = file_to_b64(request.FILES.get("profile_image"))
        coin_b64, coin_name = file_to_b64(request.FILES.get("coin_droit"))
        fond_b64, fond_name = file_to_b64(request.FILES.get("fond_verso"))

        # 4. Stockage global dans la session (sauf les fichiers bruts)
        request.session['data_inscription'] = {
            'username': username,
            'name': name,
            'school_name': school_name,
            'password': hashed_password,
            'email': email,
            'latitude' : latitude,
            'longitude' : longitude,
            'numero': numero,
            'profile_b64': profile_b64, 'profile_name': profile_name,
            'coin_b64': coin_b64, 'coin_name': coin_name,
            'fond_b64': fond_b64, 'fond_name': fond_name,
        }

        # 5. Génération et envoi de l'OTP
        otp_code = str(random.randint(100000, 999999))
        request.session['otp_code'] = otp_code

        subject = f"CODE DE VÉRIFICATION - {school_name}"
        message = f"Bonjour {name},\n\nVotre code de vérification pour finaliser l'inscription de votre établissement est : {otp_code}"
        
        try:
            send_mail(subject, message, settings.EMAIL_HOST_USER, [email])
            messages.info(request, f"Un code a été envoyé à {email}")
            return redirect("verifier_otp")
        except Exception as e:
            messages.error(request, "Erreur d'envoi d'email. Vérifiez votre connexion ou vos paramètres SMTP.")
            return redirect("inscription")

    return render(request, "sign_up.html")

from django.contrib.auth import logout as auth_logout
from django.shortcuts import redirect
from django.views.decorators.cache import never_cache

@never_cache # Empêche le bouton "Précédent" de réafficher le dashboard
def logout_view(request):
    request.session.flush()
    return redirect('login')

from django.core.files.base import ContentFile
import base64

def verifier_otp(request):
    # Sécurité : Si aucune donnée en session, on retourne à l'inscription
    if 'data_inscription' not in request.session:
        return redirect("inscription")

    if request.method == "POST":
        code_saisi = request.POST.get("otp")
        code_attendu = request.session.get('otp_code')
        data = request.session.get('data_inscription')

        if code_saisi == code_attendu:
            # 1. Fonction pour transformer le texte Base64 en fichier Django
            def b64_to_file(b64_str, filename):
                if b64_str:
                    return ContentFile(base64.b64decode(b64_str), name=filename)
                return None

            # 2. Création de l'instance du modèle Login
            new_user = Login(
                username=data['username'],
                name=data['name'],
                school_name=data['school_name'],
                password=data['password'],
                email=data['email'],
                numero=data['numero']
            )

            # 3. Récupération et conversion des images stockées en session
            if data['profile_b64']:
                new_user.profile_image = b64_to_file(data['profile_b64'], data['profile_name'])
            
            if data['coin_b64']:
                new_user.coin_droit = b64_to_file(data['coin_b64'], data['coin_name'])
            
            if data['fond_b64']:
                new_user.fond_verso = b64_to_file(data['fond_b64'], data['fond_name'])

            # 4. Sauvegarde finale en base de données et sur le disque (MEDIA)
            new_user.save()

            # 5. Nettoyage de la session
            del request.session['otp_code']
            del request.session['data_inscription']

            messages.success(request, "Email vérifié avec succès ! Bienvenue.")
            return redirect("login")
        else:
            messages.error(request, "Code incorrect. Veuillez vérifier vos emails.")

    return render(request, "verifier_otp.html")

def reset_utilisateurs(request):
    # Supprimer tous les utilisateurs de la base de données
    Login.objects.all().delete()

    messages.success(request, "Tous les comptes ont été supprimés !")
    return redirect("inscription")  # Redirige vers la page d'inscription


def connexion(request):
    if request.method == "POST":
        username_saisi = request.POST.get("username")
        password_saisi = request.POST.get("password")

        user = Login.objects.filter(username=username_saisi).first()

        if user and check_password(password_saisi, user.password):
            # SUCCESS : On crée la session
            request.session['admin_id'] = user.id
            
            # --- AJOUT : GESTION DE LA REDIRECTION ---
            # On récupère 'next' depuis l'URL (GET)
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            
            return redirect("accueil")
        else:
            messages.error(request, "Identifiants invalides.")
    
    return render(request, "login.html")

from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache
from datetime import datetime
from .models import Eleve, Login

@never_cache
def accueil_view(request):
    # 1. Vérification de la session
    if 'admin_id' not in request.session:
        return redirect(f'/login/?next={request.path}')
    
    # Récupération du nombre d'enseignants en attente
    enseignants_en_attente_count = Enseignant.objects.filter(est_approuve=False).count()

    # 2. Gestion de l'année académique automatique
    current_date = datetime.now()
    if current_date.month < 9:
        default_annee = f"{current_date.year - 1}-{current_date.year}"
    else:
        default_annee = f"{current_date.year}-{current_date.year + 1}"

    annee_academique = request.GET.get('annee', default_annee)

    # 3. Définition des structures
    niveaux_college = ['6ème', '5ème', '4ème', '3ème']
    niveaux_lycee = [
        ('2nde', 'A'), ('2nde', 'B'), ('2nde', 'C'), ('2nde', 'D'), 
        ('1ère', 'A1'), ('1ère', 'A2'), ('1ère', 'B'), ('1ère', 'C'), ('1ère', 'D'), 
        ('Tle', 'A1'), ('Tle', 'A2'), ('Tle', 'B'), ('Tle', 'C'), ('Tle', 'D')  
    ]

    # 4. Fonction utilitaire pour compter les élèves
    def get_stats(classe, serie=None):
        filters = {'classe': classe, 'annee_academique': annee_academique}
        if serie:
            filters['serie'] = serie
        
        return {
            'garçons': Eleve.objects.filter(sexe="M", **filters).count(),
            'filles': Eleve.objects.filter(sexe="F", **filters).count(),
            'total_eleves': Eleve.objects.filter(**filters).count(),
        }

    # 5. Construction du dictionnaire de données
    # ON INCLUT TOUT DANS 'context'
    context = {
        'annee_academique': annee_academique,
        'school_name': Login.objects.first().school_name if Login.objects.exists() else "",
        'enseignants_en_attente_count': enseignants_en_attente_count, # INCLUSION ICI
    }

    # Statistiques Collège
    for niv in niveaux_college:
        key = {
            '6ème': 'statistiques_sixieme',
            '5ème': 'statistiques_cinquieme',
            '4ème': 'statistiques_quatrieme',
            '3ème': 'statistiques_troisieme'
        }.get(niv)
        context[key] = get_stats(niv)

    # Statistiques Lycée
    stats_lycee = []
    for niv, ser in niveaux_lycee:
        data = get_stats(niv, ser)
        data['classe_nom'] = niv
        data['serie_nom'] = ser
        data['label'] = f"{niv} {ser}"
        stats_lycee.append(data)
    
    context['stats_lycee'] = stats_lycee

    # LE RENDER NE PREND QUE 'context'
    return render(request, 'accueil.html', context)

def traiter_langue_optionnelle(request):
    classe = request.POST.get('classe')
    serie = request.POST.get('serie')
    choix_langue = request.POST.get('option_langue')

    # Condition : Collège (4è/3è) OU Lycée (Séries A1, A2, B)
    if classe in ['4ème', '3ème'] or serie in ['A1', 'A2', 'B']:
        return choix_langue if choix_langue else None
    return None

from django.db import IntegrityError
def enregistrer_eleve(request):
    if request.method == "POST":
        try:
            # 1. Récupération des données de base
            nom = request.POST.get("nom")
            prenoms = request.POST.get("prenoms")
            matricule = request.POST.get("matricule")
            sexe = request.POST.get("sexe")
            date_naissance = request.POST.get("date_naissance") or None
            lieu_naissance = request.POST.get("lieu_naissance")
            classe = request.POST.get("classe")
            serie = request.POST.get("serie") or "Général"
            annee_academique = request.POST.get("annee_academique")
            
            # 2. Logique métier pour les LANGUES (selon le niveau)
            langue_specialite = None
            lv1 = "Anglais" # Par défaut pour tout le monde
            lv2 = None

            if classe in ['4ème', '3ème']:
                # Collège : on récupère la langue de spécialité
                langue_specialite = request.POST.get('langue_specialite')
            
            elif classe in ['2nde', '1ère', 'Tle']:
                # Lycée : LV1 obligatoire, LV2 uniquement pour séries littéraires
                lv1 = request.POST.get('lv1', 'Anglais')
                if serie in ['A1', 'A2', 'B']:
                    lv2 = request.POST.get('lv2')
                else:
                    lv2 = None # Force None pour Séries C, D, G

            # 3. Création de l'instance
            nouvel_eleve = Eleve(
                nom=nom,
                prenoms=prenoms,
                matricule=matricule,
                sexe=sexe,
                date_naissance=date_naissance,
                lieu_naissance=lieu_naissance,
                classe=classe,
                serie=serie,
                langue_specialite=langue_specialite,
                lv1=lv1,
                lv2=lv2,
                annee_academique=annee_academique,
                telephone_parent=request.POST.get("telephone_parent"),
                email_parent=request.POST.get("email_parent"),
                profile_eleve=request.FILES.get("profile_eleve")
            )

            nouvel_eleve.save()
            messages.success(request, f"L'élève {nom} {prenoms} a été inscrit avec succès !")
            return redirect('enregistrer_eleve') # Remplace par le nom de ton URL de liste

        except IntegrityError:
            messages.error(request, "Erreur : Ce matricule est déjà utilisé par un autre élève.")
        except Exception as e:
            messages.error(request, f"Une erreur est survenue : {str(e)}")

    # Pour le GET ou en cas d'erreur
    user = Login.objects.first()
    return render(request, 'enregistrer_eleve.html', {'school_name': user.school_name if user else "ACADYNOTE"})

def modifier_eleve(request, classe, eleve_id, annee):
    # 1. Récupérer l'élève ou 404
    eleve = get_object_or_404(Eleve, id=eleve_id)

    if request.method == "POST":
        # Récupération des données du formulaire
        eleve.nom = request.POST.get("nom")
        eleve.prenoms = request.POST.get("prenoms")
        eleve.matricule = request.POST.get("matricule")
        eleve.sexe = request.POST.get("sexe")
        eleve.classe = request.POST.get("classe")
        eleve.annee_academique = request.POST.get("annee_academique")
        
        # --- Gestion de la série et des langues ---
        lycee_classes = ['2nde', '1ère', 'Tle']
        
        if eleve.classe in lycee_classes:
            # CAS LYCÉE : On récupère la série et on gère la LV2
            eleve.serie = request.POST.get("serie")
            eleve.langue_specialite = None
            eleve.lv1 = request.POST.get('lv1', 'Anglais')
            
            # Si série scientifique (C ou D), on force la LV2 à vide
            if eleve.serie in ['C', 'D']:
                eleve.lv2 = None
            else:
                eleve.lv2 = request.POST.get('lv2')
        else:
            # CAS COLLÈGE (6è, 5è, 4è, 3è) : La série doit être VIDE
            eleve.serie = ""  # Force une chaîne vide en base de données
            eleve.lv2 = None
            eleve.lv1 = "Anglais"
            
            # Langue de spécialité uniquement pour 4ème/3ème
            if eleve.classe in ['4ème', '3ème']:
                eleve.langue_specialite = request.POST.get('langue_specialite')
            else:
                eleve.langue_specialite = None

        # Gestion de l'image
        new_image = request.FILES.get("profile_eleve")
        if new_image:
            eleve.profile_eleve = new_image

        # Autres infos
        eleve.telephone_parent = request.POST.get("telephone_parent")
        eleve.email_parent = request.POST.get("email_parent")
        eleve.date_naissance = request.POST.get("date_naissance") or None
        eleve.lieu_naissance = request.POST.get("lieu_naissance")

        try:
            eleve.save()
            messages.success(request, f"Modifications enregistrées pour {eleve.nom}.")
        except IntegrityError:
            messages.error(request, "Erreur : Ce matricule appartient déjà à un autre élève.")

    user = Login.objects.first()
    return render(request, "modifier_eleve.html", {
        "eleve": eleve,
        "school_name": user.school_name if user else "ACADYNOTE"
    })

from django.shortcuts import render, get_object_or_404
from .models import Eleve, Login

def liste_eleves_generique(request, classe, annee, serie=None):
    # 1. Gérer l'année académique (priorité au GET du formulaire, sinon l'URL)
    annee_academique = request.GET.get('annee', annee)
    
    # 2. Construction du filtre de base
    filters = {'classe': classe, 'annee_academique': annee_academique}
    
    # 3. Si une série est fournie (Lycée), on l'ajoute au filtre
    if serie and serie != "None":
        filters['serie'] = serie
        nom_affichage_classe = f"{classe} {serie}"
    else:
        nom_affichage_classe = classe

    # 4. Récupération des élèves
    eleves = Eleve.objects.filter(**filters).order_by('nom', 'prenoms')
    
    # 5. Infos école
    user = Login.objects.first()
    school_name = user.school_name if user else "Mon École"

    return render(request, 'listes_classes/liste_generique.html', {
        'eleves': eleves,
        'school_name': school_name,
        'classe': classe,
        "annee": annee,
        'serie': serie,
        'affichage_classe': nom_affichage_classe, # Pour le titre H2
        'annee_academique': annee_academique
    })


from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import IntegrityError
from .models import Eleve, Note, Login

def inserer_notes_classe_view(request, classe, annee_academique, serie=None):
    # --- 1. FILTRAGE INITIAL (Sélection des élèves de la classe) ---
    filters = {'classe': classe, 'annee_academique': annee_academique}
    
    # Gestion du cas série vide (Collège)
    if serie and serie != "None" and serie != "":
        filters['serie'] = serie
    else:
        # On cible les élèves sans série (6è à 3è)
        filters['serie__in'] = ["", None]
    
    tous_les_eleves_classe = Eleve.objects.filter(**filters).order_by("nom", "prenoms")

    # --- 2. ADAPTATION DES MATIÈRES DISPONIBLES ---
    matieres_base = ["Mathématiques", "Anglais", "Histoire-Géographie", "SVT", "PCT", "EPS", "Conduite", "Informatique"]
    is_lycee = classe in ['2nde', '1ère', 'Tle']
    
    if is_lycee:
        serie_upper = str(serie).upper() if serie else ""
        matieres_base = ["Français", "Philosophie"] + matieres_base
        if serie_upper == "B":
            matieres_base.append("Économie")
        
        # Récupération des langues LV2 actives pour cette classe de lycée
        options = tous_les_eleves_classe.exclude(lv2__isnull=True).exclude(lv2="").values_list('lv2', flat=True).distinct()
        for opt in options:
            if opt and opt not in matieres_base: matieres_base.append(opt)
    else:
        # Configuration Collège
        matieres_base = ["Communication-Ecrite", "Lecture"] + matieres_base
        # Langue de Spécialité (4ème / 3ème)
        if "4" in classe or "3" in classe:
            options = tous_les_eleves_classe.exclude(langue_specialite__isnull=True).exclude(langue_specialite="").values_list('langue_specialite', flat=True).distinct()
            for opt in options:
                if opt and opt not in matieres_base: matieres_base.append(opt)

    # --- 3. SÉLECTIONS COURANTES ---
    matiere_selected = request.POST.get("matiere") or request.GET.get("matiere") or (matieres_base[0] if matieres_base else "")
    trimestre_selected = int(request.POST.get("trimestre") or request.GET.get("trimestre") or 1)
    type_notes = ["interro1", "interro2", "interro3", "devoir1", "devoir2"]

    # --- 4. FILTRAGE DYNAMIQUE (Qui doit être noté dans cette matière ?) ---
    if matiere_selected in ["Espagnol", "Allemand"]:
        if is_lycee:
            eleves = tous_les_eleves_classe.filter(lv2=matiere_selected)
        else:
            eleves = tous_les_eleves_classe.filter(langue_specialite=matiere_selected)
    else:
        eleves = tous_les_eleves_classe

    eleves_list = list(eleves)

    # --- 5. CHARGEMENT DES NOTES EXISTANTES ---
    all_notes = list(
        Note.objects.filter(
            eleve__in=eleves_list,
            annee_academique=annee_academique,
            matiere=matiere_selected,
            trimestre=trimestre_selected
        )
    )

    for eleve in eleves_list:
        eleve.notes_dict = {n.type_note: n for n in all_notes if n.eleve_id == eleve.id}

    # --- 6. GESTION DES ACTIONS (POST) ---
    if request.method == "POST":
        action = request.POST.get("action")

        # --- A. SAUVEGARDE DES NOTES ---
        if action == "sauvegarder":
            updates, creations = [], []
            for eleve in eleves_list:
                for t_note in type_notes:
                    valeur_brute = request.POST.get(f"note_{eleve.id}_{t_note}")
                    if valeur_brute and valeur_brute.strip():
                        try:
                            valeur = float(valeur_brute.replace(',', '.'))
                            if not (0 <= valeur <= 20): raise ValueError
                            
                            note_obj = eleve.notes_dict.get(t_note)
                            if note_obj:
                                note_obj.valeur = valeur
                                updates.append(note_obj)
                            else:
                                creations.append(Note(
                                    eleve=eleve, matiere=matiere_selected,
                                    type_note=t_note, valeur=valeur,
                                    trimestre=trimestre_selected,
                                    annee_academique=annee_academique
                                ))
                        except ValueError:
                            messages.error(request, f"Note invalide ({valeur_brute}) pour {eleve.nom}")

            if updates: Note.objects.bulk_update(updates, ["valeur"])
            if creations: Note.objects.bulk_create(creations)
            messages.success(request, "Notes enregistrées avec succès !")
            return redirect(request.path + f"?matiere={matiere_selected}&trimestre={trimestre_selected}")

        # --- B. CALCUL DES MOYENNES ET RANGS ---
        elif action == "calculer":
            trimestre_notes = Note.objects.filter(
                eleve__in=tous_les_eleves_classe,
                trimestre=trimestre_selected,
                annee_academique=annee_academique
            )

            updates = []
            moyennes_finales_eleves = []

            for eleve in tous_les_eleves_classe:
                # Identification de sa langue optionnelle selon son niveau
                langue_optionnelle = eleve.lv2 if is_lycee else eleve.langue_specialite

                # On ne prend que ses matières communes + SA langue spécifique
                notes_eleve = [
                    n for n in trimestre_notes 
                    if n.eleve_id == eleve.id and 
                    (n.matiere not in ["Espagnol", "Allemand"] or n.matiere == langue_optionnelle)
                ]
                
                stats_par_matiere = {}
                for note in notes_eleve:
                    m = note.matiere
                    if m not in stats_par_matiere:
                        stats_par_matiere[m] = {'int': [], 'dev': [], 'm_int': 0, 'm_dev': 0, 'm_gen': None}
                    
                    if note.type_note.startswith('interro'):
                        stats_par_matiere[m]['int'].append(note.valeur)
                    else:
                        stats_par_matiere[m]['dev'].append(note.valeur)

                total_points, total_coefficients = 0, 0
                
                for m_nom, data in stats_par_matiere.items():
                    ints, devs = data['int'], data['dev']
                    data['m_int'] = round(sum(ints)/len(ints), 2) if ints else 0
                    data['m_dev'] = round(sum(devs)/len(devs), 2) if devs else 0

                    # Logique de calcul de la moyenne générale de la matière
                    if not ints: 
                        data['m_gen'] = data['m_dev']
                    elif len(devs) == 2: 
                        data['m_gen'] = round((sum(devs) + data['m_int']) / 3, 2)
                    elif len(devs) == 1: 
                        data['m_gen'] = round((devs[0] + data['m_int']) / 2, 2)
                    else: 
                        data['m_gen'] = data['m_int']

                    # Calcul avec coefficients
                    coef = get_coefficient(eleve.classe, eleve.serie, m_nom)
                    if data['m_gen'] is not None:
                        total_points += data['m_gen'] * coef
                        total_coefficients += coef

                    # Enregistrement des moyennes dans l'objet Note
                    for note in [n for n in notes_eleve if n.matiere == m_nom]:
                        note.moyenne_interrogations = data['m_int']
                        note.moyenne_devoirs = data['m_dev']
                        note.moyenne_generale = data['m_gen']
                        updates.append(note)

                # Calcul de la moyenne du trimestre
                moy_trim = round(total_points / total_coefficients, 2) if total_coefficients > 0 else 0
                for note in notes_eleve:
                    note.moyenne_trimestrielle = moy_trim
                    updates.append(note)
                
                moyennes_finales_eleves.append((eleve, moy_trim))

            # Classement des élèves
            moyennes_finales_eleves.sort(key=lambda x: x[1], reverse=True)
            for index, (eleve, _) in enumerate(moyennes_finales_eleves):
                for n in [n for n in trimestre_notes if n.eleve_id == eleve.id]:
                    n.rang = index + 1
                    updates.append(n)

            if updates:
                Note.objects.bulk_update(updates, [
                    "moyenne_interrogations", "moyenne_devoirs", 
                    "moyenne_generale", "moyenne_trimestrielle", "rang"
                ])
            messages.success(request, "Calculs des moyennes et rangs terminés !")
            return redirect(request.path + f"?matiere={matiere_selected}&trimestre={trimestre_selected}")

    # Données pour le template
    user_info = Login.objects.first()
    return render(request, "inserer_note.html", {
        "eleves": eleves_list,
        "classe": classe,
        "serie": serie,
        "annee_academique": annee_academique,
        "school_name": user_info.school_name if user_info else "ACADYNOTE",
        "matieres": matieres_base,
        "type_notes": type_notes,
        "matiere_selected": matiere_selected,
        "trimestre_selected": trimestre_selected
    })

def supprimer_eleve(request, id_eleve):
    # Récupérer l'élève avec l'ID spécifié
    eleve = get_object_or_404(Eleve, id=id_eleve)
    
    # Supprimer les notes associées à cet élève
    eleve.note_set.all().delete()
    
    # Supprimer l'élève
    eleve.delete()
     # Récupérer la première ligne de la table Login
    user = Login.objects.first()  # Récupère le premier utilisateur (si un utilisateur existe)
    
    # Si l'utilisateur existe, retourner le nom de l'école, sinon retourner une chaîne vide
    school_name = user.school_name if user else ""
     
    # Rediriger vers la page d'accueil ou une autre page
    return redirect(request.META['HTTP_REFERER'],{"school_name": school_name})  # Remplacez par l'URL de redirection souhaitée

from django.shortcuts import render, get_object_or_404
from .models import Eleve, Note, Login

def notes_eleve(request, eleve_id):
    eleve = get_object_or_404(Eleve, id=eleve_id)
    trimestre = int(request.GET.get('trimestre', 1))
    annee_academique = eleve.annee_academique.strip()

    # On récupère toutes les notes pour afficher le tableau
    notes = Note.objects.filter(eleve=eleve, trimestre=trimestre, annee_academique=annee_academique)

    # --- RÉCUPÉRATION DIRECTE DE LA MOYENNE ET DU RANG ---
    # On prend la première note de la liste, car elles partagent toutes la même moyenne_trimestrielle et le même rang
    premiere_note = notes.first()
    
    moyenne_trimestrielle = 0.0
    rang_final = "N/A"

    if premiere_note:
        moyenne_trimestrielle = premiere_note.moyenne_trimestrielle or 0.0
        rang_final = premiere_note.rang if premiere_note.rang else "N/A"

    # --- REGROUPEMENT POUR LE TABLEAU (Matières) ---
    matieres_status = {}
    for n in notes:
        if n.matiere not in matieres_status:
            matieres_status[n.matiere] = {
                'interros': [],
                'devoirs': [],
                'moyenne_generale': n.moyenne_generale or 0.0,
            }
        
        if n.type_note in ['interro1', 'interro2', 'interro3']:
            matieres_status[n.matiere]['interros'].append(n.valeur)
        elif n.type_note in ['devoir1', 'devoir2']:
            matieres_status[n.matiere]['devoirs'].append(n.valeur)

    # Appréciation basée sur la moyenne récupérée
    if moyenne_trimestrielle >= 16: appreciation = "Excellent"
    elif moyenne_trimestrielle >= 14: appreciation = "Très Bien"
    elif moyenne_trimestrielle >= 12: appreciation = "Bien"
    elif moyenne_trimestrielle >= 10: appreciation = "Passable"
    else: appreciation = "Insuffisant"

    user_info = Login.objects.first()

    context = {
        "eleve": eleve,
        "moyenne_trimestrielle": moyenne_trimestrielle,
        "rang": rang_final,
        "matieres_status": matieres_status,
        "trimestre": trimestre,
        "school_name": user_info.school_name if user_info else "LE TRESOR DE DOWA",
        "appreciation": appreciation
    }
    return render(request, "notes_eleve.html", context)

from datetime import datetime

def get_annee_scolaire_actuelle():
    """Détermine dynamiquement l'année scolaire en cours"""
    now = datetime.now()
    if now.month >= 9:  # De Septembre à Décembre
        return f"{now.year}-{now.year + 1}"
    else:  # De Janvier à Août
        return f"{now.year - 1}-{now.year}"

def telecharger_tous_bulletins(request, classe, trimestre, serie=None):
    annee_actuelle = get_annee_scolaire_actuelle()
    user = Login.objects.first()
    classe = classe.strip()
    trimestre = str(trimestre)
    pp = Enseignant.objects.filter(classes__icontains=classe).first()
    # --- AJOUT DE LA DÉFINITION MANQUANTE ---
    is_lycee = classe in ['2nde', '1ère', 'Tle']

    # 1. FILTRAGE DES ELEVES (Gestion serie vide pour le collège)
    filtres = {'classe__iexact': classe, 'annee_academique': annee_actuelle}
    if serie and serie != "None" and serie != "tout":
        filtres['serie__iexact'] = serie.strip()
    else:
        # Pour le collège ou si "tout" est sélectionné, on gère les séries vides
        if not is_lycee:
            filtres['serie__in'] = ["", None]
        
    eleves = Eleve.objects.filter(**filtres).order_by('nom')

    # 2. DEFINITION DE TOUTES LES MATIERES (Ordre complet pour le bulletin)
    if is_lycee:
        # Structure Lycée
        ordre_complet = ['Français', 'Philosophie', 'Anglais', 'Histoire-Géographie', 'Mathématiques', 'SVT']
        if serie == 'B': ordre_complet.append('Économie')
        if serie == 'C' or serie == 'D' : ordre_complet.append('PCT')
    else:
        # Structure Collège
        ordre_complet = ['Communication-Ecrite', 'Lecture', 'Anglais', 'Histoire-Géographie', 'Mathématiques', 'PCT', 'SVT']
    
    # Matières transversales
    ordre_complet.extend(['Informatique', 'EPS', 'Conduite'])

    # 3. PRE-CALCUL DES RANGS (GLOBAL)
    scores_par_matiere = {m: [] for m in ordre_complet}
    for m_lang in ['Espagnol', 'Allemand']: 
        scores_par_matiere[m_lang] = []
    
    moyennes_globales = []

    for e in eleves:
        t_pondere, t_coef = 0, 0
        notes_e = Note.objects.filter(eleve=e, trimestre=trimestre, annee_academique=annee_actuelle)
        
        mats_eleve = notes_e.values_list('matiere', flat=True).distinct()
        
        for mat_nom in mats_eleve:
            n_mat = notes_e.filter(matiere=mat_nom)
            intros = n_mat.filter(type_note__icontains='interro').values_list('valeur', flat=True)
            devs = n_mat.filter(type_note__icontains='devoir').values_list('valeur', flat=True)
            
            moy = None
            if not intros and devs: moy = sum(devs)/len(devs)
            elif intros and devs:
                moy = (sum(intros)/len(intros) + sum(devs)) / (len(devs)+1)
            elif intros and not devs:
                moy = sum(intros)/len(intros)
            
            if moy is not None:
                if mat_nom not in scores_par_matiere: scores_par_matiere[mat_nom] = []
                scores_par_matiere[mat_nom].append((e.id, moy))
                c = get_coefficient(classe, e.serie, mat_nom)
                t_pondere += moy * c
                t_coef += c
        
        moy_e = t_pondere / t_coef if t_coef > 0 else 0
        moyennes_globales.append((e.id, moy_e))

    # Dictionnaires de rangs
    rangs_matieres_dict = {m: {id_e: i+1 for i, (id_e, s) in enumerate(sorted(sc, key=lambda x: x[1], reverse=True))} 
                          for m, sc in scores_par_matiere.items()}
    
    moyennes_globales.sort(key=lambda x: x[1], reverse=True)
    dict_rangs_generaux = {id_e: i + 1 for i, (id_e, m) in enumerate(moyennes_globales)}

    # 4. CONSTRUCTION DES BULLETINS
    pp_queryset = ProfesseurPrincipal.objects.filter(classe__iexact=classe, annee_academique=annee_actuelle)
    liste_bulletins = []

    for eleve in eleves:
        # GESTION DU PP (Aucun trait si vide)
        pp_match = pp_queryset.filter(serie__iexact=eleve.serie if eleve.serie else "").first()
        nom_pp = f"{pp_match.enseignant.prenoms} {pp_match.enseignant.nom}" if pp_match else ""

        matieres_status = {}
        total_p, total_c = 0, 0
        notes_eleve = Note.objects.filter(eleve=eleve, trimestre=trimestre, annee_academique=annee_actuelle)

        # Déterminer la langue optionnelle
        langue_opt = eleve.lv2 if is_lycee else eleve.langue_specialite
        
        ma_liste_finale = list(ordre_complet)
        if langue_opt and langue_opt not in ma_liste_finale:
            try:
                idx = ma_liste_finale.index('Anglais')
                ma_liste_finale.insert(idx + 1, langue_opt)
            except ValueError:
                ma_liste_finale.append(langue_opt)

        for matiere in ma_liste_finale:
            n_m = notes_eleve.filter(matiere__iexact=matiere)
            intros = list(n_m.filter(type_note__icontains='interro').values_list('valeur', flat=True))
            devoirs = list(n_m.filter(type_note__icontains='devoir').values_list('valeur', flat=True))

            m_int = round(sum(intros) / len(intros), 2) if intros else None
            m_gen = None
            if not intros and devoirs: 
                m_gen = round(sum(devoirs) / len(devoirs), 2)
            elif intros and devoirs: 
                m_gen = round(((sum(intros)/len(intros)) + sum(devoirs)) / (len(devoirs)+1), 2)
            elif intros and not devoirs:
                m_gen = m_int 

            c = get_coefficient(classe, eleve.serie, matiere)
            m_coef = (m_gen * c) if m_gen is not None else 0

            if m_gen is not None:
                total_p += m_coef
                total_c += c

            matieres_status[matiere] = {
                'moyenne_interros': m_int if m_int is not None else "",
                'devoirs': devoirs,
                'moyenne_generale': m_gen if m_gen is not None else "",
                'coef': c,
                'moyenne_coef': round(m_coef, 2) if m_gen is not None else "",
                'rang': rangs_matieres_dict.get(matiere, {}).get(eleve.id, "-") if m_gen is not None else "-",
                'appreciations': get_appreciation(m_gen) if m_gen is not None else ""
            }

        liste_bulletins.append({
            'eleve': eleve,
            'matieres_status': matieres_status,
            'moyenne_trimestrielle': round(total_p / total_c, 2) if total_c > 0 else 0,
            'rang_trimestriel': dict_rangs_generaux.get(eleve.id, 0),
            'professeur_principal': nom_pp,
            'professeur_principal_obj': pp,
        })

    context = {
        "liste_bulletins": liste_bulletins,
        "school_name": user.school_name if user else "ACADYNOTE",
        "email": user.email if user else "",
        "numero": user.numero if user else "",
        "name": user.name if user else "",
        "profile_image": user.profile_image.url if user and user.profile_image else None,
        "trimestre": trimestre,
        "classe_nom": classe,
        "total_eleve": eleves.count(),
        "moyenne_max": round(moyennes_globales[0][1], 2) if moyennes_globales else 0,
        "moyenne_min": round(moyennes_globales[-1][1], 2) if moyennes_globales else 0,
    }
    return render(request, 'bulletin/tous_les_bulletins.html', context)


def calculer_resultats_trimestre(request, classe, annee_academique, num_trimestre, serie=None):
    # 1. Préparation des filtres
    serie_finale = serie if (serie and serie != "tout") else request.GET.get('serie', '')
    serie_safe = serie_finale.upper() if serie_finale else ""
    is_lycee = classe in ['2nde', '1ère', 'Tle']

    eleves_qs = Eleve.objects.filter(classe=classe, annee_academique=annee_academique)
    if serie_safe:
        eleves_qs = eleves_qs.filter(serie__iexact=serie_safe)
    elif not is_lycee:
        eleves_qs = eleves_qs.filter(serie__in=["", None])
    
    eleves = list(eleves_qs.order_by('nom', 'prenoms'))

    # 2. Liste de référence des colonnes (matieres_base)
    # On définit l'ordre exact des colonnes pour le tableau
    if is_lycee:
        matieres_base = ['Français', 'Philosophie', 'Anglais', 'Histoire-Géographie', 'Mathématiques', 'SVT', 'PCT']
        if serie_safe == 'B': matieres_base.append('Économie')
    else:
        matieres_base = ['Communication-Ecrite', 'Lecture', 'Anglais', 'Histoire-Géographie', 'Mathématiques', 'SVT', 'PCT']
    
    # Ajout des colonnes de langues (LV) pour éviter les décalages
    if classe in ['4ème', '3ème'] or is_lycee:
        # On ajoute les deux pour que les colonnes soient fixes pour toute la classe
        matieres_base.extend(['Espagnol', 'Allemand'])
    
    matieres_base.extend(['Informatique', 'EPS', 'Conduite'])
    
    # 3. Récupération des notes
    toutes_les_notes = Note.objects.filter(
        eleve__in=eleves, 
        trimestre=num_trimestre, 
        annee_academique=annee_academique
    )

    resultats_eleves = []
    moyennes_classe_liste = []

    for eleve in eleves:
        notes_e = [n for n in toutes_les_notes if n.eleve_id == eleve.id]
        matieres_notes_dict = {}
        total_p, total_c = 0, 0
        
        for matiere in matieres_base:
            n_m = [n for n in notes_e if n.matiere.lower() == matiere.lower()]
            intros = [n.valeur for n in n_m if "interro" in n.type_note.lower()]
            devoirs = [n.valeur for n in n_m if "devoir" in n.type_note.lower()]

            m_int = round(sum(intros) / len(intros), 2) if intros else None
            m_gen = None
            
            if m_int is not None and devoirs:
                m_gen = round((m_int + sum(devoirs)) / (len(devoirs) + 1), 2)
            elif m_int is None and devoirs:
                m_gen = round(sum(devoirs) / len(devoirs), 2)
            elif m_int is not None and not devoirs:
                m_gen = m_int

            # On remplit le dictionnaire pour CHAQUE colonne du tableau
            matieres_notes_dict[matiere] = {
                'm_int': m_int if m_int is not None else '-',
                'm_dev': round(sum(devoirs)/len(devoirs), 2) if devoirs else '-',
                'm_gen': m_gen if m_gen is not None else '-',
            }

            if m_gen is not None:
                coef = get_coefficient(classe, eleve.serie, matiere)
                total_p += (m_gen * coef)
                total_c += coef

        m_tri = round(total_p / total_c, 2) if total_c > 0 else 0
        moyennes_classe_liste.append(m_tri)
        
        resultats_eleves.append({
            'eleve': eleve,
            'matieres_notes': matieres_notes_dict,
            'moyenne_trimestrielle': m_tri,
            'rang': 0,
        })

    # 4. Calcul des Rangs
    resultats_eleves.sort(key=lambda x: x['moyenne_trimestrielle'], reverse=True)
    for idx, r in enumerate(resultats_eleves):
        r['rang'] = idx + 1
    
    # Tri final par nom
    resultats_eleves.sort(key=lambda x: (x['eleve'].nom, x['eleve'].prenoms))

    total = len(eleves)
    sup10 = sum(1 for m in moyennes_classe_liste if m >= 10)
    
    return {
        "resultats_eleves": resultats_eleves,
        "matieres_base": matieres_base,
        "trimestre": num_trimestre,
        "classe": classe,
        "serie_nom": serie_safe,
        "annee_academique": annee_academique,
        "total_eleves": total,
        "moyenne_max": max(moyennes_classe_liste) if moyennes_classe_liste else 0,
        "moyenne_min": min(moyennes_classe_liste) if moyennes_classe_liste else 0,
        "nb_moyenne_sup10": sup10,
        "nb_moyenne_inf10": total - sup10,
        "pourcentage_sup10": round((sup10 / total * 100), 2) if total > 0 else 0,
    }

# Vues par trimestre
def affichemoy_trimestre1(request, classe, annee_academique, serie=None):
    data = calculer_resultats_trimestre(request, classe, annee_academique, 1, serie)
    
    # Pagination ici
    paginator = Paginator(data['resultats_eleves'], 35)
    page_number = request.GET.get('page', 1)
    data['page_obj'] = paginator.get_page(page_number)
    
    user = Login.objects.first()
    data['school_name'] = user.school_name if user else "ACADY"
    data['profile_image'] = user.profile_image.url if user and user.profile_image else None
    
    return render(request, 'moyenne/trimestre_1.html', data)

def affichemoy_trimestre2(request, classe, annee_academique, serie=None):
    # Appel identique mais avec le chiffre 2 pour le trimestre
    data = calculer_resultats_trimestre(request, classe, annee_academique, 2, serie)
    
    paginator = Paginator(data['resultats_eleves'], 35)
    page_number = request.GET.get('page', 1)
    data['page_obj'] = paginator.get_page(page_number)
    
    user = Login.objects.first()
    data['school_name'] = user.school_name if user else "ACADY"
    data['profile_image'] = user.profile_image.url if user and user.profile_image else None
    
    return render(request, 'moyenne/trimestre_2.html', data)

def affichemoy_trimestre3(request, classe, annee_academique, serie=None):
    # Appel identique mais avec le chiffre 3 pour le trimestre
    data = calculer_resultats_trimestre(request, classe, annee_academique, 3, serie)
    
    paginator = Paginator(data['resultats_eleves'], 35)
    page_number = request.GET.get('page', 1)
    data['page_obj'] = paginator.get_page(page_number)
    
    user = Login.objects.first()
    data['school_name'] = user.school_name if user else "ACADY"
    data['profile_image'] = user.profile_image.url if user and user.profile_image else None
    
    return render(request, 'moyenne/trimestre_3.html', data)
from django.db.models import Q
from django.core.paginator import Paginator
from django.shortcuts import render

def affiche_moy_excel_generique(request, classe, annee_academique, trimestre, serie=None):
    # 1. Filtres des élèves
    if serie in [None, "None", "", "none", "tout"]:
        eleves_qs = Eleve.objects.filter(
            Q(serie__isnull=True) | Q(serie="") | Q(serie="None"),
            classe=classe,
            annee_academique=annee_academique
        )
    else:
        eleves_qs = Eleve.objects.filter(
            classe=classe,
            annee_academique=annee_academique,
            serie__iexact=serie
        )
    
    eleves = list(eleves_qs.order_by('nom', 'prenoms'))

    # 2. Configuration des colonnes (Ordre fixe)
    premier_eleve = eleves[0] if eleves else None
    serie_safe = premier_eleve.serie if premier_eleve and premier_eleve.serie else ""

    if serie_safe:
        order_of_subjects = [
            'Philosophie', 'Français', 'Histoire-Géographie', 'Mathématiques',
            'PCT', 'SVT', 'Anglais', 'Informatique', 'Espagnol', 'Allemand', 'EPS', 'Conduite'
        ]
        if str(serie_safe).upper() == 'B':
            order_of_subjects.insert(7, 'Économie')
    else:
        order_of_subjects = [
            'Communication-Ecrite', 'Lecture', 'Histoire-Géographie', 'Mathématiques',
            'PCT', 'SVT', 'Anglais', 'Informatique', 'Espagnol', 'Allemand', 'EPS', 'Conduite'
        ]

    # 3. Récupération des notes
    toutes_les_notes = Note.objects.filter(
        eleve__in=eleves, 
        trimestre=trimestre, 
        annee_academique=annee_academique
    )

    resultats_bruts = []
    for eleve in eleves:
        notes_e = [n for n in toutes_les_notes if n.eleve_id == eleve.id]
        matieres_notes_dict = {}
        # On stocke les noms des matières réellement pratiquées par l'élève
        matieres_pratiquees = []
        total_points, total_coeffs = 0, 0

        for matiere in order_of_subjects:
            n_m = [n for n in notes_e if n.matiere.lower() == matiere.lower()]
            
            if n_m:
                matieres_pratiquees.append(matiere.lower())

            intros = [n.valeur for n in n_m if "interro" in n.type_note.lower()]
            devoirs = [n.valeur for n in n_m if n.type_note in ['devoir1', 'devoir2']]

            m_int = round(sum(intros)/len(intros), 2) if intros else None
            m_dev = round(sum(devoirs)/len(devoirs), 2) if devoirs else None

            m_gen = None
            if m_int is not None and devoirs:
                m_gen = round((m_int + sum(devoirs)) / (len(devoirs) + 1), 2)
            elif m_int is None and devoirs:
                m_gen = m_dev
            elif m_int is not None and not devoirs:
                m_gen = m_int

            matieres_notes_dict[matiere] = {
                'm_int': m_int if m_int is not None else '',
                'm_dev': m_dev if m_dev is not None else '',
                'm_gen': m_gen if m_gen is not None else '',
            }

            if m_gen is not None:
                coef = get_coefficient(eleve.classe, eleve.serie, matiere)
                total_points += (m_gen * coef)
                total_coeffs += coef

        m_trim = round(total_points / total_coeffs, 2) if total_coeffs > 0 else 0
        resultats_bruts.append({
            'eleve': eleve,
            'matieres_notes': matieres_notes_dict,
            'matieres_list': matieres_pratiquees,
            'moyenne_trimestrielle': m_trim,
            'rang': 0
        })

    # 4. Rangs
    resultats_bruts.sort(key=lambda x: x['moyenne_trimestrielle'], reverse=True)
    for idx, r in enumerate(resultats_bruts):
        r['rang'] = idx + 1
    
    resultats_bruts.sort(key=lambda x: (x['eleve'].nom, x['eleve'].prenoms))

    # 5. Pagination
    moyennes_liste = [r['moyenne_trimestrielle'] for r in resultats_bruts]
    paginator = Paginator(resultats_bruts, 35)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    
    user_info = Login.objects.first()
    return render(request, 'moyenne/trimestre_excel_generique.html', {
        "page_obj": page_obj,
        "trimestre": trimestre,
        "annee_academique": annee_academique,
        "moyenne_max": max(moyennes_liste) if moyennes_liste else 0,
        "moyenne_min": min(moyennes_liste) if moyennes_liste else 0,
        "school_name": user_info.school_name if user_info else "ACADYNOTE",
        "classe": classe,
        "serie_nom": serie_safe,
        "matieres_base": order_of_subjects,
    })


def liste_eleves(request, classe, annee_academique, serie=None):
    # 1. Construction du filtre dynamique
    filters = {'classe': classe, 'annee_academique': annee_academique}
    
    # Si une série est présente, on l'ajoute au filtre
    if serie and serie != "None":
        filters['serie'] = serie
        affichage_classe = f"{classe} {serie}"
    else:
        affichage_classe = classe

    # 2. Récupération des élèves
    eleves_list = Eleve.objects.filter(**filters).order_by('nom', 'prenoms')

    # 3. Statistiques (sur la liste totale avant pagination)
    total_eleves = eleves_list.count()
    total_garcons = eleves_list.filter(sexe="M").count()
    total_filles = eleves_list.filter(sexe="F").count()

    # 4. Pagination (50 élèves par page)
    paginator = Paginator(eleves_list, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 5. Calcul des numéros globaux pour le tableau
    for index, eleve in enumerate(page_obj):
        eleve.numero_global = index + (page_obj.start_index())

    # 6. Infos École
    user = Login.objects.first()
    school_name = user.school_name if user else ""
    profile_image = user.profile_image.url if user and user.profile_image else None

    return render(request, 'listes_classes/liste_eleves.html', {
        'page_obj': page_obj,
        'eleves': page_obj, # Contient les élèves de la page actuelle avec numero_global
        'classe': classe,
        'serie': serie,
        'affichage_classe': affichage_classe,
        'school_name': school_name,
        'annee_academique': annee_academique,
        'total_eleves': total_eleves,
        'total_garcons': total_garcons,
        'total_filles': total_filles,
        'profile_image': profile_image,
    })

def fiche_note(request, classe, annee_academique, serie=None): # Ajout de serie
    # 1. Filtrage dynamique (Collège ou Lycée)
    filters = {'classe': classe, 'annee_academique': annee_academique}
    if serie and serie != "None":
        filters['serie'] = serie
    
    eleves = Eleve.objects.filter(**filters).order_by('nom','prenoms')

    # 2. Pagination (35 élèves par page)
    paginator = Paginator(eleves, 35)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # 3. Calcul du numéro global
    for index, eleve in enumerate(page_obj.object_list):
        eleve.numero_global = index + (page_obj.start_index())

    # 4. Infos école
    user = Login.objects.first()
    school_name = user.school_name if user else ""
    profile_image = user.profile_image.url if user and user.profile_image else None

    return render(request, 'fiche_note.html', {
        'page_obj': page_obj,
        'eleves': page_obj.object_list,
        'classe': classe,
        'serie': serie, # On renvoie la série
        'annee_academique': annee_academique,
        'school_name': school_name,
        'profile_image': profile_image,
    })

def choisir_trimestre(request, eleve_id):
    eleve = get_object_or_404(Eleve, id=eleve_id)

    if request.method == 'POST':
        trimestre = int(request.POST.get('trimestre'))
        return redirect('envoyer_sms_notes', eleve_id=eleve.id, trimestre=trimestre)

    return render(request, 'email.html', {"eleve": eleve})

def fiche_notes_detail(request, classe, annee_academique, serie=None):
    filters = {'classe': classe, 'annee_academique': annee_academique}
    if serie and serie not in ["None", "none", "tout", ""]:
        filters['serie__iexact'] = serie
    else:
        if classe not in ['2nde', '1ère', 'Tle', 'Terminale']:
            filters['serie__in'] = ["", None]

    eleves = Eleve.objects.filter(**filters).order_by("nom", "prenoms")

    matieres_dropdown = [
        "Communication-Ecrite", "Lecture", "Philosophie", "Français", "Anglais", "Histoire-Géographie", 
        "Mathématiques", "PCT", "SVT", "Espagnol", "Allemand", 
        "EPS", "Economie", "Conduite", "Informatique"
    ]

    matiere_choisie = request.GET.get("matiere", "").strip()
    trimestre_str = request.GET.get("trimestre", "1")
    trimestre = int(trimestre_str) if trimestre_str.isdigit() else 1

    rows = []
    stats = {
        "filles": {"total": 0, "sup10": 0, "inf10": 0},
        "garcons": {"total": 0, "sup10": 0, "inf10": 0},
        "global": {"total": 0, "sup10": 0, "inf10": 0},
    }

    if matiere_choisie:
        # Optimisation : On récupère toutes les notes de la matière
        toutes_les_notes = Note.objects.filter(
            eleve__in=eleves,
            matiere__iexact=matiere_choisie,
            trimestre=trimestre,
            annee_academique=annee_academique
        )

        for eleve in eleves:
            # Filtrage des notes de l'élève pour CETTE matière
            notes_e = [n for n in toutes_les_notes if n.eleve_id == eleve.id]
            
            # --- FILTRE LV : Si l'élève n'a AUCUNE note dans cette matière, on l'ignore ---
            if not notes_e:
                continue 

            # Extraction par type
            intros = [n.valeur for n in notes_e if "interro" in n.type_note.lower()]
            d1_list = [n.valeur for n in notes_e if n.type_note == "devoir1"]
            d2_list = [n.valeur for n in notes_e if n.type_note == "devoir2"]
            
            d1 = d1_list[0] if d1_list else None
            d2 = d2_list[0] if d2_list else None
            devoirs_vals = [v for v in [d1, d2] if v is not None]

            # Calculs des moyennes
            moy_interro = round(sum(intros) / len(intros), 2) if intros else 0
            moy_dev = round(sum(devoirs_vals) / len(devoirs_vals), 2) if devoirs_vals else 0

            if not intros and devoirs_vals:
                moy_general = moy_dev
            elif devoirs_vals:
                moy_general = round((moy_interro + sum(devoirs_vals)) / (len(devoirs_vals) + 1), 2)
            else:
                moy_general = moy_interro

            coef = get_coefficient(classe, eleve.serie, matiere_choisie)
            moy_ponderee = round(moy_general * coef, 2) if moy_general > 0 else 0

            rows.append({
                "eleve": eleve,
                "intros": intros,
                "dev1": d1,
                "dev2": d2,
                "moy_interro": moy_interro,
                "moy_devoir": moy_dev,
                "moy_general": moy_general,
                "coefficient": coef,
                "moyenne_ponderee": moy_ponderee,
                "rang": "-"
            })

            # Stats (uniquement pour ceux qui ont des notes)
            sexe = (eleve.sexe or "M").lower()
            stats["global"]["total"] += 1
            cat = "filles" if sexe.startswith("f") else "garcons"
            stats[cat]["total"] += 1
            
            if moy_general >= 10:
                stats["global"]["sup10"] += 1
                stats[cat]["sup10"] += 1
            else:
                stats["global"]["inf10"] += 1
                stats[cat]["inf10"] += 1

        # Classement sur la matière
        rows.sort(key=lambda x: x["moy_general"], reverse=True)
        for idx, r in enumerate(rows):
            if r["moy_general"] > 0:
                r["rang"] = idx + 1

    # Calcul des pourcentages
    def pct(val, total):
        return round((val / total) * 100, 2) if total > 0 else 0

    stats_pct = {
        "reussite_global": pct(stats["global"]["sup10"], stats["global"]["total"]),
        "reussite_filles": pct(stats["filles"]["sup10"], stats["filles"]["total"]),
        "reussite_garcons": pct(stats["garcons"]["sup10"], stats["garcons"]["total"]),
    }

    user = Login.objects.first()
    return render(request, "fiche_notes_detail.html", {
        "classe": classe,
        "serie": serie,
        "annee_academique": annee_academique,
        "matieres": matieres_dropdown,
        "matiere_choisie": matiere_choisie,
        "trimestre": trimestre,
        "rows": rows,
        "school_name": user.school_name if user else "Mon École",
        "profile_image": user.profile_image.url if user and user.profile_image else None,
        "stats": stats,
        "stats_pct": stats_pct,
    })

import os
import requests
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from dotenv import load_dotenv
from .models import Eleve, Note

# Charger les variables d'environnement
load_dotenv()

import os
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.db.models import Q

def envoyer_notes(request, classe, annee_academique, serie=None):
    trimestre = int(request.GET.get("trimestre", 1))
    
    # Récupération dynamique du nom de l'école
    user_info = Login.objects.first()
    NOM_ECOLE = user_info.school_name if user_info else "ACADYNOTE"

    # 1. Filtrage des élèves
    filtres = {'classe': classe, 'annee_academique': annee_academique}
    if not serie or serie in ["None", "none", "tout", ""]:
        eleves = Eleve.objects.filter(
            Q(serie__isnull=True) | Q(serie="") | Q(serie="None"),
            **filtres
        ).order_by('nom')
    else:
        filtres['serie'] = serie
        eleves = Eleve.objects.filter(**filtres).order_by('nom')

    recap = []

    for eleve in eleves:
        status = {
            "eleve": eleve, 
            "email": eleve.email_parent, 
            "email_sent": False, 
            "note_disponible": False
        }
        
        # 2. Récupération des notes
        notes = Note.objects.filter(eleve=eleve, trimestre=trimestre, annee_academique=annee_academique)

        if notes.exists():
            status["note_disponible"] = True
            matieres_status = {}
            total_points_ponderes = 0
            total_coefficients = 0

            # 3. Organisation des notes
            for n in notes:
                if n.matiere not in matieres_status:
                    coef = get_coefficient(eleve.classe, eleve.serie, n.matiere)
                    matieres_status[n.matiere] = {
                        "interros": [], "devoirs": [], "coef": coef,
                        "moyenne_interros": 0, "moyenne_generale": 0
                    }
                
                if 'interro' in n.type_note.lower():
                    matieres_status[n.matiere]["interros"].append(n.valeur)
                elif 'devoir' in n.type_note.lower():
                    matieres_status[n.matiere]["devoirs"].append(n.valeur)

            # 4. Calcul des moyennes et filtrage des LV non suivies
            matieres_a_envoyer = {} # On crée un nouveau dict pour les matières valides
            
            for matiere, m_data in matieres_status.items():
                interros = m_data["interros"]
                devoirs = m_data["devoirs"]
                
                # SI AUCUNE NOTE, on ignore totalement la matière (Cas des LV)
                if not interros and not devoirs:
                    continue

                moy_int = round(sum(interros) / len(interros), 2) if interros else 0
                
                # Logique de calcul générale
                if not devoirs:
                    m_gen = moy_int
                else:
                    if not interros:
                        m_gen = round(sum(devoirs) / len(devoirs), 2)
                    elif len(devoirs) == 2:
                        m_gen = round((sum(devoirs) + moy_int) / 3, 2)
                    elif len(devoirs) == 1:
                        m_gen = round((devoirs[0] + moy_int) / 2, 2)
                    else:
                        m_gen = round(sum(devoirs) / len(devoirs), 2)

                m_data["moyenne_interros"] = moy_int
                m_data["moyenne_generale"] = m_gen

                # Cumul moyenne trimestrielle
                if m_gen > 0:
                    total_points_ponderes += (m_gen * m_data["coef"])
                    total_coefficients += m_data["coef"]
                    matieres_a_envoyer[matiere] = m_data # On ajoute aux matières à envoyer

            # 5. Calcul Moyenne Finale
            if total_coefficients > 0:
                moy_calculee = total_points_ponderes / total_coefficients
                moyenne_trim_str = "{:.2f}".format(round(moy_calculee, 2))
            else:
                moyenne_trim_str = "0.00"

            # 6. Envoi de l'Email
            if eleve.email_parent and matieres_a_envoyer:
                try:
                    val_moy = float(moyenne_trim_str)
                    appr = "Excellent" if val_moy >= 16 else "Bien" if val_moy >= 14 else "A. Bien" if val_moy >= 12 else "Passable" if val_moy >= 10 else "Insuffisant"
                    
                    html_content = render_to_string("notes_eleve.html", {
                        "eleve": eleve,
                        "matieres_status": matieres_a_envoyer, # Liste filtrée
                        "moyenne_trimestrielle": moyenne_trim_str,
                        "trimestre": trimestre,
                        "annee_academique": annee_academique,
                        "appreciation": appr,
                        "school_name": NOM_ECOLE,
                        "serie": eleve.serie if (eleve.serie and eleve.serie != "None") else "",
                    })

                    subject = f"Notes T{trimestre} - {eleve.nom} {eleve.prenoms}"
                    text_body = f"Résultats du Trimestre {trimestre}"
                    from_email = f"{NOM_ECOLE} <{os.getenv('EMAIL_HOST_USER')}>"
                    
                    msg = EmailMultiAlternatives(subject, text_body, from_email, [eleve.email_parent])
                    msg.attach_alternative(html_content, "text/html")
                    msg.send()
                    
                    status["email_sent"] = True
                except Exception as e:
                    print(f"Erreur email {eleve.nom}: {e}")
                    status["email_sent"] = False

        recap.append(status)
    
    # Préparation de la série pour l'affichage (évite d'afficher "None")
    serie_display = serie if (serie and serie != "None") else ""
    return render(request, "email_all.html", {
        "recap": recap, 
        "school_name": NOM_ECOLE,
        "trimestre": trimestre,
        "classe": classe,
        "serie" : serie_display
    })
def matieres_email_filter(matieres_dict):
    """Petit utilitaire pour ne pas envoyer les matières sans notes dans l'email"""
    return {k: v for k, v in matieres_dict.items() if v['moyenne_generale'] > 0}

def envoyer_email_notes(request, eleve_id, trimestre):
    """
    Envoi du bulletin par email pour un seul élève.
    Affiche EXACTEMENT les matières où l'élève possède des notes (LV incluses).
    """
    eleve = get_object_or_404(Eleve, id=eleve_id)
    trimestre = int(request.GET.get("trimestre", trimestre))
    annee_academique = eleve.annee_academique
    
    # Nom de l'école dynamique
    user_info = Login.objects.first()
    NOM_ECOLE = user_info.school_name if user_info else "ACADYNOTE"

    # 1. Nettoyage de la série pour l'affichage
    serie_display = eleve.serie if (eleve.serie and eleve.serie not in ["None", "none", "tout", ""]) else ""

    # 2. Récupération de TOUTES les notes de l'élève pour ce trimestre
    # On ne filtre plus par une liste fixe, on prend ce qui existe en base
    notes = Note.objects.filter(
        eleve=eleve, 
        trimestre=trimestre, 
        annee_academique=annee_academique
    ).order_by('matiere')
    
    if not notes.exists():
        messages.error(request, f"Aucune note disponible pour {eleve.nom} au Trimestre {trimestre}.")
        return render(request, "email.html", {"eleve": eleve, "school_name": NOM_ECOLE})

    # 3. Organisation et calculs
    matieres_status = {}
    total_points_ponderes = 0
    total_coefficients = 0

    for n in notes:
        # On groupe par matière dynamiquement
        if n.matiere not in matieres_status:
            coef = get_coefficient(eleve.classe, eleve.serie, n.matiere)
            matieres_status[n.matiere] = {
                "interros": [], "devoirs": [], "coef": coef,
                "moyenne_interros": 0, "moyenne_generale": 0
            }
        
        if 'interro' in n.type_note.lower():
            matieres_status[n.matiere]["interros"].append(n.valeur)
        elif 'devoir' in n.type_note.lower():
            matieres_status[n.matiere]["devoirs"].append(n.valeur)

    # 4. Calcul des moyennes (Même logique que l'envoi groupé)
    for matiere, m_data in matieres_status.items():
        interros = m_data["interros"]
        devoirs = m_data["devoirs"]
        
        moy_int = round(sum(interros) / len(interros), 2) if interros else 0
        
        if not devoirs:
            m_gen = moy_int
        else:
            if not interros:
                m_gen = round(sum(devoirs) / len(devoirs), 2)
            elif len(devoirs) == 2:
                m_gen = round((sum(devoirs) + moy_int) / 3, 2)
            elif len(devoirs) == 1:
                m_gen = round((devoirs[0] + moy_int) / 2, 2)
            else:
                m_gen = round(sum(devoirs) / len(devoirs), 2)

        m_data["moyenne_interros"] = moy_int
        m_data["moyenne_generale"] = m_gen

        if m_gen > 0:
            total_points_ponderes += (m_gen * m_data["coef"])
            total_coefficients += m_data["coef"]

    # 5. Moyenne Trimestrielle
    if total_coefficients > 0:
        moy_brute = total_points_ponderes / total_coefficients
        moyenne_trim_str = "{:.2f}".format(round(moy_brute, 2))
    else:
        moyenne_trim_str = "0.00"

    # Rang (récupéré depuis la base)
    info_b = notes.first()
    rang = info_b.rang if (info_b and info_b.rang) else "N/A"
    
    # Appréciation
    val_moy = float(moyenne_trim_str)
    appr = "Excellent" if val_moy >= 16 else "Bien" if val_moy >= 14 else "A. Bien" if val_moy >= 12 else "Passable" if val_moy >= 10 else "Insuffisant"

    # 6. Envoi de l'Email
    if eleve.email_parent:
        try:
            html_content = render_to_string("notes_eleve.html", {
                "eleve": eleve,
                "matieres_status": matieres_status,
                "moyenne_trimestrielle": moyenne_trim_str,
                "rang": rang,
                "trimestre": trimestre,
                "annee_academique": annee_academique,
                "appreciation": appr,
                "school_name": NOM_ECOLE,
                "serie": serie_display,
            })

            subject = f"Bulletin T{trimestre} - {eleve.nom} {eleve.prenoms}"
            from_email = f"{NOM_ECOLE} <{os.getenv('EMAIL_HOST_USER')}>"
            
            msg = EmailMultiAlternatives(subject, "Veuillez trouver ci-joint vos résultats.", from_email, [eleve.email_parent])
            msg.attach_alternative(html_content, "text/html")
            msg.send()
            
            messages.success(request, f"Le bulletin de {eleve.nom} a été envoyé.")
        except Exception as e:
            messages.error(request, f"Erreur d'envoi : {e}")
    else:
        messages.warning(request, "Aucun email parent trouvé.")

    return render(request, "email.html", {
        "eleve": eleve, 
        "school_name": NOM_ECOLE,
        "trimestre": trimestre,
        "annee_academique": annee_academique,
        "serie": serie_display
    })
    
from django.shortcuts import render
from django.http import HttpResponse
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from myapp.models import Eleve, Login

# === Vue pour la page HTML avec le bouton ===
def page_telechargement(request, classe, annee_academique):
    return render(request, 'telecharger_cartes.html', {
        'classe': classe,
        'annee_academique': annee_academique
    })

import os
import qrcode
from io import BytesIO
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

# Assurez-vous que ces modèles correspondent à votre application
from .models import Eleve, Login 

def generer_cartes_pdf(request, classe, annee_academique, serie=None):
    """
    Génère un PDF de cartes scolaires complet.
    """
    
    # 1. FILTRAGE DE BASE (Année et Classe)
    # On utilise __iexact pour la classe pour éviter de confondre "3ème" et "3ème Lycée" par exemple
    eleves_queryset = Eleve.objects.filter(
        annee_academique=annee_academique,
        classe__icontains=classe
    )
    
    # 2. GESTION DE LA SÉRIE (La correction est ici)
    if serie and str(serie).lower() not in ["aucune", "none", "nan"]:
        # ⚠️ On filtre sur le champ 'serie' et non sur le champ 'classe'
        eleves_queryset = eleves_queryset.filter(serie__iexact=serie)
        classe_affichage = f"{classe} {serie}"
    else:
        classe_affichage = classe

    eleves = eleves_queryset.order_by("nom", "prenoms")

    # 3. VÉRIFICATION
    if not eleves.exists():
        return HttpResponse(f"Erreur : Aucun élève trouvé pour la série '{serie}' en classe de '{classe}' pour l'année {annee_academique}.")
    user = Login.objects.first()
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    w_page, h_page = A4
    
    # Dimensions d'une carte (CR80)
    c_w, c_h = 243, 153 

    # Positions pour 8 cartes par page (2 colonnes x 4 lignes)
    margin_x = (w_page - (c_w * 2)) / 3
    margin_y = 35
    positions = []
    for row in range(4):
        for col in range(2):
            pos_x = margin_x + col * (c_w + margin_x)
            pos_y = h_page - margin_y - (row + 1) * c_h - (row * 15)
            positions.append((pos_x, pos_y))

    # Sécurité pour le chargement des images
    def get_image_safe(image_field):
        if image_field and hasattr(image_field, 'path') and os.path.exists(image_field.path):
            try:
                return ImageReader(image_field.path)
            except:
                return None
        return None

    # Logos globaux
    logo_gauche = get_image_safe(user.profile_image) if user else None
    logo_droit = get_image_safe(user.coin_droit) if user else None
    blason_verso = get_image_safe(user.fond_verso) if user else None

    # 3. GÉNÉRATION DES PAGES
    for i in range(0, len(eleves), 8):
        groupe = eleves[i:i+8]

        # --- RECTO ---
        for j, eleve in enumerate(groupe):
            x, y = positions[j]
            
            # Bordure bleue
            pdf.setStrokeColor(colors.HexColor("#0033CC"))
            pdf.setLineWidth(1.5)
            pdf.roundRect(x, y, c_w, c_h, 10, stroke=1, fill=0)

            # Logos en-tête
            if logo_gauche:
                pdf.drawImage(logo_gauche, x + 5, y + c_h - 38, width=28, height=28, preserveAspectRatio=True)
            if logo_droit:
                pdf.drawImage(logo_droit, x + c_w - 33, y + c_h - 38, width=28, height=28, preserveAspectRatio=True)

            # Textes Administratifs (Tout est là)
            center_x = x + c_w / 2
            pdf.setFillColor(colors.black)
            pdf.setFont("Helvetica-Bold", 5.5)
            pdf.drawCentredString(center_x, y + c_h - 10, "RÉPUBLIQUE DU BÉNIN")
            pdf.setFont("Helvetica", 4.2)
            pdf.drawCentredString(center_x, y + c_h - 16, "MINISTÈRE DES ENSEIGNEMENTS SECONDAIRE, TECHNIQUE")
            pdf.drawCentredString(center_x, y + c_h - 21, "ET DE LA FORMATION PROFESSIONNELLE")
            
            pdf.setFont("Helvetica-Bold", 5)
            pdf.drawCentredString(center_x, y + c_h - 28, "DDEMP : OUEME")
            pdf.drawCentredString(center_x, y + c_h - 34, f"ANNÉE SCOLAIRE : {annee_academique}")
            
            pdf.setFillColor(colors.HexColor("#0033CC"))
            pdf.setFont("Helvetica-Bold", 7.5)
            pdf.drawCentredString(center_x, y + c_h - 44, "C.P.E.G LE TRÉSOR DE DOWA")
            pdf.setFont("Helvetica-Bold", 5)
            pdf.drawCentredString(center_x, y + c_h - 51, "Tel : 0197884441 / 98252598 Porto-Novo")

            pdf.setFillColor(colors.red)
            pdf.setFont("Helvetica-Bold", 8.5)
            pdf.drawCentredString(center_x, y + c_h - 62, "CARTE D'IDENTITÉ SCOLAIRE")

            # Informations de l'élève
            info_x = x + 10
            curr_y = y + 74 
            date_n = eleve.date_naissance.strftime("%d/%m/%Y") if eleve.date_naissance else ""
            
            infos = [
                ("NOM", eleve.nom.upper()),
                ("Prénoms", eleve.prenoms),
                ("Né(e) le", f"{date_n} à {eleve.lieu_naissance}"),
                ("Sexe", eleve.sexe),
                ("Classe", classe_affichage),
                ("Matricule", eleve.matricule),
            ]

            pdf.setFillColor(colors.black)
            for label, val in infos:
                pdf.setFont("Helvetica-Bold", 6.5)
                pdf.drawString(info_x, curr_y, f"{label}:")
                pdf.setFont("Helvetica", 6.5)
                pdf.drawString(info_x + 40, curr_y, str(val)[:32])
                curr_y -= 10.5

            # Photo
            photo_img = get_image_safe(eleve.profile_eleve)
            if photo_img:
                pdf.drawImage(photo_img, x + c_w - 75, y + 12, width=65, height=72, preserveAspectRatio=True)
            else:
                pdf.rect(x + c_w - 75, y + 12, 65, 72)

        pdf.showPage() 

        # --- VERSO ---
        for j, eleve in enumerate(groupe):
            col = j % 2
            row = j // 2
            idx_v = row * 2 + (1 - col) 
            xv, yv = positions[idx_v]

            pdf.setStrokeColor(colors.HexColor("#0033CC"))
            pdf.roundRect(xv, yv, c_w, c_h, 10, stroke=1, fill=0)

            # QR Code
            qr_data = f"ID:{eleve.matricule}|{eleve.nom}|{classe_affichage}"
            qr = qrcode.make(qr_data)
            qr_io = BytesIO()
            qr.save(qr_io, format='PNG')
            qr_io.seek(0)
            pdf.drawImage(ImageReader(qr_io), xv + c_w - 55, yv + c_h - 60, width=45, height=45)

            # Textes Sécurité Verso
            pdf.setFillColor(colors.black)
            pdf.setFont("Helvetica-Bold", 7)
            pdf.drawString(xv + 15, yv + c_h - 20, "C.P.E.G LE TRÉSOR DE DOWA")
            pdf.setFont("Helvetica-Oblique", 5.5)
            pdf.drawString(xv + 15, yv + c_h - 30, "Cette carte est strictement personnelle.")
            pdf.drawString(xv + 15, yv + c_h - 38, "En cas de perte, veuillez contacter le :")
            pdf.setFont("Helvetica-Bold", 6)
            pdf.drawString(xv + 15, yv + c_h - 46, "01 97 88 44 41 / 98 25 25 98")

            # Blason en filigrane
            if blason_verso:
                pdf.saveState()
                pdf.setStrokeAlpha(0.1)
                pdf.drawImage(blason_verso, xv + 15, yv + 25, width=45, height=45, preserveAspectRatio=True, mask='auto')
                pdf.restoreState()

            # Signature
            pdf.setFont("Helvetica-Bold", 9)
            pdf.drawCentredString(xv + c_w - 70, yv + 50, "LE DIRECTEUR")

        pdf.showPage() 

    # 4. FIN
    pdf.save()
    buffer.seek(0)
    nom_f = f"Cartes_{classe_affichage.replace(' ', '_')}.pdf"
    return HttpResponse(buffer, content_type="application/pdf", 
                        headers={"Content-Disposition": f'attachment; filename="{nom_f}"'})

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from .models import Enseignant, Eleve, Note, Login

def inserer_notes_classe_enseignant(request, classe, annee_academique, serie=None):
    # 1. Sécurité de session
    enseignant_id = request.session.get('enseignant_id')
    if not enseignant_id:
        messages.error(request, "Veuillez vous connecter.")
        return redirect('enseignant_login')

    enseignant = get_object_or_404(Enseignant, id=enseignant_id)

    # 2. Récupération de la MATIÈRE (Priorité GET, puis profil prof)
    matiere_choisie = request.GET.get('matiere') or enseignant.matiere

    # 3. Traitement du "1ère B / None"
    # Si la série est "None" mais que la classe contient la série (ex: "1ère B")
    classe_input = classe.strip()
    serie_input = serie
    
    if (not serie_input or str(serie_input).lower() == "none") and " " in classe_input:
        parts = classe_input.split(" ")
        classe_pure = parts[0]   # ex: "1ère"
        serie_propre = parts[1]  # ex: "B"
    else:
        classe_pure = classe_input
        serie_propre = serie_input if (serie_input and str(serie_input).lower() != "none") else None

    # 4. Filtrage des élèves
    # On cherche soit par le nom complet "1ère B", soit par le couple "1ère" + "B"
    query = (Q(classe__iexact=classe_pure) | Q(classe__iexact=classe_input)) & \
            Q(annee_academique__icontains=annee_academique)

    if serie_propre:
        query &= Q(serie__iexact=serie_propre)
    else:
        # Pour le collège : on exclut les séries
        query &= (Q(serie__isnull=True) | Q(serie="") | Q(serie__iexact="None"))

    # Logique spécifique pour les profs de langues
    langues_cles = ["espagnol", "allemand", "anglais", "lv1", "lv2"]
    if any(l in matiere_choisie.lower() for l in langues_cles):
        query &= (
            Q(langue_specialite__icontains=matiere_choisie) | 
            Q(lv1__icontains=matiere_choisie) | 
            Q(lv2__icontains=matiere_choisie)
        )

    eleves = Eleve.objects.filter(query).order_by("nom", "prenoms")

    # 5. Gestion du Trimestre
    trimestre_selected = int(request.POST.get("trimestre") or request.GET.get("trimestre") or 1)
    type_notes = ["interro1", "interro2", "interro3", "devoir1", "devoir2"]

    # 6. TRAITEMENT DU POST (Sauvegarde des notes)
    if request.method == "POST":
        notes_creees = 0
        for eleve in eleves:
            for tn in type_notes:
                val_raw = request.POST.get(f"note_{eleve.id}_{tn}")
                
                if val_raw is not None and val_raw.strip() != "":
                    try:
                        val_float = float(val_raw.replace(',', '.'))
                        if 0 <= val_float <= 20:
                            # SÉCURITÉ : Ne pas modifier une note déjà existante
                            note_obj, created = Note.objects.get_or_create(
                                eleve=eleve,
                                matiere=matiere_choisie,
                                type_note=tn,
                                trimestre=trimestre_selected,
                                annee_academique=annee_academique,
                                defaults={'valeur': val_float}
                            )
                            if created:
                                notes_creees += 1
                    except ValueError:
                        continue

        if notes_creees > 0:
            messages.success(request, f"{notes_creees} note(s) enregistrée(s) en {matiere_choisie}.")
        else:
            messages.info(request, "Aucune nouvelle note enregistrée (doublons ou champs vides).")
        
        # Redirection avec les paramètres pour rester sur la même sélection
        return redirect(f"{request.path}?matiere={matiere_choisie}&trimestre={trimestre_selected}")

    # 7. RÉCUPÉRATION DES NOTES POUR L'AFFICHAGE (mapping rapide)
    toutes_notes = Note.objects.filter(
        eleve__in=eleves,
        matiere=matiere_choisie,
        trimestre=trimestre_selected,
        annee_academique=annee_academique
    )
    notes_map = {(n.eleve_id, n.type_note): n.valeur for n in toutes_notes}

    for eleve in eleves:
        eleve.interro1 = notes_map.get((eleve.id, "interro1"), "")
        eleve.interro2 = notes_map.get((eleve.id, "interro2"), "")
        eleve.interro3 = notes_map.get((eleve.id, "interro3"), "")
        eleve.devoir1 = notes_map.get((eleve.id, "devoir1"), "")
        eleve.devoir2 = notes_map.get((eleve.id, "devoir2"), "")

    # 8. Infos Établissement
    config = Login.objects.first()
    school_name = config.school_name if config else "ACADYNOTE"

    return render(request, "enseignant/inserer_notes.html", {
        "eleves": eleves,
        "classe": classe_pure,
        "serie": serie_propre,
        "annee_academique": annee_academique,
        "trimestre_selected": trimestre_selected,
        "matiere": matiere_choisie, # Très important pour le bouton "Voir Fiche"
        "school_name": school_name
    })

def fiche_notes_detail_enseignant(request, classe, annee_academique, matiere, serie=None):
    # 1. Sécurité Session
    enseignant_id = request.session.get('enseignant_id')
    if not enseignant_id:
        messages.error(request, "Vous devez être connecté.")
        return redirect('enseignant_login')

    enseignant = get_object_or_404(Enseignant, id=enseignant_id)

    # 2. Paramètres (Matière récupérée directement de l'URL)
    matiere_choisie = matiere 
    trimestre = int(request.GET.get("trimestre", 1))
    
    # Nettoyage des chaînes
    serie_filtre = serie if (serie and str(serie).lower() not in ["none", "aucune", "", "nan"]) else None
    classe_str = classe.strip()
    annee_str = annee_academique.strip()

    # 3. Filtrage des élèves
    query = Q(classe__iexact=classe_str) & Q(annee_academique__icontains=annee_str)
    
    if serie_filtre:
        query &= Q(serie__iexact=serie_filtre)
        classe_affichage = f"{classe_str} {serie_filtre}"
    else:
        query &= (Q(serie__isnull=True) | Q(serie="") | Q(serie__iexact="None"))
        classe_affichage = classe_str

    # Logique spécifique Langues (LV)
    langues_cles = ["espagnol", "allemand", "anglais", "lv1", "lv2"]
    if any(l in matiere_choisie.lower() for l in langues_cles):
        query &= (
            Q(langue_specialite__icontains=matiere_choisie) | 
            Q(lv1__icontains=matiere_choisie) | 
            Q(lv2__icontains=matiere_choisie)
        )

    eleves = Eleve.objects.filter(query).order_by("nom", "prenoms")

    # 4. Récupération des notes et du COEFFICIENT
    toutes_les_notes = Note.objects.filter(
        eleve__in=eleves,
        matiere=matiere_choisie,
        trimestre=trimestre,
        annee_academique=annee_str
    )

    # --- RÉCUPÉRATION DU COEFFICIENT VIA TA FONCTION ---
    # On l'appelle sur la première note trouvée ou on met 1 par défaut
    coefficient_matiere = 1
    if toutes_les_notes.exists():
        first_note = toutes_les_notes.first()
        # On utilise la fonction get_coefficient() comme tu l'as indiqué
        try:
            coefficient_matiere = first_note.get_coefficient()
        except (AttributeError, TypeError):
            coefficient_matiere = 1

    # Mapping pour performance {(eleve_id, type_note): valeur}
    notes_dict = {(n.eleve_id, n.type_note): n.valeur for n in toutes_les_notes}
    
    rows = []
    moyennes_pour_classement = []
    stats = {
        "filles": {"total": 0, "sup10": 0, "inf10": 0},
        "garcons": {"total": 0, "sup10": 0, "inf10": 0},
        "global": {"total": 0, "sup10": 0, "inf10": 0},
    }

    # 5. Calcul des moyennes par élève
    for eleve in eleves:
        # On pioche dans le dictionnaire
        i_notes = [notes_dict.get((eleve.id, tn)) for tn in ["interro1", "interro2", "interro3"]]
        d_notes = [notes_dict.get((eleve.id, tn)) for tn in ["devoir1", "devoir2"]]

        i_valid = [n for n in i_notes if n is not None]
        d_valid = [n for n in d_notes if n is not None]

        moy_interro = round(sum(i_valid) / len(i_valid), 2) if i_valid else 0
        moy_dev = round(sum(d_valid) / len(d_valid), 2) if d_valid else 0

        # Calcul de la moyenne générale
        if not i_valid and d_valid:
            moy_general = moy_dev
        elif d_valid:
            # Formule standard : (Moyenne devoirs + Moyenne interros) / (Nb devoirs + 1)
            moy_general = round((sum(d_valid) + moy_interro) / (len(d_valid) + 1), 2)
        else:
            moy_general = moy_interro

        # Utilisation du coefficient récupéré via ta fonction
        moyenne_ponderee = round(moy_general * coefficient_matiere, 2)

        rows.append({
            "eleve": eleve,
            "int1": i_notes[0], "int2": i_notes[1], "int3": i_notes[2],
            "dev1": d_notes[0], "dev2": d_notes[1],
            "moy_interro": moy_interro, "moy_devoir": moy_dev,
            "moy_general": moy_general, "coefficient": coefficient_matiere,
            "moyenne_ponderee": moyenne_ponderee, "rang": "-"
        })

        # Mise à jour des statistiques
        if i_valid or d_valid:
            stats["global"]["total"] += 1
            genre = "filles" if eleve.sexe.upper() == "F" else "garcons"
            stats[genre]["total"] += 1
            if moy_general >= 10:
                stats["global"]["sup10"] += 1
                stats[genre]["sup10"] += 1
            else:
                stats["global"]["inf10"] += 1
                stats[genre]["inf10"] += 1
            
            moyennes_pour_classement.append({"eleve_id": eleve.id, "moy": moy_general})

    # 6. Classement automatique
    moyennes_pour_classement.sort(key=lambda x: x["moy"], reverse=True)
    for index, item in enumerate(moyennes_pour_classement):
        for r in rows:
            if r["eleve"].id == item["eleve_id"]:
                r["rang"] = index + 1

    # 7. Nom de l'école
    config = Login.objects.first()
    school_name = config.school_name if config else "ACADYNOTE"

    def pct(val, total): return round((val / total) * 100, 2) if total > 0 else 0

    context = {
        "classe": classe_str,
        "serie": serie_filtre,
        "annee_academique": annee_str,
        "classe_affichage": classe_affichage,
        "matiere_choisie": matiere_choisie,
        "trimestre": trimestre,
        "rows": rows,
        "school_name": school_name,
        "stats": stats,
        "stats_pct": {
            "reussite_global": pct(stats["global"]["sup10"], stats["global"]["total"]),
            "reussite_filles": pct(stats["filles"]["sup10"], stats["filles"]["total"]),
            "reussite_garcons": pct(stats["garcons"]["sup10"], stats["garcons"]["total"]),
        },
    }
    return render(request, "enseignant/fiche_notes_detail.html", context)

def liste_enseignants(request):
    # 1. Récupérer l'année choisie (si elle existe)
    annee_filtre = request.GET.get('annee_academique', '').strip()

    # 2. Récupérer toutes les années disponibles pour le menu déroulant
    # On prend les années distinctes présentes chez les enseignants
    annees_disponibles = Enseignant.objects.values_list('annee_academique', flat=True).distinct().order_by('-annee_academique')

    # 3. Filtrer les enseignants
    enseignants_queryset = Enseignant.objects.all()
    if annee_filtre:
        enseignants_queryset = enseignants_queryset.filter(annee_academique=annee_filtre)
    
    enseignants = enseignants_queryset.order_by('nom', 'prenoms')

    # 4. Filtrer les horaires
    # On filtre les horaires dont l'enseignant appartient à l'année choisie
    horaires_queryset = Horaire.objects.all()
    if annee_filtre:
        horaires_queryset = horaires_queryset.filter(enseignant__annee_academique=annee_filtre)
    
    horaires = horaires_queryset.order_by('classe', 'jour', 'heure_debut')

    context = {
        "enseignants": enseignants,
        "horaires": horaires,
        "annees_disponibles": annees_disponibles,
        "annee_actuelle": annee_filtre,
    }

    # Gestion des messages
    if 'success' in request.GET:
        context['success'] = request.GET.get('success')
    if 'error' in request.GET:
        context['error'] = request.GET.get('error')

    return render(request, "enseignant/liste_enseignants.html", context)


def modifier_horaire(request, enseignant_id):
    enseignant = get_object_or_404(Enseignant, id=enseignant_id)
    horaires = Horaire.objects.filter(enseignant=enseignant).order_by('classe', 'jour', 'heure_debut')
    
    # Récupérer les classes distinctes de l'enseignant
    classes = enseignant.classes.split(',')  # si tu stockes plusieurs classes séparées par virgule

    # Liste des jours
    jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"]

    if request.method == "POST":
        horaire_id = request.POST.get("horaire_id")
        classe = request.POST.get("classe")
        jour = request.POST.get("jour")
        heure_debut = request.POST.get("heure_debut")
        heure_fin = request.POST.get("heure_fin")

        horaire = get_object_or_404(Horaire, id=horaire_id)
        horaire.classe = classe
        horaire.jour = jour
        horaire.heure_debut = heure_debut
        horaire.heure_fin = heure_fin
        horaire.save()

        messages.success(request, "Horaire modifié avec succès !")
        return redirect(request.path)  # reste sur la même page

    return render(request, "enseignant/modifier_horaire.html", {
        "enseignant": enseignant,
        "horaires": horaires,
        "classes": classes,
        "jours": jours
    })

from django.shortcuts import render, get_object_or_404
from .models import Enseignant, Horaire

def ajouter_horaire(request, enseignant_id):
    enseignant = get_object_or_404(Enseignant, id=enseignant_id)
    jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"]
    classes = [c.strip() for c in enseignant.classes.split(',')]

    message = ""  # variable pour afficher le message

    if request.method == "POST":
        classe = request.POST.get("classe")
        jour = request.POST.get("jour")
        heure_debut = request.POST.get("heure_debut")
        heure_fin = request.POST.get("heure_fin")

        if classe and jour and heure_debut and heure_fin:
            Horaire.objects.create(
                classe=classe,
                jour=jour,
                heure_debut=heure_debut,
                heure_fin=heure_fin,
                matiere=enseignant.matiere,
                enseignant=enseignant,
                annee_academique=enseignant.annee_academique
            )
            message = "Horaire enregistré avec succès !"

    context = {
        "enseignant": enseignant,
        "jours": jours,
        "classes": classes,
        "message": message,
    }
    return render(request, "enseignant/ajouter_horaire.html", context)

def supprimer_enseignant(request, enseignant_id):
    enseignant = get_object_or_404(Enseignant, id=enseignant_id)
    enseignant.delete()
    # redirection vers la page liste_enseignants avec message spécifique
    return redirect(f"{request.META.get('HTTP_REFERER','/')}?success=Enseignant+supprimé+avec+succès")

from django.shortcuts import render
from django.utils.dateparse import parse_date
from .models import Note, Enseignant

def consulter_notes(request):
    date_str = request.GET.get('date')
    classe_nom = request.GET.get('classe')
    
    notes = []

    if date_str and classe_nom:
        date_obj = parse_date(date_str)  # convertir la date string en date
        # Récupérer les notes pour la classe et la date
        notes = Note.objects.filter(
            eleve__classe=classe_nom,
            date_ajout__date=date_obj
        ).select_related('eleve')
        
        # Ajouter le nom de l'enseignant à chaque note
        for note in notes:
            enseignant = Enseignant.objects.filter(
                classes=note.eleve.classe,
                matiere=note.matiere,
                annee_academique=note.annee_academique
            ).first()
            note.nom_enseignant = f"{enseignant.nom} {enseignant.prenoms}" if enseignant else "N/A"

    return render(request, 'notes_jour.html',{
        'notes': notes,
        'classe': classe_nom,
        'date': date_str
    })

def suivre_eleve_form(request):
    return render(request, 'suivre_eleve_form.html')


from decimal import Decimal, ROUND_HALF_UP
from django.shortcuts import render
from .models import Eleve, Note, Login
from .utils import get_coefficient # Ta fonction de gestion des coefficients

from decimal import Decimal, ROUND_HALF_UP

def suivre_eleve_resultat(request):
    # 1. RÉCUPÉRATION ET NETTOYAGE DES ENTRÉES
    raw_numero = request.GET.get("educmaster", "")
    numero = raw_numero.strip()
    
    trimestre_val = request.GET.get("trimestre", 1)
    annee_formulaire = request.GET.get("annee", "").strip()

    if not numero:
        return render(request, "error.html", {"message": "Veuillez entrer un numéro EducMaster."})

    # 2. RECHERCHE DE L'ÉLÈVE
    eleve = Eleve.objects.filter(matricule__iexact=numero).first()

    if not eleve:
        return render(request, "error.html", {
            "message": f"Aucun élève trouvé avec le matricule '{numero}'. Vérifiez votre saisie."
        })

    # 3. BARRIÈRE DE PAIEMENT (Optionnel selon ton besoin)
    if not eleve.email_parent:
        return render(request, "error.html", {
            "message": f"Accès restreint pour {eleve.nom}. Les frais de service numérique n'ont pas été réglés.",
            "title": "Service Non Activé"
        })

    # 4. NORMALISATION DE LA SÉRIE (Pour éviter l'affichage de 'None')
    serie_eleve = eleve.serie if (eleve.serie and eleve.serie not in ["None", "none", "aucune", ""]) else ""
    annee = annee_formulaire if annee_formulaire else eleve.annee_academique.strip()

    # 5. RÉCUPÉRATION DES NOTES
    notes = Note.objects.filter(eleve=eleve, trimestre=trimestre_val, annee_academique=annee)
    
    if not notes.exists():
        return render(request, "error.html", {
            "message": f"Élève trouvé, mais aucune note n'est enregistrée pour le trimestre {trimestre_val} en {annee}."
        })

    # 6. CALCULS PAR MATIÈRE (Dynamique pour inclure les LV seulement si présentes)
    matieres_status = {}
    total_points_trimestre = Decimal('0.00')
    total_coefficients_trimestre = Decimal('0.00')

    for n in notes:
        if n.matiere not in matieres_status:
            # On passe la série nettoyée à la fonction de coefficient
            coef = get_coefficient(eleve.classe, eleve.serie, n.matiere)
            matieres_status[n.matiere] = {
                "interros": [],
                "devoirs": [],
                "moyenne_interros": Decimal('0.00'),
                "moyenne_generale": Decimal('0.00'),
                "coefficient": coef
            }

        val_note = Decimal(str(n.valeur))
        type_n = n.type_note.lower()
        if "interro" in type_n:
            matieres_status[n.matiere]["interros"].append(val_note)
        elif "devoir" in type_n:
            matieres_status[n.matiere]["devoirs"].append(val_note)

    # 7. FINALISATION DES MOYENNES
    # On crée un dictionnaire final pour ne garder que les matières avec des points
    matieres_finales = {}

    for m, status in matieres_status.items():
        has_interros = len(status["interros"]) > 0
        if has_interros:
            status["moyenne_interros"] = (sum(status["interros"]) / Decimal(len(status["interros"]))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        
        nb_devs = len(status["devoirs"])
        
        # Calcul selon ta règle (Rectorat)
        if nb_devs > 0:
            if has_interros:
                total_matiere = status["moyenne_interros"] + sum(status["devoirs"])
                diviseur = Decimal(nb_devs + 1)
            else:
                total_matiere = sum(status["devoirs"])
                diviseur = Decimal(nb_devs)
            status["moyenne_generale"] = (total_matiere / diviseur).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            status["moyenne_generale"] = status["moyenne_interros"]

        # Cumul pour la moyenne trimestrielle
        if status["moyenne_generale"] > 0:
            total_points_trimestre += status["moyenne_generale"] * Decimal(str(status["coefficient"]))
            total_coefficients_trimestre += Decimal(str(status["coefficient"]))
            matieres_finales[m] = status # On l'ajoute à l'affichage

    # Moyenne Trimestrielle Finale
    moyenne_trimestrielle = (total_points_trimestre / total_coefficients_trimestre).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if total_coefficients_trimestre > 0 else Decimal('0.00')

    # 8. CALCUL DU RANG (Basé sur la classe et la série)
    eleves_classe = Eleve.objects.filter(classe=eleve.classe, annee_academique=annee)
    if serie_eleve:
        eleves_classe = eleves_classe.filter(serie=eleve.serie)

    moyennes_camarades = []
    for camarade in eleves_classe:
        if camarade.id == eleve.id:
            moyennes_camarades.append(moyenne_trimestrielle)
        else:
            # On récupère la moyenne stockée sur la première note du camarade pour ce trimestre
            n_c = Note.objects.filter(eleve=camarade, trimestre=trimestre_val, annee_academique=annee).first()
            moy_c = Decimal(str(n_c.moyenne_trimestrielle)) if n_c and n_c.moyenne_trimestrielle else Decimal('0.00')
            moyennes_camarades.append(moy_c)

    moyennes_camarades.sort(reverse=True)
    try:
        rang = moyennes_camarades.index(moyenne_trimestrielle) + 1
    except ValueError:
        rang = "-"

    # 9. INFOS ÉTABLISSEMENT
    appreciation = "Insuffisant"
    if moyenne_trimestrielle >= 16: appreciation = "Très Bien"
    elif moyenne_trimestrielle >= 14: appreciation = "Bien"
    elif moyenne_trimestrielle >= 12: appreciation = "Assez Bien"
    elif moyenne_trimestrielle >= 10: appreciation = "Passable"

    config = Login.objects.first()

    context = {
        "eleve": eleve,
        "matieres_status": matieres_finales, # Utilise la liste filtrée
        "moyenne_trimestrielle": moyenne_trimestrielle,
        "rang": rang,
        "total_classe": len(moyennes_camarades),
        "trimestre": trimestre_val,
        "annee": annee,
        "appreciation": appreciation,
        "school_name": config.school_name if config else "ACADYNOTE",
        "logo": config.profile_image if config else None,
        "serie": serie_eleve,
    }

    return render(request, "suivre_eleve_resultat.html", context)

from django.shortcuts import render, get_object_or_404
from myapp.models import Enseignant, Horaire

def mon_emploi_du_temps(request, enseignant_id):
    enseignant = get_object_or_404(Enseignant, id=enseignant_id)

    # Récupérer les horaires
    horaires = Horaire.objects.filter(enseignant=enseignant).order_by('classe', 'jour', 'heure_debut')
    classes_distinctes = horaires.values_list('classe', flat=True).distinct()
    jours = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi']

    return render(request, 'enseignant/mon_emploi_du_temps.html', {
        'enseignant': enseignant,
        'horaires': horaires,
        'classes_distinctes': classes_distinctes,
        'jours': jours
    })

from django.utils import timezone
from django.db import transaction
from .models import Eleve, Horaire, Presence
from datetime import datetime
import math

def calculer_distance_gps(lat1, lon1, lat2, lon2):
    """
    Calcule la distance en kilomètres entre deux points GPS
    """
    # Rayon moyen de la Terre en km
    R = 6371.0

    # Conversion des degrés en radians
    radians_lat1 = math.radians(lat1)
    radians_lon1 = math.radians(lon1)
    radians_lat2 = math.radians(lat2)
    radians_lon2 = math.radians(lon2)

    # Différence de coordonnées
    dlon = radians_lon2 - radians_lon1
    dlat = radians_lat2 - radians_lat1

    # Formule de Haversine
    a = math.sin(dlat / 2)**2 + math.cos(radians_lat1) * math.cos(radians_lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def marquer_presence(request, classe_nom, horaire_id):
    horaire = get_object_or_404(Horaire, id=horaire_id)
    
    # --- 1. DÉCOUPAGE INTELLIGENT DE LA CLASSE (Lycée vs Collège) ---
    # Si classe_nom = "2nde D", on sépare "2nde" et "D"
    parts = classe_nom.split(' ')
    nom_classe_pur = parts[0]
    serie_nom = parts[1] if len(parts) > 1 else None

    if serie_nom:
        # Filtrage Lycée : on cherche la classe ET la série
        eleves = Eleve.objects.filter(
            classe=nom_classe_pur,
            serie=serie_nom,
            annee_academique=horaire.annee_academique
        ).order_by('nom', 'prenoms')
    else:
        # Filtrage Collège : on cherche juste la classe
        eleves = Eleve.objects.filter(
            classe=classe_nom,
            annee_academique=horaire.annee_academique
        ).order_by('nom', 'prenoms')

    if request.method == 'POST':
        soumission_date = timezone.now()

        # --- 2. RÉCUPÉRATION DE LA LOCALISATION ÉCOLE (Table Login) ---
        try:
            infos_ecole = Login.objects.first() # Récupère le premier compte (l'admin/école)
            if not infos_ecole or not infos_ecole.latitude:
                raise ValueError("Coordonnées de l'école non configurées.")
            
            ECOLE_LAT = float(infos_ecole.latitude)
            ECOLE_LNG = float(infos_ecole.longitude)
        except Exception as e:
            messages.error(request, f"❌ Erreur de configuration : {str(e)}")
            return redirect(request.path)

        # Récupération de la position envoyée par le navigateur
        user_lat = request.POST.get('latitude')
        user_lng = request.POST.get('longitude')
        PÉRIMÈTRE_AUTORISÉ = 0.2  # 200 mètres

        if not user_lat or not user_lng:
            messages.error(request, "⚠️ Géolocalisation requise pour valider l'appel.")
            return redirect(request.path)

        try:
            # Remplacer par ta fonction réelle de calcul
            distance = calculer_distance_gps(ECOLE_LAT, ECOLE_LNG, float(user_lat), float(user_lng))
            
            if distance > PÉRIMÈTRE_AUTORISÉ:
                messages.error(request, f"❌ Trop loin ! Vous êtes à {round(distance * 1000)}m de l'école.")
                return redirect(request.path)
        except (ValueError, TypeError):
            messages.error(request, "❌ Données GPS invalides.")
            return redirect(request.path)

        # --- 3. CALCUL DE LA DURÉE ET ENREGISTREMENT ATOMIQUE ---
        duree = (datetime.combine(datetime.today(), horaire.heure_fin) -
                 datetime.combine(datetime.today(), horaire.heure_debut)).total_seconds() / 3600

        try:
            with transaction.atomic():
                # A. Enregistrement session Enseignant (Pointage de l'heure)
                Presence.objects.update_or_create(
                    eleve=None,
                    horaire=horaire,
                    classe=classe_nom,
                    date__date=soumission_date.date(),
                    defaults={
                        'enseignant': horaire.enseignant,
                        'date': soumission_date,
                        'etat': 'present',
                        'duree': duree,
                        'latitude': user_lat,
                        'longitude': user_lng
                    }
                )

                # B. Enregistrement individuel des élèves
                for eleve in eleves:
                    est_absent = request.POST.get(f'absent_{eleve.id}')
                    motif = request.POST.get(f'motif_{eleve.id}', '')

                    Presence.objects.update_or_create(
                        eleve=eleve,
                        horaire=horaire,
                        date__date=soumission_date.date(),
                        defaults={
                            'enseignant': horaire.enseignant,
                            'classe': classe_nom,
                            'date': soumission_date,
                            'etat': 'absent' if est_absent else 'present',
                            'duree': duree,
                            'motif': motif if est_absent else None,
                            'latitude': user_lat,
                            'longitude': user_lng
                        }
                    )

            messages.success(request, f"✅ Appel validé ! Distance : {round(distance * 1000)}m.")
            return redirect('marquer_presence', classe_nom=classe_nom, horaire_id=horaire.id)
        except Exception as e:
            messages.error(request, f"❌ Erreur lors de l'enregistrement : {str(e)}")

    return render(request, 'enseignant/marquer_presence.html', {
        'eleves': eleves,
        'classe_nom': classe_nom,
        'horaire': horaire,
        'now': timezone.now()
    })

def heures_mensuelles(request):
    # Vérifier que l'enseignant est connecté
    enseignant_id = request.session.get('enseignant_id')
    if not enseignant_id:
        return redirect('enseignant_login')

    enseignant = get_object_or_404(Enseignant, id=enseignant_id)

    # Récupérer toutes les présences pour le calcul des heures par mois
    presences = Presence.objects.filter(
        enseignant=enseignant,
        etat='present',
        horaire__isnull=False
    ).select_related('horaire').order_by('date', 'horaire')

    # Calcul des heures par mois
    heures_par_mois = {}
    vus = set()  # éviter de compter plusieurs fois le même horaire le même jour

    for p in presences:
        key = (p.date.date(), p.horaire.id)
        if key in vus:
            continue
        vus.add(key)

        # Calcul de la durée du cours en heures
        duree = (datetime.combine(datetime.today(), p.horaire.heure_fin) -
                 datetime.combine(datetime.today(), p.horaire.heure_debut))
        heures = duree.total_seconds() / 3600

        mois = p.date.month
        heures_par_mois[mois] = heures_par_mois.get(mois, 0) + heures

    # Transformer les mois en noms et arrondir
    heures_par_mois_noms = {calendar.month_name[m]: round(h, 2) for m, h in heures_par_mois.items()}

    # Récupérer les soumissions uniques par classe pour l'historique
    presences_recentes = Presence.objects.filter(
        enseignant=enseignant,
        eleve__isnull=True  # uniquement l'entrée de classe, pas par élève
    ).order_by('-date')[:10]

    return render(request, 'enseignant/heures_mensuelles.html', {
        'enseignant': enseignant,
        'heures_par_mois': heures_par_mois_noms,
        'presences_recentes': presences_recentes
    })

from django.core.mail import send_mail
from django.contrib import messages

def liste_absents(request):
    date_filter = request.GET.get('date')
    presences = Presence.objects.filter(etat='absent').select_related('horaire', 'enseignant', 'eleve')

    if date_filter:
        try:
            date_obj = datetime.strptime(date_filter, '%Y-%m-%d').date()
            presences = presences.filter(date__date=date_obj)
        except ValueError:
            date_obj = None

    # --- NOUVEAU : LOGIQUE D'ENVOI DE NOTIFICATION ---
    if 'notifier' in request.GET:
        envoyes = 0
        for p in presences:
            if p.eleve.email_parent: # On vérifie si l'email existe
                send_mail(
                    f"Alerte Absence : {p.eleve.nom} {p.eleve.prenoms}",
                    f"Bonjour,\n\nNous vous informons que votre enfant était absent au cours de {p.horaire.matiere} le {p.date.strftime('%d/%m/%Y')}.\n\nCordialement,\nLa Direction.",
                    'ne-pas-repondre@acadynote.bj',
                    [p.eleve.email_parent],
                    fail_silently=True,
                )
                envoyes += 1
        messages.success(request, f"Notifications envoyées à {envoyes} parents.")

    # Grouper par classe
    classes = {}
    for p in presences:
        classe = p.classe
        if classe not in classes:
            classes[classe] = []
        classes[classe].append(p)

    return render(request, 'liste_absents.html', {
        'classes': classes,
        'date_filter': date_filter
    })

from datetime import datetime, timedelta
import calendar
from .models import Presence

def heures_mensuelles_recap(request):
    mois_filter = request.GET.get("mois")

    presences = (
        Presence.objects
        .select_related("horaire__enseignant")
        .filter(horaire__isnull=False)
    )

    if mois_filter:
        presences = presences.filter(date__month=int(mois_filter))

    heures_par_enseignant = {}
    cours_deja_comptes = set()  # (jour, horaire_id)

    for p in presences:
        jour = p.date.date()
        key = (jour, p.horaire.id)

        if key in cours_deja_comptes:
            continue
        cours_deja_comptes.add(key)

        h = p.horaire
        enseignant = h.enseignant

        dt_debut = datetime.combine(jour, h.heure_debut)
        dt_fin = datetime.combine(jour, h.heure_fin)
        if dt_fin < dt_debut:
            dt_fin += timedelta(days=1)

        duree = (dt_fin - dt_debut).total_seconds() / 3600

        if enseignant.id not in heures_par_enseignant:
            heures_par_enseignant[enseignant.id] = {
                "enseignant": enseignant,
                "total_heures": 0,
                "classes": set(),   # 👈 on regroupe ici
            }

        heures_par_enseignant[enseignant.id]["total_heures"] += duree
        heures_par_enseignant[enseignant.id]["classes"].add(h.classe)

    # transformer les sets en listes (pour le template)
    for data in heures_par_enseignant.values():
        data["classes"] = ", ".join(sorted(data["classes"]))

    mois_options = [
        {"num": f"{m:02d}", "nom": calendar.month_name[m]}
        for m in range(1, 13)
    ]

    return render(request, "heures_mensuelles.html", {
        "heures_par_enseignant": heures_par_enseignant,
        "mois_filter": mois_filter,
        "mois_options": mois_options,
    })

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.db.models import Avg
from django.template.loader import get_template, render_to_string
from xhtml2pdf import pisa
from .models import Eleve, Note
import os

def resultats_annuels(request):
    # Récupération des listes pour les menus déroulants
    classes = Eleve.objects.values_list('classe', flat=True).distinct().order_by('classe')
    annees = Eleve.objects.values_list('annee_academique', flat=True).distinct().order_by('-annee_academique')# On récupère les séries existantes en excluant les valeurs vides ou None
    series = Eleve.objects.exclude(
        Q(serie__isnull=True) | Q(serie="") | Q(serie__iexact="None")
    ).values_list('serie', flat=True).distinct().order_by('serie')
    classe = request.GET.get('classe')
    annee = request.GET.get('annee')
    serie = request.GET.get('serie')

    resultats = []
    stats = {}

    if classe and annee:
        # Filtrage de base
        eleves = Eleve.objects.filter(classe=classe, annee_academique=annee)
        
        # Filtrage par série si une série est choisie
        if serie and serie != "" and serie != "None":
            eleves = eleves.filter(serie=serie)

        for eleve in eleves:
            t1 = Note.objects.filter(eleve=eleve, trimestre=1).aggregate(m=Avg('moyenne_trimestrielle'))['m'] or 0
            t2 = Note.objects.filter(eleve=eleve, trimestre=2).aggregate(m=Avg('moyenne_trimestrielle'))['m'] or 0
            t3 = Note.objects.filter(eleve=eleve, trimestre=3).aggregate(m=Avg('moyenne_trimestrielle'))['m'] or 0

            moyenne_annuelle = round((t1 + t2 + t3) / 3, 2)

            resultats.append({
                'eleve': eleve,
                'sexe': eleve.sexe,
                't1': round(t1, 2),
                't2': round(t2, 2),
                't3': round(t3, 2),
                'moyenne_annuelle': moyenne_annuelle,
                'decision': "Passe" if moyenne_annuelle >= 10 else "Redouble"
            })

        # Classement
        resultats.sort(key=lambda x: x['moyenne_annuelle'], reverse=True)
        for i, r in enumerate(resultats, start=1):
            r['rang'] = i

        total = len(resultats)
        if total > 0:
            admis = [r for r in resultats if r['moyenne_annuelle'] >= 10]
            redoublants = [r for r in resultats if r['moyenne_annuelle'] < 10]
            garcons = [r for r in resultats if r['sexe'] == 'M']
            filles = [r for r in resultats if r['sexe'] == 'F']

            stats = {
                'total': total,
                'admis': len(admis),
                'redoublants': len(redoublants),
                'taux_reussite': round((len(admis) / total) * 100, 2),
                'garcons_total': len(garcons),
                'garcons_admis': len([g for g in garcons if g['moyenne_annuelle'] >= 10]),
                'garcons_redoublants': len([g for g in garcons if g['moyenne_annuelle'] < 10]),
                'filles_total': len(filles),
                'filles_admises': len([f for f in filles if f['moyenne_annuelle'] >= 10]),
                'filles_redoublantes': len([f for f in filles if f['moyenne_annuelle'] < 10]),
                'premier': resultats[0],
                'dernier': resultats[-1],
            }

        # Génération PDF
        if request.GET.get('pdf') == "1":
            template = get_template('resultats_annuels.html')
            html = template.render({
                'classe': classe,
                'annee': annee,
                'serie': serie,
                'resultats': resultats,
                'stats': stats,
                'pdf': True
            })
            nom_pdf = f"Resultats_{classe}_{annee}.pdf".replace(" ", "_")
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{nom_pdf}"'
            pisa.CreatePDF(html, dest=response)
            return response

    return render(request, 'resultats_annuels.html', {
        'classes': classes,
        'annees': annees,
        'series': series,
        'classe': classe,
        'annee': annee,
        'serie': serie,
        'resultats': resultats,
        'stats': stats,
        'pdf': False
    })

def liste_attente_enseignants(request):
    # On récupère uniquement ceux qui ne sont pas encore validés
    enseignants = Enseignant.objects.filter(est_approuve=False)
    
    return render(request, 'liste_attente.html', {
        'enseignants_en_attente': enseignants
    })
def valider_enseignant(request, pk):
    enseignant = get_object_or_404(Enseignant, pk=pk)
    enseignant.est_approuve = True
    enseignant.save()

    # Notification par mail
    send_mail(
        'Validation de votre compte Acadynote',
        f'Félicitations {enseignant.nom}, votre compte a été validé. Vous pouvez maintenant vous connecter.',
        settings.DEFAULT_FROM_EMAIL,
        [enseignant.email],
        fail_silently=False,
    )
    
    messages.success(request, f"Le compte de {enseignant.nom} a été validé avec succès.")
    return redirect('liste_attente_enseignants')

def refuser_enseignant(request, pk):
    enseignant = get_object_or_404(Enseignant, pk=pk)
    email_prof = enseignant.email
    nom_prof = enseignant.nom
    
    # On supprime l'enregistrement pour qu'il puisse éventuellement se réinscrire proprement
    enseignant.delete()

    # Mail de refus
    send_mail(
        'Mise à jour de votre inscription - Acadynote',
        f'Bonjour {nom_prof}, votre demande d\'adhésion a été refusée par l\'établissement.',
        settings.DEFAULT_FROM_EMAIL,
        [email_prof],
        fail_silently=False,
    )

    messages.warning(request, f"La demande de {nom_prof} a été refusée et le compte supprimé.")
    return redirect('liste_attente_enseignants')

def rapport_heures_prof(request):
    # 1. Récupérer tous les enseignants pour le menu déroulant
    profs = Enseignant.objects.all()
    
    # 2. On ne prend que les lignes où eleve est NULL (la séance du prof)
    rapports = Presence.objects.filter(eleve__isnull=True).order_by('-date')

    # 3. Récupération des filtres depuis l'URL
    prof_id = request.GET.get('enseignant')
    mois_select = request.GET.get('mois')

    if prof_id:
        rapports = rapports.filter(enseignant_id=prof_id)
    
    if mois_select:
        # mois_select est au format "YYYY-MM"
        year, month = mois_select.split('-')
        rapports = rapports.filter(date__year=year, date__month=month)

    # 4. Calcul du total des heures
    total_heures = rapports.aggregate(Sum('duree'))['duree__sum'] or 0

    return render(request, 'rapport_heures.html', {
        'rapports': rapports,
        'profs': profs,
        'total_heures': total_heures
    })

import base64
import random
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.files.base import ContentFile
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import Enseignant , ProfesseurPrincipal

def modifier_profil(request):
    # Sécurité : vérifier si l'enseignant est connecté
    enseignant_id = request.session.get('enseignant_id')
    if not enseignant_id:
        return redirect('enseignant_login')

    enseignant = get_object_or_404(Enseignant, id=enseignant_id)
    old_email = enseignant.email

    # Configuration des données statiques
    toutes_matieres = ["Communication-Ecrite", "Lecture", "Anglais", "Mathématiques", "PCT", "SVT", "Histoire-Géographie", "EPS", "Informatique", "Espagnol", "Allemand", "Philosophie"]
    premier_cycle = ["6ème", "5ème", "4ème", "3ème"]
    second_cycle_data = {
        "2nde": ["A", "C", "D"],
        "1ère": ["A1", "A2", "B", "C", "D", "G1", "G2"],
        "Tle": ["A1", "A2", "B", "C", "D", "G1", "G2"]
    }

    if request.method == 'POST':
        # --- INFOS DE BASE ---
        enseignant.nom = request.POST.get('nom')
        enseignant.prenoms = request.POST.get('prenoms')
        new_email = request.POST.get('email', '').strip()

        # --- LOGIQUE DES MATIÈRES ---
        matieres_choisies = request.POST.getlist('matieres')
        enseignant.matiere = ",".join(matieres_choisies)

        # --- GESTION DE LA SIGNATURE (BASE64) ---
        signature_data = request.POST.get('signature_data')
        if signature_data and signature_data.startswith('data:image/png;base64,'):
            try:
                # Extraction des données binaires
                format, imgstr = signature_data.split(';base64,')
                ext = format.split('/')[-1]
                file_name = f"signature_{enseignant.id}_{timezone.now().strftime('%Y%m%d%H%M%S')}.{ext}"
                
                # Conversion en fichier Django
                data = ContentFile(base64.b64decode(imgstr), name=file_name)
                enseignant.signature = data
            except Exception as e:
                print(f"Erreur signature: {e}")

        # --- GESTION DU MOT DE PASSE ---
        password = request.POST.get('password')
        if password:
            if len(password) >= 8:
                # Note : Utilisez make_password(password) ici pour la sécurité
                enseignant.password = password 
            else:
                messages.error(request, "Mot de passe trop court.")
                return redirect('modifier_profil')

        # --- GESTION DU CHANGEMENT D'EMAIL ---
        if new_email != old_email:
            otp = str(random.randint(100000, 999999))
            enseignant.otp_code = otp
            enseignant.otp_timestamp = timezone.now()
            enseignant.is_verified = False
            enseignant.email = new_email
            
            try:
                send_mail(
                    'Vérification Acadynote',
                    f'Votre code de vérification : {otp}',
                    settings.DEFAULT_FROM_EMAIL,
                    [new_email]
                )
                enseignant.save()
                return redirect('verifier_otp_mod')
            except:
                messages.error(request, "Erreur lors de l'envoi du mail.")
                return redirect('modifier_profil')

        # Sauvegarde finale
        enseignant.save()
        messages.success(request, "Votre profil a été mis à jour avec succès !")
        return redirect('modifier_profil')

    # Données pour l'affichage (GET)
    mes_matieres_liste = enseignant.matiere.split(',') if enseignant.matiere else []
    mes_classes_completes = enseignant.classes.split(',') if enseignant.classes else []
    base_classes = [c.split(' ')[0] for c in mes_classes_completes]

    context = {
        'enseignant': enseignant,
        'toutes_matieres': toutes_matieres,
        'premier_cycle': premier_cycle,
        'second_cycle_data': second_cycle_data,
        'mes_matieres': mes_matieres_liste,
        'mes_classes': mes_classes_completes,
        'base_classes': base_classes,
    }
    return render(request, 'enseignant/modifier_profil.html', context)


def gestion_professeur_principal(request):
    enseignants = Enseignant.objects.all().order_by('nom')
    classes = ["6ème", "5ème", "4ème", "3ème", "2nde", "1ère", "Tle"]
    series_par_classe = {
        "2nde": ["A","B", "C", "D"],
        "1ère": ["A1", "A2", "B", "C", "D"],
        "Tle": ["A1", "A2", "B", "C", "D"]
    }

    if request.method == "POST":
        enseignant_id = request.POST.get('enseignant')
        classe_nom = request.POST.get('classe')
        serie_nom = request.POST.get('serie')
        annee = request.POST.get('annee_academique')

        enseignant = get_object_or_404(Enseignant, id=enseignant_id)
        
        ProfesseurPrincipal.objects.update_or_create(
            classe=classe_nom,
            serie=serie_nom if serie_nom else None,
            annee_academique=annee,
            defaults={'enseignant': enseignant}
        )
        
        # Utilise le nom de l'URL défini dans urls.py
        return redirect('gestion_pp') 

    assignations = ProfesseurPrincipal.objects.all().select_related('enseignant').order_by('classe')
    
    context = {
        'enseignants': enseignants,
        'classes': classes,
        'series_par_classe': series_par_classe,
        'assignations': assignations,
        'annee_academique': "2025-2026", # Pour ton formulaire
    }
    # VERIFIE BIEN CE CHEMIN :
    return render(request, 'gestion_pp.html', context)

def supprimer_professeur_principal(request, pk):
    assignation = get_object_or_404(ProfesseurPrincipal, pk=pk)
    nom = assignation.enseignant.nom
    classe = assignation.classe
    assignation.delete()
    
    
    return redirect('gestion_pp')