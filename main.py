import sqlite3
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import httpx

TMDB_CLE_API = "f1bd896f7ce8e2364345ee500ed5611b"
TMDB_URL_BASE = "https://api.themoviedb.org/3"
TMDB_URL_IMAGE = "https://image.tmdb.org/t/p"
FICHIER_BDD = "izmar.db"

app = FastAPI(title="IZMAR API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def initialiser_base_de_donnees():
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
    connexion = sqlite3.connect(FICHIER_BDD)
    curseur = connexion.cursor()
    curseur.execute(
        "INSERT INTO recherches (mode, critere, films_trouves) VALUES (?, ?, ?)",
        (mode, critere, json.dumps(films_trouves))
    )
    connexion.commit()
    connexion.close()


def formater_film(film):
    chemin_affiche = film.get("poster_path")
    if chemin_affiche:
        url_affiche = f"{TMDB_URL_IMAGE}/w500{chemin_affiche}"
    else:
        url_affiche = None
    return {
        "titre": film.get("title", "Titre inconnu"),
        "annee": film.get("release_date", "")[:4],
        "synopsis": film.get("overview", "Pas de synopsis."),
        "affiche": url_affiche,
        "note": round(film.get("vote_average", 0), 1),
    }


@app.get("/recommander")
async def recommander(
    mode: str,
    genre_id: Optional[int] = None,
    duree_max: Optional[int] = None,
):
    films_formates = []

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
        async with httpx.AsyncClient() as client:
            reponse = await client.get(url, params=parametres)
        donnees = reponse.json()
        liste_films = donnees.get("results", [])
        for film in liste_films[:3]:
            films_formates.append(formater_film(film))
        titres = [f["titre"] for f in films_formates]
        sauvegarder_recherche("theme", str(genre_id), titres)

    return {"films": films_formates}
