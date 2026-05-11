# Fichier : izmar/frontend/Dockerfile (LE FRONTEND)
FROM nginx:alpine

# On copie tes fichiers visuels dans le dossier du serveur web
COPY izmar.html /usr/share/nginx/html/index.html
COPY style.css /usr/share/nginx/html/
COPY cinema.jpg /usr/share/nginx/html/

EXPOSE 80