import os
import csv
import pycountry
import sqlite3
from .utils import clean
from collections import Counter
import nltk
import spacy
from newspaper import Article

nlp = spacy.load('en_core_web_sm')
"""
Modify 'Bali' and 'padang' labels as Geopolitical Entity (GPE) as it's not identified as one by the model.
This is done using Spacy's Entity Ruler.
Also, made the pattern matching case insensitive using "LOWER".
"""
ruler = nlp.add_pipe("entity_ruler", config= {"overwrite_ents":True})
patterns = [
    {"label": "GPE", "pattern": [{"LOWER":"bali"}]},
    {"label": "GPE", "pattern":[{"LOWER":"padang"}]}
    ]
ruler.add_patterns(patterns)

cur_dir = os.path.dirname(os.getcwd())
with open(cur_dir + "\\s2t-nlp-geo-coordinates\\data\\words_to_ignore.csv") as file:
    words_to_ignore = file.read().splitlines()
words_to_ignore = [a.lower() for a in words_to_ignore]

class NamedEntityExtractor(object):
    """
    This class takes a text or url input and lists out all the named entities 
    (PERSON, PLACE, ORGANIZATION, PRODUCTS) mentioned in the text body 
    with the help of nltk & spacy's named entity recognizer.
    """

    def __init__(self, text=None, url=None):
        if not text and not url:
            raise Exception('Please input any text or url')

        self.text = text
        self.url = url
        self.named_entities = [] # Stores the named_entities in a list

    
    def set_text(self):
        if not self.text and self.url:
            a = Article(self.url)
            a.download()
            a.parse()
            self.text = a.text

    def find_named_entities(self):
        self.set_text()
        
        # NLTK tokenizing and chunking the text
        text = nltk.word_tokenize(clean(self.text))
        nes = nltk.ne_chunk(nltk.pos_tag(text))

        # Spacy's parser
        doc = nlp(clean(self.text)) # Cleans the text before tokenizing using Spacy
        for ent in list(doc.ents):
            if not (str(ent).lower() in words_to_ignore) :
                self.named_entities.append(str(ent))
        
        # NLTK's parser. If a named_entity is not found in Spacy's parser but found in NLTK's parser, then append it to self.named_entities list.
        for ne in nes:
            if type(ne) is nltk.tree.Tree:
                if (ne.label() == 'GPE' or ne.label() == 'PERSON' or ne.label() == 'ORGANIZATION'):
                    l = []
                    for i in ne.leaves():
                        l.append(i[0])
                    s = u' '.join(l)
                    if not (s in self.named_entities):
                        if not (s.lower() in words_to_ignore):
                            self.named_entities.append(s)



class LocationExtractor(object):
    """
    This class takes a list of named entities and finds out the entitites which are place names
    (country, region, city etc) and relationships of countries with regions and cities
    """
    
    def __init__(self, named_entity_words, db_file=None):
        db_file = db_file or os.path.dirname(os.path.realpath(__file__)) + "/locationdata.db"
        self.conn = sqlite3.connect(db_file)
        self.named_entities = named_entity_words

    def populate_db(self):
        cur = self.conn.cursor()
        cur.execute("DROP TABLE IF EXISTS locations")    

        cur.execute("CREATE TABLE locations(geoname_id INTEGER, continent_code TEXT, continent_name TEXT, country_iso_code TEXT, country_name TEXT, subdivision_iso_code TEXT, subdivision_name TEXT, city_name TEXT, metro_code TEXT, time_zone TEXT)")

        with open(cur_dir+"/data/City-Region-Locations.csv",encoding = 'UTF') as info:
            reader = csv.reader(info)
            for row in reader:
                cur.execute("INSERT INTO locations VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?);", row)

            self.conn.commit()


    def db_has_data(self):
        cur = self.conn.cursor()

        cur.execute("SELECT Count(*) FROM sqlite_master WHERE name='locations';")
        data = cur.fetchone()[0]

        if data > 0:
            cur.execute("SELECT Count(*) FROM locations")
            data = cur.fetchone()[0]
            return data > 0

        return False

    
    def is_a_country(self, s): 
        ss = ' '.join([(i[0].upper()+i[1:].lower()) for i in s.split()])
        try:
            pycountry.countries.get(name=ss).alpha_3
            return True
        except AttributeError:
            try:
                pycountry.countries.get(official_name=ss).alpha_3
                return True
            except AttributeError:
                return False


    def set_countries(self):
        """
        Does not return any values.
        It sets the countries from self.named_entities.
        The countries are set in self.countries
        """
        countries = [place 
            for place in self.named_entities if self.is_a_country(place)]

        self.country_mentions = Counter(countries).most_common()
        self.countries = list(set(countries))


    def set_regions(self):
        self.regions = []
        self.country_regions = {}
        self.other_countries = []

        if not self.countries:
            self.set_countries()

        if not self.db_has_data():
            self.populate_db()

        if len(self.named_entities) > 0:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM locations WHERE LOWER(subdivision_name) IN (" + ",".join("?"*len(self.named_entities)) + ")", [p.lower() for p in self.named_entities])
            rows = cur.fetchall()

            for row in rows:
                country = None

                try:
                    country = pycountry.countries.get(alpha_2=row[3])
                    country_name = country.name
                except Exception:
                    country_name = row[4]

                region_name = row[6]

                if region_name not in self.regions:
                    self.regions.append(region_name)

                if country_name not in self.other_countries:
                    self.other_countries.append(country_name)

                if country_name not in self.country_regions:
                    self.country_regions[country_name] = []

                if region_name not in self.country_regions[country_name]:
                    self.country_regions[country_name].append(region_name)


    def set_cities(self):
        self.cities = []
        self.country_cities = {}
        self.region_cities = {}
        self.other_regions = []
        self.address_strings = []

        if not self.countries:
            self.set_countries()

        if not self.regions:
            self.set_regions()

        if not self.db_has_data():
            self.populate_db()
            
        if len(self.named_entities) > 0:
            cur = self.conn.cursor()
            cur.execute("SELECT * FROM locations WHERE LOWER(city_name) IN (" + ",".join("?"*len(self.named_entities)) + ")", [p.lower() for p in self.named_entities])
            rows = cur.fetchall()

            for row in rows:
                country = None

                try:
                    country = pycountry.countries.get(alpha_2=row[3])
                    country_name = country.name
                except Exception:
                    country_name = row[4]

                city_name = row[7]
                region_name = row[6]

                if city_name not in self.cities:
                    self.cities.append(city_name)

                if region_name not in self.other_regions:
                    self.other_regions.append(region_name)

                if country_name not in self.other_countries:
                    self.other_countries.append(country_name)
                    self.country_mentions.append((country_name,1))

                if region_name not in self.region_cities:
                    self.region_cities[region_name] = []

                if city_name not in self.region_cities[region_name]:
                    self.region_cities[region_name].append(city_name)

                if country_name not in self.country_cities:
                    self.country_cities[country_name] = []

                if city_name not in self.country_cities[country_name]:
                    self.country_cities[country_name].append(city_name)

                    if country_name in self.country_regions and region_name in self.country_regions[country_name]:
                        self.address_strings.append(city_name + ", " + region_name + ", " + country_name)


        all_cities = [p for p in self.named_entities if p in self.cities]
        self.city_mentions = Counter(all_cities).most_common()


    def set_other(self):
        if not self.cities:
            self.set_cities()

        def unused(place_name):
            places = self.countries + self.cities + self.regions
            return (place_name.lower() not in [a.lower() for a in places])

        self.other = [p for p in self.named_entities if unused(p)]
