from .locationextractor import NamedEntityExtractor, LocationExtractor

def find_locations(url=None, text=None):
    # Finds the name_entities using Spacy's and NLTK's parser
    e = NamedEntityExtractor(url=url, text=text)
    e.find_named_entities() # Calls the method find_named_entities() in locationextractor.py

    # Using the named_entities, find the countries, regions and cities associated with the named_entities.
    locs = LocationExtractor(e.named_entities)
    locs.set_countries()
    locs.set_regions()
    locs.set_cities()
    locs.set_other()

    return locs
