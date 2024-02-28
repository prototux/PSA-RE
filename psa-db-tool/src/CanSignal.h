#pragma once

#include <string>
#include <vector>
#include <utility>
#include "LanguageField.h"

class CanSignal
{
public:
    CanSignal(std::string n = "") : name_ (n) {}
    ~CanSignal();

    std::string  getName()         const { return name_; }
    std::string  getComment(const char *lang) const;
    std::string  getType()         const { return type_; }
    int16_t getStartByte()        const { return startByte_; }
    int16_t getStartBit()         const { return startBit_; }
    int16_t getEndByte()          const { return endByte_; }
    int16_t getEndBit()           const { return endBit_; }
    bool    getIsLittleEndian()    const { return isLittleEndian_; }
    float   getFactor()            const { return factor_; }
    int16_t getOffset()            const { return offset_; }
    int16_t getMin()               const { return min_; }
    int16_t getMax()               const { return max_; }
    std::string getUnits()         const { return units_; }
    size_t getValueCount()         const { return valueMeaning_.size(); }
    uint16_t getValueNumber(uint16_t n) const;
    std::string getValueMeaning(uint16_t n, const char *lang) const;

    void    print() const;

    void    setName(std::string name)        { name_ = name; }
    void    setComment(std::vector<LanguageField> comment) { comment_ = comment; }
    void    setType(std::string type)        { type_ = type; }
    void    setStartByte(int16_t startByte) { startByte_ = startByte; }
    void    setStartBit(int16_t startBit)   { startBit_ = startBit; }
    void    setEndByte(int16_t endByte)     { endByte_ = endByte; }
    void    setEndBit(int16_t endBit)       { endBit_ = endBit; }
    void    setIsLittleEndian(bool isLittleEndian) { isLittleEndian_ = isLittleEndian; }
    void    setFactor(float factor)          { factor_ = factor; }
    void    setOffset(int16_t offset)        { offset_ = offset; }
    void    setMin(int16_t min)              { min_ = min; }
    void    setMax(int16_t max)              { max_ = max; }
    void    setUnits(std::string units)      { units_ = units; }
    void    addValueMeaning(int16_t value, std::vector<LanguageField> meanings);
    
private:
    std::string name_;
    std::vector<LanguageField> comment_;
    std::string type_;
    int16_t startByte_;
    int16_t startBit_;
    int16_t endByte_;
    int16_t endBit_;
    bool isLittleEndian_;
    float factor_;
    int16_t offset_;
    int16_t min_;
    int16_t max_;
    std::string units_;
    std::vector<std::pair<int16_t, std::vector<LanguageField>>> valueMeaning_;
};

