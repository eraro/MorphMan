# -*- coding: utf-8 -*-
import re
from functools import lru_cache

from .morphemes import Morpheme
from .deps.zhon.hanzi import characters
from .mecab_wrapper import getMorphemesMecab, getMecabIdentity
from .deps.jieba import posseg

import csv
import io
import itertools
from .preferences import get_preference as cfg

####################################################################################################
# Base Class
####################################################################################################

class Morphemizer:
    def __init__(self):
        pass
    
    @lru_cache(maxsize=131072)
    def getMorphemesFromExpr(self, expression):
        # type: (str) -> [Morpheme]
        
        morphs = self._getMorphemesFromExpr(expression)
        return morphs
    
    def _getMorphemesFromExpr(self, expression):
        # type: (str) -> [Morpheme]
        """
        The heart of this plugin: convert an expression to a list of its morphemes.
        """
        return []

    def getDescription(self):
        # type: () -> str
        """
        Returns a single line, for which languages this Morphemizer is.
        """
        return 'No information available'

    def getName(self):
        # type: () -> str
        return self.__class__.__name__


####################################################################################################
# Morphemizer Helpers
####################################################################################################

morphemizers = None
morphemizers_by_name = {}

def getAllMorphemizers():
    # type: () -> [Morphemizer]
    global morphemizers
    if morphemizers is None:
        morphemizers = [SpaceMorphemizer(), MecabMorphemizer(), JiebaMorphemizer(), CjkCharMorphemizer(), VietnameseMorphemizer()]

        for m in morphemizers:
            morphemizers_by_name[m.getName()] = m

    return morphemizers

def getMorphemizerByName(name):
    # type: (str) -> Optional(Morphemizer)
    getAllMorphemizers()
    return morphemizers_by_name.get(name, None)


####################################################################################################
# Mecab Morphemizer
####################################################################################################

space_char_regex = re.compile(' ')

class MecabMorphemizer(Morphemizer):
    """
    Because in japanese there are no spaces to differentiate between morphemes,
    a extra tool called 'mecab' has to be used.
    """

    def _getMorphemesFromExpr(self, expression):
        # Remove simple spaces that could be added by other add-ons and break the parsing.
        if space_char_regex.search(expression):
            expression = space_char_regex.sub('', expression)

        return getMorphemesMecab(expression)

    def getDescription(self):
        try:
            identity = getMecabIdentity()
        except:
            identity = 'UNAVAILABLE'
        return 'Japanese ' + identity


####################################################################################################
# Space Morphemizer
####################################################################################################

class SpaceMorphemizer(Morphemizer):
    """
    Morphemizer for languages that use spaces (English, German, Spanish, ...). Because it is
    a general-use-morphemizer, it can't generate the base form from inflection.
    """

    def _getMorphemesFromExpr(self, expression):
        word_list = [word.lower()
                     for word in re.findall(r"\b[^\s\d]+\b", expression, re.UNICODE)]
        return [Morpheme(word, word, word, word, 'UNKNOWN', 'UNKNOWN') for word in word_list]

    def getDescription(self):
        return 'Language w/ Spaces'

####################################################################################################
# Vietnamese Morphemizer
####################################################################################################

class VietnameseMorphemizer(Morphemizer):
    """
    Vietnamese contains many compound words where the polysyllabic morphemes are divided by spaces,
    so the words in frequency.txt are used to identify words in expressions.
    """

    _known_words = []
    _known_words_underscored = []
    
    def __init__(self):
        super().__init__()
        try:
            frequencyListPath = cfg('path_frequency')
            with io.open(frequencyListPath, encoding='utf-8-sig') as csvfile:
                frequency_map = {}
                csvreader = csv.reader(csvfile, delimiter="\t")
                rows = [row for row in csvreader]

                if rows[0][0] != "#study_plan_frequency":
                    frequency_map = dict(zip([row[0] for row in rows], itertools.count(0)))
                    self._setKnownWords(list(frequency_map.keys()))

        except (FileNotFoundError, IndexError) as e:
            pass
    
    def _setKnownWords(self, words):
        words.sort(key=len)
        words.reverse()
        for word in words:
            # Only include words that contain spaces
            if ' ' in word:
                self._known_words.append(word)
                self._known_words_underscored.append(word.replace(' ', '_'))

    def _getMorphemesFromExpr(self, expression):
        e_low = expression.lower()
        for i, word in enumerate(self._known_words):
            e_low = e_low.replace(word, self._known_words_underscored[i])
        
        tokens = SpaceMorphemizer._getMorphemesFromExpr(self, e_low)
        for word in tokens:
            word.base = word.base.replace('_', ' ')
        
        return tokens

    def getDescription(self):
        return 'Vietnamese'

####################################################################################################
# CJK Character Morphemizer
####################################################################################################

class CjkCharMorphemizer(Morphemizer):
    """
    Morphemizer that splits sentence into characters and filters for Chinese-Japanese-Korean logographic/idiographic
    characters.
    """

    def _getMorphemesFromExpr(self, expression):
        return [Morpheme(character, character, character, character, 'CJK_CHAR', 'UNKNOWN') for character in
                re.findall('[%s]' % characters, expression)]

    def getDescription(self):
        return 'CJK Characters'


####################################################################################################
# Jieba Morphemizer (Chinese)
####################################################################################################

class JiebaMorphemizer(Morphemizer):
    """
    Jieba Chinese text segmentation: built to be the best Python Chinese word segmentation module.
    https://github.com/fxsjy/jieba
    """

    def _getMorphemesFromExpr(self, expression):
        # remove all punctuation
        expression = ''.join(re.findall('[%s]' % characters, expression))
        return [Morpheme(m.word, m.word, m.word, m.word, m.flag, 'UNKNOWN') for m in
                posseg.cut(expression)]  # find morphemes using jieba's POS segmenter

    def getDescription(self):
        return 'Chinese'
