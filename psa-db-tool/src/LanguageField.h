#pragma once

#include <string>

namespace std
{
    class LanguageField
    {
    public:
        LanguageField(const char *lang, string text);
        ~LanguageField();

        const char* getLanguage() const { return &language_[0]; }
        bool isLanguageEqual(const char *lang) const;
        string getText()     const { return text_; }
    private:
        char language_[2];
        string text_;
    };
} // namespace std
