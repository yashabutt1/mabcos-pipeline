"""High-quality LOCAL fallback cards for every pillar.

These run whenever Gemini is unreachable or the free-tier quota is spent, so a
batch always ships at the real quality bar. Every fact here is true and well
established. Each entry is a ready {template, data, caption, kind} result.
"""
from __future__ import annotations

import random

import config

_F = config.CTA_FOLLOW
_S = config.CTA_SAVE
_T = config.CTA_TAG


import re as _re
_EMOJI_TAIL = _re.compile(r'[\U0001F000-\U0001FAFF☀-➿←-⇿️\s]+$')


def _clean_hook(h):
    h = (h or "").strip()
    h = _re.sub(r'^[^\w"“\'‘(]+', "", h)
    return _EMOJI_TAIL.sub("", h).strip()


def _cap(hook, body, tags, cta=_F):
    t = " ".join("#" + x for x in tags[:3])   # FB ≠ IG: keep hashtags light
    return "\n\n".join(p for p in [_clean_hook(hook), body, cta, t] if p)


_EDUCATION = [
    {"template": "card.html.j2", "kind": "education", "data": {
        "series": "Bio · Education", "kicker": "Agricultural Biotech",
        "title": "The crop that quietly cut pesticides worldwide",
        "lede": "Scientists gave crops a gene from the soil microbe <b>Bacillus thuringiensis (Bt)</b>, which makes a natural insecticide. The result reshaped global farming.",
        "stats": [{"n": "9%", "l": "drop in global pesticide use, 1996–2011"},
                  {"n": "$57B", "l": "saved by farmers in pesticide costs"}],
        "callout": "Why it's safe: the <b>Bt protein only binds receptors found in insects</b> — humans, fish and birds don't have them."},
     "caption": _cap("A gene borrowed from soil bacteria cut global pesticide use by 9%",
                     "Bt crops cut pesticide use worldwide and saved farmers tens of billions — because the Bt protein is harmless to us. Which biotech fact surprised you most?",
                     ["biotechnology", "agriculture", "gmo", "science", "biochemistry", "sustainability"])},
    {"template": "card.html.j2", "kind": "education", "data": {
        "series": "Bio · Education", "kicker": "Genomics",
        "title": "Your genome, by the numbers",
        "lede": "The human genome was fully mapped by the Human Genome Project — and the scale is staggering.",
        "stats": [{"n": "3.2B", "l": "base pairs in one human genome"},
                  {"n": "~20K", "l": "protein-coding genes (fewer than expected)"}],
        "callout": "Surprise: we have roughly <b>the same number of genes as a tiny worm</b> — complexity comes from how they're regulated."},
     "caption": _cap("You carry about 20,000 genes — roughly the same count as a roundworm",
                     "3.2 billion base pairs, ~20,000 genes — about as many as a roundworm. The magic is in the regulation. What blew your mind in genetics class?",
                     ["genomics", "dna", "genetics", "biology", "biotechnology", "science"])},
    {"template": "card.html.j2", "kind": "education", "data": {
        "series": "Bio · Education", "kicker": "Molecular Biology",
        "title": "One enzyme that changed biology forever",
        "lede": "<b>PCR</b> copies a single piece of DNA into millions in a few hours — the backbone of diagnostics, forensics and research. Kary Mullis won the 1993 Nobel for it.",
        "stats": [{"n": "1M+", "l": "copies from one DNA strand in ~1 hour"},
                  {"n": "1993", "l": "Nobel Prize in Chemistry for PCR"}],
        "callout": "PCR is why a <b>tiny, degraded DNA sample</b> can identify a virus — or free an innocent person."},
     "caption": _cap("One lab reaction copies a single DNA strand into millions in under an hour",
                     "PCR turns one DNA molecule into millions, fast. It powers diagnostics, forensics and research worldwide. When did you first run (or learn) PCR?",
                     ["pcr", "molecularbiology", "biotechnology", "dna", "science", "biochemistry"])},
]

_BUSINESS = [
    {"template": "card.html.j2", "kind": "business", "data": {
        "series": "Bio · Business Idea", "kicker": "Venture", "title_size": 66,
        "title": "Soil & water testing lab",
        "lede": "Farmers constantly need to know what their land and water can actually grow — and good labs are scarce.",
        "blocks": [{"head": "💡 The idea", "body": "Offer fast soil + water quality testing with clear input recommendations for farms, nurseries and agri-startups."},
                   {"head": "💰 Who pays", "body": "Commercial farms, agribusinesses and co-ops — <b>recurring per-season testing</b>, not one-off sales."},
                   {"head": "🚀 Why now", "body": "Precision agriculture is booming and reliable testing labs barely exist outside big cities.", "tone": "blue"}],
        "footer_sub": "Would you build this? 👇"},
     "caption": _cap("Most farms still can't test their own soil — and the labs barely exist",
                     "Soil & water testing is a recurring, real need with few local labs. Low-ish startup cost, steady customers. Would you run one?",
                     ["biotechnology", "agritech", "startup", "entrepreneur", "biobusiness", "innovation"], cta=_T)},
    {"template": "card.html.j2", "kind": "business", "data": {
        "series": "Bio · Business Idea", "kicker": "Venture", "title_size": 64,
        "title": "Bioinformatics-as-a-service",
        "lede": "Labs generate huge sequencing datasets but often lack the skills to analyze them.",
        "blocks": [{"head": "💡 The idea", "body": "Offer remote data analysis: RNA-seq, variant calling, and clear reports for research labs, clinics and small biotechs."},
                   {"head": "💰 Who pays", "body": "Academic labs and startups that need results, not another full-time hire — <b>per-project or retainer</b>."},
                   {"head": "🚀 Why now", "body": "Sequencing is cheap; analysis talent is the bottleneck everywhere.", "tone": "blue"}],
        "footer_sub": "Tag a bioinformatician 👇"},
     "caption": _cap("Sequencing a genome is now cheap — reading the data is the real bottleneck",
                     "Sequencing is cheap — analysis is the bottleneck. A small team can offer bioinformatics as a service, remotely, worldwide. Who'd you hire first?",
                     ["bioinformatics", "datascience", "startup", "biotechnology", "freelance", "genomics"], cta=_T)},
    {"template": "card.html.j2", "kind": "business", "data": {
        "series": "Bio · Business Idea", "kicker": "Venture", "title_size": 64,
        "title": "Biopesticide manufacturing",
        "lede": "Demand for safer, residue-free crop protection is rising fast.",
        "blocks": [{"head": "💡 The idea", "body": "Produce biological control products — microbial or plant-extract based — that protect crops without synthetic residues."},
                   {"head": "💰 Who pays", "body": "Organic and export-focused farms that need <b>residue-free certification</b> to sell abroad."},
                   {"head": "🚀 Why now", "body": "Export markets increasingly reject chemical residues — demand outpaces local supply.", "tone": "blue"}],
        "footer_sub": "Would you build this? 👇"},
     "caption": _cap("Export farms are losing deals over chemical residues — and biology has the fix",
                     "Biopesticides help farms meet residue-free export rules. Growing demand, few local makers. Could this work where you are?",
                     ["biopesticide", "agritech", "biotechnology", "startup", "sustainability", "farming"], cta=_T)},
]

_DIDYOUKNOW = [
    {"template": "card.html.j2", "kind": "didyouknow", "data": {
        "series": "Did You Know", "title": "How much DNA do you share?", "title_size": 64,
        "lede": "You're more connected to life on Earth than you think. <span class='hl'>% of genes shared with humans:</span>",
        "bars": [{"name": "Chimpanzee", "val": 98}, {"name": "Mouse", "val": 92},
                 {"name": "Zebrafish", "val": 76}, {"name": "Fruit fly", "val": 51},
                 {"name": "Thale cress", "sub": "a weed", "val": 26},
                 {"name": "E. coli", "sub": "bacteria", "val": 18}],
        "footer_sub": "Which number surprised you most? 👇"},
     "caption": _cap("You share 98% of your genes with a chimpanzee — and 18% with a bacterium",
                     "You share ~98% of genes with chimps — and still 18% with a bacterium. Evolution's receipts. Which number surprised you?",
                     ["dna", "evolution", "genetics", "biology", "sciencefacts", "biotechnology"])},
    {"template": "card.html.j2", "kind": "didyouknow", "data": {
        "series": "Did You Know", "title": "The DNA in one cell is 2 metres long",
        "title_size": 60,
        "lede": "If you uncoiled the DNA from a <b>single cell</b>, it would stretch about 2 metres — yet it packs into a nucleus a few microns wide.",
        "callout": "Stretch out <b>all</b> the DNA in your body and it would reach the Sun and back — many times over."},
     "caption": _cap("The DNA in one of your cells would stretch two metres if you uncoiled it",
                     "Every cell packs ~2m of DNA into a nucleus millionths of a metre across. The packing problem alone is a marvel. What fact still amazes you?",
                     ["dna", "cellbiology", "biology", "sciencefacts", "biochemistry", "biotechnology"])},
]

_OPPORTUNE = [  # evergreen, always-true "how to find opportunities" cards
    {"template": "card.html.j2", "kind": "opportune", "data": {
        "series": "Bio · Opportune", "kicker": "Scholarships · Where to look",
        "title": "5 places to find biotech scholarships", "title_size": 56,
        "lede": "Funded study and research abroad is more reachable than most students think. Start here:",
        "blocks": [{"head": "🎓 Fully-funded degrees", "body": "<b>DAAD</b> (Germany), <b>Erasmus Mundus</b> (EU), <b>Chevening</b> (UK), <b>Fulbright</b> (US)."},
                   {"head": "🔬 Research & travel", "body": "<b>ISCB</b> and <b>Keystone Symposia</b> travel awards; <b>EMBO</b> fellowships; society student grants.", "tone": "blue"}],
        "callout": "Tip: follow each body directly and set a reminder <b>one month before</b> every deadline.",
        "callout_tone": "gold", "footer_sub": "Save this for application season 🔖"},
     "caption": _cap("Fully-funded science degrees abroad are more reachable than most students realize",
                     "DAAD, Erasmus Mundus, Chevening, Fulbright, EMBO, ISCB travel awards — real, recurring, and open to students worldwide. Which are you aiming for? 👇",
                     ["scholarships", "stem", "biotechnology", "studyabroad", "students", "opportunity"])},
]

_PAPER = [  # evergreen landmark papers → opportunity
    {"template": "card.html.j2", "kind": "paper", "data": {
        "series": "Paper → Opportunity", "kicker": "Gene Editing", "title_size": 60,
        "title": "The scissors that rewrote biology",
        "blocks": [{"head": "📄 The paper", "body": "Doudna & Charpentier showed <b>CRISPR-Cas9</b> could be programmed to cut DNA at a chosen site (Science, 2012). They won the 2020 Nobel in Chemistry."},
                   {"head": "💰 The opportunity", "body": "It spawned an entire industry — therapeutics, diagnostics, agriculture, and tools. <b>Gene-editing skills are in high demand.</b>", "tone": "blue"}],
        "callout": "For you: learning the <b>tools and ethics</b> of gene editing is one of the most future-proof bets in biology.",
        "callout_tone": "gold", "footer_sub": "Follow for the science behind the startups"},
     "caption": _cap("A single 2012 paper turned gene editing into a programmable tool — and won a Nobel",
                     "CRISPR-Cas9 (Doudna & Charpentier, 2012) turned gene editing into a programmable tool — and a Nobel. Gene-editing skills are now gold. Learning it?",
                     ["crispr", "geneediting", "biotechnology", "science", "nobel", "genetics"])},
    {"template": "card.html.j2", "kind": "paper", "data": {
        "series": "Paper → Opportunity", "kicker": "AI × Biology", "title_size": 60,
        "title": "AI that solved a 50-year puzzle",
        "blocks": [{"head": "📄 The paper", "body": "DeepMind's <b>AlphaFold</b> predicted protein 3D structures from sequence with stunning accuracy — a grand-challenge problem since the 1970s."},
                   {"head": "💰 The opportunity", "body": "Structures for <b>200M+ proteins</b> are now free online, accelerating drug discovery, enzymes and design. AI-for-biology is hiring hard.", "tone": "blue"}],
        "callout": "For you: <b>Python + structural biology + ML</b> is one of the most employable combinations in science today.",
        "callout_tone": "gold", "footer_sub": "Follow for the science behind the startups"},
     "caption": _cap("An AI cracked a 50-year biology problem and released 200 million protein structures for free",
                     "AlphaFold predicted 200M+ protein structures and opened them to everyone — reshaping drug discovery. AI-for-biology skills are in huge demand. Learning them?",
                     ["alphafold", "ai", "bioinformatics", "proteins", "biotechnology", "machinelearning"])},
]

_TECH = [  # photo-hero cards (image filled by caller via _photo_queries)
    {"template": "card_photo.html.j2", "kind": "tech", "data": {
        "layout": "hero", "series": "New Tech", "kicker": "Synthetic Biology",
        "title": "Programming cells like software",
        "lede": "Engineers now design genetic 'circuits' so living cells make medicines, sense toxins, or build materials — on command.",
        "footer_sub": "Follow for the tech shaping biotech",
        "_photo_queries": ["bioreactor laboratory blue", "scientist microscope blue light", "molecular research lab", "laboratory glassware science"]},
     "caption": _cap("Engineers are now writing genetic code the way programmers write software",
                     "Synthetic biology designs genetic circuits so cells make drugs, sense toxins, or build materials. Science fiction becoming lab routine. Excited or wary?",
                     ["syntheticbiology", "biotechnology", "bioengineering", "innovation", "science", "future"])},
    {"template": "card_photo.html.j2", "kind": "tech", "data": {
        "layout": "hero", "series": "New Tech", "kicker": "mRNA Technology",
        "title": "mRNA is a platform, not one vaccine",
        "lede": "mRNA tells your own cells which protein to make — so the <b>same platform</b> is being explored for cancer, rare disease and more.",
        "footer_sub": "Follow for the tech shaping biotech",
        "_photo_queries": ["vaccine vial laboratory", "molecular blue render", "mrna research lab", "scientist lab blue"]},
     "caption": _cap("mRNA was built to make almost any protein — the vaccines were only the beginning",
                     "mRNA is a programmable platform — instruct cells to make almost any protein. Cancer and rare-disease trials are next. Where do you think it goes?",
                     ["mrna", "biotechnology", "vaccines", "innovation", "science", "futuretech"])},
]

_INTERACTIVE = [
    {"template": "card.html.j2", "kind": "interactive", "data": {
        "series": "This or That", "title": "Wet lab or dry lab?", "title_size": 64,
        "lede": "Every life scientist leans one way. Where do you stand?",
        "options": [{"key": "A", "text": "Wet lab — pipettes, cells, the bench"},
                    {"key": "B", "text": "Dry lab — code, data, bioinformatics"}],
        "callout": "Comment <b>A</b> or <b>B</b> 👇 and tell us why.", "callout_tone": "gold",
        "footer_sub": "Vote in the comments 👇"},
     "caption": _cap("Every life scientist eventually picks a side: wet lab or dry lab",
                     "No wrong answer — but defend your pick. 👇 A or B?",
                     ["bioinformatics", "wetlab", "biotechnology", "thisorthat", "lablife", "science"])},
    {"template": "card.html.j2", "kind": "interactive", "data": {
        "series": "Quiz", "title": "Which enzyme unwinds DNA?", "title_size": 60,
        "lede": "No Googling — test yourself 🧠",
        "options": [{"key": "A", "text": "DNA polymerase"}, {"key": "B", "text": "Helicase"},
                    {"key": "C", "text": "Ligase"}, {"key": "D", "text": "Primase"}],
        "callout": "Drop your answer 👇 — reveal in the comments.", "callout_tone": "gold",
        "footer_sub": "Answer below 👇"},
     "caption": _cap("Most people miss this one: which enzyme actually unwinds the DNA double helix?",
                     "A, B, C or D? 👇 No Googling! (It's not polymerase.)",
                     ["biology", "quiz", "molecularbiology", "dna", "biochemistry", "sciencestudent"])},
]

_OPINION = [
    {"template": "card.html.j2", "kind": "opinion", "data": {
        "series": "Hot Take", "kicker": "Opinion", "title": "Bioinformatics should be mandatory in every biology degree",
        "title_size": 56,
        "lede": "You can run a gel, but can you read a <b>FASTQ file</b>? The lab moved to code — the syllabus didn't.",
        "callout": "Agree or disagree? Tell me below 👇", "callout_tone": "gold",
        "footer_sub": "Where do you stand?"},
     "caption": _cap("Every biology student should have to write at least one line of code before they graduate",
                     "The modern lab runs on sequencing data, not just pipettes — yet most degrees still treat coding as optional. "
                     "Students who can't analyze their own data end up dependent on whoever can.\n\nWhere do you stand?",
                     ["bioinformatics", "stem", "biotechnology"])},
    {"template": "card.html.j2", "kind": "opinion", "data": {
        "series": "Hot Take", "kicker": "Opinion", "title": "Your grades matter less than your lab skills",
        "title_size": 58,
        "lede": "A 4.0 that can't troubleshoot a failed PCR loses to a <b>3.2 who can</b>.",
        "callout": "Agree or disagree? 👇", "callout_tone": "gold",
        "footer_sub": "Where do you stand?"},
     "caption": _cap("In biotech hiring, the student who logged 500 hours at the bench usually beats the one with the perfect GPA",
                     "Transcripts show you can pass exams. Hands-on skill shows you can be trusted with a $200k instrument "
                     "and a 3-week experiment. Guess which one managers actually ask about.\n\nWhere do you stand?",
                     ["biotechnology", "careers", "sciencestudent"])},
]

_EVENT = [
    {"template": "card.html.j2", "kind": "event", "data": {
        "series": "Bio · Event", "kicker": "Conferences to watch",
        "title": "The big biotech meetings to know", "title_size": 58,
        "lede": "Put these flagship conferences on your radar — great for talks, posters and networking:",
        "blocks": [{"head": "🧬 Genomics & bioinformatics", "body": "<b>AGBT</b>, <b>ISMB/ECCB</b>, <b>ASHG</b> — cutting-edge sequencing, computation and human genetics."},
                   {"head": "🔬 Cross-field", "body": "<b>Keystone Symposia</b> and <b>Gordon Research Conferences</b> — deep, topic-focused, often with student travel awards.", "tone": "blue"}],
        "callout": "Tip: many offer <b>student travel grants</b> — check each early.", "callout_tone": "gold",
        "footer_sub": "Save for conference season 🔖"},
     "caption": _cap("The conferences where the future of biotech actually gets decided",
                     "AGBT, ISMB, ASHG, Keystone, Gordon — where the field meets. Which would you most want to attend? 👇",
                     ["conference", "genomics", "bioinformatics", "biotechnology", "agbt", "ismb"])},
]

_JOB = [
    {"template": "card.html.j2", "kind": "job", "data": {
        "series": "Bio · Jobs", "kicker": "Where to look",
        "title": "Where to find biotech jobs", "title_size": 58,
        "lede": "Stop scrolling random boards — these are where life-science roles actually get posted:",
        "blocks": [{"head": "🌐 Science-specific", "body": "<b>Nature Careers</b>, <b>Science Careers</b>, <b>BioSpace</b> — academia and industry roles."},
                   {"head": "💼 General + startups", "body": "<b>LinkedIn</b> (set keyword alerts), company career pages, and biotech-startup boards.", "tone": "blue"}],
        "callout": "Tip: <b>set alerts and apply within 48h</b> — early applicants get seen.", "callout_tone": "gold",
        "footer_sub": "Tag a job-seeking friend 👇"},
     "caption": _cap("The biotech jobs you want rarely show up on the boards you're searching",
                     "Nature Careers, Science Careers, BioSpace, LinkedIn alerts, company pages. Set alerts, apply fast. Where are you hunting? 👇",
                     ["jobs", "biotechnology", "careers", "bioinformatics", "hiring", "stem"], cta=_T)},
]

_NEWS = [
    {"template": "card_photo.html.j2", "kind": "news", "data": {
        "layout": "hero", "series": "Bio · News", "kicker": "Stay Current",
        "title": "3 sources every biotech student should follow",
        "lede": "Keep up without the noise: <b>Nature Briefing</b>, <b>STAT News</b> and <b>Endpoints News</b> cover the science and the business.",
        "footer_sub": "Follow for biotech news that matters",
        "_photo_queries": ["newspaper science reading", "laptop news science", "research news desk", "science journal"]},
     "caption": _cap("Three sources will keep you ahead of almost everyone in biotech",
                     "Nature Briefing, STAT, Endpoints — the science and the business, minus the hype. Where do you get yours? 👇",
                     ["biotechnology", "news", "science", "stayinformed", "biotech", "research"])},
]

_TUTORIAL = [
    {"template": "card_photo.html.j2", "kind": "tutorial", "data": {
        "layout": "hero", "series": "Tutorial", "kicker": "Learn Bioinformatics",
        "title": "Learn bioinformatics by solving puzzles",
        "lede": "<b>Rosalind</b> teaches bioinformatics and coding through bite-sized problems — free, hands-on and beginner-friendly.",
        "linkchip": "rosalind.info", "footer_sub": "Save this to learn later 🔖",
        "_photo_queries": ["coding laptop study", "programming screen code", "student laptop learning", "data science screen"]},
     "caption": _cap("You can learn real bioinformatics for free — by solving puzzles, not reading textbooks",
                     "Rosalind teaches coding + biology through puzzles — perfect for beginners. Start 👉 rosalind.info. Tried it yet? 👇",
                     ["bioinformatics", "learntocode", "python", "rosalind", "biotechnology", "students"], cta=_S)},
]

_SUCCESS = [
    {"template": "card_photo.html.j2", "kind": "success", "data": {
        "layout": "full", "series": "Success Story", "kicker": "Perseverance",
        "title": "Rejected for years — then a Nobel",
        "lede": "Katalin Karikó's work on mRNA was doubted and defunded for decades. She kept going — and it became the mRNA vaccines that reached billions.",
        "stat": {"n": "2023", "l": "Nobel Prize for the mRNA breakthrough"},
        "footer_sub": "Follow for stories that inspire",
        "_photo_queries": ["dna helix glowing blue", "vaccine vial laboratory", "molecular research abstract", "laboratory glassware light"]},
     "caption": _cap("Rejected and demoted for decades, her research later won a Nobel and saved millions",
                     "Katalin Karikó was rejected and demoted for years — her mRNA research later won the 2023 Nobel and helped save millions. Your hard season isn't the end. Tag someone who needs this 👇",
                     ["motivation", "mrna", "nobel", "science", "perseverance", "biotechnology"])},
]

BANK = {
    "education": _EDUCATION, "business": _BUSINESS, "didyouknow": _DIDYOUKNOW,
    "opportune": _OPPORTUNE, "paper": _PAPER, "tech": _TECH,
    "interactive": _INTERACTIVE, "opinion": _OPINION, "event": _EVENT, "job": _JOB,
    "news": _NEWS, "tutorial": _TUTORIAL, "success": _SUCCESS,
    # Last-resort fallback if every live feed is down; real posts carry source links.
    "sciencenews": _NEWS,
}


def _norm(s: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def pick(kind: str, avoid=None) -> dict:
    """Return one fallback result dict for a pillar, preferring entries whose
    title isn't in ``avoid`` (a set/list of normalized recent titles)."""
    import copy
    pool = BANK.get(kind) or BANK["education"]
    avoid = {_norm(a) for a in (avoid or [])}
    fresh = [e for e in pool if _norm(e.get("data", {}).get("title", "")) not in avoid]
    return copy.deepcopy(random.choice(fresh or pool))
