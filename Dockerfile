FROM python:3.12-alpine
WORKDIR /srv
COPY app/ .
EXPOSE 8080
CMD ["python3", "-m", "http.server", "8080"]
