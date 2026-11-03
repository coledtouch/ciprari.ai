"""Offline checks for the humanizer lint and its one revision pass (no API calls)."""
import contextlib
import io
import json
import os
import re
import tempfile
import unittest
from unittest.mock import patch
import writer

LINK = '<a href="https://example.com/a">a source</a> and <a href="https://example.com/b">another</a>'


def post(body, title="The estimator learned a new trick", desc="Short line one. Short line two.",
         caption="One dry line."):
    return {"title": title, "desc": desc, "svg_caption": caption, "body_html": body}


def stored(version):
    """A published post as a draft. Old posts never change, so their sentences make stable cases."""
    p = next(p for p in writer.ALL if p["version"] == version)
    return {"title": p["title"], "desc": p["desc"], "svg_caption": p["svg_caption"],
            "svg_inner": p["svg"], "body_html": p["body"]}


class LintTests(unittest.TestCase):
    def probs(self, body, **kw):
        return writer.humanizer_problems(post(body, **kw))

    def test_clean_post_has_no_problems(self):
        body = (f"<p>I read {LINK} this morning. The estimator now prices decks in nine seconds.</p>"
                "<h3>What changed in the queue</h3><p>Payroll lands or it doesn't.</p>"
                "<blockquote>The robot counts joists faster than I do.</blockquote>")
        self.assertEqual(self.probs(body), [])

    def test_banned_words_and_inflections(self):
        found = self.probs("<p>This crucial update enhanced the showcased landscape.</p>")
        self.assertEqual(sorted(p.split('"')[1].lower() for p in found if "banned" in p),
                         ["crucial", "enhanced", "landscape", "showcased"])
        self.assertEqual(self.probs("<p>The landscaping crew ships Monday.</p>"), [])

    def test_sentence_length(self):
        sixteen = " ".join(["word"] * 15) + " end."
        self.assertEqual(self.probs(f"<p>{sixteen}</p>"), [])
        found = self.probs(f"<p>{sixteen[:-1]} plus.</p>")
        self.assertTrue(any("17-word sentence" in p for p in found), found)

    def test_heading_does_not_run_into_the_paragraph(self):
        heading = " ".join(["Head"] * 10)
        self.assertEqual(self.probs(f"<h3>{heading}</h3><p>{' '.join(['body'] * 10)}.</p>"), [])

    def test_crosslink_macro_counts_anchor_words_only(self):
        body = "<p>See {link:v1-50-0-some-long-slug-here|the old post} for the rest of it.</p>"
        self.assertEqual(self.probs(body), [])

    def test_contrast_structures(self):
        for text in ("It's not a bug, it's a feature.", "That isn't caution — it's theater.",
                     "Not just faster but cheaper.", "Despite this, it shipped.",
                     "Not the dashboard. Not the API. The queue."):
            self.assertTrue(any("contrast" in p for p in self.probs(f"<p>{text}</p>")), text)
        found = self.probs("<p>The tooling is new. The discipline isn't.</p>")
        self.assertTrue(any("X did. Y did not." in p for p in found), found)

    def test_contrast_title(self):
        for title in ("The model shipped. The weights did not.", "Rollout Report: The API is enterprise. The bill is not.",
                      "The model ships to defenders, not developers."):
            found = writer.humanizer_problems(post("<p>Fine.</p>", title=title))
            self.assertTrue(any(p.startswith("title:") and "contrast" in p for p in found), title)
        self.assertEqual(writer.humanizer_problems(post("<p>Fine.</p>", title="Rollout Report: Five GPUs walk into a bar")), [])

    def test_authority_summary_importance_tone_bold_and_bang(self):
        cases = {"Experts say it works.": "vague authority", "Industry reports agree.": "vague authority",
                 "In conclusion, ship it.": "summary ending", "Overall, fine.": "summary ending",
                 "This matters because money.": "importance", "Now more than ever, ship.": "motivational",
                 "It shipped!": "exclamation"}
        for text, label in cases.items():
            self.assertTrue(any(label in p for p in self.probs(f"<p>{text}</p>")), text)
        self.assertTrue(any("bold" in p for p in self.probs("<p><strong>Big</strong> deal.</p>")))

    def test_desc_and_caption_are_checked(self):
        long_desc = " ".join(["word"] * 21) + "."
        found = writer.humanizer_problems(post("<p>Fine.</p>", desc=long_desc, caption="It's vibrant."))
        self.assertTrue(any(p.startswith("desc: 21-word") for p in found), found)
        self.assertTrue(any(p.startswith("svg_caption: banned") for p in found), found)

    def test_more_contrast_shapes(self):
        for text in ("This was not a pilot. It was a production deal.", "I can read the proof. I cannot call the model.",
                     "I heard it at a hearing, not from the endpoint.", "Still, the queue moved.",
                     "Not because the agents fail. Because they work.", "The weights never did.",
                     "The model is fast. The bill is not small."):
            self.assertTrue(any("contrast" in p for p in self.probs(f"<p>Fine. {text}</p>")), text)
        for text in ("Whether or not it ships, payroll runs Friday.", "The crew left at six. The truck came back at nine."):
            self.assertFalse(any("contrast" in p for p in self.probs(f"<p>{text}</p>")), text)

    def test_one_line_title_caption_and_blockquote(self):
        found = writer.humanizer_problems(post("<p>Fine.</p>", title="The agents got defunded. The model got a raise."))
        self.assertTrue(any(p.startswith("title: two sentences") for p in found), found)
        found = writer.humanizer_problems(post("<p>Fine.</p>", caption="The org chart says one thing. The endpoint says another."))
        self.assertTrue(any(p.startswith("svg_caption: two or more") for p in found), found)
        found = self.probs("<blockquote>The model failed the bar. The labs signed a promise.</blockquote>")
        self.assertTrue(any(p.startswith("blockquote: must be one line") for p in found), found)

    def test_formatting_recap_authority_and_cousins(self):
        cases = {"<p><cite index='1-2'>Pasted.</cite></p>": "cite", "<p>It was <em>not</em> fine.</p>": "<em> used",
                 "<p>Four stories, one pattern.</p>": "summary ending", "<p>Lehane reportedly said so.</p>": "vague authority",
                 "<p>The realm of agents grew.</p>": "banned", "<p>This is a reminder that APIs change.</p>": "importance"}
        for body, label in cases.items():
            self.assertTrue(any(label in p for p in self.probs(body)), body)
        for body in ("<p>Rotate the tablet to landscape mode.</p>", "<p>Overall latency dropped 40 ms.</p>",
                     "<p>When it's time to file, one tap hands the route over.</p>", "<p>I read <em>The Information</em> daily.</p>"):
            self.assertEqual(self.probs(body), [], body)

    def test_hard_wrapped_sentence_still_counts(self):
        long = " ".join(["word"] * 10) + "\n" + " ".join(["word"] * 10) + "."
        self.assertTrue(any("20-word sentence" in p for p in self.probs(f"<p>{long}</p>")))

    def test_long_sentences_listed_last(self):
        found = self.probs("<p>" + " ".join(["word"] * 20) + ". This is crucial.</p>")
        self.assertIn("banned", found[0])
        self.assertIn("-word sentence", found[-1])

    def test_anchors_art_text_and_no_runs(self):
        found = self.probs("<p>See {link:v1-50-0-x|the platform can call itself production-grade and still log too little} today.</p>")
        self.assertTrue(any("crosslink anchor" in p for p in found), found)
        self.assertFalse(any("crosslink anchor" in p for p in self.probs("<p>See {link:v1-50-0-x|the old post} today.</p>")))
        art = '<text x="1" y="1">The paper shipped. The framework did not.</text><text x="1" y="2">One dry line.</text>'
        found = writer.humanizer_problems(dict(post("<p>Fine.</p>"), svg_inner=art))
        self.assertTrue(any(p.startswith("svg_inner: contrast") for p in found), found)
        found = writer.humanizer_problems(dict(post("<p>Fine.</p>"), svg_inner='<text x="1" y="1">OTHER WORDS</text>'))
        self.assertTrue(any("must repeat svg_caption" in p for p in found), found)
        found = self.probs("<p>It keeps nothing. No logs. No accounts.</p>")
        self.assertTrue(any("Not A. Not B." in p for p in found), found)

    def test_strip_tags_removes_cite_and_bold_only(self):
        body = "<p><cite index='1'>Said.</cite> <strong>Big</strong> <b>deal</b>.</p><blockquote>Ok.</blockquote><br>"
        self.assertEqual(writer.STRIP_TAGS.sub("", body), "<p>Said. Big deal.</p><blockquote>Ok.</blockquote><br>")

    def test_stub_is_clean(self):
        self.assertEqual(writer.humanizer_problems(writer.STUB), [])

    def test_importance_lines_and_paired_contrasts(self):
        cases = {"The question is whether anyone checks.": "importance sentence (the question is)",
                 "The number that matters is forty.": "importance sentence",
                 "A promise means nothing if no one audits it.": "importance sentence",
                 "I have the invoice. I do not have the contract.": "I have X. I do not have Y.",
                 "The badge means access. It does not mean trust.": "It does not mean B.",
                 "The key is in the vault. It is not in the repo.": "It is not in B.",
                 "The API logs every request. It does not log the answer.": "X does. It does not.",
                 "The Foster report evolved.": 'banned word "evolved"'}
        for text, label in cases.items():
            self.assertTrue(any(label in p for p in self.probs(f"<p>{text}</p>")), text)
        for text in ("The Foster report came out Monday.", "Landscape contractors bid it.",
                     "The API logs every request. It keeps them for a week."):
            self.assertEqual(self.probs(f"<p>{text}</p>"), [], text)

    def test_one_liners_that_turn(self):
        for line in ("You can cut features but the GPU lease does not care.",  # v1.73.0
                     "The log shows what came back, never which rule broke.",  # v1.72.0
                     "The test was designed to catch escapes and four escaped anyway."):  # v1.76.1
            found = self.probs(f"<p>Fine.</p><blockquote>{line}</blockquote>")
            self.assertTrue(any(p.startswith("blockquote: contrast structure (X, but Y") for p in found), line)
            found = writer.humanizer_problems(post("<p>Fine.</p>", caption=line))
            self.assertTrue(any(p.startswith("svg_caption: contrast structure") for p in found), line)
        self.assertEqual(self.probs("<p>Fine.</p><blockquote>The crew poured the slab, but only after lunch.</blockquote>"), [])
        self.assertEqual(self.probs("<p>It never shipped, but nobody asked.</p>"), [])

    def test_title_clauses(self):
        def title_probs(title):
            return [p for p in writer.humanizer_problems(post("<p>Fine.</p>", title=title)) if p.startswith("title:")]
        self.assertTrue(title_probs("The model shipped on time, the weights did not"))
        self.assertTrue(any('joined by "and"' in p for p in
                            title_probs("Rollout Report: Google ships an agent and OpenAI raised prices")))
        self.assertEqual(title_probs("Rollout Report: Agents that pay and bills that grow"), [])
        self.assertEqual(title_probs("The estimator learned a new trick"), [])

    def test_crosslinks_and_source_links(self):
        slug = writer.ALL[-1]["slug"]
        old = next(p["title"] for p in writer.ALL if not p["title"].startswith("Rollout") and len(p["title"].split()) > 5)
        cases = {f"<p>See {{link:{slug}|the old post}} and {{link:{slug}|that one again}} today.</p>": f"link {slug} once",
                 f"<p>Fine. {{link:{slug}|The API logs the request}}. More.</p>": "anchor is a whole sentence",
                 f"<p>Read {{link:{slug}|{' '.join(old.split()[:4])}}} today.</p>": "repeats an old title",
                 '<p>I read <a href="https://e.com/x">the company said it would ship next year</a> twice.</p>':
                     "source link text",
                 '<p>Fine. <a href="https://e.com/y">The FTC sent letters</a>. More.</p>': "source link text",
                 '<p>I read <a href="https://e.com/z">the filing</a> and <a href="https://e.com/z">the memo</a>.</p>':
                     "linked 2 times: https://e.com/z"}
        for body, label in cases.items():
            self.assertTrue(any(label in p for p in self.probs(body)), body)
        self.assertEqual(self.probs(f'<p>I read <a href="https://e.com/x">the filing</a> and {{link:{slug}|the old post}}.</p>'), [])

    def test_reader_recap_and_repeats(self):
        dull = "<p>" + "The crew poured the slab on time. " * 50 + "</p>"
        self.assertTrue(any("talks to its reader" in p for p in self.probs(dull)))
        self.assertFalse(any("talks to its reader" in p for p in self.probs(dull.replace("</p>", " You can check it.</p>"))))
        recap = ("<h3>Payroll moved</h3><p>Fine.</p><h3>Dispatch broke</h3><p>Fine.</p><h3>Invoices doubled</h3>"
                 "<p>Fine.</p><p>Payroll, dispatch and invoices all changed.</p>")
        self.assertTrue(any("recaps 3 sections" in p for p in self.probs(recap)))
        self.assertFalse(any("recaps" in p for p in self.probs(recap.replace("Payroll, dispatch and invoices all changed.",
                                                                             "The truck came back at nine."))))
        old = next(s for s in writer._sentences(writer._plain(writer.ALL[-1]["body"])) if 6 <= writer._words(s) <= 16)
        self.assertTrue(any("repeats a sentence" in p for p in self.probs(f"<p>{old}</p>")), old)


class ClaimTests(unittest.TestCase):
    # sentences that shipped and are false (SYSTEM FACTS) or state a crime as fact
    MUST_NOT_SHIP = {
        "v1.70.0": ["The construction ERP runs on PHP.", "Atelier runs on Python.",
                    "I patched all three to the fixed builds on October 21.", "The others sat exposed for 72 days.",
                    # left behind by the first cut: a generic subject, "sat on", a paragraph's later lines
                    "The review forms and the email collector run on some version of PHP in production.",
                    "Every one of those systems sat on two memory-corruption bugs for 72 days.",
                    "I checked the firewall logs and the access logs.", "My systems did not appear in their scan.",
                    "The ERP runs PHP 8.3.34."],
        "v1.71.0": ["The estimating SaaS runs on a VPS in a data center in New Jersey."],
        "v1.72.0": ["Atelier routes user prompts to seven providers and logs the full exchange.",
                    "The D1 table stores what the user asked and what the model returned."],
        "v1.74.0": ["Atelier logs each prompt to a D1 table with the timestamp and model name."],
        "v1.65.0": ["API keys for Twilio and Stripe lived in both the old .env file and the new secret manager.",
                    "Anyone with access to that branch could read the keys.",
                    "I ran a migration for the dog-training platform last year.",
                    "User credentials moved from a Rails session store to encrypted JWTs.",
                    "The old file sat in the repo.", "I deleted the .env file the same day.",
                    "The keys existed in two places for six hours."],
        "v1.61.0": ["Abdulrahman Alfozan planted a recording device in an executive conference room."],
    }

    def test_shipped_false_claims_are_must_not_ship(self):
        for version, sentences in self.MUST_NOT_SHIP.items():
            found = writer.claim_problems(stored(version))
            for s in sentences:
                self.assertTrue(any("must not ship" in p and s[:60] in p for p in found), (version, s))

    def test_drop_high_risk_cuts_them_and_keeps_the_rest(self):
        for version, sentences in self.MUST_NOT_SHIP.items():
            draft = stored(version)
            out, cut = writer.drop_high_risk(draft)
            plain = writer._plain(out["body_html"])
            for s in sentences:
                self.assertNotIn(s[:60], plain, (version, s))
            self.assertFalse(any("must not ship" in p for p in writer.claim_problems(out)), version)
            self.assertEqual(out["body_html"].count("<blockquote>"), 1, version)
            self.assertEqual(writer._sources(out), writer._sources(draft), version)  # linked lines stay
            if version == "v1.70.0":  # a third of it was made up: too short to ship, so the run exits and retries
                self.assertTrue(any(e.startswith("body too short") for e in writer.validate(
                    dict(writer.STUB, body_html=out["body_html"]), "post")))
            else:
                self.assertGreater(writer._body_words(out), 0.8 * writer._body_words(draft), version)

    def test_a_would_clause_excuses_only_itself(self):
        for s in ("Atelier logs every prompt to D1, so I would check the retention.",
                  "Abdulrahman Alfozan planted a recording device, and I would check my own rooms.",
                  "The construction ERP runs on PHP 8.3, so I would patch it.",
                  "Atelier logs each prompt to a D1 table, not the answer.",
                  "Atelier stores every prompt and never deletes them.",
                  "Atelier logs every prompt to a D1 table and offers opt-in sync.",
                  "I rotated the keys on the ERP last week."):
            found = writer.claim_problems(post(f"<p>{s}</p>"))
            self.assertTrue(any("must not ship" in p for p in found), (s, found))
            out, cut = writer.drop_high_risk(post(f"<p>Fine.</p><p>{s}</p>"))
            self.assertEqual((out["body_html"], len(cut)), ("<p>Fine.</p>", 1), s)

    def test_the_rest_of_a_story_goes_with_it(self):
        body = ('<p>The FTC opened a case Monday. I checked the firewall logs on the ERP. The keys sat there. '
                '<a href="https://example.com/a">The FTC</a> named two vendors. I would check the repo first. '
                'It was quiet.</p><p>The court meets Friday.</p>')
        out, cut = writer.drop_high_risk(post(body))
        self.assertEqual(out["body_html"], '<p>The FTC opened a case Monday. <a href="https://example.com/a">The FTC</a> '
                                           'named two vendors. I would check the repo first.</p><p>The court meets Friday.</p>')
        self.assertEqual([c[2] for c in cut], [writer.STORY_LABEL, writer.TALE_LABEL, writer.TALE_LABEL])

    def test_a_bare_erp_is_cut_only_when_it_is_coles(self):
        for s in ("The ERP flaw left 10,000 SAP systems exposed.", "The ERP vendor patched CVE-2026-1234 on Tuesday."):
            self.assertFalse(any("must not ship" in p for p in writer.claim_problems(post(f"<p>{s}</p>"))), s)
            ours = post(f"<p>The construction ERP has a review gate.</p><p>{s}</p>")
            self.assertFalse(any("must not ship" in p for p in writer.claim_problems(ours)), s)
        alone = writer.claim_problems(post("<p>The ERP runs PHP 8.3.34.</p>"))
        self.assertTrue(alone and not any("must not ship" in p for p in alone), alone)
        ours = writer.claim_problems(post("<p>The construction ERP has a review gate.</p><p>The ERP runs PHP 8.3.34.</p>"))
        self.assertTrue(any("must not ship" in p for p in ours), ours)

    def test_cut_tidies_the_tags_it_empties(self):
        body = ('<p>I read <a href="https://example.com/a">the filing</a> today. '
                'Atelier logs every prompt to <a href="https://example.com/b">a D1 table</a>.</p>'
                '<p>Atelier runs on Python.</p><p>You can check it.</p>')
        out, cut = writer.drop_high_risk(post(body))
        self.assertEqual(out["body_html"], '<p>I read <a href="https://example.com/a">the filing</a> today.</p>'
                                           '<p>You can check it.</p>')
        self.assertEqual([c[0] for c in cut], ["body_html", "body_html"])

    def test_carry_over_and_crime_attribution(self):
        found = writer.claim_problems(post("<p>Atelier picks the model. It logs every answer to a table.</p>"))
        self.assertTrue(any("must not ship, Atelier logs no prompts" in p for p in found), found)
        self.assertTrue(any("crime stated as fact" in p for p in writer.claim_problems(post("<p>Jane Roe stole the files.</p>"))))
        self.assertEqual(writer.claim_problems(post("<p>Prosecutors say Jane Roe stole the files.</p>")), [])

    def test_soft_claims_go_back_to_the_model(self):
        cases = {"Atelier routes each request through Mistral.": "a provider Atelier does not use",
                 "Atelier expires each session after an hour.": "an Atelier detail",
                 "Valhalla K9 uses a small model to write SMS reminders.": "says it does not do",
                 "JetDesk shows NOTAMs on the route.": "says it does not do",
                 "I reviewed the CurbScript listing copy on Tuesday.": "a first-person story",
                 "The construction ERP stores every timesheet in a database.": "outside SYSTEM FACTS",
                 "Atelier, JetDesk, PermitSketch and CurbScript all shipped.": "names 4 of Cole's systems"}
        for text, label in cases.items():
            found = writer.claim_problems(post(f"<p>{text}</p>"))
            self.assertTrue(any(label in p for p in found), (text, found))
            self.assertFalse(any("must not ship" in p for p in found), text)

    def test_true_facts_and_what_ifs_stay_clean(self):
        for s in ("Atelier keeps threads in IndexedDB on your device.", "Keep Fix Cut runs on one Cloudflare Worker.",
                  "Keep Fix Cut does not save uploads or reports.", "PermitSketch is a Base44 app.",
                  "The dating-profile tool runs on one Cloudflare Worker with no PHP anywhere in the stack.",
                  "I would check which keys that branch could read.",
                  "If it leaked, anyone with access to the repo could read the key.",
                  "Atelier logs no prompts or answers.", "The ledger doesn't hold prompts or answers.",
                  "Atelier's ledger records what each request cost and when; it never holds prompts or answers.",
                  "I wrote on October 9 about the filing."):
            self.assertEqual(writer.claim_problems(post(f"<p>{s}</p>")), [], s)


class ArtTests(unittest.TestCase):
    def test_validate_refuses_broken_lines_and_off_palette_ink(self):
        self.assertEqual(writer.validate(writer.STUB, "post"), [])
        art = writer.STUB["svg_inner"]
        errs = writer.validate(dict(writer.STUB, svg_inner=art + "<line x='10' y='10' x2='90' y2='10' stroke='#33ff66'/>"), "post")
        self.assertIn("svg_inner: every <line> needs x1, y1, x2 and y2", errs)
        errs = writer.validate(dict(writer.STUB, svg_inner=art.replace(writer.G, "#ff4444")), "post")
        self.assertTrue(any(e.endswith("not ['#ff4444']") for e in errs), errs)
        errs = writer.validate(dict(writer.STUB, svg_inner=art + "<rect style='fill:#1a1a1a'/>"), "post")
        self.assertTrue(any(e.endswith("not ['#1a1a1a']") for e in errs), errs)

    def test_repair_fixes_what_validate_refuses(self):
        art = "<line x='10' y='10' x2='90' y2='10' stroke='#ff4444'/><rect fill=\"#1a1a1a\" style='stroke: #fff'/>"
        self.assertEqual(writer.repair_svg(art), "<line x1='10' y1='10' x2='90' y2='10' stroke='#ffd75e'/>"
                                                 "<rect fill=\"#04120a\" style='stroke: #ffd75e'/>")
        self.assertEqual(writer.repair_svg(writer.STUB["svg_inner"]), writer.STUB["svg_inner"])
        wrapper = re.compile(r'^<svg [^>]*><rect width="640" height="300" fill="#04120a"/>|</svg>$')
        for p in writer.ALL:  # every published picture passes once repaired
            inner = wrapper.sub("", p["svg"])
            self.assertEqual(writer.validate(dict(writer.STUB, svg_inner=writer.repair_svg(inner)), "post"), [], p["version"])

    def test_art_checks_read_tags_not_text(self):
        art = writer.STUB["svg_inner"] + "<text x='10' y='20' fill='#33ff66'>DISK FILL: 92%</text>"
        self.assertEqual(writer.validate(dict(writer.STUB, svg_inner=art), "post"), [])
        self.assertEqual(writer.repair_svg(art), art)
        grad = "<defs><linearGradient id='g'><stop offset='0' stop-color='#33ff66'/></linearGradient></defs><rect fill='url(#g)'/>"
        self.assertEqual(writer.validate(dict(writer.STUB, svg_inner=writer.STUB["svg_inner"] + grad), "post"), [])
        errs = writer.validate(dict(writer.STUB, svg_inner=writer.STUB["svg_inner"] + grad.replace("#33ff66", "#ff0000")), "post")
        self.assertTrue(any(e.endswith("not ['#ff0000']") for e in errs), errs)

    def test_repair_maps_names_rgb_and_stops(self):
        art = ("<rect fill='white' stroke='black'/><circle style='fill: rgb(255, 0, 0); stroke: transparent'/>"
               "<stop stop-color='#ff0000'/><text fill='#33ff66'>FILL: red</text>")
        self.assertEqual(writer.repair_svg(art), "<rect fill='#ffd75e' stroke='#000'/><circle style='fill: #ffd75e; "
                                                 "stroke: none'/><stop stop-color='#ffd75e'/><text fill='#33ff66'>FILL: red</text>")

    def test_art_text_must_fit_the_frame(self):
        def overflow(art):
            draft = dict(post("<p>Fine.</p>"), svg_inner=art + "<text x='1' y='290'>One dry line.</text>")
            return [p for p in writer.humanizer_problems(draft) if "runs past" in p]
        self.assertTrue(overflow("<text x='600' y='50' font-size='14'>FAR TOO WIDE</text>"))
        self.assertTrue(overflow('<text x="320" y="20" font-size="42" text-anchor="middle">TALL</text>'))
        self.assertEqual(overflow("<text x='630' y='100' font-size='20' text-anchor='end'>RIGHT EDGE</text>"), [])
        self.assertEqual(overflow("<text x='320' y='165' style='font-size:42px;text-anchor:middle'>STUB</text>"), [])
        self.assertEqual(overflow("<g transform='translate(0,-90)'><text x='600' y='50'>MOVED</text></g>"), [])


class HumanizePassTests(unittest.TestCase):
    draft = dict(writer.STUB, body_html=writer.STUB["body_html"] + "<p>This is crucial.</p>")
    messages = [{"role": "user", "content": "write it"}]

    @staticmethod
    def js(p):
        return "```json\n" + json.dumps(p) + "\n```"

    def run_pass(self, reply=None, error=None, errs=(), draft=None, mode="post", replies=None):
        """humanize() with call_claude stubbed. errs=None keeps the real validate()."""
        calls, replies = [], list(replies or [])

        def fake_call(msgs, system, search=True):
            calls.append((msgs, search))
            if error:
                raise error
            return replies.pop(0) if replies else reply

        out_buf = io.StringIO()
        checks = patch.object(writer, "validate", return_value=list(errs)) if errs is not None else contextlib.nullcontext()
        with patch.object(writer, "call_claude", side_effect=fake_call), contextlib.redirect_stdout(out_buf), checks:
            out = writer.humanize(draft or self.draft, mode, list(self.messages), "sys")
        self.log = out_buf.getvalue()
        return out, calls

    def test_no_problems_means_no_call(self):
        with patch.object(writer, "call_claude") as call:
            self.assertIs(writer.humanize(writer.STUB, "post", self.messages, "sys"), writer.STUB)
        call.assert_not_called()

    def test_cleaner_revision_is_used_without_search(self):
        fixed = dict(writer.STUB)
        out, calls = self.run_pass(reply=self.js(fixed))
        self.assertEqual(out, fixed)
        self.assertEqual(len(calls), 1)
        msgs, search = calls[0]
        self.assertFalse(search)
        self.assertEqual([m["role"] for m in msgs], ["user", "assistant", "user"])
        self.assertIn("crucial", msgs[-1]["content"])

    def test_draft_kept_when_revision_fails(self):
        out, calls = self.run_pass(error=SystemExit("Claude API error 529"))
        self.assertIs(out, self.draft)
        self.assertEqual(len(calls), 1)
        out, calls = self.run_pass(reply="no json here")
        self.assertIs(out, self.draft)
        self.assertEqual(len(calls), writer.PASSES)
        self.assertIs(self.run_pass(reply=self.js(writer.STUB), errs=["not enough outbound source links"])[0], self.draft)
        worse = dict(self.draft, body_html=self.draft["body_html"] + "<p>Crucial and pivotal!</p>")
        self.assertIs(self.run_pass(reply=self.js(worse))[0], self.draft)

    def test_transport_errors_and_odd_types_keep_draft(self):
        import urllib.error
        for err in (urllib.error.URLError("down"), TimeoutError("slow"), ConnectionResetError("reset")):
            self.assertIs(self.run_pass(error=err)[0], self.draft)
        odd = dict(writer.STUB, body_html=["not", "a", "string"])
        self.assertIs(self.run_pass(reply=self.js(odd))[0], self.draft)

    def test_invented_link_or_shrunk_body_is_refused(self):
        body = writer.STUB["body_html"]
        cut = dict(writer.STUB, body_html=body.replace("This sentence pads the stub to a plausible length. " * 30, "", 1))
        invented = dict(writer.STUB, body_html=body.replace(
            '<a href="https://ciprari.ai/status">three</a>', '<a href="https://invented.example/x">three</a>'))
        self.assertIs(self.run_pass(reply=self.js(cut))[0], self.draft)
        self.assertIn("it cut the body", self.log)
        self.assertIs(self.run_pass(reply=self.js(invented))[0], self.draft)
        self.assertIn("it added source links ['https://invented.example/x'] "
                      "(and dropped ['https://ciprari.ai/status'])", self.log)

    def test_dropped_link_is_fine_while_validate_passes(self):
        body = writer.STUB["body_html"]
        one = dict(writer.STUB, body_html=body.replace('<a href="https://ciprari.ai/status">three</a>', "three"))
        out, _ = self.run_pass(reply=self.js(one), errs=None)
        self.assertEqual(out["body_html"], one["body_html"])
        self.assertIn("dropped source links ['https://ciprari.ai/status']", self.log)
        two = dict(one, body_html=one["body_html"].replace('<a href="https://ciprari.ai/">two</a>', "two"))
        self.assertIs(self.run_pass(reply=self.js(two), errs=None)[0], self.draft)
        self.assertIn("not enough outbound source links", self.log)

    def test_unlinking_a_second_crosslink_is_fine_dropping_a_post_is_not(self):
        slug = writer.ALL[-1]["slug"]
        twice = f"<p>See {{link:{slug}|the old post}} and {{link:{slug}|that one again}} today.</p>"
        draft = dict(writer.STUB, body_html=writer.STUB["body_html"] + twice)
        self.assertIn(f"body_html: link {slug} once, not 2 times", writer.humanizer_problems(draft))
        once = dict(draft, body_html=draft["body_html"].replace(f"{{link:{slug}|that one again}}", "that one again"))
        self.assertEqual(writer.humanizer_problems(once), [])
        out, _ = self.run_pass(reply=self.js(once), errs=None, draft=draft)
        self.assertEqual(out["body_html"], once["body_html"])
        self.assertNotIn("dropped crosslinks", self.log)
        gone = dict(draft, body_html=writer.STUB["body_html"] + "<p>See the old post and that one again today.</p>")
        self.assertIs(self.run_pass(reply=self.js(gone), errs=None, draft=draft)[0], draft)
        self.assertIn(f"it dropped crosslinks ['{slug}']", self.log)

    def test_revision_art_is_repaired_before_the_merge(self):
        two = "The tap ran dry. The crew kept pouring."
        draft = dict(writer.STUB, svg_caption=two, svg_inner=writer.STUB["svg_inner"].replace("This is only a test.", two))
        rev = dict(writer.STUB, svg_inner=writer.STUB["svg_inner"].replace(writer.G, "#ff4444"))
        out, _ = self.run_pass(reply=self.js(rev), errs=None, draft=draft)
        self.assertEqual((out["svg_caption"], out["svg_inner"]), (rev["svg_caption"], writer.repair_svg(rev["svg_inner"])))
        self.assertNotIn("#ff4444", out["svg_inner"])

    def test_good_title_survives_a_bad_body(self):
        draft = dict(self.draft, title="The model shipped. The weights did not.", slug_words="the model shipped")
        rev = dict(draft, title="The model shipped on Tuesday", slug_words="the model shipped on tuesday",
                   body_html=draft["body_html"] + "<p>Pivotal and seamless.</p>")
        out, _ = self.run_pass(reply=self.js(rev), errs=None, draft=draft)
        self.assertEqual(out["title"], "The model shipped on Tuesday")
        self.assertEqual(out["slug_words"], "the model shipped on tuesday")
        self.assertEqual(out["body_html"], draft["body_html"])

    def test_non_text_slug_keeps_our_title_and_takes_the_body(self):
        for bad in (["policy", "ships"], 42):
            out, _ = self.run_pass(reply=self.js(dict(writer.STUB, slug_words=bad)))
            self.assertEqual(out["slug_words"], self.draft["slug_words"])
            self.assertEqual(out["body_html"], writer.STUB["body_html"])

    def test_must_fix_beats_a_new_long_sentence(self):
        draft = dict(writer.STUB, body_html=writer.STUB["body_html"] + "<p>Atelier runs on Python.</p>")
        rev = dict(writer.STUB, body_html=writer.STUB["body_html"] + "<p>" + " ".join(["word"] * 17) + ".</p>")
        out, _ = self.run_pass(reply=self.js(rev), errs=None, draft=draft)
        self.assertEqual(out["body_html"], rev["body_html"])

    def test_later_passes_ask_only_for_what_is_left(self):
        draft = dict(self.draft, title="The model shipped. The weights did not.")
        first = dict(writer.STUB, title=draft["title"])
        second = dict(writer.STUB, title="The model shipped on Tuesday")
        out, calls = self.run_pass(errs=None, draft=draft, replies=[self.js(first), self.js(second)])
        self.assertEqual(len(calls), 2)
        self.assertIn("crucial", calls[0][0][-1]["content"])
        self.assertNotIn("crucial", calls[1][0][-1]["content"])
        self.assertIn("title: two sentences", calls[1][0][-1]["content"])
        self.assertIn('"The model shipped. The weights did not."', calls[1][0][-2]["content"])
        self.assertEqual((out["title"], out["body_html"]), (second["title"], writer.STUB["body_html"]))

    def test_last_resort_keeps_the_first_sentence(self):
        art = writer.STUB["svg_inner"].replace("This is only a test.", "The tap ran dry at noon. The crew kept pouring.")
        draft = dict(writer.STUB, title="The promise said independence. The contract said approval.",
                     svg_caption="The tap ran dry at noon. The crew kept pouring.", svg_inner=art)
        out, calls = self.run_pass(reply="no json here", errs=None, draft=draft)
        self.assertEqual(len(calls), writer.PASSES)
        self.assertEqual(out["title"], "The promise said independence.")
        self.assertEqual(out["slug_words"], "the promise said independence")
        self.assertEqual(out["svg_caption"], "The tap ran dry at noon.")
        self.assertIn(">The tap ran dry at noon.</text>", out["svg_inner"])
        self.assertEqual(writer.humanizer_problems(out), [])
        rollout = dict(writer.STUB, title="Rollout Report: The model failed the bar. The accord has no teeth.")
        out, _ = self.run_pass(reply="no json here", errs=None, draft=rollout, mode="rollout")
        self.assertEqual(out["title"], "Rollout Report: The model failed the bar.")
        self.assertEqual(out["slug_words"], rollout["slug_words"])
        short = dict(writer.STUB, title="Shipped. The weights did not.")
        self.assertIs(self.run_pass(reply="no json here", errs=None, draft=short)[0], short)

    def test_trace_records_the_draft_and_each_pass(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "trace.jsonl")
            with patch.object(writer, "TRACE_PATH", path):
                self.run_pass(reply=self.js(writer.STUB))
            with open(path, encoding="utf-8") as f:
                rows = [json.loads(line) for line in f]
        self.assertEqual([r["kind"] for r in rows], ["draft", "revision"])
        self.assertTrue(any("crucial" in p for p in rows[0]["problems"]))
        self.assertEqual((rows[1]["n"], rows[1]["taken"], rows[1]["problems"]), (1, ["body_html"], []))
        with patch.object(writer, "TRACE_PATH", None):
            writer.trace("draft", post={})  # no path: nothing written, nothing raised

    def test_cut_sentences_stay_out_of_the_public_log_and_trace(self):
        bad = "Atelier logs every prompt to a D1 table."
        draft = dict(writer.STUB, body_html=writer.STUB["body_html"] + f"<p>{bad} You can check it.</p>")
        out_buf = io.StringIO()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "trace.jsonl")
            with patch.object(writer, "TRACE_PATH", path), patch.object(writer, "call_claude", return_value=self.js(draft)), \
                    patch.object(writer, "already_published", return_value=False), patch.object(writer, "append_post"), \
                    patch.object(writer, "try_build", return_value=(True, "")), patch.object(writer.sys, "argv", ["writer.py", "post"]), \
                    patch.dict(os.environ, {"GITHUB_OUTPUT": ""}), contextlib.redirect_stdout(out_buf):
                writer.main()
            with open(path, encoding="utf-8") as f:
                logged = f.read()
        printed = out_buf.getvalue()
        self.assertIn("claims: cut a 8-word sentence from body_html (Atelier logs no prompts", printed)
        for text in (printed, logged):
            self.assertNotIn("every prompt to a D1", text)
        rows = [json.loads(line) for line in logged.splitlines()]
        self.assertEqual([r["kind"] for r in rows], ["draft", "revision", "revision", "revision", "final"])
        self.assertIn("You can check it.", rows[0]["post"]["body_html"])
        self.assertTrue(any(p.endswith("[8 words, kept out of the trace]") for p in rows[0]["problems"]), rows[0]["problems"])
        self.assertEqual([(c["field"], c["words"]) for c in rows[-1]["cut"]], [("body_html", 8)])

    def test_revision_keeps_related_and_strips_cite(self):
        fixed = dict(writer.STUB, related=["something-else"],
                     body_html=writer.STUB["body_html"].replace("<p>End.</p>", "<p><cite index='1'>End.</cite></p>"))
        out, _ = self.run_pass(reply=self.js(fixed))
        self.assertEqual(out["related"], self.draft["related"])
        self.assertNotIn("<cite", out["body_html"])


class EmitTests(unittest.TestCase):
    def load(self, entry):
        """Evaluate a compose_entry() dict the way posts_b.py loads it."""
        return eval(compile(entry.strip().rstrip(","), "posts_b.py", "eval"), {"_svg": lambda s: s})

    def test_backslashes_survive_the_python_literal(self):
        text = r"<p>Open C:\Users\cole, run echo \N and \x41, then C:\new\temp.</p>"
        art = r'<text x="1" y="1">C:\PERMITSKETCH&gt; curl -X GET \</text>'
        post = dict(writer.STUB, body_html=text + writer.STUB["body_html"], svg_inner=art)
        loaded = self.load(writer.compose_entry(post, "post", "v9.9.0", "2026-11-02")[1])
        self.assertEqual(loaded["body"].strip(), post["body_html"])
        self.assertEqual(loaded["svg"].strip(), art)

    def test_slug_is_cut_at_a_word(self):
        cases = {"anthropic filed the s1 compute payment three billion": "anthropic-filed-the-s1-compute-payment-three",
                 "the promise said independence the contract said approval": "the-promise-said-independence-the-contract-said",
                 "the model shipped": "the-model-shipped"}
        for words, want in cases.items():
            slug = writer.compose_entry(dict(writer.STUB, slug_words=words), "post", "v9.9.0", "2026-11-02")[0]
            self.assertEqual(slug, "v9-9-0-" + want, words)
            self.assertLessEqual(len(slug) - len("v9-9-0-"), 48)


class PromptTests(unittest.TestCase):
    def test_prompt_knows_fifteen_platforms_and_the_rules(self):
        for mode in ("post", "rollout"):
            system, user = writer.build_prompt(mode, "v9.9.9", "2026-10-12")
            self.assertIn("shipped 15 production platforms", system)
            self.assertIn("keepfixcut.com", system)
            self.assertIn("HUMANIZER", system)
            self.assertIn("Never paste", system)
            self.assertNotIn("retired two-sentence", user)
            self.assertNotIn("predate the HUMANIZER", user)
            self.assertNotIn("<cite", user)

    def test_system_facts_are_closed_and_current(self):
        system, _ = writer.build_prompt("post", "v9.9.9", "2026-11-02")
        self.assertIn(writer.SYSTEM_FACTS, system)
        flat = " ".join(system.split())
        for fact in ("Nine providers: Anthropic, OpenAI, Google", "never holds prompts or answers",
                     "Uploads and reports are not saved", "kept 30 days", "4 scans a minute",
                     "No Cole system uses PHP, Python, a VPS or S3", "Atelier has no D1 database",
                     "JetDesk has no NOTAMs", "CurbScript has no service routes", "what you would check",
                     "Name at most three of Cole's systems", "charged but not convicted", "calendar dates",
                     "quotes both", "No page counts", "Source link text is a 2–6 word noun phrase",
                     "Link each URL once", "Every <line> has x1, y1, x2 and y2", "svg_alt describes only"):
            self.assertIn(fact, flat, fact)
        for stale in ("seven providers", "stores nothing", "D1 databases"):
            self.assertNotIn(stale, flat, stale)

    def test_user_prompt_carries_the_week_and_catalog_descs(self):
        _, user = writer.build_prompt("rollout", "v9.9.9", "2026-11-01")
        self.assertIn("dated Monday, October 26 through Sunday, November 1", user)
        week = [p for p in writer.ALL if "2026-10-25" <= p["date"] <= "2026-11-01"]
        for p in week:
            self.assertIn(p["title"], user.split("Catalog of recent posts")[0])
        last = writer.ALL[-1]
        self.assertIn(f'{last["slug"]} | {last["version"]} | {last["date"]}', user)
        _, user = writer.build_prompt("post", "v9.9.9", "2026-11-02")
        self.assertNotIn("Every story's source is dated", user)

    def test_catalog_marks_posts_linked_twice_this_week(self):
        busy = dict(writer.ALL[-1], body="{link:v1-50-0-x|one} and {link:v1-50-0-x|two}")
        target = dict(writer.ALL[-2], slug="v1-50-0-x")
        with patch.object(writer, "ALL", writer.ALL[:-2] + [target, busy]):
            lines = writer.recent_catalog().splitlines()
        self.assertTrue(lines[-2].endswith("[linked 2 times this week; pick another]"), lines[-2])
        self.assertNotIn("[linked", lines[-1])

    def test_old_descs_lose_their_system_claims(self):
        desc = "Google shipped a model. Atelier logs every prompt to D1. My ERP runs on PHP."
        self.assertEqual(writer._no_system_lines(desc).strip(), "Google shipped a model.")

    def test_style_examples_are_pinned_and_clean(self):
        with patch.object(writer, "_recent_sentences", return_value=set()):
            for mode, ex in writer.STYLE_EXAMPLES.items():
                self.assertEqual(writer.humanizer_problems(ex), [], mode)
                self.assertEqual(writer.claim_problems(ex), [], mode)
                for slug in re.findall(r"\{link:([a-z0-9\-]+)\|", ex["body_html"]):
                    self.assertIn(slug, writer.SLUGS, mode)
                self.assertTrue(80 <= len(ex["desc"]) <= 200, mode)
                self.assertEqual(json.loads(writer.style_example(mode)), ex)
        newest = dict(writer.ALL[-1], title="Something new entirely")
        with patch.object(writer, "ALL", writer.ALL + [newest]):
            self.assertNotIn("Something new entirely", writer.build_prompt("post", "v9.9.9", "2026-11-02")[1]
                             .split("Style example")[1])


if __name__ == "__main__":
    unittest.main()
