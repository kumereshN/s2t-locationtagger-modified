import re
import spacy

nlp = spacy.load('en_core_web_sm')

def clean(sentences):
    #removing non_ascii characters
    sentences = "".join(i for i in sentences if ord(i)<128)
    #changing non string to string.
    sentences = str(sentences)
    #1. Removing numbers.
    sentences_1 = re.sub("[^a-zA-Z&',.;-]"," ", sentences)
    #2. Removing multiple spaces with single space
    sentences_2 = re.sub(r'\s+', ' ',sentences_1, flags=re.I)
    # Checks for stop words for each token and then lemmatizes the token
    lemmas = [token.lemma_ for token in nlp(sentences_2) if not token.is_stop]
    newSentence = ' '.join(lemmas)
    return newSentence
