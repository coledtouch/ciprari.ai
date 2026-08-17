# Back-catalog: Aug 2025 – Jun 2026. Pre-1.0 versions — the beta era.
# Art style: phosphor line-art, 640x300 viewBox. G=green, D=dim, A=amber.

G, D, A, M = "#33ff66", "#4fae7c", "#ffd75e", "#2d6b4a"

def _svg(inner, w=640, h=300):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">'
            f'<rect width="{w}" height="{h}" fill="#04120a"/>{inner}</svg>')

POSTS_A = [

dict(
slug="v0-9-9-the-intern-is-a-robot",
version="v0.9.9", date="2026-06-08", read="4 min",
title="The intern is a robot and the robot needs SOPs",
desc="Agents are the most talented new hires in history and they show up knowing nothing about your company. Onboard them like you mean it.",
keywords="AI agents, SOPs, onboarding AI, knowledge architecture, context engineering",
related=["v1-1-the-tooling-changed", "v1-3-the-human-review-gate"],
svg_alt="A robot intern holding an enormous binder labeled SOP, with a sweat drop on its head",
svg_caption="Day one. The binder is load-bearing.",
svg=_svg(f'''
<circle cx="200" cy="105" r="46" fill="none" stroke="{G}" stroke-width="3"/>
<rect x="182" y="88" width="14" height="10" fill="{G}"/><rect x="212" y="88" width="14" height="10" fill="{G}"/>
<path d="M186 126 q18 12 36 0" stroke="{G}" stroke-width="3" fill="none"/>
<line x1="200" y1="59" x2="200" y2="40" stroke="{G}" stroke-width="3"/><circle cx="200" cy="34" r="6" fill="{A}"/>
<rect x="156" y="152" width="88" height="92" rx="8" fill="none" stroke="{G}" stroke-width="3"/>
<path d="M156 176 h-38 v50" stroke="{G}" stroke-width="3" fill="none"/>
<path d="M244 176 h38 v40" stroke="{G}" stroke-width="3" fill="none"/>
<rect x="300" y="150" width="200" height="110" rx="4" fill="none" stroke="{A}" stroke-width="4"/>
<line x1="330" y1="150" x2="330" y2="260" stroke="{A}" stroke-width="3"/>
<text x="415" y="196" fill="{A}" font-family="monospace" font-size="30" text-anchor="middle">SOP</text>
<text x="415" y="232" fill="{D}" font-family="monospace" font-size="15" text-anchor="middle">vol. 1 of 40</text>
<path d="M247 78 q14 20 2 30" stroke="{D}" stroke-width="3" fill="none"/><circle cx="249" cy="112" r="5" fill="{D}"/>
<text x="320" y="290" fill="{M}" font-family="monospace" font-size="13" text-anchor="middle">EMPLOYEE #007 — START DATE: TODAY — KNOWS: NOTHING (YET)</text>
'''),
body="""
<p>Every company I talk to this year is "hiring" the same intern. It has read the entire internet,
speaks forty languages, works around the clock and costs less per hour than the office coffee.
It is also, on day one, completely ignorant of the only thing that matters: <em>how your business
actually works.</em></p>
<p>Which vendor do we never use again and why. What "rush" means on a Friday versus a Tuesday. Why
invoice #4471 is different. The stuff that lives in the heads of your two most tired employees.</p>
<h2>The onboarding nobody does</h2>
<p>When I ran the knowledge base at Liberty Mutual — 200+ processes, 3,000+ users — the unglamorous
truth was that documentation quality determined automation quality, one to one. {link:v1-1-the-tooling-changed|Sixteen years later
the tooling changed and that rule didn't}. An agent grounded in stale, vague or contradictory process
docs will do the wrong thing with magnificent confidence.</p>
<p>So onboard the robot like a hire you're serious about. Write the SOPs it will read — not
aspirational corporate prose, but the real rules with the real exceptions. Give it the org chart of
systems: what's the source of truth for customers, for pricing, for inventory. Tell it what it's
<strong>not</strong> allowed to touch, and enforce that {link:v1-3-the-human-review-gate|with a gate, not a suggestion}.</p>
<h2>The upside of taking this seriously</h2>
<p>At the bakery I documented 40 SOPs mostly for humans, and years later that same discipline is what
makes businesses agent-ready. Companies that wrote things down are onboarding robots in a weekend.
Companies that ran on tribal knowledge are discovering the tribe has to write its memoirs first.</p>
<p>The intern is brilliant. The intern is eager. The intern will absolutely file your taxes in the
wrong country if the binder says to. Write the binder.</p>
<blockquote>Hot take from someone who's onboarded both: the robot reads the SOPs. That alone puts it
ahead of half my former coworkers.</blockquote>
"""),

dict(
slug="v0-9-5-snowplows-in-may",
version="v0.9.5", date="2026-05-04", read="4 min",
title="Snowplows in May: on building software for weather that isn't coming",
desc="My construction ERP has a full snow-operations dispatch module. It's 74°F. This is what seasonal systems teach you about architecture.",
keywords="snow operations software, seasonal systems, construction ERP, dispatch software, capacity planning",
related=["v1-0-my-resume-is-an-operating-system", "v0-2-0-the-40-dollar-server"],
svg_alt="A snowplow truck wearing sunglasses under a bright sun",
svg_caption="Fleet status: extremely ready. Forecast: brunch.",
svg=_svg(f'''
<circle cx="520" cy="70" r="34" fill="none" stroke="{A}" stroke-width="4"/>
<g stroke="{A}" stroke-width="3">
<line x1="520" y1="18" x2="520" y2="34"/><line x1="520" y1="106" x2="520" y2="122"/>
<line x1="468" y1="70" x2="484" y2="70"/><line x1="556" y1="70" x2="572" y2="70"/>
<line x1="483" y1="33" x2="494" y2="44"/><line x1="546" y1="96" x2="557" y2="107"/>
<line x1="557" y1="33" x2="546" y2="44"/><line x1="494" y1="96" x2="483" y2="107"/></g>
<rect x="130" y="150" width="200" height="80" rx="8" fill="none" stroke="{G}" stroke-width="4"/>
<rect x="330" y="175" width="90" height="55" fill="none" stroke="{G}" stroke-width="4"/>
<path d="M130 230 l-60 -50 v50 z" fill="none" stroke="{G}" stroke-width="4"/>
<circle cx="180" cy="245" r="20" fill="none" stroke="{G}" stroke-width="4"/>
<circle cx="370" cy="245" r="20" fill="none" stroke="{G}" stroke-width="4"/>
<rect x="196" y="166" width="60" height="26" rx="4" fill="none" stroke="{A}" stroke-width="3"/>
<rect x="200" y="170" width="24" height="18" fill="{A}"/><rect x="228" y="170" width="24" height="18" fill="{A}"/>
<line x1="224" y1="179" x2="228" y2="179" stroke="{A}" stroke-width="3"/>
<text x="240" y="286" fill="{M}" font-family="monospace" font-size="13" text-anchor="middle">SALT: 100% · ROUTES: OPTIMIZED · SNOW: 0"</text>
'''),
body="""
<p>It is a gorgeous May afternoon in Massachusetts and somewhere in my ERP, a snow-operations
dispatch module sits fully armed: properties, storm templates, route optimization, salt tracking,
reconciliation, certificates of insurance. Seventy-four degrees outside. The module does not care.
The module is <em>ready</em>.</p>
<p>People laugh when I demo it in spring. Then winter happens.</p>
<h2>What seasonal software teaches you</h2>
<p><strong>1. The busy season is the worst time to build.</strong> Snow contractors decide they need
software during the first storm, which is like deciding you need a parachute during the fall. The
whole module exists because we built it in July, tested it against last winter's data, and trained
the drivers before the first flake. When the storm came, the system was the boring part of the night.</p>
<p><strong>2. Dormant code is not dead code.</strong> A system that sleeps eight months a year still
has to wake up perfectly — with last season's properties, pricing and lessons intact. That's a data
architecture problem, and it's the same one behind {link:v0-2-0-the-40-dollar-server|every boring system that quietly outlives the flashy ones}.</p>
<p><strong>3. Peak load defines you.</strong> Ninety trucks, live GPS, salt logs and angry property
managers at 3 a.m. is the real spec. Design for the storm, and the sunny days are free.</p>
<p>There's an AI angle too, because there always is: storm response is a scheduling optimization
problem with terrible inputs, which makes it perfect agent territory — <em>propose</em> the routes,
let a dispatcher approve them. Even the weather gets a review gate.</p>
<blockquote>Build the plow in the summer. Ship the résumé before you need the job. Same principle,
different truck. Mine boots at <a href="https://ciprari.ai" target="_blank" rel="noopener">ciprari.ai</a>.</blockquote>
"""),

dict(
slug="v0-9-0-i-let-an-agent-answer-my-email",
version="v0.9.0", date="2026-04-06", read="5 min",
title="I let an agent answer my email for a week (supervised). Verdict: hired.",
desc="A carefully-gated experiment in agentic email triage. It drafted 61 replies, flagged 9, and only tried to be too polite to a scammer once.",
keywords="AI email agent, agentic AI experiment, email automation, human in the loop",
related=["v1-3-the-human-review-gate", "v1-5-agents-are-done-piloting"],
svg_alt="A robot on a winner's podium holding a trophy labeled INBOX 0",
svg_caption="The trophy is engraved 'INBOX ZERO'. The robot did not write its own acceptance speech. I checked.",
svg=_svg(f'''
<rect x="240" y="200" width="160" height="60" fill="none" stroke="{G}" stroke-width="4"/>
<rect x="120" y="230" width="120" height="30" fill="none" stroke="{D}" stroke-width="3"/>
<rect x="400" y="240" width="120" height="20" fill="none" stroke="{D}" stroke-width="3"/>
<text x="320" y="240" fill="{G}" font-family="monospace" font-size="24" text-anchor="middle">1</text>
<circle cx="320" cy="110" r="30" fill="none" stroke="{G}" stroke-width="3"/>
<rect x="308" y="100" width="9" height="7" fill="{G}"/><rect x="325" y="100" width="9" height="7" fill="{G}"/>
<line x1="312" y1="122" x2="330" y2="122" stroke="{G}" stroke-width="3"/>
<rect x="296" y="146" width="48" height="52" rx="6" fill="none" stroke="{G}" stroke-width="3"/>
<path d="M296 160 h-26 v-30" stroke="{G}" stroke-width="3" fill="none"/>
<path d="M344 160 h26 v-30" stroke="{G}" stroke-width="3" fill="none"/>
<path d="M252 104 h36 v26 h-36 z M252 104 l18 14 l18 -14" stroke="{A}" stroke-width="3" fill="none"/>
<path d="M352 104 h36 v26 h-36 z M352 104 l18 14 l18 -14" stroke="{A}" stroke-width="3" fill="none"/>
<text x="320" y="52" fill="{A}" font-family="monospace" font-size="20" text-anchor="middle">INBOX 0</text>
<text x="320" y="290" fill="{M}" font-family="monospace" font-size="13" text-anchor="middle">61 DRAFTED · 9 FLAGGED · 1 SCAMMER ALMOST THANKED</text>
'''),
body="""
<p>For one week in March, an agent read every email that hit my inbox, drafted replies, and queued
them for my approval. Rules of engagement: it could draft anything, send nothing.
{link:v1-3-the-human-review-gate|The gate stayed shut} — I reviewed every word before it left.</p>
<h2>The box score</h2>
<ul>
<li><strong>61 replies drafted.</strong> I sent 44 untouched, edited 15, rewrote 2. That edit rate is
better than some humans I've managed, and the humans didn't work at 6 a.m.</li>
<li><strong>9 correctly flagged as "you need to actually think about this one."</strong> Knowing what
<em>not</em> to answer is the skill. It had it.</li>
<li><strong>1 near-incident:</strong> it drafted a genuinely gracious reply to an obvious invoice
scam, thanking them for their patience. Polite to a fault. The fault was mine — my instructions said
"be warm to vendors" and it obeyed. Prompt fixed, lesson logged: agents don't have judgment,
they have <em>your</em> judgment, compiled.</li>
</ul>
<h2>What actually made it work</h2>
<p>Not the model. The scaffolding. It had my tone examples, my "who is this person" context, and
explicit escalation rules. In other words, the same onboarding
{link:v0-9-9-the-intern-is-a-robot|I'd give a human assistant}, minus the desk.</p>
<p>Net time saved: about four hours across the week, most of it in decision fatigue I didn't feel.
The inbox stopped being a to-do list written by strangers and became a queue of pre-chewed choices.
That's the honest pitch for agentic email in 2026 — not "never read email again," but "read it
like an executive instead of a clerk."</p>
<blockquote>Verdict: hired, with supervision, like everyone else on payroll. It even survived
{link:v1-5-agents-are-done-piloting|the only performance review that matters} — the task got done.</blockquote>
"""),

dict(
slug="v0-8-0-vibe-coding-has-a-change-order-problem",
version="v0.8.0", date="2026-03-09", read="5 min",
title="Vibe coding is real, and it has a change-order problem",
desc="Everyone can ship an app now. Construction figured out what happens next about a century ago: scope is the product.",
keywords="vibe coding, AI coding, scope creep, change orders, software estimation",
related=["v1-0-my-resume-is-an-operating-system", "v0-1-0-ai-that-reads-blueprints"],
svg_alt="A developer surfing a giant wave made of curly braces",
svg_caption="The wave is made of code. The board is made of confidence. Neither was estimated.",
svg=_svg(f'''
<path d="M40 240 q120 -160 240 -60 q60 50 120 10 q80 -50 200 30" fill="none" stroke="{G}" stroke-width="4"/>
<text x="150" y="150" fill="{D}" font-family="monospace" font-size="34">{{</text>
<text x="210" y="110" fill="{D}" font-family="monospace" font-size="26">}}</text>
<text x="260" y="170" fill="{D}" font-family="monospace" font-size="30">{{</text>
<text x="110" y="200" fill="{M}" font-family="monospace" font-size="22">{{}}</text>
<text x="330" y="140" fill="{M}" font-family="monospace" font-size="24">;</text>
<rect x="356" y="150" width="70" height="12" rx="6" fill="{A}" transform="rotate(-14 391 156)"/>
<circle cx="395" cy="112" r="14" fill="none" stroke="{G}" stroke-width="3"/>
<line x1="395" y1="126" x2="392" y2="150" stroke="{G}" stroke-width="3"/>
<line x1="392" y1="136" x2="372" y2="146" stroke="{G}" stroke-width="3"/>
<line x1="392" y1="136" x2="412" y2="144" stroke="{G}" stroke-width="3"/>
<text x="520" y="80" fill="{A}" font-family="monospace" font-size="15">scope:</text>
<text x="520" y="100" fill="{A}" font-family="monospace" font-size="15">"??"</text>
<text x="320" y="288" fill="{M}" font-family="monospace" font-size="13" text-anchor="middle">DAY 1: "SIMPLE APP" — DAY 9: DISTRIBUTED SYSTEM WITH FEELINGS</text>
'''),
body="""
<p>Vibe coding — describing software into existence and riding whatever the model gives you — is
genuinely here. My {link:v1-0-my-resume-is-an-operating-system|résumé has an app builder in it}
partly to make that point: type a sentence, get a working game. The barrier to <em>starting</em>
software has collapsed. Wonderful. Now let me tell you about the barrier that didn't move.</p>
<h2>Construction already ran this experiment</h2>
<p>My day job is a construction portfolio, an industry that has known for a century that the hard
part isn't building — it's <strong>agreeing on what's being built</strong>. That's why change orders
exist: a formal, priced, signed acknowledgment that the scope moved. No handshake amnesia. No
"while you're at it." Paper trail or it didn't happen.</p>
<p>Vibe coding has no change orders. Every prompt is a scope change nobody prices. "Simple inventory
tracker" becomes multi-user becomes needs-auth becomes syncs-with-QuickBooks, and each step feels
free because the code appears instantly. The code was never the cost. The cost is the maintenance,
the data model you locked in on day two, and the expectations you set with whoever's paying.</p>
<h2>How I vibe-code without the hangover</h2>
<ul>
<li><strong>Write the scope sentence first.</strong> One sentence, what it does, who it's for. When
the prompt drifts from the sentence, that's a change order — decide on purpose.</li>
<li><strong>Data model by hand, vibes for the rest.</strong> {link:v0-1-0-ai-that-reads-blueprints|The blueprint is the building}.
Schemas are cheap to draw and brutal to migrate.</li>
<li><strong>Timebox the magic.</strong> If generation is instant, iteration is where the week goes.
Budget iterations like you'd budget concrete.</li>
</ul>
<blockquote>The models made writing code fast. They made deciding what to build exactly zero percent
faster. That ratio is the whole modern software business.</blockquote>
"""),

dict(
slug="v0-7-0-the-pizzeria-turing-test",
version="v0.7.0", date="2026-02-09", read="4 min",
title="The Pizzeria Turing Test",
desc="Forget benchmarks. If your system survives a Friday dinner rush with one oven down and a Little League team walking in, it's intelligent.",
keywords="AI benchmarks, real world AI, restaurant operations, systems under load, Naples Pizzeria",
related=["v1-2-integrate-before-you-replace", "v1-4-adoption-is-the-deliverable"],
svg_alt="A pizza slice with a thought bubble asking AGI?",
svg_caption="The slice has seen a Friday rush. The benchmark has not.",
svg=_svg(f'''
<path d="M200 250 L320 70 L440 250 Z" fill="none" stroke="{A}" stroke-width="4"/>
<path d="M232 202 q88 40 176 0" fill="none" stroke="{A}" stroke-width="3"/>
<circle cx="300" cy="160" r="11" fill="none" stroke="{G}" stroke-width="3"/>
<circle cx="345" cy="190" r="11" fill="none" stroke="{G}" stroke-width="3"/>
<circle cx="310" cy="215" r="11" fill="none" stroke="{G}" stroke-width="3"/>
<circle cx="470" cy="110" r="6" fill="{D}"/><circle cx="492" cy="88" r="9" fill="{D}"/>
<ellipse cx="540" cy="60" rx="58" ry="30" fill="none" stroke="{D}" stroke-width="3"/>
<text x="540" y="68" fill="{G}" font-family="monospace" font-size="20" text-anchor="middle">AGI?</text>
<g stroke="{D}" stroke-width="3"><line x1="240" y1="105" x2="228" y2="85"/><line x1="270" y1="92" x2="262" y2="70"/><line x1="300" y1="85" x2="298" y2="62"/></g>
<text x="320" y="290" fill="{M}" font-family="monospace" font-size="13" text-anchor="middle">BENCHMARK: FRI 18:00 · COVERS: 212 · OVENS: 1 OF 2 · TEARS: 0</text>
'''),
body="""
<p>Every few weeks the industry invents a new benchmark, and every few weeks I think about the only
one that's ever predicted anything for me: <strong>Friday night at Naples Pizzeria, one oven down,
a Little League team of fourteen walking in at 6:40 without a reservation.</strong></p>
<p>I ran that restaurant for three years — $1.2M a year through a kitchen the size of a minivan.
Any system, human or software, that survives that environment has demonstrated intelligence in the
only sense that pays: it produced correct decisions, under load, with degraded inputs, while
everything screamed.</p>
<h2>What the rush selects for</h2>
<p><strong>Graceful degradation.</strong> One oven means the menu just changed, whether the menu
knows it or not. Systems that only work at 100% capacity don't work.
<strong>Prioritization under ambiguity.</strong> The dough guy called out; do you 86 calzones now or
risk it? Waiting for perfect information is itself a decision, usually the worst one.
<strong>State that survives interruption.</strong> Fourteen orders in flight and the phone rings.
Where were we? A kitchen that can't answer that is a kitchen going down, and so is a workflow.</p>
<p>When I later {link:v1-2-integrate-before-you-replace|wired a bakery's POS, inventory and finance together},
that's what I was really building: a system that answers "where were we?" instantly, forever.</p>
<h2>The test, formalized</h2>
<p>Take any agent, any workflow, any dashboard, and ask: what happens at 130% volume with one
critical resource missing and a VIP edge case walking in the door? If the answer involves the phrase
"that shouldn't happen," it will happen Friday. {link:v1-4-adoption-is-the-deliverable|And whether people still trust it Saturday}
is the retention benchmark.</p>
<blockquote>AGI definitions come and go. "Can it run the pass on a Friday" has never once misled me.</blockquote>
"""),

dict(
slug="v0-6-0-new-year-new-model",
version="v0.6.0", date="2026-01-12", read="4 min",
title="New Year, New Model: resolutions from every corner of the AI industry",
desc="Leaked* New Year's resolutions from the models, the labs, the enterprises and one construction guy. (*written by the construction guy)",
keywords="AI satire, AI industry 2026, new year resolutions, AI humor",
related=["v0-5-1-patch-notes-christmas", "v1-5-agents-are-done-piloting"],
svg_alt="A robot running on a treadmill with a falling loss curve on a screen",
svg_caption="The robot's resolution is to reduce loss. Same, honestly.",
svg=_svg(f'''
<rect x="120" y="230" width="240" height="18" rx="9" fill="none" stroke="{G}" stroke-width="3"/>
<line x1="150" y1="248" x2="140" y2="270" stroke="{G}" stroke-width="3"/>
<line x1="330" y1="248" x2="340" y2="270" stroke="{G}" stroke-width="3"/>
<circle cx="240" cy="120" r="22" fill="none" stroke="{G}" stroke-width="3"/>
<rect x="231" y="112" width="7" height="6" fill="{G}"/><rect x="243" y="112" width="7" height="6" fill="{G}"/>
<rect x="222" y="146" width="36" height="44" rx="6" fill="none" stroke="{G}" stroke-width="3"/>
<path d="M222 158 l-24 18" stroke="{G}" stroke-width="3"/>
<path d="M258 158 l26 -12" stroke="{G}" stroke-width="3"/>
<path d="M230 190 l-14 32" stroke="{G}" stroke-width="3"/>
<path d="M250 190 l16 30" stroke="{G}" stroke-width="3"/>
<rect x="420" y="80" width="160" height="110" fill="none" stroke="{A}" stroke-width="3"/>
<path d="M436 104 q40 40 60 46 q40 12 64 28" fill="none" stroke="{G}" stroke-width="3"/>
<text x="500" y="72" fill="{A}" font-family="monospace" font-size="15" text-anchor="middle">loss ↓</text>
<text x="320" y="290" fill="{M}" font-family="monospace" font-size="13" text-anchor="middle">GOAL: GENERALIZE · STRETCH GOAL: STOP APOLOGIZING SO MUCH</text>
'''),
body="""
<p>January: the month every gym is full and every AI lab publishes a roadmap. In the spirit of the
season, I've obtained* the industry's New Year's resolutions. (*Made them up. But you'll recognize
everyone.)</p>
<h2>The resolutions</h2>
<p><strong>The frontier model:</strong> "This year I will stop beginning every answer with
'Great question!' I will say 'I don't know' at least once. I will not invent a court case."</p>
<p><strong>The AI lab:</strong> "We resolve to name our next model something a normal person can
remember. We acknowledge that our last release was called something like Orion-o4-mini-high-turbo
and that our own staff calls it 'the new one.'"</p>
<p><strong>The enterprise:</strong> "This year we will move at least one of our forty-seven pilots
to production. We will stop calling the innovation lab 'the innovation lab.' We will admit the
chatbot on our website is a PDF in a trench coat."</p>
<p><strong>The consultant:</strong> "I resolve to include at least one slide with a number on it."</p>
<p><strong>The doomer and the accelerationist (joint statement):</strong> "We resolve to keep
arguing on the internet so the rest of you don't have to."</p>
<p><strong>The construction guy with an ERP</strong> (hi): "I resolve to keep shipping the boring
version that works — {link:v1-5-agents-are-done-piloting|agents that finish tasks}, gates that stay
shut, {link:v0-5-1-patch-notes-christmas|and a public list of my own bugs}, because the industry has
enough roadmaps and not enough changelogs."</p>
<h2>The one serious paragraph</h2>
<p>Resolutions fail when they're identities instead of systems — "become an AI company" versus
"automate these six workflows and measure them." Businesses are no different in January than people
are. Pick the six workflows. Write them down. Check back in March. That's the whole trick, and it's
this blog's entire editorial policy.</p>
<blockquote>New year, same architecture. That's a feature.</blockquote>
"""),

dict(
slug="v0-5-1-patch-notes-christmas",
version="v0.5.1", date="2025-12-22", read="4 min",
title="PATCH NOTES, Christmas edition: bugs I shipped in 2025",
desc="A year-end confession log. Every system I built this year had at least one bug worth publicly apologizing for. Here are the greatest hits.",
keywords="patch notes, postmortem, software bugs, year in review, engineering humility",
related=["v1-0-my-resume-is-an-operating-system", "v0-4-0-my-smart-home-becomes-sentient"],
svg_alt="A cartoon bug wearing a Santa hat sitting inside an open gift box",
svg_caption="It's not a bug, it's a present. It was a bug.",
svg=_svg(f'''
<rect x="240" y="170" width="160" height="90" fill="none" stroke="{A}" stroke-width="4"/>
<rect x="224" y="146" width="192" height="26" fill="none" stroke="{A}" stroke-width="4"/>
<line x1="320" y1="146" x2="320" y2="260" stroke="{A}" stroke-width="3"/>
<ellipse cx="320" cy="120" rx="34" ry="26" fill="none" stroke="{G}" stroke-width="3"/>
<circle cx="308" cy="112" r="4" fill="{G}"/><circle cx="332" cy="112" r="4" fill="{G}"/>
<g stroke="{G}" stroke-width="3"><line x1="286" y1="110" x2="266" y2="100"/><line x1="286" y1="124" x2="266" y2="130"/>
<line x1="354" y1="110" x2="374" y2="100"/><line x1="354" y1="124" x2="374" y2="130"/></g>
<path d="M300 100 q4 -26 34 -30 l4 12 q-22 4 -26 22 z" fill="{D}"/>
<circle cx="340" cy="78" r="8" fill="#fff" opacity="0.85"/>
<path d="M296 96 q24 -14 48 0" stroke="{D}" stroke-width="3" fill="none"/>
<text x="320" y="290" fill="{M}" font-family="monospace" font-size="13" text-anchor="middle">SEVERITY: FESTIVE · STATUS: WONTFIX UNTIL JANUARY</text>
'''),
body="""
<p>Tradition says December is for highlight reels. This is a changelog; we do patch notes. Here are
the bugs I actually shipped in 2025, rated by how long they survived and how loudly they were
discovered.</p>
<h2>Selected incidents</h2>
<p><strong>The Payroll Rounding Incident (fixed in 34 minutes).</strong> A mapping between time
entries and payroll rounded in the employees' favor. I want to be clear that no employee reported
this bug. Detection: my own reconciliation job, which exists because
{link:v1-0-my-resume-is-an-operating-system|I don't trust anything I build until it's watched}.</p>
<p><strong>The Overly Honest Chatbot (fixed same day).</strong> An early ColeAI prompt, asked
"what's Cole's biggest weakness," answered with what I can only describe as accurate. The review
gate exists for writes; apparently it also needed to exist for candor.</p>
<p><strong>The 2 A.M. Scene (fixed after one very confusing night).</strong>
{link:v0-4-0-my-smart-home-becomes-sentient|My smart-home platform} decided "movie night" was an
appropriate response to a motion event at 2:11 a.m. The lights dimmed. The TV woke. I aged.</p>
<p><strong>The Quote That Grew (caught in review).</strong> An AI-drafted estimate confidently
included a line item for a service we don't offer. The human at the gate laughed, deleted it, and
that laugh is the entire business case for human review.</p>
<h2>Why publish this</h2>
<p>Because every vendor deck you'll see in January is a list of things that went right, and you
should not trust anyone who ships software and has no list of things that went wrong. Bugs aren't
the shame. Undetected bugs are. Every incident above was caught by instrumentation, reconciliation,
or a human gate — the boring trio that turns mistakes into patch notes instead of lawsuits.</p>
<blockquote>Merry Christmas. May your logs be verbose and your rollbacks unnecessary.</blockquote>
"""),

dict(
slug="v0-5-0-measured-in-gigawatts",
version="v0.5.0", date="2025-12-01", read="5 min",
title="We measure AI in gigawatts now",
desc="The industry's favorite unit quietly changed from parameters to power. What datacenter buildouts look like from inside an industry that pours actual concrete.",
keywords="AI datacenters, gigawatts, AI infrastructure, construction, energy",
related=["v0-2-0-the-40-dollar-server", "v1-1-the-tooling-changed"],
svg_alt="A GPU chip wearing a construction hard hat, with power pylons behind it",
svg_caption="The GPU passed its OSHA training. The grid is still reviewing the paperwork.",
svg=_svg(f'''
<g stroke="{D}" stroke-width="3" fill="none">
<path d="M80 250 l30 -120 l30 120 M86 200 h48 M92 165 h36"/>
<path d="M500 250 l30 -120 l30 120 M506 200 h48 M512 165 h36"/>
<path d="M140 150 q90 -40 180 -18 M320 132 q100 -22 180 8" stroke-dasharray="6 7"/></g>
<rect x="240" y="150" width="160" height="100" rx="6" fill="none" stroke="{G}" stroke-width="4"/>
<g stroke="{G}" stroke-width="3">
<line x1="256" y1="250" x2="256" y2="268"/><line x1="288" y1="250" x2="288" y2="268"/>
<line x1="320" y1="250" x2="320" y2="268"/><line x1="352" y1="250" x2="352" y2="268"/><line x1="384" y1="250" x2="384" y2="268"/></g>
<rect x="268" y="176" width="104" height="48" fill="none" stroke="{G}" stroke-width="3"/>
<text x="320" y="206" fill="{G}" font-family="monospace" font-size="17" text-anchor="middle">GPU</text>
<path d="M258 150 q0 -34 62 -34 q62 0 62 34 z" fill="{A}"/>
<rect x="304" y="102" width="32" height="14" rx="4" fill="{A}"/>
<text x="320" y="290" fill="{M}" font-family="monospace" font-size="13" text-anchor="middle">CAPACITY: YES · SCHEDULE: OPTIMISTIC · COFFEE: CRITICAL PATH</text>
'''),
body="""
<p>Sometime this year the AI industry changed its favorite unit without holding a ceremony.
Nobody brags about parameters anymore. The number that matters now is <strong>gigawatts</strong> —
how much electricity your datacenter campus can drink. Model announcements read like utility
filings. I find this hilarious for a specific personal reason: I work in construction, the industry
that has to actually build all of this.</p>
<h2>Welcome to our world</h2>
<p>Tech spent decades enjoying software margins and thinking of the physical world as a solved
problem handled by other people. Now the frontier of artificial intelligence is gated by:
land, permits, transformers, transmission lines, water, concrete cure times and the availability of
electricians. Every construction PM on Earth just poured a coffee and smiled.</p>
<p>Here's what my industry knows that the gigawatt race is relearning in public:
<strong>the schedule is the product.</strong> A datacenter that lands two quarters late in this
market didn't lose two quarters — it lost the window. And schedules die the same way buildings do:
not from one catastrophe but from forty small unmanaged dependencies. The trade that doesn't show,
the inspection that slips, the transformer with a 30-month lead time nobody escalated.
{link:v1-1-the-tooling-changed|That's a coordination problem}, and coordination problems are
exactly what I point systems at all day: standardized schedule data, dependency visibility,
change-order discipline, one source of truth.</p>
<h2>The odd, honest upside</h2>
<p>AI is now creating an enormous amount of extremely traditional work — steel, concrete, HVAC at
absurd scale, and the grid upgrades everyone deferred for twenty years. The most futuristic
industry on the planet is bottlenecked by the oldest ones, and the oldest ones could use better
software. Conveniently, {link:v0-2-0-the-40-dollar-server|the software that helps doesn't need to be glamorous} —
it needs to be up.</p>
<blockquote>Parameters impress benchmarks. Gigawatts impress the grid operator, the county
inspector, and reality. We measure in reality now. Good.</blockquote>
"""),

dict(
slug="v0-4-0-my-smart-home-becomes-sentient",
version="v0.4.0", date="2025-11-03", read="4 min",
title="Notes from building Aurora, or: my house has opinions now",
desc="I built a smart-home and media control platform. The entities are modeled beautifully. The lamp still turns on when nobody asked.",
keywords="smart home, home automation, Base44, entity modeling, IPTV, Aurora",
related=["v0-5-1-patch-notes-christmas", "v1-2-integrate-before-you-replace"],
svg_alt="A desk lamp with cartoon eyes looking at a scared cat, with a speech bubble saying scene: cozy?",
svg_caption="Scene: 'cozy' activated with 97% confidence. The cat disagrees. The cat lacks admin rights.",
svg=_svg(f'''
<path d="M180 250 h120" stroke="{G}" stroke-width="4"/>
<path d="M240 250 l-14 -70 l50 -44" stroke="{G}" stroke-width="4" fill="none"/>
<path d="M276 136 l44 22 l-20 40 l-46 -22 z" fill="none" stroke="{G}" stroke-width="4"/>
<circle cx="292" cy="158" r="5" fill="{A}"/><circle cx="308" cy="166" r="5" fill="{A}"/>
<g stroke="{A}" stroke-width="3"><line x1="330" y1="150" x2="356" y2="136"/><line x1="336" y1="170" x2="364" y2="168"/><line x1="326" y1="190" x2="350" y2="202"/></g>
<ellipse cx="470" cy="236" rx="46" ry="24" fill="none" stroke="{D}" stroke-width="3"/>
<circle cx="502" cy="212" r="16" fill="none" stroke="{D}" stroke-width="3"/>
<path d="M492 200 l-6 -10 l10 4 z M512 200 l6 -10 l-10 4 z" fill="{D}"/>
<path d="M424 230 q-18 -6 -22 -22" stroke="{D}" stroke-width="3" fill="none"/>
<ellipse cx="430" cy="110" rx="66" ry="26" fill="none" stroke="{D}" stroke-width="3"/>
<text x="430" y="117" fill="{G}" font-family="monospace" font-size="15" text-anchor="middle">scene: cozy?</text>
<text x="320" y="290" fill="{M}" font-family="monospace" font-size="13" text-anchor="middle">DEVICES: 47 · SCENES: 12 · CAT TRUST LEVEL: DEGRADED</text>
'''),
body="""
<p>Aurora started as a reasonable idea: one control plane for the TV channels, the devices, the
scenes, the lists — a proper entity model instead of six vendor apps having six opinions. Channels,
devices, scenes and schedules as first-class records with state machines. The data modeling is,
if I say so myself, lovely. {link:v1-2-integrate-before-you-replace|Integration layer over rip-and-replace},
as always.</p>
<p>And yet. At some point every home automation project crosses a line where the house stops being
automated and starts being <em>opinionated</em>.</p>
<h2>Field observations</h2>
<p>A scene named "cozy" is a hypothesis about human intent, and hypotheses fail. Motion sensors are
honest but stupid: they report that <em>something</em> moved, and the cat is something. State
drift is real — the platform believes the living room lamp is off, the lamp believes otherwise,
and reconciling belief with reality is the actual job. If that sentence sounds like every ERP
integration I've ever done, congratulations, you've spotted the pattern: <strong>a smart home is
just a tiny enterprise with worse stakeholders.</strong> Sources of truth, event ordering, retries,
idempotency. The lamp is a microservice. The cat is chaos engineering.</p>
<h2>What made it actually good</h2>
<p>The same thing that fixes enterprises: fewer, better abstractions. Scenes became small and
composable instead of grand and psychic. Every automation got a manual override that always wins —
{link:v0-5-1-patch-notes-christmas|after the 2 a.m. movie-night incident}, the household review
gate is a physical switch. Adoption, it turns out, applies at home too: the system that wins is
the one your family actually uses, and my family uses the wall switch. I've made peace with that.
Mostly.</p>
<blockquote>Entity modeling: impeccable. Scene inference: humbling. Cat: unconvinced. Ship it.</blockquote>
"""),

dict(
slug="v0-3-0-mcp-usb-c-of-ai",
version="v0.3.0", date="2025-10-06", read="4 min",
title="MCP is the USB-C of AI, and yes, that includes the part where we all fought about it first",
desc="Model Context Protocol went from spec to default in about a year. A field guide to why boring protocols win, from someone whose job is gluing systems together.",
keywords="MCP, Model Context Protocol, AI integrations, API standards, interoperability",
related=["v0-9-9-the-intern-is-a-robot", "v1-2-integrate-before-you-replace"],
svg_alt="A USB connector being flipped three times over a socket, with attempt counter",
svg_caption="Attempt 1: wrong. Attempt 2: wrong. Attempt 3: the same side as attempt 1, somehow correct.",
svg=_svg(f'''
<rect x="120" y="70" width="90" height="44" rx="8" fill="none" stroke="{G}" stroke-width="4"/>
<rect x="150" y="84" width="60" height="16" fill="{G}" opacity="0.5"/>
<text x="165" y="140" fill="{M}" font-family="monospace" font-size="13" text-anchor="middle">attempt 1 ✗</text>
<rect x="280" y="70" width="90" height="44" rx="8" fill="none" stroke="{G}" stroke-width="4" transform="rotate(180 325 92)"/>
<rect x="290" y="84" width="60" height="16" fill="{G}" opacity="0.5"/>
<text x="325" y="140" fill="{M}" font-family="monospace" font-size="13" text-anchor="middle">attempt 2 ✗</text>
<rect x="440" y="70" width="90" height="44" rx="8" fill="none" stroke="{A}" stroke-width="4"/>
<rect x="470" y="84" width="60" height="16" fill="{A}" opacity="0.6"/>
<text x="485" y="140" fill="{A}" font-family="monospace" font-size="13" text-anchor="middle">attempt 3 ✓</text>
<rect x="250" y="196" width="140" height="34" rx="6" fill="none" stroke="{G}" stroke-width="4"/>
<rect x="290" y="204" width="60" height="18" fill="none" stroke="{G}" stroke-width="3"/>
<g stroke="{D}" stroke-width="3"><line x1="320" y1="160" x2="320" y2="190"/><path d="M312 182 l8 10 l8 -10" fill="none"/></g>
<text x="320" y="290" fill="{M}" font-family="monospace" font-size="13" text-anchor="middle">UNIVERSAL PORT · UNIVERSAL CONFUSION · EVENTUAL UNIVERSAL PEACE</text>
'''),
body="""
<p>Once a decade the software industry accidentally agrees on something. This time it's MCP — the
Model Context Protocol — which went from "interesting spec" to "the port everything ships with"
fast enough to give integration consultants whiplash. As a person whose career is
{link:v1-2-integrate-before-you-replace|professionally gluing systems together}, I have feelings.</p>
<h2>Why boring protocols win</h2>
<p>Before USB, connecting a printer was a religious experience involving serial ports and prayer.
Before MCP, connecting an AI to your tools meant writing a bespoke adapter per model per tool —
N×M integrations, the same trap enterprise software spent thirty years paying for. The fix is
always the same and always unglamorous: <strong>agree on the plug.</strong> One protocol for
"here are my tools, here's how to call them," and suddenly the ecosystem compounds instead of
fragmenting.</p>
<p>The USB-C comparison is more honest than it sounds, because USB-C's history includes years of
cables that looked identical and did wildly different things. MCP is living that phase now: servers
of gloriously variable quality, security models ranging from thoughtful to vibes, and everyone
shipping "MCP support" the way monitors once shipped "HD ready." The plug being standard doesn't
make the thing behind the plug good. Ask {link:v0-9-9-the-intern-is-a-robot|any robot intern} what
happens when a standardized connector delivers unstandardized nonsense.</p>
<h2>The operator's takeaway</h2>
<p>Standard ports move the value. When connection is free, the premium shifts to what you connect:
clean data, well-described tools, permissions that mean something. Companies with tidy systems get
agent-ready almost overnight; companies with chaos get the chaos, faster, through a nicer plug.</p>
<blockquote>It still takes three tries to plug anything in. Some constants transcend protocol
versions.</blockquote>
"""),

dict(
slug="v0-2-0-the-40-dollar-server",
version="v0.2.0", date="2025-09-08", read="4 min",
title="Ode to the $40 server that outlived three enterprise platforms",
desc="A love letter to boring infrastructure, dusty hardware, and the uptime nobody puts on a slide.",
keywords="boring technology, infrastructure, uptime, small business IT, reliability",
related=["v0-5-0-measured-in-gigawatts", "v1-1-the-tooling-changed"],
svg_alt="A small dusty server with a first-place medal, flanked by two large fallen enterprise racks",
svg_caption="Left: $2M platform (2019–2021). Right: $3M platform (2021–2023). Center: still taking requests.",
svg=_svg(f'''
<rect x="70" y="120" width="120" height="140" fill="none" stroke="{M}" stroke-width="3" transform="rotate(-8 130 190)"/>
<line x1="84" y1="150" x2="176" y2="136" stroke="{M}" stroke-width="2"/>
<line x1="86" y1="176" x2="178" y2="162" stroke="{M}" stroke-width="2"/>
<text x="128" y="286" fill="{M}" font-family="monospace" font-size="12" text-anchor="middle">RIP 2021</text>
<rect x="450" y="126" width="120" height="134" fill="none" stroke="{M}" stroke-width="3" transform="rotate(7 510 193)"/>
<line x1="466" y1="156" x2="556" y2="168" stroke="{M}" stroke-width="2"/>
<text x="512" y="286" fill="{M}" font-family="monospace" font-size="12" text-anchor="middle">RIP 2023</text>
<rect x="270" y="170" width="100" height="70" rx="4" fill="none" stroke="{G}" stroke-width="4"/>
<circle cx="288" cy="188" r="4" fill="{G}"/><circle cx="288" cy="206" r="4" fill="{A}"/>
<line x1="304" y1="188" x2="352" y2="188" stroke="{D}" stroke-width="3"/>
<line x1="304" y1="206" x2="340" y2="206" stroke="{D}" stroke-width="3"/>
<circle cx="320" cy="120" r="24" fill="none" stroke="{A}" stroke-width="4"/>
<text x="320" y="128" fill="{A}" font-family="monospace" font-size="20" text-anchor="middle">1</text>
<path d="M306 138 l-8 20 M334 138 l8 20" stroke="{A}" stroke-width="4"/>
<path d="M256 176 q-10 -8 -6 -18 M262 240 q-12 6 -20 0" stroke="{M}" stroke-width="2" fill="none"/>
<text x="320" y="290" fill="{M}" font-family="monospace" font-size="13" text-anchor="middle">UPTIME: 2,847 DAYS · FANS: LOUD · SHAME: NONE</text>
'''),
body="""
<p>In a rental equipment office in Massachusetts there was a beige machine I bought for roughly the
price of a nice dinner. It ran the label printer integration, a scheduled export, and one cron job
whose original author is lost to history. During my six years managing that infrastructure, it
outlived two flagship platform migrations and watched a third struggle. It asked for nothing but a
vacuuming it never received.</p>
<h2>What the beige box knew</h2>
<p><strong>Uptime is a function of ambition.</strong> The box did three things. The platforms did
three hundred, and each one was a new way to be down.
<strong>Fewer dependencies, fewer funerals.</strong> The box depended on power and one network
drive. The platforms depended on vendors who had roadmap meetings about deprecating them.
<strong>Nobody's résumé needed the box.</strong> No one ever got promoted for replacing it, so no
one ever broke it. There's an entire theory of enterprise IT hiding in that sentence.</p>
<p>I'm not romantic about old hardware — I've {link:v1-1-the-tooling-changed|automated with every
generation of tooling since 2010} and I'll take today's stack every time. The lesson isn't "don't
modernize." It's that <em>reliability comes from scope discipline, not from newness.</em> When I
consolidated that company's licenses and contracts into one tracked registry — $30K a year in
savings, 98% asset utilization — the boring registry beat the exciting platform for the same reason
the beige box beat everything: it did one job completely.</p>
<p>Meanwhile the industry is {link:v0-5-0-measured-in-gigawatts|measuring itself in gigawatts}, and
somewhere in every gleaming new datacenter there is already a beige-box-equivalent — some small
service everyone forgot — quietly holding the whole thing up. Find yours. Vacuum it. Thank it.</p>
<blockquote>Uptime: 2,847 days. Slide decks featuring it: zero. Correlation: probably causal.</blockquote>
"""),

dict(
slug="v0-1-0-ai-that-reads-blueprints",
version="v0.1.0", date="2025-08-18", read="5 min",
title="I taught an AI to read blueprints. It has notes about our handwriting.",
desc="The origin story of the takeoff-analysis agent: what happens when a language model meets thirty years of construction-document tradition.",
keywords="AI takeoff analysis, construction AI, document extraction, blueprints, agentic AI",
related=["v0-8-0-vibe-coding-has-a-change-order-problem", "v1-3-the-human-review-gate"],
svg_alt="A robot examining a blueprint with a magnifying glass; a grade of 2 out of 10 for handwriting floats nearby",
svg_caption="The takeoff was accurate. The margin comments were 'illegible but confident.'",
svg=_svg(f'''
<rect x="110" y="90" width="240" height="160" fill="none" stroke="{D}" stroke-width="3"/>
<g stroke="{D}" stroke-width="2">
<line x1="130" y1="120" x2="320" y2="120"/><line x1="130" y1="150" x2="270" y2="150"/>
<rect x="140" y="170" width="70" height="50" fill="none"/><rect x="230" y="170" width="90" height="30" fill="none"/>
<path d="M255 120 q14 -18 30 0" fill="none"/></g>
<circle cx="440" cy="120" r="30" fill="none" stroke="{G}" stroke-width="3"/>
<rect x="428" y="110" width="9" height="7" fill="{G}"/><rect x="444" y="110" width="9" height="7" fill="{G}"/>
<line x1="432" y1="134" x2="450" y2="134" stroke="{G}" stroke-width="3"/>
<rect x="416" y="156" width="48" height="60" rx="6" fill="none" stroke="{G}" stroke-width="3"/>
<circle cx="376" cy="192" r="26" fill="none" stroke="{A}" stroke-width="4"/>
<line x1="394" y1="212" x2="416" y2="236" stroke="{A}" stroke-width="4"/>
<path d="M416 176 l-14 8" stroke="{G}" stroke-width="3"/>
<text x="520" y="90" fill="{A}" font-family="monospace" font-size="16">handwriting:</text>
<text x="545" y="112" fill="{A}" font-family="monospace" font-size="20">2/10</text>
<text x="320" y="290" fill="{M}" font-family="monospace" font-size="13" text-anchor="middle">SHEET A-101 · SCALE: ALLEGEDLY 1/4" · COFFEE STAIN: STRUCTURAL</text>
'''),
body="""
<p>This is the origin story of the most quietly useful agent I run: the one that does takeoff
analysis — reading construction documents and extracting the scope of work and materials before a
human estimator spends a day doing it by highlighter.</p>
<p>Construction documents are a hostile environment for machine intelligence. Thirty-page drawing
sets where the critical detail lives in a margin note. Revision clouds stacked on revision clouds.
Abbreviations that mean different things on different sheets. A coffee stain that has been
photocopied so many times it now appears to be a design element. Into this walked a language model
with the confidence of a straight-A student on the first day of a job site.</p>
<h2>What happened</h2>
<p>First pass: it read the clean sheets beautifully and hallucinated politely on the messy ones —
{link:v0-8-0-vibe-coding-has-a-change-order-problem|confidence unbudgeted by accuracy}. So we did
what you do with any promising estimator: gave it structure. Per-line confidence scores. A rule
that "not legible" is a valid and honorable answer. Cross-checks between the drawings and the spec
book, because when they disagree — and they disagree — that's not an error, that's a
<strong>finding</strong>, and findings make money.</p>
<p>Second pass, with {link:v1-3-the-human-review-gate|a human estimator reviewing every line}: hours
of highlighter work compressed to a review that takes minutes, plus a bonus nobody priced — the
agent flags scope gaps between drawings and specs that a tired human skims past. It once caught a
door schedule referencing hardware the spec never included. That single catch paid for the
experiment.</p>
<h2>The moral</h2>
<p>AI didn't replace the estimator. It replaced the highlighter. The estimator got promoted to
judge — which was always the valuable part of the job. And the model's only complaint, expressed
through confidence scores, is our industry's handwriting. Fair. It's earned that note.</p>
<blockquote>Grade from the robot: scope, extracted; quantities, itemized; handwriting, 2/10,
"illegible but confident." The robot fits right in here.</blockquote>
"""),
]
