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


# The lines Cole had corrected on 2026-11-02, as they shipped (line number -> text, per field).
# posts_b.py now holds the true lines, so the claim tests rebuild the shipped posts from these.
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "corrected_lines.json"), encoding="utf-8") as _f:
    CORRECTED = json.load(_f)


def shipped(version):
    """A post as it went live, before the correction: the writer's real output."""
    p = dict(next(p for p in writer.ALL if p["version"] == version))
    for field, lines in CORRECTED.get(version, {}).items():
        rows = p[field].split("\n")
        for i, line in lines.items():
            rows[int(i)] = line
        p[field] = "\n".join(rows)
    return {"title": p["title"], "desc": p["desc"], "svg_caption": p["svg_caption"], "svg_alt": p["svg_alt"],
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
        # a capital passes only for a name mid-sentence, never in art labels or a Title-Case heading
        art = writer.STUB["svg_inner"] + "<text x='10' y='40'>A PIVOTAL MOMENT</text>"
        self.assertIn('svg_inner: banned word "PIVOTAL"', writer.humanizer_problems(dict(writer.STUB, svg_inner=art)))
        self.assertIn('body_html: banned word "Seamless"', self.probs("<h3>A Seamless Handoff</h3><p>Fine.</p>"))
        self.assertIn('body_html: banned word "seamless"', self.probs("<p>A seamless handoff.</p>"))
        self.assertIn('body_html: banned word "CRUCIAL"', self.probs("<p>That is CRUCIAL now.</p>"))
        self.assertEqual(self.probs("<p>Micron still sells Crucial SSDs.</p>"), [])

    def test_abbreviations_do_not_end_a_sentence(self):
        for one in ("Fleet operators in the U.S. face a new toll rule", "The FTC fined Wheels Inc. for toll markups",
                    "Dr. Lee met J. Smith of Acme Corp. at the St. Louis office", "Ford vs. GM, e.g. on price"):
            self.assertEqual(writer._sentences(one), [one])
            self.assertEqual([p for p in writer.humanizer_problems(post("<p>Fine.</p>", title=one)) if p.startswith("title:")], [], one)
        self.assertEqual(writer._sentences("Read No. 5 first. No. That was wrong."), ["Read No. 5 first.", "No.", "That was wrong."])
        self.assertEqual(writer._sentences("It ran at 2 A.M. on Monday. Then it stopped."), ["It ran at 2 A.M. on Monday.", "Then it stopped."])
        piece = "Acme Inc. lost the U.S. bid. It filed again."
        self.assertEqual(["".join(p for _, p in s).strip() for s in writer._split(piece)], ["Acme Inc. lost the U.S. bid.", "It filed again."])

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
        for one in ("Robots and humans signed a pact", "a billion users and one shared key",  # v1.7.1
                    "Google, OpenAI and Anthropic signed a pact"):
            self.assertEqual(title_probs("Rollout Report: " + one), [], one)
        for two in ("Claude filed a murder tip in July and Anthropic found it in September",  # v1.58.1
                    "The model escaped through DNS and auditors found a tenth of Codex traffic unmonitored"):  # v1.70.1
            self.assertTrue(any('joined by "and"' in p for p in title_probs("Rollout Report: " + two)), two)

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

    def test_shipped_lines_rebuild_from_the_fixture(self):
        self.assertEqual(sorted(CORRECTED), ["v1.61.0", "v1.65.0", "v1.70.0", "v1.71.0", "v1.72.0", "v1.74.0",
                                             "v1.75.0", "v1.76.0"])
        for version, sentences in self.MUST_NOT_SHIP.items():
            self.assertNotEqual(shipped(version)["body_html"], stored(version)["body_html"], version)
            for s in sentences:
                self.assertIn(s, writer._plain(shipped(version)["body_html"]), (version, s))

    def test_shipped_false_claims_are_must_not_ship(self):
        for version, sentences in self.MUST_NOT_SHIP.items():
            found = writer.claim_problems(shipped(version))
            for s in sentences:
                self.assertTrue(any("must not ship" in p and s[:60] in p for p in found), (version, s))

    def test_drop_high_risk_cuts_them_and_keeps_the_rest(self):
        for version, sentences in self.MUST_NOT_SHIP.items():
            draft = shipped(version)
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
            else:  # v1.65.0 named six systems with a false line each, so it loses near a quarter
                floor = 0.75 if version == "v1.65.0" else 0.8
                self.assertGreater(writer._body_words(out), floor * writer._body_words(draft), version)

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
        cases = {"Atelier does not use Mistral.": "a provider Atelier does not use",
                 "Atelier picks the provider for each request.": "an Atelier detail",
                 "JetDesk has no NOTAMs.": "says it does not do",
                 "I reviewed the CurbScript listing copy on Tuesday.": "a first-person story",
                 "The construction ERP sits behind a login.": "outside SYSTEM FACTS",
                 "Atelier, JetDesk, PermitSketch and CurbScript all shipped.": "names 4 of Cole's systems"}
        for text, label in cases.items():
            found = writer.claim_problems(post(f"<p>{text}</p>"))
            self.assertTrue(any(label in p for p in found), (text, found))
            self.assertFalse(any("must not ship" in p for p in found), text)

    # a system named with a term its SYSTEM FACTS line does not hold, or a first-person line about
    # all of them: the sentence, then the terms the problem names
    UNSUPPORTED = {
        "None of my platforms have scoped permissions.": "all of them: no permissions",
        "I monitor nothing.": "all of them: no monitoring",
        "My apps all log to D1.": "all of them: d1",
        "My systems all run on Vercel.": "all of them: vercel",
        "PermitSketch writes drawings to R2 and logs sessions to D1.": "PermitSketch: r2; PermitSketch: d1",
        "PermitSketch runs on Cloudflare Workers.": "PermitSketch: cloudflare",
        "PermitSketch runs on a Worker.": "PermitSketch: worker",
        "The construction ERP runs payroll for 40 people.": "Coen ERP: person 40",
        "The construction ERP stores every timesheet in a database.": "Coen ERP: database",
        "Curbscript generates service routes through an API.": "CurbScript: api",
        "CurbScript generates service routes for agents.": "CurbScript: service route",
        "JetDesk shows NOTAMs on the route.": "JetDesk: notam",
        "Valhalla K9 uses a small model to write SMS reminders.": "Valhalla K9: ai",
        "Atelier offers models from OpenAI, Anthropic, Google, Mistral, Perplexity, Cohere and xAI.": "Atelier: mistral",
        "Atelier routes each request through Mistral.": "Atelier: mistral",
        "Atelier routes prompts to seven providers.": "Atelier: provider 7",
        "Atelier expires each session after an hour.": "Atelier: session",
        "When Azure goes down, Atelier switches to AWS.": "Atelier: aws",
        "Atelier keeps nothing on a server.": "Atelier: no server",
        "Atelier stores nothing.": "Atelier: keeps no data",
        "Atelier keeps no feedback.": "Atelier: keeps no feedback",
        "Keep Fix Cut stores nothing.": "Keep Fix Cut: keeps no data",
        "Keep Fix Cut keeps your photos for a day.": "Keep Fix Cut: keeps photo",
        "Keep Fix Cut runs on a Worker and Atelier stores threads in D1.": "(Atelier: d1)",
        "JetDesk syncs your trips to the cloud.": "JetDesk: keeps trip",
        "JetDesk logs your location.": "JetDesk: keeps location",
        "JetDesk runs on Vercel.": "JetDesk: vercel",
        # "keeps nothing" and its cousins: both apps keep the data their privacy pages list
        "Atelier keeps nothing.": "Atelier: keeps no data",
        "Atelier keeps nothing about you.": "Atelier: keeps no data",
        "Keep Fix Cut keeps nothing at all.": "Keep Fix Cut: keeps no data",
        "Atelier doesn't keep anything.": "Atelier: keeps no data",
        "Atelier doesn't save anything on a server.": "Atelier: keeps no data",
        "Keep Fix Cut doesn't keep analytics.": "Keep Fix Cut: keeps no analytics",
        "Atelier doesn't keep a profile.": "Atelier: keeps no profile",
        "Keep Fix Cut has no analytics.": "Keep Fix Cut: keeps no analytics",
        "Atelier has no usage ledger.": "Atelier: keeps no analytics",
        "My apps keep nothing.": "all of them: no store",
        "Atelier keeps your threads only on your device.": "Atelier: keeps thread only on the device",
        "Your conversations never leave your device in Atelier.": "Atelier: keeps thread only on the device",
        "Atelier never stores your conversations on a server.": "Atelier: keeps no thread",
        "Atelier doesn't store feedback.": "Atelier: keeps no feedback",
        "Keep Fix Cut doesn't store anything.": "Keep Fix Cut: keeps no data",
        # a period the sheet does not give: Keep Fix Cut's analytics are kept 30 days, Atelier's cookie is 30-day
        "Keep Fix Cut keeps analytics for 90 days.": "Keep Fix Cut: analytics kept 90 days",
        "Keep Fix Cut keeps usage analytics for a year.": "Keep Fix Cut: analytics kept 365 days",
        "Keep Fix Cut keeps analytics forever.": "Keep Fix Cut: analytics kept forever",
        "Keep Fix Cut deletes analytics after a week.": "Keep Fix Cut: analytics kept 7 days",
        "Keep Fix Cut retains analytics for 90 days.": "Keep Fix Cut: analytics kept 90 days",
        "Keep Fix Cut's analytics are kept for 90 days.": "Keep Fix Cut: analytics kept 90 days",
        "Atelier's cookie lasts 90 days.": "Atelier: cookie kept 90 days",
        "Atelier uses a 90-day cookie.": "Atelier: cookie kept 90 days",
        "Atelier's tester cookie lasts a year.": "Atelier: cookie kept 365 days",
        "Atelier keeps testers signed in for 90 days.": "Atelier: cookie kept 90 days",
        "Keep Fix Cut purges analytics every 90 days.": "Keep Fix Cut: analytics kept 90 days",
        "Keep Fix Cut deletes analytics every week.": "Keep Fix Cut: analytics kept 7 days",
        "Keep Fix Cut keeps no record of you.": "Keep Fix Cut: keeps no data",
        "Keep Fix Cut forgets everything when you close the tab.": "Keep Fix Cut: keeps no data",
        "Atelier doesn't collect personal data.": "Atelier: keeps no data",
        # collects, tracks or gathers nothing; keeps, stores or saves nothing; lives only on the device
        "Keep Fix Cut collects no data.": "Keep Fix Cut: keeps no data",
        "Keep Fix Cut tracks nothing.": "Keep Fix Cut: keeps no data",
        "Keep Fix Cut gathers no data.": "Keep Fix Cut: keeps no data",
        "Keep Fix Cut doesn't track you.": "Keep Fix Cut: keeps no data",
        "Atelier collects nothing.": "Atelier: keeps no data",
        "Atelier doesn't collect any data.": "Atelier: keeps no data",
        "Atelier gathers nothing.": "Atelier: keeps no data",
        "Keep Fix Cut saves nothing.": "Keep Fix Cut: keeps no data",
        "Atelier saves nothing.": "Atelier: keeps no data",
        "Keep Fix Cut doesn't keep anything.": "Keep Fix Cut: keeps no data",
        "Atelier doesn't store anything.": "Atelier: keeps no data",
        "Atelier is fully local.": "Atelier: keeps data only on the device",
        "Everything in Atelier lives in your browser.": "Atelier: keeps data only on the device",
        "Atelier stores everything on your device.": "Atelier: keeps data only on the device",
        # who may use what, how they sign in, where it runs: xAI and Runway are owner-only, testers
        # sign in with LinkedIn, Atelier and Keep Fix Cut run on Workers (JetDesk is the Pages app)
        "Testers can use Grok in Atelier.": "Atelier: xai for testers",
        "Testers can make Runway videos in Atelier.": "Atelier: runway for testers",
        "Atelier gives testers access to xAI and Runway.": "Atelier: runway for testers",
        "Testers can use Grok or Runway in Atelier.": "Atelier: runway for testers",
        "Atelier doesn't use Claude or GPT.": "Atelier: no openai",
        "Atelier signs testers in with Google.": "Atelier: sign-in with google",
        "Testers sign in to Atelier with Google.": "Atelier: sign-in with google",
        "Atelier uses Google sign-in for testers.": "Atelier: sign-in with google",
        "Atelier runs on Cloudflare Pages.": "Atelier: pages",
        "Keep Fix Cut runs on Cloudflare Pages.": "Keep Fix Cut: pages",
        "Atelier and Keep Fix Cut run on Cloudflare Pages.": "Keep Fix Cut: pages",
        "JetDesk logs every weather query.": "JetDesk: keeps query",
    }

    def test_unsupported_system_lines_are_must_not_ship(self):
        for s, why in self.UNSUPPORTED.items():
            found = writer.claim_problems(post(f"<p>{s}</p>"))
            self.assertTrue(any("must not ship" in p and why in p for p in found), (s, found))
            out, cut = writer.drop_high_risk(post(f"<p>Fine.</p><p>{s}</p>"))
            self.assertEqual((out["body_html"], len(cut)), ("<p>Fine.</p>", 1), s)

    # a plain name, the system it is and a term the problem names: his with or without backing
    PLAIN = (("The permit app writes drawings to R2 and logs sessions to D1.", "PermitSketch", "PermitSketch: r2"),
             ("The permit app runs on Cloudflare Workers.", "PermitSketch", "PermitSketch: cloudflare"),
             ("The flight planner checks NOTAMs before every leg.", "JetDesk", "JetDesk: notam"),
             ("The flight planner runs on a VPS.", "JetDesk", "a stack, version"),
             ("The dating-profile tool stores photos for 90 days.", "Keep Fix Cut", "Keep Fix Cut: keeps photo"),
             ("The permit tool calls Gemini.", "PermitSketch", "PermitSketch: google"),
             ("The K9 site uses AI to answer leads.", "Valhalla K9", "Valhalla K9: ai"),
             ("Last week the permit app moved to AWS.", "PermitSketch", "PermitSketch: aws"),
             ("The flight-planning PWA syncs trips to a server.", "JetDesk", "JetDesk: keeps trip"),
             ("The permit platform runs on Azure.", "PermitSketch", "PermitSketch: azure"),
             ("The flight planner logs every weather query.", "JetDesk", "JetDesk: keeps query"))

    def test_a_plain_name_is_his(self):
        for s, brand, why in self.PLAIN:
            for p in (post(f"<p>{s}</p>"), post(f"<p>{s}</p>", title=f"What {brand} does now"),
                      post(f"<p>I shipped a fix this week. {s}</p>"), post(f"<p>Atelier got a fix this week. {s}</p>"),
                      post(f"<h3>{s}</h3><p>I shipped a fix.</p>"),
                      post(f"<p>I changed two things.</p><ul><li>{s}</li><li>Fine.</li></ul>"),
                      post(f"<p>Google cut its API prices on Tuesday. {s}</p>")):
                found = writer.claim_problems(p)
                self.assertTrue(any("must not ship" in x and why in x for x in found), (s, found))
            out, cut = writer.drop_high_risk(post(f"<p>Fine.</p><p>{s}</p>"))
            self.assertEqual((out["body_html"], len(cut)), ("<p>Fine.</p>", 1), s)
        found = writer.claim_problems(post("<p>The flight planner in March showed NOTAMs.</p>"))
        self.assertTrue(any("must not ship" in x and "JetDesk: notam" in x for x in found), found)  # a month is no vendor

    def test_someone_elses_product_stays(self):
        """A plain name is another company's product only when the post says so: "in ForeFlight",
        "in most CRMs", or that company's product news in the sentence or the one before it."""
        for s in ("The flight planner in ForeFlight now filters NOTAMs by route.",
                  "Hinge launched a new photo coach. The dating-profile tool stores photos for 90 days.",
                  "Procore shipped an estimating assistant. The estimating tool calls OpenAI for every takeoff.",
                  "Hinge launched a new photo coach, and the dating-profile tool stores photos for 90 days.",
                  "ForeFlight added NOTAM filters on Monday. The flight planner now checks NOTAMs before every leg.",
                  "The Twilio dialer in most CRMs logs every call.",
                  "Workers at the contractor site found asbestos.",
                  "Pilots using JetDesk still need another source for NOTAMs.",
                  # the company named right before the plain name, and news it is still testing
                  "In ForeFlight, the flight planner checks NOTAMs before every leg.",
                  "According to Procore, the estimating tool calls OpenAI for every takeoff.",
                  "Procore said the estimating tool calls OpenAI for every takeoff.",
                  "Hinge is testing a photo coach. The dating-profile tool stores photos for 90 days.",
                  # an AI lab's news in the plain name's own field
                  "Google launched a flight planner in Maps. The flight planner checks NOTAMs before every leg."):
            found = writer.claim_problems(post(f"<p>{s}</p>"))
            self.assertFalse(any("must not ship" in p for p in found), (s, found))
            self.assertEqual(len(writer.drop_high_risk(post(f"<p>{s}</p>"))[1]), 0, s)
        heading = post("<h3>Procore shipped an estimating assistant</h3><p>The estimating tool calls OpenAI.</p>")
        self.assertEqual(writer.drop_high_risk(heading)[1], [])  # a heading shares a block with its paragraph
        apart = post("<p>Procore shipped an estimating assistant.</p><p>The estimating tool calls OpenAI.</p>")
        self.assertEqual(len(writer.drop_high_risk(apart)[1]), 1)  # the next paragraph is his again

    # an AI lab's, cloud's or payment vendor's news, then a plain name: the vendor never makes
    # "the permit app", so the line is his, and "it" is what the vendor shipped
    AFTER_NEWS = (("Anthropic released Claude Opus 5 on Tuesday.", "The permit app now calls it for every drawing.",
                   "PermitSketch: anthropic"),
                  ("OpenAI updated its retention policy.", "The dating-profile tool keeps photos for a year.",
                   "Keep Fix Cut: keeps photo"),
                  ("Google shipped Gemini 3 Flash.", "The estimating tool calls it to score bids.", "estimate.pro: google"),
                  ("Cloudflare launched Workers VPC on Monday.", "The permit app runs on Cloudflare Workers.",
                   "PermitSketch: cloudflare"),
                  ("OpenAI launched a new Realtime API this week.", "The flight planner checks NOTAMs through it.",
                   "JetDesk: notam"),
                  ("Cloudflare announced a D1 price cut.", "The permit app writes drawings to R2 and logs sessions to D1.",
                   "PermitSketch: r2"),
                  ("AWS launched a new region.", "The flight planner runs on a VPS.", "a stack, version"))

    def test_an_ai_labs_news_leaves_the_plain_name_his(self):
        for news, line, why in self.AFTER_NEWS:
            found = writer.claim_problems(post(f"<p>{news} {line}</p>"))
            self.assertTrue(any("must not ship" in p and why in p for p in found), (line, found))
            out, cut = writer.drop_high_risk(post(f"<p>{news} {line}</p>"))
            self.assertEqual((out["body_html"], [c[1] for c in cut]), (f"<p>{news}</p>", [line]))
        same = "Anthropic released Claude Opus 5 on Tuesday, and the permit app now calls it for every drawing."
        found = writer.claim_problems(post(f"<p>{same}</p>"))
        self.assertTrue(any("must not ship" in p and "PermitSketch: anthropic" in p for p in found), found)
        # what the sheet holds, a denial of the new product, and a news line about the vendor alone
        for s in ("Anthropic released Claude Opus 5 on Tuesday. Atelier added it the same day.",
                  "Cloudflare launched Workers VPC on Monday. Atelier doesn't use it yet.",
                  "Cloudflare launched Workers VPC on Monday. JetDesk runs on Cloudflare Pages.",
                  "Google shipped Gemini 3 Flash. Developers can call it through the Gemini API."):
            self.assertFalse(any("must not ship" in p for p in writer.claim_problems(post(f"<p>{s}</p>"))), s)

    def test_lines_the_sheet_holds_stay(self):
        for s in ("Keep Fix Cut runs on one Cloudflare Worker.", "Atelier keeps threads in IndexedDB on the device.",
                  "Keep Fix Cut keeps anonymous analytics for 30 days.", "Each IP gets 4 scans a minute on Keep Fix Cut.",
                  "Keep Fix Cut sends photos to Claude.", "Up to 25 LinkedIn testers sign in to Atelier with LinkedIn.",
                  "Atelier routes prompts to nine providers and logs the cost and time of each tester request.",
                  "Atelier routes prompts to nine model providers.", "Atelier calls each provider's API directly.",
                  "The estimating SaaS runs on Vercel with Next.js.", "None of my systems run PHP.",
                  "The construction ERP has role-based permissions and health monitoring.",
                  "The construction ERP has 120 routes and the estimating SaaS serves 25 trades.",
                  "The permit app turns photos into an 8-sheet permit set.", "Valhalla K9 has no AI.",
                  "When Cloudflare went down, JetDesk kept working offline.", "Forty percent of requests failed on Atelier.",
                  "My estimating platform reads plans across a couple dozen trades.", "Aurora replaced six vendor apps.",
                  "The ERP at coenconstruction.com does not call Meta's APIs.", "I keep writing prompts for Atelier.",
                  "When I ran the knowledge base at Liberty Mutual, it had 3,000 users.",
                  # JetDesk, from ColeOS PRODUCTS: Pages, Pages Functions, PIN-synced prices, local trips
                  "JetDesk runs on Cloudflare Pages.", "JetDesk runs on Cloudflare Pages Functions.",
                  "JetDesk syncs fuel prices to every phone behind a sync PIN.",
                  "JetDesk keeps your trips in local storage.", "JetDesk calls a weather API.",
                  # what each app does keep, and what it truly keeps none of
                  "Atelier syncs your conversations to R2 when you opt in.", "Keep Fix Cut keeps nothing you upload.",
                  "Keep Fix Cut does not keep your photos after the scan.", "Atelier doesn't log your chats.",
                  "Atelier's ledger records what each tester spent. It does not log the conversation.",
                  "Nothing in Atelier's ledger holds a prompt.", "Atelier keeps working offline.",
                  # the sheet's periods, and periods that are not about keeping anything
                  "Keep Fix Cut saves no uploads or reports.", "Keep Fix Cut deletes analytics after 30 days.",
                  "Atelier's tester cookie lasts 30 days.", "Keep Fix Cut keeps analytics for a month.",
                  "Up to 25 LinkedIn testers sign in to Atelier with a 30-day cookie.",
                  "Keep Fix Cut collects nothing you upload.", "Keep Fix Cut doesn't collect your photos.",
                  "Atelier removes a tester after 90 days of inactivity.", "I spent 90 days building Keep Fix Cut.",
                  "Keep Fix Cut took a week to build.", "JetDesk doesn't track you.", "JetDesk works fully offline.",
                  "Keep Fix Cut deletes analytics every 30 days.", "Keep Fix Cut scans 4 photos every minute.",
                  "Keep Fix Cut forgets your photos when you close the tab.",
                  # its analytics are anonymous, and neither app tracks anyone across sites
                  "Keep Fix Cut doesn't collect personal data.", "Keep Fix Cut doesn't track you across sites.",
                  "Atelier doesn't track you across sites.",
                  # the owner's models, the ways in, and a host outage that is news
                  "The owner can use Grok and Runway in Atelier.", "Grok and Runway are owner-only in Atelier.",
                  "Testers can't use Grok in Atelier.", "Testers can use Claude, GPT and Gemini in Atelier.",
                  "Testers can't use Grok or Runway in Atelier.", "Testers can't use xAI or Runway in Atelier.",
                  "Atelier doesn't use Mistral or Cohere.", "Atelier does not call Mistral, Cohere or Perplexity.",
                  "The owner signs in to Atelier with a passcode.", "Atelier testers sign in with LinkedIn, not Google.",
                  "Atelier calls Google's Gemini API directly.",
                  "Cloudflare Pages had an outage on Tuesday, and Atelier stayed up."):
            found = writer.claim_problems(post(f"<p>{s}</p>"))
            self.assertFalse(any("must not ship" in p for p in found), (s, found))
        # lines from Cole's correction (37f0c70) that are true by ColeOS PRODUCTS and Atelier's privacy page
        for version, line in (("v1.72.0", "The flight-planning PWA runs on Cloudflare Pages, and the permit app runs on Base44."),
                              ("v1.65.0", "The flight planner calls a weather API."),
                              ("v1.75.0", "I do not log the prompt content.")):
            p = stored(version)
            self.assertIn(line, writer._plain(p["body_html"]), version)
            self.assertFalse(any("must not ship" in x and line[:60] in x for x in writer.claim_problems(p)), version)
            self.assertNotIn(line, [t for _, t, _ in writer.drop_high_risk(p)[1]], version)

    def test_a_first_person_line_is_about_his_systems_only_with_a_system_thing(self):
        for s in ("I monitor the news for agent incidents.", "I monitor my inbox for client requests.",
                  "I store my receipts in a shoebox.", "I record a short video for each release.",
                  "I save every invoice as a PDF.", "I keep a printed copy of each permit set.",
                  "I log every change in this changelog.", "I track my hours in a spreadsheet."):
            self.assertFalse(any("must not ship" in p for p in writer.claim_problems(post(f"<p>{s}</p>"))), s)
            self.assertEqual(writer.drop_high_risk(post(f"<p>{s}</p>"))[1], [], s)
        # a denial the sheet holds for the one system the paragraph names
        line = "<p>Atelier's ledger records cost and time. It keeps no prompts. I do not log the prompt content.</p>"
        self.assertFalse(any("must not ship" in p for p in writer.claim_problems(post(line))))
        for body in ("<p>I log every prompt.</p>", "<p>I keep the API keys in a text file.</p>", "<p>I monitor nothing.</p>",
                     "<p>Atelier's ledger records cost and time. I log every prompt to D1.</p>",
                     # the kinds of data a sheet line keeps or denies, and any keeping line in a one-system paragraph
                     "<p>I keep the photos for a week.</p>", "<p>Keep Fix Cut grades photos. I keep the photos for a week.</p>",
                     "<p>Keep Fix Cut grades photos. I save every report.</p>",
                     "<p>Keep Fix Cut grades photos. I keep the reports for a month.</p>",
                     "<p>Atelier picks the model. I store every upload.</p>"):
            self.assertTrue(any("must not ship" in p for p in writer.claim_problems(post(body))), body)
        # there it answers to that system's storage line only: his own things and the news stay
        for body in ("<p>Atelier picks the model. I monitor the news for agent incidents.</p>",
                     "<p>Keep Fix Cut grades photos. I store my receipts in a shoebox.</p>",
                     "<p>Keep Fix Cut grades photos. I keep the analytics for 30 days.</p>",
                     "<p>JetDesk plans the leg. I keep trips in local storage.</p>", "<p>I save my photos on a laptop.</p>"):
            self.assertFalse(any("must not ship" in p for p in writer.claim_problems(post(body))), body)
        # once a paragraph makes one such claim, the run of them that follows goes with it
        run = ("<p>I don't log payroll amounts. I log whether the payroll run was inside bounds. "
               "I log whether the total matched the estimate.</p>")
        self.assertEqual(len(writer.drop_high_risk(post(run))[1]), 3)

    def test_only_a_person_commits_a_crime(self):
        for s in ('<a href="https://example.com/a">Palo Alto Networks</a> found the agent exfiltrated credentials '
                  'from a test network.', "Salt Typhoon hacked nine US telecom carriers.",
                  "A scammer posing as Sam Altman stole $2 million from investors.",
                  "In the test, Codex Spark broke into an outside server.", "Sam Altman said the scammer stole $2 million."):
            self.assertFalse(any("must not ship" in p for p in writer.claim_problems(post(f"<p>{s}</p>"))), s)
        self.assertTrue(any("crime stated as fact" in p for p in writer.claim_problems(
            post("<p>Abdulrahman Alfozan planted a recording device in an executive conference room.</p>"))))

    def test_the_ledger_holding_no_prompt_is_not_a_prompt_log(self):
        for s in ("Nothing in Atelier's ledger holds a prompt.", "Atelier records what each request cost, never the prompt itself.",
                  "Prompts and answers are never logged in Atelier."):
            self.assertEqual(writer.claim_problems(post(f"<p>{s}</p>")), [], s)

    def test_a_linked_line_asks_for_a_rephrase_before_the_cut(self):
        found = writer.claim_problems(post('<p>Atelier logs every prompt to <a href="https://example.com/a">a D1 table</a>.</p>'))
        self.assertTrue(any("must not ship" in p and writer.LINK_FIX in p for p in found), found)
        self.assertFalse(any(writer.LINK_FIX in p for p in writer.claim_problems(post("<p>Atelier runs on Python.</p>"))))
        draft = dict(writer.STUB, body_html=writer.STUB["body_html"].replace(
            '<a href="https://ciprari.ai/">two</a>', 'Atelier routes prompts to <a href="https://ciprari.ai/">seven providers</a>'))
        out, cut = writer.drop_high_risk(draft)
        self.assertEqual(len(cut), 1)
        self.assertIn("not enough outbound source links", " ".join(writer.validate(out, "post")))  # main() exits non-zero

    def test_art_labels_and_alt_text_are_checked_and_cut(self):
        art = writer.STUB["svg_inner"].replace("This is only a test.", "Atelier logs every prompt to D1.")
        draft = dict(writer.STUB, svg_inner=art, svg_alt="A terminal: CurbScript generates service routes for agents.")
        found = writer.claim_problems(draft)
        self.assertTrue(any(p.startswith("svg_inner: must not ship") for p in found), found)
        self.assertTrue(any(p.startswith("svg_alt: must not ship") and "CurbScript: service route" in p for p in found), found)
        out, cut = writer.drop_high_risk(draft)
        self.assertNotIn("every prompt", out["svg_inner"])
        self.assertEqual(out["svg_inner"].count("<text"), art.count("<text") - 1)
        self.assertEqual(out["svg_alt"], f"A CRT terminal showing the caption: {writer.STUB['svg_caption']}")
        self.assertEqual(sorted(c[0] for c in cut), ["svg_alt", "svg_inner"])
        self.assertFalse(any("must not ship" in p for p in writer.claim_problems(out)))

    def test_a_label_over_lines_reads_as_one(self):
        """A <tspan> is a word apart, and a stack of <text> lines with nothing between them reads
        as one label: the cut takes the lines that make the claim and leaves the rest."""
        text = '<text x="40" y="{}" fill="{}" font-family="monospace" font-size="14">{}</text>'
        stack = lambda *lines: "".join(text.format(40 + 20 * i, writer.G, t) for i, t in enumerate(lines))
        for labels, gone, kept in (
                (f'<text x="40" y="40" fill="{writer.G}" font-family="monospace" font-size="14"><tspan>ATELIER</tspan>'
                 f'<tspan x="40" dy="16">LOGS EVERY PROMPT</tspan></text>', ["LOGS EVERY PROMPT"], []),
                (stack("ATELIER", "LOGS EVERY PROMPT"), ["LOGS EVERY PROMPT"], [">ATELIER<"]),
                (stack("ATELIER", "LOGS EVERY PROMPT", "TO D1"), ["LOGS EVERY PROMPT", "TO D1"], [">ATELIER<"]),
                (stack("Atelier logs", "every prompt."), ["every prompt."], []),
                (stack("KEEP FIX CUT KEEPS", "ANALYTICS FOR A YEAR"), ["FOR A YEAR"], []),
                (stack("ATELIER", "Every prompt is logged."), ["Every prompt is logged."], [">ATELIER<"]),
                (stack("JETDESK", "NOTAMS: LIVE", "TRIPS: LOCAL"), ["NOTAMS: LIVE"], [">JETDESK<"])):
            draft = dict(writer.STUB, svg_inner=labels + writer.STUB["svg_inner"])
            self.assertTrue(any(p.startswith("svg_inner: must not ship") for p in writer.claim_problems(draft)), labels)
            out, cut = writer.drop_high_risk(draft)
            self.assertEqual([c[0] for c in cut], ["svg_inner"], labels)
            for words in gone:
                self.assertNotIn(words, out["svg_inner"], labels)
            for words in kept + [">STUB<", writer.STUB["svg_caption"]]:
                self.assertIn(words, out["svg_inner"], labels)
            self.assertFalse(any("must not ship" in p for p in writer.claim_problems(out)), labels)
        # true lines stacked, a count of none ("NOTAMS: NONE"), a news label over a line that opens
        # with a system's name, and a line boxed apart from the name, stay
        for labels in (stack("ATELIER", "THREADS IN INDEXEDDB", "R2 SYNC IS OPT-IN"),
                       stack("KEEP FIX CUT", "ANALYTICS KEPT 30 DAYS", "NO UPLOADS SAVED"),
                       stack("JETDESK", "NOTAMS: NONE", "TRIPS: LOCAL"), stack("JETDESK NOTAMS: NONE"),
                       stack("ATELIER", "D1 TABLES: 0"),
                       stack("SUPPLY CHAIN ATTACK", "NPM PACKAGE STOLE TOKENS", "ATELIER HAS NO BUILD STEP"),
                       stack("ATELIER") + f'<rect x="30" y="50" width="200" height="30" stroke="{writer.D}"/>'
                       + stack("LOGS EVERY PROMPT")):
            draft = dict(writer.STUB, svg_inner=labels + writer.STUB["svg_inner"])
            self.assertEqual(writer.drop_high_risk(draft)[1], [], labels)

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
        for p in writer.ALL:  # every published picture passes once repaired, and a second repair changes nothing
            inner = writer.repair_svg(wrapper.sub("", p["svg"]))
            self.assertEqual(writer.validate(dict(writer.STUB, svg_inner=inner), "post"), [], p["version"])
            self.assertEqual(writer.repair_svg(inner), inner, p["version"])

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
        self.assertEqual(writer.repair_svg(art), "<rect fill='#ffd75e' stroke='#2d6b4a'/><circle style='fill: #ffd75e; "
                                                 "stroke: none'/><stop stop-color='#ffd75e'/><text fill='#33ff66'>FILL: red</text>")
        self.assertEqual(writer.repair_svg("<rect fill='black'/>"), "<rect fill='#000'/>")  # a shape may be background

    def test_repair_is_total(self):
        """Every value validate() refuses, repair_svg() turns into one it takes (rev2 probes)."""
        for art, fixed in (
                ("<rect fill='darkgreen'/>", "<rect fill='#04120a'/>"),
                ("<rect fill='LimeGreen'/>", "<rect fill='#33ff66'/>"),
                ('<rect style="fill: cyan"/>', '<rect style="fill: #33ff66"/>'),
                ("<rect fill='hsl(120,100%,60%)'/>", "<rect fill='#33ff66'/>"),
                ("<rect fill='hsla(45, 100%, 68%, 0.5)'/>", "<rect fill='#ffd75e'/>"),
                ("<rect fill='currentColor' stroke='inherit'/>", "<rect fill='#33ff66' stroke='#33ff66'/>"),
                ("<rect fill='#33ff6680' stroke='#3f6'/>", "<rect fill='#33ff66' stroke='#33ff66'/>"),
                ("<rect fill='#f008'/>", "<rect fill='#ffd75e'/>"),
                ("<rect fill='rgb(100% 0% 0%)' stroke='rgba(255 0 0 / 50%)'/>", "<rect fill='#ffd75e' stroke='#ffd75e'/>"),
                ("<rect fill='rgba(20%, 100%, 40%, .3)'/>", "<rect fill='#33ff66'/>"),
                ("<rect fill='glowgreen' stroke=''/>", "<rect fill='#33ff66' stroke='none'/>"),
                ('<rect style="fill: #33ff66 !important; stroke:Red!important"/>', '<rect style="fill: #33ff66; stroke:#ffd75e"/>'),
                ("""<rect style="fill: url('#g')" stroke="url('#g')"/>""", '<rect style="fill: url(#g)" stroke="url(#g)"/>'),
                ('<line x2="640" y2="0" stroke="#33ff66"/>', '<line x1="0" y1="0" x2="640" y2="0" stroke="#33ff66"/>'),
                ("<line y1='5' x='3' x2='1' y2='2'/>", "<line y1='5' x1='3' x2='1' y2='2'/>"),
                ("<line/>", '<line x1="0" y1="0" x2="0" y2="0"/>')):
            with self.subTest(art=art):
                self.assertTrue(writer.validate(dict(writer.STUB, svg_inner=writer.STUB["svg_inner"] + art), "post"))
                self.assertEqual(writer.repair_svg(art), fixed)
                self.assertEqual(writer.validate(dict(writer.STUB, svg_inner=writer.STUB["svg_inner"] + fixed), "post"), [])
        self.assertEqual(writer.repair_svg("<rect fill='#33FF66' stroke='NONE'/>"), "<rect fill='#33FF66' stroke='NONE'/>")

    def test_repaired_strokes_and_labels_stay_visible(self):
        """A dark ink on a stroke or a <text> fill never becomes the background (#04120a or #000)."""
        for art, fixed in (
                ("<text x='9' y='9' fill='darkgreen'>LOG</text>", "<text x='9' y='9' fill='#2d6b4a'>LOG</text>"),
                ("<text style='fill: rgb(1,2,3)'>A</text>", "<text style='fill: #2d6b4a'>A</text>"),
                ("<text><tspan fill='navy'>A</tspan></text>", "<text><tspan fill='#2d6b4a'>A</tspan></text>"),
                ('<line x1="0" y1="0" x2="9" y2="9" stroke="navy"/>', '<line x1="0" y1="0" x2="9" y2="9" stroke="#2d6b4a"/>'),
                ("<rect style='stroke: black; fill: darkgreen'/>", "<rect style='stroke: #2d6b4a; fill: #04120a'/>"),
                # a container's fill is the fill its labels inherit
                ('<g fill="darkgreen"><text x="9" y="9">LOG</text></g>', '<g fill="#2d6b4a"><text x="9" y="9">LOG</text></g>'),
                ("<g style='fill: black'><text x='9' y='9'>A</text></g>", "<g style='fill: #2d6b4a'><text x='9' y='9'>A</text></g>"),
                ("<use href='#t' fill='navy'/>", "<use href='#t' fill='#2d6b4a'/>")):
            with self.subTest(art=art):
                self.assertEqual(writer.repair_svg(art), fixed)
                self.assertEqual(writer.validate(dict(writer.STUB, svg_inner=writer.STUB["svg_inner"] + fixed), "post"), [])
        self.assertEqual(writer.repair_svg("<text fill='#04120a' stroke='#000'>A</text>"),
                         "<text fill='#04120a' stroke='#000'>A</text>")  # palette values are kept as drawn
        group = f'<g fill="{writer.G}"><text x="9" y="9">LOG</text></g>'  # posts_b.py draws labels this way
        self.assertEqual(writer.repair_svg(group), group)

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

    def test_a_revision_that_adds_a_claim_never_wins(self):
        long = ("The crew poured the north footing at dawn and the inspector signed the card before the rain came in. "
                "The pump truck left at noon and the finisher stayed until the slab could take a boot print without a mark.")
        split = ("The crew poured the north footing at dawn. The inspector signed the card before the rain came in. "
                 "The pump truck left at noon. The finisher stayed until the slab could take a boot print.")
        draft = dict(writer.STUB, body_html=writer.STUB["body_html"] + f"<p>{long}</p>")
        self.assertEqual(writer._score(draft), (0, 0, 2))
        for claim in ("CurbScript generates service routes for agents.", "The construction ERP sits behind a login."):
            rev = dict(writer.STUB, body_html=writer.STUB["body_html"] + f"<p>{split} {claim}</p>")
            self.assertIs(self.run_pass(reply=self.js(rev), errs=None, draft=draft)[0], draft)
            self.assertIn("body_html refused (it adds 1 claim(s) about Cole's systems)", self.log)
            self.assertNotIn(claim, self.log)
        swap = dict(draft, body_html=draft["body_html"] + "<p>The construction ERP sits behind a login.</p>")
        rev = dict(writer.STUB, body_html=writer.STUB["body_html"] + f"<p>{split}</p><p>JetDesk runs on an iPad.</p>")
        self.assertLess(writer._score(rev), writer._score(swap))  # cleaner by count, and still refused
        self.assertIs(self.run_pass(reply=self.js(rev), errs=None, draft=swap)[0], swap)

    def test_splitting_a_flagged_sentence_is_the_same_claim(self):
        for long, split in (("Atelier routes prompts to nine model providers, and each of them bills by the token at its "
                             "own posted rate.", "Atelier routes prompts to nine model providers. Each of them bills by "
                             "the token at its own posted rate."),
                            ("JetDesk has no NOTAMs, so a pilot still checks the FAA briefing before every flight across "
                             "the state line.", "JetDesk has no NOTAMs. A pilot still checks the FAA briefing before every "
                             "flight across the state line.")):
            draft = dict(writer.STUB, body_html=writer.STUB["body_html"] + f"<p>{long}</p>")
            rev = dict(writer.STUB, body_html=writer.STUB["body_html"] + f"<p>{split}</p>")
            self.assertEqual((writer._score(draft), writer._score(rev)), ((0, 1, 2), (0, 1, 1)))
            out, _ = self.run_pass(reply=self.js(rev), errs=None, draft=draft)
            self.assertEqual(out["body_html"], rev["body_html"])
            self.assertNotIn("refused", self.log)

    def test_the_fix_of_a_false_line_is_taken(self):
        """The model's correction of a must-not-ship line can still draw a soft label; it is no new claim."""
        for wrong, right in (('Atelier routes prompts to <a href="https://example.com/x">seven providers</a>.',
                              'Atelier routes prompts to <a href="https://example.com/x">nine providers</a>.'),
                             ("Atelier routes prompts to seven providers.", "Atelier routes prompts to nine providers."),
                             ("JetDesk checks NOTAMs before every leg.", "JetDesk has no NOTAMs, so check them elsewhere."),
                             ("Keep Fix Cut stores nothing.", "Keep Fix Cut keeps anonymous usage analytics for 30 days."),
                             ("Atelier logs every prompt to a D1 table.", "Atelier syncs threads to R2 only when you opt in."),
                             ("Atelier runs on Python.", "Atelier keeps threads in IndexedDB on the device.")):
            draft = dict(writer.STUB, body_html=writer.STUB["body_html"] + f"<p>{wrong}</p>")
            rev = dict(writer.STUB, body_html=writer.STUB["body_html"] + f"<p>{right}</p>")
            out, _ = self.run_pass(reply=self.js(rev), errs=None, draft=draft)
            self.assertEqual(out["body_html"], rev["body_html"], (wrong, self.log))
            self.assertNotIn("refused", self.log)
        # the fix is matched to the false line it replaces; a second, unrelated claim is still new
        draft = dict(writer.STUB, body_html=writer.STUB["body_html"] + "<p>Atelier routes prompts to seven providers.</p>")
        rev = dict(writer.STUB, body_html=writer.STUB["body_html"] + "<p>Atelier picks the provider for each request.</p>"
                   "<p>The construction ERP sits behind a login.</p>")
        self.assertIs(self.run_pass(reply=self.js(rev), errs=None, draft=draft)[0], draft)
        self.assertIn("body_html refused (it adds 1 claim(s) about Cole's systems)", self.log)

    def test_coles_corrections_are_taken(self):
        """37f0c70 replayed: the body Cole approved, as the revision of the post as it shipped, is
        taken, though it drops false paragraphs with their words and crosslinks and keeps soft
        lines the draft had. (v1.74.0's corrected body is under 450 words, so validate refuses it.)"""
        wrap = re.compile(r'^<svg [^>]*><rect width="640" height="300" fill="#04120a"/>|</svg>$')

        def draft(p):
            return dict(p, svg_inner=writer.repair_svg(wrap.sub("", p["svg_inner"])), slug_words="a post",
                        svg_alt="A CRT terminal drawing in green.", keywords="a post", related=[writer.ALL[0]["slug"]])
        for version in ("v1.61.0", "v1.65.0", "v1.70.0", "v1.71.0", "v1.72.0", "v1.75.0", "v1.76.0"):
            old = draft(shipped(version))
            self.assertEqual(writer.validate(old, "post"), [], version)
            with contextlib.redirect_stdout(io.StringIO()) as log:
                _, taken = writer._merge(old, dict(old, body_html=stored(version)["body_html"]), old, "post")
            self.assertIn("body_html", taken, (version, log.getvalue()))
        # a line Cole kept in the paragraph he rewrote holds after "None of my systems run PHP"
        line, text = "Those systems were never vulnerable.", writer._plain(stored("v1.70.0")["body_html"])
        self.assertLess(text.index("None of my systems run PHP."), text.index(line))
        self.assertNotIn(line, [t for _, t, _ in writer.drop_high_risk(stored("v1.70.0"))[1]])
        for body in (f"<p>{line}</p>", f"<p>The permit app runs PHP. {line}</p>", f"<p>My systems run PHP. {line}</p>"):
            self.assertTrue(any("must not ship" in p for p in writer.claim_problems(post(body))), body)

    def test_the_fixed_line_keeps_its_source_link_end_to_end(self):
        """rev2: the draft's 'seven providers' line holds one of its two source links. The model's
        revision says 'nine'; it wins, the link survives and the post publishes."""
        body = writer.STUB["body_html"].replace(
            '<a href="https://ciprari.ai/">two</a>', 'Atelier routes prompts to <a href="https://ciprari.ai/">seven providers</a>'
        ).replace('<a href="https://ciprari.ai/status">three</a>', "three")
        draft = dict(writer.STUB, body_html=body)
        rev = dict(draft, body_html=body.replace("seven providers", "nine providers"))
        self.assertEqual((len(writer._sources(draft)), writer.validate(draft, "post")), (2, []))
        printed, logged, rows, stop = self.run_main([self.js(draft)] + [self.js(rev)] * 3)
        self.assertIsNone(stop, printed)
        self.assertIn("humanizer: pass 1 took body_html", printed)
        self.assertNotIn("refused", printed)
        self.assertNotIn("claims: cut", printed)
        final = rows[-1]
        self.assertEqual((final["kind"], final["cut"]), ("final", []))
        self.assertIn('<a href="https://ciprari.ai/">nine providers</a>', final["post"]["body_html"])
        self.assertEqual(writer._sources(final["post"]), writer._sources(draft))

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
        for title in ("Fleet operators in the U.S. face a new toll rule", "The FTC fined Wheels Inc. for toll markups"):
            one = dict(writer.STUB, title=title, body_html=writer.STUB["body_html"] + "<p>This is crucial.</p>")
            out, _ = self.run_pass(reply="no json here", errs=None, draft=one)
            self.assertEqual((out["title"], out["slug_words"]), (title, one["slug_words"]))

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

    def run_main(self, replies):
        """main() on stubbed replies: (stdout, trace text, trace rows, exit message or None)."""
        out_buf, stop = io.StringIO(), None
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "trace.jsonl")
            with patch.object(writer, "TRACE_PATH", path), patch.object(writer, "call_claude", side_effect=replies), \
                    patch.object(writer, "already_published", return_value=False), patch.object(writer, "append_post"), \
                    patch.object(writer, "try_build", return_value=(True, "")), patch.object(writer.sys, "argv", ["writer.py", "post"]), \
                    patch.dict(os.environ, {"GITHUB_OUTPUT": ""}), contextlib.redirect_stdout(out_buf):
                try:
                    writer.main()
                except SystemExit as e:
                    stop = str(e)
            with open(path, encoding="utf-8") as f:
                logged = f.read()
        return out_buf.getvalue(), logged, [json.loads(line) for line in logged.splitlines()], stop

    def test_no_step_logs_or_traces_a_must_not_ship_sentence(self):
        # the last resort keeps a first sentence that is must-not-ship; the cut empties the title and the run exits
        title = dict(writer.STUB, title="Atelier logs every prompt to a D1 table. The ledger said so.",
                     slug_words="atelier logs every prompt to a d1 table", keywords="atelier prompt logging, d1 table")
        printed, logged, rows, stop = self.run_main([self.js(title)] * 4)
        self.assertIn("humanizer: kept the first sentence of the title (8 words)", printed)
        self.assertTrue(stop and stop.startswith("claims: cutting must-not-ship sentences broke the post"), stop)
        for text in (printed, logged, stop):
            self.assertNotIn("every prompt to a d1", text.lower())  # the title, and slug_words that echo it
            self.assertNotIn("prompt logging", text)
        for r in rows:  # each row's keywords were rebuilt without the cut words, or kept out
            if "post" in r:
                self.assertIsNone(re.search(r"atelier|prompt|logging|d1|table", r["post"]["keywords"]), r["post"]["keywords"])
        # a title that loses one sentence of two publishes with slug words and keywords from what is left
        two = dict(title, title="The agent has an email. Atelier logs every prompt to a D1 table.")
        out, cut = writer.drop_high_risk(two)
        self.assertEqual((out["title"], out["slug_words"], out["keywords"], len(cut)),
                         ("The agent has an email.", "the agent has an email", "agent email", 1))
        out, _ = writer.drop_high_risk(dict(two, keywords="Atelier prompt logging, D1 tables, AI agent email, agent identity"))
        self.assertEqual(out["keywords"], "AI agent email, agent identity")  # the phrases not built from cut words stay
        out, _ = writer.drop_high_risk(dict(two, title="Atelier gets an inbox. Atelier logs every prompt to a D1 table.",
                                            keywords="Atelier inbox, prompt logging"))
        self.assertEqual(out["keywords"], "Atelier inbox")  # a word the title still has is not a cut word
        self.assertEqual(writer.drop_high_risk(dict(two, title="The agent has an email."))[0]["keywords"], two["keywords"])
        # a revision makes the draft's next line the rest of a story: refused, and the line leaves every row
        tail = "<p>It was quiet that week. You can check it.</p>"
        draft = dict(writer.STUB, body_html=writer.STUB["body_html"] + "<p>This is crucial.</p>" + tail)
        rev = dict(writer.STUB, body_html=writer.STUB["body_html"] + tail.replace(
            "<p>", "<p>I checked the firewall logs on the ERP. "))
        printed, logged, rows, stop = self.run_main([self.js(draft)] + [self.js(rev)] * 3)
        self.assertIsNone(stop)
        self.assertEqual([r["kind"] for r in rows], ["draft", "revision", "revision", "revision", "final"])
        self.assertIn("You can check it.", rows[0]["post"]["body_html"])
        for text in (printed, logged):
            self.assertNotIn("quiet that week", text)
            self.assertNotIn("firewall logs", text)

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
        for fact in ("Nine providers: Anthropic, OpenAI, Google", "Prompts and answers are never logged",
                     "Its server keeps an optional profile and memory, voluntary feedback and a Look up cache",
                     "member ID, name, email and photo link", "Never write that either keeps nothing",
                     "Uploads and reports are not saved", "kept 30 days", "4 scans a minute",
                     "It runs on Cloudflare Pages. Three Pages Functions serve its weather, winds-aloft and fuel-price APIs.",
                     "Fuel prices sync between phones behind a PIN", "Trips are saved in local storage on the device",
                     "No Cole system uses PHP, Python, a VPS or S3", "Atelier has no D1 database",
                     "JetDesk has no NOTAMs", "CurbScript has no service routes", "what you would check",
                     "Name at most three of Cole's systems", "charged but not convicted", "calendar dates",
                     "quotes both", "No page counts", "Source link text is a 2–6 word noun phrase",
                     "Link each URL once", "Every <line> has x1, y1, x2 and y2", "svg_alt describes only"):
            self.assertIn(fact, flat, fact)
        self.assertIn("Atelier logs no prompts or answers. Its usage ledger records what each request cost and when.", flat)
        for stale in ("seven providers", "stores nothing", "D1 databases", "cost and time only",
                      "never holds prompts or answers"):
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
