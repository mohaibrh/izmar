# Mon Backend en FastAPI
# C'est lui qui fait le pont entre le navigateur de l'utilisateur et l'API des films (TMDB).
# C'est aussi lui qui sauvegarde l'historique dans ma base de données.

import sqlite3
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import httpx # J'utilise httpx parce qu'il gère super bien les requêtes asynchrones


# --- MA CONFIGURATION ---
TMDB_CLE_API = "f1bd896f7ce8e2364345ee500ed5611b" # C'est mieux de la garder ici côté serveur que dans le HTML
TMDB_URL_BASE = "https://api.themoviedb.org/3"
TMDB_URL_IMAGE = "https://image.tmdb.org/t/p"
FICHIER_BDD = "izmar.db"


app = FastAPI(title="IZMAR API", version="1.0.0")

# Le fameux CORS ! Obligatoire, sinon le navigateur bloque les requêtes 
# parce que mon frontend (port 8080) essaie de parler à mon backend (port 8000).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# MA BASE DE DONNÉES SQLITE
# ============================================================

def initialiser_base_de_donnees():
    """Au lancement, je vérifie que ma table existe.
       J'ai choisi SQLite parce que c'est super léger, ça stocke tout dans un petit fichier."""
    connexion = sqlite3.connect(FICHIER_BDD)
    curseur = connexion.cursor()
    curseur.execute("""
        CREATE TABLE IF NOT EXISTS recherches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mode TEXT,
            critere TEXT,
            films_trouves TEXT
        )
    """)
    connexion.commit()
    connexion.close()


initialiser_base_de_donnees()


def sauvegarder_recherche(mode, critere, films_trouves):
    """Petite fonction pour garder une trace de ce que cherchent les utilisateurs."""
    connexion = sqlite3.connect(FICHIER_BDD)
    curseur = connexion.cursor()
    curseur.execute(
        "INSERT INTO recherches (mode, critere, films_trouves) VALUES (?, ?, ?)",
        (mode, critere, json.dumps(films_trouves))
    )
    connexion.commit()
    connexion.close()


# ============================================================
# MA FONCTION UTILITAIRE
# ============================================================

def formater_film(film):
    """L'API TMDB me renvoie une tonne de trucs inutiles. 
       Je fais le tri ici pour n'envoyer que ce dont mon frontend a vraiment besoin."""
    chemin_affiche = film.get("poster_path")
    if chemin_affiche:
        url_affiche = f"{TMDB_URL_IMAGE}/w500{chemin_affiche}"
    else:
        url_affiche = None
    return {
        "titre": film.get("title", "Titre inconnu"),
        "annee": film.get("release_date", "")[:4], # Je coupe pour ne garder que l'année (les 4 premiers chiffres)
        "synopsis": film.get("overview", "Pas de synopsis."),
        "affiche": url_affiche,
    }


# ============================================================
# MA ROUTE PRINCIPALE : /recommander
# ============================================================

@app.get("/recommander")
async def recommander(
    mode: str,
    genre_id: Optional[int] = None,
    duree_max: Optional[int] = None,
    acteur_nom: Optional[str] = None,
):
    """C'est ici que mon front vient taper. Je récupère les paramètres depuis l'URL."""
    films_formates = []
    acteur_trouve = None

    # --- SI L'UTILISATEUR CHERCHE PAR THÈME ---
    if mode == "theme":
        url = f"{TMDB_URL_BASE}/discover/movie"
        parametres = {
            "api_key": TMDB_CLE_API,
            "language": "fr-FR",
            "with_genres": genre_id,
            "with_runtime.lte": duree_max,
            "sort_by": "popularity.desc",
            "vote_count.gte": 100,
        }
        
        # J'interroge TMDB sans bloquer le reste de mon app
        async with httpx.AsyncClient(timeout=10) as client:
            reponse = await client.get(url, params=parametres)
        donnees = reponse.json()
        liste_films = donnees.get("results", [])

        # Je ne renvoie que le top 3 pour ne pas surcharger l'affichage
        for film in liste_films[:3]:
            films_formates.append(formater_film(film))

        titres = [f["titre"] for f in films_formates]
        sauvegarder_recherche("theme", str(genre_id), titres)

    # --- SI L'UTILISATEUR CHERCHE PAR ACTEUR ---
    elif mode == "acteur":
        url_recherche = f"{TMDB_URL_BASE}/search/person"
        parametres_recherche = {
            "api_key": TMDB_CLE_API,
            "language": "fr-FR",
            "query": acteur_nom,
        }
        
        # Étape 1 : Trouver le vrai nom de l'acteur et son ID sur TMDB
        async with httpx.AsyncClient(timeout=10) as client:
            reponse = await client.get(url_recherche, params=parametres_recherche)
        donnees = reponse.json()
        personnes = donnees.get("results", [])

        if len(personnes) > 0:
            acteur = personnes[0]
            acteur_trouve = acteur["name"]

            acteur_id = acteur["id"]
            
            # Étape 2 : Récupérer les films où il a joué avec son ID
            url_films = f"{TMDB_URL_BASE}/person/{acteur_id}/movie_credits"
            parametres_films = {
                "api_key": TMDB_CLE_API,
                "language": "fr-FR",
            }
            async with httpx.AsyncClient(timeout=10) as client:
                reponse = await client.get(url_films, params=parametres_films)
            donnees_films = reponse.json()
            tous_les_films = donnees_films.get("cast", [])

            # Je trie la liste pour avoir les films les plus connus en premier
            films_tries = sorted(
                tous_les_films,
                key=lambda f: f.get("popularity", 0),
                reverse=True
            )
            for film in films_tries[:3]:
                films_formates.append(formater_film(film))

        titres = [f["titre"] for f in films_formates]
        sauvegarder_recherche("acteur", acteur_nom, titres)

    # FastAPI s'occupe de transformer mon dictionnaire en JSON tout seul
    return {"films": films_formates, "acteur_trouve": acteur_trouve}