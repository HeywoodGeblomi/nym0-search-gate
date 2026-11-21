from nltk.corpus import wordnet as wn
def gloss_texts(w, n=2):
    key = w.split()[0] if " " not in w else w.replace(" ", "_")
    ss = wn.synsets(key, 'v')[:n]
    if not ss and " " in w: ss = wn.synsets(w.split()[0], 'v')[:n]
    return [f"{w}: {s.definition()}" for s in ss]
