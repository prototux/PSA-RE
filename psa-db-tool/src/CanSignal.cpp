#include "CanSignal.h"
#include <iostream>
#include <iomanip>

CanSignal::~CanSignal()
{
}

std::string CanSignal::getComment(const char *lang) const
{
    for (size_t i=0; i<comment_.size(); i++)
    {
        if (comment_.at(i).isLanguageEqual(lang))
            return comment_.at(i).getText();
    }
    return "";
}

uint16_t CanSignal::getValueNumber(uint16_t n) const
{
    return valueMeaning_[n].first;
}

std::string CanSignal::getValueMeaning(uint16_t n, const char *lang) const
{
    for (size_t i=0; i<valueMeaning_[n].second.size(); i++)
    {
        if (valueMeaning_[n].second.at(i).isLanguageEqual(lang))
            return valueMeaning_[n].second.at(i).getText();
    }
    return "";
}

void CanSignal::print() const
{
    std::cout << std::setw(20) << name_ << ' ';
    std::cout << startByte_ << "." << startBit_ << "-";
    std::cout << endByte_ << "." << endBit_ << ' ';
    std::cout << std::setw(5) << type_ << ' ';
    std::cout << std::setw(7) << factor_ << ' ';
    std::cout << std::setw(7) << offset_ << ' ';
    std::cout << std::setw(6) << min_ << ' ';
    std::cout << std::setw(6) << max_ << ' ';
    std::cout << std::setw(7) << units_ << ' ';
    std::cout << std::setw(10) << getComment("en") << ' ';
    for (auto i=0; i<valueMeaning_.size(); i++)
    {
        std::cout << valueMeaning_[i].first << "=" << getValueMeaning(i, "en") << ", ";
    }
    std::cout << std::endl;
}

void CanSignal::addValueMeaning(int16_t value, std::vector<LanguageField> meanings)
{
    valueMeaning_.push_back(make_pair(value, meanings));
}
