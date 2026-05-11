from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class Login(models.Model):
    username = models.CharField(max_length=100)
    school_name = models.CharField(max_length=100)
    password = models.CharField(max_length=100)
    email= models.CharField(max_length=100)
    numero = models.CharField(max_length=100)
    name = models.CharField(max_length=100,null=True)
    profile_image = models.ImageField(upload_to="profile_images/", blank=True, null=True)
    coin_droit = models.ImageField(upload_to="cartes/recto/", blank=True, null=True)
    fond_verso = models.ImageField(upload_to="cartes/verso/", blank=True, null=True)
    latitude = models.DecimalField(
        max_digits=22, 
        decimal_places=16, 
        default=6.505650347028947
    )
    longitude = models.DecimalField(
        max_digits=22, 
        decimal_places=16, 
        default=2.5984622632404064
    )


class Enseignant(models.Model):
    nom = models.CharField(max_length=150)
    prenoms = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    matiere = models.CharField(max_length=255, blank=True)
    signature = models.ImageField(upload_to='signatures/', null=True, blank=True)
    classes = models.CharField(max_length=200)  
    series = models.CharField(max_length=100, blank=True, null=True)
    annee_academique = models.CharField(max_length=20)
    est_approuve = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    otp_code = models.CharField(max_length=6, null=True, blank=True)
    otp_timestamp = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.nom} {self.prenoms}"
    
class ProfesseurPrincipal(models.Model):
    enseignant = models.ForeignKey(Enseignant, on_delete=models.CASCADE)
    classe = models.CharField(max_length=50)  # Ex: "1ère"
    serie = models.CharField(max_length=50, blank=True, null=True)  # Ex: "D"
    annee_academique = models.CharField(max_length=20)

    class Meta:
        # Empêche d'avoir deux profs pour la même "1ère D"
        unique_together = ('classe', 'serie', 'annee_academique')

    def __str__(self):
        return f"{self.enseignant.nom} - {self.classe} {self.serie if self.serie else ''}"
       
from django.db import models

class Eleve(models.Model):
    # --- CHOIX ---
    NIVEAU_CHOICES = [
        ('6ème', '6ème'), ('5ème', '5ème'), ('4ème', '4ème'), ('3ème', '3ème'),
        ('2nde', 'Seconde'), ('1ère', 'Première'), ('Tle', 'Terminale'),
    ]
    SERIE_CHOICES = [
        ('Général', 'Général (Collège)'),
        ('A1', 'Série A1'), ('A2', 'Série A2'), 
        ('B', 'Série B'), ('C', 'Série C'), ('D', 'Série D'),
    ]
    SEXE_CHOICES = [('M', 'Masculin'), ('F', 'Féminin')]
    
    LANGUE_CHOICES = [
        ('Anglais', 'Anglais'),
        ('Espagnol', 'Espagnol'),
        ('Allemand', 'Allemand'),
    ]

    # --- IDENTITÉ ---
    matricule = models.CharField(max_length=50, unique=True, null=True, blank=True)
    nom = models.CharField(max_length=100)
    prenoms = models.CharField(max_length=100)
    sexe = models.CharField(max_length=10, choices=SEXE_CHOICES)
    date_naissance = models.DateField(null=True, blank=True)
    lieu_naissance = models.CharField(max_length=100, null=True, blank=True)
    nationalite = models.CharField(max_length=50, default="Béninoise")
    profile_eleve = models.ImageField(upload_to="profile_images/", null=True, blank=True)

    # --- SCOLARITÉ ---
    annee_academique = models.CharField(max_length=50, help_text="Ex: 2023-2024")
    classe = models.CharField(max_length=50, choices=NIVEAU_CHOICES)
    serie = models.CharField(max_length=10, choices=SERIE_CHOICES, null=True, blank=True)

    # --- GESTION DES LANGUES (Le cœur de votre besoin) ---
    
    # 1. Pour le Premier Cycle (4ème et 3ème)
    # L'anglais est automatique, ce champ définit la matière de spécialité choisie.
    langue_specialite = models.CharField(
        max_length=20, 
        choices=LANGUE_CHOICES[1:], # Uniquement Espagnol ou Allemand
        blank=True, 
        null=True,
        verbose_name="Langue de Spécialité (Collège)",
        help_text="À remplir uniquement pour les élèves de 4ème et 3ème."
    )

    # 2. Pour le Second Cycle (Séries A1, A2, B)
    # Permet de définir quelle langue est LV1 (Coef fort) et laquelle est LV2
    lv1 = models.CharField(
        max_length=20, 
        choices=LANGUE_CHOICES, 
        default='Anglais',
        verbose_name="Langue Vivante 1 (Lycée)"
    )
    lv2 = models.CharField(
        max_length=20, 
        choices=LANGUE_CHOICES, 
        blank=True, 
        null=True,
        verbose_name="Langue Vivante 2 (Lycée)"
    )

    # --- CONTACTS ---
    telephone_parent = models.CharField(max_length=15, blank=True, null=True)
    email_parent = models.EmailField(blank=True, null=True)
    date_enregistrement = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Élève"
        verbose_name_plural = "Élèves"
        ordering = ['nom', 'prenoms']

    def __str__(self):
        return f"{self.nom} {self.prenoms} ({self.classe} {self.serie})"

    def __str__(self):
        return f"{self.nom} {self.prenoms}"
    def calculer_moyenne(self, trimestre,annee_academique):
        """
        Calcule la moyenne de l'élève pour un trimestre donné.
        """
        # Récupérer toutes les notes de l'élève pour le trimestre
        notes = Note.objects.filter(eleve=self, trimestre=trimestre,annee_academique=annee_academique)
        
        # Calculer la moyenne pondérée
        total_notes_ponderees = 0
        total_coefficients = 0
        
        for note in notes:
            coefficient = note.coefficient# Récupère le coefficient de la note
            total_notes_ponderees += note.valeur * coefficient
            total_coefficients += coefficient
        
        # Calcul de la moyenne trimestrielle
        if total_coefficients > 0:
            return total_notes_ponderees / total_coefficients
        return 0

from django.db import models
from django.utils import timezone

class Note(models.Model):
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE)
    matiere = models.CharField(max_length=100)
    trimestre = models.IntegerField()
    valeur = models.FloatField()
    type_note = models.CharField(max_length=20)
    moyenne_interrogations = models.FloatField(null=True, blank=True)
    moyenne_devoirs = models.FloatField(null=True, blank=True)
    moyenne_generale = models.FloatField(null=True, blank=True)
    moyenne_trimestrielle = models.FloatField(null=True, blank=True, default=0.0)
    rang = models.IntegerField(null=True, blank=True)
    date_ajout = models.DateTimeField(default=timezone.now)
    annee_academique = models.CharField(max_length=10, blank=True, null=True)

    def __str__(self):
        return f"{self.eleve} - {self.matiere} - {self.trimestre}"

    def save(self, *args, **kwargs):
        if not self.annee_academique and self.eleve:
            self.annee_academique = self.eleve.annee_academique
        super().save(*args, **kwargs)


class Horaire(models.Model):
    classe = models.CharField(max_length=20)
    jour = models.CharField(max_length=10)  # Lundi, Mardi...
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    matiere = models.CharField(max_length=50)
    enseignant = models.ForeignKey(Enseignant, on_delete=models.CASCADE)
    annee_academique = models.CharField(max_length=20)


class Presence(models.Model):
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, null=True,  blank=True)
    enseignant = models.ForeignKey(Enseignant, on_delete=models.CASCADE)
    classe = models.CharField(max_length=100)
    date = models.DateTimeField(auto_now_add=True)  # date + heure de soumission
    etat = models.CharField(max_length=20, choices=[('present', 'Présent'), ('absent', 'Absent')])
    horaire = models.ForeignKey(Horaire, on_delete=models.SET_NULL, null=True, blank=True)
    motif = models.CharField(max_length=255, blank=True, null=True)
    duree = models.FloatField(blank=True, null=True)  # durée en heures
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
