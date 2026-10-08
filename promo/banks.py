"""Hook text, story sequences and caption pieces. Placeholders in {braces} are
filled from album.json; any hook whose placeholders can't be filled is skipped,
so hooks that make factual claims (where it was made, how long it took) only
appear once those facts are provided."""

# phase: pre | release | post | any.  kinds let the planner match hooks to moments/templates.
HOOKS = [
    # --- discovery / relatable
    ("any", "pov", "POV: you found your new favorite song"),
    ("any", "pov", "POV: you're early"),
    ("any", "pov", "POV: it's 2am and this comes on"),
    ("any", "pov", "POV: the drive home hits different with this"),
    ("any", "pov", "songs that feel like {vibe}"),
    ("any", "pov", "music for {activity}"),
    ("any", "pov", "this is your sign to put headphones on"),
    ("any", "pov", "send this to someone who needs it today"),
    # --- comparison targeting
    ("any", "compare", "if you like {sim1}, I think you'll like this"),
    ("any", "compare", "for fans of {sim1} and {sim2}"),
    ("any", "compare", "{sim1} fans, I need your honest opinion"),
    ("any", "compare", "if your playlist has {sim2} on it, add this"),
    # --- retention / curiosity
    ("any", "wait", "wait for it"),
    ("any", "wait", "wait for the chorus"),
    ("any", "drop", "the moment it kicks in"),
    ("any", "drop", "wait for the drop"),
    ("any", "wait", "listen with headphones"),
    ("any", "replay", "the part I can't stop replaying"),
    ("any", "replay", "this part lives in my head rent free"),
    ("any", "replay", "the part at {ts} lives in my head"),
    ("any", "replay", "skip to {ts}. trust me"),
    # --- engagement prompts
    ("any", "ask", "rate this 1-10"),
    ("any", "ask", "be honest: skip or replay?"),
    ("any", "ask", "would you add this to your playlist? be honest"),
    ("any", "ask", "tell me where you're listening from"),
    ("any", "ask", "what does this song remind you of?"),
    # --- artist story (only when facts are provided)
    ("any", "story", "I made this album in {made_where}"),
    ("any", "story", "{months} months of work for this"),
    ("any", "story", "I wrote this song about {about}"),
    ("any", "story", "this one is for anyone who {for_anyone_who}"),
    ("any", "story", "independent artist. no label. just this song"),
    ("any", "story", "I almost didn't release this one"),
    ("any", "lyric", "my favorite lyric I've ever written"),
    ("any", "lyric", "“{lyric}”"),
    # --- pre-release
    ("pre", "tease", "unreleased. out {day_name}"),
    ("pre", "tease", "you're hearing this before everyone else"),
    ("pre", "tease", "sneak peek from my album {album}"),
    ("pre", "tease", "{album} comes out in {days} days"),
    ("pre", "tease", "{days} days until my album drops"),
    ("pre", "tease", "should this be the next single?"),
    ("pre", "tease", "pre-save it so it's waiting for you on release day"),
    ("pre", "tease", "my album comes out {date} and I'm nervous"),
    ("pre", "tease", "first listen: {song}"),
    # --- release window
    ("release", "out", "{album} is out now"),
    ("release", "out", "my album is finally out"),
    ("release", "out", "it's out. all {n_tracks} songs"),
    ("release", "out", "{song} is out now everywhere"),
    ("release", "out", "my album just came out and I can't breathe"),
    # --- post-release
    ("post", "out", "{song}, out now"),
    ("post", "out", "track {track_no} from {album}"),
    ("post", "ask", "which song from {album} is your favorite?"),
    ("post", "series", "day {post_day} of posting my album until it finds its people"),
    ("post", "series", "day {post_day} of posting {song} until it finds its people"),
    ("post", "out", "the song from {album} I'm proudest of"),
]

# text_story sequences (one line per bar or two)
STORIES = [
    ("any", ["if you like {sim1}", "and {sim2}", "this might be your new favorite"]),
    ("any", ["I made this album", "in {made_where}", "this is {song}"]),
    ("any", ["{months} months", "one album", "this is {song}"]),
    ("any", ["this song is about", "{about}", "it's called {song}"]),
    ("pre", ["this is {song}", "from my album {album}", "out {date}"]),
    ("pre", ["{days} days", "until {album}", "pre-save, link in bio"]),
    ("pre", ["no label", "no budget", "just an album", "out {date}"]),
    ("release", ["it's out", "{album}", "{n_tracks} songs", "link in bio"]),
    ("post", ["{album}", "out now", "start with {song}"]),
    ("post", ["day {post_day}", "of posting my album", "until it finds its people"]),
]

CAPTION_LINES = {
    "pre": ["{song}, from my album {album}, out {date}", "unreleased. {album} drops {date}",
            "{days} days until {album}", "sneak peek: {song}", "{album} is almost here",
            "first look at {song}"],
    "release": ["{album} is out now", "{song} is out now", "it's finally out", "{album}, out everywhere today"],
    "post": ["{song} from {album}, out now", "{album} is out now", "have you heard {song} yet?",
             "track {track_no}: {song}", "{song}. that's it, that's the post"],
}

CTA = {
    "pre": {"tiktok": "pre-save link in bio", "reels": "Pre-save link in bio.", "shorts": "Pre-save: {link}"},
    "release": {"tiktok": "out now, link in bio", "reels": "Out now. Link in bio.", "shorts": "Listen: {link}"},
    "post": {"tiktok": "out now, link in bio", "reels": "Out now. Link in bio.", "shorts": "Listen: {link}"},
}

ASK_LINES = ["rate it 1-10", "skip or replay?", "where are you listening from?", "what does it remind you of?",
             "favorite part?", ""]
