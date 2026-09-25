# 📚 Book Tracker

Jednoduchá, ľahká (lightweight) self-hosted appka na sledovanie prečítaných kníh. Beží v jednom Docker kontajneri, dáta si drží vo vlastnom SQLite súbore — žiadna externá databáza, žiadne platené API kľúče.

## Čo appka vie

- Vyhľadávanie kníh cez [Open Library](https://openlibrary.org) (zadarmo, bez API kľúča)
- Viacero používateľov, každý má vlastný účet a vlastnú knižnicu
- Označovanie kníh: **chcem čítať / čítam / prečítané / nedočítané**
- Hodnotenie kníh (1–5 hviezd), poznámky, dátum začatia a dočítania
- Dashboard so štatistikami: počet prečítaných kníh, tento rok, priemerné hodnotenie, knihy podľa rokov/mesiacov, najčítanejší autori
- Sledovanie sérií — ak si prečítal viac kníh z jednej série, appka ti ukáže, ktoré diely ti ešte chýbajú (vyhľadaním ďalších dielov cez Open Library)
- Slovenčina aj angličtina (prepínanie priamo v appke), pripravené na pridanie ďalších jazykov

## Technológie

Zámerne minimalistický stack, aby appka bola naozaj "lightweight" a ľahko sa dala hostovať na malom domácom serveri (napr. Raspberry Pi, mini PC, NAS):

- **Python + FastAPI** — backend
- **SQLite** — celá databáza je jeden súbor (`data/booktracker.db`), žiadny extra kontajner
- **Jinja2 + vanilla JS** — server-rendered šablóny, žiadny náročný frontend build (React/Vite a pod.)
- **Open Library API** — verejné, zadarmo, bez registrácie

## Spustenie (Docker)

Potrebuješ len [Docker](https://docs.docker.com/get-docker/) a Docker Compose.

```bash
git clone <adresa-tvojho-repa>
cd booktracker
cp .env.example .env
# uprav SECRET_KEY v .env na vlastný náhodný reťazec!
docker compose up -d --build
```

Appka bude bežať na `http://localhost:8000` (alebo `http://ip-tvojho-serveru:8000`).

Dáta (databáza) sa ukladajú do Docker volume `booktracker-data`, takže prežijú reštart aj update appky.

### Aktualizácia na novú verziu

```bash
git pull
docker compose up -d --build
```

## Konfigurácia (.env)

| Premenná | Popis | Default |
|---|---|---|
| `SECRET_KEY` | Tajný kľúč na podpisovanie session cookies. **Zmeň si to!** | — |
| `DEFAULT_LANGUAGE` | Predvolený jazyk appky (`sk` alebo `en`) | `sk` |
| `ALLOW_REGISTRATION` | Či sa môžu registrovať noví používatelia (`true`/`false`). Vypni, keď chceš appku len pre seba/rodinu po počiatočnom nastavení. | `true` |

## Spustenie lokálne bez Dockeru (pre vývoj)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Poznámky k dátam o sériách

Open Library nemá úplne spoľahlivé/štruktúrované dáta o knižných sériách — appka sa preto snaží sériu a poradie dielu odhadnúť z názvu knihy (bežný formát typu `Názov (Séria, #2)`), a zároveň ti umožní sériu a poradie ručne upraviť/opraviť pri každej knihe vo svojej knižnici. Funkcia "nájsť ďalšie diely" hľadá ďalšie knihy podľa názvu série cez Open Library vyhľadávanie — výsledky preto stojí za to skontrolovať očami, nemusia byť 100% presné.

## Prispievanie

Appka je zámerne jednoduchá (FastAPI + Jinja2 + SQLite), takže by malo byť pomerne ľahké sa v kóde zorientovať aj bez väčšej skúsenosti s Pythonom. PR-ky a nápady vítané.

## Licencia

MIT — používaj, upravuj, zdieľaj podľa ľubovôle.
