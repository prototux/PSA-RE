#pragma once

#include <string>
#include "CanSignal.h"
#include "LanguageField.h"

class CanFrame
{
public:
    CanFrame() {}
    ~CanFrame() {}

    uint16_t    getHexId()        const { return hexId_; }
    std::string getName()         const { return name_; }
    void        printAltNames()   const;
    uint16_t    getLength()       const { return length_; }
    std::string getComment(const char *lang) const;
    std::string getType()         const { return type_; }
    std::string getPeriod()       const { return period_; }

    std::vector<std::string> getSenders() const { return senders_; }
    std::vector<CanSignal> getSignals() const { return signals_; }
    void        print()           const;
    void        printSenders()    const;
    void        printReceivers()  const;

    void    setHexId(uint16_t hexId)           { hexId_ = hexId; }
    // void    setHexId(string hexId)        { hexId_ = stoi(hexId, nullptr, 16); }
    void    setName(std::string name)          { name_ = name; }
    void    addAltName(std::string name)       { altNames_.push_back(name); }
    void    setLength(uint16_t length)         { length_ = length; }
    void    addComment(LanguageField comment)  { comments_.push_back(comment); }
    void    setType(std::string type)          { type_ = type; }
    void    setPeriod(std::string period)      { period_ = period; }
    void    addSender(std::string sender)      { senders_.push_back(sender); }
    void    addReceiver(std::string receiver)  { receivers_.push_back(receiver); }
    void    addSignal(CanSignal signal)        { signals_.push_back(signal); }

    bool    isFrameInvalid() const;

private:
    uint16_t hexId_ = 0xFFFF;
    std::string name_;
    std::vector<std::string> altNames_;
    uint16_t length_ = 0xFFFF;
    std::vector<LanguageField> comments_;
    std::string type_;
    std::string period_;
    std::vector<std::string> senders_;
    std::vector<std::string> receivers_;
    std::vector<CanSignal> signals_;

    void printVector(std::vector<std::string> someVector) const;
};
