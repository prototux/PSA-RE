#include "CanSignal.h"
#include <iostream>
#include <iomanip>

// CanSignal::CanSignal(/* args */)
// {
// }

CanSignal::~CanSignal()
{
}

string CanSignal::getValueMeaning(uint16_t n, const char *lang) const
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
    for (auto i=0; i<valueMeaning_.size(); i++)
    {
        std::cout << valueMeaning_[i].first << "=" << getValueMeaning(i, "en") << ", ";
    }
    std::cout << std::endl;
}

void CanSignal::setName(string name)
{
    name_ = name;
}

void CanSignal::setType(string type)
{
    type_ = type;
}

void CanSignal::addValueMeaning(int16_t value, vector<LanguageField> meanings)
{
    valueMeaning_.push_back(make_pair(value, meanings));
}
