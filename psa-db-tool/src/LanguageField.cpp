#include "LanguageField.h"
#include <cstring>

LanguageField::LanguageField(const char* lang, std::string text)
{
    memcpy(language_, lang, 2);
    text_ = text;
}

LanguageField::~LanguageField()
{
}

bool LanguageField::isLanguageEqual(const char *lang) const
{
    return (0 == strncmp(language_, lang, sizeof(language_)));
}
