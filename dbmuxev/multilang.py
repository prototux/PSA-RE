"""Translated texts (the 'multilang' type: {'en': ..., 'fr': ...})"""

__all__ = ['MultiLang', 'LANGUAGES', 'set_language', 'get_language']

# languages used in the PSA repositories, 'en' is mandatory and 'fr' strongly recommended
LANGUAGES = ('en', 'fr', 'es', 'de', 'it', 'pl', 'ru', 'zh', 'hu', 'pt')

_language = 'en'


def set_language(lang):
    """Default language used by str(MultiLang) and by the decoders (labels)"""
    global _language
    _language = lang


def get_language():
    return _language


class MultiLang(dict):
    """A translated text: a dict language code -> text, 'en' first.

    ``str(text)`` gives the text in the default language (see :func:`set_language`),
    falling back to english.
    """

    @classmethod
    def of(cls, value):
        """MultiLang from a dict, a plain string (english) or None"""
        if value is None or isinstance(value, cls):
            return value
        if isinstance(value, str):
            return cls(en=value)
        if isinstance(value, dict):
            return cls(value)
        raise TypeError(f'cannot make a translated text from {value!r}')

    def get_text(self, lang=None, fallback=True):
        """Text in ``lang`` (default language when None); english, then any text, when missing and fallback is True"""
        lang = lang or _language
        if self.get(lang):
            return self[lang]
        if '-' in lang and self.get(lang.split('-')[0]):
            return self[lang.split('-')[0]]
        if not fallback:
            return None
        return self.get('en') or next((v for v in self.values() if isinstance(v, str)), None)

    def text(self, lang=None):
        return self.get_text(lang) or ''

    @property
    def languages(self):
        return [k for k in self if isinstance(k, str)]

    def missing(self, langs=('en', 'fr')):
        return [lang for lang in langs if not self.get(lang)]

    def matches(self, text):
        """True if ``text`` equals one of the translations (case insensitive)"""
        t = str(text).strip().casefold()
        return any(isinstance(v, str) and v.strip().casefold() == t for v in self.values())

    def to_dict(self):
        return dict(self)

    def __str__(self):
        return self.text()

    def __repr__(self):
        return f'MultiLang({dict.__repr__(self)})'
