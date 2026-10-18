# BTCFeed - Copilot handoff

Yeh file doosre VS Code/Copilot profile ko project aur ab tak ke kaam ka context dene ke liye hai. Isme kisi credential ya `.env` value ko jaan-boojhkar shamil nahi kiya gaya hai.

## User aur kaam karne ka tareeqa

- User Hindi/Hinglish mein baat karta hai; jawab aur explanations Hindi/Hinglish mein dena behtar hai.
- User aksar seedha requested code/file change chahta hai. Pehle relevant files aur current git status dekho, phir change karke verify karo.
- Secrets ko output, commit, handoff, logs, ya screenshots mein expose mat karo. `.env` kholne ki zaroorat na ho to mat kholo.
- Changes surgical rakho. Existing unrelated/untracked files ko overwrite, stage, ya delete mat karo.

## Project kya hai

BTCFeed (repository/folder name: BTCFed) ek browser-based live financial/news feed hai. Frontend [index.html](./index.html) Supabase ke public `feed` endpoint se recent stories load karta hai. Python worker RSS sources fetch karta hai, stories deduplicate/classify/sentiment-score karta hai, aur Supabase mein save karta hai. Sources [sources.json](./sources.json) mein configured hain.

### Main files

- [index.html](./index.html): Single-page UI; filters, source search, priority/event mode, read tracking, sentiment, links, pinned data aur periodic feed refresh.
- [worker.py](./worker.py): RSS ingestion, URL/title/embedding deduplication, sentiment model aur Supabase writes.
- [sources.json](./sources.json): RSS feeds aur unke metadata.
- [supabase/schema.sql](./supabase/schema.sql): Tables, vector matching function, public feed view aur access grants.
- [\.github/workflows/ingest.yml](./.github/workflows/ingest.yml): GitHub Actions mein har 5 minute scheduled ingestion; manual dispatch bhi hai.
- [requirements.txt](./requirements.txt): Python dependencies; sentence-transformers/transformers/PyTorch ki wajah se worker comparatively heavy hai.
- [test_feeds.py](./test_feeds.py): External RSS URLs par connectivity/entry-count smoke check; chalane ke liye network access chahiye.
- [start_live.bat](./start_live.bat): Windows par `python worker.py --loop` chalata hai.
- [README.md](./README.md): Abhi sirf project title; setup documentation nahi ke barabar hai.

## Credentials aur configuration

- Worker ko `SUPABASE_URL` aur `SUPABASE_SERVICE_KEY` chahiye. Local development mein worker inhe project root ke `.env` se load karta hai.
- `.github/workflows/ingest.yml` in dono ko GitHub Actions repository secrets se leta hai.
- Service-role key secret hai: ise browser code, git, logs, ya is handoff mein kabhi mat daalo. Frontend mein Supabase URL aur public/anon key configured hain; public key ko service-role key se replace mat karo.
- Root [.gitignore](./.gitignore) mein `.env` ignore hoti hai. Ignore hone ka matlab file remote par surakshit/backed-up hai, yeh nahi hota; local `.env` ko manually share/commit mat karo.

## Is conversation mein kiya gaya kaam

1. User ki request par root `.gitignore` banaya aur `.env` rule add kiya; `git check-ignore` se verify kiya.
2. User ki request par [index.html](./index.html) ke `<style>` block ke end mein responsive CSS add ki:
   - `.app` max-width 1500px.
   - 760px se wide screens par news list 2 columns.
   - 1500px se 3 columns.
   - Grid items ke borders/gaps aur `.empty` full-row behavior.
3. `git diff --check` pass hua. RSS tests ya build run nahi kiye gaye.

## Abhi verify karne layak issue

`sources.json` ke `type` values `forex`, `crypto`, aur `macro` hain, jabki [supabase/schema.sql](./supabase/schema.sql) mein `stories.type` par check constraint sirf `social` ya `newspaper` allow karti hai. [worker.py](./worker.py) seedha `source["type"]` ko insert karta hai. Isliye current feeds se nayi story insert hote waqt constraint violation sambhav hai. Agla coding task is mismatch ko resolve karne se pehle product ke intended categories confirm kare; schema, UI labels/filters aur source metadata ko ek saath align karna hoga. Yeh change abhi nahi kiya gaya.

## Git/worktree ki sthiti (handoff banate waqt)

- Branch `main` par hai.
- `git ls-files` ke mutabik sirf `README.md` tracked tha.
- `.gitignore`, `index.html`, `worker.py`, `sources.json`, `requirements.txt`, `start_live.bat`, `test_feeds.py`, `.github/`, aur `supabase/` untracked the. Yeh files is assistant ne is handoff task mein nahi banayi; pehle se worktree mein maujood thin.
- Agla Copilot pehle `git status --short` dobara check kare. In files ko user ki permission ke bina stage/commit, overwrite, ya clean na kare.

## Agle session ke liye

Current `git status` check karke user ka agla specific request follow karo. Category/schema mismatch ko known follow-up samjho, lekin user ke kehne ke bina unrelated scope mein fix mat karo. Agar user worker/debugging maange, secrets print kiye bina env-variable names aur error context inspect karo. Worker commands model downloads aur network maang sakte hain; pehle lightweight targeted checks ko tarjeeh do.
