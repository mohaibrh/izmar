# --- MA BOÎTE À OUTILS ---
# J'importe les outils dont je vais avoir besoin pour construire mon serveur

import sqlite3 # Mon outil pour créer et lire un fichier de sauvegarde (une base de données)
import json # Un traducteur qui transforme les listes compliquées en texte simple
import random # Mon outil pour faire des choix au hasard (comme lancer un dé)
from fastapi import FastAPI # Le cœur de mon serveur, c'est lui qui écoute les demandes du site web
from fastapi.middleware.cors import CORSMiddleware # Le "vigile" de mon serveur qui autorise mon site à lui parler
from typing import Optional # Pour dire que certaines informations sont facultatives (l'utilisateur n'est pas obligé de les donner)
import httpx # Mon "facteur" virtuel, qui va chercher des informations sur d'autres sites internet (ici, l'API de films)

# --- MES VARIABLES IMPORTANTES (MES RÉGLAGES) ---
# TMDB c'est The Movie Database, le site énorme où je vais piocher les films.
TMDB_CLE_API = "f1bd896f7ce8e2364345ee500ed5611b" # Mon mot de passe secret pour avoir le droit de demander des films à TMDB
TMDB_URL_BASE = "https://api.themoviedb.org/3" # L'adresse principale de leur catalogue
TMDB_URL_IMAGE = "https://image.tmdb.org/t/p" # L'adresse où ils rangent les affiches (images) des films
FICHIER_BDD = "izmar.db" # Le nom du fichier de sauvegarde que je vais créer sur mon ordinateur

# Je crée un dictionnaire des catégories avec leurs codes secrets. 
# Par exemple, pour The Movie Database, le code 28 veut dire "Action".
GENRES_DISPONIBLES = [
    (28, "Action"),
    (35, "Comedie"),
    (18, "Drame"),
    (27, "Horreur"),
    (10749, "Romance"),
    (53, "Thriller"),
]

# --- ALLUMAGE DU SERVEUR ---
app = FastAPI(title="IZMAR API", version="1.1.0") # Je crée mon serveur et je lui donne un nom

# Je dis au "vigile" de mon serveur : "Laisse entrer les demandes qui viennent de mon site web HTML, ne les bloque pas."
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# --- LA MÉMOIRE DE MON SERVEUR ---

# Fonction pour préparer mon carnet de notes (la base de données) au tout début
def initialiser_base_de_donnees():
    connexion = sqlite3.connect(FICHIER_BDD) # J'ouvre ou je crée mon fichier izmar.db
    curseur = connexion.cursor() # Je prends mon stylo virtuel pour écrire dedans
    
    # Je dis : "Crée un tableau qui s'appelle 'recherches' s'il n'existe pas déjà."
    # C'est comme un tableau Excel avec des colonnes : un numéro, le mode de recherche, ce que la personne a cherché, et ce que je lui ai trouvé.
    curseur.execute("""
        CREATE TABLE IF NOT EXISTS recherches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mode TEXT,
            critere TEXT,
            films_trouves TEXT
        )
    """)
    connexion.commit() # Je sauvegarde mes modifications
    connexion.close() # Je referme le fichier

# J'exécute la fonction tout de suite au démarrage du programme pour être sûr que le fichier existe
initialiser_base_de_donnees()

# Fonction pour noter une recherche dans le carnet à chaque fois que quelqu'un utilise le site
def sauvegarder_recherche(mode, critere, films_trouves):
    connexion = sqlite3.connect(FICHIER_BDD) # J'ouvre mon carnet
    curseur = connexion.cursor()
    # J'ajoute une nouvelle ligne dans mon tableau avec les informations
    curseur.execute(
        "INSERT INTO recherches (mode, critere, films_trouves) VALUES (?, ?, ?)",
        (mode, critere, json.dumps(films_trouves)) # Je transforme ma liste de films en texte simple pour pouvoir l'écrire
    )
    connexion.commit() # Je sauvegarde
    connexion.close() # Je ferme le carnet


# --- LE NETTOYAGE DES RÉSULTATS ---

# The Movie Database m'envoie plein d'infos inutiles pour chaque film. 
# Cette fonction prend le gros paquet d'infos, et ne garde que ce qui m'intéresse.
def formater_film(film):
    chemin_affiche = film.get("poster_path")
    # Si le film a une image, je construis l'adresse complète pour l'afficher sur mon site
    if chemin_affiche:
        url_affiche = f"{TMDB_URL_IMAGE}/w500{chemin_affiche}"
    else:
        url_affiche = None # Sinon, pas d'image
        
    # Je fabrique une petite boîte avec juste l'essentiel pour mon site web
    return {
        "titre": film.get("title", "Titre inconnu"),
        "annee": film.get("release_date", "")[:4], # Je garde juste les 4 premiers chiffres pour avoir l'année (ex: 2023)
        "synopsis": film.get("overview", "Pas de synopsis."),
        "affiche": url_affiche,
        "note": round(film.get("vote_average", 0), 1), # J'arrondis la note à un chiffre après la virgule (ex: 8.5)
    }


# --- LES GUICHETS DE MON SERVEUR (LES ROUTES) ---

# GUICHET N°1 : La recommandation (par thème ou par acteur)
@app.get("/recommander")
# Cette fonction est "async" parce que le serveur va devoir attendre que The Movie Database lui réponde.
async def recommander(
    mode: str, # On me dit si on cherche par "theme" ou par "acteur"
    genre_id: Optional[int] = None, # Le code du genre (facultatif, seulement pour le mode thème)
    duree_max: Optional[int] = None, # La durée maximum (facultatif)
    ambiance: Optional[str] = None, # "recent" ou "classique" (facultatif)
    acteur_nom: Optional[str] = None, # Le nom de l'acteur (facultatif, seulement pour le mode acteur)
):
    films_formates = [] # Je prépare la liste vide que je vais renvoyer à mon site web
    acteur_trouve = None

    # SI L'UTILISATEUR A CHOISI "THÈME"
    if mode == "theme":
        url = f"{TMDB_URL_BASE}/discover/movie" # Je prépare l'adresse de recherche
        
        # Je remplis mon enveloppe avec tous les critères demandés (mot de passe, en français, le bon genre, etc.)
        parametres = {
            "api_key": TMDB_CLE_API,
            "language": "fr-FR",
            "with_genres": genre_id,
            "with_runtime.lte": duree_max, # .lte veut dire "Less Than or Equal" (plus petit ou égal à la durée)
            "vote_count.gte": 100, # Je veux que le film ait au moins 100 votes pour éviter les films inconnus nuls
        }

        # Je trie les résultats selon l'ambiance choisie
        if ambiance == "recent":
            parametres["sort_by"] = "primary_release_date.desc" # Les plus récents en premier
        elif ambiance == "classique":
            parametres["sort_by"] = "vote_average.desc" # Les mieux notés en premier
            parametres["vote_count.gte"] = 1000 # Pour les classiques, j'exige au moins 1000 votes
        else:
            parametres["sort_by"] = "popularity.desc" # Sinon, les plus populaires en premier

        # J'envoie mon "facteur" chercher les résultats sur internet
        async with httpx.AsyncClient(timeout=10) as client:
            reponse = await client.get(url, params=parametres)
            
        donnees = reponse.json() # Je lis la réponse
        liste_films = donnees.get("results", []) # Je prends la liste des résultats
        
        # Pour les 3 premiers films de la liste, je les nettoie avec ma fonction, et je les ajoute à ma boîte finale
        for film in liste_films[:3]:
            films_formates.append(formater_film(film))

        # Je retrouve le vrai nom du genre (ex: "Action") à partir de son numéro (ex: 28) pour pouvoir le sauvegarder proprement
        nom_genre = next(
            (nom for gid, nom in GENRES_DISPONIBLES if gid == genre_id),
            "Genre"
        )
        critere_lisible = f"{nom_genre} - {duree_max}min - {ambiance or 'populaire'}"
        titres = [f["titre"] for f in films_formates] # Je récupère juste les titres
        sauvegarder_recherche("theme", critere_lisible, titres) # Je note tout ça dans mon fichier de sauvegarde izmar.db

    # SI L'UTILISATEUR A CHOISI "ACTEUR"
    elif mode == "acteur":
        # Étape 1 : Je dois d'abord trouver le bon acteur dans leur catalogue
        url_recherche = f"{TMDB_URL_BASE}/search/person"
        parametres_recherche = {
            "api_key": TMDB_CLE_API,
            "language": "fr-FR",
            "query": acteur_nom, # Le nom tapé sur le site
        }
        
        async with httpx.AsyncClient(timeout=10) as client:
            reponse = await client.get(url_recherche, params=parametres_recherche)
            
        donnees = reponse.json()
        personnes = donnees.get("results", [])
        
        # Si j'ai trouvé quelqu'un qui correspond
        if len(personnes) > 0:
            acteur = personnes[0] # Je prends le premier résultat
            acteur_trouve = acteur["name"] # Je garde son vrai nom bien orthographié
            acteur_id = acteur["id"] # Je garde son code secret (ID) pour chercher ses films
            
            # Étape 2 : Je cherche les films où cet acteur a joué
            url_films = f"{TMDB_URL_BASE}/person/{acteur_id}/movie_credits"
            parametres_films = {
                "api_key": TMDB_CLE_API,
                "language": "fr-FR",
            }
            
            async with httpx.AsyncClient(timeout=10) as client:
                reponse = await client.get(url_films, params=parametres_films)
                
            donnees_films = reponse.json()
            tous_les_films = donnees_films.get("cast", []) # "cast" c'est tous les rôles qu'il a eus
            
            # Je trie sa filmographie pour mettre les films les plus populaires en haut de la liste
            films_tries = sorted(tous_les_films, key=lambda f: f.get("popularity", 0), reverse=True)
            
            # Je nettoie les 3 premiers films et je les ajoute à ma boîte finale
            for film in films_tries[:3]:
                films_formates.append(formater_film(film))
                
        titres = [f["titre"] for f in films_formates]
        sauvegarder_recherche("acteur", f"Acteur : {acteur_trouve or acteur_nom}", titres) # Je sauvegarde dans mon carnet

    # Je renvoie la liste finale au site web HTML
    return {"films": films_formates, "acteur_trouve": acteur_trouve}


# GUICHET N°2 : Le mode Surprise !
@app.get("/surprise")
async def surprise():
    # Je choisis un genre totalement au hasard dans ma liste
    genre_id, nom_genre = random.choice(GENRES_DISPONIBLES)
    # Je choisis une page au hasard entre 1 et 5 sur The Movie Database (pour ne pas avoir toujours les mêmes films)
    page_aleatoire = random.randint(1, 5)

    url = f"{TMDB_URL_BASE}/discover/movie"
    parametres = {
        "api_key": TMDB_CLE_API,
        "language": "fr-FR",
        "with_genres": genre_id, # Je donne le genre tiré au sort
        "vote_count.gte": 500, # Je demande quand même de bons films (au moins 500 votes)
        "sort_by": "popularity.desc",
        "page": page_aleatoire, # Je fouille à la page tirée au sort
    }

    # Je vais chercher les résultats sur internet
    async with httpx.AsyncClient(timeout=10) as client:
        reponse = await client.get(url, params=parametres)

    donnees = reponse.json()
    liste_films = donnees.get("results", [])
    
    # Pour que ça soit vraiment une surprise, je mélange les résultats comme un paquet de cartes
    random.shuffle(liste_films)

    films_formates = []
    # Je prends les 3 premiers du paquet mélangé, je les nettoie
    for film in liste_films[:3]:
        films_formates.append(formater_film(film))

    # Je sauvegarde cette recherche surprise dans mon carnet
    titres = [f["titre"] for f in films_formates]
    sauvegarder_recherche("surprise", f"Surprise : {nom_genre}", titres)

    # J'envoie le résultat au site web HTML, en précisant quel genre a été tiré au sort
    return {"films": films_formates, "genre_pioche": nom_genre}