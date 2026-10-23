import os,sqlite3,secrets,re,hmac
from flask import Flask,request,redirect,session,abort,render_template_string,url_for
app=Flask(__name__);app.secret_key=os.environ.get("SECRET_KEY",secrets.token_hex(32))
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Lax",SESSION_COOKIE_SECURE=os.environ.get("HTTPS","0")=="1")
DB=os.environ.get("DATABASE_PATH","/tmp/podcast-trail.db")
SHOW="https://open.spotify.com/show/103URFuKDPmddv30ihF3Hl?si=N-QNiCfDQ8WAlXG35aSnsg"
EP="https://open.spotify.com/episode/19mYZVTqkvyC5hUYryNycp?si=GI6CBk1gQAeRNmUKN6Svvg"
def db():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def setup():
 with db() as c:
  c.executescript("""CREATE TABLE IF NOT EXISTS creators(id INTEGER PRIMARY KEY,handle TEXT UNIQUE,status TEXT DEFAULT 'pending',token TEXT UNIQUE);
CREATE TABLE IF NOT EXISTS episodes(id INTEGER PRIMARY KEY,title TEXT,url TEXT,active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS clicks(id INTEGER PRIMARY KEY,creator INTEGER,visitor TEXT,kind TEXT,episode INTEGER,created TEXT DEFAULT CURRENT_TIMESTAMP);""")
  if not c.execute("SELECT 1 FROM episodes").fetchone():c.execute("INSERT INTO episodes(title,url) VALUES (?,?)",("Featured Flurzi episode",EP))
setup()
CSS="""<style>body{font-family:Inter,system-ui,sans-serif;background:#0a0b19;color:#f7f6ff;margin:0}header{padding:22px 7%;border-bottom:1px solid #292842;display:flex;justify-content:space-between}main{max-width:1060px;margin:45px auto;padding:0 22px}h1{font-size:clamp(30px,6vw,58px);letter-spacing:-2px}a{color:#c2b5ff}p,small{color:#b7b5d0}section,.tile{background:#17172c;border:1px solid #343150;border-radius:20px;padding:24px;margin:14px 0}button,.btn{background:linear-gradient(110deg,#824eff,#df56c4);color:white;border:0;padding:13px 20px;border-radius:12px;cursor:pointer;text-decoration:none;display:inline-block}input{background:#24233a;border:1px solid #514d74;color:white;border-radius:10px;padding:13px;margin:8px;max-width:90%}.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}.big{font-size:36px;font-weight:800;color:#e0c8ff}form{display:inline-block}table{width:100%;border-collapse:collapse}td,th{padding:12px;border-bottom:1px solid #343150;text-align:left;overflow-wrap:anywhere}.muted{color:#b7b5d0}</style>"""
def page(body,**kwargs):return render_template_string(CSS+"<header><b>✦ FLURZI / PODCAST TRAIL</b><a href='/creators'>Creators</a></header><main>"+body+"</main>",**kwargs)
def auth():
 if not session.get("admin"):abort(403)
def stat(cid):
 with db() as c:
  a=c.execute("SELECT kind,COUNT(*) n,COUNT(DISTINCT visitor) u FROM clicks WHERE creator=? GROUP BY kind",(cid,)).fetchall()
 return {r["kind"]:(r["n"],r["u"]) for r in a}
@app.after_request
def secure(r):
 r.headers["X-Frame-Options"]="DENY";r.headers["X-Content-Type-Options"]="nosniff";r.headers["Cache-Control"]="no-store";return r
@app.route("/")
def index():return redirect("/creators")
@app.route("/creators",methods=["GET","POST"])
def creators():
 msg=""
 if request.method=="POST":
  handle=request.form.get("handle","").strip().lower().lstrip("@")
  if not re.fullmatch(r"[a-z0-9._]{2,24}",handle):msg="Enter a valid TikTok handle."
  else:
   try:
    with db() as c:c.execute("INSERT INTO creators(handle) VALUES (?)",(handle,))
    msg="Application received! Your handle is pending Flurzi approval."
   except sqlite3.IntegrityError:msg="This handle has already applied."
 return page("<h1>Turn your audience into impact.</h1><p>Flurzi Podcast creator programme. Apply with your exact TikTok handle; no account signup required.</p><section><h2>Apply as a creator</h2><form method='post'><input name='handle' placeholder='@yourtiktok' required><button>Request approval</button></form><p>{{msg}}</p></section><p>Approved creators receive private dashboard and share links. Spotify outbound clicks are tracked; Spotify listening duration and follows cannot be independently verified here.</p>",msg=msg)
@app.route("/admin/login",methods=["GET","POST"])
def login():
 msg=""
 if request.method=="POST":
  pw=os.environ.get("ADMIN_PASSWORD","")
  if pw and hmac.compare_digest(request.form.get("password",""),pw):
   session.clear();session["admin"]=True;return redirect("/admin")
  msg="Incorrect password or ADMIN_PASSWORD not configured."
 return page("<h1>Admin access</h1><section><form method='post'><input type='password' name='password' placeholder='Admin password' required><button>Sign in</button></form><p>{{msg}}</p></section>",msg=msg)
@app.get("/admin")
def admin():
 auth()
 with db() as c:
  people=c.execute("SELECT * FROM creators ORDER BY id DESC").fetchall()
  episodes=c.execute("SELECT * FROM episodes ORDER BY id DESC").fetchall()
 return page("""<h1>Command centre</h1><p>Approve TikTok handles, manage episodes, and review measurable referral activity.</p><section><h2>Creator applications</h2><table><tr><th>Handle</th><th>Status</th><th>Visits / unique</th><th>Spotify clicks</th><th>Actions</th></tr>{% for p in people %}<tr><td>@{{p.handle}}</td><td>{{p.status}}{% if p.token %}<p><a href='/dashboard/{{p.token}}'>Dashboard</a> · <a href='/c/{{p.token}}'>Share URL</a></p>{% endif %}</td><td>{{stats[p.id].get('visit',(0,0))[0]}} / {{stats[p.id].get('visit',(0,0))[1]}}</td><td>{{stats[p.id].get('show',(0,0))[0]+stats[p.id].get('episode',(0,0))[0]}}</td><td><form method='post' action='/admin/creator/{{p.id}}/approve'><button>Approve</button></form> <form method='post' action='/admin/creator/{{p.id}}/revoke'><button>Revoke</button></form></td></tr>{% endfor %}</table></section><section><h2>Episodes</h2><form method='post' action='/admin/episode'><input name='title' placeholder='Episode title' required><input name='url' placeholder='https://open.spotify.com/episode/...' required><button>Add episode</button></form>{% for e in episodes %}<p>{{e.title}} · {{'Active' if e.active else 'Hidden'}} <form method='post' action='/admin/episode/{{e.id}}/toggle'><button>Toggle</button></form></p>{% endfor %}</section><form method='post' action='/admin/logout'><button>Sign out</button></form>""",people=people,episodes=episodes,stats={p["id"]:stat(p["id"]) for p in people})
@app.post("/admin/logout")
def logout():auth();session.clear();return redirect("/admin/login")
@app.post("/admin/creator/<int:cid>/<action>")
def update_creator(cid,action):
 auth()
 if action not in ("approve","revoke"):abort(404)
 with db() as c:
  if action=="approve":c.execute("UPDATE creators SET status='approved',token=COALESCE(token,?) WHERE id=?",(secrets.token_urlsafe(32),cid))
  else:c.execute("UPDATE creators SET status='revoked',token=NULL WHERE id=?",(cid,))
 return redirect("/admin")
@app.post("/admin/episode")
def add_episode():
 auth();title=request.form.get("title","").strip()[:160];url=request.form.get("url","").strip()
 if not title or not url.startswith("https://open.spotify.com/episode/"):abort(400)
 with db() as c:c.execute("INSERT INTO episodes(title,url) VALUES (?,?)",(title,url))
 return redirect("/admin")
@app.post("/admin/episode/<int:eid>/toggle")
def toggle(eid):
 auth()
 with db() as c:c.execute("UPDATE episodes SET active=1-active WHERE id=?",(eid,))
 return redirect("/admin")
def creator(token):
 with db() as c:return c.execute("SELECT * FROM creators WHERE token=? AND status='approved'",(token,)).fetchone()
def visit(cid,kind,eid=None):
 vid=request.cookies.get("pt_visitor")
 if not vid or not re.fullmatch("[a-f0-9]{32}",vid):vid=secrets.token_hex(16)
 with db() as c:c.execute("INSERT INTO clicks(creator,visitor,kind,episode) VALUES (?,?,?,?)",(cid,vid,kind,eid))
 return vid
@app.get("/c/<token>")
def landing(token):
 p=creator(token)
 if not p:abort(404)
 vid=visit(p["id"],"visit")
 with db() as c:eps=c.execute("SELECT * FROM episodes WHERE active=1").fetchall()
 r=app.make_response(page("<h1>Discover Flurzi Podcast</h1><p>Recommended by @{{p.handle}}</p><section><a class='btn' href='/go/{{p.token}}/show/0'>Listen to the show on Spotify</a></section><h2>Episodes</h2>{% for e in eps %}<section><h3>{{e.title}}</h3><a class='btn' href='/go/{{p.token}}/episode/{{e.id}}'>Open episode on Spotify</a></section>{% endfor %}",p=p,eps=eps))
 r.set_cookie("pt_visitor",vid,max_age=31536000,httponly=True,samesite="Lax",secure=os.environ.get("HTTPS","0")=="1");return r
@app.get("/go/<token>/<kind>/<int:eid>")
def go(token,kind,eid):
 p=creator(token)
 if not p or kind not in ("show","episode"):abort(404)
 if kind=="show":url=SHOW
 else:
  with db() as c:e=c.execute("SELECT * FROM episodes WHERE id=? AND active=1",(eid,)).fetchone()
  if not e:abort(404)
  url=e["url"]
 visit(p["id"],kind,eid);return redirect(url)
@app.get("/dashboard/<token>")
def dashboard(token):
 p=creator(token)
 if not p:abort(404)
 return page("""<h1>@{{p.handle}}'s creator studio</h1><p>Your live referral performance · refreshes every 15 seconds</p><div class='tiles'><div class='tile'><p>Page visits</p><div class='big' id='visits'>—</div></div><div class='tile'><p>Unique visitors</p><div class='big' id='unique'>—</div></div><div class='tile'><p>Spotify outbound clicks</p><div class='big' id='clicks'>—</div></div><div class='tile'><p>Verified Spotify listens</p><div class='big'>Unavailable</div></div></div><section><h2>Your referral link</h2><p id='link'></p><button onclick='navigator.clipboard.writeText(location.origin+"/c/{{p.token}}")'>Copy referral link</button></section><p>Spotify does not share per-person duration, attributed follows, or verified listens through this link. Clicks are not eligible payout listens. Private dashboard link: keep it confidential.</p><script>const link=location.origin+"/c/{{p.token}}";document.getElementById("link").textContent=link;async function refresh(){const r=await fetch("/api/dashboard/{{p.token}}");if(!r.ok)return;const d=await r.json();for(const k of ["visits","unique","clicks"])document.getElementById(k).textContent=d[k].toLocaleString()}refresh();setInterval(refresh,15000)</script>""",p=p)
@app.get("/api/dashboard/<token>")
def dashboard_api(token):
 from flask import jsonify
 p=creator(token)
 if not p:abort(404)
 s=stat(p["id"])
 return jsonify(visits=s.get("visit",(0,0))[0],unique=s.get("visit",(0,0))[1],clicks=s.get("show",(0,0))[0]+s.get("episode",(0,0))[0])
if __name__=="__main__":app.run(host="0.0.0.0",port=int(os.environ.get("PORT","5000")))
