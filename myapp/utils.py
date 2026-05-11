# myapp/utils.py

def get_coefficient(classe, serie, matiere):
    """
    Unique source de vérité pour les coefficients du système Acadynote.
    Gère le Collège (Option) et le Lycée (Séries A1, A2, B, C, D).
    """
    c = str(classe or "").lower()
    s = str(serie or "").upper()
    m = str(matiere or "").lower()

    # --- 0. EXCEPTIONS GÉNÉRALES (Toutes classes confondues) ---
    # EPS, Conduite et Informatique sont toujours coefficient 1
    if any(x in m for x in ["eps", "conduite", "informatique"]):
        return 1

    # --- 1. COLLÈGE (6ème, 5ème, 4ème, 3ème) ---
    if any(x in c for x in ["6", "5", "4", "3"]):
        
        # Cas spécifique PCT (6è/5è = 1, 4è/3è = 2)
        if "pct" in m:
            return 2 if ("4" in c or "3" in c) else 1
            
        # Cas 4ème et 3ème
        if "4" in c or "3" in c:
            if "math" in m: return 3 
            if any(x in m for x in ["franç", "lecture", "comm"]): return 2
            # Option Langue (Espagnol ou Allemand)
            if any(x in m for x in ["svt", "angl", "hist", "espagnol", "allemand"]): 
                return 2
            return 1
            
        # Cas 6ème et 5ème (Base 1 pour presque tout)
        if any(x in m for x in ["math", "franç", "lecture", "comm", "svt", "angl", "hist"]):
            return 2 
        return 1

    # --- 2. LYCÉE : SECONDE (2de) ---
    if "2nd" in c or "2de" in c:
        if s in ["C", "D"]:
            if any(sci in m for sci in ["math", "pct", "svt"]): return 3
            return 2
        elif s == "B":
            if any(x in m for x in ["écon", "angl", "math"]): return 3
            return 2
        elif "A" in s:
            if any(x in m for x in ["franç", "angl", "hist", "espagnol", "allemand"]): return 3
            return 2
        return 2

    # --- 3. LYCÉE : 1ère & TERMINALE ---
    
    # Séries Scientifiques (C, D)
    if s == "C":
        if "pct" in m: return 6
        if "math" in m: return 5
        if "svt" in m: return 2
        return 2
    
    elif s == "D":
        if "svt" in m: return 5
        if "math" in m or "pct" in m: return 4
        return 2
        
    # Série Économique (B)
    elif s == "B":
        if any(x in m for x in ["écon", "math", "hist"]): return 4
        if "franç" in m: return 3
        # La LV2 en Série B
        if any(x in m for x in ["espagnol", "allemand"]): return 3
        return 2
        
    # Séries Littéraires (A1 & A2)
    elif "A" in s:
        # Matières Dominantes
        if any(x in m for x in ["franç", "philo", "hist"]):
            return 5 if s == "A1" else 4
        
        # Langues (LV1 Anglais et LV2 Espagnol/Allemand)
        if any(x in m for x in ["angl", "espagnol", "allemand", "langue"]):
            return 4 if s == "A1" else 3
            
        return 2

    # --- 4. SÉCURITÉ FINALE ---
    return 1

def get_appreciation(moyenne):
    if moyenne is None: return ""
    if moyenne < 7: return "Médiocre"
    elif moyenne < 8.5: return "Faible"
    elif moyenne < 10: return "Insuffisant"
    elif moyenne < 12: return "Passable"
    elif moyenne < 14: return "Assez-Bien"
    elif moyenne < 16: return "Bien"
    elif moyenne < 18: return "Très-Bien"
    else: return "Excellent"
