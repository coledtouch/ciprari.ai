"""Offline checks for the humanizer lint and its one revision pass (no API calls)."""
import json
import unittest
from unittest.mock import patch
import writer

LINK = '<a href="https://example.com/a">a source</a> and <a href="https://example.com/b">another</a>'


def post(body, title="The estimator learned a new trick", desc="Short line one. Short line two.",
         caption="One dry line."):
    return {"title": title, "desc": desc, "svg_caption": caption, "body_html": body}


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
        self.assertTrue(any("blockquote must be one line" in p for p in found), found)

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


class HumanizePassTests(unittest.TestCase):
    draft = dict(writer.STUB, body_html=writer.STUB["body_html"] + "<p>This is crucial.</p>")
    messages = [{"role": "user", "content": "write it"}]

    def run_pass(self, reply=None, error=None, errs=()):
        calls = []

        def fake_call(msgs, system, search=True):
            calls.append((msgs, search))
            if error:
                raise error
            return reply

        with patch.object(writer, "call_claude", side_effect=fake_call), \
             patch.object(writer, "validate", return_value=list(errs)):
            out = writer.humanize(self.draft, "post", list(self.messages), "sys")
        return out, calls

    def test_no_problems_means_no_call(self):
        with patch.object(writer, "call_claude") as call:
            self.assertIs(writer.humanize(writer.STUB, "post", self.messages, "sys"), writer.STUB)
        call.assert_not_called()

    def test_cleaner_revision_is_used_without_search(self):
        fixed = dict(writer.STUB)
        out, calls = self.run_pass(reply="```json\n" + json.dumps(fixed) + "\n```")
        self.assertEqual(out, fixed)
        msgs, search = calls[0]
        self.assertFalse(search)
        self.assertEqual([m["role"] for m in msgs], ["user", "assistant", "user"])
        self.assertIn("crucial", msgs[-1]["content"])

    def test_draft_kept_when_revision_fails(self):
        self.assertIs(self.run_pass(error=SystemExit("Claude API error 529"))[0], self.draft)
        self.assertIs(self.run_pass(reply="no json here")[0], self.draft)
        fixed = "```json\n" + json.dumps(writer.STUB) + "\n```"
        self.assertIs(self.run_pass(reply=fixed, errs=["not enough outbound source links"])[0], self.draft)
        worse = dict(self.draft, body_html=self.draft["body_html"] + "<p>Crucial and pivotal!</p>")
        self.assertIs(self.run_pass(reply="```json\n" + json.dumps(worse) + "\n```")[0], self.draft)


    def test_transport_errors_and_odd_types_keep_draft(self):
        import urllib.error
        for err in (urllib.error.URLError("down"), TimeoutError("slow"), ConnectionResetError("reset")):
            self.assertIs(self.run_pass(error=err)[0], self.draft)
        odd = dict(writer.STUB, body_html=["not", "a", "string"])
        self.assertIs(self.run_pass(reply="```json\n" + json.dumps(odd) + "\n```")[0], self.draft)

    def test_revision_that_loses_or_invents_material_is_refused(self):
        body = writer.STUB["body_html"]
        cut = dict(writer.STUB, body_html=body.replace("This sentence pads the stub to a plausible length. " * 30, "", 1))
        dropped = dict(writer.STUB, body_html=body.replace('<a href="https://ciprari.ai/status">three</a>', "three"))
        invented = dict(writer.STUB, body_html=body.replace("<p>End.</p>", '<p>See <a href="https://invented.example/x">this</a>.</p>'))
        for rev in (cut, dropped, invented):
            self.assertIs(self.run_pass(reply="```json\n" + json.dumps(rev) + "\n```")[0], self.draft)

    def test_non_text_slug_keeps_draft(self):
        for bad in (["policy", "ships"], 42):
            rev = dict(writer.STUB, slug_words=bad)
            self.assertIs(self.run_pass(reply="```json\n" + json.dumps(rev) + "\n```")[0], self.draft)

    def test_revision_keeps_related_and_strips_cite(self):
        fixed = dict(writer.STUB, related=["something-else"],
                     body_html=writer.STUB["body_html"].replace("<p>End.</p>", "<p><cite index='1'>End.</cite></p>"))
        out, _ = self.run_pass(reply="```json\n" + json.dumps(fixed) + "\n```")
        self.assertEqual(out["related"], self.draft["related"])
        self.assertNotIn("<cite", out["body_html"])


class PromptTests(unittest.TestCase):
    def test_prompt_knows_fifteen_platforms_and_the_rules(self):
        for mode in ("post", "rollout"):
            system, user = writer.build_prompt(mode, "v9.9.9", "2026-10-12")
            self.assertIn("shipped 15 production platforms", system)
            self.assertIn("keepfixcut.com", system)
            self.assertIn("HUMANIZER", system)
            self.assertIn("Never paste", system)
            self.assertIn("retired two-sentence", user)
            self.assertNotIn("<cite", user)

if __name__ == "__main__":
    unittest.main()
