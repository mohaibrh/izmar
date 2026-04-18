import sqlite3
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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


@app.get("/health")
async def health():
    return {"status": "ok"}
