#pragma once

#include <string>

class LanguageField
{
public:
    LanguageField(const char *lang, std::string text);
    ~LanguageField();

    const char* getLanguage() const { return &language_[0]; }
    bool isLanguageEqual(const char *lang) const;
    std::string getText()     const { return text_; }
private:
    char language_[2];
    std::string text_;
};
