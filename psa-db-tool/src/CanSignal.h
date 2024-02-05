#pragma once

#include <string>
#include <vector>
#include <utility>
#include "LanguageField.h"

using namespace std;

// class CanSignalMeaning
// {
// public:
//     CanSignalMeaning(uint16_t value) : value_(value) {}
//     ~CanSignalMeaning() {}

//     string getMeaning() { return valueMeaning_[0].getText(); }      // TODO
//     void addMeaning(LanguageField meaning) {valueMeaning_.push_back(meaning); }

// private:
//     uint16_t value_;
//     vector<LanguageField> valueMeaning_;
// };

class CanSignal
{
public:
    CanSignal(string n = "") : name_ (n) {}
    ~CanSignal();

    string  getName()               const { return name_; }
    string  getType()               const { return type_; }
    uint16_t getStartByte()          const { return startByte_; }
    uint16_t getStartBit()           const { return startBit_; }
    // uint16_t getDbcStartPosition()   const;
    uint16_t getEndByte()            const { return endByte_; }
    uint16_t getEndBit()             const { return endBit_; }
    bool    getIsLittleEndian()     const { return isLittleEndian_; }
    float   getFactor()             const { return factor_; }
    int16_t getOffset()            const { return offset_; }
    int16_t getMin()               const { return min_; }
    int16_t getMax()               const { return max_; }
    string  getUnits()             const { return units_; }
    // uint16_t getValueCount()       const { return valueMeaning_.size(); }
    // int16_t getValue(uint16_t n)   const { return valueMeaning_[n].first; }
    string getValueMeaning(uint16_t n, const char *lang) const;

    void    print() const;

    void    setName(string name);
    void    setType(string type);
    void    setStartByte(uint16_t startByte) { startByte_ = startByte; }
    void    setStartBit(uint16_t startBit) { startBit_ = startBit; }
    void    setEndByte(uint16_t endByte) { endByte_ = endByte; }
    void    setEndBit(uint16_t endBit) { endBit_ = endBit; }
    void    setIsLittleEndian(bool isLittleEndian) { isLittleEndian_ = isLittleEndian; }
    void    setFactor(float factor) { factor_ = factor; }
    void    setOffset(int16_t offset) { offset_ = offset; }
    void    setMin(int16_t min) { min_ = min; }
    void    setMax(int16_t max) { max_ = max; }
    void    setUnits(string units) { units_ = units; }
    void    addValueMeaning(int16_t value, vector<LanguageField> meanings);
    
private:
    string name_;
    pair<char[2], string> comment_;      // vector
    string type_;
    uint16_t startByte_;
    uint16_t startBit_;
    uint16_t endByte_;
    uint16_t endBit_;
    // short lenInBits;
    bool isLittleEndian_;
    float factor_;
    int16_t offset_;
    int16_t min_;
    int16_t max_;
    string units_;
    vector<pair<int16_t, vector<LanguageField>>> valueMeaning_;
    // vector<CanSignalMeaning> values;
};

