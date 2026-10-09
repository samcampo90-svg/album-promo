"""Hook text, story sequences and caption pieces, in Spanish (Puerto Rican
register) and English. Placeholders in {braces} are filled from album.json; a
hook whose placeholders can't be filled is skipped, so hooks that state facts
(where it was made, what a song is about) only appear once those facts exist in
that language (e.g. "about_es" for Spanish).

Each hook: (phase, kind, text). phase: pre | release | post | any."""

HOOKS = {
    "es": [
        # descubrimiento
        ("any", "pov", "POV: encontraste tu nueva canción favorita"),
        ("any", "pov", "POV: llegaste antes que todo el mundo"),
        ("any", "pov", "POV: son las 3am y suena esto"),
        ("any", "pov", "POV: guiando de noche y suena esto"),
        ("any", "pov", "canciones que se sienten como {vibe}"),
        ("any", "pov", "música pa' {activity}"),
        ("any", "pov", "esta es tu señal pa' ponerte los audífonos"),
        ("any", "pov", "mándaselo a alguien que lo necesite hoy"),
        ("any", "pov", "mándaselo al corillo"),
        # comparación
        ("any", "compare", "si te gusta {sim1}, creo que esto te va a gustar"),
        ("any", "compare", "pa' los fans de {sim1} y {sim2}"),
        ("any", "compare", "fans de {sim1}, necesito su opinión honesta"),
        ("any", "compare", "si tu playlist tiene {sim2}, añade esta"),
        # retención
        ("any", "wait", "espérate a que entre"),
        ("any", "wait", "espérate al coro"),
        ("any", "drop", "el momento en que entra"),
        ("any", "drop", "espera el drop"),
        ("any", "wait", "escúchalo con audífonos"),
        ("any", "replay", "la parte que no puedo dejar de repetir"),
        ("any", "replay", "esta parte vive en mi cabeza sin pagar renta"),
        ("any", "replay", "la parte en el {ts} vive en mi cabeza"),
        ("any", "replay", "brinca al {ts}. confía"),
        # preguntas
        ("any", "ask", "del 1 al 10, ¿cuánto le das?"),
        ("any", "ask", "sin mentir: ¿skip o replay?"),
        ("any", "ask", "¿la añadirías a tu playlist? sé honesto"),
        ("any", "ask", "dime desde dónde lo estás escuchando"),
        ("any", "ask", "¿a qué te recuerda esta canción?"),
        # historia (solo con datos reales)
        ("any", "story", "hice este álbum en {made_where}"),
        ("any", "story", "{months} meses trabajando en esto"),
        ("any", "story", "escribí esta canción sobre {about}"),
        ("any", "story", "esta es pa' cualquiera que {for_anyone_who}"),
        ("any", "story", "artista independiente. sin disquera. solo esta canción"),
        ("any", "story", "casi no saco esta"),
        ("any", "lyric", "la mejor línea que he escrito"),
        ("any", "lyric", "“{lyric}”"),
        # antes del lanzamiento
        ("pre", "tease", "todavía no ha salido. sale {day_name}"),
        ("pre", "tease", "lo estás escuchando antes que nadie"),
        ("pre", "tease", "adelanto de mi álbum {album}"),
        ("pre", "tease", "{album} sale en {days} días"),
        ("pre", "tease", "faltan {days} días pa' mi álbum"),
        ("pre", "tease", "¿esta debería ser el próximo sencillo?"),
        ("pre", "tease", "dale pre-save pa' que te llegue el día que salga"),
        ("pre", "tease", "mi álbum sale {day_name} y estoy nervioso"),
        ("pre", "tease", "primera escucha: {song}"),
        # lanzamiento
        ("release", "out", "{album} ya salió"),
        ("release", "out", "mi álbum por fin salió"),
        ("release", "out", "ya salió. las {n_tracks} canciones"),
        ("release", "out", "{song} ya está en todas las plataformas"),
        ("release", "out", "mi álbum acaba de salir y no puedo ni respirar"),
        # después
        ("post", "out", "{song}, ya disponible"),
        ("post", "out", "track {track_no} de {album}"),
        ("post", "ask", "¿cuál es tu favorita de {album}?"),
        ("post", "series", "día {post_day} posteando mi álbum hasta que encuentre a su gente"),
        ("post", "series", "día {post_day} posteando {song} hasta que encuentre a su gente"),
        ("post", "out", "la de {album} que más orgullo me da"),
    ],
    "en": [
        ("any", "pov", "POV: you found your new favorite song"),
        ("any", "pov", "POV: you're early"),
        ("any", "pov", "POV: it's 2am and this comes on"),
        ("any", "pov", "POV: the drive home hits different with this"),
        ("any", "pov", "songs that feel like {vibe}"),
        ("any", "pov", "music for {activity}"),
        ("any", "pov", "this is your sign to put headphones on"),
        ("any", "pov", "send this to someone who needs it today"),
        ("any", "compare", "if you like {sim1}, I think you'll like this"),
        ("any", "compare", "for fans of {sim1} and {sim2}"),
        ("any", "compare", "{sim1} fans, I need your honest opinion"),
        ("any", "compare", "if your playlist has {sim2} on it, add this"),
        ("any", "wait", "wait for it"),
        ("any", "wait", "wait for the chorus"),
        ("any", "drop", "the moment it kicks in"),
        ("any", "drop", "wait for the drop"),
        ("any", "wait", "listen with headphones"),
        ("any", "replay", "the part I can't stop replaying"),
        ("any", "replay", "this part lives in my head rent free"),
        ("any", "replay", "the part at {ts} lives in my head"),
        ("any", "replay", "skip to {ts}. trust me"),
        ("any", "ask", "rate this 1-10"),
        ("any", "ask", "be honest: skip or replay?"),
        ("any", "ask", "would you add this to your playlist? be honest"),
        ("any", "ask", "tell me where you're listening from"),
        ("any", "ask", "what does this song remind you of?"),
        ("any", "story", "I made this album in {made_where}"),
        ("any", "story", "{months} months of work for this"),
        ("any", "story", "I wrote this song about {about}"),
        ("any", "story", "this one is for anyone who {for_anyone_who}"),
        ("any", "story", "independent artist. no label. just this song"),
        ("any", "story", "I almost didn't release this one"),
        ("any", "lyric", "my favorite lyric I've ever written"),
        ("any", "lyric", "“{lyric}”"),
        ("pre", "tease", "unreleased. out {day_name}"),
        ("pre", "tease", "you're hearing this before everyone else"),
        ("pre", "tease", "sneak peek from my album {album}"),
        ("pre", "tease", "{album} comes out in {days} days"),
        ("pre", "tease", "{days} days until my album drops"),
        ("pre", "tease", "should this be the next single?"),
        ("pre", "tease", "pre-save it so it's waiting for you on release day"),
        ("pre", "tease", "my album comes out {day_name} and I'm nervous"),
        ("pre", "tease", "first listen: {song}"),
        ("release", "out", "{album} is out now"),
        ("release", "out", "my album is finally out"),
        ("release", "out", "it's out. all {n_tracks} songs"),
        ("release", "out", "{song} is out now everywhere"),
        ("release", "out", "my album just came out and I can't breathe"),
        ("post", "out", "{song}, out now"),
        ("post", "out", "track {track_no} from {album}"),
        ("post", "ask", "which song from {album} is your favorite?"),
        ("post", "series", "day {post_day} of posting my album until it finds its people"),
        ("post", "series", "day {post_day} of posting {song} until it finds its people"),
        ("post", "out", "the song from {album} I'm proudest of"),
    ],
}

# text_story sequences (one line per bar or two)
STORIES = {
    "es": [
        ("any", ["si te gusta {sim1}", "y {sim2}", "esta podría ser tu nueva favorita"]),
        ("any", ["hice este álbum", "en {made_where}", "esta es {song}"]),
        ("any", ["{months} meses", "un álbum", "esta es {song}"]),
        ("any", ["esta canción es sobre", "{about}", "se llama {song}"]),
        ("pre", ["esta es {song}", "de mi álbum {album}", "sale {day_name}"]),
        ("pre", ["faltan {days} días", "pa' {album}", "pre-save en la bio"]),
        ("pre", ["sin disquera", "sin presupuesto", "solo un álbum", "sale {day_name}"]),
        ("release", ["ya salió", "{album}", "{n_tracks} canciones", "link en la bio"]),
        ("post", ["{album}", "ya disponible", "empieza con {song}"]),
        ("post", ["día {post_day}", "posteando mi álbum", "hasta que encuentre a su gente"]),
    ],
    "en": [
        ("any", ["if you like {sim1}", "and {sim2}", "this might be your new favorite"]),
        ("any", ["I made this album", "in {made_where}", "this is {song}"]),
        ("any", ["{months} months", "one album", "this is {song}"]),
        ("any", ["this song is about", "{about}", "it's called {song}"]),
        ("pre", ["this is {song}", "from my album {album}", "out {day_name}"]),
        ("pre", ["{days} days", "until {album}", "pre-save, link in bio"]),
        ("pre", ["no label", "no budget", "just an album", "out {day_name}"]),
        ("release", ["it's out", "{album}", "{n_tracks} songs", "link in bio"]),
        ("post", ["{album}", "out now", "start with {song}"]),
        ("post", ["day {post_day}", "of posting my album", "until it finds its people"]),
    ],
}

CAPTION_LINES = {
    "es": {
        "pre": ["{song}, de mi álbum {album}. sale {day_name}", "todavía no ha salido. {album} sale {day_name}",
                "faltan {days} días pa' {album}", "adelanto: {song}", "{album} ya casi está aquí",
                "primer adelanto de {song}"],
        "release": ["{album} ya salió", "{song} ya está afuera", "por fin salió", "{album}, ya en todas las plataformas"],
        "post": ["{song}, de {album}. ya disponible", "{album} ya está afuera", "¿ya escuchaste {song}?",
                 "track {track_no}: {song}", "{song}. y ya"],
    },
    "en": {
        "pre": ["{song}, from my album {album}, out {day_name}", "unreleased. {album} drops {day_name}",
                "{days} days until {album}", "sneak peek: {song}", "{album} is almost here", "first look at {song}"],
        "release": ["{album} is out now", "{song} is out now", "it's finally out", "{album}, out everywhere today"],
        "post": ["{song} from {album}, out now", "{album} is out now", "have you heard {song} yet?",
                 "track {track_no}: {song}", "{song}. that's the post"],
    },
}

CTA = {
    "es": {
        "pre": {"tiktok": "pre-save en el link de mi bio", "reels": "Pre-save en el link de la bio.", "shorts": "Pre-save: {link}"},
        "release": {"tiktok": "ya disponible, link en la bio", "reels": "Ya disponible. Link en la bio.", "shorts": "Escúchalo: {link}"},
        "post": {"tiktok": "ya disponible, link en la bio", "reels": "Ya disponible. Link en la bio.", "shorts": "Escúchalo: {link}"},
    },
    "en": {
        "pre": {"tiktok": "pre-save link in bio", "reels": "Pre-save link in bio.", "shorts": "Pre-save: {link}"},
        "release": {"tiktok": "out now, link in bio", "reels": "Out now. Link in bio.", "shorts": "Listen: {link}"},
        "post": {"tiktok": "out now, link in bio", "reels": "Out now. Link in bio.", "shorts": "Listen: {link}"},
    },
}

ASK_LINES = {
    "es": ["¿del 1 al 10?", "¿skip o replay?", "¿desde dónde lo escuchas?", "¿a qué te recuerda?", "¿tu parte favorita?", ""],
    "en": ["rate it 1-10", "skip or replay?", "where are you listening from?", "what does it remind you of?",
           "favorite part?", ""],
}

STORY_NOTES = {
    "es": ["Añade una encuesta: ¿replay o skip?", "Añade un sticker de música o link", "Añade una caja de preguntas: ¿línea favorita?",
           "Añade un slider de emoji"],
    "en": ["Add a poll: replay or skip?", "Add a music/link sticker", "Add a question box: favorite lyric?",
           "Add a slider emoji sticker"],
}

# card and countdown wording
CARD = {
    "es": {"day": "DÍA", "days": "DÍAS", "until": "PA' {album}", "out": "SALE {date}", "outnow": "YA SALIÓ"},
    "en": {"day": "DAY", "days": "DAYS", "until": "UNTIL {album}", "out": "OUT {date}", "outnow": "OUT NOW"},
}

DAYS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MONTHS_ES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MONTHS_ES_LONG = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
                  "octubre", "noviembre", "diciembre"]


def date_words(release, days_left, lang):
    """(day_name, date, short_date) in the given language. day_name carries its
    own preposition in Spanish ("el viernes", "el 30 de octubre")."""
    if lang == "es":
        date = f"{release.day} de {MONTHS_ES_LONG[release.month - 1]}"
        short = f"{release.day} {MONTHS_ES[release.month - 1]}".upper()
        day_name = f"el {DAYS_ES[release.weekday()]}" if 0 < days_left <= 6 else f"el {date}"
        return day_name, date, short
    date = release.strftime("%b %-d")
    day_name = release.strftime("%A") if 0 < days_left <= 6 else f"on {date}"
    return day_name, date, date.upper()
