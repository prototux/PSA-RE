#include "LanguageField.h"
#include <cstring>

namespace std
{
    LanguageField::LanguageField(const char* lang, string text)
    {
        // if (lang.length() > 3)
        //     cout << "Language name is too long." << endl;
        // else
        // {
        //     // strcpy(language_, lang.c_str());
        //     language_ = lang;
        //     text_ = text;
        // }
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
} // namespace std